"""CSI ingestion pipeline.

    python -m etl.run_pipeline --source api    --wave 2026-09
    python -m etl.run_pipeline --source excel  --raw "Raw Data 09_21_26.xlsx" \
                               --crosstab "Cross Tabs 09_21_26.xlsx" --wave 2026-09

Both sources produce the same rows. `api` is the target state; `excel` is the
bridge that works today, before the Forsta API key is issued.
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from types import SimpleNamespace
from typing import Any, Optional

from sqlalchemy import bindparam, text

from app.core.config import config
from app.core.database import execute_many, get_engine
from etl import excel_parsers as xp
from etl import survey_map
from etl.loaders import finish_run, load_definitions, start_run, upsert_survey

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s | %(message)s"
)
log = logging.getLogger("cip.pipeline")

STATUS_MAP = {"Terminated": 1, "Overquota": 2, "Qualified": 3, "Partial": 4}


# ═══════════════════════════════════════════════════════════════════════════
def ingest_excel(raw_path: str, crosstab_path: Optional[str], wave: Optional[str],
                 family: str = "CSI-US") -> None:
    questions = xp.parse_datamap(raw_path)
    log.info("Parsed %d question blocks from the datamap", len(questions))

    title = next((q.qtext for q in questions if q.qcode == "record"), "Coresight survey")
    survey_id = upsert_survey(
        host=config.forsta.host,
        path=config.forsta.survey_path or f"excel::{raw_path}",
        title=f"{family} {wave or ''}".strip(),
        survey_family=family,
        wave_label=wave,
        wave_date=f"{wave}-01" if wave and len(wave) == 7 else None,
    )
    log.info("survey_id=%s", survey_id)

    run = start_run(survey_id, "excel", "datamap", raw_path)
    var_map = load_definitions(survey_id, questions, family)
    finish_run(run, len(questions), len(var_map))
    log.info("Loaded %d variables", len(var_map))

    code_map = _code_lookup(survey_id)
    run = start_run(survey_id, "excel", "data", raw_path)
    read = loaded = 0
    for record in xp.iter_raw_records(raw_path):
        read += 1
        loaded += _load_one_respondent(survey_id, record, var_map, run, code_map)
    finish_run(run, read, loaded)
    log.info("Loaded %d/%d respondents", loaded, read)

    _rebuild_profiles(survey_id, questions, family)
    _rebuild_question_bases(survey_id)

    if crosstab_path:
        ingest_crosstabs(survey_id, crosstab_path)


def _code_lookup(survey_id: int) -> dict[int, dict[str, int]]:
    """field_id -> {answer label: code}, for every question that is not a
    0/1 multi-punch.

    The Forsta export we receive is in LABEL format: a single-punch cell holds
    "Yes", not 1. Running it through the multi-punch rule would stamp every
    answered cell with code 1 — which silently makes "BNPL users" 404 people
    instead of 133, and every single-punch filter useless. The datamap already
    carries the dictionary, so the label is resolved back to its code here.
    """
    with get_engine("etl").connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT f.field_id, o.value_label, o.value_code
                  FROM csi_field  f
                  JOIN csi_question q ON q.question_id = f.question_id
                  JOIN csi_option   o ON o.question_id = q.question_id
                 WHERE f.survey_id = :sid AND q.is_multi = 0
                """
            ),
            {"sid": survey_id},
        ).all()
    lookup: dict[int, dict[str, int]] = {}
    for field_id, label, code in rows:
        lookup.setdefault(int(field_id), {})[str(label).strip().lower()] = int(code)
    return lookup


