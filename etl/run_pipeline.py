"""Loader steps shared by the Forsta, legacy and Qualtrics pipelines:
respondent upserts, profiles, question bases and the wave label.

Forsta loads run through etl/forsta_etl.py.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, Optional

from sqlalchemy import bindparam, text

from app.core.database import execute_many, get_engine
from etl import records as xp
from etl import survey_map

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s | %(message)s"
)
log = logging.getLogger("cip.pipeline")

STATUS_MAP = {"Terminated": 1, "Overquota": 2, "Qualified": 3, "Partial": 4}


# ═══════════════════════════════════════════════════════════════════════════
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
                  FROM cip_field  f
                  JOIN cip_question q ON q.question_id = f.question_id
                  JOIN cip_option   o ON o.question_id = q.question_id
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
                INSERT INTO cip_respondent
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
            text("SELECT respondent_id FROM cip_respondent "
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
                    INSERT INTO cip_answer
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
    """Flatten the demographic questions into cip_profile.

    Which question supplies which cut is resolved per survey — from
    config/survey_map.yml when the family is known, otherwise auto-detected
    from the question wording. The decision is written to cip_profile_map so
    it is visible, auditable and correctable without touching code.

    A dimension that cannot be resolved is simply absent: the column stays
    NULL and the portal hides that filter rather than failing.
    """
    eng = get_engine("etl")

    if questions is None:
        with eng.connect() as conn:
            rows = conn.execute(
                text("SELECT qcode, qtext FROM cip_question WHERE survey_id = :sid"),
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
                    INSERT INTO cip_profile_map (survey_id, dimension, qcode, resolved_by)
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
                  FROM cip_answer a
                  JOIN cip_field f ON f.field_id = a.field_id
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
        age = survey_map.classify_age(values.get("age"))
        state = values.get("state_name")
        payload.append({
            "rid": respondent_id, "sid": survey_id,
            "gender": values.get("gender"),
            "age": age["age"],
            "band": age["band"],
            "age_mid": age["mid"],
            "inc_mid": survey_map.income_mid_k(values.get("income_band")),
            "gen": age["gen"],
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
            INSERT INTO cip_profile
                (respondent_id, survey_id, gender, age_years, age_band, generation,
                 relationship, ethnicity, income_band, urbanicity, political,
                 state_name, census_region, outlook_income, outlook_economy,
                 age_mid, income_mid_k)
            VALUES (:rid, :sid, :gender, :age, :band, :gen, :rel, :eth, :inc,
                    :urb, :pol, :state, :region, :oi, :oe, :age_mid, :inc_mid)
            ON DUPLICATE KEY UPDATE
                gender = VALUES(gender), age_years = VALUES(age_years),
                age_band = VALUES(age_band), generation = VALUES(generation),
                relationship = VALUES(relationship), ethnicity = VALUES(ethnicity),
                income_band = VALUES(income_band), urbanicity = VALUES(urbanicity),
                political = VALUES(political), state_name = VALUES(state_name),
                census_region = VALUES(census_region),
                outlook_income = VALUES(outlook_income),
                outlook_economy = VALUES(outlook_economy),
                age_mid = VALUES(age_mid), income_mid_k = VALUES(income_mid_k)
            """,
            payload,
        )
    log.info("Rebuilt %d profiles for survey_id=%s", len(payload), survey_id)


def _rebuild_question_bases(survey_id: int) -> None:
    """Set cip_question.base_n to the number of qualified respondents who
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
                UPDATE cip_question
                   SET base_n = (
                       SELECT COUNT(DISTINCT a.respondent_id)
                         FROM cip_answer a
                         JOIN cip_field f ON f.field_id = a.field_id
                         JOIN cip_respondent r ON r.respondent_id = a.respondent_id
                        WHERE f.question_id = cip_question.question_id
                          AND r.is_qualified = 1
                          AND (a.value_code IS NOT NULL
                               OR a.value_label IS NOT NULL
                               OR a.value_number IS NOT NULL
                               OR a.value_text IS NOT NULL)
                   )
                 WHERE cip_question.survey_id = :sid
                """
            ),
            {"sid": survey_id},
        )
    log.info("Rebuilt question bases for survey_id=%s", survey_id)


# ═══════════════════════════════════════════════════════════════════════════
def wave_from_records(records: list[dict]) -> str:
    """A weekly wave is labelled by the Monday of its first fielding day
    (the Excel exports: 2026-09-21, 2026-09-28)."""
    days = []
    for rec in records:
        stamp = _dt(rec.get("date"))
        if stamp:
            days.append(stamp.date())
    if not days:
        raise ValueError("no record carries a date — pass --wave explicitly")
    first = min(days)
    return (first - timedelta(days=first.weekday())).isoformat()


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
