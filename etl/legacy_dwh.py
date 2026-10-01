"""Load a legacy survey (dwh_sm* — the Qualtrics and SurveyMonkey years) into CSI.

The legacy tables sit on the same MySQL server as csi_*, so answers are moved
server-side (INSERT … SELECT): only the small question definitions travel to
this process. That is what makes 142 waves loadable over the India–Azure link.

The legacy `family` label cannot be trusted for Qualtrics waves (yes/no
questions are stored as 'multiple_choice'), so the type is inferred from the
data: more than one answer from any respondent, or "select all" wording,
means multi-select. Questions with no answer rows (grids such as B11 were never
imported) are skipped and counted.

    python -m etl.legacy_dwh --all            # every Qualtrics-era wave, oldest first
    python -m etl.legacy_dwh --id SV_0IHGTy1GPAlUsGa
"""
from __future__ import annotations

import argparse
import hashlib
import logging
import re
from typing import Optional

from sqlalchemy import bindparam, text

from app.core.database import get_engine
from app.data import cube, harmonise
from etl import excel_parsers as xp
from etl.loaders import finish_run, load_definitions, start_run, upsert_survey

log = logging.getLogger("cip.legacy")

LEGACY_STATUS = {"completed": (3, "Qualified"), "partial": (4, "Partial"),
                 "disqualified": (1, "Terminated"), "overquota": (2, "Overquota")}
_MULTI_WORDING = re.compile(r"select all|all that apply|select up to|select (two|three)", re.I)
_TRACKER = re.compile(r"^\s*shopping(,| and)\s+spending", re.I)


def legacy_qtype(family: Optional[str], title: str, max_per_response: Optional[int],
                 n_answers: int) -> Optional[str]:
    if max_per_response is None:
        return None
    if family == "matrix":
        return "grid"
    if n_answers == 0:
        return "text"
    if max_per_response > 1 or _MULTI_WORDING.search(title or ""):
        return "multi"
    return "single"


def study_for(title: str, completes: int) -> tuple[str, str]:
    if _TRACKER.match(title or ""):
        return "CSI-US", "tracker"
    family = re.sub(r"[^A-Z0-9]+", "_", (title or "").upper()).strip("_")[:60] or "ADHOC"
    return family, "annual" if completes >= 1500 else "adhoc"


def legacy_surveys(conn, era: str = "qualtrics") -> list[dict]:
    """Legacy waves with completed responses, oldest first. Qualtrics ids
    start 'SV_'; SurveyMonkey ids are numeric (Phase 6)."""
    op = "=" if era == "qualtrics" else "<>"
    rows = conn.execute(text(f"""
        SELECT d.id, d.title, MIN(r.date_filled), COUNT(*)
          FROM dwh_smsurveydetail d
          JOIN dwh_smresponse r ON r.survey_id = d.id AND r.response_status = 'completed'
               -- hand-entered summary rows are keyed '<survey id>_Q1_R1', not by respondent
               AND SUBSTR(r.id, 1, LENGTH(d.id)) <> d.id
         WHERE SUBSTR(d.id, 1, 3) {op} 'SV_' AND COALESCE(d.isvalid, 1) = 1
         GROUP BY d.id, d.title
         ORDER BY MIN(r.date_filled), d.id""")).all()
    return [{"id": i, "title": t, "first": f, "completes": n} for i, t, f, n in rows]


def _qid_number(question_id: str) -> int:
    m = re.search(r"QID(\d+)$", str(question_id))
    return int(m.group(1)) if m else 0


