"""Ask CIP's arithmetic: a plan (api/ask_reader.py) and one question's exact counts (api/ask_index.py) → figures.

Who calls it: api/assistant.py. Every percentage is people ÷ base from the published counts; a period of several
waves (two weeks, four weeks, a month, a quarter, a year, "the last 8 weeks") pools them: the people who gave the
answer in all its waves ÷ all its bases, the same as reading the respondents of those waves together. numpy
bincounts: well under a millisecond for a period, a few for a long series.

Grains: wave (each wave), biweek and 4week (consecutive waves counted back from the newest, so the latest group is
always complete), month, quarter, year (calendar, by wave date).
"""
from __future__ import annotations

import calendar
import re
from datetime import date, timedelta

import numpy as np

from api.dashboards import significant
from etl.weekly_report import band

PERIOD_KEY = {"month": lambda d: d[:7], "quarter": lambda d: f"{d[:4]}-Q{(int(d[5:7]) + 2) // 3}", "year": lambda d: d[:4]}
AUTO_WAVES, AUTO_MONTHS = 26, 36   # a trend with no grain asked: waves up to 26 points, then months, then quarters


def label_date(day: str) -> str:
    d = date.fromisoformat(day)
    return f"{d.day} {calendar.month_abbr[d.month]} {d.year}"


def pick(spec: dict, dates: list[str]) -> list[int]:
    """The indexes (into the question's waves, oldest first) that one period spec covers."""
    if not dates:
        return []
    newest = date.fromisoformat(dates[-1])
    within = lambda lo, hi: [i for i, d in enumerate(dates) if lo <= d <= hi]   # noqa: E731
    if "latest" in spec:
        return [len(dates) - spec["latest"]] if spec["latest"] <= len(dates) else []
    if "first" in spec:
        return [spec["first"] - 1] if spec["first"] <= len(dates) else []
    if "all" in spec:
        return list(range(len(dates)))
    if "year" in spec:
        return within(f"{spec['year']}-01-01", f"{spec['year']}-12-31")
    if "month" in spec:
        y, m = spec["month"]
        return within(f"{y}-{m:02d}-01", f"{y}-{m:02d}-31")
    if "quarter" in spec:
        y, q = spec["quarter"]
        return within(f"{y}-{3 * q - 2:02d}-01", f"{y}-{3 * q:02d}-31")
    if "from" in spec:
        return within(spec["from"], spec["to"])
    if "last" in spec:
        n, unit = spec["last"], spec["unit"]
        if unit == "wave":
            return list(range(max(0, len(dates) - n), len(dates)))
        if spec.get("previous"):   # "last month" / "last year": the calendar one before the newest wave's
            if unit == "month":
                y, m = (newest.year, newest.month - 1) if newest.month > 1 else (newest.year - 1, 12)
                return within(f"{y}-{m:02d}-01", f"{y}-{m:02d}-31")
            return within(f"{newest.year - 1}-01-01", f"{newest.year - 1}-12-31")
        days = {"week": 7, "month": 30.44, "year": 365.25}[unit] * n
        return within(str(newest - timedelta(days=round(days) - 1)), dates[-1])
    return []


