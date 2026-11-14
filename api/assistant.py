"""Ask CIP: a question in plain words, answered from the portal's own published survey figures, with a chart.

Who calls it: api/main.py ask (POST /api/v1/ask). No database, and no AI needed: our own small models on this CPU (the
search's and the reader's, api/ask_model.py) answer in about 100 ms at no cost; the AI (optional, a key) is asked
only when the reader is unsure.

  1. read     api/ask_reader.py   the periods, grain, cuts and kind of question, by rules
  2. find     api/ask_index.py    the survey question it is about (its words, answers, topic and sector words), then
              api/ask_model.py    Ask's own reader picks among the closest (the AI only when the reader is unsure)
  3. compute  api/ask_figures.py  exact pooled figures from the published counts, for the waves this person may see
  4. write    here                sentences from the figures, the chart that fits, the sources, other matches

Every number in an answer is one of the computed figures; a question it cannot place is answered with the closest
questions, never with a guess. Answers are kept per published version, person's access and wording (ANSWERS).
"""
from __future__ import annotations

import json
import logging
import math
import os
import re
import threading
from collections import OrderedDict
from pathlib import Path

from datetime import date, timedelta

import numpy as np

from api import ask_figures, ask_model, ask_reader
from api.ask_index import LEARNED, Index, name_key, read_json, stems

log = logging.getLogger("cip.assistant")
# the reader's lead (logits) from which its pick is final and the AI is not asked: at 2, half the golden set's questions
# that reach this step (52%), and 98.5% of those agree with Qwen3-32B; on 900 held-out practice questions 51% at 90%
# (scripts/ask_v6.py, 14 Nov 2026). The reader's own scale, so it is read from its calibration.json
READER_SURE = float(ask_model.read_calibration(ask_model.READER_DIR).get("sure", 2.0))
LEARNED_KEPT = 5000                  # questions the AI settled, kept to answer close ones at once (learn)
LEARN_LOCK = threading.Lock()
KEEP_ANSWERS = 500                   # answers kept in memory, newest used last out
TOP, SERIES = 5, 5                   # answers listed for "top", lines on a trend chart
CURRENT_DAYS = 365                   # "latest"/"last N weeks": only questions asked within this many days of the newest wave
CANDIDATES = 10                      # survey questions the model chooses between (api/ask_index.py retrieve)
TREND_FROM = 3                       # with no time named, a question asked in this many waves or more is shown as a trend
OWN_WORDING = 0.8                    # a question with this share of a survey question's words is that question: no model
# closeness in meaning (0-1) below which no survey question is near, unless every word is found ("walmrt shoppers"). It
# belongs to the search model: each model scores on its own scale, so it is read from the model's calibration.json
# (bge-small as shipped: 0.64, from the golden set's off-topic 0.55-0.63 vs real 0.652 and up, 12 Nov 2026)
NEAR_FLOOR = float(ask_model.calibration().get("near_floor", 0.64))
# a question found by meaning is answered only when its survey question beats the next *different* one by this margin;
# closer than that, Ask asks which was meant ("choose") instead of guessing. Also the model's own: etl/ask_quality.py
# records each answer's margin and the gate is the smallest at which 99% of the answers shown are right
# bge-small as shipped, 12 Nov 2026, at 0.04: bank 83% answered directly, 98.7% of them right; golden (people's own
# wording) 52% answered, 97.6% right, the rest asked to choose (86% right with no gate). The AI check settles a choice
# where it is on, so only unsure questions cost a call
GATE = float(ask_model.calibration().get("gate", 0.04))
EVERY_WORD = 1.0                     # keyword match share at which every word of the question was found
NEAR_EQUAL = 0.8                     # rules only: a match scoring this share of the best counts as near-equal
EVENT = re.compile(r"\b(prime day|big deal|deal days|black friday|cyber monday|holidays?|valentine'?s?|easter|halloween|thanksgiving|"
                   r"back.to.school|mother'?s day|father'?s day)\b")   # a survey question about one answers only a question naming one
GENERIC = re.compile(r"^(yes|no|none of (these|the above)|other.*|don['’]?t know.*|not sure|prefer not to say|n/?a)$", re.I)   # alike in any question
SAME_ANSWERS = 0.5                   # share of answers alike for two questions to be the same one asked under other codes
SCALE_ANSWERS = 5                    # an answer list this short (a rating scale) proves nothing alone: the wording must match too
JUNK_BELOW = 0.35                    # below this share of words matched, no survey asks it: free, no model
MIN_MATCH = 0.45                     # share of the question's words found below which it is "not in the surveys" (scripts/ask_bench.py)
NOTE_STARTS = ("Note", "Not asked", "Asked under", "Shown by")   # sentences that qualify the answer, shown apart
SMALL_BASE = 50                      # config/methodology.yml: a figure on fewer people is marked small base, read with caution
DONUT_MAX = 8                        # a single-choice question with this many answers or fewer is a donut
SKIP = re.compile(r"^(none of (these|the above)|other( - please specify)?|prefer not to say|don['’]?t know|not sure)$", re.I)
INDEX: dict = {"version": None, "index": None}
INDEX_LOCK = threading.Lock()
ANSWERS: OrderedDict = OrderedDict()
ANSWERS_LOCK = threading.Lock()
FAMILY = {"CSI-US": "Weekly US consumer tracker"}


