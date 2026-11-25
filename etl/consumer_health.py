"""The Consumer Health dataset: the data science team's respondent workbook, kept up to date by CIP every week.

What it is: "Consumer Health — Master Raw Respondent Dataset", which the data science team built by hand from the weekly
raw exports. One row per US weekly respondent, 73 columns: dates, the source trail, pseudonymised IDs, quality flags,
demographics, the 0/1 answers to "Which, if any, of these have you done in the past two weeks?", and counts, pairs and
patterns derived from them. One sheet per year, plus Read Me, Source QA and Data Dictionary.

How it stays up to date: their workbook (to 10 Aug 2026) is the history, loaded once into cip_dataset_history
(sql/011_dataset_history.sql) and never changed here. Each published US weekly wave after its last week becomes rows
the same way, from CIP's own respondents (cip_respondent, cip_answer), and the whole workbook is written again in their
format: the same sheets, columns, widths, colours, filters and highlights.

Who calls it:
  etl/publish.py write_views()   each publish → api/v1/datasets/Consumer_Health_..._2023_<year>.xlsx
  api/main.py dataset()          GET /api/v1/datasets/consumer-health sends it to those given "datasets" (config/access.yml)
  python -m etl.consumer_health --history <their workbook.xlsx>   once, and again when they hand over a new copy
Rules: config/consumer_health.yml. Checked by tests/test_consumer_health.py.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import logging
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

import yaml
from openpyxl import Workbook, load_workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from sqlalchemy import bindparam, inspect, text

from etl.harmonise import normalise_text
from etl.weekly_report import read_waves
from shared.core.database import apply_sql, get_engine

log = logging.getLogger("cip.consumer_health")
CONFIG = Path(__file__).resolve().parents[1] / "config/consumer_health.yml"
TABLE = Path(__file__).resolve().parents[1] / "sql/011_dataset_history.sql"
FOLDER = "api/v1/datasets"
NAME = "Consumer_Health_Raw_Respondent_Data_Chronological_{first}_{last}.xlsx"

# The team's look, read from their workbook's styles.xml (25 Nov 2026): Calibri, bold headers on colour
EDGE = Side(style="thin", color="FFD9D9D9")
BOLD = {"name": "Calibri", "family": 2, "scheme": "minor", "b": True}
HEADER = {"font": Font(**BOLD, sz=11, color="FFFFFFFF"), "border": Border(left=EDGE, right=EDGE, top=EDGE, bottom=EDGE),
          "alignment": Alignment(horizontal="center", vertical="center", wrap_text=True)}
BLUE, GREEN, PURPLE = (PatternFill("solid", fgColor=c) for c in ("FF4472C4", "FF70AD47", "FF8064A2"))
TITLE = {"font": Font(**BOLD, sz=16, color="FFFFFFFF"), "fill": PatternFill("solid", fgColor="FF17365D"),
         "alignment": Alignment(vertical="center")}
LABEL = {"font": Font(**BOLD, sz=11, color="FF17365D"), "fill": PatternFill("solid", fgColor="FFD9EAF7")}
VALUE = {"alignment": Alignment(vertical="top", wrap_text=True)}
FLAG = {"font": Font(color="FF9C0006"), "fill": PatternFill(bgColor="FFFCE4D6")}   # a cell worth checking, in red
# column widths in characters, (first column, last column, characters); Excel adds 0.7109375 of padding to each
DATA_WIDTHS = [(1, 1, 15), (2, 4, 12), (5, 5, 18), (6, 8, 22), (9, 12, 15), (13, 13, 52), (14, 18, 18), (19, 26, 14),
               (27, 33, 20), (34, 48, 16), (49, 51, 20), (52, 73, 17)]
README_WIDTHS = [(1, 1, 27), (2, 2, 72), (3, 3, 3), (4, 4, 22), (5, 5, 52), (6, 7, 18), (8, 8, 40)]
QA_WIDTHS = [(1, 4, 16), (5, 5, 58), (6, 15, 18)]
DICTIONARY_WIDTHS = [(1, 1, 32), (2, 2, 24), (3, 3, 22), (4, 4, 82)]
README_HEIGHTS = {1: 27.95, 3: 15.95, 9: 15.95, 10: 15.95, 13: 32.1, 14: 15.95, 15: 32.1, 16: 15.95, 17: 15.95, 18: 15.95, 19: 32.1}


@lru_cache(maxsize=1)
def settings() -> dict:
    """config/consumer_health.yml, read once."""
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


def monday(day: str) -> date:
    """The Monday of a date's week: a wave and the team's row of it share it, whichever day each names."""
    when = date.fromisoformat(str(day)[:10])
    return when - timedelta(days=when.weekday())


def age_band(answer: str | None) -> str | None:
    """An age answer in the team's bands: one of their bands ("30 - 44", "over 60") as it is, else by its first number
    ("54" → "45 - 60", "70 or more" → "over 60", "Under 18" → "18 - 29", as the team counts the few who say so); one
    without a number ("prefer not to say") as it is."""
    bands, oldest = settings()["age_bands"], settings()["oldest_band"]
    found = re.search(r"\d+", answer or "")
    if answer in bands or answer == oldest or not found:
        return answer
    return next((band for band, last in bands.items() if int(found.group()) <= last), oldest)


def read_people(conn, survey_id: int) -> tuple[list[dict], set[str]]:
    """One wave's qualified respondents (record number, Forsta ID, completion and start times, each demographic's
    answer, each activity 1 or 0, keyed by its answer label) and the activities the wave asked."""
    rules = settings()
    wanted = {normalise_text(rules["activities"]["question"]): "activities"}
    wanted.update({normalise_text(w): column for column, wordings in rules["demographics"].items() for w in wordings})
    questions = {qid: wanted[normalise_text(wording)] for qid, wording in conn.execute(
        text("SELECT question_id, qtext FROM cip_question WHERE survey_id = :s"), {"s": survey_id})
        if normalise_text(wording) in wanted}
    people = {r.respondent_id: {"record": r.record_no, "uuid": r.forsta_uuid, "done": datetime.fromisoformat(str(r.completed_at))}
              for r in conn.execute(text(
        "SELECT respondent_id, record_no, forsta_uuid, completed_at FROM cip_respondent WHERE survey_id = :s AND is_qualified = 1"),
        {"s": survey_id})}
    asked = set()
    for a in conn.execute(text(
            "SELECT a.respondent_id, f.field_name, f.question_id, i.item_label, a.value_code, a.value_text, o.value_label"
            " FROM cip_answer a JOIN cip_field f ON f.field_id = a.field_id LEFT JOIN cip_item i ON i.item_id = f.item_id"
            " LEFT JOIN cip_option o ON o.question_id = f.question_id AND o.value_code = a.value_code"
            " WHERE a.survey_id = :s AND (f.field_name = 'start_date' OR f.question_id IN :q)")
            .bindparams(bindparam("q", expanding=True)), {"s": survey_id, "q": list(questions) or [-1]}):
        person = people.get(a.respondent_id)
        if person is None:
            continue
        if a.field_name == "start_date":
            person["start"] = a.value_text
        elif questions[a.question_id] == "activities":
            asked.add(a.item_label)
            person[a.item_label] = int(a.value_code == 1)
        else:
            person[questions[a.question_id]] = a.value_label
    return list(people.values()), asked


def wave_rows(wave: dict, people: list[dict], asked: set[str]) -> list[dict]:
    """One CIP wave's respondents as the team's rows, ordered and keyed as theirs are (by response time)."""
    rules = settings()
    activities = rules["activities"]
    done = Counter(p["done"].date() for p in people)
    day = min(done, key=lambda d: (-done[d], d))   # the date most people answered on: the team's Survey_Wave_Date
    label = date.fromisoformat(wave["wave_date"])
    iso_year, iso_week, _ = day.isocalendar()
    rows = []
    # Source_Row: the row each has in Forsta's line-by-line export (qualified people by record number, row 1 the header)
    for row_number, p in enumerate(sorted(people, key=lambda p: p["record"]), start=2):
        start = datetime.strptime(p["start"], "%m/%d/%Y %H:%M") if p.get("start") else None
        row = {
            "Survey_Wave_Date": str(day), "Survey_Year": day.year, "Survey_Month": f"{day:%Y-%m}-01", "File_Label_Date": str(label),
            "Response_Recorded_Date": str(p["done"].date()), "Response_Recorded_Datetime": f"{p['done']:%Y-%m-%d %H:%M:%S}",
            "Response_Start_Datetime": f"{start:%Y-%m-%d %H:%M:%S}" if start else None, "Response_End_Datetime": None,
            "Response_Date_vs_Wave_Days": (p["done"].date() - day).days, "Response_Date_Matches_Wave": int(p["done"].date() == day),
            "Survey_Date": str(day), "Week_ID": f"{iso_year}-W{iso_week:02d}", "Source_File": wave["source_ref"],
            "Source_Sheet": rules["source_sheet"], "Source_Row": row_number,
            "Response_Hash": hashlib.sha256(str(p["uuid"]).encode()).hexdigest()[:18],   # as the team pseudonymised it
            "Panelist_Hash": None, "Panelist_Weeks_Observed": 1, "Repeat_Panelist_Flag": 0, "Completed_Flag": 1, "Progress": 100,
            "Recaptcha_Score": None, "Duplicate_Flag": 0, "Duplicate_Score": None, "Fraud_Score": None,   # Forsta gives none
            **{column: p.get(column) for column in rules["demographics"]},
            **{column: p.get(a["answer"], 0) for column, a in activities["original"].items()},
            **{column: p.get(answer, 0) if answer in asked else None for column, answer in activities["added"].items()},
            "None_Selected": p.get(activities["none"], 0),
        }
        row["Age_Group"] = age_band(row["Age_Group"])
        rows.append(derive(row))
    rows.sort(key=lambda r: (r["Response_Recorded_Datetime"], r["Source_Row"]))   # a minute's ties in export order
    for n, row in enumerate(rows, start=1):
        row["Respondent_Key"] = f"{day}-R{n:04d}"
    return rows


def derive(row: dict) -> dict:
    """The columns the team derives from the answers (their Data Dictionary), by their rules (config/consumer_health.yml):
    each rule reproduced all 62,109 rows of their workbook. An added activity left blank was not asked that week."""
    rules = settings()
    original, high = list(rules["activities"]["original"]), rules["high_activity"]
    added = sum(row[c] is not None for c in rules["activities"]["added"])
    chosen = {column: row[column] or 0 for column in original + list(rules["activities"]["added"])}
    count, count_all = sum(chosen[c] for c in original), sum(chosen.values())
    missing, contradiction = int(count_all == 0 and not row["None_Selected"]), int(count_all > 0 and row["None_Selected"] == 1)
    return {**row, "Q1_Activities_Available": len(original) + added,
            "Activity_Question_Version": f"{len(original) + added} activities + None",
            "Activity_Count": count, "Activity_Count_All_Available": count_all, "Any_Activity": int(count_all > 0),
            "Q1_Missing_Flag": missing, "Q1_Contradiction_Flag": contradiction,
            "Core_Valid_Flag": int(row["Completed_Flag"] == 1 and not missing and not contradiction),
            "Activity_Count_Band": f"{high}+" if count >= high else str(count),
            **{name: None if all(row[c] is None for c in columns) else sum(chosen[c] for c in columns)   # not asked: blank
               for name, columns in rules["counts"].items()},
            **{name: int(all(any(chosen[c] for c in group) for group in groups)) for name, groups in rules["pairs"].items()},
            "High_Activity_5Plus": int(count >= high),
            "Activity_Pattern_Bitmask": sum(chosen[c] << bit for bit, c in enumerate(original)),
            "Activity_Pattern_Code": "+".join(a["code"] for c, a in rules["activities"]["original"].items() if chosen[c]) or None}


def qa_line(wave: dict, rows: list[dict]) -> dict:
    """The wave's line in Source QA: where its rows came from and how many passed each check."""
    day, label = rows[0]["Survey_Wave_Date"], rows[0]["File_Label_Date"]
    recorded = [r["Response_Recorded_Date"] for r in rows]
    return {"Survey_Wave_Date": day, "Survey_Year": rows[0]["Survey_Year"], "File_Label_Date": label,
            "File_Date_Diff_Days": (date.fromisoformat(label) - date.fromisoformat(day)).days, "Source_File": wave["source_ref"],
            "Source_Sheet": settings()["source_sheet"], "Schema": wave["platform"].capitalize(), "Respondents": len(rows),
            "Completed": sum(r["Completed_Flag"] for r in rows), "Core_Valid": sum(r["Core_Valid_Flag"] for r in rows),
            "Q1_Missing": sum(r["Q1_Missing_Flag"] for r in rows), "Q1_Contradiction": sum(r["Q1_Contradiction_Flag"] for r in rows),
            "Q1_Activities_Available": rows[0]["Q1_Activities_Available"], "Recorded_Date_Min": min(recorded),
            "Recorded_Date_Max": max(recorded)}


