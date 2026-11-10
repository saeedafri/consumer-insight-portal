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

log = logging.getLogger("cip.ask")
CONFIG = Path(__file__).resolve().parents[1] / "config"
SAME_WORDING = 0.5   # shared words / all words: "holiday 2025" vs "holiday 2026" stays one question, a reused code does not
COUNT_CACHE_MB = 48   # parsed question files kept in memory; the largest (q1, every tracker wave) is ~4 MB
FIELDS = {"text": 3.0, "topic": 2.5, "answers": 2.0, "older": 1.5}
STOP = set("""about above after again against also among answer answers been before being below between both could
    during each from further have having here into itself just more most other over same should some such than that their
    them then there these they this those through under until very were what when where which while whom will with would
    your yours following past select apply""".split())


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
        topics = topic_words()
        self.docs: dict[str, dict] = {}
        self.postings: dict[str, dict[str, float]] = {}   # stem → {question key: best field weight}
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
                labels = {data["answers"][a][2] for a in used} | {data["answers"][a][0] for a in used if data["answers"][a][0]}
                texts = [data["versions"][v - 1] for v in versions]
                self.docs[key] = {"key": key, "file": file, "versions": versions, "qcode": qcode, "family": family,
                                  "study_type": study_type, "text": texts[-1], "first": asked[0]["wave_date"],
                                  "last": asked[-1]["wave_date"], "waves": len(asked),
                                  "surveys": [w["survey_id"] for w in asked], "dates": [w["wave_date"] for w in asked]}
                fields = {"text": texts[-1], "topic": " ".join(topics.get(qcode.upper(), [])),
                          "answers": " ".join(labels), "older": " ".join(texts[:-1])}
                for field, words in fields.items():
                    for s in set(stems(words)):
                        held = self.postings.setdefault(s, {})
                        held[key] = max(held.get(key, 0.0), FIELDS[field])
        total = max(len(self.docs), 1)
        self.idf = {s: math.log(1 + total / len(keys)) for s, keys in self.postings.items()}
        self.vocabulary = sorted(self.postings)
        self.newest = max((d["last"] for d in self.docs.values()), default="2000-01-01")
        log.info("Ask CIP index: %d questions, %d words, from %s", len(self.docs), len(self.postings), root)

    def known(self, stem: str) -> str | None:
        if stem in self.postings:
            return stem
        if len(stem) < 4 or stem.isdigit():
            return None
        close = difflib.get_close_matches(stem, self.vocabulary, n=1, cutoff=0.8)
        return close[0] if close else None

    def find(self, words: str, plan: dict | None = None, limit: int = 8, visible: set[int] | None = None) -> list[dict]:
        """The best-matching questions, best first, each with its score; [] when no word of the question is known."""
        plan = plan or {}
        asked = {s for s in (self.known(s) for s in stems(words)) if s}
        if not asked:
            return []
        scores: dict[str, float] = {}
        for s in asked:
            best: dict[str, float] = {}
            for term in {s} | {x for x in self.synonyms.get(s, ()) if x in self.postings}:
                for key, field in self.postings[term].items():
                    best[key] = max(best.get(key, 0.0), field * (1.0 if term == s else 0.8))
            for key, field in best.items():
                scores[key] = scores.get(key, 0.0) + self.idf[s] * field
        weight = 3.0 * sum(self.idf[s] for s in asked)
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
            ranked.append(((score / weight) * (1 + boost), key))
        ranked.sort(reverse=True)
        said = set(re.findall(r"[a-z0-9]+", (plan.get("question") or words).lower()))
        close = []   # the best few re-ranked by how much of their own wording the question uses: typing a survey's
        for score, key in ranked[:30]:   # exact text finds that question even beside a near-twin
            own = set(re.findall(r"[a-z0-9]+", self.docs[key]["text"].lower()))
            close.append((score + 0.5 * len(own & said) / max(len(own | said), 1), key))
        close.sort(reverse=True)
        return [{**self.docs[key], "score": round(score, 3)} for score, key in close[:limit]]

    def counts(self, key: str) -> dict:
        """One question file as arrays: waves [[survey_id, date, version]], versions, answers, cuts, and per cell
        w (wave index), c (cut index), a (answer index), n (people, -1 when not published), b (base). Kept per file:
        the questions split from one reused code share it."""
        key = self.docs[key]["file"] if key in self.docs else key
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key)
                return self.cache[key]
        data = json.loads(gzip.decompress((self.root / f"{key}.json.gz").read_bytes()))
        found = {k: data[k] for k in ("qcode", "waves", "versions", "answers", "cuts")}
        found.update(w=np.array(data["w"], np.int32), c=np.array(data["c"], np.int32), a=np.array(data["a"], np.int32),
                     n=np.array([-1 if x is None else x for x in data["n"]], np.int64), b=np.array(data["b"], np.int64))
        size = sum(found[k].nbytes for k in "wcanb")
        with self.lock:
            self.cache[key] = found
            self.cached_bytes += size
            while self.cached_bytes > COUNT_CACHE_MB * 2**20 and len(self.cache) > 1:
                _, old = self.cache.popitem(last=False)
                self.cached_bytes -= sum(old[k].nbytes for k in "wcanb")
        return found
