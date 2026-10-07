"""Qualtrics' Excel export: row 1 column codes (B10_3), row 2 question text
("<question> - <answer>"), then one row per respondent. There is no datamap,
so types and answer lists are recovered from the columns and their values:

  * `…_TEXT` columns are open text ("Other (please specify)")
  * a group whose every cell holds its own column's answer is a multi-select
    — the header ends " - <that answer>"; the answer is the item label (it may
    itself contain " - ", so the header is never split to find it)
  * any other multi-column group is a grid (rows = columns, scale = values)
  * a single column is single-choice

Personal and system columns (IP, location, recipient, panel RID, Q_* fraud
scores) are never read into CSI.

    python -m etl.qualtrics_export --file "…_May 20, 2025_08.00 1.xlsx" --wave 2025-05-12
"""
from __future__ import annotations

import argparse
import logging
import re
from pathlib import Path

import openpyxl
from sqlalchemy import text

from app.core.database import get_engine
from app.data import cube, harmonise
from etl import records as xp
from etl.loaders import finish_run, index_survey, load_definitions, start_run, upsert_survey

log = logging.getLogger("cip.qualtrics")

DROPPED = {"StartDate", "IPAddress", "Progress", "Finished", "RecipientLastName", "RecipientFirstName",
           "RecipientEmail", "ExternalReference", "LocationLatitude", "LocationLongitude",
           "DistributionChannel", "UserLanguage", "RecordedDate", "Status", "RID", "SC0", "COMPLETE"}
META = {"EndDate", "Duration (in seconds)", "ResponseId"}


def _multi_stem(cols: list[int], headers: list[str], values: dict[int, set]):
    """The question text if every column holds only its own answer, else None."""
    stem = None
    for i in cols:
        if len(values[i]) > 1:
            return None
        if values[i]:
            (value,) = values[i]
            if not headers[i].endswith(" - " + value):
                return None
            stem = headers[i][: -len(" - " + value)]
    return stem


def parse_export(path) -> tuple[list, list[dict]]:
    """-> (ParsedQuestions, loader records in the Forsta label convention)."""
    ws = openpyxl.load_workbook(path, read_only=True, data_only=True).worksheets[0]
    rows = ws.iter_rows(values_only=True)
    codes = [re.sub(r"\s+(?=_)", "", str(c or "").strip()) for c in next(rows)]   # "B9C _10_TEXT"
    headers = [xp.clean_text(t or "") for t in next(rows)]
    data = [list(r) for r in rows if any(v not in (None, "") for v in r)]
    cell = [[None if v in (None, "") else xp.clean_text(v) for v in r] for r in data]

    groups: dict[str, list[int]] = {}
    for i, code in enumerate(codes):
        if not code or code in DROPPED or code in META or code.startswith("Q_"):
            continue
        key = code if code.endswith("_TEXT") or "_" not in code else code.split("_")[0]
        groups.setdefault(key, []).append(i)

    questions, kinds = [], {}
    for key, cols in groups.items():
        values = {i: {r[i] for r in cell if r[i] is not None} for i in cols}
        stem = _multi_stem(cols, headers, values) if len(cols) > 1 else None
        if key.endswith("_TEXT"):
            questions.append(xp.ParsedQuestion(qcode=key, qtext=headers[cols[0]], qtype="text"))
            kinds[key] = "text"
        elif stem:
            items = [(codes[i], headers[i][len(stem) + 3:]) for i in cols]
            questions.append(xp.ParsedQuestion(qcode=key, qtext=stem, qtype="multi",
                                               value_min=0, value_max=1, rows=items))
            kinds[key] = "multi"
        elif len(cols) > 1:
            scale = list(dict.fromkeys(r[i] for r in cell for i in cols if r[i] is not None))
            questions.append(xp.ParsedQuestion(qcode=key, qtext=headers[cols[0]].rsplit(" - ", 1)[0],
                                               qtype="grid_single", value_min=1, value_max=len(scale),
                                               rows=[(codes[i], headers[i].rsplit(" - ", 1)[-1]) for i in cols],
                                               options=list(enumerate(scale, start=1))))
            kinds[key] = "grid"
        else:
            options = list(dict.fromkeys(r[cols[0]] for r in cell if r[cols[0]] is not None))
            questions.append(xp.ParsedQuestion(qcode=key, qtext=headers[cols[0]], qtype="single",
                                               value_min=1, value_max=len(options),
                                               options=list(enumerate(options, start=1))))
            kinds[key] = "single"

    at = {c: i for i, c in enumerate(codes)}
    labels = {q.qcode: dict(q.rows) for q in questions if q.qtype == "multi"}
    records = []
    for n, (raw, r) in enumerate(zip(data, cell), start=1):
        rec = {"record": n, "uuid": r[at["ResponseId"]], "status": "Qualified",
               "date": raw[at["EndDate"]], "qtime": raw[at["Duration (in seconds)"]]}
        for key, cols in groups.items():
            if kinds[key] == "multi":
                if any(r[i] is not None for i in cols):
                    for i in cols:
                        label = labels[key][codes[i]]
                        rec[codes[i]] = label if r[i] is not None else f"{xp.NO_TO}{label}"
            elif kinds[key] == "grid":
                rec.update({codes[i]: r[i] for i in cols if r[i] is not None})
            elif r[cols[0]] is not None:
                rec[key] = r[cols[0]]
        records.append(rec)
    return questions, records


