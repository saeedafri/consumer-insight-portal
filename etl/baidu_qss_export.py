"""Loads one week of the China Consumer Survey from Baidu QSS (百度智能云问卷) into CIP, checked against Baidu's own topline.

Baidu has no API reachable from outside China, so each week an analyst downloads two files from it:
  the raw export   one row per respondent: Baidu's columns (masked user id, time taken "159秒", submit time
                   "10/21/26 22:19", five blank panel fields), then per question one column ("Q6.Q1. <text>【单选】")
                   or, for a multiple choice, one column per answer ("…【多选】-<answer>") holding the answer when
                   picked; "-Text" columns hold typed "other" answers. A .csv in GB18030 (Simplified Chinese
                   Windows), as Baidu writes it, or the same table saved as .xlsx.
  the topline      "Consumer Tracker_ <date>.xls": per question its answers' counts and "答题人数：<n>" (who answered).
Every Chinese wording goes through config/china_codebook.yml. Before anything is written, every count CIP
computes from the raw rows must equal the topline's: a wording the codebook lacks, a question missing, or one count
off stops the upload and is listed on the Upload survey page. Typed "other" answers are not loaded: they are
Chinese free text, and their "Other" ticks are.

Called by: api/ingest.py (the Upload survey page, /app/ingest): preview() writes nothing, load() loads the wave;
and by hand:  python -m etl.baidu_qss_export --raw "Original 7.csv" --topline "Consumer Tracker_ 2026-11-05.xls" [--preview]
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import logging
import re
import statistics
import zipfile
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Optional

import openpyxl
import xlrd
import yaml
from sqlalchemy import text

from etl import cube, harmonise, serving
from etl.loaders import (drop_unlisted_items, etl_lock, finish_run, index_survey, load_definitions, set_load_status,
                         start_run, upsert_survey)
from etl.records import NO_TO, ParsedQuestion, clean_text
from etl.wave_loader import (code_lookup, parse_datetime, rebuild_profiles, rebuild_question_bases, replace_respondents,
                             wave_from_records)
from shared.core.database import get_engine

log = logging.getLogger("cip.baidu")
CODEBOOK = Path(__file__).resolve().parents[1] / "config/china_codebook.yml"
COLUMN = re.compile(r"^Q\d+\.([SQ]\d+)\.\s*.*?【(?:单选|多选)】(?:-(.*))?$")   # "Q8.Q3. <text>【多选】-<answer>"
TITLE = re.compile(r"^\d+\.([SQ]\d+)\.")                                   # the topline's "8.Q3.<text>"


def load_codebook() -> dict:
    """config/china_codebook.yml: each question's English wording and its answers, Chinese to English."""
    return yaml.safe_load(CODEBOOK.read_text(encoding="utf-8"))


def cell(value) -> Optional[str]:
    """A cell as clean text, None when empty."""
    return clean_text(value) or None if value is not None else None


def read_table(path: Path) -> list[list]:
    """The file's first sheet as rows of cells. A wave's files are under 1 MB, so reading them whole is fine.
    A file no reader can open raises ValueError, as every other fault in the files does."""
    try:
        return read_sheet(path)
    except (OSError, ValueError, KeyError, xlrd.XLRDError, zipfile.BadZipFile, csv.Error) as exc:
        raise ValueError(f"{path.name[-40:]} could not be read as {path.suffix}: {exc}") from exc


def read_sheet(path: Path) -> list[list]:
    """read_table's reader for each of Baidu's formats."""
    suffix = path.suffix.lower()
    if suffix == ".csv":
        data = path.read_bytes()
        try:
            decoded = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            decoded = data.decode("gb18030")   # Baidu's own encoding; a superset of GBK
        return list(csv.reader(io.StringIO(decoded)))
    if suffix == ".xls":
        sheet = xlrd.open_workbook(path).sheet_by_index(0)
        return [sheet.row_values(r) for r in range(sheet.nrows)]
    book = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        return [list(row) for row in book.worksheets[0].iter_rows(values_only=True)]
    finally:
        book.close()


def read_topline(path: Path) -> dict[str, dict]:
    """Baidu's topline: {question code: {"base": who answered, "counts": {Chinese answer: count}}}."""
    found: dict[str, dict] = {}
    current = None
    for row in read_table(path):
        first = cell(row[0]) if row else None
        if not first:
            continue
        if title := TITLE.match(first):
            current = found[title[1]] = {"base": None, "counts": {}}
        elif current is None or first in ("选项", "总计"):
            continue
        elif first.startswith("答题人数"):
            current["base"] = int(re.sub(r"\D", "", first) or 0)
        else:
            current["counts"][first] = int(float(row[1] or 0)) if len(row) > 1 else 0
    if not found:
        raise ValueError(f"{path.name} is not a Baidu topline: no question titles such as '1.S1.' found")
    return found