def index_for(root: Path, version: str, waves: list[dict]) -> Index:
    """The question index of this published version, built once (other threads wait for it, never build twice)."""
    with INDEX_LOCK:
        if INDEX["version"] != version or not INDEX["index"].docs:   # empty: built before a deploy restored the files
            INDEX.update(version=version, index=Index(root, waves))
            threading.Thread(target=INDEX["index"].add_vectors, daemon=True, name="ask-vectors").start()
            with ANSWERS_LOCK:
                ANSWERS.clear()
        return INDEX["index"]


def focus(question: str, labels: list[str]) -> list[int]:
    """The answers the question names ("Amazon", "Walmart"), longest names first so "Amazon Fresh" beats "Amazon"."""
    text = " " + " ".join(re.findall(r"[a-z0-9$&']+", question.lower())) + " "
    found = []
    for i, label in sorted(enumerate(labels), key=lambda x: -len(x[1])):
        words = " ".join(re.findall(r"[a-z0-9$&']+", label.lower()))
        if len(words) >= 3 and f" {words} " in text and not any(words in " ".join(re.findall(r"[a-z0-9$&']+", labels[j].lower())) for j in found):
            found.append(i)
    return found


def fmt(pct: float) -> str:
    return f"{pct:.1f}%"


def ranked(fig: dict, period: int = -1) -> list[int]:
    """Answers biggest first in a period (averaged over the cut columns shown), leaving out none/other/don't know."""
    shown = ~np.isnan(fig["pct"][period])
    values = np.where(shown.any(axis=0), np.nansum(fig["pct"][period], axis=0) / np.maximum(shown.sum(axis=0), 1), np.nan)
    order = [i for i in np.argsort(-np.nan_to_num(values, nan=-1)) if not math.isnan(values[i]) and not SKIP.match(fig["answers"][i])]
    return order


def chart(fig: dict, shown: list[int]) -> dict | None:
    """The chart that fits the figures: a line over time, grouped bars by a cut, a donut for a single choice of a few
    answers that add up to 100%, else bars, biggest first. None when no answer has a figure to draw (a cut whose groups
    were never asked it: the question bank found two, 12 Nov 2026), so the answer is the table and its sentences."""
    if not shown:
        return None
    pct = lambda p, c, a: None if math.isnan(fig["pct"][p, c, a]) else float(fig["pct"][p, c, a])   # noqa: E731
    periods, columns = fig["periods"], fig["columns"]
    if len(periods) > 1:
        if len(columns) > 1:   # a trend by a cut: one line per group for the main answer, never one group unlabelled
            series = [{"name": f"{v}: {fig['answers'][shown[0]]}", "data": [pct(p, c, shown[0]) for p in range(len(periods))]}
                      for c, (_, v) in enumerate(columns)]
        else:
            series = [{"name": fig["answers"][a], "data": [pct(p, 0, a) for p in range(len(periods))]} for a in shown]
        return {"type": "line", "categories": [p["label"] for p in periods], "series": series, "unit": "%"}
    if len(columns) > 1:
        return {"type": "grouped", "categories": [fig["answers"][a] for a in shown],
                "series": [{"name": v, "data": [pct(0, c, a) for a in shown]} for c, (_, v) in enumerate(columns)], "unit": "%"}
    total = np.nansum(fig["pct"][0, 0])
    every = ranked(fig)
    if len(fig["answers"]) <= DONUT_MAX and abs(total - 100) <= 1.5:
        return {"type": "donut", "categories": [fig["answers"][a] for a in every],
                "series": [{"name": periods[0]["label"], "data": [pct(0, 0, a) for a in every]}], "unit": "%"}
    keep = shown if len(shown) > 1 else every[:12]
    return {"type": "bar", "categories": [fig["answers"][a] for a in keep],
            "series": [{"name": periods[0]["label"], "data": [pct(0, 0, a) for a in keep]}], "unit": "%"}