def load_history(path: Path) -> int:
    """The team's workbook → cip_dataset_history, replacing the copy before: the year sheets' rows under one header and
    the other three sheets as their cells say, written back unchanged by each publish. Returns the rows kept."""
    book = load_workbook(path, read_only=True)
    sheet = lambda ws: [list(r) for r in ws.iter_rows(values_only=True)]   # noqa: E731
    years = [sheet(ws) for ws in book.worksheets if ws.title.isdigit()]
    payload = {"header": years[0][0], "rows": [r for part in years for r in part[1:] if any(v is not None for v in r)],
               "source_qa": sheet(book["Source QA"]), "dictionary": sheet(book["Data Dictionary"]), "read_me": sheet(book["Read Me"])}
    engine = get_engine("etl")
    if "cip_dataset_history" not in inspect(engine).get_table_names():
        apply_sql(TABLE, engine)
    with engine.begin() as conn:
        conn.execute(text("REPLACE INTO cip_dataset_history (dataset, loaded_at, source, payload) VALUES ('consumer_health', :t, :n, :p)"),
                     {"t": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), "n": path.name[:255],
                      "p": gzip.compress(json.dumps(payload, separators=(",", ":")).encode(), 6)})
    return len(payload["rows"])


def read_history() -> dict | None:
    """The team's workbook as loaded (load_history), or None before it is."""
    engine = get_engine("app")
    if "cip_dataset_history" not in inspect(engine).get_table_names():
        return None
    with engine.connect() as conn:
        payload = conn.execute(text("SELECT payload FROM cip_dataset_history WHERE dataset = 'consumer_health'")).scalar()
    return json.loads(gzip.decompress(payload)) if payload else None