def _definitions(conn, legacy_id: str):
    """-> (ParsedQuestions, answer map rows, skipped question count)."""
    questions = conn.execute(text(
        "SELECT id, family, title, srt1, srt2 FROM dwh_smquestion WHERE survey_id = :lid"
        " ORDER BY srt1, srt2, id"), {"lid": legacy_id}).all()
    # The Aug 2022 waves have no srt1/srt2: order and number by Qualtrics' own
    # QID<n> (as text, QID11 would sort before QID2).
    questions = sorted(questions, key=lambda q: (q[3] is None, q[3] or 0, q[4] or 0, _qid_number(q[0]), q[0]))
    most = dict(conn.execute(text("""
        SELECT question_id, MAX(n) FROM (
            SELECT question_id, response_id, COUNT(*) AS n FROM dwh_smresponseqa
             WHERE survey_id = :lid GROUP BY question_id, response_id) per_response
         GROUP BY question_id"""), {"lid": legacy_id}).all())
    answers: dict[str, list] = {}
    for aid, qid, title in conn.execute(text(
            "SELECT id, question_id, title FROM dwh_smanswer WHERE survey_id = :lid"
            " ORDER BY question_id, srt, id"), {"lid": legacy_id}):
        answers.setdefault(qid, []).append((aid, xp.clean_text(title)))
    # Selections whose answer id is missing from dwh_smanswer (2,167 rows in
    # dwh_stg — "Clubhouse", "None of these"): the label survives only in
    # answer_text. Choice questions only, so an open-text question stays text.
    for qid, aid, label in conn.execute(text("""
            SELECT x.question_id, x.answer_id, MIN(x.answer_text) FROM dwh_smresponseqa x
              LEFT JOIN dwh_smanswer a ON a.id = x.answer_id
             WHERE x.survey_id = :lid AND a.id IS NULL AND x.answer_id IS NOT NULL
             GROUP BY x.question_id, x.answer_id ORDER BY x.question_id, x.answer_id"""),
            {"lid": legacy_id}):
        if qid in answers:
            answers[qid].append((aid, xp.clean_text(label) or str(aid)))

    parsed, amap, skipped, seen = [], [], 0, set()
    for qid, family, title, srt1, srt2 in questions:
        title = xp.clean_text(title)
        opts = answers.get(qid, [])
        qtype = legacy_qtype(family, title, most.get(qid), len(opts))
        if qtype is None:
            skipped += 1
            continue
        qcode = (f"Q{srt1 + 1}" + (f"_{srt2}" if srt2 else "") if srt1 is not None
                 else f"Q{_qid_number(qid)}")
        while qcode in seen:
            qcode += "b"
        seen.add(qcode)
        if qtype == "grid":
            question, cells = _matrix(conn, qid, qcode, title, opts)
            if question.rows and most.get(qid, 0) <= len(question.rows):
                parsed.append(question)
                amap += cells
                continue
            if question.rows or sum(1 for _, label in opts if not label) != 1:
                # a checkbox matrix, or one whose rows cannot be read: skipped,
                # counted, and flagged by reconcile — never guessed
                skipped += 1
                continue
            # one blank row: the answers carry no "<row> | " — a plain single choice
            qtype, opts = "single", [(aid, label) for aid, label in opts if label]
        if qtype == "multi":
            rows = [(f"{qcode}r{i}", label) for i, (_, label) in enumerate(opts, start=1)]
            parsed.append(xp.ParsedQuestion(qcode=qcode, qtext=title, qtype="multi",
                                            value_min=0, value_max=1, rows=rows))
            amap += [{"aid": aid, "qid": qid, "qcode": qcode, "field": code, "code": 1, "label": label}
                     for (aid, _), (code, label) in zip(opts, rows)]
        elif qtype == "single":
            options = [(i, label) for i, (_, label) in enumerate(opts, start=1)]
            parsed.append(xp.ParsedQuestion(qcode=qcode, qtext=title, qtype="single",
                                            value_min=1, value_max=len(options), options=options))
            amap += [{"aid": aid, "qid": qid, "qcode": qcode, "field": qcode, "code": code, "label": label}
                     for (aid, _), (code, label) in zip(opts, options)]
        else:
            parsed.append(xp.ParsedQuestion(qcode=qcode, qtext=title, qtype="text"))
    return parsed, amap, skipped


