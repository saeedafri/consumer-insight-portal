"""Ask CIP: a question in plain words, answered from the portal's own published survey figures, with a chart.

Who calls it: api/main.py ask (POST /api/v1/ask). No database, and no AI needed: our own small models on this CPU (the
search's and the reader's, api/ask_model.py) answer in about 100 ms at no cost; the AI (optional, a key) is asked
only when the reader is unsure.

  1. read     api/ask_reader.py   the periods, grain, cuts and kind of question, by rules
  2. find     api/ask_index.py    the survey question it is about (its words, answers, topic and sector words), then
              api/ask_model.py    Ask's own reader picks among the closest (the AI only when the reader is unsure)
  3. compute  api/ask_figures.py  exact pooled figures from the published counts, for the waves this person may see
  4. write    here                sentences from the figures, the chart that fits, the figures at a glance (tiles and
                                  what they tell), follow-up questions, the sources, other matches

Every number in an answer is one of the computed figures; a question it cannot place is answered with the closest
questions, never with a guess. Answers are kept per published version, person's access, wording and follow-up key
(ANSWERS).
"""
from __future__ import annotations

import functools
import gzip
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
import yaml

from api import ask_figures, ask_model, ask_reader
from api.ask_index import FRAME_WORDS, LEARNED, STOP, Index, name_key, read_json, stems
from etl import weighting
from shared.data import payloads

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
# ponytail: a rarity cut, measured on the golden, fresh and researched sets (21 Nov 2026): words missed by right picks
# were common (bought 2.1, used 2.9, why 3.2), by wrong ones specific (subscription 3.4, progress 3.5, inflation 4.7)
RARE_WORD = 3.3                      # api/ask_index.py idf: a word at least this specific is a subject, not a verb
NEAR_EQUAL = 0.8                     # rules only: a match scoring this share of the best counts as near-equal
EVENT = re.compile(r"\b(prime day|big deal|deal days|black friday|cyber monday|holidays?|valentine'?s?|easter|halloween|thanksgiving|"
                   r"back.to.school|mother'?s day|father'?s day|labor day|memorial day|super bowl|presidents?'?s? day|fourth of july|"
                   r"4th of july|independence day|new year'?s?|singles?'?s? day|christmas)\b")   # a survey question about one answers only
# a question naming one ("personal finances quarterly" was the Labor Day question, staging, 14 Nov 2026)
GENERIC = re.compile(r"^(yes|no|none of (these|the above)|other.*|don['’]?t know.*|not sure|prefer not to say|n/?a)$", re.I)   # alike in any question
SAME_ANSWERS = 0.5                   # share of answers alike for two questions to be the same one asked under other codes
SCALE_ANSWERS = 5                    # an answer list this short (a rating scale) proves nothing alone: the wording must match too
JUNK_BELOW = 0.35                    # below this share of words matched, no survey asks it: free, no model
MIN_MATCH = 0.45                     # share of the question's words found below which it is "not in the surveys" (scripts/ask_bench.py)
NOTE_STARTS = ("Note", "Not asked", "Asked under", "Shown by")   # sentences that qualify the answer, shown apart
SMALL_BASE = 50                      # config/methodology.yml: a figure on fewer people is marked small base, read with caution
SPLIT_MAX = 6                        # a single choice of this many answers or fewer is one segmented bar (dataviz: ≤ 6 parts)
HEATMAP_MIN = 4                      # groups and answers from which a cut is a heatmap: fewer read better as grouped bars
FOLLOW_CUTS = (("generation", "generation"), ("income_band", "income"))   # the cuts a follow-up offers, in words ask_reader reads
SHARES = [(1 / 10, "one in ten"), (1 / 5, "one in five"), (1 / 4, "one in four"), (1 / 3, "one in three"), (2 / 5, "two in five"),
          (1 / 2, "half"), (3 / 5, "three in five"), (2 / 3, "two in three"), (3 / 4, "three in four"), (4 / 5, "four in five"),
          (9 / 10, "nine in ten")]   # the plain fractions a share is said as (say_share)
SKIP = re.compile(r"^(none of (these|the above)|other( - please specify)?|prefer not to say|don['’]?t know|not sure)$", re.I)
INDEX: dict = {"version": None, "index": None}
INDEX_LOCK = threading.Lock()
ANSWERS: OrderedDict = OrderedDict()
ANSWERS_LOCK = threading.Lock()
FAMILY = {"CSI-US": "Weekly US consumer tracker", "CSI-CN": "Weekly China consumer tracker"}


def index_for(root: Path, version: str, waves: list[dict]) -> Index:
    """The question index of this published version, built once (other threads wait for it, never build twice)."""
    with INDEX_LOCK:
        if INDEX["version"] != version or not INDEX["index"].docs:   # empty: built before a deploy restored the files
            INDEX.update(version=version, index=Index(root.resolve(), waves))
            INDEX["index"].settled = False   # until add_vectors ends, with or without vectors: ask() keeps no answer before
            threading.Thread(target=settle, args=(INDEX["index"],), daemon=True, name="ask-vectors").start()
            with ANSWERS_LOCK:
                clear_answers()
        return INDEX["index"]


def clear_answers() -> None:
    """Replace the cache while holding ANSWERS_LOCK so in-flight answers cannot refill it."""
    global ANSWERS
    ANSWERS = OrderedDict()


SUGGEST = 6   # suggestions offered while someone types (api/main.py ask_suggest)


@functools.lru_cache(maxsize=20_000)   # the same few thousand names on every pause in typing: 1,128 reads for "in"
def names_a_period(text: str) -> bool:
    """Does this text name a period the rules read as dates ("2025 vs 2024", "last week"): a follow-up or a suggestion
    asked with it would be answered for that period only."""
    return any(w not in ({"latest": 1}, {"all": True}) for w in ask_reader.read(text)["when"])


def suggest(typed: str, index: Index, visible: set[int]) -> dict:
    """What the Ask box offers while someone types: the words put right (correct_spelling: "subcription" →
    "subscription") and up to SUGGEST survey questions whose analyst name or alias has a word starting with each word
    typed ("ama prim" finds "Amazon Prime membership"), longest-running first. Names only, no search and no model: a few milliseconds, no cost.
    Each carries its survey question's key, so choosing one answers from that question (15 Nov 2026)."""
    asked = " ".join(str(typed).split())[:200]
    fixed = index.correct_spelling(asked)
    words = [w for w in re.findall(r"[a-z0-9]+", fixed.lower()) if w not in STOP and len(w) >= 2]
    found: dict[str, dict] = {}
    if words:
        for key, doc in index.docs.items():
            if visible.isdisjoint(doc["surveys"]):
                continue
            for name in [doc["name"] or doc["text"], *doc.get("aliases", [])]:   # a question not named yet: its wording
                said = re.findall(r"[a-z0-9]+", name.lower())
                # a name with a period ("… 2025 vs 2024") would be read as dates when asked: another name of it, or none
                if all(any(s.startswith(w) for s in said) for w in words) and not names_a_period(name):
                    found.setdefault(key, {"text": name, "key": key, "qcode": doc["qcode"], "family": doc["family"],
                                           "waves": len(visible.intersection(doc["surveys"]))})   # the waves this person sees
                    break
    unique, names = [], set()   # one per name, the longest-running (a wording asked by several studies)
    for s in sorted(found.values(), key=lambda s: (-s["waves"], s["text"])):
        if s["text"].lower() not in names:
            names.add(s["text"].lower())
            unique.append(s)
    return {"corrected": fixed if fixed != asked else None, "suggestions": unique[:SUGGEST]}


def settle(index: Index) -> None:
    """The index's vectors, in the background (index_for); settled once done, even with none (no search model)."""
    try:
        index.add_vectors()
    finally:
        index.settled = True


def focus(question: str, labels: list[str], full_names: frozenset[str] = frozenset()) -> list[int]:
    """The answers the question names ("Amazon", "Walmart"), longest names first so "Amazon Fresh" beats "Amazon"; one
    said only inside a longer name the question says (full_names, lower case) is not named: "Amazon" in "Amazon Prime"."""
    text = " " + " ".join(re.findall(r"[a-z0-9$&']+", question.lower())) + " "
    longer = [f" {n} " for n in full_names if f" {n} " in text]
    found = []
    for i, label in sorted(enumerate(labels), key=lambda x: -len(x[1])):
        words = " ".join(re.findall(r"[a-z0-9$&']+", label.lower()))
        alone = text   # the question without the longer names holding this one: "…members also buy from Amazon" names it
        for n in longer:
            if f" {words} " in n and n != f" {words} ":
                alone = alone.replace(n, " ")
        if len(words) >= 3 and f" {words} " in alone and not any(words in " ".join(re.findall(r"[a-z0-9$&']+", labels[j].lower())) for j in found):
            found.append(i)
    return found


FOLLOW_LEAD = re.compile(r"^(?:(?:and|also|now|ok(?:ay)?|so|then|but)\b,?\s*)?(?:(?:what|how) about|same (?:for|but|among|in|by)|"
                         r"(?:compare|compared) (?:with|to|against)|vs\.?|versus|just|only|among)?\b\s*")
FOLLOW_FILLER = {"same", "only", "just", "also", "then", "now", "ok", "okay", "so", "but", "among", "instead", "please", "there"}


