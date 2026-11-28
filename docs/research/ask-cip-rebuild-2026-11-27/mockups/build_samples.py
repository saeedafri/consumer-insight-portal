"""The manager's 13 sample questions for Ask CIP, with their expected answers, read from the published files.

What it is for: Phase M of the Ask CIP rebuild (../PROMPT.md, ../04-council-verdict.md). Every figure in the mock-ups
(index.html) and in the sample set for the analyst (samples.md) comes from here, read from one survey's published question
file or one wave's respondent file, never through Ask's own trend join (api/ask_index.py wording_groups, which mixes
questions). Each trend's waves were checked to share one wording (the file's `versions` and each wave's book).
Who runs it: a person, by hand, from the repo root:
    .venv/bin/python docs/research/ask-cip-rebuild-2026-11-27/mockups/build_samples.py
It writes samples.js (the data index.html draws) and samples.md next to itself. Run it again after the wording_groups fix
(Phase 1) to recompute every figure; the check at the bottom fails if a figure the manager already saw changes.
Sentences here are fixed patterns per answer type, the way Phase 2 will write them: no model writes text.
"""
from __future__ import annotations

import gzip
import json
import math
import statistics
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from api.ask_engine import mask, size_of  # noqa: E402
from api.ask_figures import middle  # noqa: E402
from api.dashboards import significant  # noqa: E402

PUBLISHED = ROOT / "data/published/preview/current/api/v1"   # the 27 Nov 2026 build: the only local copy with China
HERE = Path(__file__).resolve().parent
US, CN = "Coresight US Consumer Survey", "Coresight China Consumer Survey"
SMALL = 50            # a group under this is marked and left out of highest/lowest (01-template-spec.md 4.3)
UNUSUAL_POINTS = 10   # an unusual reading lies this far from the series median (01-template-spec.md 4.3)
GENERATIONS = {"GenZ": "Gen Z", "Millennial": "Millennials", "GenX": "Gen X", "Boomer": "Boomers"}
INCOMES = {"Under $50k": ["under $25,000", "$25,000 - $49,999"], "$50k-$99k": ["$50,000 - $99,999"],
           "$100k+": ["$100,000 - $149,999", "$150,000 - $199,999", "$200,000 or greater"]}   # api/ask_reader.py INCOME_GROUPS
CN_AGES = ["18-25", "26-41", "42-57", "57-76", "77+"]
sources: list[dict] = []   # every figure's survey, date and file, for samples.md


def load(code: str, family: str = "CSI-US/tracker") -> dict:
    path = PUBLISHED / "questions" / family / f"{code}.json.gz"
    data = json.loads(gzip.decompress(path.read_bytes()))
    data["file"] = str(path.relative_to(ROOT))
    return data


def counts(q: dict, when: str, cut: tuple[str, str] = ("total", "Total")) -> dict[str, tuple[int, int]]:
    """{answer: (people, base)} for one survey date and one cut; two surveys on one date are added together."""
    out: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for w, c, a, n, b in zip(q["w"], q["c"], q["a"], q["n"], q["b"]):
        if q["waves"][w][1] == when and tuple(q["cuts"][c]) == cut:
            out[q["answers"][a][2]][0] += n
            out[q["answers"][a][2]][1] += b
    return {k: tuple(v) for k, v in out.items()}


def dates_of(q: dict) -> list[str]:
    return sorted({w[1] for w in q["waves"]})


def share(people: int, base: int) -> float:
    return 100 * people / base


def side(cells: dict, starts: list[str]) -> tuple[int, int]:
    """People giving any answer that starts with one of `starts` (a net such as "worse"), and the base."""
    base = max(b for _, b in cells.values())
    return sum(n for k, (n, _) in cells.items() if any(k.startswith(s) for s in starts)), base


def note(q: dict, figure: str, when: str, pct: float) -> str:
    sources.append({"figure": figure, "value": f"{pct:.1f}%", "date": day(when), "file": q["file"],
                    "wording": q["versions"][-1]})
    return f"{pct:.1f}%"


def day(iso: str) -> str:
    return date.fromisoformat(iso).strftime("%-d %b %Y")


def month(iso: str) -> str:
    return date.fromisoformat(iso).strftime("%B %Y")


def mon(iso: str) -> str:
    return date.fromisoformat(iso).strftime("%b %Y")


def change_words(new: tuple[int, int], old: tuple[int, int]) -> tuple[str, str, float]:
    """("up 5.0 percentage points from", tone, points) when the 95% test says real, else ("about the same as", "same", points)."""
    p_new, p_old = share(*new), share(*old)
    points = p_new - p_old
    if not significant(p_new, new[1], p_old, old[1]):
        return "about the same as", "same", points
    return (f"up {points:.1f} percentage points from" if points > 0 else f"down {-points:.1f} percentage points from"), \
        ("up" if points > 0 else "down"), points


def change_card(label: str, new, old) -> dict:
    words, tone, points = change_words(new, old)
    value = "About the same" if tone == "same" else f"{points:+.1f} pts"
    return {"label": label, "value": value, "note": f"From {share(*old):.1f}%", "tone": tone}


def window_verdict(readings: list[tuple[str, int, int]]) -> tuple[str, float, float]:
    """Steady / Rising / Falling / Up and down for a window of readings (01-template-spec.md 4.4 T2 verdict rule)."""
    pcts = [share(n, b) for _, n, b in readings]
    real_steps = [significant(pcts[i + 1], readings[i + 1][2], pcts[i], readings[i][2]) * (1 if pcts[i + 1] > pcts[i] else -1)
                  for i in range(len(pcts) - 1)]
    overall = significant(pcts[-1], readings[-1][2], pcts[0], readings[0][2])
    if max(pcts) - min(pcts) <= 5 and not any(real_steps):
        verdict = "Steady"
    elif overall and pcts[-1] > pcts[0] and -1 not in real_steps:
        verdict = "Rising"
    elif overall and pcts[-1] < pcts[0] and 1 not in real_steps:
        verdict = "Falling"
    else:
        verdict = "Up and down"
    return verdict, min(pcts), max(pcts)


