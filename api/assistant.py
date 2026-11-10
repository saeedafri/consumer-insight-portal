"""Ask CIP: a question in plain words, answered from the portal's own published survey figures, with a chart.

Who calls it: api/main.py ask (POST /api/v1/ask). No AI model and no database: in about a millisecond to tens of
milliseconds, and at no cost per question.

  1. read     api/ask_reader.py   the periods, grain, cuts and kind of question, by rules
  2. find     api/ask_index.py    the survey question it is about (its words, answers, topic and sector words)
  3. compute  api/ask_figures.py  exact pooled figures from the published counts, for the waves this person may see
  4. write    here                sentences from the figures, the chart that fits, the sources, other matches

Every number in an answer is one of the computed figures; a question it cannot place is answered with the closest
questions, never with a guess. Answers are kept per published version, person's access and wording (ANSWERS).
"""
from __future__ import annotations

import logging
import math
import re
import threading
from collections import OrderedDict
from pathlib import Path

import numpy as np

from api import ask_figures, ask_reader
from api.ask_index import Index

log = logging.getLogger("cip.assistant")
KEEP_ANSWERS = 500                   # answers kept in memory, newest used last out
TOP, SERIES = 5, 5                   # answers listed for "top", lines on a trend chart
DONUT_MAX = 8                        # a single-choice question with this many answers or fewer is a donut
SKIP = re.compile(r"^(none of (these|the above)|other( - please specify)?|prefer not to say|don'?t know|not sure)$", re.I)
INDEX: dict = {"version": None, "index": None}
INDEX_LOCK = threading.Lock()
ANSWERS: OrderedDict = OrderedDict()
ANSWERS_LOCK = threading.Lock()
FAMILY = {"CSI-US": "Weekly US consumer tracker"}


def index_for(root: Path, version: str, waves: list[dict]) -> Index:
    """The question index of this published version, built once (other threads wait for it, never build twice)."""
    with INDEX_LOCK:
        if INDEX["version"] != version:
            INDEX.update(version=version, index=Index(root, waves))
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


def chart(fig: dict, shown: list[int]) -> dict:
    """The chart that fits the figures: a line over time, grouped bars by a cut, a donut for a single choice of a few
    answers that add up to 100%, else bars, biggest first."""
    pct = lambda p, c, a: None if math.isnan(fig["pct"][p, c, a]) else float(fig["pct"][p, c, a])   # noqa: E731
    periods, columns = fig["periods"], fig["columns"]
    if len(periods) > 1:
        if len(columns) > 1 and len(shown) == 1:
            series = [{"name": v, "data": [pct(p, c, shown[0]) for p in range(len(periods))]} for c, (_, v) in enumerate(columns)]
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
    if len(columns) > 1:
        dim = columns[0][0].replace("_", " ")
        for a in shown[:3]:
            parts = [f"{v} {fmt(fig['pct'][-1, c, a])}" for c, (_, v) in enumerate(columns) if not math.isnan(fig['pct'][-1, c, a])]
            say.append(f"By {dim}, “{fig['answers'][a]}” in {periods[-1]['label']}: " + ", ".join(parts) + ".")
    elif len(periods) > 1 and (kind == "trend" or fig["grain"]):
        grain = {"wave": "wave by wave", "biweek": "every two weeks", "4week": "every four weeks", "month": "by month",
                 "quarter": "by quarter", "year": "by year"}.get(fig["grain"], "")
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
        if kind == "top":
            say.append(f"Top {len(shown)} in {when}: " + "; ".join(
                f"{i + 1}. {fig['answers'][a]} {fmt(fig['pct'][0, 0, a])}" for i, a in enumerate(shown)) + ".")
        for a in shown if kind != "top" else shown[:1]:
            if math.isnan(fig["pct"][0, 0, a]):
                continue
            lead = (f"{people(0, 0, a):,} of {base(0, 0, a):,} respondents ({fmt(fig['pct'][0, 0, a])})" if kind == "count"
                    else f"{fmt(fig['pct'][0, 0, a])} ({people(0, 0, a):,} of {base(0, 0, a):,} respondents)")
            say.append(f"In {when}, {lead} answered “{fig['answers'][a]}”.")
    if len({v for p in periods for v in p["versions"]}) > 1:
        say.append("Note: the question's wording changed within these periods; see Trends for each wording.")
    if fig["missing"]:
        say.append("Note: some periods asked about had no wave asking this question" +
                   f" (it was asked {ask_figures.label_date(fig['asked'][0])} – {ask_figures.label_date(fig['asked'][-1])}).")
    if plan["cuts"] and len(plan["cuts"]) > 1:
        say.append(f"Shown by {columns[0][0].replace('_', ' ')} only; ask again for another cut.")
    return say, shown