def group(indexes: list[int], dates: list[str], grain: str) -> list[list[int]]:
    """Consecutive groups of waves for a series, oldest group first. Months, quarters and years with no wave between
    the first and the last are empty groups (named by calendar_gaps), so a gap shows as a gap, never as a smooth line."""
    if grain == "wave":
        return [[i] for i in indexes]
    if grain in ("biweek", "4week"):   # calendar windows of 14 or 28 days counted back from the newest wave
        days, newest = (14 if grain == "biweek" else 28), date.fromisoformat(dates[indexes[-1]]) if indexes else None
        windows: dict[int, list[int]] = {}
        for i in indexes:
            windows.setdefault((newest - date.fromisoformat(dates[i])).days // days, []).append(i)
        return [windows[k] for k in sorted(windows, reverse=True)]
    key = PERIOD_KEY[grain]
    out: dict[str, list[int]] = {k: [] for k in calendar_keys(key(dates[indexes[0]]), key(dates[indexes[-1]]), grain)} if indexes else {}
    for i in indexes:
        out.setdefault(key(dates[i]), []).append(i)
    return list(out.values())


def calendar_keys(first: str, last: str, grain: str) -> list[str]:
    """Every month ("2024-03"), quarter ("2024-Q1") or year ("2024") from first to last."""
    if grain == "year":
        return [str(y) for y in range(int(first), int(last) + 1)]
    if grain == "quarter":
        y, q = int(first[:4]), int(first[-1])
        out = []
        while f"{y}-Q{q}" <= last:
            out.append(f"{y}-Q{q}")
            y, q = (y + 1, 1) if q == 4 else (y, q + 1)
        return out
    y, m = int(first[:4]), int(first[5:7])
    out = []
    while f"{y}-{m:02d}" <= last:
        out.append(f"{y}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def name_period(waves: list[int], dates: list[str], grain: str | None) -> str:
    first, last = dates[waves[0]], dates[waves[-1]]
    if grain == "month":
        return f"{calendar.month_abbr[int(first[5:7])]} {first[:4]}"
    if grain == "quarter":
        return f"Q{(int(first[5:7]) + 2) // 3} {first[:4]}"
    if grain == "year":
        return first[:4]
    return label_date(first) if first == last else f"{label_date(first)} – {label_date(last)}"


def calendar_label(key: str) -> str:
    """ "2024-03" → "Mar 2024", "2024-Q1" → "Q1 2024", "2024" → "2024"."""
    if "-Q" in key:
        return f"Q{key[-1]} {key[:4]}"
    if "-" in key:
        return f"{calendar.month_abbr[int(key[5:7])]} {key[:4]}"
    return key


def auto_grain(indexes: list[int], dates: list[str]) -> str:
    if len(indexes) <= AUTO_WAVES:
        return "wave"
    months = {dates[i][:7] for i in indexes}
    return "month" if len(months) <= AUTO_MONTHS else "quarter"


def income_floor(band: str) -> int | None:
    """An income band's lowest dollar amount ("$100,000-$124,999" 100,000, "under $25,000" 0); None for "prefer not to say"."""
    text = band.lower().replace(",", "")
    if "prefer" in text or "not" in text:
        return None
    if text.startswith(("under", "less than")):
        return 0
    found = re.search(r"\$\s*(\d+)", text)
    return int(found[1]) if found else None


def cut_columns(counts: dict, cuts: dict) -> list[int]:
    """The cut indexes to show: Total, or the values asked for (every value of a dimension for "by …")."""
    present = [tuple(c) for c in counts["cuts"]]
    out = []
    for dim, values in cuts.items():
        out += [i for i, (d, v) in enumerate(present) if d == dim and (values == "all" or v in values)]
        if out:
            break   # one dimension at a time keeps a chart readable; the answer says which was used
    return out or [0]


def pool(counts: dict, waves: list[int], cut: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """people, bases and "some wave not published" per answer, summed over the waves of one period and one cut."""
    size = len(counts["answers"])
    keep = np.isin(counts["w"], waves) & (counts["c"] == cut)
    a, n, b = counts["a"][keep], counts["n"][keep], counts["b"][keep]
    people = np.bincount(a, weights=np.maximum(n, 0), minlength=size)
    bases = np.bincount(a, weights=b, minlength=size)
    hidden = np.bincount(a, weights=(n < 0), minlength=size) > 0
    return people, bases, hidden


def compute(counts: dict, plan: dict, visible: set[int], versions: list[int] | None = None) -> dict:
    """The figures a plan asks for: periods, columns (cuts), and per period × column × answer the people, base and %.
    `versions`: the wordings that make this question (api/ask_index.py splits a reused code); None for all."""
    waves = [w for w in counts["waves"] if w[0] in visible and (versions is None or w[2] in versions)]
    index_of = {w[0]: i for i, w in enumerate(counts["waves"])}
    if not plan["when"] and plan["cuts"]:   # no period named: the newest wave that has the group asked about. 12 of q3's
        dim, groups = next(iter(plan["cuts"].items()))   # 219 waves have no generation figures, one of them the newest
        cols = [i for i, (cut, value) in enumerate(counts["cuts"]) if cut == dim and (groups == "all" or value in groups)]
        having = set(np.asarray(counts["w"])[np.isin(counts["c"], cols)].tolist())   # of that wording ("Gen Z clothing online", 20 Nov 2026)
        waves = [w for w in waves if index_of[w[0]] in having] or waves
    dates = [w[1] for w in waves]
    when = plan["when"] or ([{"all": True}] if plan["kind"] == "trend" else [{"latest": 1}])
    grain = plan["grain"]
    picked = [pick(spec, dates) for spec in when]
    if plan["kind"] == "trend" or (grain and len(when) == 1):
        chosen = sorted(set(sum(picked, [])))
        grain = grain or auto_grain(chosen, dates)
        groups = group(chosen, dates, grain)
        key = PERIOD_KEY.get(grain)
        names = calendar_keys(key(dates[chosen[0]]), key(dates[chosen[-1]]), grain) if key and chosen else None
    else:
        groups = sorted((p for p in picked if p), key=lambda p: p[0])   # oldest first: a change reads forwards in time
        if plan["kind"] == "change" and len(groups) == 1 and groups[0] and groups[0][0] > 0:
            size = len(groups[0])   # a change: against the same length of time just before
            groups = [list(range(max(0, groups[0][0] - size), groups[0][0])), groups[0]]
        grain = None
        names = None
    if names is None:
        groups = [g for g in groups if g]
    columns = [(tuple(counts["cuts"][c]), [c]) for c in cut_columns(counts, plan["cuts"])]
    if plan.get("merge"):   # named groups of values ("high income" = the bands from $100,000): their people summed
        dim = next(iter(plan["cuts"]))
        inside = lambda v, values: (income_floor(v) is not None and values[0] <= income_floor(v) < values[1]) \
            if isinstance(values, tuple) else v in values   # noqa: E731  a dollar range, or the values themselves
        columns = [col for col in (((dim, label), [c for c, (d, v) in enumerate(counts["cuts"]) if d == dim and inside(v, values)])
                                   for label, values in plan["merge"].items()) if col[1]] or columns
    periods, people, bases, hidden = [], [], [], []
    for k, g in enumerate(groups):
        rows = [[sum(part) for part in zip(*(pool(counts, [index_of[waves[i][0]] for i in g], c) for c in cuts))] for _, cuts in columns]
        rows = [(r[0], r[1], r[2] > 0) for r in rows]
        people.append([r[0] for r in rows])
        bases.append([r[1] for r in rows])
        hidden.append([r[2] for r in rows])
        if not g:   # a calendar period with no wave: a gap in the series
            periods.append({"label": calendar_label(names[k]), "from": "", "to": "", "waves": [], "versions": []})
            continue
        periods.append({"label": name_period(g, dates, grain) if grain or len(g) > 1 else label_date(dates[g[0]]),
                        "from": dates[g[0]], "to": dates[g[-1]], "waves": [waves[i][0] for i in g],
                        "versions": sorted({waves[i][2] for i in g})})
    n, b = np.array(people), np.array(bases)
    with np.errstate(divide="ignore", invalid="ignore"):
        shown = (b > 0) & ~np.array(hidden, bool)
        # Python's round on each figure, as every screen rounds (shared/data/payloads.py): numpy's differs on halves
        pct = np.array([round(100 * x / y, 1) if ok else np.nan for x, y, ok in zip(n.ravel(), b.ravel(), shown.ravel())]
                       ).reshape(n.shape) if periods else np.zeros((0, 0, 0))
    if len(columns) > 1 and pct.size:   # a group these periods never had (the income bands before 2023): no empty column
        kept = ~np.isnan(pct).all(axis=(0, 2))
        if kept.any():
            columns, n, b, pct = [c for c, k in zip(columns, kept) if k], n[:, kept], b[:, kept], pct[:, kept]
    answers = [f"{item}: {label}" if item and item != label else label for item, _, label in counts["answers"]]
    return {"periods": periods, "grain": grain, "columns": [list(cut) for cut, _ in columns], "answers": answers,
            "people": n, "bases": b, "pct": pct, "asked": [w[1] for w in waves],
            "versions": counts["versions"], "missing": [i for i, p in enumerate(picked) if not p]}


def middle(fig: dict) -> list[tuple[int, str, float]]:
    """For an amount question (a holiday budget in dollar bands), per column of the latest period: the band the middle
    person's answer falls in (exact, from the counts) and the average estimated from band mid-points, an open top band
    counted at its floor. Only those who gave an amount count ("Don't know" left out). Empty when the answers are not
    amount bands. Called by api/assistant.py answer for "median", "average", "typical" questions."""
    bands = sorted(((b, a) for a, label in enumerate(fig["answers"]) if (b := band(label))), key=lambda x: x[0][0])
    if len(bands) < 3 or not len(fig["periods"]):
        return []
    found = []
    for column in range(len(fig["columns"])):
        people = [float(fig["people"][-1, column, a]) for _, a in bands]
        total = sum(people)
        if not total:
            continue
        running = np.cumsum(people)
        median_band = fig["answers"][bands[int(np.searchsorted(running, total / 2))][1]]
        mean = sum(n * ((low + high) / 2 if high is not None else low) for n, ((low, high), _) in zip(people, bands)) / total
        found.append((column, median_band, round(mean)))
    return found


def moved(fig: dict, answer: int, column: int = 0) -> tuple[float, bool] | None:
    """The change in points between the last two periods for one answer, and whether it is significant (95%)."""
    if len(fig["periods"]) < 2:
        return None
    p1, p2 = fig["pct"][-2, column, answer], fig["pct"][-1, column, answer]
    n1, n2 = int(fig["bases"][-2, column, answer]), int(fig["bases"][-1, column, answer])
    if np.isnan(p1) or np.isnan(p2):
        return None
    tested = fig.get("tested", fig["pct"])   # weighted figures are tested on their unweighted shares (etl/weighting.py)
    if "tested" not in fig:   # unweighted: the change of the real shares, not of two rounded ones (42.6 to 51.7 is 9.2 points)
        p1, p2 = 100 * fig["people"][-2, column, answer] / n1, 100 * fig["people"][-1, column, answer] / n2
    return round(float(p2 - p1), 1), significant(float(tested[-1, column, answer]), n2, float(tested[-2, column, answer]), n1)