def seconds_taken(value) -> Optional[int]:
    """'159秒' or '1分12秒' as seconds."""
    found = re.fullmatch(r"(?:(\d+)分)?(?:(\d+)秒)?", cell(value) or "")
    if not found or not any(found.groups()):
        return None
    return int(found[1] or 0) * 60 + int(found[2] or 0)


def read_raw(path: Path, codebook: dict) -> tuple[list[ParsedQuestion], list[dict], list[str]]:
    """The raw export as (questions in English, respondent records in the loaders' label convention, problems)."""
    rows = read_table(path)
    if not rows:
        raise ValueError(f"{path.name} is empty")
    questions_zh = codebook["questions"]
    columns: dict[str, dict] = {}
    problems = []
    if [cell(h) for h in rows[0][:3]] != ["用户ID", "答题时长", "提交时间"]:   # read by position below
        problems.append(f"the first columns are not Baidu's user id, time taken, submit time: {rows[0][:3]}")
    for i, header in enumerate(cell(h) or "" for h in rows[0]):
        found = COLUMN.match(header)
        if not found:
            continue   # Baidu's own columns: user id, time taken, submit time, panel fields
        qcode, answer = found[1], found[2]
        if qcode not in questions_zh:
            problems.append(f"{qcode} is in the file but not in config/china_codebook.yml")
            continue
        place = columns.setdefault(qcode, {"items": [], "codes": {a: f"{qcode}_{n}" for n, a in
                                                            enumerate(questions_zh[qcode]["answers"], start=1)}})
        if answer is None:
            place["answer"] = i
        elif not answer.endswith("-Text"):   # "-Text": a typed "other" answer, not loaded
            if answer not in questions_zh[qcode]["answers"]:
                problems.append(f"{qcode} answer not in the codebook: {answer}")
            place["items"].append((i, answer))
    if not columns:
        raise ValueError(f"{path.name} has no Baidu question columns ('Q1.S1. …【单选】'): is it the raw export?")
    problems += [f"{qcode} is missing from the file" for qcode in questions_zh if qcode not in columns]
    problems += [f"{qcode} answer missing from the file: {answer}" for qcode, place in columns.items()
                 if questions_zh[qcode]["type"] == "multi"
                 for answer in questions_zh[qcode]["answers"] if answer not in {a for _, a in place["items"]}]

    questions = []
    for qcode, entry in questions_zh.items():
        english = list(entry["answers"].values())
        if entry["type"] == "single":
            questions.append(ParsedQuestion(qcode, entry["text"], "single", 1, len(english),
                                            options=list(enumerate(english, start=1))))
        else:
            questions.append(ParsedQuestion(qcode, entry["text"], "multi", 0, 1,
                                            rows=[(f"{qcode}_{n}", label) for n, label in enumerate(english, start=1)]))

    records = []
    for number, row in enumerate((r for r in rows[1:] if any(cell(v) for v in r)), start=1):
        record = {"record": number, "status": "Qualified",   # the export holds completed interviews only
                  "date": parse_datetime(row[2]),
                  "qtime": seconds_taken(row[1])}
        if record["date"] is None:
            problems.append(f"row {number + 1}: submit time not understood: {row[2]!r}")
        for qcode, place in columns.items():
            answers = questions_zh[qcode]["answers"]
            if "answer" in place:
                chosen = cell(row[place["answer"]])
                if chosen and chosen not in answers:
                    problems.append(f"{qcode} answer not in the codebook: {chosen}")
                elif chosen:
                    record[qcode] = answers[chosen]
            else:
                picked = [(answer, cell(row[i]) is not None) for i, answer in place["items"] if answer in answers]
                # Baidu requires an answer to every question it shows, so a blank one was routed past (Q3 follows
                # only "Yes" at Q2): leaving it out keeps the person out of its base, as Baidu's topline does
                if any(was for _, was in picked):
                    record.update({place["codes"][answer]: answers[answer] if was else f"{NO_TO}{answers[answer]}"
                                   for answer, was in picked})
        records.append(record)
    if not records:
        raise ValueError(f"{path.name} has no respondents")
    return questions, records, list(dict.fromkeys(problems))   # each problem once, in the order found


def count_answers(question: ParsedQuestion, records: list[dict]) -> tuple[int, dict[str, int]]:
    """(who answered, {English answer: how many chose it}), counted from the records as the cube will."""
    if question.qtype == "single":
        chosen = Counter(r[question.qcode] for r in records if question.qcode in r)
        return sum(chosen.values()), {label: chosen[label] for _, label in question.options}
    asked = [r for r in records if any(code in r for code, _ in question.rows)]
    return len(asked), {label: sum(r.get(code) == label for r in asked) for code, label in question.rows}