def _matrix(conn, qid: str, qcode: str, title: str, opts: list):
    """A SurveyMonkey matrix: dwh_smanswer lists the row labels and the scale
    columns together; each response row stores "<row> | <column>" in
    answer_text with the COLUMN's id in answer_id. Rows are the labels seen
    before " | "; the rest of the answers are the scale, in srt order."""
    texts = conn.execute(text(
        "SELECT DISTINCT answer_id, answer_text FROM dwh_smresponseqa WHERE question_id = :q"
        " AND answer_text IS NOT NULL"), {"q": qid}).all()
    row_of = {raw: xp.clean_text(raw.rsplit(" | ", 1)[0]) for _, raw in texts if " | " in raw}
    labels = {label for _, label in opts}
    row_labels = [label for _, label in opts if label in set(row_of.values())]
    row_labels += sorted(set(row_of.values()) - labels)          # a row not listed in dwh_smanswer
    # the scale is the columns respondents actually chose — a row nobody
    # answered is still listed in dwh_smanswer and is NOT a scale point
    used = {aid for aid, raw in texts if raw in row_of}
    scale = [(aid, label) for aid, label in opts if aid in used]
    rows = [(f"{qcode}r{i}", label) for i, label in enumerate(row_labels, start=1)]
    field_of = {label: code for code, label in rows}
    code_of = {aid: n for n, (aid, _) in enumerate(scale, start=1)}
    question = xp.ParsedQuestion(qcode=qcode, qtext=title, qtype="grid_single", value_min=1,
                                 value_max=len(scale), rows=rows,
                                 options=[(n, label) for n, (_, label) in enumerate(scale, start=1)])
    cells = [{"aid": aid, "qid": qid, "qcode": qcode, "field": field_of[row_of[raw]], "code": code_of[aid],
              "label": dict(scale)[aid], "match": raw}
             for aid, raw in texts if raw in row_of and aid in code_of]
    return question, cells


def _move_answers(conn, survey_id: int, legacy_id: str, rows: list[dict]) -> int:
    """Replace the wave's answers from dwh_smresponseqa, inside MySQL.

    The two maps are temp tables cloned from the legacy tables (WHERE 1 = 0)
    so their id columns carry the legacy collation — csi_* uses another, and
    comparing the two directly fails with "Illegal mix of collations"."""
    conn.execute(text("CREATE TEMPORARY TABLE IF NOT EXISTS csi_tmp_answer_map AS"
                      " SELECT id AS answer_id, CAST(0 AS SIGNED) AS field_id, CAST(0 AS SIGNED) AS value_code,"
                      " title AS value_label, title AS match_text FROM dwh_smanswer WHERE 1 = 0"))
    conn.execute(text("CREATE TEMPORARY TABLE IF NOT EXISTS csi_tmp_response_map AS"
                      " SELECT id AS response_id, CAST(0 AS SIGNED) AS respondent_id"
                      " FROM dwh_smresponse WHERE 1 = 0"))
    conn.execute(text("DELETE FROM csi_tmp_answer_map"))
    conn.execute(text("DELETE FROM csi_tmp_response_map"))
    if rows:
        conn.execute(text("INSERT INTO csi_tmp_answer_map (answer_id, field_id, value_code, value_label, match_text)"
                          " VALUES (:aid, :fid, :code, :label, :match)"), rows)
    conn.execute(text("INSERT INTO csi_tmp_response_map (response_id, respondent_id)"
                      " SELECT forsta_uuid, respondent_id FROM csi_respondent WHERE survey_id = :sid"),
                 {"sid": survey_id})
    conn.execute(text("DELETE FROM csi_answer WHERE survey_id = :sid"), {"sid": survey_id})
    # the answers people gave
    conn.execute(text("""
        INSERT INTO csi_answer (respondent_id, survey_id, field_id, value_code, value_label)
        SELECT rm.respondent_id, :sid, m.field_id, MIN(m.value_code), MIN(m.value_label)
          FROM dwh_smresponseqa x
          JOIN csi_tmp_answer_map m ON m.answer_id = x.answer_id
               -- a matrix cell is its column id AND its "<row> | <column>" text
               AND (m.match_text IS NULL OR m.match_text = x.answer_text)
          JOIN csi_tmp_response_map rm ON rm.response_id = x.response_id
         WHERE x.survey_id = :lid
         GROUP BY rm.respondent_id, m.field_id"""), {"sid": survey_id, "lid": legacy_id})
    # multi-select items a respondent saw but did not choose -> 0, so the
    # "Total Answering" base counts everyone who answered the question
    conn.execute(text("""
        INSERT INTO csi_answer (respondent_id, survey_id, field_id, value_code, value_label)
        SELECT a.respondent_id, :sid, f.field_id, 0, i.item_label
          FROM (SELECT DISTINCT z.respondent_id, f2.question_id
                  FROM csi_answer z
                  JOIN csi_field f2 ON f2.field_id = z.field_id
                  JOIN csi_question q ON q.question_id = f2.question_id
                 WHERE z.survey_id = :sid AND q.is_multi = 1) a
          JOIN csi_field f ON f.question_id = a.question_id AND f.item_id IS NOT NULL
          JOIN csi_item i ON i.item_id = f.item_id
         WHERE NOT EXISTS (SELECT 1 FROM csi_answer y
                            WHERE y.respondent_id = a.respondent_id AND y.field_id = f.field_id)"""),
        {"sid": survey_id})
    return conn.execute(text("SELECT COUNT(*) FROM csi_answer WHERE survey_id = :sid"),
                        {"sid": survey_id}).scalar()


