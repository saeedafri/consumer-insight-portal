"""Excel and PowerPoint versions of any table a screen can download as CSV: the same name, header, rows and notes
(question wording, wave, bases, source), so the three formats can never disagree; and a book of tables (a databank's
every tab, a survey's every section, a tracker's every week) as one Excel workbook of tabs. Called by api/main.py
export (the Export button, frontend/src/csv.ts) and api/team.py (a board's pins and deck). Rendered here, not in the
browser, so the files are real .xlsx (typed numbers, the Coresight house style) and .pptx (a native, editable chart in
the Coresight palette).
"""
from __future__ import annotations

import io
import os
import re
import textwrap
from datetime import date
from pathlib import Path

MAX_ROWS, MAX_COLUMNS = 2000, 200   # 200 columns: a tracker's every week for almost four years
MAX_SHEETS, MAX_BOOK_ROWS = 40, 10_000   # the largest survey: 34 sections, 977 rows (27 Nov 2026)
RED, INK, GREY, GRID = "D62E2F", "2D2A29", "6B6A68", "D9D9D9"
BLUES = ["1F5C99", "4A86C5", "8DB8E2", "C2DAF0"]


def check(spec: dict, limit: int = MAX_ROWS) -> dict:
    """The table a screen sent: header (strings), rows (strings, numbers, empty), notes (strings), and how its numbers
    read in Excel: unit "%" (every number a percentage) and plain (the rows that are not: people asked, a net score,
    by index). Bounded."""
    header = [str(h)[:120] for h in spec.get("header", [])][:MAX_COLUMNS]
    rows = [[c if isinstance(c, (int, float)) or c is None else str(c)[:500] for c in r[:MAX_COLUMNS]] for r in spec.get("rows", [])][:limit]
    notes = [str(n)[:600] for n in spec.get("notes", [])][:12]
    if not header:
        raise ValueError("nothing to export")
    rows = rows or [["No rows match the screen's filters"] + [None] * (len(header) - 1)]   # an empty table still downloads
    plain = sorted({i for i in spec.get("plain") or [] if isinstance(i, int)})
    return {"name": file_name(spec.get("name")), "header": header, "rows": rows, "notes": notes,
            **({"unit": "%"} if spec.get("unit") == "%" else {}), **({"plain": plain} if plain else {})}


def check_book(spec: dict) -> dict:
    """A workbook a screen sent (every tab of a databank, every section of a survey): its name and its tables, each a
    tab under its own title. One too big is refused whole, never cut, so a download never drops weeks or answers
    unseen; the bounds keep one download from holding the single API worker for long."""
    sheets = spec.get("sheets")
    if not isinstance(sheets, list) or not sheets:
        raise ValueError("nothing to export")
    if (len(sheets) > MAX_SHEETS or sum(len(s.get("rows") or []) for s in sheets) > MAX_BOOK_ROWS
            or any(len(s.get("header") or []) > MAX_COLUMNS for s in sheets)):
        raise ValueError(f"too big for one workbook: at most {MAX_SHEETS} tabs, {MAX_BOOK_ROWS:,} rows and {MAX_COLUMNS} columns")
    return {"name": file_name(spec.get("name")),
            "sheets": [{**check(sheet, MAX_BOOK_ROWS), "title": str(sheet.get("title") or f"Sheet {k}")} for k, sheet in enumerate(sheets, 1)]}


def file_name(name) -> str:
    """A download's file name: letters, digits, dots and dashes only, at most 80 characters."""
    return re.sub(r"[^\w.-]+", "-", str(name or "cip-export"))[:80]


def literal(value):
    """Text that Excel would run as a formula (=, +, -, @) stays text."""
    return f"'{value}" if isinstance(value, str) and value[:1] in ("=", "+", "-", "@") else value