def follow_on(question: str, previous: str, key: str | None, index: Index) -> tuple[str, str | None]:
    """A typed follow-up ("What about Gen Z?", "and by income?", "how about in 2025?", "what about Target?") read with the
    question before it, as a chat reads it: the earlier question with the new group, period or answer in place of its own,
    answered from the same survey question (key). A question with a subject of its own comes back as asked, no key.
    Called by ask() for the Ask page, which sends the question its latest answer was for (21 Nov 2026)."""
    rest = FOLLOW_LEAD.sub("", question.strip().lower(), count=1).strip(" ?.!")
    new = ask_reader.read(rest)
    labels = index.docs[key].get("labels", []) if key in index.docs else []
    names = focus(rest, labels)
    named_words = {w for i in names for w in re.findall(r"[a-z0-9$&']+", labels[i].lower())}
    if not rest or set(new["about"].split()) - FOLLOW_FILLER - named_words:
        return question, None   # its own subject: a new question
    base = " " + previous.lower().rstrip(" ?.!") + " "
    if new["when"] or new["kind"] == "trend":
        base = ask_reader.periods(base)[1]
    # "and Target", "vs boomers": both, side by side; "and by income" is a new cut, so it replaces
    before = ask_reader.read(previous)["cuts"]
    adds = re.match(r"^(?:and\b|(?:compare|compared) |vs|versus)", question.strip().lower()) and \
        all(before.get(dim) not in (None, "all") and values != "all" for dim, values in new["cuts"].items())
    if new["cuts"] and not adds:
        for pattern, *_ in ask_reader.CUT_DIMS + ask_reader.CUT_VALUES:
            base = re.sub(rf"(?:\b(?:among|for)\s+)?(?:{pattern})", " ", base)
        base = re.sub(r"\s(?:vs\.?|versus|and|or|(?:more |less )?than)\s+(?=(?:among|for|by|in|over)\b|$)", " ", base)
    if names and not adds and (old := focus(base, labels)):   # "what about Target?": Target where Amazon was
        said = " and ".join(labels[i] for i in names)
        for n, i in enumerate(old):
            base = re.sub(rf"\b{re.escape(labels[i].lower())}\b", said if n == 0 else " ", base, count=1)
        for word in sorted(named_words, key=len, reverse=True):
            rest = re.sub(rf"\b{re.escape(word)}\b", " ", rest)
    rest = " ".join(w for w in rest.split() if w not in FOLLOW_FILLER)
    among = "among " if new["cuts"] and not new["when"] and not re.match(r"(by|among|for|in|vs|versus) ", rest) and rest else ""
    return " ".join(f"{base} {among}{rest}".split()), key


def fmt(pct: float) -> str:
    return f"{pct:.1f}%"


def say_share(pct: float) -> str:
    """A share as people say it, within 2.5 points of a plain fraction ("About two in three (67.2%)"), else its figure."""
    share, words = min(SHARES, key=lambda s: abs(pct - 100 * s[0]))
    if abs(pct - 100 * share) > 2.5:
        return fmt(pct)
    return f"{'' if abs(pct - 100 * share) < 0.5 else 'about '}{words}".capitalize() + f" ({fmt(pct)})"


def ranked(fig: dict, period: int = -1) -> list[int]:
    """Answers biggest first in a period (averaged over the cut columns shown), leaving out none/other/don't know."""
    shown = ~np.isnan(fig["pct"][period])
    values = np.where(shown.any(axis=0), np.nansum(fig["pct"][period], axis=0) / np.maximum(shown.sum(axis=0), 1), np.nan)
    order = [i for i in np.argsort(-np.nan_to_num(values, nan=-1)) if not math.isnan(values[i]) and not SKIP.match(fig["answers"][i])]
    return order


def say_period(label: str) -> str:
    """A period as a sentence says it: on a wave's day ("on 9 Nov 2026"), over a span, in a month, quarter or year."""
    return f"over {label}" if "–" in label else f"on {label}" if label[:1].isdigit() else f"in {label}"


def single_choice(fig: dict, column: int = 0) -> bool:
    """Whether every period's answers add up to 100% in this column (one answer a person): a whole split into parts,
    not a list of answers to rank."""
    totals = [t for t in np.nansum(fig["pct"][:, column], axis=1) if t]
    return bool(totals) and all(abs(t - 100) <= 1.5 for t in totals)


def common_base(cells) -> int:
    """Return the base shared by every displayed cell, or zero if no one base applies."""
    bases = set(cells) - {None}
    return bases.pop() if len(bases) == 1 else 0


def chart(fig: dict, shown: list[int], named: bool = False) -> dict | None:
    """The chart that fits the figures (the dataviz skill's forms, 15 Nov 2026). Over time: a line (a yes/no draws its
    main answer alone: the other line only mirrors it), a dumbbell for two periods compared (before → after per answer), one line
    per group by a cut. One period by a cut: 100% stacked bars for a single choice of a few answers, a heatmap for many
    answers by four groups or more, else grouped bars. One period: one segmented bar for a single choice of up to six
    answers, else bars, biggest first. None when no answer has a figure to draw (a cut whose groups were never asked it:
    the question bank found two, 12 Nov 2026), so the answer is the table and its sentences."""
    if not shown:
        return None
    pct = lambda p, c, a: None if math.isnan(fig["pct"][p, c, a]) else float(fig["pct"][p, c, a])   # noqa: E731
    periods, columns, answers = fig["periods"], fig["columns"], fig["answers"]
    # every answer with a figure in the survey's own order (a scale or a progress keeps it: dataviz), none/other/don't
    # know last: the parts that make a single choice's 100%
    every = sorted((a for a in range(len(answers)) if not np.all(np.isnan(fig["pct"][-1, :, a]))), key=lambda a: (bool(SKIP.match(answers[a])), a))
    if len(periods) > 1:
        if len(columns) > 1:   # a trend by a cut: one line per group for the main answer, never one group unlabelled
            series = [{"name": f"{v}: {answers[shown[0]]}", "data": [pct(p, c, shown[0]) for p in range(len(periods))]}
                      for c, (_, v) in enumerate(columns)]
            return {"type": "line", "categories": [p["label"] for p in periods], "series": series, "unit": "%"}
        if len(periods) == 2 and not fig["grain"]:   # two periods compared (first vs latest), not a trend that has two
            return {"type": "dumbbell", "categories": [answers[a] for a in shown],
                    "series": [{"name": periods[p]["label"], "data": [pct(p, 0, a) for a in shown]} for p in (0, 1)], "unit": "%"}
        lines = shown[:1] if len(every) == 2 and single_choice(fig) else shown   # a yes/no: the other line only mirrors it
        return {"type": "line", "categories": [p["label"] for p in periods],
                "series": [{"name": answers[a], "data": [pct(p, 0, a) for p in range(len(periods))]} for a in lines], "unit": "%"}
    if len(columns) > 1:
        stacked = all(single_choice(fig, c) for c in range(len(columns))) and len(every) <= SPLIT_MAX
        rows = every if stacked else ((shown if len(shown) >= HEATMAP_MIN or named else ranked(fig)[:8]) if len(columns) >= HEATMAP_MIN else shown)
        bases = {v: base for c, (_, v) in enumerate(columns)
                 if (base := common_base(int(fig["bases"][0, c, a]) for a in rows if pct(0, c, a) is not None))}
        if stacked:
            return {"type": "stacked", "categories": [v for _, v in columns], "bases": bases,
                    "series": [{"name": answers[a], "data": [pct(0, c, a) for c in range(len(columns))]} for a in rows], "unit": "%"}
        return {"type": "heatmap" if len(columns) >= HEATMAP_MIN and len(rows) >= HEATMAP_MIN else "grouped", "categories": [answers[a] for a in rows], "bases": bases,
                "series": [{"name": v, "data": [pct(0, c, a) for a in rows]} for c, (_, v) in enumerate(columns)], "unit": "%"}
    if single_choice(fig) and len(every) <= SPLIT_MAX:
        return {"type": "split", "categories": [answers[a] for a in every],
                "series": [{"name": periods[0]["label"], "data": [pct(0, 0, a) for a in every]}], "unit": "%"}
    keep = shown if len(shown) > 1 else ranked(fig)[:12]
    return {"type": "bar", "categories": [answers[a] for a in keep],
            "series": [{"name": periods[0]["label"], "data": [pct(0, 0, a) for a in keep]}], "unit": "%"}


