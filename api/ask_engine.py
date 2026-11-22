"""Ask CIP's plan engine: runs a plan (what is counted, among whom, split by what, which weeks, which operation) over each
wave's respondents and returns exact figures, so a question that joins several survey questions for the same people
("among recent AI users, what share used GenAI to shop", "bought from both", a funnel) can be answered at all.

Who calls it: scripts/ask_hard.py --engine (checks every plan of the hard test set against figures worked out from the
raw files); next, Ask's plan reader (step 3-4 of the Ask rebuild). It reads only published files: each wave's
people.json.gz (for every answer, one bit per respondent who gave it; "0,0" is everyone asked) and waves.json.gz.
Numpy bit operations on ~400 respondents a wave: well under a millisecond a wave, no database. 22 Nov 2026.

A plan (the format of scripts/ask_hard.yml):
    waves: [2026-11-16, ...]        weeks by fielded date; per: wave (default) or pooled
    ask: <condition>                what is counted (op share), or {q: CODE} for op top / counts
    among: <condition>              optional: only these people
    by: {q: CODE} | {groups: {name: <condition>}}     optional: one figure per group
    op: share | top | counts | chain    top: N; chain: steps: [<condition>, ...], each a share of the step before
    base: all                       a share of everyone, not of those asked the question
    test: true                      two figures: the change in points and its two-sided z-test
    weighted: true                  Census-weighted counts (each wave's people.json weights)
A condition: {q: CODE, is: [answer starts]}, {q: CODE, any: true} (any but "none of these"), {q: CODE, item: ROW,
is: [...]} (a grid row), {q: D2, between: [18, 34]} (a number), {either: [...]}, {both: [...]}, {not: {...}}.
"""
from __future__ import annotations

import functools
import gzip
import html
import json
import math
import re
from pathlib import Path

import numpy as np

NONE_LIKE = re.compile(r"^(none of|have not|i have not|haven't|did not|do not|i do not|not used)", re.I)