def build_xlsx(spec: dict) -> bytes:
    """The table as a workbook of one tab, Data; a book (check_book) as one tab per table, in the screen's order."""
    from openpyxl import Workbook   # imported on use: openpyxl, python-pptx and numpy cost each API worker ~25 MB
    book = Workbook()
    book.remove(book.active)
    taken: set[str] = set()
    for table in spec.get("sheets") or [spec]:
        write_sheet(book.create_sheet(tab_title(table.get("title", "Data"), taken)), table)
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()


def tab_title(title: str, taken: set[str]) -> str:
    """An Excel tab name: at most 31 characters, cut at a word, none of [ ] : * ? / \\, and never another tab's (Excel
    refuses all three)."""
    clean = re.sub(r"[\[\]:*?/\\]", " ", title)
    first = textwrap.shorten(clean, 31, placeholder="") or clean.strip()[:31] or "Data"
    name, k = first, 2
    while name.lower() in taken:
        name, k = f"{first[:26]} ({k})", k + 1
    taken.add(name.lower())
    return name


def write_sheet(sheet, table: dict):
    """One table in the house style (the business team, 27 Nov 2026): its title in bold and its notes in grey above,
    the header in Coresight red with white bold text, then the rows. A number is a percentage (61.0%) in a column whose
    header says % or anywhere in a "%" table, except in a plain row (people asked 1,234, a net score 12.3); a 2026-11-23 is a date
    (Nov 23, 2026). Columns as wide as their text (long text wraps), the header and first column stay in view, and
    the header has a filter."""
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    for k, note in enumerate(table["notes"], 1):
        sheet.cell(k, 1, literal(note)).font = Font(bold=True, size=13, color=INK) if k == 1 else Font(size=9, color=GREY)
    top = len(table["notes"]) + 2   # a blank row between the notes and the header
    header = table["header"]
    widths = [len(str(h)) for h in header] + [0] * (max(map(len, table["rows"])) - len(header))
    for j, heading in enumerate(header, 1):
        cell = sheet.cell(top, j, read_week(heading) or literal(heading))   # a week's date as a date Excel can sort
        cell.font, cell.fill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor=RED)
        cell.alignment = Alignment(wrap_text=True, vertical="center", horizontal="left" if j == 1 else "right")
    plain, percent = set(table.get("plain", [])), table.get("unit") == "%"
    for i, row in enumerate(table["rows"]):
        for j, value in enumerate(row):
            cell = sheet.cell(top + 1 + i, j + 1, read_week(value) or literal(value))
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                share = i not in plain and (percent or j < len(header) and "%" in header[j])
                cell.number_format = '0.0"%"' if share else "#,##0" if isinstance(value, int) else "#,##0.0"
            widths[j] = max(widths[j], len(f"{value:,.1f}") + 1 if isinstance(value, (int, float)) else len(str(value or "")))
    for j, width in enumerate(widths, 1):
        shown = min(60 if j <= 2 else 40, max(10, width + 2))
        sheet.column_dimensions[get_column_letter(j)].width = shown
        for (cell,) in sheet.iter_rows(min_row=top, min_col=j, max_col=j):
            if isinstance(cell.value, date):
                cell.number_format = "mmm d, yyyy"
            elif cell.row > top and isinstance(cell.value, str) and len(cell.value) > shown:
                cell.alignment = Alignment(wrap_text=True, vertical="top")
    sheet.freeze_panes = sheet.cell(top + 1, 2)
    sheet.auto_filter.ref = f"A{top}:{get_column_letter(len(widths))}{top + len(table['rows'])}"


# The Coresight logo on a deck's cover: in the server image it sits with the built website (CIP_WEB_DIR), on a
# developer's machine in the frontend's public folder. Was web/public/…, a folder that no longer exists, so decks
# went out without it.
LOGO = next((p for p in (Path(os.environ.get("CIP_WEB_DIR", "/srv/cip/web")) / "coresight-logo.png",
                         Path(__file__).resolve().parents[1] / "frontend" / "public" / "coresight-logo.png") if p.exists()),
            Path("coresight-logo.png"))


def build_pptx(spec: dict) -> bytes:
    """One 16:9 slide of one table (add_slide)."""
    deck = new_deck()
    add_slide(deck, spec)
    return save(deck)