def _load_one_respondent(survey_id: int, rec: dict[str, Any], var_map: dict[str, int],
                         run_id: int, code_map: Optional[dict[int, dict[str, int]]] = None) -> int:
    status_label = str(rec.get("status") or "").strip()
    status_code = STATUS_MAP.get(status_label)
    with get_engine("etl").begin() as conn:
        res = conn.execute(
            text(
                """
                INSERT INTO csi_respondent
                    (survey_id, record_no, forsta_uuid, status_code, status_label,
                     is_qualified, completed_at, interview_secs, panel_source, sample_rid,
                     markers, device, os, browser, dropout_qcode,
                     load_id)
                VALUES (:sid, :rec, :uuid, :sc, :sl, :qual, :done, :secs, :src, :rid,
                        :markers, :dev, :os, :br, :drop, :run)
                ON DUPLICATE KEY UPDATE
                    status_code = VALUES(status_code), status_label = VALUES(status_label),
                    is_qualified = VALUES(is_qualified), completed_at = VALUES(completed_at),
                    interview_secs = VALUES(interview_secs),
                    load_id = VALUES(load_id),
                    respondent_id = LAST_INSERT_ID(respondent_id)
                """
            ),
            {
                "sid": survey_id,
                "rec": _int(rec.get("record")) or 0,
                "uuid": _str(rec.get("uuid"), 64),
                "sc": status_code,
                "sl": status_label[:30] or None,
                "qual": 1 if status_code == 3 else 0,
                "done": _dt(rec.get("date")),
                "secs": _int(rec.get("qtime")),
                "src": _str(rec.get("source"), 100),
                "rid": _str(rec.get("RID"), 100),
                "markers": _str(rec.get("markers"), 1000),
                "dev": _str(rec.get("vmobiledevice"), 50),
                "os": _str(rec.get("vos"), 100),
                "br": _str(rec.get("vbrowser"), 100),
                "drop": _str(rec.get("vdropout"), 50),
                "run": run_id,
            },
        )
        respondent_id = conn.execute(
            text("SELECT respondent_id FROM csi_respondent "
                 "WHERE survey_id = :sid AND record_no = :rec"),
            {"sid": survey_id, "rec": _int(rec.get("record")) or 0},
        ).scalar()

        payload = []
        for column, value in rec.items():
            vid = var_map.get(column)
            if vid is None or value is None:
                continue
            code, label = xp.normalise_label_cell(value)
            # Single-punch and grid cells carry a scale label, not 0/1 — resolve
            # it back to the datamap's code so filters and ordering work.
            choices = (code_map or {}).get(vid)
            if choices is not None and label is not None:
                code = choices.get(label.strip().lower())
            payload.append(
                {
                    "rid": respondent_id, "sid": survey_id, "vid": vid,
                    "code": code, "label": (label or "")[:500] or None,
                    "num": _float(value), "txt": None,
                }
            )
        if payload:
            conn.execute(
                text(
                    """
                    INSERT INTO csi_answer
                        (respondent_id, survey_id, field_id, value_code,
                         value_label, value_number, value_text)
                    VALUES (:rid, :sid, :vid, :code, :label, :num, :txt)
                    ON DUPLICATE KEY UPDATE
                        value_code = VALUES(value_code), value_label = VALUES(value_label),
                        value_number = VALUES(value_number), value_text = VALUES(value_text)
                    """
                ),
                payload,
            )
    return 1