def unusual(readings: list[tuple[str, int, int]]) -> list[dict]:
    """Readings that differ by the 95% test from both neighbours in the same direction and lie UNUSUAL_POINTS from the median."""
    pcts = [share(n, b) for _, n, b in readings]
    median = statistics.median(pcts)
    found = []
    for i in range(1, len(readings) - 1):
        before, now, after = pcts[i - 1], pcts[i], pcts[i + 1]
        same_way = (now > before and now > after) or (now < before and now < after)
        if same_way and abs(now - median) >= UNUSUAL_POINTS \
                and significant(now, readings[i][2], before, readings[i - 1][2]) \
                and significant(now, readings[i][2], after, readings[i + 1][2]):
            found.append({"date": readings[i][0], "label": f"Unusual {'high' if now > median else 'low'}: {now:.1f}% ({mon(readings[i][0])})"})
    return found


def table_rows(readings, answers=("Yes", "No"), q=None) -> list[list[str]]:
    return [[day(d), *[f"{share(*counts(q, d)[a]):.1f}%" for a in answers]] for d, _, _ in reversed(readings)]


def groups_answer(q: dict, when: str, answer: str, groups: dict[str, list[tuple[str, str]]]) -> list[dict]:
    """[{group, people, base}] adding cut values together (income bands into three groups)."""
    out = []
    for name, cuts in groups.items():
        n = b = 0
        for cut in cuts:
            cell = counts(q, when, cut).get(answer)
            if cell:
                n, b = n + cell[0], b + cell[1]
        if b:   # a group nobody in this survey belongs to (China's 77+ some weeks) is left out
            out.append({"group": name, "people": n, "base": b, "pct": round(share(n, b), 1), "small": b < SMALL})
    return out


def compare_groups(rows: list[dict]) -> dict:
    """Highest (with the groups tied with it), lowest, and whether the gap is real; groups under SMALL left out."""
    big = [r for r in rows if not r["small"]]
    top = max(big, key=lambda r: r["pct"])
    low = min(big, key=lambda r: r["pct"])
    tied = [r for r in big if r is top or not significant(r["pct"], r["base"], top["pct"], top["base"])]
    return {"big": big, "top": top, "tied": tied, "low": low, "real": significant(top["pct"], top["base"], low["pct"], low["base"])}


def group_headline(cmp: dict, who, phrase: str) -> str:
    """The T3 sentence: groups tied with the highest named together (01-template-spec.md 4.2 ties); `who(rows)` names groups."""
    span = lambda rows: f"{min(r['pct'] for r in rows):.1f}% to {max(r['pct'] for r in rows):.1f}%"   # noqa: E731
    if not cmp["real"]:
        return f"{who(cmp['big'])} were about equally likely to {phrase} (<em>{span(cmp['big'])}</em>); the differences could be chance"
    if len(cmp["tied"]) > 1:
        return (f"{who(cmp['tied'])} were about equally likely to {phrase} (<em>{span(cmp['tied'])}</em>); "
                f"{who([cmp['low']])} were the least likely ({cmp['low']['pct']:.1f}%)")
    return (f"{who([cmp['top']])} were the most likely to {phrase} (<em>{cmp['top']['pct']:.1f}%</em>), "
            f"and {who([cmp['low']])} the least likely ({cmp['low']['pct']:.1f}%)")


def names(rows: list[dict]) -> str:
    labels = [r["group"] for r in rows]
    return labels[0] if len(labels) == 1 else ", ".join(labels[:-1]) + " and " + labels[-1]


def line_series(q: dict, starts: list[str] | None = None, answer: str = "Yes") -> list[tuple[str, int, int]]:
    """(date, people, base) for every survey of one question, total; `starts` adds the answers of one side."""
    out = []
    for d in dates_of(q):
        cells = counts(q, d)
        n, b = side(cells, starts) if starts else cells[answer]
        out.append((d, n, b))
    return out


def as_points(readings) -> list[dict]:
    return [{"date": d, "n": n, "b": b} for d, n, b in readings]


# ---------------------------------------------------------------------------------------------------------------------
beauty = load("BT1")
latest, previous = "2026-09-28", "2026-07-06"
beauty_series = line_series(beauty)
yes_latest, yes_prev = counts(beauty, latest)["Yes"], counts(beauty, previous)["Yes"]
assert len(beauty["versions"]) == 1, "the beauty file joins one wording only"
BEAUTY_WORDING = beauty["versions"][0]
samples = []

# S1 easy, T1 single latest value ------------------------------------------------------------------------------------
words, tone, _ = change_words(yes_latest, yes_prev)
samples.append({
    "id": "s1", "level": "Easy", "type": "T1 Latest value", "market": "US", "survey": US,
    "question": "Did people buy beauty products recently?",
    "headline": f"In the latest survey ({day(latest)}), <em>{note(beauty, 'Bought beauty products, latest', latest, share(*yes_latest))}</em> "
                f"of US adults said they bought beauty products in the past three months, {words} on {day(previous)} "
                f"({note(beauty, 'Bought beauty products, survey before', previous, share(*yes_prev))}).",
    "cards": [{"label": "Latest survey", "value": f"{share(*yes_latest):.1f}%", "note": day(latest), "tone": "main"},
              change_card(f"Since {day(previous)}", yes_latest, yes_prev),
              {"label": "Said no", "value": f"{share(*counts(beauty, latest)['No']):.1f}%", "note": day(latest), "tone": ""}],
    "chart": {"kind": "columns", "title": "Bought beauty products in the past three months", "unit": f"% of US adults, {day(latest)}",
              "bars": [{"label": a, "pct": round(share(*counts(beauty, latest)[a]), 1)} for a in ("Yes", "No")],
              "foot": ["Shares of everyone asked add up to 100%."]},
    "evidence": {"wording": [BEAUTY_WORDING], "source": f"{US}, {day(latest)}",
                 "table": {"head": ["Survey date", "Yes", "No"], "rows": table_rows(beauty_series[-2:], q=beauty)}},
    "alternatives": ["Which beauty products people bought (Coresight US Consumer Survey, last asked 28 Sep 2026)",
                     "Types of beauty products bought (Coresight US Consumer Survey, last asked 28 Sep 2026)"],
    "chips": [{"label": "Over time", "goto": "s2"}, {"label": "By generation", "goto": "s3"},
              {"label": "By household income", "goto": "s4"}, {"label": "Where people buy them", "goto": "s5"}],
})