def new_weeks(out: Path, history: dict) -> tuple[list[dict], list[dict]]:
    """Rows and Source QA lines of every published US weekly wave after the history's last week."""
    header = history["header"]
    last = max(monday(r[header.index("Survey_Wave_Date")]) for r in history["rows"])
    rows, qa = [], []
    with get_engine("app").connect() as conn:
        for wave in read_waves(out, settings()["family"], "tracker"):
            if monday(wave["wave_date"]) > last:
                people, asked = read_people(conn, wave["survey_id"])
                if people:
                    week = wave_rows(wave, people, asked)
                    rows += week
                    qa.append(qa_line(wave, week))
    return rows, qa


def save(folder: Path, history: dict, rows: list[dict], qa: list[dict]) -> Path:
    """The whole workbook in the team's format, named for its years: Read Me (its figures recounted), one sheet per
    year, Source QA, Data Dictionary. openpyxl's write-only mode streams the cells to the file; the rows themselves
    (~68,000 in Nov 2026) are held once, ~180 MB at the peak, 12 s. Returns the file."""
    header = history["header"]
    all_rows = history["rows"] + [[row.get(c) for c in header] for row in rows]
    lines = history["source_qa"][1:] + [list(line.values()) for line in qa]
    book = Workbook(write_only=True)
    write_read_me(book.create_sheet("Read Me"), history["read_me"], read_me_figures(header, all_rows, lines))
    years = defaultdict(list)
    year_column = header.index("Survey_Year")
    for row in all_rows:
        years[str(row[year_column])].append(row)
    activities = settings()["activities"]
    green = set(activities["original"]) | set(activities["added"]) | {"None_Selected"}
    first_green = min(header.index(c) for c in green)
    fills = [BLUE if i < first_green else GREEN if c in green else PURPLE for i, c in enumerate(header)]
    for year in sorted(years):
        ws = book.create_sheet(year)
        ws.sheet_view.zoomScale = 80
        if year != min(years):   # header and columns A-M stay in view, as in theirs from 2024 (their 2023 sheet has none)
            ws.freeze_panes = "N2"
        write_sheet(ws, header, years[year], DATA_WIDTHS, 33.95, fills, {"Response_Date_Matches_Wave": [("equal", "0")],
                                                                           "Core_Valid_Flag": [("equal", "0")]})
    qa_sheet = book.create_sheet("Source QA")
    qa_sheet.freeze_panes = "E2"
    write_sheet(qa_sheet, history["source_qa"][0], lines, QA_WIDTHS, 32.1, None,   # a file dated a week off its wave, in red
                {"File_Date_Diff_Days": [("greaterThan", "7"), ("lessThan", "-7")]})
    dictionary = book.create_sheet("Data Dictionary")
    dictionary.freeze_panes = "A2"
    write_sheet(dictionary, history["dictionary"][0], history["dictionary"][1:], DICTIONARY_WIDTHS, 15.95, None, {})
    book.active = 1   # opens on the first year, as theirs does
    path = folder / NAME.format(first=min(years), last=max(years))
    book.save(path)
    return path