def _panel_profiles(survey_id: int, legacy_id: str) -> int:
    """SurveyMonkey Audience supplied age, gender, income and Census division
    per response (dwh_smdemography), not as questions. They fill the profile
    where no question did — a respondent's own answer is never overwritten.
    About 2,000 responses have the row twice; one per response is used."""
    from etl import survey_map

    eng = get_engine("etl")
    with eng.connect() as conn:
        # matched in Python: the legacy ids and csi_respondent use different
        # collations, and MySQL refuses to compare them ("Illegal mix")
        respondent = dict(conn.execute(text(
            "SELECT forsta_uuid, respondent_id FROM csi_respondent WHERE survey_id = :sid"), {"sid": survey_id}).all())
        panel = conn.execute(text("""
            SELECT response_id, MIN(age), MIN(gender), MIN(income), MIN(region) FROM dwh_smdemography
             WHERE survey_id = :lid GROUP BY response_id"""), {"lid": legacy_id}).all()
        own = {r[0]: dict(r._mapping) for r in conn.execute(text(
            "SELECT respondent_id, gender, age_years, age_band, generation, age_mid, income_band, income_mid_k,"
            " census_region FROM csi_profile WHERE survey_id = :sid"), {"sid": survey_id})}
    rows = []
    for response_id, age, gender, income, division in panel:
        rid = respondent.get(str(response_id))
        if rid is None:
            continue
        a = survey_map.classify_age(age)
        have = own.get(rid, {})
        row = {"respondent_id": rid, **{k: have.get(k) for k in (
            "gender", "age_years", "age_band", "generation", "age_mid", "income_band", "income_mid_k", "census_region")}}
        # a whole group comes from one source: an answered income question keeps
        # its "Prefer not to say" and never gains the panel's midpoint
        if row["gender"] is None:
            row["gender"] = gender
        if all(row[k] is None for k in ("age_years", "age_band", "age_mid")):
            row.update(age_years=a["age"], age_band=a["band"], generation=a["gen"], age_mid=a["mid"])
        if row["income_band"] is None:
            row.update(income_band=income, income_mid_k=survey_map.income_mid_k(income))
        if row["census_region"] is None:
            row["census_region"] = survey_map.census_region_of_division(division)
        rows.append({**row, "sid": survey_id})
    if rows:
        with eng.begin() as conn:
            conn.execute(text("""
                INSERT INTO csi_profile (respondent_id, survey_id, gender, age_years, age_band, generation,
                                         age_mid, income_band, income_mid_k, census_region)
                VALUES (:respondent_id, :sid, :gender, :age_years, :age_band, :generation, :age_mid,
                        :income_band, :income_mid_k, :census_region)
                ON DUPLICATE KEY UPDATE
                    gender = VALUES(gender), age_years = VALUES(age_years), age_band = VALUES(age_band),
                    generation = VALUES(generation), age_mid = VALUES(age_mid), income_band = VALUES(income_band),
                    income_mid_k = VALUES(income_mid_k), census_region = VALUES(census_region)"""), rows)
    return len(rows)


