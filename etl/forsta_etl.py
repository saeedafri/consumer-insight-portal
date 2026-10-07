"""The Forsta pipeline: discover → load → verify → publish → derive.

Forsta (Decipher) is the source from Oct 2026. Every weekly wave of the
consumer tracker is its own survey (selfserve/58f/YYMMNN), launched on a
Monday, fielded for ~13 hours, closed the same night. Annual trackers
(Holiday, Amazon Apparel, Online Grocery, Back-to-school) and client studies
come the same way. Forsta hibernates a survey after ~3–4 months (it then
answers 428 until reactivated) and deletes it after 365 days — so every wave is
loaded as soon as it closes, and the warehouse is the record.

    python -m etl.forsta_etl --discover          # refresh the register (cip_forsta_survey)
    python -m etl.forsta_etl --due               # discover, then load every closed, readable, unloaded wave
    python -m etl.forsta_etl --survey selfserve/58f/260907
    python -m etl.forsta_etl --reconcile         # every loaded Forsta wave vs the API
    python -m etl.forsta_etl --reindex           # rebuild the search index of every verified wave

The API's codes are written as codes — no label round trip (a bipolar grid's
answers have no labels at all). Personal fields never reach the database:
the browser string, link, session and fingerprint are dropped; the panel id is
kept only as a sha256 (respondent_key). Forsta is only ever read (GET).
"""
from __future__ import annotations

import argparse
import hashlib
import logging
import math
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import bindparam, text

from app.core.config import config
from app.core.database import get_engine
from app.data import cube, harmonise
from etl import forsta_api
from etl.forsta_client import ForstaError
from etl.loaders import finish_run, index_survey, load_definitions, start_run, upsert_survey
from etl.run_pipeline import _dt, _rebuild_profiles, _rebuild_question_bases, wave_from_records

log = logging.getLogger("cip.forsta")

TRACKER_FAMILY = "CSI-US"
_CHUNK = 5000                       # answer rows per batched INSERT


# ── the register ───────────────────────────────────────────────────────────
def study_type(meta: dict) -> str:
    tags = {str(t).lower() for t in meta.get("tags") or []}
    if "weekly consumer tracker" in tags or str(meta.get("title", "")).lower().startswith("shopping and spending"):
        return "tracker"
    return "annual" if "annual tracker" in tags else "adhoc"


def family(meta: dict) -> str:
    """Waves of one study share a family, so they trend together: the weekly
    tracker is CSI-US; an annual study drops its year ("Holiday Shopping 2026")."""
    if study_type(meta) == "tracker":
        return TRACKER_FAMILY
    name = re.sub(r"\b(19|20)\d{2}\b", "", str(meta.get("title", "")))
    return re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_")[:60] or "ADHOC"


def _when(value: Any) -> Optional[datetime]:
    if not value:
        return None
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)


def discover(client) -> dict[str, int]:
    """Upsert every survey the key can see into cip_forsta_survey and decide
    what to do with it: due (closed, readable, not loaded), hibernated,
    testing, loaded, failed. Returns how many surveys are in each state."""
    eng = get_engine("etl")
    with eng.connect() as conn:
        known = {p: (state, sid, str(closed or "")[:19], total) for p, state, sid, closed, total in conn.execute(text(
            "SELECT forsta_path, load_state, survey_id, closed_at, total_n FROM cip_forsta_survey"))}
    rows = []
    for m in client.surveys():
        path = str(m["path"]).strip("/")
        previous, survey_id, closed, total = known.get(path, (None, None, "", None))
        closed_now = _when(m.get("closedDate"))
        reopened = (closed_now and str(closed_now)[:19] != closed) or (m.get("total") not in (None, total))
        if previous == "loaded" and not reopened:
            state = "loaded"
        elif m.get("state") != "closed":
            state = "testing"
        elif m.get("hibernated"):
            state = "hibernated"
        else:
            state = "failed" if previous == "failed" else "due"
        rows.append({"path": path, "title": str(m.get("title", ""))[:500], "fstate": str(m.get("state", ""))[:30],
                     "hib": 1 if m.get("hibernated") else 0, "tags": ", ".join(m.get("tags") or [])[:500],
                     "stype": study_type(m), "created": _when(m.get("createdOn")),
                     "launched": _when(m.get("dateLaunched")), "closed": _when(m.get("closedDate")),
                     "qn": m.get("qualified"), "tn": m.get("total"), "seen": datetime.now(timezone.utc).replace(tzinfo=None),
                     "lstate": state, "sid": survey_id})
    if rows:
        with eng.begin() as conn:
            conn.execute(text("""
                INSERT INTO cip_forsta_survey (forsta_path, title, state, hibernated, tags, study_type, created_on,
                    launched_at, closed_at, qualified_n, total_n, last_seen, load_state, survey_id)
                VALUES (:path, :title, :fstate, :hib, :tags, :stype, :created, :launched, :closed, :qn, :tn, :seen,
                        :lstate, :sid)
                ON DUPLICATE KEY UPDATE
                    title = VALUES(title), state = VALUES(state), hibernated = VALUES(hibernated), tags = VALUES(tags),
                    study_type = VALUES(study_type), created_on = VALUES(created_on),
                    launched_at = VALUES(launched_at), closed_at = VALUES(closed_at),
                    qualified_n = VALUES(qualified_n), total_n = VALUES(total_n), last_seen = VALUES(last_seen),
                    load_state = VALUES(load_state)"""), rows)
    return dict(Counter(r["lstate"] for r in rows))


