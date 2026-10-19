"""The data team's cross-tab workbook, built from cip_stg instead of Forsta's crosstab tool.

Same layout as their Forsta export (Cross Tabs, Holiday Status Cross Tabs,
Inflation_Sentiment Cross Tabs): a Summary tab (report settings, segment
definitions with n), then Percentages and Counts, one stacked table per
question, banner columns across, the base ("N=") under the headers, and a flag
column beside each segment (* under 100 respondents, ** under 30). Segments are
the team's own Forsta expressions (config/crosstab_banners.yml), qualified
respondents only, percentage base = total answering. A banner set with
`stat_groups` gets Forsta's significance letters in the flag column (upper case
95 %, lower case 90 %): a pooled z-test on proportions, a t-test on means.

    python -m etl.crosstab_export --compare "Cross Tabs 10_12_26.xlsx" [--survey 412]

--compare rebuilds the same banner from the database and reports every table
row whose count differs from the team's file.
"""
from __future__ import annotations

import argparse
import io
import math
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import yaml
from sqlalchemy import text

from app.core.database import get_engine

CONFIG = Path(__file__).resolve().parents[1] / "config" / "crosstab_banners.yml"
TOKEN = re.compile(r"^(?P<q>[A-Za-z0-9_]+)\.(?P<kind>r|ch)(?P<n>\d+)(?:\.c(?P<c>\d+))?$")


@lru_cache(maxsize=1)
def banners() -> dict:
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


@dataclass
class Wave:
    title: str
    people: pd.DataFrame          # qualified respondents: respondent_id
    wide: pd.DataFrame            # respondent_id x field_name: value_code (or number)
    questions: pd.DataFrame
    items: pd.DataFrame
    options: pd.DataFrame
    fields: pd.DataFrame


def load_wave(survey_id: int, role: str = "etl") -> Wave:
    with get_engine(role).connect() as conn:
        read = lambda sql: pd.read_sql(text(sql), conn, params={"s": survey_id})
        title = conn.execute(text("SELECT title FROM cip_survey WHERE survey_id = :s"), {"s": survey_id}).scalar()
        people = read("SELECT respondent_id FROM cip_respondent WHERE survey_id = :s AND is_qualified = 1")
        answers = read("""SELECT a.respondent_id, f.field_name, COALESCE(a.value_code, a.value_number) AS v
                            FROM cip_answer a JOIN cip_field f ON f.field_id = a.field_id
                            JOIN cip_respondent r ON r.respondent_id = a.respondent_id AND r.is_qualified = 1
                           WHERE a.survey_id = :s AND COALESCE(a.value_code, a.value_number) IS NOT NULL""")
        questions = read("""SELECT question_id, qcode, qtext, qtype, is_multi, sort_order FROM cip_question
                             WHERE survey_id = :s AND is_virtual = 0 AND is_technical = 0 ORDER BY sort_order""")
        items = read("""SELECT i.item_id, i.question_id, i.item_code, i.item_label, i.sort_order FROM cip_item i
                          JOIN cip_question q ON q.question_id = i.question_id WHERE q.survey_id = :s ORDER BY i.sort_order""")
        options = read("""SELECT o.question_id, o.value_code, o.value_label, o.sort_order FROM cip_option o
                            JOIN cip_question q ON q.question_id = o.question_id WHERE q.survey_id = :s ORDER BY o.sort_order""")
        fields = read("SELECT field_name, question_id, item_id FROM cip_field WHERE survey_id = :s")
    wide = answers.pivot_table(index="respondent_id", columns="field_name", values="v", aggfunc="first")
    wide = wide.reindex(people["respondent_id"])
    return Wave(title or "", people, wide, questions, items, options, fields)


def member(wave: Wave, expression: str) -> pd.Series:
    """Respondents matching a Forsta expression (terms joined by ' or ')."""
    hit = pd.Series(False, index=wave.wide.index)
    for term in expression.split(" or "):
        m = TOKEN.match(term.strip())
        if not m:
            raise ValueError(f"cannot read segment term {term!r}")
        q, kind, n, cell = m["q"], m["kind"], int(m["n"]), m["c"]
        if cell is not None:                                  # grid cell: row n, column c
            column, want = f"{q}r{n}", int(cell)
        elif f"{q}r{n}" in wave.wide.columns and q not in wave.wide.columns:   # one box of a multi
            column, want = f"{q}r{n}", 1
        else:                                                 # single or dropdown: choice n
            column, want = q, banners().get("choice_code", {}).get(q, {}).get(n, n) if kind == "ch" else n
        if column in wave.wide.columns:
            hit |= wave.wide[column] == want
    return hit