# S2 easy, T2 trend (quarterly module, one wording since 5 Sep 2022) ------------------------------------------------
first = beauty_series[0]
year_readings = [r for r in beauty_series if r[0].startswith("2026")]
verdict, low, high = window_verdict(year_readings)
words, tone, _ = change_words(yes_latest, first[1:])
flags = unusual(beauty_series)
samples.append({
    "id": "s2", "level": "Easy", "type": "T2 Trend over time", "market": "US", "survey": US,
    "question": "How have beauty purchases changed over time?",
    "headline": f"In the latest survey ({day(latest)}), <em>{share(*yes_latest):.1f}%</em> of US adults said they bought beauty products "
                f"in the past three months, {words} in {month(first[0])} "
                f"({note(beauty, 'Bought beauty products, first survey with this wording', first[0], share(*first[1:]))}). "
                f"The share has {'stayed' if verdict == 'Steady' else 'moved'} between {low:.1f}% and {high:.1f}% during 2026.",
    "cards": [{"label": "Latest survey", "value": f"{share(*yes_latest):.1f}%", "note": day(latest), "tone": "main"},
              change_card(f"Since {mon(first[0])}", yes_latest, first[1:]),
              {"label": "During 2026", "value": verdict, "note": f"Between {low:.1f}% and {high:.1f}%", "tone": ""}],
    "chart": {"kind": "line", "title": "Bought beauty products in the past three months", "unit": "% of US adults in each survey",
              "cadence": "quarterly", "grains": ["Quarterly", "Yearly"], "ranges": ["Last 12 months", f"Since {first[0][:4]}"],
              "default_range": 1, "series": [{"name": "Bought beauty products", "points": as_points(beauty_series)}],
              "unusual": flags,
              "foot": ["Each dot is one survey.", "Dashed lines join surveys more than four months apart."]
              + (["One reading is far from the others, so treat it with care."] if flags else [])},
    "evidence": {"wording": [BEAUTY_WORDING], "source": f"{US}, {day(first[0])} to {day(latest)}",
                 "table": {"head": ["Survey date", "Yes", "No"], "rows": table_rows(beauty_series, q=beauty)}},
    "alternatives": [],
    "chips": [{"label": "By generation", "goto": "s3"}, {"label": "By household income", "goto": "s4"},
              {"label": "Where people buy them", "goto": "s5"}, {"label": "How much people spend", "goto": "s6"},
              {"label": f"{mon(first[0])} vs latest"}],
})
for d, n, b in beauty_series[1:-1]:
    note(beauty, "Bought beauty products (trend reading)", d, share(n, b))

# S3 easy, T3 compare generations (the tie) --------------------------------------------------------------------------
gens = groups_answer(beauty, latest, "Yes", {label: [("generation", key)] for key, label in GENERATIONS.items()})
cmp = compare_groups(gens)
for r in gens:
    note(beauty, f"Bought beauty products, {r['group']}", latest, r["pct"])
gap = cmp["top"]["pct"] - cmp["low"]["pct"]
samples.append({
    "id": "s3", "level": "Easy", "type": "T3 Compare groups", "market": "US", "survey": US,
    "question": "Which generation buys the most beauty products?",
    "headline": f"In the latest survey ({day(latest)}), "
                + group_headline(cmp, names, "have bought beauty products in the past three months") + ".",
    "cards": [{"label": "Highest", "value": f"{cmp['top']['pct']:.1f}%", "tone": "main",
               "note": cmp["top"]["group"] + (f"; about the same as {names([r for r in cmp['tied'] if r is not cmp['top']])}" if len(cmp["tied"]) > 1 else "")},
              {"label": "Lowest", "value": f"{cmp['low']['pct']:.1f}%", "note": cmp["low"]["group"], "tone": ""},
              {"label": "Difference", "value": f"{gap:.1f} pts", "note": "A real gap" if cmp["real"] else "Could be chance", "tone": ""}],
    "chart": {"kind": "columns", "title": "Bought beauty products in the past three months, by generation",
              "unit": f"% of each generation, US, {day(latest)}", "ranges": ["Latest survey"],
              "bars": [{"label": r["group"], "pct": r["pct"], "small": r["small"]} for r in gens],
              "foot": ["Generations whose gap to the highest could be chance are named together."]},
    "evidence": {"wording": [BEAUTY_WORDING], "source": f"{US}, {day(latest)}",
                 "table": {"head": ["Generation", "Yes"], "rows": [[r["group"], f"{r['pct']:.1f}%"] for r in gens]}},
    "alternatives": [],
    "chips": [{"label": "By household income", "goto": "s4"}, {"label": "By gender"}, {"label": "By age group"},
              {"label": "Over time by generation"}],
})

# S4 hard, T14 typed follow-up of S3 ----------------------------------------------------------------------------------
incomes = groups_answer(beauty, latest, "Yes", {label: [("income_band", v) for v in values] for label, values in INCOMES.items()})
cmp_i = compare_groups(incomes)
for r in incomes:
    note(beauty, f"Bought beauty products, income {r['group']}", latest, r["pct"])
inc_gap = cmp_i["top"]["pct"] - cmp_i["low"]["pct"]
samples.append({
    "id": "s4", "level": "Hard", "type": "T14 Follow-up (by income)", "market": "US", "survey": US, "previous": "s3",
    "question": "And by household income?",
    "read_as": f"Beauty purchases by household income, latest survey ({day(latest)})",
    "headline": f"In the latest survey ({day(latest)}), " + group_headline(
        cmp_i, lambda rows: "US adults in households earning " + names(rows).replace("Under", "under"),
        "have bought beauty products in the past three months") + ".",
    "cards": [{"label": "Highest", "value": f"{cmp_i['top']['pct']:.1f}%", "tone": "main",
               "note": f"Household income {cmp_i['top']['group']}" + (f"; about the same as {names([r for r in cmp_i['tied'] if r is not cmp_i['top']])}" if len(cmp_i["tied"]) > 1 else "")},
              {"label": "Lowest", "value": f"{cmp_i['low']['pct']:.1f}%", "note": f"Household income {cmp_i['low']['group']}", "tone": ""},
              {"label": "Difference", "value": f"{inc_gap:.1f} pts", "note": "A real gap" if cmp_i["real"] else "Could be chance", "tone": ""}],
    "chart": {"kind": "columns", "title": "Bought beauty products in the past three months, by household income",
              "unit": f"% of each income group, US, {day(latest)}", "ranges": ["Latest survey"],
              "bars": [{"label": r["group"], "pct": r["pct"], "small": r["small"]} for r in incomes],
              "foot": ["People who preferred not to give their income are left out."]},
    "evidence": {"wording": [BEAUTY_WORDING], "source": f"{US}, {day(latest)}",
                 "table": {"head": ["Household income", "Yes"], "rows": [[r["group"], f"{r['pct']:.1f}%"] for r in incomes]}},
    "alternatives": [],
    "chips": [{"label": "By generation", "goto": "s3"}, {"label": "By gender"}, {"label": "How much people spend", "goto": "s6"}],
})

