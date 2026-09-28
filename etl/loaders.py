"""Upsert helpers: turn parsed Forsta objects into CSI rows.

Everything is idempotent — re-running a load for the same wave updates in
place rather than duplicating, so a failed nightly run can simply be re-run.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime
from typing import Any, Iterable, Optional

from sqlalchemy import text

from app.core.database import execute_many, get_engine, session_scope

logger = logging.getLogger(__name__)

SYSTEM_QCODES = {
    "record", "uuid", "date", "markers", "status", "vlist", "qtime", "vos",
    "vosr15oe", "vbrowser", "vbrowserr15oe", "vmobiledevice", "vmobileos",
    "start_date", "vdropout", "source", "decLang", "list", "userAgent",
    "dcua", "url", "session", "RID", "conditions",
}

GROUP_RULES: list[tuple[str, str]] = [
    (r"^(q[1-6])$", "SHOPPING"),
    (r"^DP\d", "DEPT_STORES"),
    (r"^DJ\d", "DIAMONDS"),
    (r"^BN\d", "BNPL"),
    (r"^D(28|29|30|31|32|33|34|35)", "AI_GENAI"),
    (r"^GP\d", "GLP1"),
    (r"^CS\d", "SENTIMENT"),
    (r"^D(12|13|14|15)$", "MACRO"),
    (r"^D([1-8])$", "DEMOGRAPHICS"),
]


def classify_group(qcode: str) -> str:
    if qcode in SYSTEM_QCODES or qcode.startswith(("voq", "vq", "vterm")):
        return "PARADATA"
    for pattern, group in GROUP_RULES:
        if re.match(pattern, qcode):
            return group
    return "PARADATA" if qcode.startswith("v") else "SHOPPING"


def short_label(text_value: str, limit: int = 120) -> str:
    clean = " ".join(str(text_value).split())
    return clean if len(clean) <= limit else clean[: limit - 1].rstrip() + "…"


# ── survey ─────────────────────────────────────────────────────────────────
def upsert_survey(
    host: str,
    path: str,
    title: str,
    survey_family: Optional[str] = None,
    wave_label: Optional[str] = None,
    wave_date: Optional[str] = None,
    datamap_payload: Any = None,
) -> int:
    digest = (
        hashlib.sha256(json.dumps(datamap_payload, sort_keys=True, default=str).encode()).hexdigest()
        if datamap_payload is not None
        else None
    )
    sql = text(
        """
        INSERT INTO csi_survey
            (forsta_host, forsta_path, title, survey_family, wave_label, wave_date, datamap_hash)
        VALUES (:host, :path, :title, :family, :wave, :wave_date, :digest)
        ON DUPLICATE KEY UPDATE
            title = VALUES(title),
            survey_family = COALESCE(VALUES(survey_family), survey_family),
            wave_label = COALESCE(VALUES(wave_label), wave_label),
            wave_date = COALESCE(VALUES(wave_date), wave_date),
            datamap_hash = COALESCE(VALUES(datamap_hash), datamap_hash),
            survey_id = LAST_INSERT_ID(survey_id)
        """
    )
    with get_engine("etl").begin() as conn:
        res = conn.execute(
            sql,
            {
                "host": host, "path": path, "title": title[:500],
                "family": survey_family, "wave": wave_label,
                "wave_date": wave_date, "digest": digest,
            },
        )
        return int(res.lastrowid)


# ── definition layer ───────────────────────────────────────────────────────
def load_definitions(survey_id: int, questions: list) -> dict[str, int]:
    """Insert questions, rows, options and variables. Returns {field_name: field_id}."""
    with get_engine("etl").begin() as conn:
        groups = {
            code: gid
            for code, gid in conn.execute(
                text("SELECT topic_code, topic_id FROM csi_topic")
            ).all()
        }

        for order, q in enumerate(questions, start=1):
            gid = groups.get(classify_group(q.qcode))
            is_technical = 1 if classify_group(q.qcode) == "PARADATA" else 0
            conn.execute(
                text(
                    """
                    INSERT INTO csi_question
                        (survey_id, topic_id, qcode, qtext, qtext_short, qtype,
                         value_min, value_max, is_technical, is_multi, sort_order)
                    VALUES (:sid, :gid, :qcode, :qtext, :short, :qtype,
                            :vmin, :vmax, :sys, :multi, :ord)
                    ON DUPLICATE KEY UPDATE
                        topic_id = VALUES(topic_id), qtext = VALUES(qtext),
                        qtext_short = VALUES(qtext_short), qtype = VALUES(qtype),
                        value_min = VALUES(value_min), value_max = VALUES(value_max),
                        is_technical = VALUES(is_technical), is_multi = VALUES(is_multi),
                        sort_order = VALUES(sort_order),
                        question_id = LAST_INSERT_ID(question_id)
                    """
                ),
                {
                    "sid": survey_id, "gid": gid, "qcode": q.qcode[:50],
                    "qtext": q.qtext, "short": short_label(q.qtext),
                    "qtype": q.qtype, "vmin": q.value_min, "vmax": q.value_max,
                    "sys": is_technical, "multi": 1 if q.is_multi else 0, "ord": order,
                },
            )
            qid = conn.execute(text("SELECT LAST_INSERT_ID()")).scalar()

            for i, (code, label) in enumerate(q.options, start=1):
                conn.execute(
                    text(
                        """
                        INSERT INTO csi_option
                            (question_id, value_code, value_label, is_nonresponse, sort_order)
                        VALUES (:qid, :code, :label, :nr, :ord)
                        ON DUPLICATE KEY UPDATE
                            value_label = VALUES(value_label),
                            is_nonresponse = VALUES(is_nonresponse),
                            sort_order = VALUES(sort_order)
                        """
                    ),
                    {
                        "qid": qid, "code": code, "label": (label or "")[:500],
                        "nr": 1 if _is_nonresponse(label) else 0, "ord": i,
                    },
                )

            for i, (item_code, item_label) in enumerate(q.rows, start=1):
                conn.execute(
                    text(
                        """
                        INSERT INTO csi_item
                            (question_id, item_code, item_label, item_short,
                             is_exclusive, is_other_specify, sort_order)
                        VALUES (:qid, :rc, :rl, :rs, :excl, :oe, :ord)
                        ON DUPLICATE KEY UPDATE
                            item_label = VALUES(item_label),
                            item_short = VALUES(item_short),
                            is_exclusive = VALUES(is_exclusive),
                            is_other_specify = VALUES(is_other_specify),
                            sort_order = VALUES(sort_order)
                        """
                    ),
                    {
                        "qid": qid, "rc": item_code[:50], "rl": (item_label or "")[:1000],
                        "rs": short_label(item_label or "", 80),
                        "excl": 1 if _is_exclusive(item_label) else 0,
                        "oe": 1 if item_code.endswith("oe") else 0,
                        "ord": i,
                    },
                )

        # variables: one row per export column
        conn.execute(
            text(
                """
                INSERT IGNORE INTO csi_field
                    (survey_id, question_id, item_id, field_name, storage_type)
                SELECT q.survey_id, q.question_id, r.item_id, r.item_code,
                       CASE WHEN q.qtype IN ('numeric') THEN 'numeric'
                            WHEN q.qtype IN ('text') THEN 'text'
                            ELSE 'code' END
                FROM csi_question q
                JOIN csi_item r ON r.question_id = q.question_id
                WHERE q.survey_id = :sid
                """
            ),
            {"sid": survey_id},
        )
        conn.execute(
            text(
                """
                INSERT IGNORE INTO csi_field
                    (survey_id, question_id, item_id, field_name, storage_type)
                SELECT q.survey_id, q.question_id, NULL, q.qcode,
                       CASE WHEN q.qtype = 'numeric' THEN 'numeric'
                            WHEN q.qtype = 'text' THEN 'text'
                            ELSE 'code' END
                FROM csi_question q
                LEFT JOIN csi_item r ON r.question_id = q.question_id
                WHERE q.survey_id = :sid AND r.item_id IS NULL
                """
            ),
            {"sid": survey_id},
        )

        return {
            name: vid
            for name, vid in conn.execute(
                text("SELECT field_name, field_id FROM csi_field WHERE survey_id = :sid"),
                {"sid": survey_id},
            ).all()
        }


def _is_nonresponse(label: Optional[str]) -> bool:
    if not label:
        return False
    low = label.lower()
    return any(k in low for k in ("don't know", "dont know", "not sure", "prefer not to say"))


def _is_exclusive(label: Optional[str]) -> bool:
    return bool(label) and label.strip().lower().startswith("none of these")


# ── ops ────────────────────────────────────────────────────────────────────
def start_run(survey_id: Optional[int], source_type: str, object_type: str, source_ref: str) -> int:
    with get_engine("etl").begin() as conn:
        res = conn.execute(
            text(
                """
                INSERT INTO csi_load_log (survey_id, source_type, object_type, source_ref)
                VALUES (:sid, :src, :obj, :ref)
                """
            ),
            {"sid": survey_id, "src": source_type, "obj": object_type, "ref": source_ref[:500]},
        )
        return int(res.lastrowid)


def finish_run(run_id: int, read: int, loaded: int, rejected: int = 0, error: Optional[str] = None) -> None:
    status = "failed" if error else ("partial" if rejected else "success")
    with get_engine("etl").begin() as conn:
        conn.execute(
            text(
                """
                UPDATE csi_load_log
                   SET rows_read = :read, rows_loaded = :loaded,
                       rows_bad = :rej, status = :status,
                       error_text = :err, finished_at = NOW()
                 WHERE load_id = :rid
                """
            ),
            {"read": read, "loaded": loaded, "rej": rejected, "status": status,
             "err": error, "rid": run_id},
        )