def load_legacy(legacy_id: str) -> int:
    """Load (or reload) one legacy wave. Returns its survey_id."""
    from etl.run_pipeline import _rebuild_profiles, _rebuild_question_bases

    eng = get_engine("etl")
    with eng.connect() as conn:
        title, created = conn.execute(text(
            "SELECT title, date_created FROM dwh_smsurveydetail WHERE id = :lid"),
            {"lid": legacy_id}).one()
        responses = conn.execute(text(
            "SELECT id, response_status, date_filled, total_time_spent FROM dwh_smresponse"
            " WHERE survey_id = :lid ORDER BY id"), {"lid": legacy_id}).all()
        questions, amap, skipped = _definitions(conn, legacy_id)

    completes = sum(1 for r in responses if r[1] == "completed")
    first = min((r[2] for r in responses if r[1] == "completed" and r[2]), default=created)
    wave = str(first)[:10]
    family, study_type = study_for(title, completes)
    platform = "qualtrics" if str(legacy_id).startswith("SV_") else "surveymonkey"
    survey_id = upsert_survey(host=platform, path=legacy_id, title=xp.clean_text(title)[:500],
                              survey_family=family, wave_label=wave, wave_date=wave,
                              platform=platform, source_ref=legacy_id, study_type=study_type)
    run = start_run(survey_id, "manual", "data", f"dwh_stg.dwh_sm*:{legacy_id}")
    fields = load_definitions(survey_id, questions, family)

    respondents = []
    for n, (rid, status, filled, secs) in enumerate(responses, start=1):
        code, label = LEGACY_STATUS.get(status, (None, status))
        respondents.append({
            "sid": survey_id, "rec": n, "uuid": str(rid)[:64], "sc": code,
            "sl": (label or "")[:30] or None, "qual": 1 if status == "completed" else 0,
            "done": filled, "secs": secs,
            "key": hashlib.sha256(str(rid).encode()).hexdigest(), "run": run})
    with eng.begin() as conn:
        if respondents:
            conn.execute(text("""
                INSERT INTO csi_respondent (survey_id, record_no, forsta_uuid, status_code, status_label,
                                            is_qualified, completed_at, interview_secs, respondent_key, load_id)
                VALUES (:sid, :rec, :uuid, :sc, :sl, :qual, :done, :secs, :key, :run)
                ON DUPLICATE KEY UPDATE
                    forsta_uuid = VALUES(forsta_uuid), status_code = VALUES(status_code),
                    status_label = VALUES(status_label), is_qualified = VALUES(is_qualified),
                    completed_at = VALUES(completed_at), interview_secs = VALUES(interview_secs),
                    respondent_key = VALUES(respondent_key), load_id = VALUES(load_id)"""), respondents)
        rows = [{"aid": m["aid"], "fid": fields[m["field"]], "code": m["code"], "label": m["label"][:500],
                 "match": m.get("match")} for m in amap if m["field"] in fields]
        loaded = _move_answers(conn, survey_id, legacy_id, rows)

    with eng.begin() as conn:                   # profiles are rebuilt, never patched
        conn.execute(text("DELETE FROM csi_profile WHERE survey_id = :sid"), {"sid": survey_id})
    _rebuild_profiles(survey_id, None, family)
    if platform == "surveymonkey":
        _panel_profiles(survey_id, legacy_id)
    _rebuild_question_bases(survey_id)
    finish_run(run, len(responses), len(responses))
    log.info("%s -> survey_id=%s wave=%s: %d completes, %d answers, %d questions without answer "
             "rows skipped; harmonised %s", legacy_id, survey_id, wave, completes, loaded, skipped,
             harmonise.harmonise_survey(survey_id))
    log.info("Cube: %d cells", cube.refresh_wave(survey_id))
    return survey_id