def compare_with_topline(questions: list[ParsedQuestion], records: list[dict], topline: dict, codebook: dict) -> tuple[int, list[str]]:
    """(figures that match, problems): every base and count from the raw rows against Baidu's topline."""
    matched, problems = 0, []
    for question in questions:
        theirs = topline.get(question.qcode)
        if theirs is None:
            problems.append(f"{question.qcode} is missing from the topline")
            continue
        base, ours = count_answers(question, records)
        if base != theirs["base"]:
            problems.append(f"{question.qcode}: {base} answered in the raw file, the topline says {theirs['base']}")
        else:
            matched += 1
        answers = codebook["questions"][question.qcode]["answers"]
        for chinese, count in theirs["counts"].items():
            english = answers.get(chinese)
            if english is None:
                problems.append(f"{question.qcode} topline answer not in the codebook: {chinese}")
            elif ours[english] != count:
                problems.append(f"{question.qcode} '{english}': {ours[english]} in the raw file, the topline says {count}")
            else:
                matched += 1
        listed = {answers.get(chinese) for chinese in theirs["counts"]}
        problems += [f"{question.qcode} '{english}': {n} in the raw file, not in the topline"
                     for english, n in ours.items() if n and english not in listed]
    return matched, problems


def read_wave(raw: Path, topline: Path) -> dict:
    """Both files read and checked: the questions, records, wave date and every problem. Writes nothing."""
    codebook = load_codebook()
    questions, records, problems = read_raw(raw, codebook)
    topline_figures = read_topline(topline)
    matched, mismatches = compare_with_topline(questions, records, topline_figures, codebook)
    dates = [r["date"] for r in records if r["date"]]
    seconds = [r["qtime"] for r in records if r["qtime"] is not None]
    return {"questions": questions, "records": records, "problems": problems + mismatches, "matched": matched,
            "topline": topline_figures,
            "wave": wave_from_records(records) if dates else None,
            "field_start": min(dates, default=None), "field_end": max(dates, default=None),
            "median_seconds": statistics.median(seconds) if seconds else None}


def store_topline(conn, survey_id: int, topline: dict, source_file: str) -> int:
    """Baidu's topline, as printed, into cip_crosstab (one run, one Total column; the wave's earlier run replaced):
    the vendor's own figures beside CIP's, so a check can be repeated later. Returns the cells written."""
    conn.execute(text("DELETE FROM cip_crosstab_run WHERE survey_id = :s"), {"s": survey_id})
    conn.execute(text("DELETE FROM cip_banner WHERE survey_id = :s"), {"s": survey_id})
    banner = conn.execute(text("INSERT INTO cip_banner (survey_id, banner_code, banner_name) VALUES (:s, 'TOTAL', 'Total')"),
                          {"s": survey_id}).lastrowid
    segment = conn.execute(text("INSERT INTO cip_segment (banner_id, survey_id, seg_label, is_total)"
                                " VALUES (:b, :s, 'Total', 1)"), {"b": banner, "s": survey_id}).lastrowid
    run = conn.execute(text("INSERT INTO cip_crosstab_run (survey_id, run_label, respondent_base, pct_base, source_file)"
                            " VALUES (:s, 'Baidu QSS topline', 'All completes', 'Total answering', :f)"),
                       {"s": survey_id, "f": source_file[:255]}).lastrowid
    answers = load_codebook()["questions"]
    ids = {(qcode, label): (qid, iid, oid) for qcode, label, qid, iid, oid in conn.execute(text(
        "SELECT q.qcode, COALESCE(o.value_label, i.item_label), q.question_id, i.item_id, o.option_id FROM cip_question q"
        " LEFT JOIN cip_option o ON o.question_id = q.question_id LEFT JOIN cip_item i ON i.question_id = q.question_id"
        " WHERE q.survey_id = :s"), {"s": survey_id})}
    cells = [{"run": run, "s": survey_id, "q": qid, "i": iid, "o": oid, "seg": segment, "label": chinese,
              "n": count, "base": figures["base"], "pct": count / figures["base"] if figures["base"] else None}
             for qcode, figures in topline.items() if qcode in answers
             for chinese, count in figures["counts"].items()
             for qid, iid, oid in [ids[(qcode, answers[qcode]["answers"][chinese])]]]
    conn.execute(text("INSERT INTO cip_crosstab (run_id, survey_id, question_id, item_id, option_id, segment_id,"
                      " stub_label, stub_key, pct, count_n, answer_base_n)"
                      " VALUES (:run, :s, :q, :i, :o, :seg, :label, :label, :pct, :n, :base)"), cells)
    return len(cells)


