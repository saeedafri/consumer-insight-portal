"""Parsers for the two Forsta Excel exports.

These exist as a bridge: until the API key is issued, CSI can be loaded from
the same files the team receives today. Once the key is live the API path
produces identical rows, so nothing downstream changes.

Layouts observed in the 09/21/26 files:

  Raw Data 09_21_26.xlsx
    sheet 'A1'      — 1 header row of variable names (375 cols), 1 row per
                      respondent (404). Cells hold LABELS, not codes, and
                      unchecked multi-punch items read "NO TO: <label>".
    sheet 'Datamap' — 3 columns, blank-line separated blocks:
                        "<qcode>: <question text>"
                        "Values: <min>-<max>" | "Open text/numeric response"
                        (blank, <code>, <label>)        -> answer options
                        (blank, [<rowcode>], <label>)   -> list/grid rows

  Cross Tabs 09_21_26.xlsx
    sheet 'Summary'     — run settings + 'Segment Definitions' (label,
                          Forsta expression, base n)
    sheet 'Percentages' — 78 stacked tables; header block of 3 rows
                          (banner group / segment+letter / N=), data columns
                          on every 2nd column, sig letters in the odd columns
    sheet 'Counts'      — identical geometry, integer counts
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterator, Optional

import openpyxl

NO_TO = "NO TO: "


def clean_text(value: Any) -> str:
    """Collapse every run of whitespace to one space.

    Forsta's datamap writes some labels with non-breaking spaces
    ('Spent\xa0a lot less…') while the raw export uses ordinary ones. Compared
    as-is the label->code lookup misses and the answer loads with no code, so
    every label passes through here, on every sheet."""
    return " ".join(str(value).split())
# Datamap headers appear both bare (`q1: ...`) and bracketed (`[CS1]: ...`).
QCODE_RE = re.compile(r"^\[?([A-Za-z_][A-Za-z0-9_]*)\]?:\s*(.*)$", re.DOTALL)
VALUES_RE = re.compile(r"^Values:\s*(-?\d+)\s*-\s*(-?\d+)")
SEGMENT_LETTER_RE = re.compile(r"^(.*)\s+\(([A-Z]\d?)\)\s*$")
BASE_RE = re.compile(r"^[Nn]=(\d+)$")


# ═══════════════════════════════════════════════════════════════════════════
# Datamap
# ═══════════════════════════════════════════════════════════════════════════
@dataclass
class ParsedQuestion:
    qcode: str
    qtext: str
    qtype: str = "text"
    value_min: Optional[int] = None
    value_max: Optional[int] = None
    options: list[tuple[int, str]] = field(default_factory=list)
    rows: list[tuple[str, str]] = field(default_factory=list)

    @property
    def is_multi(self) -> bool:
        return bool(self.rows) and (self.value_min, self.value_max) == (0, 1)


def parse_datamap(path: str, sheet: str = "Datamap") -> list[ParsedQuestion]:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[sheet]
    out: list[ParsedQuestion] = []
    current: Optional[ParsedQuestion] = None

    for raw in ws.iter_rows(values_only=True):
        cells = [("" if c is None else clean_text(c)) for c in (list(raw) + ["", "", ""])[:3]]
        a, b, c = cells

        m = QCODE_RE.match(a) if a else None
        if m and not a.startswith(("Values:", "Open ")):
            if current:
                out.append(current)
            current = ParsedQuestion(qcode=m.group(1).strip("[]"), qtext=m.group(2).strip())
            continue

        if current is None:
            continue

        if a.startswith("Values:"):
            vm = VALUES_RE.match(a)
            if vm:
                current.value_min, current.value_max = int(vm.group(1)), int(vm.group(2))
            current.qtype = "single"
        elif a.startswith("Open numeric"):
            current.qtype = "numeric"
        elif a.startswith("Open text"):
            current.qtype = "text"
        elif b.startswith("[") and b.endswith("]"):
            current.rows.append((b.strip("[]"), c))
        elif b:
            try:
                current.options.append((int(b), c))
            except ValueError:
                pass

    if current:
        out.append(current)
    wb.close()

    for q in out:
        if q.rows and (q.value_min, q.value_max) == (0, 1):
            q.qtype = "multi"
        elif q.rows:
            q.qtype = "grid_single"
    return out


def expand_variables(questions: list[ParsedQuestion]) -> list[tuple[str, str, Optional[str]]]:
    """(field_name, qcode, item_code) for every column of the flat export."""
    variables: list[tuple[str, str, Optional[str]]] = []
    for q in questions:
        if q.rows:
            variables.extend((rc, q.qcode, rc) for rc, _ in q.rows)
        else:
            variables.append((q.qcode, q.qcode, None))
    return variables


# ═══════════════════════════════════════════════════════════════════════════
# Raw data sheet
# ═══════════════════════════════════════════════════════════════════════════
def iter_raw_records(path: str, sheet: str = "A1") -> Iterator[dict[str, Any]]:
    """Yield one dict per respondent, keyed on the export's column headers."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[sheet]
    rows = ws.iter_rows(values_only=True)
    header = [("" if h is None else str(h).strip()) for h in next(rows)]
    for r in rows:
        if all(c is None for c in r):
            continue
        yield {header[i]: r[i] for i in range(min(len(header), len(r)))}
    wb.close()