def read_me_figures(header: list, rows: list[list], lines: list[list]) -> dict:
    """The Read Me's figures for the whole workbook, by their label there."""
    column = {name: header.index(name) for name in ("Survey_Wave_Date", "Core_Valid_Flag", "Q1_Missing_Flag", "Q1_Contradiction_Flag")}
    dates = [r[column["Survey_Wave_Date"]] for r in rows]
    flagged = lambda name: sum(r[column[name]] == 1 for r in rows)   # noqa: E731
    return {"Uploaded coverage": f"{min(dates)} to {max(dates)}", "Survey waves": len(lines), "Respondent records": len(rows),
            "Completed / core-valid records": flagged("Core_Valid_Flag"), "Q1 missing responses": flagged("Q1_Missing_Flag"),
            "Q1 contradictory responses": flagged("Q1_Contradiction_Flag")}


def set_widths(ws, widths: list) -> None:
    """Each column's width as the team set it: characters plus Excel's padding."""
    for first, last, characters in widths:
        for column in range(first, last + 1):
            ws.column_dimensions[get_column_letter(column)].width = characters + 0.7109375


def write_sheet(ws, header: list, rows: list[list], widths: list, height: float, fills: list | None, flags: dict) -> None:
    """A sheet of the workbook: a coloured header, the rows, a filter on every column and the red-flag rules."""
    set_widths(ws, widths)
    ws.row_dimensions[1].height = height
    ws.append([make_cell(ws, name, **HEADER, fill=fills[i] if fills else BLUE) for i, name in enumerate(header)])
    for row in rows:
        ws.append(row)
    end = len(rows) + 1
    ws.auto_filter.ref = f"A1:{get_column_letter(len(header))}{end}"
    for name, rules in flags.items():
        letter = get_column_letter(header.index(name) + 1)
        for operator, value in rules:
            ws.conditional_formatting.add(f"{letter}2:{letter}{end}", CellIsRule(operator=operator, formula=[value], **FLAG))