# S5 hard, T4 long ranked list (retailers): vertical and horizontal side by side ------------------------------------
shops = load("BT13")
cells = counts(shops, latest)
ranked = sorted(((k, v) for k, v in cells.items() if not k.lower().startswith(("none", "other"))), key=lambda kv: -kv[1][0])
top10 = [{"label": k, "pct": round(share(*v), 1)} for k, v in ranked[:10]]
(a_name, a), (b_name, b), (c_name, c) = ranked[:3]
level = not significant(share(*a), a[1], share(*b), b[1])
for k, v in ranked[:10]:
    note(shops, f"Bought beauty products from {k}", latest, share(*v))
samples.append({
    "id": "s5", "level": "Hard", "type": "T4 Ranked answers (long list)", "market": "US", "survey": US,
    "question": "Where do people buy beauty products?",
    "headline": (f"{a_name} and {b_name} were about level as the places US adults bought beauty products in the past three months "
                 f"(<em>{share(*a):.1f}%</em> and {share(*b):.1f}%) in the latest survey ({day(latest)}), ahead of {c_name} ({share(*c):.1f}%)."
                 if level else
                 f"{a_name} was the most common place: <em>{share(*a):.1f}%</em> of US adults bought beauty products there in the past "
                 f"three months, in the latest survey ({day(latest)}), ahead of {b_name} ({share(*b):.1f}%) and {c_name} ({share(*c):.1f}%)."),
    "cards": [{"label": "Top answer", "value": f"{share(*a):.1f}%", "note": a_name, "tone": "main"},
              {"label": "Second", "value": f"{share(*b):.1f}%", "note": b_name, "tone": ""},
              {"label": "Gap between them", "value": f"{share(*a) - share(*b):.1f} pts", "note": "Could be chance" if level else "A real gap", "tone": ""}],
    "chart": {"kind": "both-bars", "title": "Where people bought beauty products in the past three months (top 10)",
              "unit": f"% of US adults, {day(latest)}", "bars": top10,
              "foot": ["People could choose more than one, so shares add up to more than 100%.",
                       "Mock-up only: the same list drawn as vertical bars (the meeting's choice) and horizontal bars (easier "
                       "to read for long names). The manager picks one."]},
    "evidence": {"wording": [shops["versions"][-1]], "source": f"{US}, {day(latest)}",
                 "table": {"head": ["Retailer or platform", "Share"], "rows": [[k, f"{share(*v):.1f}%"] for k, v in ranked]}},
    "alternatives": ["How people feel about each place they bought beauty products (Coresight US Consumer Survey, last asked 28 Sep 2026)"],
    "chips": [{"label": f"{a_name} over time"}, {"label": "By generation"}, {"label": "How much people spend", "goto": "s6"}],
})

# S6 hard, T8 amounts asked in bands -----------------------------------------------------------------------------------
spend = load("BT15")
cells = counts(spend, latest)
labels = [a[2] for a in spend["answers"]]
people = np.array([[[cells.get(lab, (0, 0))[0] for lab in labels]]], dtype=float)
(_, median_band, average), = middle({"answers": labels, "periods": [latest], "columns": ["Total"], "people": people})
banded = [lab for lab in labels if not lab.lower().startswith(("don", "prefer", "not sure"))]
most = max(banded, key=lambda lab: cells[lab][0])
spend_base = max(b for _, b in cells.values())
for lab in banded:
    note(spend, f"Spent {lab} on beauty products", latest, share(*cells[lab]))
samples.append({
    "id": "s6", "level": "Hard", "type": "T8 Amounts in ranges", "market": "US", "survey": US,
    "question": "How much do people spend on beauty products?",
    "headline": f"In the latest survey ({day(latest)}), the middle answer among US adults was <em>{median_band}</em> spent on beauty "
                f"products in the past three months; the average was about ${average} (worked out from the ranges people chose).",
    "cards": [{"label": "Middle answer", "value": median_band, "note": "Half spent less, half more", "tone": "main"},
              {"label": "Average (estimate)", "value": f"${average}", "note": "From the ranges people chose", "tone": ""},
              {"label": "Most chosen range", "value": f"{share(*cells[most]):.1f}%", "note": most, "tone": ""}],
    "chart": {"kind": "columns", "title": "Spent on beauty products in the past three months", "unit": f"% of US adults, {day(latest)}",
              "bars": [{"label": lab, "pct": round(share(*cells[lab]), 1)} for lab in banded],
              "foot": ["Spending was asked in ranges, so the average is an estimate; the top range counts at its lower end.",
                       "Ranges are shown in their own order, never ranked."]},
    "evidence": {"wording": [spend["versions"][-1]], "source": f"{US}, {day(latest)}",
                 "table": {"head": ["Amount", "Share"], "rows": [[lab, f"{share(*cells[lab]):.1f}%"] for lab in labels if lab in cells]}},
    "alternatives": [],
    "chips": [{"label": "By household income"}, {"label": "Over time"}, {"label": "By generation"}],
})

# S7 hard, T2 + T11 monthly trend of a scale (tariffs), with monthly / quarterly / yearly views ----------------------
tariffs = load("TF1")
assert len(tariffs["versions"]) == 1
NEG, POS = ["Tariffs have a very negative", "Tariffs have a somewhat negative"], ["Tariffs have a very positive", "Tariffs have a somewhat positive"]
neg, pos = line_series(tariffs, NEG), line_series(tariffs, POS)
t_last, t_first = neg[-1], neg[0]
words, tone, _ = change_words(t_last[1:], t_first[1:])
verdict, low, high = window_verdict([r for r in neg if r[0].startswith("2026")])
for d, n, b in neg:
    note(tariffs, "Say tariffs hurt them personally (very or somewhat negative)", d, share(n, b))
for d, n, b in pos[-1:]:
    note(tariffs, "Say tariffs help them personally (very or somewhat positive)", d, share(n, b))