def deck_pptx(title: str, subtitle: str, specs: list[dict]) -> bytes:
    """A branded deck: a cover (logo, title, who and when), then one slide per table, numbered, each with its own
    wave, bases and source. A board downloads this way (api/team.py)."""
    from pptx.dml.color import RGBColor
    from pptx.util import Inches, Pt
    deck = new_deck()
    cover = deck.slides.add_slide(deck.slide_layouts[6])
    band = cover.shapes.add_shape(1, 0, 0, deck.slide_width, Inches(0.25))   # 1 = rectangle: the brand-red top band
    band.fill.solid()
    band.fill.fore_color.rgb = RGBColor.from_string(RED)
    band.line.fill.background()
    if LOGO.exists():
        cover.shapes.add_picture(str(LOGO), Inches(0.8), Inches(0.9), height=Inches(0.7))
    for text, top, size, bold, colour in ((title, 2.7, 36, True, INK), (subtitle, 3.9, 16, False, GREY),
                                          (f"{len(specs)} slides · Coresight Research US Consumer Survey", 6.6, 11, False, GREY)):
        frame = cover.shapes.add_textbox(Inches(0.8), Inches(top), Inches(11.7), Inches(1.1)).text_frame
        frame.word_wrap = True
        frame.text = text
        run = frame.paragraphs[0].runs[0]
        run.font.size, run.font.bold, run.font.color.rgb = Pt(size), bold, RGBColor.from_string(colour)
    for number, spec in enumerate(specs, 2):
        slide = add_slide(deck, spec)
        mark = slide.shapes.add_textbox(Inches(11.3), Inches(7.05), Inches(1.6), Inches(0.35)).text_frame
        mark.text = f"Coresight Research · {number}"
        mark.paragraphs[0].runs[0].font.size, mark.paragraphs[0].runs[0].font.color.rgb = Pt(8), RGBColor.from_string(GREY)
    return save(deck)


def new_deck():
    from pptx import Presentation
    from pptx.util import Inches
    deck = Presentation()
    deck.slide_width, deck.slide_height = Inches(13.333), Inches(7.5)
    return deck


def save(deck) -> bytes:
    out = io.BytesIO()
    deck.save(out)
    return out.getvalue()


def read_week(cell) -> date | None:
    """The date a row's first cell names (2026-11-23), or None: rows that are all dates are a trend's weeks."""
    try:
        return date.fromisoformat(cell) if isinstance(cell, str) and len(cell) == 10 else None
    except ValueError:   # 2026-13-01 is no week: the table is drawn as bars
        return None


