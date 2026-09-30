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

from sqlalchemy import text

from app.core.database import get_engine
from app.data import harmonise
from etl import excel_parsers as xp
from etl.loaders import finish_run, load_definitions, start_run, upsert_survey

log = logging.getLogger("cip.legacy")

LEGACY_STATUS = {"completed": (3, "Qualified"), "partial": (4, "Partial"),
                 "disqualified": (1, "Terminated"), "overquota": (2, "Overquota")}
_MULTI_WORDING = re.compile(r"select all|all that apply|select up to|select (two|three)", re.I)
_TRACKER = re.compile(r"^\s*shopping(,| and)\s+spending", re.I)


def legacy_qtype(family: Optional[str], title: str, max_per_response: Optional[int],
                 n_answers: int) -> Optional[str]:
    if max_per_response is None or family == "matrix":
        return None
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


def _definitions(conn, legacy_id: str):
    """-> (ParsedQuestions, answer map rows, skipped question count)."""
    questions = conn.execute(text(
        "SELECT id, family, title, srt1, srt2 FROM dwh_smquestion WHERE survey_id = :lid"
        " ORDER BY srt1, srt2, id"), {"lid": legacy_id}).all()
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
        qcode = f"Q{(srt1 or 0) + 1}" + (f"_{srt2}" if srt2 else "")
        while qcode in seen:
            qcode += "b"
        seen.add(qcode)
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


def _move_answers(conn, survey_id: int, legacy_id: str, rows: list[dict]) -> int:
    """Replace the wave's answers from dwh_smresponseqa, inside MySQL.

    The two maps are temp tables cloned from the legacy tables (WHERE 1 = 0)
    so their id columns carry the legacy collation — csi_* uses another, and
    comparing the two directly fails with "Illegal mix of collations"."""
    conn.execute(text("CREATE TEMPORARY TABLE IF NOT EXISTS csi_tmp_answer_map AS"
                      " SELECT id AS answer_id, CAST(0 AS SIGNED) AS field_id, CAST(0 AS SIGNED) AS value_code,"
                      " title AS value_label FROM dwh_smanswer WHERE 1 = 0"))
    conn.execute(text("CREATE TEMPORARY TABLE IF NOT EXISTS csi_tmp_response_map AS"
                      " SELECT id AS response_id, CAST(0 AS SIGNED) AS respondent_id"
                      " FROM dwh_smresponse WHERE 1 = 0"))
    conn.execute(text("DELETE FROM csi_tmp_answer_map"))
    conn.execute(text("DELETE FROM csi_tmp_response_map"))
    if rows:
        conn.execute(text("INSERT INTO csi_tmp_answer_map (answer_id, field_id, value_code, value_label)"
                          " VALUES (:aid, :fid, :code, :label)"), rows)
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
        rows = [{"aid": m["aid"], "fid": fields[m["field"]], "code": m["code"], "label": m["label"][:500]}
                for m in amap if m["field"] in fields]
        loaded = _move_answers(conn, survey_id, legacy_id, rows)

    _rebuild_profiles(survey_id, None, family)
    _rebuild_question_bases(survey_id)
    finish_run(run, len(responses), len(responses))
    log.info("%s -> survey_id=%s wave=%s: %d completes, %d answers, %d questions without answer "
             "rows skipped; harmonised %s", legacy_id, survey_id, wave, completes, loaded, skipped,
             harmonise.harmonise_survey(survey_id))
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
        qualified = conn.execute(text(
            "SELECT COUNT(*) FROM csi_respondent WHERE survey_id = :s AND is_qualified = 1"),
            {"s": survey_id}).scalar()
        completes = conn.execute(text(
            "SELECT COUNT(*) FROM dwh_smresponse WHERE survey_id = :lid AND response_status = 'completed'"),
            {"lid": legacy_id}).scalar()
    problems = [] if qualified == completes else [f"completes: ours {qualified}, source {completes}"]
    checked = 0
    for m in amap:
        if m["field"] not in fields:
            problems.append(f"{m['qcode']} '{m['label'][:50]}': in the source, not loaded")
            continue
        checked += 1
        got, want = ours.get((fields[m["field"]], m["code"]), 0), source.get(m["aid"], 0)
        if got != want:
            problems.append(f"{m['qcode']} '{m['label'][:50]}': ours {got}, source {want}")
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
    group.add_argument("--all", action="store_true", help="every Qualtrics-era wave, oldest first")
    args = ap.parse_args()
    if args.id:
        load_legacy(args.id)
        return 0
    with get_engine("etl").connect() as conn:
        surveys = legacy_surveys(conn)
    for n, s in enumerate(surveys, start=1):
        log.info("[%d/%d] %s %s", n, len(surveys), s["id"], s["title"][:60])
        load_legacy(s["id"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
