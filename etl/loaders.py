"""Upsert helpers: turn parsed survey definitions into CIP rows.

Everything is idempotent — re-running a load for the same wave updates in
place rather than duplicating, so a failed nightly run can simply be re-run.
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Optional

from sqlalchemy import text

from app.core.database import get_engine
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
        text("SELECT topic_id FROM cip_topic WHERE topic_code = :c"), {"c": topic_code}
    ).first()
    if row:
        return int(row[0])
    conn.execute(
        text(
            """
            INSERT INTO cip_topic (topic_code, topic_name, is_technical, sort_order)
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
        text("SELECT topic_id FROM cip_topic WHERE topic_code = :c"), {"c": topic_code}
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
    platform: str = "forsta",
    source_ref: Optional[str] = None,
    study_type: str = "tracker",
) -> int:
    digest = (
        hashlib.sha256(json.dumps(datamap_payload, sort_keys=True, default=str).encode()).hexdigest()
        if datamap_payload is not None
        else None
    )
    sql = text(
        """
        INSERT INTO cip_survey
            (forsta_host, forsta_path, title, survey_family, wave_label, wave_date,
             datamap_hash, platform, source_ref, study_type)
        VALUES (:host, :path, :title, :family, :wave, :wave_date, :digest,
                :platform, :source_ref, :study_type)
        ON DUPLICATE KEY UPDATE
            title = VALUES(title),
            survey_family = COALESCE(VALUES(survey_family), survey_family),
            wave_label = COALESCE(VALUES(wave_label), wave_label),
            wave_date = COALESCE(VALUES(wave_date), wave_date),
            datamap_hash = COALESCE(VALUES(datamap_hash), datamap_hash),
            forsta_host = VALUES(forsta_host),
            study_type = VALUES(study_type),
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
                "platform": platform, "source_ref": source_ref or path,
                "study_type": study_type,
            },
        )
        # Read the id back rather than trusting LAST_INSERT_ID(): that MySQL
        # idiom returns nothing useful after an ON CONFLICT UPDATE, and is not
        # portable to the local SQLite engine used for development.
        return int(conn.execute(
            text("SELECT survey_id FROM cip_survey WHERE platform = :platform "
                 "AND source_ref = :source_ref AND wave_label = :wave"),
            {"platform": platform, "source_ref": source_ref or path, "wave": wave_label},
        ).scalar())


# ── definition layer ───────────────────────────────────────────────────────
def load_definitions(survey_id: int, questions: list,
                     family: Optional[str] = None) -> dict[str, int]:
    """Insert questions, rows, options and variables. Returns {field_name: field_id}.

    Batched: a constant number of statements per wave (each round trip is
    ~250 ms from the India office), whatever the number of questions."""
    with get_engine("etl").begin() as conn:
        topic_ids: dict[str, Optional[int]] = {}
        question_rows = []
        for order, q in enumerate(questions, start=1):
            topic_code = classify_group(q.qcode, q.qtext, family)
            if topic_code not in topic_ids:
                topic_ids[topic_code] = ensure_topic(conn, topic_code)
            question_rows.append({
                "sid": survey_id, "gid": topic_ids[topic_code], "qcode": q.qcode[:50],
                "qtext": q.qtext, "short": short_label(q.qtext), "qtype": q.qtype,
                "vmin": q.value_min, "vmax": q.value_max,
                "sys": 1 if survey_map.is_technical(topic_code) or "t" in getattr(q, "flags", ()) else 0,
                "virtual": 1 if "v" in getattr(q, "flags", ()) else 0,
                "multi": 1 if q.is_multi else 0, "ord": order,
            })
        if question_rows:
            conn.execute(text(
                """
                INSERT INTO cip_question
                    (survey_id, topic_id, qcode, qtext, qtext_short, qtype,
                     value_min, value_max, is_technical, is_virtual, is_multi, sort_order)
                VALUES (:sid, :gid, :qcode, :qtext, :short, :qtype,
                        :vmin, :vmax, :sys, :virtual, :multi, :ord)
                ON DUPLICATE KEY UPDATE
                    topic_id = VALUES(topic_id), qtext = VALUES(qtext),
                    qtext_short = VALUES(qtext_short), qtype = VALUES(qtype),
                    value_min = VALUES(value_min), value_max = VALUES(value_max),
                    is_technical = VALUES(is_technical), is_virtual = VALUES(is_virtual),
                    is_multi = VALUES(is_multi), sort_order = VALUES(sort_order)
                """), question_rows)
        qid = dict(conn.execute(text(
            "SELECT qcode, question_id FROM cip_question WHERE survey_id = :sid"),
            {"sid": survey_id}).all())

        option_rows = [
            {"qid": qid[q.qcode[:50]], "code": code, "label": (label or "")[:500],
             "nr": 1 if _is_nonresponse(label) else 0, "ord": i}
            for q in questions for i, (code, label) in enumerate(q.options, start=1)]
        if option_rows:
            conn.execute(text(
                """
                INSERT INTO cip_option
                    (question_id, value_code, value_label, is_nonresponse, sort_order)
                VALUES (:qid, :code, :label, :nr, :ord)
                ON DUPLICATE KEY UPDATE
                    value_label = VALUES(value_label),
                    is_nonresponse = VALUES(is_nonresponse),
                    sort_order = VALUES(sort_order)
                """), option_rows)

        item_rows = [
            {"qid": qid[q.qcode[:50]], "rc": item_code[:50], "rl": (item_label or "")[:1000],
             "rs": short_label(item_label or "", 80),
             "excl": 1 if _is_exclusive(item_label) else 0,
             "oe": 1 if item_code.endswith("oe") else 0, "ord": i,
             "left": (getattr(q, "bipolar", {}).get(item_code) or (None, None))[0],
             "right": (getattr(q, "bipolar", {}).get(item_code) or (None, None))[1]}
            for q in questions for i, (item_code, item_label) in enumerate(q.rows, start=1)]
        if item_rows:
            conn.execute(text(
                """
                INSERT INTO cip_item
                    (question_id, item_code, item_label, item_short,
                     is_exclusive, is_other, left_label, right_label, sort_order)
                VALUES (:qid, :rc, :rl, :rs, :excl, :oe, :left, :right, :ord)
                ON DUPLICATE KEY UPDATE
                    item_label = VALUES(item_label), item_short = VALUES(item_short),
                    is_exclusive = VALUES(is_exclusive), is_other = VALUES(is_other),
                    left_label = VALUES(left_label), right_label = VALUES(right_label),
                    sort_order = VALUES(sort_order)
                """), item_rows)

        # variables: one row per export column
        conn.execute(
            text(
                """
                INSERT IGNORE INTO cip_field
                    (survey_id, question_id, item_id, field_name, value_type)
                SELECT q.survey_id, q.question_id, r.item_id, r.item_code,
                       CASE WHEN q.qtype IN ('numeric') THEN 'numeric'
                            WHEN q.qtype IN ('text') THEN 'text'
                            ELSE 'code' END
                FROM cip_question q
                JOIN cip_item r ON r.question_id = q.question_id
                WHERE q.survey_id = :sid
                """
            ),
            {"sid": survey_id},
        )
        conn.execute(
            text(
                """
                INSERT IGNORE INTO cip_field
                    (survey_id, question_id, item_id, field_name, value_type)
                SELECT q.survey_id, q.question_id, NULL, q.qcode,
                       CASE WHEN q.qtype = 'numeric' THEN 'numeric'
                            WHEN q.qtype = 'text' THEN 'text'
                            ELSE 'code' END
                FROM cip_question q
                LEFT JOIN cip_item r ON r.question_id = q.question_id
                WHERE q.survey_id = :sid AND r.item_id IS NULL
                """
            ),
            {"sid": survey_id},
        )

        return {
            name: vid
            for name, vid in conn.execute(
                text("SELECT field_name, field_id FROM cip_field WHERE survey_id = :sid"),
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
                INSERT INTO cip_load_log (survey_id, source_type, object_type, source_ref)
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
                UPDATE cip_load_log
                   SET rows_read = :read, rows_loaded = :loaded,
                       rows_bad = :rej, status = :status,
                       error_text = :err, finished_at = NOW()
                 WHERE load_id = :rid
                """
            ),
            {"read": read, "loaded": loaded, "rej": rejected, "status": status,
             "err": error, "rid": run_id},
        )


