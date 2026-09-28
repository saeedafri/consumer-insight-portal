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
from etl import survey_map

logger = logging.getLogger(__name__)

def classify_group(qcode: str, qtext: str = "", family: Optional[str] = None) -> str:
    """Topic for a question. Config-driven — see config/survey_map.yml.

    Kept under the old name because the tests and callers use it; it now
    delegates to the rules file, so a new module in a future wave is a config
    edit rather than a code change.
    """
    return survey_map.classify_topic(qcode, qtext, family)


def ensure_topic(conn, topic_code: str) -> Optional[int]:
    """Return the topic_id, creating the topic if the questionnaire introduced
    one we have never seen. An unknown module must never block a load."""
    if not topic_code:
        return None
    row = conn.execute(
        text("SELECT topic_id FROM csi_topic WHERE topic_code = :c"), {"c": topic_code}
    ).first()
    if row:
        return int(row[0])
    conn.execute(
        text(
            """
            INSERT INTO csi_topic (topic_code, topic_name, is_technical, sort_order)
            VALUES (:c, :n, :tech, 500)
            ON DUPLICATE KEY UPDATE topic_id = LAST_INSERT_ID(topic_id)
            """
        ),
        {
            "c": topic_code,
            "n": topic_code.replace("_", " ").title(),
            "tech": 1 if survey_map.is_technical(topic_code) else 0,
        },
    )
    return int(conn.execute(
        text("SELECT topic_id FROM csi_topic WHERE topic_code = :c"), {"c": topic_code}
    ).scalar())


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
        conn.execute(
            sql,
            {
                "host": host, "path": path, "title": title[:500],
                "family": survey_family, "wave": wave_label,
                "wave_date": wave_date, "digest": digest,
            },
        )
        # Read the id back rather than trusting LAST_INSERT_ID(): that MySQL
        # idiom returns nothing useful after an ON CONFLICT UPDATE, and is not
        # portable to the local SQLite engine used for development.
        return int(conn.execute(
            text("SELECT survey_id FROM csi_survey "
                 "WHERE forsta_host = :host AND forsta_path = :path"),
            {"host": host, "path": path},
        ).scalar())


# ── definition layer ───────────────────────────────────────────────────────
def load_definitions(survey_id: int, questions: list,
                     family: Optional[str] = None) -> dict[str, int]:
    """Insert questions, rows, options and variables. Returns {field_name: field_id}."""
    with get_engine("etl").begin() as conn:
        for order, q in enumerate(questions, start=1):
            topic_code = classify_group(q.qcode, q.qtext, family)
            gid = ensure_topic(conn, topic_code)
            is_technical = 1 if survey_map.is_technical(topic_code) else 0
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
            qid = conn.execute(
                text("SELECT question_id FROM csi_question "
                     "WHERE survey_id = :sid AND qcode = :qcode"),
                {"sid": survey_id, "qcode": q.qcode[:50]},
            ).scalar()

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
                             is_exclusive, is_other, sort_order)
                        VALUES (:qid, :rc, :rl, :rs, :excl, :oe, :ord)
                        ON DUPLICATE KEY UPDATE
                            item_label = VALUES(item_label),
                            item_short = VALUES(item_short),
                            is_exclusive = VALUES(is_exclusive),
                            is_other = VALUES(is_other),
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
                    (survey_id, question_id, item_id, field_name, value_type)
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
                    (survey_id, question_id, item_id, field_name, value_type)
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