def _meta(client, path: str) -> dict:
    return next((m for m in client.surveys() if str(m["path"]).strip("/") == path), {"path": path, "title": path})


def _mark(path: str, state: str, survey_id: Optional[int] = None, error: Optional[str] = None) -> None:
    with get_engine("etl").begin() as conn:
        conn.execute(text(
            "UPDATE cip_forsta_survey SET load_state = :st, last_error = :err,"
            " survey_id = COALESCE(:sid, survey_id), loaded_at = CASE WHEN :st = 'loaded' THEN :now ELSE loaded_at END"
            " WHERE forsta_path = :p"),
            {"st": state, "err": (error or None) and error[:1000], "sid": survey_id, "now": datetime.now(timezone.utc).replace(tzinfo=None), "p": path})


# ── one wave ───────────────────────────────────────────────────────────────
def _number(value: Any) -> Optional[float]:
    """A number cip_answer.value_number (DECIMAL(18,4)) can hold, else None."""
    try:
        number = float(str(value).strip())
    except ValueError:
        return None
    return number if math.isfinite(number) and abs(number) < 1e14 else None


def _set_status(survey_id: int, status: str) -> None:
    with get_engine("etl").begin() as conn:
        conn.execute(text("UPDATE cip_survey SET load_status = :st WHERE survey_id = :s"),
                     {"st": status, "s": survey_id})


def _fields(conn, survey_id: int) -> dict[str, dict]:
    """field name → how to store its value: kind (code / numeric / text) and,
    for coded fields, the label of each code."""
    fields = {}
    for fid, name, vtype, is_multi, item_label, qid in conn.execute(text("""
            SELECT f.field_id, f.field_name, f.value_type, q.is_multi, i.item_label, q.question_id
              FROM cip_field f JOIN cip_question q ON q.question_id = f.question_id
              LEFT JOIN cip_item i ON i.item_id = f.item_id
             WHERE f.survey_id = :s"""), {"s": survey_id}):
        fields[name] = {"id": fid, "kind": vtype, "multi": bool(is_multi), "item": item_label, "qid": qid}
    labels: dict[int, dict[int, str]] = {}
    for qid, code, label in conn.execute(text(
            "SELECT o.question_id, o.value_code, o.value_label FROM cip_option o JOIN cip_question q"
            " ON q.question_id = o.question_id WHERE q.survey_id = :s"), {"s": survey_id}):
        labels.setdefault(qid, {})[int(code)] = label
    for f in fields.values():
        f["labels"] = labels.get(f["qid"], {})
    return fields


def _answer(field: dict, value: Any) -> Optional[dict]:
    """One stored answer from one API value — None when there is nothing to store."""
    if value is None or str(value).strip() == "":
        return None
    if field["kind"] == "numeric":
        number = _number(value)
        return None if number is None else {"code": None, "label": None, "num": number, "txt": None}
    if field["kind"] == "text":
        return {"code": None, "label": None, "num": None, "txt": str(value)}
    code = forsta_api.whole(value)
    if code is None:
        return {"code": None, "label": str(value)[:500], "num": None, "txt": None}
    label = field["item"] if field["multi"] else field["labels"].get(code)
    return {"code": code, "label": (label or None) and label[:500], "num": None, "txt": None}