def write(plan: dict, fig: dict, doc: dict, named: list[int]) -> tuple[list[str], list[int]]:
    """The answer's sentences, and the answers they are about."""
    periods, columns, kind = fig["periods"], fig["columns"], plan["kind"]
    say = [f"From “{doc['text'][:220]}” ({FAMILY.get(doc['family'], doc['family'].replace('_', ' ').title())}, "
           f"{doc['qcode']}, asked in {doc['waves']} {'wave' if doc['waves'] == 1 else 'waves'}, "
           f"{ask_figures.label_date(doc['first'])} – {ask_figures.label_date(doc['last'])})."]
    base = lambda p, c, a: int(fig["bases"][p, c, a])   # noqa: E731
    people = lambda p, c, a: int(fig["people"][p, c, a])   # noqa: E731
    shown = named or ranked(fig)[: (plan["top"] or TOP) if kind == "top" else (SERIES if len(periods) > 1 else 3)]
    if kind == "top":   # biggest first, whatever order they were named in
        shown = sorted(shown, key=lambda a: -np.nan_to_num(fig["pct"][-1, 0, a], nan=-1))
    if len(columns) > 1:
        dim = columns[0][0].replace("_", " ")
        for a in shown[:3]:
            parts = [f"{v} {fmt(fig['pct'][-1, c, a])}" for c, (_, v) in enumerate(columns) if not math.isnan(fig['pct'][-1, c, a])]
            say.append(f"By {dim}, “{fig['answers'][a]}” in {periods[-1]['label']}: " + ", ".join(parts) + ".")
    elif len(periods) > 1 and (kind == "trend" or fig["grain"]):
        grain = {"wave": "wave by wave", "biweek": "every two weeks", "4week": "every four weeks", "month": "by month",
                 "quarter": "by quarter", "year": "by year"}.get(fig["grain"], "")
        latest = max((p for p in range(len(periods)) if periods[p]["waves"]), default=len(periods) - 1)
        for a in shown[:1]:   # the newest figure first: what an analyst asks "how many" or "what share" about
            if not math.isnan(fig["pct"][latest, 0, a]):
                n, b = people(latest, 0, a), base(latest, 0, a)
                among = f" among {columns[0][1]}" if columns[0][0] != "total" else ""
                # the finding first, then when and of how many (Pew Research's headlines; the page shows this sentence first)
                say.append(f"{n:,} of {b:,} respondents{among} ({fmt(fig['pct'][latest, 0, a])}) answered “{fig['answers'][a]}” in {periods[latest]['label']}, the latest."
                           if plan["kind"] == "count" else
                           f"{fmt(fig['pct'][latest, 0, a])}{among} answered “{fig['answers'][a]}” in {periods[latest]['label']}, the latest ({n:,} of {b:,} respondents).")
        say.append(f"{len(periods)} periods, {grain}, {periods[0]['label']} to {periods[-1]['label']}:")
        for a in shown:
            line = [(p, fig["pct"][p, 0, a]) for p in range(len(periods)) if not math.isnan(fig["pct"][p, 0, a])]
            if not line:
                continue
            (p0, v0), (p1, v1) = line[0], line[-1]
            high = max(line, key=lambda x: x[1])
            low = min(line, key=lambda x: x[1])
            change = ask_figures.moved(fig, a)
            sig = f"; latest change {change[0]:+.1f} pts{', significant' if change[1] else ''}" if change else ""
            say.append(f"“{fig['answers'][a]}”: {fmt(v0)} ({periods[p0]['label']}) → {fmt(v1)} ({periods[p1]['label']}), "
                       f"{v1 - v0:+.1f} pts. Highest {fmt(high[1])} ({periods[high[0]]['label']}), "
                       f"lowest {fmt(low[1])} ({periods[low[0]]['label']}){sig}.")
    elif len(periods) == 2:
        for a in shown:
            change = ask_figures.moved(fig, a)
            if change is None:
                continue
            say.append(f"“{fig['answers'][a]}”: {fmt(fig['pct'][0, 0, a])} in {periods[0]['label']} (n={base(0, 0, a):,}) vs "
                       f"{fmt(fig['pct'][1, 0, a])} in {periods[1]['label']} (n={base(1, 0, a):,}), {change[0]:+.1f} pts"
                       f"{' — a significant change' if change[1] else ', not a significant change'}.")
    else:
        when = periods[0]["label"] + (f" ({len(periods[0]['waves'])} waves pooled)" if len(periods[0]["waves"]) > 1 else "")
        among = f" among {columns[0][1]}" if columns[0][0] != "total" else ""   # one cut value asked for: "Gen Z"
        if kind == "top":   # the group named too: "Top 5 in 9 Nov" for Gen Z alone read as everyone's (13 Nov 2026)
            say.append(f"Top {len(shown)}{among} in {when}: " + "; ".join(
                f"{i + 1}. {fig['answers'][a]} {fmt(fig['pct'][0, 0, a])}" for i, a in enumerate(shown)) + ".")
        for a in shown if kind != "top" else shown[:1]:
            if math.isnan(fig["pct"][0, 0, a]):
                continue
            say.append(f"{people(0, 0, a):,} of {base(0, 0, a):,} respondents{among} ({fmt(fig['pct'][0, 0, a])}) answered “{fig['answers'][a]}” in {when}."
                       if kind == "count" else
                       f"{fmt(fig['pct'][0, 0, a])}{among} answered “{fig['answers'][a]}” in {when} ({people(0, 0, a):,} of {base(0, 0, a):,} respondents).")
    if len(doc.get("codes", [])) > 1 and len({v for p in periods for v in p["versions"]}) > 1:
        say.append(f"Asked under the codes {', '.join(doc['codes'])} over the years: their waves are joined as one series.")
    few = fig["bases"][:, :, shown]
    few = few[(few > 0) & (few < SMALL_BASE)]
    if few.size:
        say.append(f"Note: small base, as few as {int(few.min()):,} respondents: read with caution.")
    gaps = [p["label"] for p in periods if not p["waves"]]
    if gaps:
        say.append(f"Not asked in: {', '.join(gaps[:12])}{'…' if len(gaps) > 12 else ''} (gaps in the chart).")
    if fig["missing"]:
        say.append("Note: some periods asked about had no wave asking this question" +
                   f" (it was asked {ask_figures.label_date(fig['asked'][0])} – {ask_figures.label_date(fig['asked'][-1])}).")
    if plan["cuts"] and len(plan["cuts"]) > 1:
        say.append(f"Shown by {columns[0][0].replace('_', ' ')} only; ask again for another cut.")
    return say, shown


def period_of(when: list[dict]) -> str:
    """A plan's period in the verified library's words (api/ask_model.py SCHEMA p): dates named stay with the rules."""
    if when == [{"all": True}]:
        return "all"
    if when == [{"latest": 1}]:
        return "latest"
    if when == [{"latest": 2}]:
        return "previous"
    return "first_vs_latest" if when == [{"first": 1}, {"latest": 1}] else "named"