def reconcile_legacy(survey_id: int) -> tuple[int, list[str]]:
    """Every loaded count must equal the legacy source: completes, and for each
    mapped answer, the completes who gave it. -> (answers checked, problems)."""
    with get_engine("etl").connect() as conn:
        legacy_id = conn.execute(text("SELECT source_ref FROM csi_survey WHERE survey_id = :s"),
                                 {"s": survey_id}).scalar()
        _, amap, _ = _definitions(conn, legacy_id)
        fields = dict(conn.execute(text(
            "SELECT field_name, field_id FROM csi_field WHERE survey_id = :s"), {"s": survey_id}).all())
        ours = {(f, c): n for f, c, n in conn.execute(text("""
            SELECT a.field_id, a.value_code, COUNT(*) FROM csi_answer a
              JOIN csi_respondent r ON r.respondent_id = a.respondent_id AND r.is_qualified = 1
             WHERE a.survey_id = :s AND a.value_code > 0 GROUP BY a.field_id, a.value_code"""),
            {"s": survey_id})}
        by_answer = conn.execute(text("""
            SELECT x.question_id, x.answer_id, COUNT(DISTINCT x.response_id) FROM dwh_smresponseqa x
              JOIN dwh_smresponse r ON r.id = x.response_id AND r.response_status = 'completed'
             WHERE x.survey_id = :lid GROUP BY x.question_id, x.answer_id"""), {"lid": legacy_id}).all()
        source = {aid: n for _, aid, n in by_answer}
        grids = sorted({m["qid"] for m in amap if m.get("match")})
        if grids:                                    # a matrix cell = column id + "<row> | <column>"
            source.update({(aid, raw): n for aid, raw, n in conn.execute(text("""
                SELECT x.answer_id, x.answer_text, COUNT(DISTINCT x.response_id) FROM dwh_smresponseqa x
                  JOIN dwh_smresponse r ON r.id = x.response_id AND r.response_status = 'completed'
                 WHERE x.survey_id = :lid AND x.question_id IN :g GROUP BY x.answer_id, x.answer_text""")
                .bindparams(bindparam("g", expanding=True)), {"lid": legacy_id, "g": grids})})
        qualified = conn.execute(text(
            "SELECT COUNT(*) FROM csi_respondent WHERE survey_id = :s AND is_qualified = 1"),
            {"s": survey_id}).scalar()
        completes = conn.execute(text(
            "SELECT COUNT(*) FROM dwh_smresponse WHERE survey_id = :lid AND response_status = 'completed'"),
            {"lid": legacy_id}).scalar()
    problems = [] if qualified == completes else [f"completes: ours {qualified}, source {completes}"]
    # One expected count per loaded cell: a matrix cell's text variants
    # ("Amazon | Good", "Amazon  | Good") are one cell, so their counts add.
    expected: dict[tuple, int] = {}
    label_of: dict[tuple, str] = {}
    for m in amap:
        if m["field"] not in fields:
            problems.append(f"{m['qcode']} '{m['label'][:50]}': in the source, not loaded")
            continue
        cell = (fields[m["field"]], m["code"])
        key = (m["aid"], m["match"]) if m.get("match") else m["aid"]
        expected[cell] = expected.get(cell, 0) + source.get(key, 0)
        label_of[cell] = f"{m['qcode']} '{m['label'][:50]}'"
    checked = len(expected)
    problems += [f"{label_of[cell]}: ours {ours.get(cell, 0)}, source {want}"
                 for cell, want in expected.items() if ours.get(cell, 0) != want]
    # a choice question with answers in the source but nothing loaded at all
    with get_engine("etl").connect() as conn:
        listed = {r[0] for r in conn.execute(text(
            "SELECT DISTINCT question_id FROM dwh_smanswer WHERE survey_id = :lid"), {"lid": legacy_id})}
    answered = {}
    for qid, _, n in by_answer:
        answered[qid] = answered.get(qid, 0) + n
    problems += [f"question {qid}: {n} source answers, not loaded"
                 for qid, n in sorted(answered.items()) if qid in listed and qid not in {m["qid"] for m in amap}]
    # completed source rows of a loaded question whose answer nothing maps
    loaded, mapped = {m["qid"] for m in amap}, {m["aid"] for m in amap}
    problems += [f"unmapped source answer {aid} of question {qid}: {n} completes"
                 for qid, aid, n in by_answer if qid in loaded and aid not in mapped]
    return checked, problems

def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s | %(message)s")
    ap = argparse.ArgumentParser(description="Load legacy (dwh_sm*) surveys into CSI")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--id", help="one legacy survey id")
    group.add_argument("--all", action="store_true", help="every wave of the era, oldest first")
    ap.add_argument("--era", choices=("qualtrics", "surveymonkey"), default="qualtrics")
    args = ap.parse_args()
    if args.id:
        load_legacy(args.id)
        return 0
    with get_engine("etl").connect() as conn:
        surveys = legacy_surveys(conn, era=args.era)
    failed = []
    for n, s in enumerate(surveys, start=1):
        log.info("[%d/%d] %s %s", n, len(surveys), s["id"], s["title"][:60])
        try:
            load_legacy(s["id"])
        except Exception:                        # one bad wave must not stop the other 144
            log.exception("%s failed — continuing; rerun it with --id", s["id"])
            failed.append(s["id"])
    if failed:
        log.error("%d of %d waves failed: %s", len(failed), len(surveys), ", ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