samples.append({
    "id": "s7", "level": "Hard", "type": "T2 + T11 Monthly trend of a scale", "market": "US", "survey": US,
    "question": "Do people think tariffs are hurting them?",
    "headline": f"In the latest survey ({day(t_last[0])}), <em>{share(*t_last[1:]):.1f}%</em> of US adults said tariffs have a negative "
                f"impact on them personally, {words} in {month(t_first[0])} ({share(*t_first[1:]):.1f}%). "
                f"During 2026 the share has gone up and down between {low:.1f}% and {high:.1f}%; "
                f"{share(*pos[-1][1:]):.1f}% now say tariffs help them.",
    "cards": [{"label": "Latest survey", "value": f"{share(*t_last[1:]):.1f}%", "note": f"Negative impact, {day(t_last[0])}", "tone": "main"},
              change_card(f"Since {mon(t_first[0])}", t_last[1:], t_first[1:]),
              {"label": "During 2026", "value": verdict, "note": f"Between {low:.1f}% and {high:.1f}%", "tone": ""}],
    "chart": {"kind": "line", "title": "Say tariffs have a negative or positive impact on them personally",
              "unit": "% of US adults in each survey", "cadence": "monthly", "grains": ["Monthly", "Quarterly", "Yearly"],
              "ranges": ["Last 12 months", f"Since {t_first[0][:4]}"], "default_range": 0,
              "series": [{"name": "Negative impact", "points": as_points(neg)}, {"name": "Positive impact", "points": as_points(pos)}],
              "unusual": unusual(neg),
              "foot": ["Negative: very or somewhat negative. Positive: very or somewhat positive.",
                       "Quarterly and yearly views add up everyone asked in that period's surveys."]},
    "evidence": {"wording": [tariffs["versions"][0]], "source": f"{US}, {day(t_first[0])} to {day(t_last[0])}",
                 "table": {"head": ["Survey date", "Negative", "Positive"],
                           "rows": [[day(d), f"{share(n, b):.1f}%", f"{share(*p[1:]):.1f}%"] for (d, n, b), p in zip(reversed(neg), reversed(pos))]}},
    "alternatives": ["Impact of tariffs on the US economy (Coresight US Consumer Survey, last asked 23 Nov 2026)"],
    "chips": [{"label": "By household income"}, {"label": "By generation"},
              {"label": "Did people change how they shop?", "goto": "s13"}, {"label": "Impact on the economy"}],
})

# S8 complex, T13 both markets ask back, then T11 per market ---------------------------------------------------------
economy_us, economy_cn = load("CS2"), load("Q9", "CSI-CN/tracker")
us_day, cn_day = dates_of(economy_us)[-1], dates_of(economy_cn)[-1]
us_cells, cn_cells = counts(economy_us, us_day), counts(economy_cn, cn_day)
better, worse = side(us_cells, ["Much better", "Somewhat better"]), side(us_cells, ["Much worse", "Somewhat worse"])
p_better, p_worse = share(*better), share(*worse)
base_us = better[1]
# two answers of one survey: the variance of their difference is (p1 + p2 - (p1 - p2)^2) / n
apart = abs(p_better - p_worse) / 100 / math.sqrt(((p_better + p_worse) / 100 - ((p_better - p_worse) / 100) ** 2) / base_us) > 1.96
cn_pos, cn_neg = share(*cn_cells["Positive"]), share(*cn_cells["Negative"])
note(economy_us, "Expect the economy to get better (much or somewhat)", us_day, p_better)
note(economy_us, "Expect the economy to get worse (much or somewhat)", us_day, p_worse)
note(economy_cn, "Expect the economy to be positive (China)", cn_day, cn_pos)
note(economy_cn, "Expect the economy to be negative (China)", cn_day, cn_neg)
US_SCALE = ["Much better", "Somewhat better", "About the same", "Somewhat worse", "Much worse", "Don't know / not sure"]
CN_SCALE = ["Positive", "Same as now", "Negative", "Don't know"]
us_answer = {
    "survey": US,
    "headline": f"More US adults expect the economy to get worse over the next 12 months (<em>{p_worse:.1f}%</em>) than better "
                f"({p_better:.1f}%), in the latest survey ({day(us_day)})." if apart else
                f"US adults are split on the economy over the next 12 months: {p_worse:.1f}% expect worse, {p_better:.1f}% better ({day(us_day)}).",
    "cards": [{"label": "Expect worse", "value": f"{p_worse:.1f}%", "note": "Much or somewhat worse", "tone": "main"},
              {"label": "Expect better", "value": f"{p_better:.1f}%", "note": "Much or somewhat better", "tone": ""},
              {"label": "Net", "value": f"{p_better - p_worse:+.1f} pts", "note": "Better minus worse", "tone": ""}],
    "chart": {"kind": "columns", "title": "Expectations for the economy over the next 12 months", "unit": f"% of US adults, {day(us_day)}",
              "bars": [{"label": a, "pct": round(share(*us_cells[a]), 1), "side": ("pos" if "better" in a else "neg" if "worse" in a else "")} for a in US_SCALE],
              "foot": ["Answers in the survey's own order; the better side and the worse side are shaded."]},
    "evidence": {"wording": [economy_us["versions"][-1]], "source": f"{US}, {day(us_day)}",
                 "table": {"head": ["Answer", "Share"], "rows": [[a, f"{share(*us_cells[a]):.1f}%"] for a in US_SCALE]}},
    "chips": [{"label": "Over time"}, {"label": "By generation"}, {"label": "Same in China", "market": "CN"}],
}
cn_answer = {
    "survey": CN,
    "headline": f"In the latest China survey ({day(cn_day)}), <em>{cn_pos:.1f}%</em> of adults in China expected the economy to be "
                f"positive over the next 12 months; {cn_neg:.1f}% expected it to be negative.",
    "cards": [{"label": "Positive", "value": f"{cn_pos:.1f}%", "note": day(cn_day), "tone": "main"},
              {"label": "Negative", "value": f"{cn_neg:.1f}%", "note": day(cn_day), "tone": ""},
              {"label": "Net", "value": f"{cn_pos - cn_neg:+.1f} pts", "note": "Positive minus negative", "tone": ""}],
    "chart": {"kind": "columns", "title": "Expectations for the economy over the next 12 months", "unit": f"% of adults in China, {day(cn_day)}",
              "bars": [{"label": a, "pct": round(share(*cn_cells[a]), 1), "side": {"Positive": "pos", "Negative": "neg"}.get(a, "")} for a in CN_SCALE],
              "foot": ["Answers in the survey's own order. The two surveys word the question and its answers differently, so "
                       "their figures are never added together."]},
    "evidence": {"wording": [economy_cn["versions"][-1]], "source": f"{CN}, {day(cn_day)}",
                 "table": {"head": ["Answer", "Share"], "rows": [[a, f"{share(*cn_cells[a]):.1f}%"] for a in CN_SCALE]}},
    "chips": [{"label": "By age group", "goto": "s9"}, {"label": "By city tier"}, {"label": "Same in the US", "market": "US"}],
}
samples.append({
    "id": "s8", "level": "Complex", "type": "T13 Both markets: ask back", "market": "both",
    "question": "What do consumers expect for the economy over the next year?",
    "ask_back": {"text": "Both the US and China surveys ask this. Which results do you want?",
                 "choices": [{"label": f"US results (latest {day(us_day)})", "market": "US"},
                             {"label": f"China results (latest {day(cn_day)})", "market": "CN"}]},
    "answers": {"US": us_answer, "CN": cn_answer},
})