def save_verified(entry: dict, index: Index) -> dict:
    """An admin's verified question (Ask page, "Save as verified"): kept in logs/ask-verified.json (on /home, so a
    deploy keeps it), and in use at once. config/ask_verified.yml is the reviewed list in git."""
    keep = {k: entry[k] for k in ("question", "key", "code", "family", "focus", "kind", "cut", "period") if k in entry}
    if not str(keep.get("question", "")).strip() or not keep.get("code"):
        raise ValueError("a question and its survey question code are needed")
    path = ask_model.LOGS / "ask-verified.json"
    with ANSWERS_LOCK:
        try:
            saved = json.loads(path.read_text())
        except (OSError, ValueError):
            saved = []
        saved = [v for v in saved if v["question"].lower() != keep["question"].lower()] + [keep]
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(saved, indent=1))
        ANSWERS.clear()
    index.load_verified()
    return {"saved": keep, "verified": len(index.verified)}


def learn(reading: dict, index: Index) -> None:
    """Keeps the AI check's reading of a question (logs/ask-learned.json, on /home so a deploy keeps it, newest LEARNED_KEPT)
    and loads it at once: the same or a close question (Index.verified_for) is then answered from it with no AI call. The
    small model learns from the large one as it is used ("Cache & Distil", ACL 2024); the file is also training data."""
    keep = {k: reading[k] for k in ("question", "key", "code", "family", "focus", "kind", "cut", "period") if k in reading}
    keep["model"] = ask_model.model()   # reused only while this model is the AI (Index.load_verified)
    if not keep.get("question") or not keep.get("key"):
        return
    with LEARN_LOCK:
        learned = [v for v in read_json(LEARNED) or [] if v.get("question", "").lower() != keep["question"].lower()]
        LEARNED.parent.mkdir(exist_ok=True)
        part = LEARNED.with_suffix(f".{os.getpid()}.part")
        part.write_text(json.dumps((learned + [keep])[-LEARNED_KEPT:], indent=0))
        os.replace(part, LEARNED)
    index.load_verified()


def read_with_model(plan: dict, reading: dict) -> dict:
    """The rules' plan with the model's reading: its kind, cut and grain, and its period unless the question named dates
    (the rules read those exactly: "October 2026", "last 8 weeks")."""
    when = plan["when"]   # the time the question names, read by the rules from its own words, always wins; with none,
    if not when:          # only a comparison the model reads is added, and the answer is the trend over every wave
        when = {"previous": [{"latest": 2}], "first_vs_latest": [{"first": 1}, {"latest": 1}]}.get(reading["period"], [])
    asks_group = re.search(r"\b(young|younger|old|older|age|ages|aged|generation|gender|sex|male|female|men|women|income|"
                           r"rich|poor|wealthy|region|regions|urban|rural|suburban|demographic)", plan["question"])
    cuts = plan["cuts"] or ({reading["cut"]: "all"} if reading["cut"] != "none" and asks_group else {})   # a group the words name
    kind = plan["kind"] if plan["kind"] != "share" else reading["kind"]   # "top", "how many", "trend" in the words win
    grain = plan["grain"] or (reading["grain"] if kind == "trend" and reading["grain"] != "auto" else None)   # a series only for a trend
    return {**plan, "kind": kind, "when": when, "cuts": cuts, "grain": grain, "compare": plan["compare"] or len(when) > 1}