def write(plan: dict, fig: dict, doc: dict, named: list[int]) -> tuple[list[str], list[int]]:
    """The answer's sentences, and the answers they are about."""
    periods, columns, kind = fig["periods"], fig["columns"], plan["kind"]
    asked = fig["asked"]
    say = [f"From “{doc['text'][:220]}” ({FAMILY.get(doc['family'], doc['family'].replace('_', ' ').title())}, "
           f"{doc['qcode']}, asked in {len(asked)} {'wave' if len(asked) == 1 else 'waves'}, "
           f"{ask_figures.label_date(asked[0])} – {ask_figures.label_date(asked[-1])})."]
    base = lambda p, c, a: int(fig["bases"][p, c, a])   # noqa: E731
    people = lambda p, c, a: int(fig["people"][p, c, a])   # noqa: E731
    shown = named or ranked(fig)[: (plan["top"] or TOP) if kind == "top" else (SERIES if len(periods) > 1 else 3)]
    if kind == "top":   # biggest first, whatever order they were named in
        shown = sorted(shown, key=lambda a: -np.nan_to_num(fig["pct"][-1, 0, a], nan=-1))
    if len(columns) > 1:
        dim = columns[0][0].replace("_", " ")
        for a in shown[:3]:
            parts = [f"{v} {fmt(fig['pct'][-1, c, a])}" for c, (_, v) in enumerate(columns) if not math.isnan(fig['pct'][-1, c, a])]
            say.append(f"By {dim}, “{fig['answers'][a]}” {say_period(periods[-1]['label'])}: " + ", ".join(parts) + ".")
    elif len(periods) > 1 and (kind == "trend" or fig["grain"]):
        grain = {"wave": "wave by wave", "biweek": "every two weeks", "4week": "every four weeks", "month": "by month",
                 "quarter": "by quarter", "year": "by year"}.get(fig["grain"], "")
        latest = max((p for p in range(len(periods)) if periods[p]["waves"]), default=len(periods) - 1)
        for a in shown[:1]:   # the newest figure first: what an analyst asks "how many" or "what share" about
            if not math.isnan(fig["pct"][latest, 0, a]):
                n, b = people(latest, 0, a), base(latest, 0, a)
                among = f" among {columns[0][1]}" if columns[0][0] != "total" else ""
                # the finding first, then when and of how many (Pew Research's headlines; the page shows this sentence first)
                say.append(f"{n:,} of {b:,} respondents{among} ({fmt(fig['pct'][latest, 0, a])}) answered “{fig['answers'][a]}” {say_period(periods[latest]['label'])}, the latest."
                           if plan["kind"] == "count" else
                           f"{fmt(fig['pct'][latest, 0, a])}{among} answered “{fig['answers'][a]}” {say_period(periods[latest]['label'])}, the latest ({n:,} of {b:,} respondents).")
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
            say.append(f"“{fig['answers'][a]}”: {fmt(fig['pct'][0, 0, a])} {say_period(periods[0]['label'])} (n={base(0, 0, a):,}) vs "
                       f"{fmt(fig['pct'][1, 0, a])} {say_period(periods[1]['label'])} (n={base(1, 0, a):,}), {change[0]:+.1f} pts"
                       f"{' — a significant change' if change[1] else ', not a significant change'}.")
    else:
        when = periods[0]["label"] + (f" ({len(periods[0]['waves'])} waves pooled)" if len(periods[0]["waves"]) > 1 else "")
        among = f" among {columns[0][1]}" if columns[0][0] != "total" else ""   # one cut value asked for: "Gen Z"
        if kind == "top":   # the group named too: "Top 5 in 9 Nov" for Gen Z alone read as everyone's (13 Nov 2026)
            say.append(f"Top {len(shown)}{among} {say_period(when)}: " + "; ".join(
                f"{i + 1}. {fig['answers'][a]} {fmt(fig['pct'][0, 0, a])}" for i, a in enumerate(shown)) + ".")
        for a in shown if kind != "top" else shown[:1]:
            if math.isnan(fig["pct"][0, 0, a]):
                continue
            say.append(f"{people(0, 0, a):,} of {base(0, 0, a):,} respondents{among} ({fmt(fig['pct'][0, 0, a])}) answered “{fig['answers'][a]}” {say_period(when)}."
                       if kind == "count" else
                       f"{fmt(fig['pct'][0, 0, a])}{among} answered “{fig['answers'][a]}” {say_period(when)} ({people(0, 0, a):,} of {base(0, 0, a):,} respondents).")
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


def brief(plan: dict, fig: dict, doc: dict, shown: list[int], named: bool = False) -> dict:
    """The answer at a glance, from the same figures as its sentences (the Ask page leads with it): up to three stat
    tiles, the main figure first (by a cut: highest, lowest and their gap, tested; over time: latest, change since the
    first, latest change; one period: the answers shown), and one sentence on what the figures tell (a gap, a change and
    a record, a lead). 15 Nov 2026."""
    periods, columns, answers = fig["periods"], fig["columns"], fig["answers"]
    pct = lambda p, c, a: None if math.isnan(fig["pct"][p, c, a]) else float(fig["pct"][p, c, a])   # noqa: E731
    respondents = lambda p, c, a: f"{int(fig['people'][p, c, a]):,} of {int(fig['bases'][p, c, a]):,} respondents"   # noqa: E731
    if not shown:
        return {"tiles": [], "takeaway": ""}
    main, tiles, takeaway = shown[0], [], ""
    # a yes or a no is said with its question: a bare "Yes, Nov 2026" told a client nothing (the gas-prices answer)
    name = (doc.get("name") or doc["text"][:60]).strip().rstrip("?.")
    plain = lambda a: f"{name}: {answers[a].lower()}" if answers[a].lower() in ("yes", "no") else answers[a]   # noqa: E731
    yes_no = answers[main].lower() in ("yes", "no")
    subject, chose = (f"“{answers[main]}” to “{doc['text'].strip()}”", "answered") if yes_no else (f"“{answers[main]}”", "chose")
    if len(columns) > 1 and named and len(shown) >= 2:   # "Walmart and Target by income": the two, group by group
        p, other = len(periods) - 1, shown[1]
        gaps = [(pct(p, c, main) - pct(p, c, other), v) for c, (_, v) in enumerate(columns)
                if pct(p, c, main) is not None and pct(p, c, other) is not None
                and min(fig["bases"][p, c, main], fig["bases"][p, c, other]) >= SMALL_BASE]
        if gaps:
            ahead = sum(g > 0 for g, _ in gaps)
            lead, behind = (main, other) if ahead * 2 >= len(gaps) else (other, main)
            sized = sorted(abs(g) for g, _ in gaps)
            widest = max(gaps, key=lambda x: abs(x[0]))
            when = say_period(periods[p]["label"])
            kind = {"income_band": "income", "age_band": "age", "census_region": "region", "urbanicity": "area"}.get(columns[0][0], columns[0][0])
            left_out = len(columns) - len(gaps)
            takeaway = (f"“{answers[lead]}” is ahead of “{answers[behind]}” in all {len(gaps)} {kind} groups {when}, by {sized[0]:.1f} to {sized[-1]:.1f} points"
                        if ahead in (0, len(gaps)) else
                        f"“{answers[lead]}” is ahead of “{answers[behind]}” in {max(ahead, len(gaps) - ahead)} of {len(gaps)} {kind} groups {when}; "
                        f"the widest gap is {abs(widest[0]):.1f} points among {widest[1]}, where “{answers[main if widest[0] > 0 else other]}” leads") + \
                (f" ({left_out} {'group' if left_out == 1 else 'groups'} under {SMALL_BASE} respondents left out)." if left_out else ".")
            tiles = [{"label": f"Widest gap: {widest[1]}", "value": f"{abs(widest[0]):.1f} pts", "note": f"{answers[main]} vs {answers[other]}"}] + [
                {"label": f"{answers[a]}: highest", "value": fmt(top[0]), "note": top[1]}
                for a in (main, other) if (top := max(((pct(p, c, a), v) for c, (_, v) in enumerate(columns) if pct(p, c, a) is not None
                                                       and fig["bases"][p, c, a] >= SMALL_BASE), default=None))]
            return {"tiles": tiles, "takeaway": takeaway}
    if len(columns) > 1:
        p = len(periods) - 1
        groups = sorted(((pct(p, c, main), v, int(fig["bases"][p, c, main])) for c, (_, v) in enumerate(columns)
                         if pct(p, c, main) is not None and fig["bases"][p, c, main] >= SMALL_BASE), reverse=True)   # never a "highest" of 3 people
        if len(groups) >= 2:
            (high, top, top_base), (low, bottom, bottom_base) = groups[0], groups[-1]
            tested = "significant" if ask_figures.significant(high, top_base, low, bottom_base) else "not significant"
            note = f"{plain(main)}, {periods[p]['label']}"
            tiles = [{"label": f"Highest: {top}", "value": fmt(high), "note": note}, {"label": f"Lowest: {bottom}", "value": fmt(low), "note": note},
                     {"label": "Gap", "value": f"{high - low:.1f} pts", "note": f"{top} vs {bottom}, {tested}"}]
            left_out = sum(1 for c in range(len(columns)) if pct(p, c, main) is not None and fig["bases"][p, c, main] < SMALL_BASE)
            takeaway = (f"{subject} runs from {fmt(low)} among {bottom} to {fmt(high)} among {top} {say_period(periods[p]['label'])}, "
                        f"a {high - low:.1f}-point gap" + (f" ({left_out} {'group' if left_out == 1 else 'groups'} under {SMALL_BASE} "
                        "respondents left out)." if left_out else "."))   # the chart shows them: say why "highest" skips them
    elif len(periods) > 1:
        line = [(p, pct(p, 0, main)) for p in range(len(periods)) if pct(p, 0, main) is not None]
        if line:
            (first, was), (latest, now) = line[0], line[-1]
            tiles = [{"label": f"{plain(main)}, {periods[latest]['label']}", "value": fmt(now), "note": respondents(latest, 0, main)}]
            if len(line) > 1:
                tiles.append({"label": f"Change since {periods[first]['label']}", "value": f"{now - was:+.1f} pts", "note": f"{fmt(was)} → {fmt(now)}"})
            change = ask_figures.moved(fig, main)
            if change and len(line) > 2:
                tiles.append({"label": "Latest change", "value": f"{change[0]:+.1f} pts", "note": "significant" if change[1] else "not significant"})
            values = [v for _, v in line]
            record = "" if len(line) < 3 else ", the highest in this series" if now == max(values) else ", the lowest in this series" if now == min(values) else ""
            since = f", {'up' if now > was else 'down'} {abs(now - was):.1f} points since {periods[first]['label']}" if round(now - was, 1) else ""
            takeaway = f"{say_share(now)} {chose} {subject} {say_period(periods[latest]['label'])}{since}{record}."
    else:
        rows = sorted(((pct(0, 0, a), a) for a in shown if pct(0, 0, a) is not None), reverse=True)
        tiles = [{"label": plain(a), "value": f"{int(fig['people'][0, 0, a]):,}" if plan["kind"] == "count" else fmt(share),
                  "note": respondents(0, 0, a)} for share, a in rows[:3]]
        if len(rows) >= 2 and not yes_no:
            (top_share, top), (next_share, runner_up) = rows[0], rows[1]
            # "most common" and "leads" only for the first of all the answers, not of the few named (Better and Worse of three)
            lead = ("is the most common answer at" if single_choice(fig) else "leads at") if ranked(fig)[:1] == [top] else "is at"
            takeaway = f"“{answers[top]}” {lead} {fmt(top_share)}, {top_share - next_share:.1f} points ahead of “{answers[runner_up]}” ({fmt(next_share)})."
        elif pct(0, 0, main) is not None:
            takeaway = f"{say_share(pct(0, 0, main))} {chose} {subject} {say_period(periods[0]['label'])}."
    return {"tiles": tiles, "takeaway": takeaway}