# S9 complex, T12 China by age group (asked "by generation") ---------------------------------------------------------
ages = groups_answer(economy_cn, cn_day, "Positive", {a: [("age_band", a)] for a in CN_AGES})
cmp_a = compare_groups(ages)
for r in ages:
    note(economy_cn, f"Expect the economy to be positive, aged {r['group']} (China)", cn_day, r["pct"])
samples.append({
    "id": "s9", "level": "Complex", "type": "T12 China, by age group", "market": "CN", "survey": CN,
    "question": "Which generation in China is most positive about the economy?",
    "headline": f"The China survey records age groups, not generations. In the latest China survey ({day(cn_day)}), "
                + group_headline(cmp_a, lambda rows: "adults in China aged " + names(rows),
                                 "expect the economy to be positive over the next 12 months") + ".",
    "cards": [{"label": "Highest", "value": f"{cmp_a['top']['pct']:.1f}%", "tone": "main",
               "note": f"Aged {cmp_a['top']['group']}" + (f"; about the same as {names([r for r in cmp_a['tied'] if r is not cmp_a['top']])}" if len(cmp_a["tied"]) > 1 else "")},
              {"label": "Lowest", "value": f"{cmp_a['low']['pct']:.1f}%", "note": f"Aged {cmp_a['low']['group']}", "tone": ""},
              {"label": "Difference", "value": f"{cmp_a['top']['pct'] - cmp_a['low']['pct']:.1f} pts",
               "note": "A real gap" if cmp_a["real"] else "Could be chance", "tone": ""}],
    "chart": {"kind": "columns", "title": "Expect the economy to be positive over the next 12 months, by age group",
              "unit": f"% of each age group, China, {day(cn_day)}", "ranges": ["Latest survey", "Last 12 months"],
              "bars": [{"label": r["group"], "pct": r["pct"], "small": r["small"]} for r in ages],
              "foot": ["The China survey records age groups, not generations."]
              + (["Fewer than 50 people answered in a hatched group: read with caution. Groups with fewer than 50 people are not compared."]
                 if any(r["small"] for r in ages) else [])},
    "evidence": {"wording": [economy_cn["versions"][-1]], "source": f"{CN}, {day(cn_day)}",
                 "table": {"head": ["Age group", "Positive"], "rows": [[r["group"], f"{r['pct']:.1f}%"] for r in ages]}},
    "alternatives": [],
    "chips": [{"label": "By city tier"}, {"label": "By monthly income"}, {"label": "Over time by age group"},
              {"label": "Same in the US", "goto": "s8"}],
})

# S10 hard, T15 a "why" question --------------------------------------------------------------------------------------
dip = "2026-01-19"
i = [r[0] for r in beauty_series].index(dip)
before, now, after = beauty_series[i - 1], beauty_series[i], beauty_series[i + 1]
fell_real = significant(share(*now[1:]), now[2], share(*before[1:]), before[2])
samples.append({
    "id": "s10", "level": "Hard", "type": "T15 Why question", "market": "US", "survey": US,
    "question": "Why did beauty purchases drop at the start of 2026?",
    "headline": f"The surveys record what people did and said, not why. On {day(now[0])}, <em>{share(*now[1:]):.1f}%</em> of US adults said "
                f"they bought beauty products in the past three months; the surveys before and after were {share(*before[1:]):.1f}% "
                f"({day(before[0])}) and {share(*after[1:]):.1f}% ({day(after[0])}). "
                + ("The fall from October was real" if fell_real else "The fall from October could be chance")
                + ", and it was the same question, asked the same way.",
    "cards": [{"label": "That reading", "value": f"{share(*now[1:]):.1f}%", "note": day(now[0]), "tone": "main"},
              {"label": "Survey before", "value": f"{share(*before[1:]):.1f}%", "note": day(before[0]), "tone": ""},
              {"label": "Survey after", "value": f"{share(*after[1:]):.1f}%", "note": day(after[0]), "tone": ""}],
    "chart": {"kind": "line", "title": "Bought beauty products in the past three months", "unit": "% of US adults in each survey",
              "cadence": "quarterly", "grains": ["Quarterly"], "ranges": ["Around the reading"], "default_range": 0,
              "focus": now[0], "series": [{"name": "Bought beauty products", "points": as_points(beauty_series[i - 2:i + 3])}],
              "foot": ["The asked reading is circled. Each dot is one survey."]},
    "evidence": {"wording": [BEAUTY_WORDING], "source": f"{US}, {day(beauty_series[i - 2][0])} to {day(beauty_series[i + 2][0])}",
                 "table": {"head": ["Survey date", "Yes", "No"], "rows": table_rows(beauty_series[i - 2:i + 3], q=beauty)}},
    "alternatives": [],
    "chips": [{"label": f"Compare {mon(now[0])} with the surveys either side"},
              {"label": "Why people buy beauty products (the reasons they gave)"}, {"label": "Over time", "goto": "s2"}],
})

# S11 hard, T17 no survey asks this ----------------------------------------------------------------------------------
# checked 27 Nov 2026: no wording or answer in the 2,720 question files names electric cars or vehicles, EVs or owning a car
samples.append({
    "id": "s11", "level": "Hard", "type": "T17 No survey asks this", "market": "US",
    "question": "How many Americans own an electric car?",
    "no_answer": {"text": "None of our surveys asks whether people own an electric car. These are the closest questions we have:",
                  "closest": ["Categories people planned to buy during the Presidents' Day weekend, which include automobiles "
                              "(Coresight US Consumer Survey, 12 Jan 2026)",
                              "Holiday purchases in the last seven days (Coresight US Consumer Survey, 23 Nov 2026)",
                              "What impact tariffs have on you personally (Coresight US Consumer Survey, 23 Nov 2026)"]},
})