def normalise_label_cell(value: Any) -> tuple[Optional[int], Optional[str]]:
    """Turn a label-format cell into (code, label) for multi-punch columns.

    'NO TO: Gone to a bar' -> (0, 'Gone to a bar')
    'Gone to a bar'        -> (1, 'Gone to a bar')
    '' / None              -> (None, None)
    """
    if value is None:
        return None, None
    s = clean_text(value)
    if not s:
        return None, None
    if s.startswith(NO_TO):
        return 0, s[len(NO_TO):].strip()
    return 1, s


# ═══════════════════════════════════════════════════════════════════════════
# Cross-tab workbook
# ═══════════════════════════════════════════════════════════════════════════
@dataclass
class ParsedSegment:
    label: str
    letter: Optional[str]
    definition: Optional[str]
    base_n: Optional[int]
    banner_name: Optional[str] = None
    column_index: Optional[int] = None
    low_base: str = ""
    is_total: bool = False


def parse_crosstab_summary(path: str, sheet: str = "Summary") -> tuple[dict, list[ParsedSegment]]:
    """Return ({setting: value}, [segment definitions])."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[sheet]
    settings: dict[str, Any] = {}
    segments: list[ParsedSegment] = []
    mode = None

    for raw in ws.iter_rows(values_only=True):
        cells = [("" if c is None else str(c).strip()) for c in (list(raw) + [""] * 4)[:4]]
        _, b, c, d = cells
        if b == "Report Settings":
            mode = "settings"
            continue
        if b == "Segment Definitions":
            mode = "segments"
            continue
        if not b:
            continue
        if mode == "settings" and c:
            settings[b.rstrip(":")] = c
        elif mode == "segments":
            base = None
            m = BASE_RE.match(d)
            if m:
                base = int(m.group(1))
            segments.append(
                ParsedSegment(label=b, letter=None, definition=c or None, base_n=base)
            )
    wb.close()
    if "Title" not in settings:
        settings["Title"] = _first_cell(path, sheet)
    return settings, segments


def _first_cell(path: str, sheet: str) -> str:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[sheet]
    for raw in ws.iter_rows(values_only=True):
        for c in raw:
            if c:
                wb.close()
                return str(c).strip()
    wb.close()
    return ""


def parse_banner(path: str, sheet: str = "Percentages") -> list[ParsedSegment]:
    """Read the 3-row header block once; it repeats above every table."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[sheet]
    head = [list(r) for r in ws.iter_rows(min_row=1, max_row=8, values_only=True)]
    wb.close()

    group_row, seg_row, base_row = head[4], head[5], head[6]
    banner_name: Optional[str] = None
    segments: list[ParsedSegment] = []

    for idx, cell in enumerate(seg_row):
        if not cell:
            continue
        label = clean_text(cell)
        if group_row[idx]:
            banner_name = clean_text(group_row[idx])
        letter = None
        m = SEGMENT_LETTER_RE.match(label)
        if m:
            label, letter = m.group(1).strip(), m.group(2)
        base = None
        bm = BASE_RE.match(str(base_row[idx] or "").strip())
        if bm:
            base = int(bm.group(1))
        flag = ""
        nxt = str(base_row[idx + 1] or "").strip() if idx + 1 < len(base_row) else ""
        if nxt in {"*", "**"}:
            flag = nxt
        segments.append(
            ParsedSegment(
                label=label,
                letter=letter,
                definition=None,
                base_n=base,
                banner_name=banner_name if label.lower() != "total" else "Total",
                column_index=idx,
                low_base=flag,
                is_total=label.lower() == "total",
            )
        )
    return segments