def preview(raw: Path, topline: Path) -> dict:
    """What the Upload survey page shows before anything is loaded: the wave, the check, every question's counts."""
    wave = read_wave(raw, topline)
    questions = []
    for q in wave["questions"]:
        base, counts = count_answers(q, wave["records"])
        questions.append({"qcode": q.qcode, "text": q.qtext, "type": q.qtype, "base": base,
                          "answers": [[label, n, round(100 * n / base, 1) if base else 0] for label, n in counts.items()]})
    return {"wave": wave["wave"], "respondents": len(wave["records"]), "matched": wave["matched"],
            "problems": wave["problems"][:50], "problem_count": len(wave["problems"]),
            "field_start": wave["field_start"] and wave["field_start"].isoformat(),
            "field_end": wave["field_end"] and wave["field_end"].isoformat(),
            "median_seconds": wave["median_seconds"], "questions": questions}


def load(raw: Path, topline: Path, wave_date: Optional[str] = None) -> dict:
    """Load the week as a wave and build what the screens read (profiles, bases, concepts, cube, search, serving
    rows), the steps and order of the Forsta loads (etl/forsta_etl.py _load_snapshot). The same week uploaded
    again replaces it. Refuses, writing nothing, while read_wave reports any problem."""
    wave = read_wave(raw, topline)
    if wave["problems"]:
        raise ValueError(f"{len(wave['problems'])} problems, nothing loaded: " + "; ".join(wave["problems"][:10]))
    label = wave_date or wave["wave"]
    family = load_codebook()["family"]
    ref = f"baidu:{family}"   # one row per week: (platform, source_ref, wave_label) is the wave's identity
    questions, records = wave["questions"], wave["records"]
    when = date.fromisoformat(label)
    with etl_lock():
        engine = get_engine("etl")
        with engine.connect() as conn:   # read before the upsert: a new row starts as 'verified'
            previous = conn.execute(text("SELECT load_status FROM cip_survey WHERE platform = 'baidu'"
                                         " AND source_ref = :ref AND wave_label = :w"),
                                    {"ref": ref, "w": label}).scalar()
        survey_id = upsert_survey(host="baidu", path=ref, source_ref=ref, platform="baidu",
                                  title=f"China Consumer Survey, week of {when.day} {when:%b %Y}",
                                  survey_family=family, wave_label=label, wave_date=label, study_type="tracker")
        with engine.begin() as conn:
            conn.execute(text("UPDATE cip_survey SET load_status = 'loading', country = 'CN', total_n = :n,"
                              " field_start = :fs, field_end = :fe WHERE survey_id = :s"),
                         {"n": len(records), "fs": wave["field_start"], "fe": wave["field_end"], "s": survey_id})
        run = start_run(survey_id, "excel", "data", f"baidu:{raw.name} + {topline.name}")
        written = None
        try:
            fields = load_definitions(survey_id, questions, family)
            written = replace_respondents(survey_id, records, fields, run, code_lookup(survey_id))
            drop_unlisted_items(survey_id, questions)
            rebuild_profiles(survey_id, None, family)
            rebuild_question_bases(survey_id, drop_labels=False)
            harmonise.harmonise_survey(survey_id)
            cells = cube.refresh_wave(survey_id)
            index_survey(survey_id)
            serving.build_wave(survey_id)
            with engine.begin() as conn:
                store_topline(conn, survey_id, wave["topline"], topline.name)
        except Exception as exc:
            finish_run(run, len(records), written or 0, error=str(exc)[:2000])
            intact = written is None and previous == "verified"   # the answers never changed: the old week stands
            set_load_status(survey_id, "verified" if intact else "failed")
            if not intact:   # serving rows for answers that are gone must not stay on screen
                with engine.begin() as conn:
                    serving.drop_wave(conn, survey_id)
            raise
        finish_run(run, len(records), written)
        set_load_status(survey_id, "verified")
        serving.rebuild_dependants(survey_id)   # next week now has this one to compare with
    log.info("China survey %s (%s): %d respondents, %d cube cells, %d topline figures equal",
             survey_id, label, written, cells, wave["matched"])
    return {"survey_id": survey_id, "wave": label, "respondents": written, "matched": wave["matched"]}


def main() -> int:
    """By hand: check (--preview) or load one week from its two files."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s | %(message)s")
    parser = argparse.ArgumentParser(description="Load one week of the China Consumer Survey (Baidu QSS)")
    parser.add_argument("--raw", required=True, type=Path, help="the raw export (.csv or .xlsx)")
    parser.add_argument("--topline", required=True, type=Path, help="Baidu's topline (.xls or .xlsx)")
    parser.add_argument("--wave", help="the wave's Monday, YYYY-MM-DD (default: the Monday of the first submit)")
    parser.add_argument("--preview", action="store_true", help="check and show; write nothing")
    args = parser.parse_args()
    out = preview(args.raw, args.topline) if args.preview else load(args.raw, args.topline, args.wave)
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