def _cut(value: Any, limit: int) -> Optional[str]:
    return str(value)[:limit] if value not in (None, "") else None


def _respondent(survey_id: int, rec: dict, run: int) -> dict:
    status = forsta_api.whole(rec.get("status"))
    seconds = _number(rec.get("qtime"))
    return {"sid": survey_id, "rec": forsta_api.whole(rec.get("record")) or 0, "uuid": str(rec.get("uuid") or "")[:64],
            "sc": status, "sl": forsta_api.STATUS.get(status), "qual": 1 if status == 3 else 0,
            "done": _dt(rec.get("date")), "secs": int(seconds) if seconds is not None else None,
            "markers": _cut(rec.get("markers"), 1000), "dev": _cut(rec.get("vmobiledevice"), 50),
            "os": _cut(rec.get("vos"), 50), "br": _cut(rec.get("vbrowser"), 50), "drop": _cut(rec.get("vdropout"), 50),
            "src": _cut(rec.get("vlist") or rec.get("list"), 100),
            "key": hashlib.sha256(str(rec["RID"]).encode()).hexdigest() if rec.get("RID") else None, "run": run}


def load_survey(client, path: str) -> int:
    """Load (or reload) one Forsta survey as one wave. Returns its survey_id.

    Invisible while it loads (load_status = loading); visible only once every
    respondent and every answer is proven equal to the payload."""
    path = path.strip("/")
    meta = _meta(client, path)
    datamap = client.survey_datamap(path)
    questions = forsta_api.questions_from_datamap(datamap)
    records = [r for r in client.survey_data(path) if r.get("uuid")]
    eng = get_engine("etl")
    with eng.connect() as conn:                   # a reload keeps its wave, even if the first date moved
        existing = conn.execute(text(
            "SELECT wave_label, load_status FROM cip_survey WHERE platform = 'forsta' AND source_ref = :p"
            " ORDER BY survey_id LIMIT 1"), {"p": path}).first()
    qualified = [r for r in records if forsta_api.whole(r.get("status")) == 3] or records
    wave = existing.wave_label if existing else wave_from_records(qualified)
    previous = existing.load_status if existing else None
    kind, fam = study_type(meta), family(meta)

    survey_id = upsert_survey(host=getattr(client, "host", config.forsta.host), path=path,
                              title=str(meta.get("title") or path)[:500], survey_family=fam, wave_label=wave,
                              wave_date=wave, datamap_payload=datamap, platform="forsta", source_ref=path,
                              study_type=kind)
    with eng.begin() as conn:
        conn.execute(text(
            "UPDATE cip_survey SET load_status = 'loading', sample_source = :src, total_n = :tn, tags = :tags,"
            " field_start = :fs, field_end = :fe WHERE survey_id = :s"),
            {"src": ", ".join(str(x) for x in meta.get("sampleSources") or []) or None,
             "tn": meta.get("total") or len(records), "tags": ", ".join(meta.get("tags") or [])[:500] or None,
             "fs": _when(meta.get("dateLaunched")), "fe": _when(meta.get("closedDate")), "s": survey_id})
    run = start_run(survey_id, "api", "data", f"forsta:{path}")
    written = None
    try:
        load_definitions(survey_id, questions, fam)
        written = _write(survey_id, records, run)
        problems = verify(survey_id, datamap, records)
        if problems:
            raise RuntimeError(f"{path} does not match its payload: {problems[:5]}")
        _rebuild_profiles(survey_id, None, fam)
        _rebuild_question_bases(survey_id)
        log.info("%s → survey_id %s (%s): %d respondents; harmonised %s; cube %d cells", path, survey_id, wave,
                 len(records), harmonise.harmonise_survey(survey_id), cube.refresh_wave(survey_id))
        index_survey(survey_id)
    except Exception as exc:
        finish_run(run, len(records), written or 0, error=str(exc)[:2000])
        # the answers write is one transaction: if it never committed, a verified wave is still intact
        _set_status(survey_id, "verified" if written is None and previous == "verified" else "failed")
        raise
    finish_run(run, len(records), written)
    _set_status(survey_id, "verified")
    _mark(path, "loaded", survey_id)
    return survey_id