def answer(question: str, index: Index, visible: set[int]) -> dict:
    """{answer, chart, table, sources, suggestions, plan, mode}: mode "figures" when answered, "none" when nothing in
    the surveys matches (then suggestions lists the closest questions, if any)."""
    question = " ".join(str(question).split())[:500]
    plan = ask_reader.read(question)
    hits = []   # the topic words, and the whole question (a cut can be the subject: "What is your age group?"), best kept
    if len(question) >= 3:
        best = {}
        for words in dict.fromkeys([plan["about"] or question, question]):
            for h in index.find(words, plan, 8, visible):
                if h["score"] > best.get(h["key"], {"score": -1})["score"]:
                    best[h["key"]] = h
        hits = sorted(best.values(), key=lambda h: -h["score"])[:8]
    suggestions = [{"qcode": h["qcode"], "text": h["text"][:200], "family": h["family"], "key": h["key"]} for h in hits[1:5]]
    if not hits:
        return {"answer": "No survey question in the portal matches this. Try other words, or browse Search questions.",
                "chart": None, "table": None, "sources": [], "suggestions": [], "plan": plan, "mode": "none", "no_source": True}
    doc = index.docs[hits[0]["key"]]
    counts = index.counts(doc["key"])
    fig = ask_figures.compute(counts, plan, visible, doc.get("versions"))
    if not fig["periods"]:
        asked = f"{ask_figures.label_date(fig['asked'][0])} – {ask_figures.label_date(fig['asked'][-1])}" if fig["asked"] else "never"
        return {"answer": f"“{doc['text'][:200]}” ({doc['qcode']}) was not asked in the period you named: it was asked {asked}.",
                "chart": None, "table": None, "sources": [], "suggestions": suggestions, "plan": plan, "mode": "none", "no_source": True}
    named = focus(question, fig["answers"])
    rest = question   # words the survey itself uses ("compare to last year", an answer "Spent more than last year") are
    for a in named:   # the question's wording, not a period: without them, the plan is read again
        rest = re.sub(re.escape(fig["answers"][a]), " ", rest, flags=re.I)
    own = " ".join(re.findall(r"[a-z0-9]+", doc["text"].lower()))
    for phrase in set(re.findall(r"\b(?:this|last|past|previous|next)\s+(?:\d+\s+|two\s+|three\s+|twelve\s+|few\s+)?(?:weeks?|months?|years?|days?|holiday season)\b", rest.lower())):
        if phrase in own:
            rest = re.sub(re.escape(phrase), " ", rest, flags=re.I)
    if rest != question:
        again = ask_reader.read(rest)
        if (again["when"], again["grain"]) != (plan["when"], plan["grain"]):
            replan = {**plan, **{k: again[k] for k in ("when", "grain", "kind", "compare")}}
            refig = ask_figures.compute(counts, replan, visible, doc.get("versions"))
            if refig["periods"]:   # only when the re-read still finds waves
                plan, fig = replan, refig
    sentences, shown = write(plan, fig, doc, named)
    last = fig["periods"][-1]
    table = {"head": ["Answer"] + [f"{p['label']}" + (f" · {v}" if len(fig['columns']) > 1 else "")
                                   for p in fig["periods"] for _, v in fig["columns"]],
             "rows": [[fig["answers"][a]] + [None if math.isnan(fig["pct"][p, c, a]) else float(fig["pct"][p, c, a])
                                             for p in range(len(fig["periods"])) for c in range(len(fig["columns"]))]
                      for a in (shown if len(fig["answers"]) > 15 else range(len(fig["answers"])))
                      if not np.all(np.isnan(fig["pct"][:, :, a]))],   # an answer these waves never offered is not a row
             "bases": [int(fig["bases"][p, c].max()) for p in range(len(fig["periods"])) for c in range(len(fig["columns"]))]}
    return {"answer": "\n".join(sentences), "chart": chart(fig, shown), "table": table, "plan": plan, "mode": "figures",
            "no_source": False, "suggestions": suggestions,
            "sources": [{"id": "S1", "key": doc["key"], "qcode": doc["qcode"], "question": doc["text"], "family": doc["family"],
                         "survey_id": last["waves"][-1], "wave_date": last["to"], "waves": len(set(sum((p["waves"] for p in fig["periods"]), []))),
                         "link": f"/w/{last['waves'][-1]}/{'trends' if len(fig['periods']) > 1 else 'questions'}/{doc['qcode']}"}]}


def ask(question: str, index: Index, visible: set[int], scope: str) -> dict:
    """answer(), kept per published version (the index), access scope and question wording."""
    key = (id(index), scope, " ".join(question.lower().split()))
    with ANSWERS_LOCK:
        if key in ANSWERS:
            ANSWERS.move_to_end(key)
            return ANSWERS[key]
    found = answer(question, index, visible)
    with ANSWERS_LOCK:
        ANSWERS[key] = found
        while len(ANSWERS) > KEEP_ANSWERS:
            ANSWERS.popitem(last=False)
    return found