def available(wave: Wave) -> list[str]:
    """The banner sets this wave's questionnaire can fill: every question a segment reads must exist in the wave."""
    fields = set(wave.fields["field_name"])
    keys = []
    for key, plan in banners().items():
        if not (isinstance(plan, dict) and "segments" in plan):
            continue
        needed = set()
        for s in plan["segments"]:
            for term in s["expr"].split(" or "):
                m = TOKEN.match(term.strip())
                if m:
                    needed.add((f"{m['q']}r{m['n']}",) if m["c"] is not None else (m["q"], f"{m['q']}r{m['n']}"))
        if all(any(name in fields for name in names) for names in needed):
            keys.append(key)
    return keys


def flag(n: int) -> str:
    return "**" if n < 30 else "*" if n < 100 else ""


def segments(wave: Wave, key: str) -> list[tuple[str, pd.Series]]:
    return [(s["label"], member(wave, s["expr"])) for s in banners()[key]["segments"]]


def tables(wave: Wave) -> list[dict]:
    """Every tabulated question as {qcode, title, blocks:[{name, rows:[(label, field_or_code, kind)]}]}."""
    out = []
    for q in wave.questions.itertuples():
        items = wave.items[wave.items["question_id"] == q.question_id]
        options = wave.options[wave.options["question_id"] == q.question_id]
        title = f"{q.qcode}: {q.qtext}"
        fields = list(wave.fields[wave.fields["question_id"] == q.question_id]["field_name"])
        if q.qtype == "text":
            continue
        if q.qtype == "numeric":                    # Forsta's "Don't know" box is a separate noanswer field
            unsure = wave.fields[wave.fields["field_name"] == f"noanswer{q.qcode}_r1"]
            label = wave.items[wave.items["item_id"].isin(unsure["item_id"])]["item_label"]
            out.append({"qcode": q.qcode, "title": title, "kind": "numeric", "fields": fields, "blocks": [],
                        "unsure": (str(label.iloc[0]).rsplit(": ", 1)[-1] if len(label) else "Don't know",
                                   f"noanswer{q.qcode}_r1") if len(unsure) else None})
        elif q.is_multi:
            rows = [(r.item_label, r.item_code) for r in items.itertuples()]
            out.append({"qcode": q.qcode, "title": title, "kind": "multi", "fields": fields,
                        "blocks": [{"name": None, "rows": rows}]})
        elif len(items) and q.qtype.startswith("grid"):
            blocks = [{"name": r.item_label, "field": r.item_code,
                       "rows": [(o.value_label, int(o.value_code)) for o in options.itertuples()]} for r in items.itertuples()]
            out.append({"qcode": q.qcode, "title": title, "kind": "grid", "fields": fields, "blocks": blocks})
        else:
            out.append({"qcode": q.qcode, "title": title, "kind": "single", "fields": fields,
                        "blocks": [{"name": None, "field": q.qcode,
                                    "rows": [(o.value_label, int(o.value_code)) for o in options.itertuples()]}]})
    return out