def follow_ups(plan: dict, fig: dict, doc: dict, named: list[int]) -> list[dict]:
    """Questions to continue the analysis, made from what this survey question can answer (a cut its data holds, its other
    waves, its first and latest wave): no model and nothing stored, each answerable by construction. Each carries its
    survey question's key for api/main.py ask: by words alone, shared names sent 20 of 521 to another question (15 Nov 2026)."""
    # a period in a name or wording ("Previous year's…", "…last year") would narrow every follow-up; "current" is the latest
    name = (doc.get("name") or doc["text"][:80]).strip().rstrip("?.")
    if names_a_period(name):   # "Previous year's Prime Day purchases": the wording instead, whose own time words are checked below
        name = doc["text"][:120].strip().rstrip("?.")
    lead = [fig["answers"][a] for a in named[:1] if not GENERIC.match(fig["answers"][a])]   # "Amazon …", never "Yes …"
    subject = f"{lead[0]} {name[:1].lower()}{name[1:]}" if lead else name
    # the wording too has a period ("…the Prime Day promotion last year"): every follow-up would ask about it. And a
    # demographic question is the sample's make-up: its "Age group over time" read "age group" as a cut (15 Nov 2026)
    if names_a_period(subject) or doc.get("area") == "demographics":
        return []
    questions = []
    if not plan["cuts"]:
        questions += [f"{subject} by {words}" for dim, words in FOLLOW_CUTS if dim in doc["cuts"]]
    if len(fig["periods"]) == 1 and doc["waves"] >= 3:
        questions.append(f"{subject} over time")
    elif len(fig["periods"]) > 2 and len(fig["columns"]) == 1:
        questions.append(f"{subject} in the first and latest wave")   # the subject first, as written: no capital mid-sentence
    return [{"question": q, "key": doc["key"]} for q in questions[:3]]


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
    if keep.get("key") in index.docs:   # its survey question's wording: found again if a publish renumbers the key
        keep["text"] = index.docs[keep["key"]]["text"]
    path = ask_model.LOGS / "ask-verified.json"
    with ANSWERS_LOCK:
        try:
            saved = json.loads(path.read_text())
        except FileNotFoundError:
            saved = []
        except ValueError as exc:   # saving over it kept only the new answer: every admin's verified answer lost (15 Nov 2026)
            raise ValueError(f"{path.name} cannot be read ({exc}): repair or move it, then save again") from exc
        saved = [v for v in saved if v["question"].lower() != keep["question"].lower()] + [keep]
        path.parent.mkdir(exist_ok=True)
        part = path.with_suffix(f".{os.getpid()}.part")   # written whole, then put in place: a kill mid-write left half a file
        part.write_text(json.dumps(saved, indent=1))
        os.replace(part, path)
        clear_answers()
    index.load_verified()
    return {"saved": keep, "verified": len(index.verified)}


def learn(reading: dict, index: Index) -> None:
    """Keeps the AI check's reading of a question (logs/ask-learned.json, on /home so a deploy keeps it, newest LEARNED_KEPT)
    and loads it at once: the same or a close question (Index.verified_for) is then answered from it with no AI call. The
    small model learns from the large one as it is used ("Cache & Distil", ACL 2024); the file is also training data."""
    keep = {k: reading[k] for k in ("question", "key", "code", "family", "focus", "kind", "cut", "period") if k in reading}
    keep["model"] = ask_model.model()   # reused only while this model is the AI (Index.load_verified)
    keep["text"] = index.docs.get(keep.get("key"), {}).get("text", "")   # found again by wording if a publish renumbers the key
    if not keep.get("question") or not keep.get("key"):
        return
    with LEARN_LOCK:
        learned = [v for v in read_json(LEARNED) or [] if v.get("question", "").lower() != keep["question"].lower()]
        LEARNED.parent.mkdir(exist_ok=True)
        part = LEARNED.with_suffix(f".{os.getpid()}.part")
        part.write_text(json.dumps((learned + [keep])[-LEARNED_KEPT:], indent=0))
        os.replace(part, LEARNED)
    index.load_verified()
    with ANSWERS_LOCK:   # a kept quick answer to it, or to a close question, is out of date: the same wording showed it
        clear_answers()


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


def lacks_group(fig: dict, plan: dict) -> bool:
    """A demographic group the question asks about has no figures in fig: answer() tries the next close match, then says so."""
    if not plan["cuts"]:
        return False
    dimension, groups = next(iter(plan["cuts"].items()))
    available = {value for col, (cut, value) in enumerate(fig["columns"])
                 if cut == dimension and not np.isnan(fig["pct"][:, col]).all()}
    return not available or (groups != "all" and bool(set(groups) - available))


def add_net(question: str, fig: dict, counts: dict, nets: list[tuple[str, list[int]]]) -> int | None:
    """The answer a dashboard tile's name in the question stands for, and its place in fig; None when none fits. The
    most specific name wins ("not started" is Not yet started, not Started). A tile counting several answers is added
    to fig as one more answer, its people summed, on a single-choice question only (its people add up). "What share
    started holiday shopping?" led with Still shopping alone; Started is Still shopping plus Finished shopping, as the
    Holiday dashboard shows it (21 Nov 2026)."""
    words = set(stems(question)) | ({"not"} if re.search(r"n't\b|\bnever\b", question.lower()) else set())
    for label, codes in sorted(nets, key=lambda net: -len(stems(net[0]))):
        parts = [i for i, (_, code, _) in enumerate(counts["answers"]) if code in codes]
        if not parts or not set(stems(label)) <= words:
            continue
        if len(parts) == 1:
            return parts[0]
        if not single_choice(fig):
            continue
        people = fig["people"][:, :, parts].sum(axis=2)
        bases = fig["bases"][:, :, parts].max(axis=2)   # one base a column: a single choice
        hidden = np.isnan(fig["pct"][:, :, parts]).any(axis=2)
        pct = np.array([np.nan if off else round(100 * n / b, 1) for n, b, off in zip(people.ravel(), bases.ravel(), hidden.ravel())]).reshape(people.shape)
        fig["people"], fig["bases"], fig["pct"] = (np.concatenate([fig[k], new[:, :, None]], axis=2)
                                                   for k, new in (("people", people), ("bases", bases), ("pct", pct)))
        fig["answers"] = fig["answers"] + [f"{label} ({' + '.join(fig['answers'][i] for i in parts)})"]
        return len(fig["answers"]) - 1
    return None


def lacking(plan: dict, key: str, index: Index) -> tuple[list[str], int, bool]:
    """The question's subject words that a survey question never uses (its wording, name, aliases, topic or answers, or
    a synonym of the word), how many subject words there are, and whether one of them no survey uses at all."""
    lacking, unknown, words = [], False, 0
    for word in dict.fromkeys(w for w in re.findall(r"[a-z0-9]+", plan["about"].replace("'", "")) if w not in FRAME_WORDS and stems(w)):   # as the index splits ("glp-1")
        # a misspelt word counts as the word it is close to, a synonym list's word as its list ("glp1" is GLP-1)
        stem = index.known(word) or next((s for s in stems(word) if s in index.synonyms), None)
        words += 1
        if stem is None:
            unknown = True
            lacking.append(word)
        elif not any(key in index.postings.get(s, ()) for s in index.synonyms.get(stem, set()) | {stem}):
            lacking.append(word)
    return lacking, words, unknown


def unasked(plan: dict, key: str, index: Index) -> list[str]:
    """The subject words the chosen survey question lacks, when they show it asks about something else: all of two or
    more, three or more, or two with one no survey uses at all. "Fed rate cuts" and "saving more money" were answered
    from the gas-prices question; right answers in the golden, fresh and researched sets miss at most two such words, never
    every one and none unknown (21 Nov 2026), so an empty list means the pick stands."""
    missing, words, unknown = lacking(plan, key, index)
    # ponytail: counts words, not meaning; the reranker in the Colab plan can replace it once it beats the golden set
    return missing if len(missing) >= 3 or (unknown and len(missing) >= 2) or (words >= 2 and len(missing) == words) else []


REPORT = yaml.safe_load((Path(__file__).resolve().parents[1] / "config" / "weekly_report.yml").read_text())
OVERVIEW = re.compile(r"\b(summar(?:y|ise|ize)|overview|snapshot|big picture|key (?:findings|takeaways|figures)|highlights|"
                      r"state of the (?:us |american )?consumers?|consumer (?:mood|pulse)|"
                      r"how (?:do|are) (?:us |american )?(?:consumers|people|shoppers|americans) (?:feel(?:ing)?|doing)|"
                      r"(?:this|latest) week'?s? (?:survey|results|findings|picture))\b")


