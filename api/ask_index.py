"""Ask CIP's map of what the surveys asked, and its store of exact counts.

Who calls it: api/assistant.py (POST /api/v1/ask). Built from the ETL's published question files
(api/v1/questions/<family>/<study type>/<code>.json.gz: one question across every wave and cut, with the people who
gave each answer and the base), the published waves list, the topic words of config/dashboards.yml and
config/sectors.yml, and the synonyms of config/search_synonyms.yml. Nothing here reads the database.

  find()    ranks every question for a question's words: each word scores by how rare it is (idf) in the field it is
            found in (wording 3, topic 2.5, answers 2, older wording 1.5); synonyms count as the word; a misspelt word
            is corrected to the closest known one. Then what the question asks moves the ranking: a recent question
            for "latest"/"last N", one asked in the period named, one asked over many waves for a trend.
            An inverted index (word → questions): a few milliseconds for thousands of questions.
  versions  a code that older surveys reused for a different question (Q14 was once GenAI at work, once ways to save)
            is split by wording: wordings at least SAME_WORDING alike stay one question (a year or a brand changed in
            the text), others become their own entry, each with only its own waves and answers.
  counts()  a question file's cells as numpy arrays, parsed on first use and kept in a byte-capped cache
            (COUNT_CACHE_MB), so a question read again costs nothing and memory never grows past the cap.
"""
from __future__ import annotations

import difflib
import gzip
import hashlib
import json
import logging
import math
import re
import threading
from collections import OrderedDict
from datetime import date
from pathlib import Path

import numpy as np
import yaml

from api import ask_model, ask_reader

log = logging.getLogger("cip.ask")
CONFIG = Path(__file__).resolve().parents[1] / "config"
SAME_IGNORES = frozenset("select all that apply only one or none of these the a an".split())   # not what a question asks
WORD_CANDIDATES = 4  # retrieval: candidates from the keyword ranking the meaning ones missed (names, "dining out")
AREAS = ["retailers", "shopping categories", "online and ecommerce", "grocery and food", "apparel", "beauty", "home",
         "holidays and events", "deals and promotions", "genai and technology", "health and glp-1", "personal finances",
         "economy and prices", "tariffs", "social media shopping", "travel and leisure", "demographics", "other"]   # etl/ask_semantic.py TOPICS
AREA_BOOST = 0.03   # retrieval: added for a question in the asked question's business area
ASK_WEIGHT = 0.3    # retrieval: the nearest ask's share of closeness; golden set right first 109 alone, 118 at 0.3, 97 at max (12 Nov 2026)
VERIFIED = CONFIG / "ask_verified.yml"   # approved question → answer plans (reviewed in git); admins add more at runtime
LEARNED = ask_model.LOGS / "ask-learned.json"   # questions the AI check settled: the same or a close question is answered from them at once
VERIFIED_NEAR = 0.91   # closeness in meaning (local model) from which a question is a verified one (with the same names and
                       # groups): "Holiday spending expectations" is 0.903 from the holiday finances one, a different question
STANDING = 0.06     # retrieval: up to this added to a closeness (~0.5–0.8) for a question asked a year of waves and still asked
SAME_ANSWERS = 0.6   # share of a wave's answers that must be the question's own for the wave to join its series
SAME_WORDING = 0.5   # shared words / all words: "holiday 2025" vs "holiday 2026" stays one question, a reused code does not
UNIT_ONLY = {"$", "%", "#"}   # a typed-number question loaded without its numbers: its one "answer" is the unit, chosen by 100%
COUNT_CACHE_MB = 48   # parsed question files kept in memory; the largest (q1, every tracker wave) is ~4 MB
FIELDS = {"name": 3.5, "text": 3.0, "topic": 2.5, "answers": 2.0, "older": 1.5}   # name: the semantic layer's business name and aliases
# words that frame a question rather than name its subject ("Should we act on tariff concerns? Show the latest numbers"):
# left out on both sides when a question is matched to a survey question's name (Index.named)
# words that tell two questions apart though the reader drops them from a subject ("spend more" vs "spend less" on categories)
DIRECTION_WORDS = frozenset("more less fewer increase increased decrease decreased higher lower".split())
FRAME_WORDS = frozenset("""should we act say said says chose choose chosen answers answer among over indexes index grown grow rising
falling going up down trend top numbers number base figures latest about consumers people think feel different differ likely
tell change changed over-indexes over-index""".split())
SEMANTIC = CONFIG / "ask_semantic.json"   # etl/ask_semantic.py: a business name, aliases and topic per question wording
SEMANTIC_ADDED = ask_model.LOGS / "ask-semantic.json"   # the same, for wordings named after a publish (etl/ask_quality.py)
STOP = set("""about above after again against also among answer answers been before being below between both could
    during each from further have having here into itself just more most other over same should some such than that their
    them then there these they this those through under until very were what when where which while whom will with would
    your yours following past select apply""".split())