# S12 hard, T5 two periods compared across a list (GenAI tools, a year apart) -----------------------------------------
genai = load("G5")
g_new, g_old = "2026-11-02", "2025-11-03"
new_cells, old_cells = counts(genai, g_new), counts(genai, g_old)
tools = [k for k, _ in sorted(new_cells.items(), key=lambda kv: -kv[1][0])
         if k in old_cells and not k.lower().startswith(("none", "other"))][:6]
moves = {t: change_words(new_cells[t], old_cells[t]) for t in tools}
rose = [t for t in tools if moves[t][1] == "up"]
same = [t for t in tools if moves[t][1] == "same"]
people_532 = json.loads(gzip.decompress((PUBLISHED / "waves/532/people.json.gz").read_bytes()))
heard, _ = mask(people_532, size_of(people_532), {"q": "G4", "any": True})   # heard of at least one tool, not "None of these"
assert int(heard.sum()) == max(b for _, b in new_cells.values()), "G5 is asked of those who have heard of at least one AI tool"
for t in tools:
    note(genai, f"Used {t} (of those who have heard of an AI tool)", g_new, share(*new_cells[t]))
    note(genai, f"Used {t} (of those who have heard of an AI tool)", g_old, share(*old_cells[t]))
lead = rose[0] if rose else tools[0]
samples.append({
    "id": "s12", "level": "Hard", "type": "T5 Two periods compared", "market": "US", "survey": US,
    "question": "Are more people using AI tools like ChatGPT and Gemini than a year ago?",
    "headline": f"Among US adults who have heard of at least one AI tool, use of {lead} rose from {share(*old_cells[lead]):.1f}% ({day(g_old)}) to "
                f"<em>{share(*new_cells[lead]):.1f}%</em> ({day(g_new)})"
                + (f"; {names([{'group': t} for t in same])} {'was' if len(same) == 1 else 'were'} about the same a year apart"
                   f" (ChatGPT {share(*old_cells['ChatGPT']):.1f}% then, {share(*new_cells['ChatGPT']):.1f}% now)." if same else "."),
    "cards": [{"label": f"{lead}, {day(g_new)}", "value": f"{share(*new_cells[lead]):.1f}%", "note": "Of those who have heard of an AI tool", "tone": "main"},
              {"label": f"{lead}, {day(g_old)}", "value": f"{share(*old_cells[lead]):.1f}%", "note": "A year earlier", "tone": ""},
              {"label": "Change", "value": f"{moves[lead][2]:+.1f} pts", "note": "A real rise" if moves[lead][1] == "up" else "Could be chance", "tone": moves[lead][1]}],
    "chart": {"kind": "paired", "title": "AI tools people have used", "unit": "% of US adults who have heard of at least one AI tool",
              "periods": [day(g_old), day(g_new)],
              "bars": [{"label": t, "old": round(share(*old_cells[t]), 1), "pct": round(share(*new_cells[t]), 1)} for t in tools],
              "foot": ["People could choose more than one.", "Asked only of people who have heard of at least one of the tools listed."]},
    "evidence": {"wording": [genai["versions"][-1], "Asked of people who had heard of at least one tool in “" + load("G4")["versions"][-1] + "”"],
                 "source": f"{US}, {day(g_old)} and {day(g_new)}",
                 "table": {"head": ["Tool", day(g_old), day(g_new)],
                           "rows": [[t, f"{share(*old_cells[t]):.1f}%", f"{share(*new_cells[t]):.1f}%"] for t in tools]}},
    "alternatives": ["AI tools people have heard of (Coresight US Consumer Survey, last asked 2 Nov 2026)",
                     "AI tools people used to help them shop (Coresight US Consumer Survey, last asked 3 Aug 2026)"],
    "chips": [{"label": "Over time"}, {"label": "By generation"}, {"label": "AI used for shopping"}],
})

# S13 complex, T6 one group within another question (respondent level, one survey) ------------------------------------
t_day, t_sid = "2026-11-23", 725
people_725 = json.loads(gzip.decompress((PUBLISHED / f"waves/{t_sid}/people.json.gz").read_bytes()))
size = size_of(people_725)
hurt, asked_tf1 = mask(people_725, size, {"q": "TF1", "is": NEG})
changed, asked_tf5 = mask(people_725, size, {"q": "TF5", "is": ["Yes"]})
both = asked_tf1 & asked_tf5
group_n, group_b = int((changed & hurt & both).sum()), int((hurt & both).sum())
rest_n, rest_b = int((changed & ~hurt & both).sum()), int((~hurt & both).sum())
all_n, all_b = int((changed & both).sum()), int(both.sum())
assert (all_n, all_b) == counts(load("TF5"), t_day)["Yes"], "respondent file and question file agree"
real = significant(share(group_n, group_b), group_b, share(rest_n, rest_b), rest_b)
tf5 = load("TF5")
sources.append({"figure": "Changed how they shop, among those who say tariffs hurt them", "value": f"{share(group_n, group_b):.1f}%",
                "date": day(t_day), "file": f"data/published/preview/current/api/v1/waves/{t_sid}/people.json.gz", "wording": tf5["versions"][-1]})
sources.append({"figure": "Changed how they shop, everyone else", "value": f"{share(rest_n, rest_b):.1f}%",
                "date": day(t_day), "file": f"data/published/preview/current/api/v1/waves/{t_sid}/people.json.gz", "wording": tf5["versions"][-1]})