def _write(survey_id: int, records: list[dict], run: int) -> int:
    """Respondents (one batched upsert) and answers (deleted, then batched
    inserts) — a constant number of round trips per wave, whatever its size."""
    eng = get_engine("etl")
    with eng.begin() as conn:
        people = [_respondent(survey_id, r, run) for r in records]
        conn.execute(text("""
            INSERT INTO cip_respondent (survey_id, record_no, forsta_uuid, status_code, status_label, is_qualified,
                completed_at, interview_secs, markers, device, os, browser, dropout_qcode, panel_source,
                respondent_key, load_id)
            VALUES (:sid, :rec, :uuid, :sc, :sl, :qual, :done, :secs, :markers, :dev, :os, :br, :drop, :src, :key, :run)
            ON DUPLICATE KEY UPDATE
                forsta_uuid = VALUES(forsta_uuid), status_code = VALUES(status_code),
                status_label = VALUES(status_label), is_qualified = VALUES(is_qualified),
                completed_at = VALUES(completed_at), interview_secs = VALUES(interview_secs),
                markers = VALUES(markers), device = VALUES(device), os = VALUES(os), browser = VALUES(browser),
                dropout_qcode = VALUES(dropout_qcode), panel_source = VALUES(panel_source),
                respondent_key = VALUES(respondent_key), sample_rid = NULL, load_id = VALUES(load_id)"""), people)
        ids = dict(conn.execute(text("SELECT forsta_uuid, respondent_id FROM cip_respondent WHERE survey_id = :s"),
                                {"s": survey_id}).all())
        sent = {p["uuid"] for p in people}
        gone = [rid for uuid, rid in ids.items() if uuid not in sent]   # removed in Forsta since the last load
        if gone:
            conn.execute(text("DELETE FROM cip_answer WHERE survey_id = :s"), {"s": survey_id})
            for table in ("cip_respondent_cohort", "cip_profile", "cip_respondent"):
                conn.execute(text(f"DELETE FROM {table} WHERE respondent_id IN :ids")
                             .bindparams(bindparam("ids", expanding=True)), {"ids": gone})
        fields = _fields(conn, survey_id)
        rows = []
        for rec in records:
            rid = ids[str(rec["uuid"])[:64]]
            for name, value in rec.items():
                field = fields.get(name)
                stored = field and _answer(field, value)
                if stored:
                    rows.append({"rid": rid, "sid": survey_id, "fid": field["id"], **stored})
        conn.execute(text("DELETE FROM cip_answer WHERE survey_id = :s"), {"s": survey_id})
        statement = text("INSERT INTO cip_answer (respondent_id, survey_id, field_id, value_code, value_label,"
                         " value_number, value_text) VALUES (:rid, :sid, :fid, :code, :label, :num, :txt)")
        for i in range(0, len(rows), _CHUNK):
            conn.execute(statement, rows[i:i + _CHUNK])
    return len(people)


def verify(survey_id: int, datamap: dict, records: list[dict]) -> list[str]:
    """Every record a respondent, every datamap variable a field, every field
    exactly as many answers as the payload carries."""
    with get_engine("etl").connect() as conn:
        stored_people = conn.execute(text("SELECT COUNT(*) FROM cip_respondent WHERE survey_id = :s"),
                                     {"s": survey_id}).scalar()
        fields = {n for (n,) in conn.execute(text("SELECT field_name FROM cip_field WHERE survey_id = :s"),
                                             {"s": survey_id})}
        stored = dict(conn.execute(text(
            "SELECT f.field_name, COUNT(*) FROM cip_answer a JOIN cip_field f ON f.field_id = a.field_id"
            " WHERE a.survey_id = :s GROUP BY f.field_name"), {"s": survey_id}).all())
    problems = [] if stored_people == len(records) else [f"respondents: {stored_people} stored, {len(records)} sent"]
    variables = {str(v["label"]) for q in datamap.get("questions", []) for v in q.get("variables") or []
                 if v.get("label") and v["label"] not in forsta_api.PERSONAL}
    problems += [f"datamap variable {v} has no field" for v in sorted(variables - fields)]
    sent = Counter(k for r in records for k, v in r.items() if k in fields and v is not None and str(v).strip() != "")
    problems += [f"{f}: {n} sent, {stored.get(f, 0)} stored" for f, n in sorted(sent.items()) if stored.get(f, 0) != n]
    return problems