def digest(text: str) -> str:
    """A question wording's key in config/ask_semantic.json: the same wording under any code shares one entry."""
    return hashlib.sha1(" ".join(text.lower().split()).encode()).hexdigest()[:12]


def read_json(path: Path) -> dict:
    """A JSON file's content, {} when it is missing or unreadable."""
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def name_key(text: str) -> str:
    """A subject as the name table holds it: the reader's subject words (api/ask_reader.py read), frame words left out,
    and a year that names the subject rather than a period ("Holiday spending 2025" is not "Holiday spending 2024")."""
    text = re.sub(r"[\u201c\"][^\u201d\"]*[\u201d\"]|\b(more|less) likely\b", " ", text)   # a quoted answer ("Yes") is not the subject
    plan = ask_reader.read(text)
    years = {y for y in re.findall(r"\b20[12]\d\b", text) if y not in repr(plan["when"])}
    direction = DIRECTION_WORDS & set(re.findall(r"[a-z]+", text.lower()))
    # a set, in order: "Categories for online shopping" and "online shopping categories" are one name
    return " ".join(sorted({w for w in plan["about"].split() if w not in FRAME_WORDS} | years | direction))


def stems(text: str) -> list[str]:
    """Words cut to five letters, so shopped/shopping and retailer/retailers meet; short words stay whole."""
    return [w[:5] for w in re.findall(r"[a-z0-9]+", text.lower().replace("'", "")) if (len(w) >= 3 or w.isdigit()) and w not in STOP]


def topic_words() -> dict[str, list[str]]:
    """question code → the dashboard titles and sector names (with their table names) that show it."""
    words: dict[str, list[str]] = {}
    for board in (yaml.safe_load((CONFIG / "dashboards.yml").read_text()) or {}).values():
        if isinstance(board, dict):
            for part in (board.get("tiles") or []) + (board.get("lists") or []):   # "Holiday Survey Databank Progress: have started"
                said = " ".join(str(part.get(k, "")) for k in ("head", "label", "say", "tile"))
                words.setdefault(str(part.get("qcode", "")).upper(), []).append(f"{board.get('title', '')} {said}")
    report = yaml.safe_load((CONFIG / "weekly_report.yml").read_text()) or {}
    for part in report.get("sections", []):
        words.setdefault(str(part["question"]).upper(), []).append(f"weekly report {part['part']} {part['name']}")
    for name, code in (report.get("sentiment") or {}).items():
        words.setdefault(str(code).upper(), []).append(f"weekly report consumer sentiment {name} net better worse")
    for sector in (yaml.safe_load((CONFIG / "sectors.yml").read_text()) or {}).get("sectors", []):
        name = sector["name"]
        if sector.get("purchase"):
            words.setdefault(str(sector["purchase"]["question"]).upper(), []).append(f"{name} sector purchase rate bought")
        for tab, code in (sector.get("tables") or {}).items():
            words.setdefault(str(code).upper(), []).append(f"{name} sector {tab}")
    return words


def synonym_groups() -> dict[str, set[str]]:
    """stem → every stem of its synonym groups (config/search_synonyms.yml), phrases split into words."""
    groups = (yaml.safe_load((CONFIG / "search_synonyms.yml").read_text()) or {}).get("groups", [])
    out: dict[str, set[str]] = {}
    for group in groups:
        members = {s for term in group for s in stems(str(term))}
        for s in members:
            out.setdefault(s, set()).update(members)
    return out