def iter_crosstab_cells(
    path: str, segments: list[ParsedSegment], pct_sheet: str = "Percentages", cnt_sheet: str = "Counts"
) -> Iterator[dict[str, Any]]:
    """Walk the stacked tables and yield one dict per cell.

    Two structures appear in these sheets and they are easy to confuse:

    * A **flat table** — one stub row per list item, e.g. q1's 15 activities.

    * A **grid** — printed as a run of sub-tables, one per grid item, each with
      its own banner block and its own base. DP7 "How do you feel about each of
      the following retailers?" prints nine of them:

            DP7: How do you feel about each of the following retailers?
            Bergdorf Goodman                  <- sub-item header, no data
                              Total (A)       <- banner repeats
            Total             N=16            <- this item's own base
            Very positive     0.5625          <- stub rows are the scale points
            ...
            Bloomingdale's
            Total             N=22
            ...

      So the scale labels repeat once per retailer. Keyed on the stub alone
      they collide and 8 of every 9 rows are lost — which is exactly what
      happened before this was handled. `item_label` disambiguates them, and
      the per-item `N=` is captured as that sub-table's base.

    Percentages and Counts share identical geometry, so they are read in
    lock-step and merged into one record per cell.
    """
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    pct_rows = list(wb[pct_sheet].iter_rows(values_only=True))
    cnt_rows = list(wb[cnt_sheet].iter_rows(values_only=True))
    wb.close()

    data_columns = [s.column_index for s in segments if s.column_index is not None]
    current_q: Optional[tuple[str, str]] = None
    current_item: Optional[str] = None
    item_base: Optional[int] = None

    for i, prow in enumerate(pct_rows):
        stub = "" if not prow or prow[0] is None else clean_text(prow[0])
        if not stub:
            continue

        # a new question table
        m = QCODE_RE.match(stub)
        if m and len(prow) > 1 and all(c is None for c in prow[1:6]):
            current_q = (m.group(1), m.group(2).strip())
            current_item, item_base = None, None
            continue
        if current_q is None:
            continue

        row_has_data = any(
            j < len(prow) and prow[j] is not None for j in data_columns
        )

        # the base line of a table or sub-table: "Total | N=16"
        if stub.lower() == "total":
            first = next((prow[j] for j in data_columns if j < len(prow) and prow[j] is not None), None)
            bm = BASE_RE.match(str(first or "").strip())
            item_base = int(bm.group(1)) if bm else None
            continue

        # a sub-item header inside a grid: label in column A, no data beside it
        if not row_has_data:
            current_item = stub
            item_base = None
            continue

        crow = cnt_rows[i] if i < len(cnt_rows) else [None] * len(prow)
        kind = _stub_kind(stub)
        for seg in segments:
            j = seg.column_index
            if j is None or j >= len(prow):
                continue
            pct, cnt = prow[j], (crow[j] if j < len(crow) else None)
            if pct is None and cnt is None:
                continue
            sig = prow[j + 1] if j + 1 < len(prow) else None
            pct_v, cnt_v = _as_float(pct), _as_int(cnt)
            yield {
                "qcode": current_q[0],
                "qtext": current_q[1],
                "item_label": current_item,
                "stub_label": stub,
                "stub_type": kind,
                "seg_label": seg.label,
                "seg_letter": seg.letter,
                "pct": pct_v,
                "count_n": cnt_v,
                # The segment's size (404 for Total) — what Forsta prints in the header.
                "segment_base_n": seg.base_n,
                # The real denominator behind the percentage. Forsta's
                # "Total Answering" base is the number ROUTED INTO the question,
                # not the segment size: DP2 divides by 222, BN2 by 133, GP8 by 71.
                # count / pct recovers it exactly; the sub-table's own N= is the
                # fallback for a 0% cell inside a grid.
                "answer_base_n": _answer_base(cnt_v, pct_v) or (item_base if seg.is_total else None),
                "sig_letters": str(sig).strip() if sig and str(sig).strip() not in {"*", "**"} else None,
            }


def _answer_base(count_n: Optional[int], pct: Optional[float]) -> Optional[int]:
    """Recover the denominator Forsta divided by: base = count / pct.

    Verified against the 09/21/26 export, exact in every case:
        DP2  16 / 0.07207207 = 222   (department-store buyers)
        DJ3  .. / ..          = 186   (would consider lab-grown)
        BN2  46 / 0.34586466 = 133   (BNPL users)
        GP8  16 / 0.22535211 =  71   (GLP-1 users)
        D15  .. / ..          = 260   (cut spending on gas)
    Grid rows carry their own base — DP7 ranges from 16 to 107 across
    retailers, because only shoppers of a retailer rate it.

    Returns None when the cell is 0% and the base cannot be recovered.
    Deliberately NOT falling back to the segment size: substituting 404 for an
    unknown denominator is the exact error this column exists to prevent. The
    caller has the segment size on csi_segment if it needs a display fallback.
    """
    if count_n is None or not pct:
        return None
    base = count_n / pct
    return int(round(base)) if 0 < base < 10_000_000 else None


def _stub_kind(stub: str) -> str:
    low = stub.lower()
    if low == "count":
        return "count"
    if low.startswith("mean"):
        return "mean"
    if low.startswith("net"):
        return "net"
    if low.startswith("total"):
        return "base"
    return "item"


def _as_float(v: Any) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _as_int(v: Any) -> Optional[int]:
    try:
        return int(round(float(v)))
    except (TypeError, ValueError):
        return None