def reconcile_survey(survey_id: int, client=None) -> tuple[int, list[str]]:
    """Re-read the wave from Forsta (GET) and compare every stored answer."""
    client = client or _client()
    with get_engine("etl").connect() as conn:
        path = conn.execute(text("SELECT source_ref FROM cip_survey WHERE survey_id = :s"), {"s": survey_id}).scalar()
        fields = _fields(conn, survey_id)
        stored = {(u, f): (c, n, t) for u, f, c, n, t in conn.execute(text("""
            SELECT r.forsta_uuid, f.field_name, a.value_code, a.value_number, a.value_text FROM cip_answer a
              JOIN cip_field f ON f.field_id = a.field_id JOIN cip_respondent r ON r.respondent_id = a.respondent_id
             WHERE a.survey_id = :s"""), {"s": survey_id})}
    checked, problems = 0, []
    try:
        records = client.survey_data(path)
    except ForstaError as exc:                    # 428 = hibernated: nothing to compare against until reactivated
        log.warning("survey_id %s (%s) not checked: %s", survey_id, path, exc)
        return 0, []
    for rec in records:
        for name, value in rec.items():
            field = fields.get(name)
            want = field and _answer(field, value)
            if not want:
                continue
            checked += 1
            got = stored.get((str(rec.get("uuid")), name))
            same = got is not None and (
                (want["code"] is not None and got[0] == want["code"]) or
                (want["num"] is not None and got[1] is not None and round(float(got[1]), 4) == round(want["num"], 4)) or
                (want["txt"] is not None and got[2] == want["txt"]) or
                (want["code"] is None and want["num"] is None and want["txt"] is None))
            if not same and len(problems) < 200:
                problems.append(f"{rec.get('uuid')} {name}: Forsta {value!r}, stored {got}")
    return checked, problems


# ── the run ────────────────────────────────────────────────────────────────
def run_due(client) -> dict[str, list[str]]:
    """Load every due (and previously failed) wave, oldest first; a failure is
    recorded and the run carries on."""
    with get_engine("etl").connect() as conn:
        due = [p for (p,) in conn.execute(text(
            "SELECT forsta_path FROM cip_forsta_survey WHERE load_state IN ('due', 'failed')"
            " ORDER BY closed_at, forsta_path"))]
    result: dict[str, list[str]] = {"loaded": [], "failed": []}
    for path in due:
        try:
            load_survey(client, path)
            result["loaded"].append(path)
        except Exception as exc:                 # recorded in the register and the load log
            log.exception("%s failed", path)
            _mark(path, "failed", error=str(exc))
            result["failed"].append(path)
    return result


def _client():
    from etl.forsta_client import ForstaClient
    fc = config.forsta
    return ForstaClient(fc.host, fc.api_key, fc.timeout, fc.max_retries)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s | %(message)s")
    ap = argparse.ArgumentParser(description="Forsta → CIP pipeline (reads Forsta, never writes it)")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--discover", action="store_true")
    group.add_argument("--due", action="store_true")
    group.add_argument("--survey")
    group.add_argument("--reconcile", action="store_true")
    group.add_argument("--reindex", action="store_true")
    args = ap.parse_args()
    if args.reindex:
        with get_engine("etl").connect() as conn:
            ids = [s for (s,) in conn.execute(text("SELECT survey_id FROM cip_survey WHERE load_status = 'verified'"))]
        for sid in ids:
            index_survey(sid)
        log.info("Indexed %d waves", len(ids))
        return 0
    client = _client()
    if args.discover:
        log.info("Register: %s", discover(client))
    elif args.survey:
        try:
            load_survey(client, args.survey)
        except Exception as exc:
            _mark(args.survey.strip("/"), "failed", error=str(exc))
            raise
    elif args.due:
        log.info("Register: %s", discover(client))
        result = run_due(client)
        log.info("Loaded %d, failed %d: %s", len(result["loaded"]), len(result["failed"]), result["failed"])
        return 1 if result["failed"] else 0
    else:
        with get_engine("etl").connect() as conn:
            ids = [s for (s,) in conn.execute(text(
                "SELECT survey_id FROM cip_survey WHERE platform = 'forsta' AND load_status = 'verified'"))]
        bad = 0
        for sid in ids:
            checked, problems = reconcile_survey(sid, client)
            bad += len(problems)
            log.info("survey_id %s: %d answers checked, %d differ %s", sid, checked, len(problems), problems[:3])
        return 1 if bad else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