def cells(wave: Wave, table: dict, seg: pd.Series) -> list[tuple[Optional[str], list[tuple[str, float]], int]]:
    """For one segment: per block, [(row label, count)], and the block's base (people answering)."""
    out = []
    wide = wave.wide[seg.values]
    for block in table["blocks"] or [None]:
        if table["kind"] == "numeric":
            values = wide[table["fields"][0]].dropna() if table["fields"] and table["fields"][0] in wide else pd.Series(dtype=float)
            stats = [("Mean", values.mean()), ("Median", values.median()), ("Standard Deviation", values.std(ddof=1))]
            if table.get("unsure"):                 # counted beside the base, as Forsta does
                label, column = table["unsure"]
                stats.append((label, float((wide[column] == 1).sum()) if column in wide else 0.0))
            out.append((None, stats, int(len(values))))
        elif table["kind"] == "multi":
            have = [f for f in table["fields"] if f in wide.columns]
            answered = wide[have].notna().any(axis=1) if have else pd.Series(False, index=wide.index)
            counts = [(label, float((wide[code] == 1).sum()) if code in wide else 0.0) for label, code in block["rows"]]
            base = int(answered.sum())
            out.append((None, counts + [("Count", sum(c for _, c in counts) / base if base else float("nan"))], base))
        elif table["kind"] == "grid":
            column = block["field"]
            answered = wide[column].notna() if column in wide else pd.Series(False, index=wide.index)
            counts = [(label, float((wide[column] == code).sum()) if column in wide else 0.0) for label, code in block["rows"]]
            out.append((block["name"], counts, int(answered.sum())))
        else:
            column = block["field"]
            answered = wide[column].notna() if column in wide else pd.Series(False, index=wide.index)
            counts = [(label, float((wide[column] == code).sum()) if column in wide else 0.0) for label, code in block["rows"]]
            out.append((None, counts, int(answered.sum())))
    return out


STATS = ("Count", "Mean", "Median", "Standard Deviation")
Z95, Z90 = 1.959964, 1.644854


def ztest(x1: float, n1: int, x2: float, n2: int) -> float:
    """Column proportions, as Forsta tests them — reverse-fitted on the team's 10/12/26 exports: pooled
    proportion over n−1 bases (4,064 of 4,068 holiday-banner letters equal; the 4 others have bases under 30)."""
    if n1 < 2 or n2 < 2:
        return 0.0
    p = (x1 + x2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / (n1 - 1) + 1 / (n2 - 1)))
    return (x1 / n1 - x2 / n2) / se if se else 0.0


def ttest(m1: float, s1: float, n1: int, m2: float, s2: float, n2: int) -> float:
    """Column means (Welch's t, judged on the normal critical values like the proportions)."""
    if n1 < 2 or n2 < 2 or any(v != v for v in (m1, s1, m2, s2)):
        return 0.0
    se = math.sqrt(s1 ** 2 / n1 + s2 ** 2 / n2)
    return (m1 - m2) / se if se else 0.0


def stat_groups(key: str) -> list[list[int]]:
    """'B-E,FG' -> [[1, 2, 3, 4], [5, 6]]: column indexes (Total = 0) tested against each other."""
    groups = []
    for part in str(banners()[key].get("stat_groups") or "").split(","):
        part = part.strip()
        if "-" in part:
            first, last = part.split("-")
            groups.append(list(range(ord(first) - 65, ord(last) - 64)))
        elif part:
            groups.append([ord(c) - 65 for c in part])
    return groups


def marks(per: list, b: int, groups: list[list[int]]) -> dict[int, list[str]]:
    """Significance letters for block b: {row index: letters per column}. Proportion rows get the
    z-test, a numeric block's Mean the t-test; Count, Median, SD and "Don't know" rows get none."""
    if not groups:
        return {}
    names = [name for name, _ in per[0][b][1]]
    if names[:1] == ["Mean"]:
        stats = [(c[b][1][0][1], c[b][1][2][1], c[b][2]) for c in per]
        rows = {0: (stats, ttest)}
    else:
        rows = {k: ([(c[b][1][k][1], c[b][2]) for c in per], ztest) for k, name in enumerate(names) if name not in STATS}
    out = {}
    for k, (stats, test) in rows.items():
        letters = [""] * len(per)
        for group in groups:
            for j in group:
                for other in group:
                    if other != j and j < len(per) and other < len(per):
                        z = test(*stats[j], *stats[other])
                        letters[j] += _letter(other) if z > Z95 else _letter(other).lower() if z > Z90 else ""
        out[k] = letters
    return out