def order_like_concepts(questions: list) -> None:
    """The export gives no answer order — values appear in the order people
    happened to answer ('30 - 44' before '18 - 29'). Where a concept already
    has the question (from a legacy wave, in questionnaire order), use its
    order; answers it does not know keep their place after the known ones."""
    with get_engine("etl").connect() as conn:
        concepts = harmonise._concepts(conn)
        position = dict(conn.execute(text("SELECT concept_option_id, sort_order FROM cip_concept_option")).all())
    order = {c.match_text: {label: position[coid] for label, coid in c.options.items()}
             for c in concepts.values() if c.qtype == "single" or c.qtype.startswith("grid")}
    for q in questions:
        if not q.options:
            continue
        wording = f"{q.qtext} :: {q.rows[0][1]}" if q.rows else q.qtext
        known = order.get(harmonise.normalise_text(wording))
        if known:
            labels = sorted((label for _, label in q.options),
                            key=lambda label: known.get(harmonise.normalise_text(label), len(known) + 1000))
            q.options = list(enumerate(labels, start=1))


def ingest_export(path, wave: str, family: str = "CSI-US") -> int:
    from etl.run_pipeline import _code_lookup, _load_one_respondent, _rebuild_profiles, _rebuild_question_bases

    questions, records = parse_export(path)
    order_like_concepts(questions)
    title = re.sub(r"_[A-Z][a-z]+ \d+, \d{4}.*$", "", Path(path).stem)
    ref = f"xlsx:{title}"[:255]
    survey_id = upsert_survey(host="qualtrics", path=ref, title=title[:500], survey_family=family,
                              wave_label=wave, wave_date=wave, platform="qualtrics", source_ref=ref)
    run = start_run(survey_id, "excel", "data", str(path))
    fields = load_definitions(survey_id, questions, family)
    code_map = _code_lookup(survey_id)
    loaded = sum(_load_one_respondent(survey_id, rec, fields, run, code_map) for rec in records)
    finish_run(run, len(records), loaded)
    # Demographics by wording, never the Forsta D-code map: Qualtrics numbers
    # them differently (its D7 is state, Forsta's D7 is political view).
    _rebuild_profiles(survey_id, None, None)
    _rebuild_question_bases(survey_id)
    log.info("%s -> survey_id=%s: %d respondents; harmonised %s", Path(path).name, survey_id, loaded,
             harmonise.harmonise_survey(survey_id))
    log.info("Cube: %d cells", cube.refresh_wave(survey_id))
    index_survey(survey_id)
    return survey_id


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s | %(message)s")
    ap = argparse.ArgumentParser(description="Load a Qualtrics Excel export into CSI")
    ap.add_argument("--file", required=True)
    ap.add_argument("--wave", required=True, help="first fielding day, e.g. 2025-05-12")
    ap.add_argument("--family", default="CSI-US")
    args = ap.parse_args()
    ingest_export(args.file, args.wave, args.family)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