def in_period(spec: dict, dates: list[str]) -> bool:
    """Whether any of a question's wave dates falls in a named year, month, quarter or range."""
    if "year" in spec:
        lo, hi = f"{spec['year']}-01-01", f"{spec['year']}-12-31"
    elif "month" in spec:
        lo, hi = f"{spec['month'][0]}-{spec['month'][1]:02d}-01", f"{spec['month'][0]}-{spec['month'][1]:02d}-31"
    elif "quarter" in spec:
        y, q = spec["quarter"]
        lo, hi = f"{y}-{3 * q - 2:02d}-01", f"{y}-{3 * q:02d}-31"
    elif "from" in spec:
        lo, hi = spec["from"], spec["to"]
    else:
        return False
    return any(lo <= d <= hi for d in dates)


def wording_groups(versions: list[str]) -> list[list[int]]:
    """Version numbers (1-based, as the waves carry them) grouped by alike wording, in first-asked order."""
    words = [set(re.findall(r"[a-z]+", text.lower())) for text in versions]
    alike_words = lambda a, b: len(a & b) / max(len(a | b), 1) >= SAME_WORDING   # noqa: E731
    groups: list[list[int]] = []
    for v, text in enumerate(versions, start=1):
        alike = next((g for g in groups if alike_words(words[g[-1] - 1], words[v - 1])), None)
        if alike is None:
            groups.append([v])
        else:
            alike.append(v)
    return groups