def compute(wave: Wave, key: str) -> dict:
    """{(qcode, block name, row label, column letter): (count, base)}, the significance letters on the same
    keys, and each column's size and label — all from the database. Keyed by letter: two segments can share
    a label ("Very" under Higher Inflation and under Higher Gas Prices)."""
    segs = segments(wave, key)
    masks = [pd.Series(True, index=wave.wide.index)] + [m for _, m in segs]
    labels = ["Total"] + [label for label, _ in segs]
    groups = stat_groups(key)
    result, letters = {}, {}
    for table in tables(wave):
        per = [cells(wave, table, m) for m in masks]
        for b, (name, rows, _) in enumerate(per[0]):
            sig = marks(per, b, groups)
            for k, (row, _) in enumerate(rows):
                for j in range(len(masks)):
                    result[(table["qcode"], name, row, _letter(j))] = (per[j][b][1][k][1], per[j][b][2])
                    if k in sig:
                        letters[(table["qcode"], name, row, _letter(j))] = sig[k][j]
    return {"cells": result, "letters": letters, "sizes": {_letter(j): int(m.sum()) for j, m in enumerate(masks)},
            "labels": {_letter(j): label for j, label in enumerate(labels)}}


# ── the workbook ───────────────────────────────────────────────────────────
def build(survey_id: int, key: str, wave: Optional[Wave] = None) -> bytes:
    """One banner set as an .xlsx: Summary, Percentages, Counts."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wave = wave or load_wave(survey_id)
    plan = banners()[key]
    segs = segments(wave, key)
    labels = ["Total"] + [label for label, _ in segs]
    masks = [pd.Series(True, index=wave.wide.index)] + [s for _, s in segs]
    sizes = [int(m.sum()) for m in masks]
    all_tables = tables(wave)
    results = [[cells(wave, t, m) for m in masks] for t in all_tables]
    groups = stat_groups(key)

    book = Workbook()
    summary = book.active
    summary.title = "Summary"
    bold = Font(bold=True)
    summary["B1"] = wave.title
    summary["B1"].font = Font(bold=True, size=13)
    summary["B3"] = "Report Settings"
    summary["B3"].font = bold
    tested = plan.get("stat_groups")
    for r, (a, b) in enumerate([("Respondents:", "Qualified Only"), ("Additional Filter:", "None"), ("Table Set:", "All"),
                                ("Percentage Base:", "Total Answering"),
                                ("Stat Test Levels:", "95 / 90  (z-test)" if tested else "None / None  (z-test)"),
                                ("Stat Test Groups:", tested or "None"), ("Source:", "Consumer Insight Portal (cip_stg), built by the ETL")], start=4):
        summary.cell(r, 2, a).font = bold
        summary.cell(r, 3, b)
    row = 13
    summary.cell(row, 2, "Segment Definitions").font = bold
    row += 1
    summary.cell(row, 2, "Total"), summary.cell(row, 3, "(ALL)"), summary.cell(row, 4, f"n={sizes[0]}")
    for s, n in zip(plan["segments"], sizes[1:]):
        row += 1
        summary.cell(row, 2, f"{s['under']} — {s['label']}" if s.get("under") else s["label"])
        summary.cell(row, 3, f"({s['expr']})")
        summary.cell(row, 4, f"n={n}")
    summary.column_dimensions["B"].width, summary.column_dimensions["C"].width = 56, 60

    def sheet(name: str, percent: bool) -> None:
        ws = book.create_sheet(name)
        ws.cell(1, 1, wave.title).font = Font(bold=True, size=12)
        r = 3
        spans, col = [], 4
        for g in plan["groups"]:
            spans.append((col, g["title"], g["columns"]))
            col += 2 * len(g["columns"])
        for table, per_segment in zip(all_tables, results):
            ws.cell(r, 1, table["title"]).font = Font(bold=True)
            r += 2
            for b, block in enumerate(per_segment[0]):
                if block[0]:
                    ws.cell(r, 1, block[0]).font = bold
                    r += 1
                for start, title, _ in spans:
                    ws.cell(r, start, title).font = bold
                r += 1
                ws.cell(r, 2, "Total (A)").font = bold
                for j, label in enumerate(labels[1:], start=1):
                    ws.cell(r, 2 + 2 * j, f"{label} ({_letter(j)})").font = bold
                r += 1
                ws.cell(r, 1, "Total")
                for j, n in enumerate(sizes):
                    base = per_segment[j][b][2]
                    ws.cell(r, 2 + 2 * j, f"N={base}" if percent else base)
                    if flag(base):
                        ws.cell(r, 3 + 2 * j, flag(base))
                r += 1
                sig = marks(per_segment, b, groups) if percent else {}
                for k, (row_label, _) in enumerate(block[1]):
                    ws.cell(r, 1, row_label)
                    for j in range(len(labels)):
                        count, base = per_segment[j][b][1][k][1], per_segment[j][b][2]
                        stat = row_label in STATS
                        value = round(count, 4) if stat else (count / base if base else 0) if percent else count
                        cell = ws.cell(r, 2 + 2 * j, 0 if value is None or (isinstance(value, float) and np.isnan(value)) else value)
                        if percent and not stat:
                            cell.number_format = "0%"
                        if k in sig and sig[k][j]:
                            ws.cell(r, 3 + 2 * j, sig[k][j]).font = Font(bold=True, color="D62E2F")
                    r += 1
                r += 1
            r += 1
        ws.column_dimensions["A"].width = 58
        ws.freeze_panes = "B1"

    sheet("Percentages", True)
    sheet("Counts", False)
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def _letter(i: int) -> str:
    """Forsta's column letters: A..Z, then A1..Z1, A2.. (Total is A)."""
    n = i
    return chr(65 + n % 26) + (str(n // 26) if n >= 26 else "")


# ── what the email shows ───────────────────────────────────────────────────
def describe(wave: Wave, expression: str) -> str:
    """A segment's Forsta expression in words: 'D1: Male', or 'D2: 11 choices' for a long list."""
    terms = [TOKEN.match(t.strip()) for t in expression.split(" or ")]
    first = terms[0]
    if first is None:
        return expression
    q = wave.questions[wave.questions["qcode"] == first["q"]]
    if len(terms) > 1 or q.empty:
        return f"{first['q']}: {len(terms)} choices"
    qid = int(q["question_id"].iloc[0])
    n = int(first["n"])
    if first["c"] is not None:
        item = wave.items[(wave.items["question_id"] == qid) & (wave.items["item_code"] == f"r{n}")]["item_label"]
        option = wave.options[(wave.options["question_id"] == qid) & (wave.options["value_code"] == int(first["c"]))]["value_label"]
        return f"{first['q']}: {item.iloc[0] if len(item) else 'row ' + str(n)} = {option.iloc[0] if len(option) else first['c']}"
    code = banners().get("choice_code", {}).get(first["q"], {}).get(n, n) if first["kind"] == "ch" else n
    option = wave.options[(wave.options["question_id"] == qid) & (wave.options["value_code"] == code)]["value_label"]
    return f"{first['q']}: {option.iloc[0] if len(option) else code}"


def segment_rows(wave: Wave, key: str) -> list[tuple[str, str, int]]:
    """[(label, definition in words, n)] for the banner set, Total first."""
    plan = banners()[key]
    rows = [("Total", "All qualified respondents", len(wave.wide))]
    for s in plan["segments"]:
        label = f"{s['under']} — {s['label']}" if s.get("under") else s["label"]
        rows.append((label, describe(wave, s["expr"]), int(member(wave, s["expr"]).sum())))
    return rows


def preview(wave: Wave, key: str, qcode: str, labels: list[str], top: int = 0) -> tuple[str, list[str], list[tuple[str, list[Optional[float]]]], list[int]]:
    """(title, column labels, [(row label, [share per column])], bases) for one table across chosen segments."""
    masks = dict(segments(wave, key))
    masks["Total"] = pd.Series(True, index=wave.wide.index)
    labels = [label for label in labels if label in masks]
    table = next((t for t in tables(wave) if t["qcode"] == qcode), None)
    if table is None or table["kind"] == "numeric":
        return "", [], [], []
    per = [cells(wave, table, masks[label])[0] for label in labels]
    rows = [(name, [(c[1][k][1] / c[2]) if c[2] else None for c in per])
            for k, (name, _) in enumerate(per[0][1]) if name != "Count"]
    if top:
        rows = sorted(rows, key=lambda r: -(r[1][0] or 0))[:top]
    return table["title"], labels, rows, [c[2] for c in per]


# ── compare with the team's file ───────────────────────────────────────────
HEADER = re.compile(r"^(?P<label>.*?)\s*\((?P<letter>[A-Z]+\d?)\)$")


def read_team_file(path: str, sheet: str = "Counts") -> tuple[dict, dict, dict]:
    """From a Forsta cross-tab export: ({(qcode, block, row, letter): (value, base)}, the significance letters
    on the same keys, {letter: (label, size)})."""
    from openpyxl import load_workbook

    ws = load_workbook(path, read_only=True, data_only=True)[sheet]
    rows = list(ws.iter_rows(values_only=True))
    found, letters, columns, qcode = {}, {}, {}, None
    for i, row in enumerate(rows):
        first = str(row[0]) if row[0] is not None else ""
        if re.match(r"^[A-Za-z0-9_]+: ", first) and row[1] is None:
            qcode = first.split(":")[0]
        if row[1] != "Total (A)":
            continue
        header = [(c, HEADER.match(str(v))) for c, v in enumerate(row) if v and HEADER.match(str(v))]
        block = str(rows[i - 2][0]) if rows[i - 2][0] else None
        total = rows[i + 1]
        base = {c: int(str(total[c]).removeprefix("N=")) if str(total[c]).removeprefix("N=").isdigit() else None
                for c, _ in header}
        j = i + 2
        while j < len(rows) and rows[j][0] not in (None, ""):
            for c, m in header:
                key = (qcode, block, str(rows[j][0]), m["letter"])
                if isinstance(rows[j][c], (int, float)):
                    found[key] = (float(rows[j][c]), base[c])
                mark = rows[j][c + 1] if c + 1 < len(rows[j]) else None
                letters[key] = "" if mark in (None, "*", "**") else str(mark)
            j += 1
        if qcode == "q1":
            columns.update({m["letter"]: (m["label"], base[c]) for c, m in header if m["letter"] not in columns})
    return found, letters, columns


def compare(path: str, key: str, survey_id: int) -> list[str]:
    """Every count, base and significance letter of the team's file against ours. The first lines
    summarise; the rest name each difference (at most 60)."""
    theirs, _, columns = read_team_file(path, "Counts")
    _, their_letters, _ = read_team_file(path, "Percentages")
    ours = compute(load_wave(survey_id), key)
    problems = [f"column {c} {label}: team n={n}, ours n={ours['sizes'].get(c)} ({ours['labels'].get(c)})"
                for c, (label, n) in columns.items() if ours["sizes"].get(c) != n or ours["labels"].get(c) != label]
    matched = equal = 0
    for k, (count, base) in theirs.items():
        mine = ours["cells"].get(k)
        if mine is None:
            continue
        matched += 1
        value = 0.0 if mine[0] != mine[0] else mine[0]          # Forsta writes 0 where there is no one to count
        if k[2] in STATS:
            same = abs(value - count) < 1e-3 * max(1, abs(count)) and mine[1] == base
        else:
            same = round(value) == round(count) and mine[1] == base
        equal += same
        if not same and len(problems) < 60:
            problems.append(f"{k}: team {count} (base {base}), ours {mine[0]} (base {mine[1]})")
    tested = [k for k in their_letters if k in ours["letters"]]
    same_letters = sum(their_letters[k] == ours["letters"][k] for k in tested)
    for k in tested:
        if their_letters[k] != ours["letters"][k] and len(problems) < 60:
            problems.append(f"{k}: team letters {their_letters[k]!r}, ours {ours['letters'][k]!r} (base {ours['cells'][k][1]})")
    problems[:0] = [f"{matched} of the team's {len(theirs)} cells have a counterpart here (the rest are paradata); {equal} equal",
                    f"significance letters: {same_letters} of {len(tested)} equal"]
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description="Compare our cross-tabs with the team's Forsta export")
    ap.add_argument("--compare", required=True)
    ap.add_argument("--survey", type=int, default=0)
    args = ap.parse_args()
    name = Path(args.compare).name
    key = next((k for k, v in banners().items() if isinstance(v, dict) and "file" in v and v["file"].split("10_12_26")[0].strip() == name.split("10_12_26")[0].strip()), None)
    if key is None:
        raise SystemExit(f"{name}: no banner set in config/crosstab_banners.yml")
    survey_id = args.survey or int(get_engine("etl").connect().execute(text(
        "SELECT survey_id FROM cip_survey WHERE platform = 'forsta' AND load_status = 'verified' ORDER BY wave_date DESC LIMIT 1")).scalar())
    for line in compare(args.compare, key, survey_id):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