note(tf5, "Changed how they shop, all US adults", t_day, share(all_n, all_b))
samples.append({
    "id": "s13", "level": "Complex", "type": "T6 One group within another question", "market": "US", "survey": US,
    "question": "Among people who say tariffs hurt them, how many have changed how they shop?",
    "headline": f"Among US adults who say tariffs have a negative impact on them, <em>{share(group_n, group_b):.1f}%</em> said they had "
                f"changed their shopping to avoid the effects of tariffs in the latest survey ({day(t_day)}), compared with "
                f"{share(all_n, all_b):.1f}% of all US adults and {share(rest_n, rest_b):.1f}% of everyone else, "
                f"{'a real difference' if real else 'a difference that could be chance'}.",
    "cards": [{"label": "Say tariffs hurt them", "value": f"{share(group_n, group_b):.1f}%", "note": "Changed how they shop", "tone": "main"},
              {"label": "All US adults", "value": f"{share(all_n, all_b):.1f}%", "note": "Changed how they shop", "tone": ""},
              {"label": "Difference", "value": f"{share(group_n, group_b) - share(rest_n, rest_b):.1f} pts",
               "note": ("A real difference" if real else "Could be chance") + " vs everyone else", "tone": ""}],
    "chart": {"kind": "columns", "title": "Changed their shopping to avoid the effects of tariffs", "unit": f"% of each group, US, {day(t_day)}",
              "bars": [{"label": "Say tariffs hurt them", "pct": round(share(group_n, group_b), 1)},
                       {"label": "Everyone else", "pct": round(share(rest_n, rest_b), 1)},
                       {"label": "All US adults", "pct": round(share(all_n, all_b), 1)}],
              "foot": ["Counted person by person from the same survey's answers."]},
    "evidence": {"wording": [tf5["versions"][-1], f"Say tariffs hurt them: people who answered “very negative” or “somewhat negative” "
                                                  f"to “{tariffs['versions'][0]}”"],
                 "source": f"{US}, {day(t_day)}",
                 "table": {"head": ["Group", "Changed how they shop"],
                           "rows": [["Say tariffs hurt them", f"{share(group_n, group_b):.1f}%"], ["Everyone else", f"{share(rest_n, rest_b):.1f}%"],
                                    ["All US adults", f"{share(all_n, all_b):.1f}%"]]}},
    "alternatives": ["How people changed their shopping to avoid tariffs (Coresight US Consumer Survey, last asked 23 Nov 2026)"],
    "chips": [{"label": "How they changed it"}, {"label": "Over time"}, {"label": "Tariffs hurting people over time", "goto": "s7"}],
})

OPEN_QUESTIONS = [
    ("Show the word “unweighted” on answers?", "No. Say “Census-weighted figures” only when the weighted switch is on."),
    ("Keep the number of people asked in the Excel export?", "No."),
    ("Long ranked lists (retailers, products): vertical or horizontal bars?", "Vertical, as decided; the retailer mock-up shows both so you can choose."),
    ("A weekly view for questions asked every week?", "No: monthly, quarterly and yearly only."),
    ("A side-by-side option when both markets ask a question?", "No: two buttons, US results and China results."),
    ("Does a country named in the question override the market selector?", "Yes: “Chinese consumers” answers from China whatever the selector says."),
    ("Neutral or green/red arrows on changes?", "Neutral ink arrows: up is not always good (“worried about tariffs” up)."),
    ("When two survey questions fit about equally: ask back first, or answer the best match and offer the other?",
     "Answer the best match and offer the others under “Not what you meant?” (today's behaviour)."),
    ("How to warn about small samples without showing the number of people?",
     "“Fewer than 50 people answered here: read with caution.” Under 30, the figure is kept out of the headline and cards."),
    ("A market ask-back and a question ask-back in the same answer?", "Ask the market only, then answer the best match and offer the others."),
    ("The selected market does not ask the question at all (China selected, a US-only question)?",
     "Answer from the market that asks it and say so at the top of the answer."),
]

assert f"{share(*yes_latest):.1f}" == "65.5", "the manager's one real template figure (28 Sep 2026)"

HERE.joinpath("samples.js").write_text(
    "// Written by build_samples.py from the published files of 27 Nov 2026. Do not edit by hand: run the script again.\n"
    "window.SAMPLES = " + json.dumps(samples, indent=1, ensure_ascii=False) + ";\n"
    "window.OPEN_QUESTIONS = " + json.dumps(OPEN_QUESTIONS, indent=1, ensure_ascii=False) + ";\n")

lines = ["# Ask CIP: sample questions and expected answers (awaiting analyst check)", "",
         "Status: **checked by the user, all correct (27 Nov 2026).** Written 27 Nov 2026 by `build_samples.py` from the published files of 27 Nov 2026",
         "(`data/published/preview/current`). The mock-ups (`index.html`) draw the same answers. Every sentence comes from a fixed",
         "pattern per answer type, every figure from one survey's file. Keep these questions out of every tuning set and out of",
         "`config/ask_verified.yml`.", "",
         "Rule used for “higher / lower / up / down”: the 95% two-proportion test of `api/dashboards.py` significant; otherwise",
         "“about the same” or “could be chance”. The number of people asked is not shown in the answers (the meeting's decision);",
         "it is in each file named below.", ""]
for s in samples:
    lines += [f"## {s['id'].upper()}. {s['question']}", "", f"- Level: {s['level']}. Answer type: {s['type']}. Market: {s['market']}."]
    if s.get("read_as"):
        lines.append(f"- Follow-up of {s['previous'].upper()}. Read as: {s['read_as']}.")
    if s.get("ask_back"):
        lines.append(f"- Market Both: Ask asks back: “{s['ask_back']['text']}” ({' / '.join(c['label'] for c in s['ask_back']['choices'])}).")
        for key, ans in s["answers"].items():
            lines.append(f"- If {key}: {ans['headline'].replace('<em>', '**').replace('</em>', '**')}")
            lines.append("  - Cards: " + " | ".join(f"{c['label']}: {c['value']} ({c['note']})" for c in ans["cards"]))
    elif s.get("no_answer"):
        lines.append(f"- Expected answer: {s['no_answer']['text']} " + "; ".join(s["no_answer"]["closest"]) + ". No figures.")
    else:
        lines.append(f"- Expected answer: {s['headline'].replace('<em>', '**').replace('</em>', '**')}")
        lines.append("  - Cards: " + " | ".join(f"{c['label']}: {c['value']} ({c['note']})" for c in s["cards"]))
        lines.append(f"  - Chart: {s['chart']['kind']}, “{s['chart']['title']}”.")
    lines.append("")
lines += ["## Where every figure comes from", "", "| Figure | Value | Survey date | File |", "|---|---|---|---|"]
lines += [f"| {r['figure']} | {r['value']} | {r['date']} | `{r['file']}` |" for r in sources]
lines += ["", "## Open questions for the manager (built with the default until answered)", ""]
lines += [f"{n}. {q} **Default:** {d}" for n, (q, d) in enumerate(OPEN_QUESTIONS, 1)]
HERE.joinpath("samples.md").write_text("\n".join(lines) + "\n")
print(f"{len(samples)} samples, {len(sources)} figures -> {HERE}")