def answer(question: str, index: Index, visible: set[int], quick: bool = False) -> dict:
    """{answer, chart, table, sources, suggestions, plan, mode, check}: mode "figures" when answered, "none" when nothing
    in the surveys matches (then suggestions lists the closest questions, if any). quick: the nearest survey question by
    meaning and the rules, no model (~100 ms); check is then true when the model's reading may differ, and the page
    asks again without quick to have it read (the Ask page shows the quick answer meanwhile)."""
    question = index.correct_spelling(" ".join(str(question).split())[:500])   # "walmrt shoppers" is Walmart's
    plan = ask_reader.read(question)
    topic = {w for w in stems(question) if len(w) >= 4}   # the question's own words: which answers and questions name it
    visible = {s for s in visible if index.country.get(s, "US") == plan["country"]}   # a US question never reads China's waves
    hits = []   # the topic words, and the whole question (a cut can be the subject: "What is your age group?"), best kept
    if len(question) >= 3:
        best = {}
        for words in dict.fromkeys([plan["about"] or question, question]):
            for h in index.find(words, plan, 8, visible):
                if h["score"] > best.get(h["key"], {"score": -1})["score"]:
                    best[h["key"]] = h
        hits = sorted(best.values(), key=lambda h: -h["score"])[:8]
    understood = "rules"
    margin = None   # how far the question found by meaning beats the next different one (etl/ask_quality.py calibrates the gate on it)
    reading = None
    named, sure = index.named(question, visible, plan)
    shared = [] if sure or not named else [named] + [k for k in index.names.get(name_key(question), []) if k != named]
    if named and sure:   # the question uses a survey question's own analyst name (the stored patterns): that question, no
        understood = "named"   # search or model; its periods, cuts and kind are the rules' reading of this question
        hits = [{**index.docs[named], "key": named, "match": 1.0}] + [h for h in hits if h["key"] != named]
    named = named if sure else None   # a name different questions share: the search picks among them (shared, below)
    alternative = None   # the model's second choice: shown first as "did you mean", never answered instead
    # the model reads a new question unless the rules need no help: nothing in the surveys matches (below MIN_MATCH, the
    # closest are shown), or the question is a survey question's own wording. The rules alone pick right only ~65% of
    # analysts' questions and their confidence does not tell which (scripts/ask_golden.py, 11 Nov 2026)
    own_words = hits and len(set(re.findall(r"[a-z0-9]+", question.lower())) & set(re.findall(r"[a-z0-9]+", hits[0]["text"].lower()))) \
        >= OWN_WORDING * len(set(re.findall(r"[a-z0-9]+", hits[0]["text"].lower())))
    unsure = bool(hits) and hits[0]["match"] >= JUNK_BELOW and not own_words and not named
    subject = plan["about"] if len(plan["about"]) >= 3 else question   # time and cut words are the rules'; search the subject
    # the subject's vector searches the survey questions; verified and learned questions are matched by subject and by the
    # whole question (a subject alone missed an exact repeat of a learned question, 13 Nov 2026)
    made = ask_model.embed([subject, question]) if unsure else None   # local, ~1.5 ms each
    asked = made[0] if made is not None else None
    found = [v for v in (index.verified_for(asked), index.verified_for(made[1] if made is not None else None)) if v]
    verified = max(found, key=lambda v: v["near"]) if found else None   # the closer of subject and whole question
    # (a short question matches by its subject: "Top holiday retailers"; a repeat matches as a whole)
    if verified and visible.isdisjoint(index.docs[verified["key"]]["surveys"]):
        verified = None
    if verified:   # an approved question with the same names and groups: its plan, no model (Snowflake's verified queries)
        doc_labels = index.docs[verified["key"]].get("labels", [])
        same_names = set(focus(question, doc_labels)) == set(focus(verified["question"], doc_labels))
        same_groups = set(plan["cuts"]) == set(ask_reader.read(verified["question"])["cuts"])
        if not (same_names and same_groups):
            verified = None
    # a learned entry is the AI's earlier pick: the reader reads the question too, and a sure reader's pick stands (below)
    learned = bool(verified and verified.get("learned"))
    candidates = index.retrieve(subject, plan, CANDIDATES, visible, asked) if unsure and asked is not None and (learned or not verified) else []
    closeness = [c["near"] for c in candidates if "near" in c]   # only the ones found by meaning carry a closeness
    if not verified and closeness and max(closeness) < NEAR_FLOOR and hits[0]["match"] < EVERY_WORD:   # nothing close in meaning or words ("walmrt" is corrected): free, no model
        return {"answer": "None of the surveys asks this. The closest questions are below.", "chart": None, "table": None,
                "sources": [], "plan": plan, "mode": "none", "no_source": True, "understood": "meaning",
                "suggestions": [{"qcode": c["qcode"], "text": c["text"][:200], "family": c["family"], "key": c["key"]} for c in candidates[:4]]}
    if any("latest" in w or "last" in w for w in plan["when"]):   # "latest", "last 8 weeks": questions still being asked
        recent = [c for c in candidates if c["last"] >= str(date.fromisoformat(index.newest) - timedelta(days=CURRENT_DAYS))]
        candidates = recent or candidates
    # a retailer or brand named among a long-running question's answers brings it in even when its wording is far in
    # meaning: "Amazon in 2025 vs 2026" is the weekly retailer lists, not one of the Amazon studies (golden set, 11 Nov 2026)
    seen = {c["key"] for c in candidates}
    candidates += [d for k, d in index.docs.items() if candidates and k not in seen and d["waves"] >= TREND_FROM * 5
                   and not visible.isdisjoint(d["surveys"]) and focus(question, d.get("labels", []))][:3]
    if not EVENT.search(question.lower()):   # "Walmart shoppers" is not the holiday retailers question
        candidates = [c for c in candidates if not EVENT.search(c["text"].lower())] or candidates
    # the same wording asked by several studies is one choice, the longest-running standing for it: four of fourteen
    # places the AI read held "When do you expect to start holiday shopping?" (13 Nov 2026)
    longest_of = {}
    for c in candidates:
        if c["waves"] > longest_of.get(c["text"].lower(), {"waves": -1})["waves"]:
            longest_of[c["text"].lower()] = c
    candidates = list({c["text"].lower(): longest_of[c["text"].lower()] for c in candidates}.values())
    by_meaning = list(candidates)   # the order with no reader and no AI: nearest first
    # a retailer or brand the question names among a question's answers ("Amazon" in the retailer lists) goes first, the
    # longest-running first: the model otherwise favours a question with the name in its wording (Amazon's Big Deal Days)
    candidates.sort(key=lambda c: (not focus(question, c.get("labels", [])), -c["waves"] if focus(question, c.get("labels", [])) else 0))
    listed = [{"number": i, "text": c["text"], "name": c.get("name", ""), "family": FAMILY.get(c["family"], c["family"]),
               "waves": c["waves"], "first": c["first"], "last": c["last"],
               "answers": sorted(c.get("labels", []), key=lambda l: -len(topic & set(stems(l))))}   # the answers the question
              for i, c in enumerate(candidates)]   # names first: six are read ("movie theater" was 13th of 15, 13 Nov)
    # Ask's own reader picks from the lines the AI reads (~70 ms, no cost); the AI reads the question only when the
    # reader is unsure (or absent) and a key is set; rules keep any dates the question names
    reader_pick = ask_model.read_pick(question, listed)   # (number or None, lead), None without the reader
    reader_sure = reader_pick is not None and reader_pick[1] >= READER_SURE
    if learned and reader_sure:   # the AI's earlier pick only where the AI would be asked: staging reused gpt-4o-mini's pick
        verified = None           # for "Do GLP-1 users eat less?" on "Which foods…", over a reader sure at a lead of 7 (14 Nov 2026)
    if listed and not quick and not reader_sure and not verified:
        reading = ask_model.plan(question, listed)
    by_reader = reading is None and reader_pick is not None
    if by_reader:   # its pick only: the rules read the kind, period and group, as the reading's defaults say
        reading = {"pick": reader_pick[0], "alt": None, "focus": [], "kind": "share", "grain": "auto", "cut": "none", "period": "all"}
    if verified:
        understood = "learned" if verified.get("learned") else "verified"
        reading = {"pick": None, "focus": verified.get("focus", []), "kind": verified.get("kind", "share"),
                   "grain": verified.get("grain", "auto"), "cut": verified.get("cut", "none"), "period": verified.get("period", "all")}
        chosen = {**index.docs[verified["key"]], "key": verified["key"]}
        hits = [chosen] + [h for h in hits if h["key"] != chosen["key"]]
        plan = read_with_model(plan, reading)
    if candidates and not verified:   # the reader's or the AI's pick, or with neither the nearest by meaning
        understood = "reader" if by_reader else "model" if reading else "meaning"
        if reading and reading["pick"] is None:
            return {"answer": "None of the surveys asks this. The closest questions are below.", "chart": None, "table": None,
                    "sources": [], "plan": plan, "mode": "none", "no_source": True, "understood": understood,
                    "check": quick and not reader_sure and ask_model.ready(),   # an unsure "none": the AI may find one
                    "suggestions": [{"qcode": c["qcode"], "text": c["text"][:200], "family": c["family"], "key": c["key"]} for c in candidates[:4]]}
        chosen = candidates[reading["pick"]] if reading else by_meaning[0]
        alternative = candidates[reading["alt"]] if reading and reading.get("alt") is not None and reading["alt"] != reading["pick"] else None
        # rules the model was told but breaks, enforced here for free: a retailer or brand named among a long-running
        # question's answers is that question unless an event is named; a trend needs a question with history
        named = [c for c in candidates if c["waves"] >= TREND_FROM * 5 and focus(question, c.get("labels", []))]
        longest = max(named, key=lambda c: c["waves"], default=None)
        names = [longest["labels"][i] for i in focus(question, longest["labels"])] if longest else []
        named_stems = {s for n in names for s in stems(n)}
        rest = {s for s in stems(question) if len(s) >= 4} - named_stems   # quick: "Costco shoppers" is not "why Costco"
        # a reading's pick with the name in its wording stands only when the question asks more than the name and a time:
        # "Amazon in 2025 vs 2026" is the retailer lists, though the AI picked Prime membership (14 Nov 2026)
        asks_more = bool({s for s in stems(plan["about"]) if len(s) >= 4} - named_stems)
        own_name = any(n.lower() in chosen["text"].lower() for n in names) and (bool(reading) and asks_more or bool(rest & set(stems(chosen["text"]))))
        # the pick shares more of the question's other words than the list: it asks what the question asks ("How do people
        # feel about Target?" is the feelings question, not the purchases list that has Target among its answers, 13 Nov)
        asks_else = longest is not None and len(rest & set(stems(chosen["text"]))) > len(rest & set(stems(longest["text"])))
        if longest and not own_name and not asks_else and not EVENT.search(question.lower()) and (   # "Amazon Prime" questions keep their own
                not focus(question, chosen.get("labels", [])) or chosen["waves"] * 3 < longest["waves"]):   # q5 (195 waves) over EC2 (22)
            chosen = longest
        if chosen["waves"] <= 2:   # the same question asked over more waves is the better source: most of its own,
            own = {a.lower() for a in chosen.get("labels", []) if not GENERIC.match(a)}   # specific answers alike
            # a short list such as a 5-point scale (much better … much worse) is shared by different questions: then the
            # wording must be alike too ("your finances" is not "the economy", 13 Nov 2026)
            longer = [c for c in candidates if c["waves"] >= TREND_FROM * 2 and len(own) >= 3
                      and len(own & {a.lower() for a in c.get("labels", [])}) >= SAME_ANSWERS * len(own)
                      and (len(own) > SCALE_ANSWERS or index.alike(chosen["key"], c["key"]))]
            chosen = max(longer, key=lambda c: c["waves"], default=chosen)
        if (plan["grain"] or plan["kind"] == "trend" or (reading or {}).get("kind") == "trend") and chosen["waves"] < TREND_FROM:
            # the one with history that names most of what the question is about, then the longest-running: the first one
            # found answered "online grocery trend" from grocery categories (3 waves), not online purchases (219, 13 Nov)
            history = [c for c in candidates if c["waves"] >= TREND_FROM]
            # a word none of them uses counts by its synonyms ("dining out" is "Gone to a restaurant (dine in)"); a word one
            # uses counts alone (by its synonyms, "online" found "app" in a beauty retailer list, 14 Nov 2026)
            said = {c["key"]: set(stems(c["text"] + " " + " ".join(c.get("labels", [])))) for c in history}
            wanted = topic | {s for w in topic - set().union(*said.values()) for s in index.synonyms.get(w, ())}
            chosen = max(history, key=lambda c: (len(wanted & said[c["key"]]), c["waves"]), default=chosen)
        alternative = alternative if alternative and alternative["key"] != chosen["key"] else None
        # the next question that asks something else: a near-twin from another study (alike wording) is a right answer too
        others = [c["near"] for c in candidates if "near" in c and c["key"] != chosen["key"] and not index.alike(chosen["key"], c["key"])]
        margin = round(chosen["near"] - max(others), 3) if "near" in chosen and others else None
        # unsure between different questions: ask which was meant, but only when no AI check can follow. With one, the
        # best match shows at once and the check confirms or replaces it in about a second: "choose" first made half of
        # people's questions wait for the AI (49% of the golden set live on staging, 12 Nov 2026)
        # a stored name the question uses (shared) is decided by the name step below, not asked about (13 Nov 2026)
        if understood == "meaning" and margin is not None and margin < GATE and not shared and not (quick and ask_model.ready()):
            shown, texts = [], set()
            for c in [chosen] + by_meaning:
                if c["text"].lower() not in texts and len(shown) < 3:
                    texts.add(c["text"].lower())
                    shown.append({"qcode": c["qcode"], "text": c.get("name") or c["text"][:200], "family": c["family"], "key": c["key"]})
            return {"answer": "This could be more than one survey question. Which did you mean?", "chart": None, "table": None,
                    "sources": [], "plan": plan, "mode": "choose", "no_source": True, "understood": understood, "margin": margin,
                    "suggestions": shown, "check": quick and ask_model.ready()}
        hits = [chosen] + ([alternative] if alternative else []) + [c for c in candidates if c["key"] not in (chosen["key"], (alternative or {}).get("key"))]
        plan = read_with_model(plan, reading) if reading else plan
    if shared:   # a name questions share ("Economic outlook"): the search's pick if it is one of them, else the longest-running
        first = hits[0]["key"] if hits and hits[0]["key"] in shared else shared[0]   # that can answer; a best match, the others listed
        understood = "name"
        hits = [{**index.docs[k], "key": k, "match": 1.0} for k in [first] + [k for k in shared if k != first]] + [h for h in hits if h["key"] not in shared]
    if understood == "rules" and hits and hits[0]["match"] < MIN_MATCH:   # too little matched: the closest, never an answer
        return {"answer": "No survey question matches this well enough to answer it. The closest questions are below.",
                "chart": None, "table": None, "sources": [], "plan": plan, "mode": "none", "no_source": True,
                "suggestions": [{"qcode": h["qcode"], "text": h["text"][:200], "family": h["family"], "key": h["key"]} for h in hits[:4]]}
    offered = {}   # one per wording shown: a question asked by several studies was listed up to four times (Q6_2, 12 Nov)
    for h in hits[1:]:   # a question sharing the answer's name is shown by its own wording: the name would not tell them apart
        text = h["text"][:200] if h.get("name") and h["name"].lower() == (hits[0].get("name") or "").lower() else h.get("name") or h["text"][:200]
        if text.lower() != (hits[0].get("name") or hits[0]["text"][:200]).lower():
            offered.setdefault(text.lower(), {"qcode": h["qcode"], "text": text, "family": h["family"], "key": h["key"],
                                              "alt": bool(alternative) and h["key"] == alternative["key"]})
    suggestions = list(offered.values())[:4]
    if not hits:
        return {"answer": "No survey question in the portal matches this. Try other words, or browse Search questions.",
                "chart": None, "table": None, "sources": [], "suggestions": [], "plan": plan, "mode": "none", "no_source": True}
    if understood == "rules" and hits and hits[0]["waves"] <= 2:   # no model: a near-equal match with history is the better source
        longer = [h for h in hits[1:6] if h["waves"] >= TREND_FROM * 2 and h["score"] >= NEAR_EQUAL * hits[0]["score"]]
        if longer:
            hits = [max(longer, key=lambda h: h["waves"])] + [h for h in hits if h["key"] != max(longer, key=lambda h: h["waves"])["key"]]
    asked_plan = plan
    # the pick, or when it was not asked in the period named the same question asked by another study, or the next match
    # naming the same retailer or brand that was ("Temu over the last year": the retailer lists; "online last month": the
    # weekly online categories, as the quarterly one stopped in September, 13 Nov 2026)
    fallbacks = [h for h in hits[1:] if focus(question, h.get("labels", [])) or index.alike(hits[0]["key"], h["key"])]
    for hit in hits[:1] + fallbacks[:3]:
        doc = index.docs[hit["key"]]
        plan = asked_plan
        if not plan["when"] and not plan["cuts"] and (plan["kind"] in ("share", "count", "change") or plan["grain"]) and doc["waves"] >= TREND_FROM:
            plan = {**plan, "kind": "trend", "when": [{"all": True}]}   # no time named: every wave, the latest figure first
        counts = index.counts(doc["key"])
        fig = ask_figures.compute(counts, plan, visible)
        if hit is hits[0]:
            first = (doc, plan, counts, fig)
        if fig["periods"]:
            break
    else:
        doc, plan, counts, fig = first   # none was: say when the pick was asked
    if not fig["periods"]:
        asked = f"{ask_figures.label_date(fig['asked'][0])} – {ask_figures.label_date(fig['asked'][-1])}" if fig["asked"] else "never"
        return {"answer": f"“{doc['text'][:200]}” ({doc['qcode']}) was not asked in the period you named: it was asked {asked}.",
                "chart": None, "table": None, "sources": [], "suggestions": suggestions, "plan": plan, "mode": "none", "no_source": True}
    said = (reading or {}).get("focus", [])
    if plan["kind"] == "top" or len(said) > 4:   # "top", or the model listing most answers: every answer, ranked
        said = []
    if understood == "model":   # an answer the model names but the question does not ("Which retailers do Gen Z prefer?"
        words = set(re.findall(r"[a-z0-9]{3,}", question.lower()))   # → "Abercrombie & Fitch", staging 12 Nov): ranked instead
        said = [a for a in said if words & set(re.findall(r"[a-z0-9]{3,}", a.lower()))]
    named = [fig["answers"].index(a) for a in said if a in fig["answers"] and (not SKIP.match(a) or a.lower() in question.lower())] \
        or focus(question, fig["answers"])
    named = [a for a in named if not np.all(np.isnan(fig["pct"][:, :, a]))]   # an answer these waves never offered: not shown
    rest = question   # words the survey itself uses ("compare to last year", an answer "Spent more than last year") are
    for a in named:   # the question's wording, not a period: without them, the plan is read again
        rest = re.sub(re.escape(fig["answers"][a]), " ", rest, flags=re.I)
    own = " ".join(re.findall(r"[a-z0-9]+", " ".join([doc["text"]] + fig["answers"]).lower()))   # "than last year" in an answer too
    for phrase in set(re.findall(r"\b(?:this|last|past|previous|next)\s+(?:\d+\s+|two\s+|three\s+|twelve\s+|few\s+)?(?:weeks?|months?|years?|days?|holiday season)\b", rest.lower())):
        if phrase in own:
            rest = re.sub(re.escape(phrase), " ", rest, flags=re.I)
    if rest != question:
        again = ask_reader.read(rest)
        if (again["when"], again["grain"]) != (plan["when"], plan["grain"]):
            replan = {**plan, **{k: again[k] for k in ("when", "grain", "kind", "compare")}}
            refig = ask_figures.compute(counts, replan, visible)
            if refig["periods"]:   # only when the re-read still finds waves
                plan, fig = replan, refig
    sentences, shown = write(plan, fig, doc, named)
    last = fig["periods"][-1]
    shown = list(dict.fromkeys(shown + [fig["answers"].index(c) for c in (chart(fig, shown) or {}).get("categories", [])
                                        if c in fig["answers"]]))   # the table lists at least every charted answer
    table = {"head": ["Answer"] + [f"{p['label']}" + (f" · {v}" if len(fig['columns']) > 1 else "")
                                   for p in fig["periods"] for _, v in fig["columns"]],
             "rows": [[fig["answers"][a]] + [None if math.isnan(fig["pct"][p, c, a]) else float(fig["pct"][p, c, a])
                                             for p in range(len(fig["periods"])) for c in range(len(fig["columns"]))]
                      for a in (shown if len(fig["answers"]) > 15 else range(len(fig["answers"])))
                      if not np.all(np.isnan(fig["pct"][:, :, a]))],   # an answer these waves never offered is not a row
             "bases": [int(fig["bases"][p, c].max()) for p in range(len(fig["periods"])) for c in range(len(fig["columns"]))]}
    notes = [x for x in sentences[1:] if x.startswith(NOTE_STARTS)]
    points = [x for x in sentences[1:] if not x.startswith(NOTE_STARTS)]
    headline = next((x for x in points if "%" in x), points[0] if points else "")   # the first sentence with a figure
    return {"answer": "\n".join(sentences), "headline": headline, "points": [x for x in points if x != headline], "notes": notes,
            "source_line": sentences[0], "weighting": "unweighted", "understood": understood,
            "check": quick and understood in ("meaning", "reader") and not reader_sure and ask_model.ready(), "margin": margin,
            "verify": {"question": question, "key": doc["key"], "code": doc["qcode"], "family": doc["family"], "focus": [fig["answers"][a] for a in named],
                       "kind": plan["kind"], "cut": next(iter(plan["cuts"]), "none"), "period": period_of(plan["when"])}, "codes": doc.get("codes", [doc["qcode"]]),
            "chart": chart(fig, shown), "table": table, "plan": plan, "mode": "figures", "no_source": False,
            "suggestions": suggestions,
            "sources": [{"id": "S1", "key": doc["key"], "qcode": doc["qcode"], "question": doc["text"], "family": doc["family"],
                         "survey_id": last["waves"][-1], "wave_date": last["to"], "waves": len(set(sum((p["waves"] for p in fig["periods"]), []))),
                         "link": f"/w/{last['waves'][-1]}/{'trends' if len(fig['periods']) > 1 else 'questions'}/{doc['qcode']}"}]}


def ask(question: str, index: Index, visible: set[int], scope: str, quick: bool = False) -> dict:
    """answer(), kept per published version (the index), access scope, quick or not, and question wording; a question
    the AI check settled is learned, so the same or a close question is answered at once next time, with no AI."""
    key = (id(index), scope, quick, " ".join(question.lower().split()))
    with ANSWERS_LOCK:
        if key in ANSWERS:
            ANSWERS.move_to_end(key)
            return ANSWERS[key]
    found = answer(question, index, visible, quick)
    if found.get("understood") == "model" and found.get("mode") == "figures":
        learn(found["verify"], index)
    with ANSWERS_LOCK:
        ANSWERS[key] = found
        while len(ANSWERS) > KEEP_ANSWERS:
            ANSWERS.popitem(last=False)
    return found