def index_survey(survey_id: int, concepts: bool = True) -> None:
    """Rebuild this wave's rows in cip_search, and (unless told not to — a
    reindex of every wave does them once at the end) the concept rows."""
    with get_engine("etl").begin() as conn:
        conn.execute(text("DELETE FROM cip_search WHERE survey_id = :s"), {"s": survey_id})
        wave, title, fam, tags, ref = conn.execute(text(
            "SELECT wave_label, title, survey_family, tags, source_ref FROM cip_survey WHERE survey_id = :s"),
            {"s": survey_id}).one()
        conn.execute(text(
            "INSERT INTO cip_search (kind, survey_id, wave_label, title, body)"
            " VALUES ('survey', :s, :wave, :title, :body)"),
            {"s": survey_id, "wave": wave, "title": title,
             "body": " ".join(str(x) for x in (fam, tags, ref) if x)})
        conn.execute(text("""
            INSERT INTO cip_search (kind, survey_id, question_id, wave_label, title, body)
            SELECT 'question', q.survey_id, q.question_id, s.wave_label, SUBSTR(q.qtext, 1, 500), q.qcode
              FROM cip_question q JOIN cip_survey s ON s.survey_id = q.survey_id
             WHERE q.survey_id = :s AND q.is_technical = 0 AND q.is_virtual = 0"""), {"s": survey_id})
        if not concepts:
            return
        conn.execute(text("DELETE FROM cip_search WHERE kind = 'concept'"))
        conn.execute(text("""
            INSERT INTO cip_search (kind, concept_id, waves, title, body)
            SELECT 'concept', c.concept_id, COUNT(DISTINCT m.survey_id), SUBSTR(c.concept_name, 1, 500), c.concept_code
              FROM cip_concept c JOIN cip_concept_map m ON m.concept_id = c.concept_id
                   AND m.status = 'confirmed' AND m.concept_option_id IS NULL
             GROUP BY c.concept_id, c.concept_name, c.concept_code"""))
