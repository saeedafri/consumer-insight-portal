"""Excel and PowerPoint versions of any table a screen can download as CSV: the same name, header, rows and notes
(question wording, wave, bases, source), so the three formats can never disagree. Rendered here, not in the browser,
so the files are real .xlsx (typed numbers, frozen header) and .pptx (a native, editable chart in the Coresight palette).
"""
from __future__ import annotations

import io
import re

MAX_ROWS = 2000
RED, INK, GREY = "D62E2F", "2D2A29", "6B6A68"
BLUES = ["1F5C99", "4A86C5", "8DB8E2", "C2DAF0"]


def check(spec: dict) -> dict:
    """The table a screen sent: header (strings), rows (strings, numbers, empty), notes (strings). Bounded."""
    header = [str(h)[:120] for h in spec.get("header", [])][:60]
    rows = [[c if isinstance(c, (int, float)) or c is None else str(c)[:500] for c in r[:60]] for r in spec.get("rows", [])][:MAX_ROWS]
    notes = [str(n)[:600] for n in spec.get("notes", [])][:12]
    if not header:
        raise ValueError("nothing to export")
    rows = rows or [["No rows match the screen's filters"] + [None] * (len(header) - 1)]   # an empty table still downloads
    return {"name": re.sub(r"[^\w.-]+", "-", str(spec.get("name", "cip-export")))[:80], "header": header, "rows": rows, "notes": notes}


def literal(value):
    """Text that Excel would run as a formula (=, +, -, @) stays text."""
    return f"'{value}" if isinstance(value, str) and value[:1] in ("=", "+", "-", "@") else value


def xlsx(spec: dict) -> bytes:
    from openpyxl import Workbook   # imported on use: openpyxl, python-pptx and numpy cost each API worker ~25 MB
    from openpyxl.styles import Font, PatternFill
    book = Workbook()
    sheet = book.active
    sheet.title = "Data"
    for note in spec["notes"]:
        sheet.append([literal(note)])
    sheet.append([])
    top = len(spec["notes"]) + 2
    sheet.append(spec["header"])
    for cell in sheet[top]:
        cell.font, cell.fill = Font(bold=True, color="FAFAFA"), PatternFill("solid", fgColor="2D2A29")
    for row in spec["rows"]:
        sheet.append([literal(c) for c in row])
    sheet.freeze_panes = sheet.cell(top + 1, 2)
    sheet.column_dimensions["A"].width = min(60, max(14, max(len(str(r[0] or "")) for r in spec["rows"]) + 2))
    if spec["notes"]:
        sheet["A1"].font = Font(bold=True, size=12)
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()


def pptx(spec: dict) -> bytes:
    """One 16:9 slide: the question as title, a bar chart of the % columns (Total in red, the rest in blues), the
    first rows as a table when they fit, and the notes (wave, bases, source) as the footer."""
    from pptx import Presentation
    from pptx.chart.data import CategoryChartData
    from pptx.dml.color import RGBColor
    from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
    from pptx.util import Inches, Pt
    deck = Presentation()
    deck.slide_width, deck.slide_height = Inches(13.333), Inches(7.5)
    slide = deck.slides.add_slide(deck.slide_layouts[6])
    title = slide.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(12.3), Inches(1.0)).text_frame
    title.word_wrap = True
    title.text = spec["notes"][0] if spec["notes"] else spec["name"]
    title.paragraphs[0].runs[0].font.size, title.paragraphs[0].runs[0].font.bold = Pt(20), True
    title.paragraphs[0].runs[0].font.color.rgb = RGBColor.from_string(INK)
    numeric = [i for i, h in enumerate(spec["header"]) if i and all(isinstance(r[i], (int, float)) or r[i] in (None, "") for r in spec["rows"])
               and any(isinstance(r[i], (int, float)) for r in spec["rows"])]
    shown = [i for i in numeric if "%" in spec["header"][i]] or numeric
    rows = spec["rows"][:16]
    if shown:
        data = CategoryChartData()
        data.categories = [str(r[0])[:60] for r in rows]
        for i in shown[:6]:
            data.add_series(spec["header"][i], [r[i] if isinstance(r[i], (int, float)) else None for r in rows])
        frame = slide.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(0.5), Inches(1.4), Inches(12.3), Inches(5.0), data)
        chart = frame.chart
        chart.has_legend = len(shown) > 1
        if chart.has_legend:
            chart.legend.position, chart.legend.include_in_layout = XL_LEGEND_POSITION.TOP, False
        chart.category_axis.reverse_order = True
        chart.category_axis.tick_labels.font.size = Pt(10)
        chart.value_axis.has_major_gridlines = False
        chart.value_axis.tick_labels.font.size = Pt(9)
        plot = chart.plots[0]
        plot.has_data_labels = True
        plot.data_labels.font.size, plot.data_labels.number_format, plot.data_labels.number_format_is_linked = Pt(9), '0.0', False
        for k, series in enumerate(plot.series):
            series.format.fill.solid()
            series.format.fill.fore_color.rgb = RGBColor.from_string(RED if k == 0 else BLUES[(k - 1) % len(BLUES)])
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
    out = io.BytesIO()
    deck.save(out)
    return out.getvalue()