def add_slide(deck, spec: dict):
    """The question as title, a bar chart of the % columns (Total in red, the rest in blues), the first rows as a table
    when there is nothing to chart, and the notes (wave, bases, source) as the footer. A trend (rows that are weeks) is a
    line of every week, labelled once at its end: as bars it showed its first 16 weeks (the research team, 25 Nov 2026)."""
    from pptx.chart.data import CategoryChartData
    from pptx.dml.color import RGBColor
    from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION, XL_MARKER_STYLE
    from pptx.util import Inches, Pt
    slide = deck.slides.add_slide(deck.slide_layouts[6])
    title = slide.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(12.3), Inches(1.0)).text_frame
    title.word_wrap = True
    title.text = spec["notes"][0] if spec["notes"] else spec["name"]
    title.paragraphs[0].runs[0].font.size, title.paragraphs[0].runs[0].font.bold = Pt(20), True
    title.paragraphs[0].runs[0].font.color.rgb = RGBColor.from_string(INK)
    numeric = [i for i, h in enumerate(spec["header"]) if i and all(isinstance(r[i], (int, float)) or r[i] in (None, "") for r in spec["rows"])
               and any(isinstance(r[i], (int, float)) for r in spec["rows"])]
    shown = [i for i in numeric if "%" in spec["header"][i]] or numeric
    weekly = bool(shown) and all(read_week(r[0]) for r in spec["rows"])
    rows = sorted(spec["rows"], key=lambda r: r[0]) if weekly else spec["rows"][:16]
    if shown:
        data = CategoryChartData()
        data.categories = [read_week(r[0]) for r in rows] if weekly else [str(r[0])[:60] for r in rows]
        for i in shown[:6]:
            data.add_series(spec["header"][i], [r[i] if isinstance(r[i], (int, float)) else None for r in rows])
        kind = XL_CHART_TYPE.LINE if weekly else XL_CHART_TYPE.BAR_CLUSTERED
        frame = slide.shapes.add_chart(kind, Inches(0.5), Inches(1.4), Inches(12.3), Inches(5.0), data)
        chart = frame.chart
        chart.has_legend = len(shown) > 1
        if chart.has_legend:
            chart.legend.position, chart.legend.include_in_layout = XL_LEGEND_POSITION.TOP, False
        chart.category_axis.tick_labels.font.size = Pt(10)
        # a trend reads against faint horizontal lines and a % axis, as on screen (the research team, 26 Nov 2026)
        chart.value_axis.has_major_gridlines = weekly
        if weekly:
            chart.value_axis.major_gridlines.format.line.color.rgb = RGBColor.from_string(GRID)
        percent_sign = '"%"' if "%" in spec["header"][shown[0]] else ""
        if percent_sign:
            chart.value_axis.tick_labels.number_format, chart.value_axis.tick_labels.number_format_is_linked = f"0{percent_sign}", False
        chart.value_axis.tick_labels.font.size = Pt(9)
        plot = chart.plots[0]
        for k, series in enumerate(plot.series):
            colour = RGBColor.from_string(RED if k == 0 else BLUES[(k - 1) % len(BLUES)])
            if not weekly:
                series.format.fill.solid()
                series.format.fill.fore_color.rgb = colour
                continue
            series.smooth, series.marker.style = False, XL_MARKER_STYLE.NONE
            series.format.line.color.rgb, series.format.line.width = colour, Pt(2)
            # the latest figure once, at the line's end, not on every week
            values = [r[shown[k]] for r in rows]
            end = max((j for j, v in enumerate(values) if isinstance(v, (int, float))), default=None)
            if end is not None:
                label = series.points[end].data_label
                label.position, label.text_frame.text = XL_LABEL_POSITION.RIGHT, f"{values[end]:.1f}%"
                label.font.size, label.font.bold, label.font.color.rgb = Pt(10), True, colour
        if weekly:
            chart.category_axis.tick_labels.number_format, chart.category_axis.tick_labels.number_format_is_linked = "mmm yyyy", False
        else:
            chart.category_axis.reverse_order = True
            plot.has_data_labels = True
            plot.data_labels.font.size, plot.data_labels.number_format, plot.data_labels.number_format_is_linked = Pt(9), f"0.0{percent_sign}", False
    else:   # no numbers to chart: the table itself
        table = slide.shapes.add_table(len(rows) + 1, len(spec["header"]), Inches(0.5), Inches(1.4), Inches(12.3), Inches(0.3) * (len(rows) + 1)).table
        for j, h in enumerate(spec["header"]):
            table.cell(0, j).text = h
        for i, r in enumerate(rows, 1):
            for j, c in enumerate(r):
                table.cell(i, j).text = "" if c is None else str(c)
    foot = slide.shapes.add_textbox(Inches(0.5), Inches(6.55), Inches(12.3), Inches(0.8)).text_frame
    foot.word_wrap = True
    lines = spec["notes"][1:] + ([f"First {len(rows)} of {len(spec['rows'])} rows; the Excel export has all"] if len(spec["rows"]) > len(rows) else [])
    foot.text = " · ".join(lines)[:900] or "Source: Coresight Research US Consumer Survey"
    for run in foot.paragraphs[0].runs:
        run.font.size, run.font.color.rgb = Pt(9), RGBColor.from_string(GREY)
    return slide