def overview(question: str, plan: dict, index: Index, visible: set[int], quick: bool) -> dict | None:
    """"Summarize this week", "How do consumers feel?": one line from each question the weekly report reads
    (config/weekly_report.yml ask_overview), each answered by answer() from its own survey question with the
    question's period and group, the sentiment ones as net better (% better − % worse, as the report says it). What
    ChatGPT does with several sources, from the survey's own figures (21 Nov 2026). None when no line can be answered."""
    rest = OVERVIEW.sub(" ", plan["question"])
    rest = " ".join(w for w in re.findall(r"[a-z0-9$'-]+", rest) if w not in {
        "how", "do", "does", "are", "is", "what", "feel", "feeling", "doing", "the", "of", "us", "american", "consumer", "consumers",
        "people", "shoppers", "americans", "me", "give", "show", "please", "can", "you", "survey", "results", "findings", "an", "a"})
    if ask_reader.read(rest)["about"]:   # "Summarize tariff concerns": a subject of its own, answered as any question
        return None
    lines, parts, tiles, first = [], [], [], None
    for item in REPORT.get("ask_overview", []):
        docs = [(k, d) for k, d in index.docs.items() if d["family"] == REPORT["family"] and d["qcode"] == item["question"]
                and not visible.isdisjoint(d["surveys"])]
        if not docs:
            continue
        key = max(docs, key=lambda kd: kd[1]["last"])[0]
        found = answer(rest or "latest", index, visible, quick, key)
        if found["mode"] != "figures" or not found.get("table"):
            continue
        rows, said = found["table"]["rows"], found.get("takeaway") or found.get("headline", "")
        if item.get("net") and len(found["table"]["head"]) == 2:
            share = lambda words: sum(r[1] or 0 for r in rows if any(w in r[0].lower() for w in words))   # noqa: E731
            better, worse = share(REPORT["net_words"]["positive"]), share(REPORT["net_words"]["negative"])
            said = f"net better {better - worse:+.1f} ({better:.1f}% better, {worse:.1f}% worse)"
            tiles.append({"label": item["name"], "value": f"{better - worse:+.1f}", "note": f"net better, {found['scope']['period']}"})
        first = first or found
        parts.append({"name": item["name"], "text": said, "qcode": found["sources"][0]["qcode"], "link": found["sources"][0]["link"]})
        lines.append(f"{item['name']}: {said}")
        found["sources"][0]["id"] = f"S{len(parts)}"
        parts[-1]["source"] = found["sources"][0]
    if not parts:
        return None
    scope = first.get("scope")
    when = scope["period"] if scope else ""
    base = f" ({scope['base']:,} respondents)" if scope and scope.get("base") else ""
    lead = (", ".join(f"{t['label'].lower()} net better {t['value']}" for t in tiles) + "." if tiles else lines[0])
    groups = [v for values in plan["cuts"].values() if values != "all" for v in values]
    base = (f" among {' and '.join(groups)}" if groups else "") + base
    return {**first, "answer": "\n".join([f"The weekly US survey, {when}{base}:"] + lines), "chart": None, "table": None,
            "headline": f"The weekly US survey, {when}{base}: {lead}", "takeaway": "", "points": [], "notes": [],
            "overview": [{k: p[k] for k in ("name", "text", "qcode", "link")} for p in parts], "tiles": tiles[:3],
            "sources": [p["source"] for p in parts], "understood": "named", "check": False,
            "next": [{"question": f"{p['name']} over time", "key": p["source"]["key"]} for p in parts[:3]]}