class Index:
    """Every published question, ranked for a question, with where its counts are."""

    def __init__(self, root: Path, waves: list[dict]):
        self.root = root
        self.lock = threading.Lock()
        self.cache: OrderedDict[str, dict] = OrderedDict()
        self.cached_bytes = 0
        self.synonyms = synonym_groups()
        known = {w["survey_id"]: {**w, "wave_date": str(w["wave_date"])[:10]} for w in waves}   # the API's list has dates
        self.country = {sid: w.get("country") or "US" for sid, w in known.items()}   # api/assistant.py answer: one country a question
        topics = topic_words()
        parts: dict[str, dict] = {}                        # one per file and wording: where the counts are
        part_words: dict[str, dict[str, str]] = {}         # its searchable fields
        for path in sorted(root.glob("*/*/*.json.gz")):
            family, study_type, qcode = path.parts[-3], path.parts[-2], path.name[:-len(".json.gz")]
            try:
                data = json.loads(gzip.decompress(path.read_bytes()))
            except (OSError, ValueError):
                log.warning("Ask CIP: unreadable question file %s", path)
                continue
            file = f"{family}/{study_type}/{qcode}"
            groups = wording_groups(data["versions"])
            for g, versions in enumerate(groups):
                asked = [known[w[0]] for w in data["waves"] if w[0] in known and w[2] in versions]
                if not asked:
                    continue
                key = file if len(groups) == 1 else f"{file}#{g + 1}"
                waves_in = {i for i, w in enumerate(data["waves"]) if w[2] in versions}
                used = {a for w, a in zip(data["w"], data["a"]) if w in waves_in}
                if all(data["answers"][a][2].strip() in UNIT_ONLY for a in used):
                    continue   # "How much, in dollars…" holds no amounts (28 such questions, 12 Nov 2026): never quote "$ 100%"
                labels = {data["answers"][a][2] for a in used} | {data["answers"][a][0] for a in used if data["answers"][a][0]}
                texts = [data["versions"][v - 1] for v in versions]
                shown = [f"{data['answers'][a][0]}: {data['answers'][a][2]}" if data["answers"][a][0] and data["answers"][a][0] != data["answers"][a][2]
                         else data["answers"][a][2] for a in sorted(used)]   # as api/ask_figures.py names them
                by_wave: dict[int, set[str]] = {}   # each wave's own answers (Total), to tell a reused code's waves apart
                for w, c, a in zip(data["w"], data["c"], data["a"]):
                    if c == 0 and w in waves_in:
                        by_wave.setdefault(data["waves"][w][0], set()).add(data["answers"][a][2])
                parts[key] = {"key": key, "file": file, "labels": shown, "cuts": {c[0] for c in data["cuts"]}, "wave_answers": by_wave, "versions": versions, "qcode": qcode, "family": family,
                                  "study_type": study_type, "text": texts[-1], "first": asked[0]["wave_date"],
                                  "title": family.replace("_", " ").title(),
                                  "last": asked[-1]["wave_date"], "waves": len(asked),
                                  "surveys": [w["survey_id"] for w in asked], "dates": [w["wave_date"] for w in asked]}
                part_words[key] = {"text": texts[-1], "topic": " ".join(topics.get(qcode.upper(), []) + [family.replace("_", " ").replace("-", " ")]),
                                   "answers": " ".join(labels), "older": " ".join(texts[:-1])}
        named = {**read_json(SEMANTIC), **read_json(SEMANTIC_ADDED)}   # a publish's new names and renames (etl/ask_semantic.py) over the config
        for part in parts.values():   # the semantic layer: what analysts call it, how else they say it, its topic
            entry = named.get(digest(part["text"]), {})
            part.update(name=entry.get("name", ""), aliases=entry.get("aliases", []), area=entry.get("topic", ""), asks=entry.get("asks", []))
            part_words[part["key"]]["name"] = " ".join([part["name"], *part["aliases"]])
        # one entry per question whatever code it was asked under: the same wording in the same study (q5 since 2024, Q5
        # before) is one series, so "all waves" means all of them
        self.docs: dict[str, dict] = {}
        self.postings: dict[str, dict[str, float]] = {}   # stem → {question key: best field weight}
        same: dict[tuple, list[dict]] = {}
        for part in parts.values():
            words = frozenset(re.findall(r"[a-z0-9]+", part["text"].lower())) - SAME_IGNORES
            same.setdefault((part["family"], part["study_type"], words), []).append(part)
        for group in same.values():
            group.sort(key=lambda p: p["first"])
            last = max(group, key=lambda p: p["last"])
            # a wave counts only when most of its answers are this question's own, as its newest wave asks it: older
            # waves reused codes for other questions, and their files mix them (Q22 "economy" holding Easter answers)
            own = {a.lower() for a in last["wave_answers"].get(last["surveys"][-1], ())}
            for p in group:
                p["keep"] = {sid for sid, answers in p["wave_answers"].items()
                             if len({a.lower() for a in answers} & own) >= SAME_ANSWERS * max(len(answers), 1)}
            group = [p for p in group if p["keep"]]
            if not group:   # no wave with its own answers (no Total row): nothing to answer from
                continue
            kept = sorted((d, sid) for p in group for sid, d in zip(p["surveys"], p["dates"]) if sid in p["keep"])
            surveys = [sid for _, sid in kept]
            dates = [d for d, _ in kept]
            key = last["key"]
            labels = {a.lower(): a for p in group for sid, answers in p["wave_answers"].items() if sid in p["keep"] for a in answers}
            self.docs[key] = {**last, "labels": [l for l in last["labels"] if l.split(": ")[-1].lower() in labels] or last["labels"],
                              "parts": [p["key"] for p in group], "codes": list(dict.fromkeys(p["qcode"] for p in group)),
                              "first": min(dates), "last": max(dates), "waves": len(set(surveys)), "surveys": surveys, "dates": sorted(dates)}
            for p in group:
                for field, words in part_words[p["key"]].items():
                    for s in set(stems(words)):
                        held = self.postings.setdefault(s, {})
                        held[key] = max(held.get(key, 0.0), FIELDS[field])
        self.parts = parts
        self.vectors = self.verified_vectors = None   # keyword ranking until add_vectors has run (retrieve, verified_for)
        self.vector_keys, self.verified = [], []
        self.embed_text = {key: f"{doc['name']}; {'; '.join(doc['aliases'])}. {doc['text']} | answers: {'; '.join(doc['labels'])[:300]}"
                           for key, doc in self.docs.items()}
        # the stored patterns: each survey question's analyst name and aliases, as a question's subject reads (name_key),
        # to its survey questions, longest-running first. A question whose subject is one of them is answered from it at
        # once; its periods, cuts and kind still come from the question (etl/ask_quality.py tests every one)
        self.names: dict[str, list[str]] = {}
        for key, doc in sorted(self.docs.items(), key=lambda kv: (kv[1]["waves"], kv[1]["last"]), reverse=True):
            for name in dict.fromkeys([doc["name"], *doc["aliases"]]):
                pattern = name_key(name)
                if pattern and key not in self.names.get(pattern, []):
                    self.names.setdefault(pattern, []).append(key)
        words = {key: set(re.findall(r"[a-z0-9]+", doc["text"].lower())) - SAME_IGNORES for key, doc in self.docs.items()}
        alike = lambda a, b: len(words[a] & words[b]) >= SAME_WORDING * len(words[a] | words[b])   # noqa: E731
        # a name two different questions share ("Economic outlook": the economy, and the pace of price rises) is left to the
        # search; the same question asked by several studies (Amazon Prime) keeps the name
        # names two different questions share ("Economic outlook": the economy, and the pace of price rises; "Valentine's Day
        # spending expectations" 2021 and 2023): used only when the question's period leaves questions alike (named)
        self.ambiguous = {p for p, keys in self.names.items() if not all(alike(keys[0], k) for k in keys[1:])}
        self.alike = alike
        self.name_words = {p: frozenset(p.split()) for p in self.names}
        self.answer_words = {key: set(re.findall(r"[a-z0-9$%'-]+", " ".join(doc["labels"]).lower())) for key, doc in self.docs.items()}
        total = max(len(self.docs), 1)
        self.idf = {s: math.log(1 + total / len(keys)) for s, keys in self.postings.items()}
        self.vocabulary = sorted({w for d in self.docs.values() for w in re.findall(r"[a-z]{4,}", d["text"].lower())}
                                 | {w for g in self.synonyms.values() for w in g if len(w) >= 4})   # whole words, to correct spelling
        self.newest = max((d["last"] for d in self.docs.values()), default="2000-01-01")
        log.info("Ask CIP index: %d questions, %d words, from %s", len(self.docs), len(self.postings), root)

    def add_vectors(self) -> None:
        """Meaning: one vector per question (api/ask_model.py), from its wording, answers and topic words, and one per
        analyst's ask (config/ask_semantic.json); a question's closeness joins its own and its nearest ask's (ASK_WEIGHT).
        api/assistant.py index_for runs it in the background: a deploy that brings ~18,000 new texts embeds them on one
        thread for minutes (12 Nov 2026), and asks are answered by the keyword ranking meanwhile, never kept waiting."""
        found = ask_model.question_vectors({**self.embed_text, **{f"ask {a}": a for doc in self.docs.values() for a in doc.get("asks", [])}}, prune=True)
        keys = [k for k in self.docs if k in found]
        owners = [(i, f"ask {a}") for i, k in enumerate(keys) for a in self.docs[k].get("asks", []) if f"ask {a}" in found]
        self.ask_owner = np.array([i for i, _ in owners], np.int32)
        self.ask_vectors = np.array([found[a] for _, a in owners], np.float32) if owners else None
        areas = ask_model.question_vectors({a: f"survey questions about {a}" for a in AREAS}) if keys else {}
        self.area_vectors = np.array([areas[a] for a in AREAS], np.float32) if len(areas) == len(AREAS) else None
        newest = date.fromisoformat(max((d["last"] for d in self.docs.values()), default="2000-01-01"))
        self.standing = np.array([STANDING * (min(math.log1p(self.docs[k]["waves"]) / math.log1p(52), 1.0)
                                              + math.exp(-(newest - date.fromisoformat(self.docs[k]["last"])).days / 365)) / 2
                                  for k in keys], np.float32)
        self.vector_keys = keys
        self.vectors = np.array([found[k] for k in keys], np.float32) if keys else None   # last: retrieve reads it first
        self.load_verified()
        model = ask_model.status()
        (log.info if model["on"] else log.warning)("Ask model %s: %s; %d questions with vectors", "ON" if model["on"] else "OFF",
                                                   f"key from {model['key_from']}, {model['model']}" if model["on"] else model["why_off"],
                                                   len(self.vector_keys))

    def known(self, word: str) -> str | None:
        """The stem a word searches by: its own, or a misspelt word's closest whole word ("amazn" → amazon), else None."""
        stem = word[:5]
        if stem in self.postings:
            return stem
        if len(word) < 5 or word.isdigit():
            return None
        close = difflib.get_close_matches(word, self.vocabulary, n=1, cutoff=0.85)   # whole words: "submarine" stays unknown
        return close[0][:5] if close and close[0][:5] in self.postings else None

    def find(self, words: str, plan: dict | None = None, limit: int = 8, visible: set[int] | None = None) -> list[dict]:
        """The best-matching questions, best first, each with its score; [] when no word of the question is known."""
        plan = plan or {}
        said = {w for w in re.findall(r"[a-z0-9]+", words.lower().replace("'", "")) if (len(w) >= 3 or w.isdigit()) and w not in STOP}
        asked = {s for s in (self.known(w) for w in said) if s}
        if not asked:
            return []
        unknown = len(said) - len(asked)   # a word no survey uses ("submarine") counts against every match: never a guess
        scores: dict[str, float] = {}
        for s in asked:
            best: dict[str, float] = {}
            for term in {s} | {x for x in self.synonyms.get(s, ()) if x in self.postings}:
                for key, field in self.postings[term].items():
                    best[key] = max(best.get(key, 0.0), field * (1.0 if term == s else 0.8))
            for key, field in best.items():
                scores[key] = scores.get(key, 0.0) + self.idf[s] * field
        weight = 3.0 * (sum(self.idf[s] for s in asked) + unknown * max(self.idf.values()))
        newest = date.fromisoformat(self.newest)
        when = plan.get("when") or []
        relative = not when or any(k in spec for spec in when for k in ("latest", "last", "all"))
        named = [spec for spec in when if not any(k in spec for k in ("latest", "last", "all", "first"))]
        series = plan.get("kind") in ("trend", "change") or bool(plan.get("grain")) or plan.get("compare") or len(when) > 1
        ranked = []
        for key, score in scores.items():
            doc = self.docs[key]
            if visible is not None and visible.isdisjoint(doc["surveys"]):
                continue
            boost = 0.05 * (doc["study_type"] == "tracker") + 0.1 * min(math.log1p(doc["waves"]) / math.log1p(52), 1.0)
            if relative:   # still asked: "latest" or "last N weeks" can be answered from it
                boost += 0.25 * math.exp(-(newest - date.fromisoformat(doc["last"])).days / 120)
            if series:     # a year of waves or more makes a trend
                boost += 0.25 * min(math.log1p(doc["waves"]) / math.log1p(52), 1.0)
            if named:
                boost += 0.3 * any(in_period(spec, doc["dates"]) for spec in named)
            ranked.append(((score / weight) * (1 + boost), key, score / weight))
        ranked.sort(reverse=True)
        said_words = set(re.findall(r"[a-z0-9]+", (plan.get("question") or words).lower()))
        close = []   # the best few re-ranked by how much of their own wording the question uses: typing a survey's
        for score, key, match in ranked[:30]:   # exact text finds that question even beside a near-twin
            own = set(re.findall(r"[a-z0-9]+", self.docs[key]["text"].lower()))
            close.append((score + 0.5 * len(own & said_words) / max(len(own | said_words), 1), key, match))
        close.sort(reverse=True)
        # match: the share of the question's words found (1.0 = all in the wording), before any boost: "not in the surveys" test
        return [{**self.docs[key], "score": round(score, 3), "match": round(match, 3)} for score, key, match in close[:limit]]

    def retrieve(self, question: str, plan: dict | None, limit: int, visible: set[int] | None, asked: np.ndarray | None = None) -> list[dict]:
        """The candidates for a question: its nearest survey questions by meaning (vectors) joined with the keyword
        ranking (find), best first; the keyword ranking alone when there are no vectors or the model is off. `asked`:
        the question's vector when the caller has it already (api/assistant.py embeds once per question)."""
        words = self.find(question, plan, limit, visible)
        if self.vectors is None:
            return words
        if asked is None:
            made = ask_model.embed([question])
            asked = made[0] if made is not None else None
        if asked is None:
            return words
        near = self.vectors @ asked
        if self.ask_vectors is not None:   # joined with its nearest analyst's ask
            nearest_ask = near.copy()
            np.maximum.at(nearest_ask, self.ask_owner, self.ask_vectors @ asked)
            near = (1 - ASK_WEIGHT) * near + ASK_WEIGHT * nearest_ask
        near = near + self.standing   # plus a little for long-running and recent questions
        if self.area_vectors is not None:   # the question's business area (Uber's "workspaces"): its questions a little ahead
            area = AREAS[int(np.argmax(self.area_vectors @ asked))]
            near = near + AREA_BOOST * np.array([self.docs[k]["area"] == area for k in self.vector_keys], np.float32)
        seen = {}
        for i in np.argsort(-near):
            doc = self.docs[self.vector_keys[i]]
            if visible is None or not visible.isdisjoint(doc["surveys"]):
                seen[doc["key"]] = {**doc, "near": round(float(near[i]), 3)}
            if len(seen) >= limit:
                break
        out = list(seen.values())
        for w in words:   # a name the vectors rank low ("Costco") still comes in through its words
            if w["key"] not in seen:
                out.append(w)
        return out[:limit + WORD_CANDIDATES]   # the nearest by meaning, and a few found only by their words ("Costco")

    def named(self, question: str, visible: set[int], plan: dict | None = None) -> tuple[str | None, bool]:
        """(survey question, sure) for a question that uses a survey question's analyst name or an alias, else (None,
        False). The name may be the whole subject, or sit among that question's own answers ("Are women or men more
        likely to choose Toys or games for categories purchased from mass merchandisers?"; two words or more, the
        longest wins). Of the studies holding the name, the first (longest-running) this person may see that can answer:
        asked in the period named, holding the cut, with history for a trend. sure: the name is that question's alone,
        or the period leaves only questions alike; a name different questions share ("Recent clothing purchases") gives
        the longest-running, not sure: a best match, the others listed. ~1 ms."""
        subject = name_key(question)
        words = set(subject.split())
        keys = self.names.get(subject)
        if not keys:
            inside = [(len(n), p) for p, n in self.name_words.items() if len(n) >= 2 and n <= words and p not in self.ambiguous
                      and words - n <= self.answer_words[self.names[p][0]]]
            keys = self.names[max(inside)[1]] if inside else []
        keys = [k for k in keys if not visible.isdisjoint(self.docs[k]["surveys"])]
        plan = plan or {}
        dated = [s for s in plan.get("when", []) if {"year", "month", "quarter", "from"} & s.keys()]
        sure = subject not in self.ambiguous
        if not sure:   # the period may leave only one of the questions sharing the name
            within = [k for k in keys if dated and all(in_period(s, self.docs[k]["dates"]) for s in dated)]
            if within and all(self.alike(within[0], k) for k in within[1:]):
                keys, sure = within, True
        trend = bool(plan.get("grain")) or plan.get("kind") == "trend"
        able = lambda k: (all(in_period(s, self.docs[k]["dates"]) for s in dated),   # noqa: E731
                          set(plan.get("cuts", {})) <= self.docs[k]["cuts"], not trend or self.docs[k]["waves"] >= 3)
        best = min(keys, key=lambda k: [not ok for ok in able(k)], default=None)
        # none holds the cut or the history asked for: the search may find a question that does ("in-store clothing by
        # quarter" is the weekly categories question, not a one-off study); not asked in the period is an answer
        return (best, sure) if best is not None and all(able(best)[1:]) else (None, False)

    def load_verified(self) -> None:
        """The verified questions (config/ask_verified.yml and the admins' additions in logs/ask-verified.json) and the
        learned ones (logs/ask-learned.json: questions the AI check settled, api/assistant.py learn), each resolved to its
        survey question by key (by code and family for the reviewed list), with its vector for matching. An admin's reading wins over a learned one."""
        listed = (yaml.safe_load(VERIFIED.read_text()) or []) if VERIFIED.exists() else []
        listed += read_json(ask_model.LOGS / "ask-verified.json") or []
        mine = {str(v.get("question", "")).lower() for v in listed}
        listed += [{**v, "learned": True} for v in read_json(LEARNED) or [] if str(v.get("question", "")).lower() not in mine]
        by_code = {}
        for key, doc in self.docs.items():
            for code in doc.get("codes", [doc["qcode"]]):
                by_code.setdefault((doc["family"], code.lower()), key)
        # a code alone is ambiguous (115 codes are reused by different studies' questions: q2, D14, Q10), so the AI's and
        # admins' entries carry the question's key; a learned entry without one resolved to the wrong study (13 Nov 2026)
        resolved = [{**v, "key": v["key"] if v.get("key") in self.docs else
                     None if v.get("learned") else by_code.get((v.get("family", "CSI-US"), str(v.get("code", "")).lower()))} for v in listed]
        self.verified = [v for v in resolved if v["key"]]
        found = ask_model.question_vectors({v["question"]: v["question"] for v in self.verified}) if self.verified else {}
        self.verified = [v for v in self.verified if v["question"] in found]
        self.verified_vectors = np.array([found[v["question"]] for v in self.verified], np.float32) if self.verified else None
        log.info("Ask verified questions: %d", len(self.verified))

    def verified_for(self, asked: np.ndarray | None) -> dict | None:
        """The verified question nearest in meaning, if at least VERIFIED_NEAR (the caller checks names and groups).
        Milliseconds: no model call."""
        if asked is None or self.verified_vectors is None:
            return None
        near = self.verified_vectors @ asked
        best = int(np.argmax(near))
        return {**self.verified[best], "near": float(near[best])} if near[best] >= VERIFIED_NEAR else None

    def counts(self, key: str) -> dict:
        """One question's cells over every code and wording it was asked under, as one series: waves (oldest first,
        [survey_id, date, n] with n its part's number), versions (each part's wording), answers and cuts matched by
        label, and the w, c, a, n, b arrays (see file_counts). Kept in the same byte-capped cache."""
        doc = self.docs[key]
        with self.lock:
            if ("q", key) in self.cache:
                self.cache.move_to_end(("q", key))
                return self.cache[("q", key)]
        waves, versions, answers, cuts, cells, seen = [], [], {}, {("total", "Total"): 0}, [], set()
        for number, part_key in enumerate(doc["parts"], start=1):
            part = self.parts[part_key]
            raw = self.file_counts(part["file"])
            versions.append(part["text"])
            wave_at = np.full(len(raw["waves"]), -1, np.int32)
            for i, (sid, day, version) in enumerate(raw["waves"]):
                if version in part["versions"] and sid in part["keep"] and sid not in seen:
                    seen.add(sid)
                    wave_at[i] = len(waves)
                    waves.append([sid, day, number])
            answer_at = np.array([answers.setdefault((item.lower(), label.lower()), (len(answers), [item, code, label]))[0]
                                  for item, code, label in raw["answers"]] or [0], np.int32)
            cut_at = np.array([cuts.setdefault((d, v), len(cuts)) for d, v in raw["cuts"]], np.int32)
            keep = wave_at[raw["w"]] >= 0
            cells.append((wave_at[raw["w"][keep]], cut_at[raw["c"][keep]], answer_at[raw["a"][keep]], raw["n"][keep], raw["b"][keep]))
        order = sorted(range(len(waves)), key=lambda i: waves[i][1])   # oldest first, whichever code asked it
        rank = np.empty(len(waves), np.int32)
        rank[order] = np.arange(len(waves))
        found = {"qcode": doc["qcode"], "waves": [waves[i] for i in order], "versions": versions,
                 "answers": [a[1] for a in sorted(answers.values())], "cuts": [list(c) for c in sorted(cuts, key=cuts.get)],
                 "w": rank[np.concatenate([c[0] for c in cells])], "c": np.concatenate([c[1] for c in cells]),
                 "a": np.concatenate([c[2] for c in cells]), "n": np.concatenate([c[3] for c in cells]),
                 "b": np.concatenate([c[4] for c in cells])}
        self.keep(("q", key), found)
        return found

    def keep(self, key, found: dict) -> None:
        size = sum(found[k].nbytes for k in "wcanb")
        with self.lock:
            self.cache[key] = found
            self.cached_bytes += size
            while self.cached_bytes > COUNT_CACHE_MB * 2**20 and len(self.cache) > 1:
                _, old = self.cache.popitem(last=False)
                self.cached_bytes -= sum(old[k].nbytes for k in "wcanb")

    def file_counts(self, key: str) -> dict:
        """One question file as arrays: waves [[survey_id, date, version]], versions, answers, cuts, and per cell
        w (wave index), c (cut index), a (answer index), n (people, -1 when not published), b (base). Kept per file:
        the questions split from one reused code share it."""
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key)
                return self.cache[key]
        data = json.loads(gzip.decompress((self.root / f"{key}.json.gz").read_bytes()))
        found = {k: data[k] for k in ("qcode", "waves", "versions", "answers", "cuts")}
        found.update(w=np.array(data["w"], np.int32), c=np.array(data["c"], np.int32), a=np.array(data["a"], np.int32),
                     n=np.array([-1 if x is None else x for x in data["n"]], np.int64), b=np.array(data["b"], np.int64))
        self.keep(key, found)
        return found