def bit_mask(hexed: str | None, size: int) -> np.ndarray:
    """A people.json bitset (hex, respondent i = bit i) as booleans in seat order."""
    value = int(hexed or "0", 16)
    return np.unpackbits(np.frombuffer(value.to_bytes((size + 7) // 8, "little"), np.uint8), bitorder="little")[:size].astype(bool)


def question_in(people: dict, qcode: str) -> dict | None:
    """A question in one wave's people.json by its code in any case: the wave spells the weekly core q5, the joined question
    file Q5, and on staging's case-sensitive files the weighted answer quietly fell back to unweighted (22 Nov 2026)."""
    return people["questions"].get(qcode) or next((q for code, q in people["questions"].items() if code.lower() == qcode.lower()), None)


def clean(text) -> str:
    return " ".join(html.unescape(str(text or "")).replace("\xa0", " ").split())


@functools.lru_cache(maxsize=64)
def people_of(path: Path) -> dict:
    return json.loads(gzip.decompress(path.read_bytes()))


def starts(label: str, wanted: list[str]) -> bool:
    return any(clean(label).lower().startswith(clean(w).lower()) for w in wanted)


def age_of(label: str) -> float:
    """A number answer as a number: "70 or more" is 70, "Under 18" none (never an adult age band)."""
    found = re.search(r"\d+", "" if re.match(r"\s*under", label, re.I) else label)
    return float(found[0]) if found else math.nan


def code_in(q, sid: int | None) -> list[str]:
    """The codes to try in one wave: a code, a list, or {survey id: code} (the exact code each week asked it under:
    a question's older codes can name another question today, "Q6" before footwear's FW1 is the weekly q6)."""
    if isinstance(q, dict):
        return [q[sid]] if sid in q else [q[str(sid)]] if str(sid) in q else []
    return [q] if isinstance(q, str) else list(q)


def mask(people: dict, size: int, cond: dict, sid: int | None = None) -> tuple[np.ndarray, np.ndarray]:
    """(true, asked) for one condition in one wave: who meets it, and who was asked every question it reads."""
    if "either" in cond or "both" in cond:
        parts = [mask(people, size, c, sid) for c in cond.get("either") or cond["both"]]
        asked = np.logical_and.reduce([a for _, a in parts])
        true = (np.logical_or if "either" in cond else np.logical_and).reduce([t for t, _ in parts])
        return true & asked, asked
    if "not" in cond:
        true, asked = mask(people, size, cond["not"], sid)
        return ~true & asked, asked
    # a code, or the codes one question was asked under (GLP-1 use is EAT9 on 14 Sep, GP1 later): the first this wave has
    question = next((q for code in code_in(cond["q"], sid) if (q := question_in(people, code))), None)
    if question is None:   # not asked in this wave
        return np.zeros(size, bool), np.zeros(size, bool)
    rows = [r for r in question["rows"] if "item" not in cond or starts(r[2], [cond["item"]])]
    bits = lambda r: bit_mask(question["bits"].get(f"{r[0]},{r[1]}"), size)   # noqa: E731
    multi = all(r[1] == 0 for r in rows)
    if multi:   # a select-all: an item's bit is a respondent who chose it; "0,0" is everyone asked
        asked = bit_mask(question["bits"]["0,0"], size) if "0,0" in question["bits"] else np.logical_or.reduce([bits(r) for r in rows])
        chosen = [r for r in rows if (not NONE_LIKE.match(clean(r[2])) if cond.get("any") else starts(r[2], cond.get("is", [])))]
    else:
        asked = np.logical_or.reduce([bits(r) for r in rows]) if rows else np.zeros(size, bool)
        if "between" in cond:
            low, high = cond["between"]
            chosen = [r for r in rows if low <= age_of(clean(r[4])) <= high]
        else:
            chosen = rows if cond.get("any") else [r for r in rows if starts(r[4], cond.get("is", []))]
    true = np.logical_or.reduce([bits(r) for r in chosen]) if chosen else np.zeros(size, bool)
    return true & asked, asked


def answers_of(people: dict, code, sid: int | None = None) -> list[str]:
    """A question's answers in survey order: its items (select-all) or its options."""
    question = next((q for c in code_in(code, sid) if (q := question_in(people, c))), {"rows": []})
    return list(dict.fromkeys(clean(r[2] if r[1] == 0 else r[4]) for r in question["rows"] if r[0] or r[1]))


def surveys(published: Path, country: str = "US") -> dict[str, int]:
    """Fielded date → survey id, for one country's weekly tracker."""
    waves = json.loads(gzip.decompress((published / "waves.json.gz").read_bytes()))
    return {w["wave_date"]: w["survey_id"] for w in waves if w.get("country", "US") == country and w.get("study_type") == "tracker"}


def run(plan: dict, published: Path, ids: dict[str, int] | None = None) -> list[dict]:
    """The figures of one plan: rows of {when, label, pct, n, base} (and group), plus the change and its test."""
    ids = ids or surveys(published)
    dates = [str(w) for w in plan["waves"]]
    buckets = [("pooled", dates)] if plan.get("per") == "pooled" else [(d, [d]) for d in dates]
    op = plan.get("op", "share")
    out = []
    for when, group_dates in buckets:
        loaded = [(ids[d], people_of(published / "waves" / str(ids[d]) / "people.json.gz")) for d in group_dates]
        groups: list = [(None, None)]
        if "by" in plan:
            by = plan["by"]
            groups = list(by["groups"].items()) if "groups" in by else \
                [(a, {"q": by["q"], "is": [a]}) for a in answers_of(loaded[-1][1], by["q"], loaded[-1][0]) if not re.match(r"prefer not", a, re.I)]
        for name, group_cond in groups:
            totals: dict = {}
            for sid, people in loaded:
                size = len(people["weights"])
                weight = np.asarray(people["weights"], float) if plan.get("weighted") else np.ones(size)
                among = np.ones(size, bool)
                for cond in (plan.get("among"), group_cond):
                    if cond:
                        among &= mask(people, size, cond, sid)[0]

                def add(key: str, true: np.ndarray, base: np.ndarray) -> None:   # people and base, summed over pooled waves
                    n, b = totals.get(key, (0.0, 0.0))
                    totals[key] = (n + weight[true].sum(), b + weight[base].sum())
                if op == "share":
                    true, asked = mask(people, size, plan["ask"], sid)
                    add("share", true & among, among if plan.get("base") == "all" else asked & among)
                elif op in ("top", "counts"):
                    for answer in answers_of(people, plan["ask"]["q"], sid):
                        if op == "top" and NONE_LIKE.match(answer):
                            continue
                        true, asked = mask(people, size, {"q": plan["ask"]["q"], "is": [answer]}, sid)
                        add(answer, true & among, asked & among)
                elif op == "chain":
                    reached = among
                    for number, step in enumerate(plan["steps"], 1):
                        true, _ = mask(people, size, step, sid)
                        add(step.get("say", f"step {number}"), true & reached, reached)
                        reached = reached & true
            rows = [{"when": when, "label": label, "pct": round(100 * n / b, 1) if b else None, "n": round(n), "base": round(b),
                     **({"group": name} if name else {})} for label, (n, b) in totals.items()]
            out += sorted(rows, key=lambda r: -(r["pct"] or 0))[: plan.get("top", 5)] if op == "top" else rows
    if op == "share" and len(out) == 2 and plan.get("test") and all(r["base"] for r in out) and 0 < sum(r["n"] for r in out) < sum(r["base"] for r in out):
        (a, b) = out   # the change in points and its two-sided z-test (95%); never on an empty group or all one answer
        p1, p2 = a["n"] / a["base"], b["n"] / b["base"]
        pooled = (a["n"] + b["n"]) / (a["base"] + b["base"])
        z = (p2 - p1) / math.sqrt(pooled * (1 - pooled) * (1 / a["base"] + 1 / b["base"]))
        out.append({"label": "change", "points": round(100 * (p2 - p1), 1), "p": round(math.erfc(abs(z) / math.sqrt(2)), 3)})
    return out