def bit_mask(hexed: str | None, size: int) -> np.ndarray:
    """A people.json bitset (hex, respondent i = bit i) as booleans in seat order."""
    value = int(hexed or "0", 16)
    return np.unpackbits(np.frombuffer(value.to_bytes((size + 7) // 8, "little"), np.uint8), bitorder="little")[:size].astype(bool)


@functools.lru_cache(maxsize=2048)
def weights_of(path: Path) -> np.ndarray | None:
    """One wave's Census weight per respondent, in people.json's seat order: the ETL's (shared/data/payloads.py
    people, from 21 Nov 2026), or for a publication before them raked here from the same file's gender, age and
    region, as etl/weighting.py does. None when the wave has no people file."""
    try:
        people = json.loads(gzip.decompress(path.read_bytes()))
    except OSError:
        return None
    if "weights" in people:
        return np.array(people["weights"], float)
    size = max((int(h, 16).bit_length() for h in [*(h for values in people["cuts"].values() for h in values.values()),
                                                   *(h for q in people["questions"].values() for h in q["bits"].values())]), default=0)
    config = weighting.targets()
    seats: dict[int, dict] = {i: {} for i in range(size)}
    for margin in config["margins"]:
        for value, hexed in people["cuts"].get(margin, {}).items():
            for i in np.flatnonzero(bit_mask(hexed, size)):
                seats[int(i)][margin] = value
    raked = weighting.rake(seats, config["margins"], (config["trim_low"], config["trim_high"]))
    return np.array([raked[i] for i in range(size)], float)


def weighted_counts(people: dict, weights: np.ndarray, qcode: str, answers: list[str], groups: list[np.ndarray | None]):
    """Weighted people and bases (answers × groups) of one wave's question, a group a respondent mask (None: everyone);
    an answer the wave does not have stays NaN. A single choice's base is those who answered its row, a select-all's
    those who answered the question (bit 0,0), as srv_result counts them."""
    size, question = len(weights), people["questions"].get(qcode)
    n, b = np.full((len(answers), len(groups)), np.nan), np.full((len(answers), len(groups)), np.nan)
    if not question:
        return n, b
    rows, items = {}, {}
    for item_id, option_id, item_label, _, option_label in question["rows"]:
        chosen = bit_mask(question["bits"].get(f"{item_id},{option_id}"), size)
        name = f"{item_label}: {option_label}" if item_label and option_label and item_label != option_label else option_label or item_label
        rows[name] = (item_id, option_id, chosen)
        rows.setdefault(option_label or item_label, (item_id, option_id, chosen))   # the cross-tab files' label
        if option_id:
            items[item_id] = items.get(item_id, np.zeros(size, bool)) | chosen
    answered = bit_mask(question["bits"].get("0,0"), size) if "0,0" in question["bits"] else None
    for a, name in enumerate(answers):
        if name not in rows:
            continue
        item_id, option_id, chosen = rows[name]
        base = items[item_id] if option_id else answered
        if base is None:
            continue
        for g, group in enumerate(groups):
            inside = np.ones(size, bool) if group is None else group
            n[a, g], b[a, g] = weights[chosen & inside].sum(), weights[base & inside].sum()
    return n, b


def weigh(fig: dict, counts: dict, index: Index):
    """fig's shares Census-weighted (gender, age, region) for any group, from each wave's respondents and weights
    (people.json): a pooled period sums its waves' weighted people and bases. A period where a shown figure has no
    weighted twin (a wave with no people file) is all NaN, and answer() leaves it out: never half and half. 21 Nov 2026."""
    folder, out = index.root.parent / "waves", np.full(fig["pct"].shape, np.nan)
    for p, period in enumerate(fig["periods"]):
        people_n = np.zeros(out.shape[1:][::-1])
        people_b = np.zeros(out.shape[1:][::-1])
        for sid in period["waves"]:
            path = folder / str(sid) / "people.json.gz"
            weights = weights_of(path)
            if weights is None or sid not in counts["sources"]:
                people_b[:] = np.nan
                break
            people = json.loads(gzip.decompress(path.read_bytes()))
            groups = [None if dim == "total" else bit_mask(people["cuts"].get(dim, {}).get(value), len(weights)) for dim, value in fig["columns"]]
            n, b = weighted_counts(people, weights, counts["sources"][sid][0], fig["answers"], groups)
            people_n, people_b = people_n + np.nan_to_num(n), people_b + np.nan_to_num(b)
        with np.errstate(divide="ignore", invalid="ignore"):
            out[p] = np.where(people_b.T > 0, np.round(100 * people_n.T / people_b.T, 1), np.nan)
    out[(~np.isnan(fig["pct"]) & np.isnan(out)).any(axis=(1, 2))] = np.nan
    out[np.isnan(fig["pct"])] = np.nan
    return out


POOL_WEEKS = 4   # two groups at once ("Gen Z women") are few in one wave of ~400: the Cross-tab screen's 4-week pool


def two_groups(question: str, plan: dict, index: Index, visible: set[int], quick: bool, key: str | None = None,
               weighted: bool = False) -> dict | None:
    """A question naming two kinds of group at once ("Gen Z women", "Amazon by generation and gender"): the survey
    question found as for any question, then its figures by both cuts from each wave's published cut file (the
    Cross-tab screen's, shared/data/payloads.py crosstab_from), the latest POOL_WEEKS waves pooled. None when the
    question without its groups is not about anything. 21 Nov 2026."""
    text = " " + plan["question"] + " "
    for pattern, *_ in ask_reader.CUT_DIMS + ask_reader.CUT_VALUES:
        text = re.sub(rf"(?:\b(?:among|for|by)\s+)?(?:{pattern})", " ", text)
    text = re.sub(r"\s(?:and|vs\.?|versus|or)\s+(?=(?:and|vs\.?|versus|or|among|in|over)\b|\W*$)", " ", text)
    if not ask_reader.read(text)["about"]:
        return None
    inner = answer(text, index, visible, quick, key)
    if inner["mode"] != "figures":
        return inner
    source = inner["sources"][0]
    survey_id, qcode = source["survey_id"], source["qcode"]
    folder = index.root.parent / "waves"
    if not (folder / str(survey_id) / "cuts" / f"{qcode}.json.gz").exists():
        return no_figure("Figures by two groups at once are not published for this survey question. Try one group, or open Cross-tabs.", plan, inner["suggestions"])
    family = {sid: {**w, "prior_survey_id": w.get("prior_survey_id")} for sid, w in index.waves.items()
              if sid in visible and w.get("survey_family") == index.waves[survey_id].get("survey_family")}
    parts = {w["survey_id"]: json.loads(gzip.decompress(path.read_bytes())) for w in payloads.chain(family, survey_id, POOL_WEEKS)
             if (path := folder / str(w["survey_id"]) / "cuts" / f"{qcode}.json.gz").exists()}
    pool = [family[sid] for sid in parts]
    (first, wanted1), (second, wanted2) = plan["cuts"].items()
    rows = payloads.crosstab_from(survey_id, qcode, (first, second), pool, parts)["rows"]
    rows = [r for r in rows if (wanted1 == "all" or r[0] in wanted1) and (wanted2 == "all" or r[1] in wanted2) and r[7] is not None]
    if not rows:
        return no_figure("At least one requested demographic group is unavailable for this survey question. Try a different group or ask for all respondents.", plan, inner["suggestions"])
    label = lambda r: r[4] or r[2]   # noqa: E731  a single choice's option, a select-all's item
    combos = list(dict.fromkeys(f"{r[0]} · {r[1]}" for r in rows))
    cell = {(label(r), f"{r[0]} · {r[1]}"): r for r in rows}
    weighting = "unweighted"
    if weighted:   # each wave's respondents in both groups, Census-weighted (weigh), pooled as the counts are
        pairs = [tuple(c.split(" · ")) for c in combos]
        names = list(dict.fromkeys(label(r) for r in rows))
        n, b = np.zeros((len(names), len(pairs))), np.zeros((len(names), len(pairs)))
        for sid in parts:
            path = folder / str(sid) / "people.json.gz"
            weights = weights_of(path)
            if weights is None:
                b[:] = np.nan
                break
            people = json.loads(gzip.decompress(path.read_bytes()))
            groups = [bit_mask(people["cuts"].get(first, {}).get(v1), len(weights)) & bit_mask(people["cuts"].get(second, {}).get(v2), len(weights))
                      for v1, v2 in pairs]
            wn, wb = weighted_counts(people, weights, qcode, names, groups)
            n, b = n + np.nan_to_num(wn), b + np.nan_to_num(wb)
        if not np.isnan(b).any() and all(b[names.index(label(r)), combos.index(f"{r[0]} · {r[1]}")] > 0 for r in rows):
            weighting = "weighted"
            cell = {(a, c): [*cell[a, c][:5], round(n[i, j] * cell[a, c][6] / b[i, j]), cell[a, c][6], 100 * n[i, j] / b[i, j], *cell[a, c][8:]]
                    for (a, c) in cell for i, j in [(names.index(a), combos.index(c))]}
    answers = list(dict.fromkeys(label(r) for r in rows))
    pooled = lambda a: sum(r[5] for r in rows if label(r) == a) / max(1, sum(r[6] for r in rows if label(r) == a))   # noqa: E731
    named = [a for a in inner.get("verify", {}).get("focus", []) if a in answers]
    shown = named or sorted(answers, key=pooled, reverse=True)[:1 if len(combos) > 1 else 8]
    main = shown[0]
    dates = sorted(index.waves[sid]["wave_date"] for sid in parts)
    span = ask_figures.label_date(dates[0]) + (f" – {ask_figures.label_date(dates[-1])}" if len(dates) > 1 else "")
    period = f"on {span}" if len(dates) == 1 else f"over {span} ({len(dates)} waves pooled)"
    figure = lambda a, c: round(cell[a, c][7], 1) if (a, c) in cell else None   # noqa: E731
    sure = [(round(cell[main, c][7], 1), c, cell[main, c]) for c in combos if (main, c) in cell and cell[main, c][6] >= SMALL_BASE]
    group = combos[0].replace(" · ", " ")
    if len(combos) == 1 and plan["kind"] == "top":
        headline = f"Top {min(len(shown), plan['top'] or TOP)} among {group} {period}: " + "; ".join(
            f"{i + 1}. {a} {figure(a, combos[0]):.1f}%" for i, a in enumerate(shown[:plan["top"] or TOP])) + "."
    elif len(combos) == 1:
        r = cell.get((main, combos[0]))
        headline = f"{round(r[7], 1):.1f}% of {group} respondents chose “{main}” {period} ({r[5]:,} of {r[6]:,})." if r else ""
    elif len(sure) >= 2:
        (high, top, _), (low, bottom, _) = max(sure), min(sure)
        left_out = len([c for c in combos if (main, c) in cell]) - len(sure)
        headline = (f"“{main}” runs from {low:.1f}% among {bottom} to {high:.1f}% among {top} {period}, a {high - low:.1f}-point gap"
                    + (f" ({left_out} {'group' if left_out == 1 else 'groups'} under {SMALL_BASE} respondents left out)." if left_out else "."))
    else:
        headline = f"Every group but one has under {SMALL_BASE} respondents for “{main}” {period}: read the figures below with caution."
    listed = shown if len(combos) == 1 else list(dict.fromkeys(shown + sorted(answers, key=pooled, reverse=True)[:5]))
    chart_type = "bar" if len(combos) == 1 else "heatmap" if len(combos) >= HEATMAP_MIN else "grouped"
    series = ([{"name": period, "data": [figure(a, combos[0]) for a in listed]}] if len(combos) == 1 else
              [{"name": c, "data": [figure(a, c) for a in listed]} for c in combos])
    bases = {c: max(r[6] for r in rows if f"{r[0]} · {r[1]}" == c) for c in combos}
    small = [c for c, b in bases.items() if b < SMALL_BASE]
    notes = [f"Figures by {first.replace('_', ' ')} and {second.replace('_', ' ')} at once, from the latest {len(dates)} "
             f"{'wave' if len(dates) == 1 else 'waves'} of this question pooled so each group has more respondents."] + \
            ([("Census-weighted figures (gender, age, region): counts of people are weighted estimates." if weighting == "weighted"
               else "Unweighted figures: these waves have no respondent file to weight.")] if weighted else []) + \
            ([f"Note: small base, under {SMALL_BASE} respondents in {', '.join(small)}: read with caution."] if small else [])
    return {**inner, "answer": "\n".join([inner.get("source_line", ""), headline] + notes), "headline": headline, "takeaway": "",
            "points": [], "notes": notes, "tiles": [{"label": c, "value": f"{v:.1f}%", "note": f"{main}, {r[6]:,} respondents"}
                                                     for v, c, r in sorted(sure, reverse=True)[:3]],
            "chart": {"type": chart_type, "categories": listed, "series": series, "bases": bases, "unit": "%"},
            "table": {"head": ["Answer", *combos], "rows": [[a, *(figure(a, c) for c in combos)] for a in listed],
                      "bases": [bases[c] for c in combos], "cell_bases": [[cell[a, c][6] if (a, c) in cell else None for c in combos] for a in listed]},
            "scope": {**inner["scope"], "period": span, "waves": len(dates), "base": bases[combos[0]] if len(combos) == 1 else 0},
            "sources": [{**source, "waves": len(dates), "link": f"/w/{survey_id}/crosstab/{qcode}?mode=two&a={first}&b={second}&weeks={POOL_WEEKS}"}],
            "next": [], "check": False, "plan": plan, "weighting": weighting}


def no_figure(message: str, plan: dict, suggestions=()) -> dict:
    """Explain why a requested analysis has no sound figure."""
    return {"answer": message, "chart": None, "table": None, "sources": [], "suggestions": list(suggestions),
            "plan": plan, "mode": "none", "no_source": True}


def answer(question: str, index: Index, visible: set[int], quick: bool = False, key: str | None = None, weighted: bool = False) -> dict:
    """{answer, chart, table, sources, suggestions, plan, mode, check, tiles, takeaway, next}: mode "figures" when
    answered, "none" when nothing in the surveys matches (then suggestions lists the closest questions, if any). quick:
    the nearest survey question by meaning and the rules, no model (~100 ms); check is then true when the model's reading
    may differ, and the page asks again without quick to have it read (the Ask page shows the quick answer meanwhile).
    key: a follow-up's survey question (follow_ups), answered from it when this person may see it; else ignored."""
    question = index.correct_spelling(" ".join(str(question).split())[:500])   # "walmrt shoppers" is Walmart's
    plan = ask_reader.read(question)
    text = plan["question"]
    if re.search(r"\b(?:census|survey|population)[ -]weighted\b|\b(?<!un[- ])(?<!not )weighted "
                 r"(?:share|percentage|proportion|averages?|means?|medians?|rates?|estimates?|results?|figures?|counts?|data|by)\b|"
                 r"\b(?<!not )(?<!don't )(?:use|apply) (?:survey |census |population )?(?:weights|weighting)\b", text):
        weighted = True   # "the Census-weighted share": the weighted figures (weigh), the subject without the weighting words
        question = re.sub(r"\b(?:census|survey|population)[ -]weighted\b|\bweighted\b|\b(?:use|apply|with) (?:survey |census |population )?"
                          r"(?:weights|weighting)\b|\b(?:census|survey) weights\b", " ", question, flags=re.I)
        plan = ask_reader.read(question)
        text = plan["question"]
    if re.search(r"\b(?:who also (?:bought|purchased|used|shopped|selected|chose|answered)|"
                 r"(?:bought|purchased|shopped) (?:from|at) both)\b", text):
        return no_figure("This question needs a count of people who did both things. Try Audiences to check for overlap within a survey wave, or ask about each group separately.", plan)
    if re.search(r"\b(?:causal effect|causal impact|did .{1,80} cause|what caused|how much did .{1,80} cause)\b", plan["question"]):
        return no_figure("These survey results cannot establish what caused the change. Try asking what respondents reported or how their answers changed over time.", plan)
    if key is None and OVERVIEW.search(text) and (summed := overview(question, plan, index, visible, quick)):
        return summed
    if len(plan["cuts"]) == 2 and (both := two_groups(question, plan, index, visible, quick, key, weighted)):
        return both
    if len(plan["cuts"]) > 1:
        return no_figure("Ask CIP can show at most two kinds of group at once (for example Gen Z women). Try fewer groups, or Cross-tabs.", plan)
    if re.search(r"\b(?:median|average (?:price|amount|cost|spend(?:ing)?))\b", plan["question"]):
        return no_figure("Ask CIP cannot calculate that spending or price statistic from its published response shares. Try a spending range or ask what share chose one.", plan)
    # an acronym no survey uses ("OTT", "DTC", "HBO"): the surveys do not ask about it, so no nearby figure stands in for it
    # ("How many people has subcription of OTT?" was answered from a meal-kit question, fresh set, 20 Nov 2026). Not when
    # the whole question is in capitals
    missing = [w for w in re.findall(r"\b[A-Z]{3,6}\b", question) if w.lower() not in STOP and not index.known(w.lower())
               and not any(words.search(w.lower()) for words in ask_reader.COUNTRY_WORDS.values())]
    if missing and key not in index.docs and sum(c.islower() for c in question) > sum(c.isupper() for c in question):
        near = index.find(plan["about"] or plan["question"], plan, 4, visible)
        return no_figure(f"The surveys do not ask about {missing[0]}. The closest survey questions are below.", plan,
                         [{"qcode": h["qcode"], "text": h["text"][:200], "family": h["family"], "key": h["key"]} for h in near])
    selected = next((sid for sid in reversed(index.docs[key]["surveys"]) if sid in visible), None) if key in index.docs else None
    if selected is not None:   # a follow-up keeps the selected question's country
        plan["country"] = index.country.get(selected, "US")
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
    by_words = {h["key"]: h["score"] for h in hits}   # the word search's own scores, kept after the reader reorders hits
    understood = "rules"
    margin = None   # how far the question found by meaning beats the next different one (etl/ask_quality.py calibrates the gate on it)
    reading = None
    named, sure = index.named(question, visible, plan)
    if selected is not None:
        named, sure = key, True                                                   # its survey question, by key, the rules reading the rest
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
    # a stored name's question is matched against the verified ones too: an admin's check beats the AI's name ("Categories
    # purchased online in the latest survey" is the weekly q3, verified; its words are EC4's name, 8 waves; 14 Nov 2026)
    # local, ~3 ms each; one when the subject is the whole question (it was embedded twice, review of 15 Nov 2026)
    made = ask_model.embed(list(dict.fromkeys([ask_model.as_query(subject), ask_model.as_query(question)]))) if selected is None and (unsure or named) else None
    asked = made[0] if made is not None else None
    found = [v for v in (index.verified_for(asked), index.verified_for(made[-1] if made is not None else None)) if v
             and not (named and v.get("learned"))]   # an AI's earlier pick never overrules a stored name
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
    # "How many people bought Amazon prime?" is the Prime membership question, not "Amazon" in the retailer lists: the
    # lists went first and the reader took them, sure (fresh set, 15 Nov 2026). A name the questions found by meaning
    # write in full ("Amazon Prime") is read whole, before "latest" drops the older ones.
    # ponytail: any Title Case run counts ("Grocery Shopping" too); 3,211 test questions unchanged; brand names only if one misfires
    full_names = frozenset(n.lower() for c in candidates for n in re.findall(r"\b[A-Z][a-z]+(?: [A-Z][a-z]+)+", c["text"]))
    if any("latest" in w or "last" in w for w in plan["when"]):   # "latest", "last 8 weeks": questions still being asked
        recent = [c for c in candidates if c["last"] >= str(date.fromisoformat(index.newest) - timedelta(days=CURRENT_DAYS))]
        candidates = recent or candidates
    # a retailer or brand named among a long-running question's answers brings it in even when its wording is far in
    # meaning: "Amazon in 2025 vs 2026" is the weekly retailer lists, not one of the Amazon studies (golden set, 11 Nov 2026)
    seen = {c["key"] for c in candidates}
    candidates += [d for k, d in index.docs.items() if candidates and k not in seen and d["waves"] >= TREND_FROM * 5
                   and not visible.isdisjoint(d["surveys"]) and focus(question, d.get("labels", []), full_names)][:3]
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
    candidates.sort(key=lambda c: (0, -c["waves"]) if focus(question, c.get("labels", []), full_names) else (1, 0))
    listed = [{"number": i, "text": c["text"], "name": c.get("name", ""), "family": FAMILY.get(c["family"], c["family"]),
               "waves": c["waves"], "first": c["first"], "last": c["last"],
               "answers": sorted(c.get("labels", []), key=lambda l: -len(topic & set(stems(l))))}   # the answers the question
              for i, c in enumerate(candidates)]   # names first: six are read ("movie theater" was 13th of 15, 13 Nov)
    # Ask's own reader picks from the lines the AI reads (~70 ms, no cost); the AI reads the question only when the
    # reader is unsure (or absent) and a key is set; rules keep any dates the question names
    reader_pick = ask_model.read_pick(ask_reader.by_cut(question), listed) if listed else None
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
        named = [c for c in candidates if c["waves"] >= TREND_FROM * 5 and focus(question, c.get("labels", []), full_names)]
        longest = max(named, key=lambda c: c["waves"], default=None)
        names = [longest["labels"][i] for i in focus(question, longest["labels"], full_names)] if longest else []
        named_stems = {s for n in names for s in stems(n)}
        rest = {s for s in stems(question) if len(s) >= 4} - named_stems   # quick: "Costco shoppers" is not "why Costco"
        # a reading's pick with the name in its wording stands only when the question asks more than the name and a time:
        # "Amazon in 2025 vs 2026" is the retailer lists, though the AI picked Prime membership (14 Nov 2026)
        asks_more = bool({s for s in stems(plan["about"]) if len(s) >= 4} - named_stems)
        # Ask's own reader counts as a reading too, and "buy" as asking more: "What do people buy on TikTok?" is the
        # TikTok purchases question it picked, not the beauty retailers list with TikTok among its answers (21 Nov 2026)
        asks_more = asks_more or by_reader and bool(set(stems(plan["about"])) - named_stems)
        own_name = any(n.lower() in chosen["text"].lower() for n in names) and ((bool(reading) or by_reader) and asks_more or bool(rest & set(stems(chosen["text"]))))
        # the pick shares more of the question's other words than the list: it asks what the question asks ("How do people
        # feel about Target?" is the feelings question, not the purchases list that has Target among its answers, 13 Nov)
        asks_else = longest is not None and len(rest & set(stems(chosen["text"]))) > len(rest & set(stems(longest["text"])))
        if longest and not own_name and not asks_else and not EVENT.search(question.lower()) and (   # "Amazon Prime" questions keep their own
                not focus(question, chosen.get("labels", []), full_names) or chosen["waves"] * 3 < longest["waves"]):   # q5 (195 waves) over EC2 (22)
            chosen = longest
        # an unsure reader's pick asked only years ago, with no period named: the nearest question still asked, with
        # history, among the three nearest by meaning ("Personal finances outlook" took a 2022 one-off over CS1, 71 waves;
        # applied to sure picks too it broke three right answers, 21 Nov 2026)
        current = str(date.fromisoformat(index.newest) - timedelta(days=CURRENT_DAYS))
        if by_reader and not reader_sure and not plan["when"] and chosen["last"] < current:
            chosen = next((c for c in by_meaning[:3] if c["waves"] >= TREND_FROM and c["last"] >= current), chosen)
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
        if by_reader and not reader_sure and any(index.idf.get(index.known(w) or "", 99) >= RARE_WORD for w in lacking(plan, chosen["key"], index)[0]):
            # an unsure reader's pick missing a specific word of the subject: the first candidate that uses every one
            # ("Holiday progress" took the recent purchases question over the shopping status one). Sure picks keep
            # theirs: for them it broke 14 right answers that miss only a common word ("plans", "bought", 21 Nov 2026)
            chosen = next((c for c in candidates if not lacking(plan, c["key"], index)[0]), chosen)
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
        if missing := unasked(plan, chosen["key"], index):   # the nearest question, but about something else
            rare = sorted(missing, key=lambda w: -index.idf.get(index.known(w) or "", 99))[:3]   # unknown, then rarest
            return {**no_figure(f"None of the surveys asks this: no survey question covers {' and '.join(f'“{w}”' for w in rare)}. "
                                "The closest questions are below.", plan,
                                [{"qcode": c["qcode"], "text": c["text"][:200], "family": c["family"], "key": c["key"]} for c in candidates[:4]]),
                    "understood": understood}
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
    fallbacks = [] if selected is not None else [
        h for h in hits[1:] if focus(question, h.get("labels", []), full_names) or index.alike(hits[0]["key"], h["key"])]
    # then the next closest matches, for a question naming its periods: "online in October 2026 than September 2026"
    # read the quarterly EC1 (September only); the weekly q3, second closest, holds both months (fresh set, 20 Nov 2026)
    # Only a near-equal match: "ways to save money in October" must never borrow the retailer question (test_assistant)
    top = by_words.get(hits[0]["key"], 0)
    # A group asked about counts as a period does: "Gen Z buying clothing online" read the Amazon apparel study's one wave,
    # which has no Gen Z figures; the weekly q3 has them (20 Nov 2026)
    fallbacks += [h for h in hits[1:3] if h not in fallbacks and top and by_words.get(h["key"], 0) >= NEAR_EQUAL * top] \
        if selected is None and (asked_plan["when"] or asked_plan["cuts"]) else []
    for hit in hits[:1] + fallbacks[:5]:
        doc = index.docs[hit["key"]]
        plan = asked_plan
        if not plan["when"] and not plan["cuts"] and (plan["kind"] in ("share", "count", "change") or plan["grain"]) and doc["waves"] >= TREND_FROM:
            plan = {**plan, "kind": "trend", "when": [{"all": True}]}   # no time named: every wave, the latest figure first
        counts = index.counts(doc["key"])
        fig = ask_figures.compute(counts, plan, visible)
        if hit is hits[0]:
            first = (doc, plan, counts, fig)
        if fig["periods"] and not (len(plan["when"]) > 1 and fig["missing"]) and not lacks_group(fig, plan):
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
        or focus(question, ["" if np.all(np.isnan(fig["pct"][:, :, a])) else name for a, name in enumerate(fig["answers"])], full_names)
    # an answer these waves never offered is not shown, nor named: "Walmart+" (no figures) hid "Walmart" (21 Nov 2026)
    named = [a for a in named if not np.all(np.isnan(fig["pct"][:, :, a]))]
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
    nets = index.nets.get(doc["qcode"].upper(), []) if doc["family"] == "CSI-US" else []
    if (net := add_net(question, fig, counts, nets)) is not None:
        named = [net]
    if len(plan["when"]) > 1 and fig["missing"]:
        return no_figure("At least one requested period has no comparable survey data. Try a single period or choose two available periods in Trends.", plan, suggestions)
    if plan["cuts"]:
        dimension, groups = next(iter(plan["cuts"].items()))
        if lacks_group(fig, plan):
            return no_figure("At least one requested demographic group is unavailable for this survey question. Try a different group or ask for all respondents.", plan, suggestions)
        if len(plan["when"]) > 1 and not fig["grain"] and groups != "all":
            columns = [col for col, (cut, value) in enumerate(fig["columns"]) if cut == dimension and value in groups]
            present = ~np.isnan(fig["pct"][:, columns])
            if not (present[:, :, named].all() if named else present.any(axis=2).all()):
                return no_figure("A requested group or answer has no reportable figures in one of the periods. Try a single period or ask for all respondents.", plan, suggestions)
    if np.isnan(fig["pct"]).all():
        return no_figure("The survey question matches, but there are no reportable figures for the requested period. Try another period.", plan, suggestions)
    weighting = "unweighted"
    shares = weigh(fig, counts, index) if weighted else None
    kept = [p for p in range(len(fig["periods"])) if shares is not None and not np.isnan(shares[p]).all()]
    if kept:   # the periods with weighted figures; the people said are the weighted share of each base, and
        # significance stays on the unweighted figures (etl/weighting.py)
        fig = {**fig, "periods": [fig["periods"][p] for p in kept], "tested": fig["pct"][kept], "pct": shares[kept],
               "bases": fig["bases"][kept], "people": np.round(shares[kept] * fig["bases"][kept] / 100)}
        weighting = "weighted"
    periods = [p for p in fig["periods"] if p["waves"]]
    first, last = periods[0], periods[-1]
    source_wave = last["waves"][-1]
    source_code, source_text = counts["sources"][source_wave]
    source_doc = {**doc, "qcode": source_code, "text": source_text}
    sentences, shown = write(plan, fig, source_doc, named)
    glance = {**brief(plan, fig, source_doc, shown, len(named) >= 2), "next": follow_ups(plan, fig, doc, named)}
    # one wave alone says nothing of direction: the change since the wave before, tested, as a chat would add (21 Nov 2026)
    if len(fig["periods"]) == 1 and len(fig["periods"][0]["waves"]) == 1 and len(fig["columns"]) == 1 and shown and glance["takeaway"] \
            and (before := [d for d in fig["asked"] if d < fig["periods"][0]["from"]]):
        pair = ask_figures.compute(counts, {**plan, "kind": "share", "grain": None, "when": [
            {"from": before[-1], "to": before[-1]}, {"from": fig["periods"][0]["from"], "to": fig["periods"][0]["to"]}]}, visible)
        if weighting == "weighted":
            shares = weigh(pair, counts, index)
            pair = {**pair, "tested": pair["pct"], "pct": shares} if shares is not None else {**pair, "periods": []}
        change = ask_figures.moved(pair, shown[0]) if len(pair["periods"]) == 2 and shown[0] < pair["pct"].shape[2] else None
        if change:
            since = ask_figures.label_date(before[-1])
            said = f"“{fig['answers'][shown[0]]}”"
            glance["takeaway"] += (f" {said} is unchanged from {since}." if not change[0] else
                                   f" {said} is {'up' if change[0] > 0 else 'down'} {abs(change[0]):.1f} points from {since}"
                                   f" ({'a significant change' if change[1] else 'not a significant change'}).")
            if len(glance["tiles"]) < 3:
                glance["tiles"].append({"label": f"Change since {since}", "value": f"{change[0]:+.1f} pts",
                                        "note": "significant" if change[1] else "not significant"})
    waves_used = len({wave for period in periods for wave in period["waves"]})
    period = first["label"] if len(periods) == 1 else f"{first['label']} vs {last['label']}" if plan["compare"] and len(periods) == 2 \
        else f"{ask_figures.label_date(first['from'])} – {ask_figures.label_date(last['to'])}"
    drawn = chart(fig, shown, len(named) >= 2)
    listed = list(dict.fromkeys(shown + [fig["answers"].index(c) for c in (drawn or {}).get("categories", [])
                                       if c in fig["answers"]]))
    if listed != shown:
        drawn = chart(fig, listed, len(named) >= 2)
    table = figure_table(fig, listed)
    notes = [x for x in sentences[1:] if x.startswith(NOTE_STARTS)]
    if weighted:
        notes.append("Census-weighted figures (gender, age, region): counts of people are weighted estimates, and changes are tested on the unweighted figures." if weighting == "weighted" else
                     "Unweighted figures: these waves have no respondent file to weight.")
        if weighting == "weighted" and (dropped := len(ask_figures.compute(counts, plan, visible)["periods"]) - len(fig["periods"])):
            notes.append(f"{dropped} {'period' if dropped == 1 else 'periods'} left out: their waves have no weighted figures.")
    points = [x for x in sentences[1:] if not x.startswith(NOTE_STARTS)]
    # the answer first, in one sentence (ChatGPT's and Tableau Agent's order, 21 Nov 2026): the finding when there is one,
    # else the first sentence with a figure; the figure sentences follow as points ("Top 5: 1. … 2. …" read as a list)
    # not for a count (it leads with people) or one named group (the takeaway does not say "among Gen Z": 13 Nov 2026)
    everyone = len(fig["columns"]) > 1 or fig["columns"][0][0] == "total"
    lead = glance["takeaway"] if plan["kind"] != "count" and everyone else ""
    headline = lead or next((x for x in points if "%" in x), points[0] if points else "")
    if last["to"] < str(date.fromisoformat(index.newest) - timedelta(days=CURRENT_DAYS)):   # an old question: said up front
        headline += f" Last asked {ask_figures.label_date(last['to'])}."   # ("worried about losing their job": 2020)
    main_base = int(fig["bases"][0, 0, shown[0]]) if shown and len(fig["periods"]) == 1 and len(fig["columns"]) == 1 else 0
    return {"answer": "\n".join(sentences), "headline": headline, "points": [x for x in points if x != headline], "notes": notes,
            "scope": {"country": plan["country"], "period": period, "waves": waves_used, "base": main_base},
            "source_line": sentences[0], "weighting": weighting, "understood": understood,
            "check": quick and understood in ("meaning", "reader") and not reader_sure and ask_model.ready(), "margin": margin,
            "verify": {"question": question, "key": doc["key"], "code": doc["qcode"], "family": doc["family"], "focus": [fig["answers"][a] for a in named],
                       "kind": plan["kind"], "cut": next(iter(plan["cuts"]), "none"), "period": period_of(plan["when"])}, "codes": doc.get("codes", [doc["qcode"]]),
            "chart": drawn, "table": table, "plan": plan, "mode": "figures", "no_source": False,
            "suggestions": suggestions, **glance,
            "sources": [{"id": "S1", "key": doc["key"], "qcode": source_code, "question": source_text, "name": doc.get("name", ""), "family": doc["family"],
                         "survey_id": source_wave, "wave_date": last["to"], "waves": waves_used,
                         "link": f"/w/{source_wave}/{'trends' if len(fig['periods']) > 1 else 'questions'}/{source_code}"}]}


def figure_table(fig: dict, shown: list[int]) -> dict:
    """Serialize the displayed shares and their own bases. Suppressed cells carry neither."""
    columns = fig["columns"]
    head = ["Answer"] + [p["label"] + (f" · {v}" if len(columns) > 1 else "")
                         for p in fig["periods"] for _, v in columns]
    rows, cell_bases = [], []
    for answer in shown if len(fig["answers"]) > 15 else range(len(fig["answers"])):
        values = fig["pct"][:, :, answer].ravel()
        if np.isnan(values).all():
            continue
        shares = [None if math.isnan(value) else float(value) for value in values]
        rows.append([fig["answers"][answer], *shares])
        cell_bases.append([None if share is None else int(base)
                           for share, base in zip(shares, fig["bases"][:, :, answer].ravel())])
    bases = [common_base(column) for column in zip(*cell_bases)] if cell_bases else [0] * (len(head) - 1)
    return {"head": head, "rows": rows, "bases": bases, "cell_bases": cell_bases}


def ask(question: str, index: Index, visible: set[int], scope: str, quick: bool = False, key: str | None = None,
        previous: str | None = None, previous_key: str | None = None, weighted: bool = False) -> dict:
    """answer(), kept per published version (the index), access scope, quick or not, follow-up key and question wording; a question
    the AI check settled is learned, so the same or a close question is answered at once next time, with no AI. An answer from
    keywords alone, before the search vectors are ready (the minutes after a deploy), is not kept: it stayed until the next
    publish (15 Nov 2026). previous, previous_key: the question the page's latest answer was for and its survey question,
    so a typed follow-up ("What about Gen Z?") is read with it (follow_on); the answer then says how it was read (asked_as)."""
    question = " ".join(question.split())[:500]
    asked_as = None
    if previous and key is None:
        merged, follow_key = follow_on(question, " ".join(previous.split())[:500], previous_key, index)
        if follow_key:
            question, key, asked_as = merged, follow_key, merged
    kept = (id(index), scope, quick, key, weighted, question.lower())
    with ANSWERS_LOCK:
        cache = ANSWERS
        if kept in ANSWERS:
            ANSWERS.move_to_end(kept)
            return ANSWERS[kept]
    # read before answering, as they can arrive while it runs; an index whose build ended with no vectors (no search model)
    # keeps its answers too, or every repeat was worked out again (second review, 15 Nov 2026)
    vectors_ready = index.vectors is not None or getattr(index, "settled", True)
    found = answer(question, index, visible, quick, key, weighted)
    if (fixed := index.correct_spelling(question)) != question:   # the page says so: "answered as …, the spelling put right"
        found = {**found, "corrected": fixed}
    if asked_as:
        found = {**found, "asked_as": asked_as}
    if found.get("understood") == "model" and found.get("mode") == "figures":
        learn(found["verify"], index)
    if vectors_ready:
        with ANSWERS_LOCK:
            if cache is ANSWERS:
                ANSWERS[kept] = found
                while len(ANSWERS) > KEEP_ANSWERS:
                    ANSWERS.popitem(last=False)
    return found