def _rebuild_profiles(survey_id: int, questions: Optional[list] = None,
                      family: Optional[str] = None) -> None:
    """Flatten the demographic questions into csi_profile.

    Which question supplies which cut is resolved per survey — from
    config/survey_map.yml when the family is known, otherwise auto-detected
    from the question wording. The decision is written to csi_profile_map so
    it is visible, auditable and correctable without touching code.

    A dimension that cannot be resolved is simply absent: the column stays
    NULL and the portal hides that filter rather than failing.
    """
    eng = get_engine("etl")

    if questions is None:
        with eng.connect() as conn:
            rows = conn.execute(
                text("SELECT qcode, qtext FROM csi_question WHERE survey_id = :sid"),
                {"sid": survey_id},
            ).all()
        questions = [SimpleNamespace(qcode=r[0], qtext=r[1]) for r in rows]

    mapping = survey_map.resolve_profile_map(questions, family)
    if not mapping:
        log.warning("No demographic questions resolved for survey_id=%s — "
                    "profile filters will be empty", survey_id)
        return

    explicit = (survey_map.load_config().get("profile") or {}).get(family or "", {})
    with eng.begin() as conn:
        for dimension, qcode in mapping.items():
            conn.execute(
                text(
                    """
                    INSERT INTO csi_profile_map (survey_id, dimension, qcode, resolved_by)
                    VALUES (:sid, :dim, :qcode, :how)
                    ON DUPLICATE KEY UPDATE
                        qcode = VALUES(qcode), resolved_by = VALUES(resolved_by)
                    """
                ),
                {"sid": survey_id, "dim": dimension, "qcode": qcode,
                 "how": "config" if explicit.get(dimension) == qcode else "detected"},
            )
    log.info("Profile mapping for survey_id=%s: %s", survey_id,
             ", ".join(f"{k}<-{v}" for k, v in sorted(mapping.items())))

    # Pull one row per respondent across only the mapped fields.
    wanted = list(mapping.values())
    with eng.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT a.respondent_id, f.field_name, a.value_label
                  FROM csi_answer a
                  JOIN csi_field f ON f.field_id = a.field_id
                 WHERE a.survey_id = :sid AND f.field_name IN :names
                """
            ).bindparams(bindparam("names", expanding=True)),
            {"sid": survey_id, "names": wanted},
        ).all()

    by_respondent: dict[int, dict[str, Any]] = {}
    inverse = {v: k for k, v in mapping.items()}
    for respondent_id, field_name, value in rows:
        by_respondent.setdefault(respondent_id, {})[inverse[field_name]] = value

    payload = []
    for respondent_id, values in by_respondent.items():
        age = survey_map.parse_age(values.get("age"))
        state = values.get("state_name")
        payload.append({
            "rid": respondent_id, "sid": survey_id,
            "gender": values.get("gender"),
            "age": age,
            "band": survey_map.age_band(age),
            "gen": survey_map.generation(age),
            "rel": values.get("relationship"),
            "eth": values.get("ethnicity"),
            "inc": values.get("income_band"),
            "urb": values.get("urbanicity"),
            "pol": values.get("political"),
            "state": state,
            "region": survey_map.census_region(state),
            "oi": values.get("outlook_income"),
            "oe": values.get("outlook_economy"),
        })

    if payload:
        execute_many(
            """
            INSERT INTO csi_profile
                (respondent_id, survey_id, gender, age_years, age_band, generation,
                 relationship, ethnicity, income_band, urbanicity, political,
                 state_name, census_region, outlook_income, outlook_economy)
            VALUES (:rid, :sid, :gender, :age, :band, :gen, :rel, :eth, :inc,
                    :urb, :pol, :state, :region, :oi, :oe)
            ON DUPLICATE KEY UPDATE
                gender = VALUES(gender), age_years = VALUES(age_years),
                age_band = VALUES(age_band), generation = VALUES(generation),
                relationship = VALUES(relationship), ethnicity = VALUES(ethnicity),
                income_band = VALUES(income_band), urbanicity = VALUES(urbanicity),
                political = VALUES(political), state_name = VALUES(state_name),
                census_region = VALUES(census_region),
                outlook_income = VALUES(outlook_income),
                outlook_economy = VALUES(outlook_economy)
            """,
            payload,
        )
    log.info("Rebuilt %d profiles for survey_id=%s", len(payload), survey_id)


def _rebuild_question_bases(survey_id: int) -> None:
    """Set csi_question.base_n to the number of qualified respondents who
    actually reached each question.

    This survey routes heavily — DP2-DP8 are asked only of department-store
    buyers, BN2-BN8 only of BNPL users, GP2-GP10 only of GLP-1 users. Charting
    any of them against the wave base understates them by 2-6x, so the base is
    stored on the question and every view carries it.
    """
    with get_engine("etl").begin() as conn:
        conn.execute(
            text(
                """
                UPDATE csi_question
                   SET base_n = (
                       SELECT COUNT(DISTINCT a.respondent_id)
                         FROM csi_answer a
                         JOIN csi_field f ON f.field_id = a.field_id
                         JOIN csi_respondent r ON r.respondent_id = a.respondent_id
                        WHERE f.question_id = csi_question.question_id
                          AND r.is_qualified = 1
                          AND (a.value_code IS NOT NULL
                               OR a.value_label IS NOT NULL
                               OR a.value_number IS NOT NULL
                               OR a.value_text IS NOT NULL)
                   )
                 WHERE csi_question.survey_id = :sid
                """
            ),
            {"sid": survey_id},
        )
    log.info("Rebuilt question bases for survey_id=%s", survey_id)


# ═══════════════════════════════════════════════════════════════════════════
def ingest_crosstabs(survey_id: int, path: str) -> None:
    settings, defs = xp.parse_crosstab_summary(path)
    banner_segments = xp.parse_banner(path)
    definition_by_label = {d.label: d.definition for d in defs}
    base_by_label = {d.label: d.base_n for d in defs}

    run_id = start_run(survey_id, "excel", "crosstab", path)
    eng = get_engine("etl")
    with eng.begin() as conn:
        conn.execute(
            text("UPDATE csi_crosstab_run SET is_current = 0 WHERE survey_id = :sid"),
            {"sid": survey_id},
        )
        res = conn.execute(
            text(
                """
                INSERT INTO csi_crosstab_run
                    (survey_id, run_label, respondent_base, extra_filter, table_set,
                     pct_base, stat_test, source_type, source_file, is_current)
                VALUES (:sid, :label, :resp, :filt, :ts, :pb, :stl, 'excel', :file, 1)
                """
            ),
            {
                "sid": survey_id,
                "label": str(settings.get("Title", "Cross tabs"))[:255],
                "resp": settings.get("Respondents"),
                "filt": settings.get("Additional Filter"),
                "ts": settings.get("Table Set"),
                "pb": settings.get("Percentage Base"),
                "stl": settings.get("Stat Test Levels"),
                "file": path.split("/")[-1][:255],
            },
        )
        ct_run = int(res.lastrowid)

        seg_ids: dict[str, int] = {}
        for order, seg in enumerate(banner_segments, start=1):
            banner_name = seg.banner_name or "Total"
            bcode = _banner_code(banner_name)
            conn.execute(
                text(
                    """
                    INSERT INTO csi_banner (survey_id, banner_code, banner_name, sort_order)
                    VALUES (:sid, :code, :name, :ord)
                    ON DUPLICATE KEY UPDATE banner_name = VALUES(banner_name),
                                            banner_id = LAST_INSERT_ID(banner_id)
                    """
                ),
                {"sid": survey_id, "code": bcode, "name": banner_name[:500], "ord": order},
            )
            banner_id = conn.execute(
                text("SELECT banner_id FROM csi_banner "
                     "WHERE survey_id = :sid AND banner_code = :code"),
                {"sid": survey_id, "code": bcode},
            ).scalar()
            conn.execute(
                text(
                    """
                    INSERT INTO csi_segment
                        (banner_id, survey_id, seg_letter, seg_label, seg_definition,
                         seg_base_n, is_total, low_base, sort_order)
                    VALUES (:bid, :sid, :letter, :label, :defn, :base, :tot, :flag, :ord)
                    ON DUPLICATE KEY UPDATE
                        seg_letter = VALUES(seg_letter),
                        seg_definition = COALESCE(VALUES(seg_definition), seg_definition),
                        seg_base_n = VALUES(seg_base_n), low_base = VALUES(low_base),
                        segment_id = LAST_INSERT_ID(segment_id)
                    """
                ),
                {
                    "bid": banner_id, "sid": survey_id, "letter": seg.letter,
                    "label": seg.label[:255],
                    "defn": definition_by_label.get(seg.label),
                    "base": seg.base_n or base_by_label.get(seg.label),
                    "tot": 1 if seg.label.lower() == "total" else 0,
                    "flag": seg.low_base, "ord": order,
                },
            )
            seg_ids[seg.label] = conn.execute(
                text("SELECT segment_id FROM csi_segment "
                     "WHERE banner_id = :bid AND seg_label = :label"),
                {"bid": banner_id, "label": seg.label[:255]},
            ).scalar()

        qid_by_code = {
            code: qid
            for code, qid in conn.execute(
                text("SELECT qcode, question_id FROM csi_question WHERE survey_id = :sid"),
                {"sid": survey_id},
            ).all()
        }

    cells, read, skipped = [], 0, {}
    for cell in xp.iter_crosstab_cells(path, banner_segments):
        read += 1
        qid = qid_by_code.get(cell["qcode"])
        sid_seg = seg_ids.get(cell["seg_label"])
        if not qid or not sid_seg:
            # Quota and terminate tables (vqtable*, voqtable*, vterm) are printed
            # in the cross-tab but never appear in the datamap, so they have no
            # question to attach to. Counted, not silently dropped.
            skipped[cell["qcode"]] = skipped.get(cell["qcode"], 0) + 1
            continue
        item_label = cell.get("item_label")
        cells.append(
            {
                "run": ct_run, "sid": survey_id, "qid": qid, "seg": sid_seg,
                "item": item_label[:500] if item_label else None,
                "key": f"{item_label or ''}|{cell['stub_label']}"[:600],
                "stub": cell["stub_label"][:1000], "kind": cell["stub_type"],
                "pct": cell["pct"], "cnt": cell["count_n"],
                "base": cell["answer_base_n"],
                "sig": cell["sig_letters"],
            }
        )

    sql = """
        INSERT INTO csi_crosstab
            (run_id, survey_id, question_id, segment_id, item_label, stub_key,
             stub_label, stub_type, pct, count_n, answer_base_n, sig_letters)
        VALUES (:run, :sid, :qid, :seg, :item, :key, :stub, :kind,
                :pct, :cnt, :base, :sig)
        ON DUPLICATE KEY UPDATE
            pct = VALUES(pct), count_n = VALUES(count_n),
            answer_base_n = VALUES(answer_base_n), sig_letters = VALUES(sig_letters)
    """
    from app.core.database import execute_many

    loaded = execute_many(sql, cells) if cells else 0
    finish_run(run_id, read, loaded, rejected=sum(skipped.values()))
    log.info("Loaded %d/%d cross-tab cells", loaded, read)
    if skipped:
        log.info("Skipped %d cells with no matching question: %s",
                 sum(skipped.values()),
                 ", ".join(f"{k}({v})" for k, v in sorted(skipped.items())))


def _banner_code(name: str) -> str:
    import re as _re

    slug = _re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").upper()
    return slug[:50] or "TOTAL"


# ═══════════════════════════════════════════════════════════════════════════
def ingest_api(wave: Optional[str], family: str = "CSI-US", full: bool = False) -> None:
    from etl.forsta_client import ForstaClient

    fc = config.forsta
    if not fc.is_configured:
        raise SystemExit(
            "Forsta is not configured. Set FORSTA_HOST, FORSTA_API_KEY and "
            "FORSTA_SURVEY_PATH in .env — see docs/04-it-requirements-checklist.md."
        )
    client = ForstaClient(fc.host, fc.api_key, fc.survey_path, fc.timeout, fc.max_retries)

    log.info("Fetching datamap from %s", client.base_url)
    datamap = client.datamap()
    questions = _questions_from_api_datamap(datamap)

    survey_id = upsert_survey(
        host=fc.host, path=fc.survey_path,
        title=f"{family} {wave or ''}".strip(), survey_family=family,
        wave_label=wave, wave_date=f"{wave}-01" if wave and len(wave) == 7 else None,
        datamap_payload=datamap,
    )
    run = start_run(survey_id, "api", "datamap", f"{client.base_url}/surveys/{fc.survey_path}/datamap")
    var_map = load_definitions(survey_id, questions, family)
    finish_run(run, len(questions), len(var_map))

    watermark = None if full else _watermark(survey_id)
    code_map = _code_lookup(survey_id)
    run = start_run(survey_id, "api", "data", f"{client.base_url}/surveys/{fc.survey_path}/data")
    read = loaded = 0
    for rec in client.iter_records(cond=config.ingest_cond, start=watermark, layout=fc.layout_id):
        read += 1
        loaded += _load_one_respondent(survey_id, rec, var_map, run, code_map)
    finish_run(run, read, loaded)
    _rebuild_profiles(survey_id, questions, family)
    _rebuild_question_bases(survey_id)
    log.info("API ingest complete: %d records", loaded)


def _watermark(survey_id: int) -> Optional[str]:
    with get_engine("etl").connect() as conn:
        ts = conn.execute(
            text("SELECT MAX(completed_at) FROM csi_respondent WHERE survey_id = :sid"),
            {"sid": survey_id},
        ).scalar()
    return ts.strftime("%Y-%m-%d %H:%M:%S") if ts else None


def _questions_from_api_datamap(payload: dict) -> list:
    """Adapt the JSON datamap to the same shape the Excel parser produces."""
    questions: list[xp.ParsedQuestion] = []
    for var in payload.get("variables", payload.get("questions", [])):
        q = xp.ParsedQuestion(
            qcode=str(var.get("label") or var.get("qlabel") or var.get("title") or "")[:50],
            qtext=str(var.get("qtitle") or var.get("title") or var.get("text") or ""),
            qtype=_api_type(var.get("type")),
        )
        for v in var.get("values", []) or []:
            try:
                q.options.append((int(v.get("value")), str(v.get("title") or v.get("label") or "")))
            except (TypeError, ValueError):
                continue
        if q.options:
            codes = [c for c, _ in q.options]
            q.value_min, q.value_max = min(codes), max(codes)
        for r in var.get("rows", []) or []:
            q.rows.append((str(r.get("label") or ""), str(r.get("title") or r.get("text") or "")))
        if q.qcode:
            questions.append(q)
    return questions


def _api_type(t: Any) -> str:
    return {
        "single": "single", "multiple": "multi", "number": "numeric",
        "text": "text", "float": "numeric", "date": "datetime",
    }.get(str(t or "").lower(), "single")


# ── coercion helpers ───────────────────────────────────────────────────────
def _int(v: Any) -> Optional[int]:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _float(v: Any) -> Optional[float]:
    try:
        f = float(v)
        return f
    except (TypeError, ValueError):
        return None


def _str(v: Any, limit: int) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s[:limit] or None


def _dt(v: Any) -> Optional[datetime]:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    for fmt in ("%m/%d/%Y %H:%M", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(v).strip(), fmt)
        except ValueError:
            continue
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Consumer Insight Portal ingestion")
    ap.add_argument("--source", choices=["api", "excel"], default="api")
    ap.add_argument("--raw", help="path to the raw-data .xlsx (source=excel)")
    ap.add_argument("--crosstab", help="path to the cross-tabs .xlsx (source=excel)")
    ap.add_argument("--wave", help="wave label, e.g. 2026-09")
    ap.add_argument("--family", default="CSI-US", help="survey family for trending")
    ap.add_argument("--full", action="store_true", help="ignore the watermark; reload everything")
    args = ap.parse_args()

    if args.source == "excel":
        if not args.raw:
            ap.error("--raw is required when --source excel")
        ingest_excel(args.raw, args.crosstab, args.wave, args.family)
    else:
        ingest_api(args.wave, args.family, args.full)
    return 0


if __name__ == "__main__":
    sys.exit(main())