def write_read_me(ws, cells: list[list], figures: dict) -> None:
    """The Read Me as the team wrote it, its figures recounted for the whole workbook: a title, label and value pairs,
    a notes heading."""
    set_widths(ws, README_WIDTHS)
    ws.freeze_panes = "A2"
    for number, row in enumerate(cells, start=1):
        if number in README_HEIGHTS:
            ws.row_dimensions[number].height = README_HEIGHTS[number]
        label, value = (list(row) + [None, None])[:2]   # an empty row may come back with no cells at all
        if number == 1 or (label and value is None):   # the title, and a heading across the sheet (the notes)
            ws.merged_cells.add(f"A{number}:H{number}")
            look = TITLE if number == 1 else LABEL
            ws.append([make_cell(ws, label, **look)] + [make_cell(ws, None, **look) for _ in range(7)])
        elif label:
            ws.append([make_cell(ws, label, **LABEL), make_cell(ws, figures.get(label, value), **VALUE)])
        else:
            ws.append([])


def make_cell(ws, value, **look) -> WriteOnlyCell:
    """A cell with its font, fill, border or alignment, for a write-only sheet."""
    cell = WriteOnlyCell(ws, value=value)
    for name, style in look.items():
        setattr(cell, name, style)
    return cell


def publish(out: Path) -> int:
    """Called by etl/publish.py write_views(): the workbook (history plus every newer US weekly wave) in out's
    api/v1/datasets, replacing the one before. Nothing until the history is loaded. Returns the bytes written."""
    history = read_history()
    if not history:
        return 0
    rows, qa = new_weeks(out, history)
    folder = out / FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("Consumer_Health_*.xlsx"):   # a hard link to the live version's file: never written through
        old.unlink()
    path = save(folder, history, rows, qa)
    log.info("Consumer Health dataset: %d history rows + %d new rows (%d weeks), %s", len(history["rows"]), len(rows), len(qa), path.name)
    return path.stat().st_size


def main() -> int:
    """The command line: load the team's workbook as the history."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--history", type=Path, required=True, help="the team's workbook, loaded as the frozen history")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s | %(message)s")
    log.info("Loaded %d history rows from %s", load_history(args.history), args.history.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
