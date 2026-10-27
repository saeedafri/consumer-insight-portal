"""Execute the owner-approved CIP Stage 2 read-only MySQL plan manifest.

This is intentionally a fixed allowlist: one small catalogue SELECT and seven
EXPLAIN FORMAT=JSON statements. It does not accept arbitrary SQL or retry.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pymysql
from pymysql.cursors import DictCursor

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.core.config import Config


OUTPUT_PATH = (
    REPO_ROOT
    / "docs/performance/cip_staging_verification/evidence/STAGE2_SANITIZED_RESULTS.json"
)
EXPECTED_DATABASE = "cip_stg"
EXPECTED_SERVER_HOST_HASH = "sha256:3c3485f00d05"
EXPECTED_ACCOUNT_HASH = "sha256:2837eb29d5ae"
MAX_THREADS_RUNNING = 8


SQL: list[tuple[str, str]] = [
    (
        "SQL-030",
        """SELECT VERSION() AS server_version,
       DATABASE() AS current_database,
       CURRENT_USER() AS authenticated_account,
       @@hostname AS server_hostname,
       @@port AS server_port,
       CONNECTION_ID() AS inspection_connection_id,
       @@session.autocommit AS session_autocommit,
       @@session.transaction_read_only AS transaction_read_only,
       @@session.max_execution_time AS max_execution_time_ms,
       @@session.lock_wait_timeout AS metadata_lock_wait_seconds,
       @@session.innodb_lock_wait_timeout AS row_lock_wait_seconds""",
    ),
    ("SQL-031", "SET SESSION TRANSACTION READ ONLY"),
    ("SQL-032", "SET SESSION max_execution_time = 5000"),
    ("SQL-033", "SET SESSION lock_wait_timeout = 3"),
    ("SQL-034", "SET SESSION innodb_lock_wait_timeout = 3"),
    (
        "SQL-035",
        """SELECT @@session.autocommit AS session_autocommit,
       @@session.transaction_read_only AS transaction_read_only,
       @@session.max_execution_time AS max_execution_time_ms,
       @@session.lock_wait_timeout AS metadata_lock_wait_seconds,
       @@session.innodb_lock_wait_timeout AS row_lock_wait_seconds""",
    ),
    ("SQL-036", "SELECT IS_USED_LOCK('cip_etl') AS cip_etl_owner_connection_id"),
    (
        "SQL-037",
        """SHOW GLOBAL STATUS
WHERE Variable_name IN (
    'Threads_connected', 'Threads_running', 'Connections',
    'Aborted_connects', 'Created_tmp_tables',
    'Created_tmp_disk_tables', 'Slow_queries', 'Questions', 'Uptime'
)""",
    ),
    (
        "SQL-019",
        """SELECT survey_id, study_type, wave_date, qualified_n, rows_built,
       prior_survey_id, ly_survey_id
FROM cip_stg.srv_wave
ORDER BY rows_built ASC, survey_id ASC
LIMIT 10""",
    ),
    (
        "SQL-023",
        """EXPLAIN FORMAT=JSON
SELECT survey_id, qcode, item_id, option_id,
       gender, age_band, generation, income_band, census_region, urbanicity,
       COUNT(*)
FROM cip_stg.srv_answer
WHERE survey_id IN (262)
GROUP BY survey_id, qcode, item_id, option_id,
         gender, age_band, generation, income_band, census_region, urbanicity""",
    ),
    (
        "SQL-024",
        """EXPLAIN FORMAT=JSON
SELECT respondent_id, qcode, item_id, option_id,
       gender, age_band, generation, income_band, census_region, urbanicity
FROM cip_stg.srv_answer
WHERE survey_id = 262""",
    ),
    (
        "SQL-025",
        """EXPLAIN FORMAT=JSON
SELECT c.survey_id, c.question_id, q.qcode, q.qtype,
       COALESCE(c.item_id, 0) AS item_id,
       COALESCE(c.option_id, 0) AS option_id,
       COALESCE(i.item_label, '') AS item_label,
       o.value_code AS option_code,
       o.value_label AS option_label,
       COALESCE(i.sort_order, 0) * 1000 + COALESCE(o.sort_order, 0) AS sort_order,
       COALESCE(c.concept_option_id, m.concept_option_id) AS concept_option_id,
       c.dim, c.dim_value, c.n, c.base_n
FROM cip_stg.cip_agg_cell AS c
JOIN cip_stg.cip_question AS q
  ON q.question_id = c.question_id
 AND q.survey_id = c.survey_id
 AND q.survey_id IN (262)
 AND q.is_technical = 0
 AND q.is_virtual = 0
LEFT JOIN cip_stg.cip_item AS i
  ON i.item_id = c.item_id
LEFT JOIN cip_stg.cip_option AS o
  ON o.option_id = c.option_id
LEFT JOIN cip_stg.cip_concept_map AS m
  ON m.survey_id = c.survey_id
 AND m.map_key = c.map_key
 AND m.status = 'confirmed'
 AND m.concept_option_id IS NOT NULL
WHERE c.survey_id IN (262)
  AND c.cohort_id IS NULL
  AND c.base_n > 0
  AND (c.dim = 'total' OR c.dim_value <> '')""",
    ),
    (
        "SQL-026",
        """EXPLAIN FORMAT=JSON
SELECT a.answer_id
FROM cip_stg.cip_answer AS a
JOIN cip_stg.cip_field AS f
  ON f.field_id = a.field_id
LEFT JOIN cip_stg.cip_option AS o
  ON o.question_id = f.question_id
 AND o.value_code = a.value_code
LEFT JOIN cip_stg.cip_item AS i
  ON i.item_id = f.item_id
WHERE a.survey_id = 262
  AND a.value_label = COALESCE(o.value_label, i.item_label)""",
    ),
    (
        "SQL-027",
        """EXPLAIN FORMAT=JSON
SELECT record_no, respondent_id
FROM cip_stg.cip_respondent
WHERE survey_id = 262""",
    ),
    (
        "SQL-028",
        """EXPLAIN FORMAT=JSON
SELECT answer_id
FROM cip_stg.cip_answer
WHERE survey_id = 262""",
    ),
    (
        "SQL-029",
        """EXPLAIN FORMAT=JSON
SELECT r.survey_id, r.qcode, r.item_id, r.option_id,
       r.item_label, r.option_code, r.option_label, r.sort_order,
       r.flags, r.concept_option_id, q.qtext
FROM cip_stg.srv_result AS r
JOIN cip_stg.cip_question AS q
  ON q.question_id = r.question_id
WHERE r.survey_id IN (262)
  AND r.dim = 'total'""",
    ),
]

LOCK_CHECK = "SELECT IS_USED_LOCK('cip_etl') AS cip_etl_owner_connection_id"
PRESSURE_CHECK = """SHOW GLOBAL STATUS
WHERE Variable_name IN (
    'Threads_connected', 'Threads_running', 'Connections',
    'Aborted_connects', 'Created_tmp_tables',
    'Created_tmp_disk_tables', 'Slow_queries', 'Questions', 'Uptime'
)"""


def _hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(str(value).encode()).hexdigest()[:12]


def _json_value(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return value


def _status(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {row["Variable_name"]: int(row["Value"]) for row in rows}


def _execute(cursor: DictCursor, sql_id: str, statement: str) -> dict[str, Any]:
    started = time.perf_counter()
    cursor.execute(statement)
    rows = cursor.fetchall() if cursor.description else []
    elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
    record: dict[str, Any] = {
        "sql_id": sql_id,
        "status": "ok",
        "elapsed_ms": elapsed_ms,
        "row_count": len(rows),
        "affected_rows": max(cursor.rowcount, 0) if not cursor.description else 0,
        "rows": [
            {key: _json_value(value) for key, value in row.items()} for row in rows
        ],
    }
    print(f"{sql_id}: ok ({elapsed_ms:.3f} ms, {len(rows)} rows)", flush=True)
    return record


def _validate_identity(record: dict[str, Any]) -> None:
    row = record["rows"][0]
    if row["current_database"] != EXPECTED_DATABASE:
        raise RuntimeError("unexpected database")
    if "azure" not in str(row["server_version"]).lower():
        raise RuntimeError("server is not the approved Azure MySQL target")
    if _hash(row["server_hostname"]) != EXPECTED_SERVER_HOST_HASH:
        raise RuntimeError("server identity differs from approved Stage 1 target")
    if _hash(row["authenticated_account"]) != EXPECTED_ACCOUNT_HASH:
        raise RuntimeError("account identity differs from approved Stage 1 target")
    if int(row["server_port"]) != 3306 or int(row["session_autocommit"]) != 1:
        raise RuntimeError("unexpected port or autocommit state")
    row["server_hostname"] = EXPECTED_SERVER_HOST_HASH
    row["authenticated_account"] = EXPECTED_ACCOUNT_HASH
    row["inspection_connection_id"] = _hash(row["inspection_connection_id"])


def _validate_guards(record: dict[str, Any]) -> None:
    row = record["rows"][0]
    actual = tuple(
        int(row[key])
        for key in (
            "session_autocommit",
            "transaction_read_only",
            "max_execution_time_ms",
            "metadata_lock_wait_seconds",
            "row_lock_wait_seconds",
        )
    )
    if actual != (1, 1, 5000, 3, 3):
        raise RuntimeError(f"session guard verification failed: {actual}")


def _validate_lock(record: dict[str, Any]) -> None:
    if record["rows"][0]["cip_etl_owner_connection_id"] is not None:
        raise RuntimeError("cip_etl lock is held")


def _validate_pressure(record: dict[str, Any]) -> None:
    status = _status(record["rows"])
    if status.get("Threads_running", MAX_THREADS_RUNNING + 1) > MAX_THREADS_RUNNING:
        raise RuntimeError("Threads_running exceeds approved threshold")


def _parse_plan(record: dict[str, Any]) -> None:
    record["rows"] = [{"plan": json.loads(record["rows"][0]["EXPLAIN"])}]


def main() -> int:
    output: dict[str, Any] = {
        "approved_manifest": "08_STAGE2_SQL_EXECUTION_APPROVAL_MANIFEST.md",
        "target": EXPECTED_DATABASE,
        "connection_opened": False,
        "connection_closed": False,
        "completed": False,
        "stopped_reason": None,
        "statements": [],
        "monitoring_checks": [],
    }
    connection = None
    try:
        db = Config().database("etl")
        if db.database != EXPECTED_DATABASE or not db.host or not db.user or not db.password:
            raise RuntimeError("configured database target or credentials are unavailable")
        ssl_args = db.connect_args.get("ssl")
        if ssl_args is None:
            raise RuntimeError("TLS configuration is unavailable")
        connection = pymysql.connect(
            host=db.host,
            port=db.port,
            user=db.user,
            password=db.password,
            database=EXPECTED_DATABASE,
            charset="utf8mb4",
            cursorclass=DictCursor,
            autocommit=True,
            connect_timeout=5,
            read_timeout=10,
            write_timeout=10,
            local_infile=False,
            ssl=ssl_args,
        )
        output["connection_opened"] = True
        with connection.cursor() as cursor:
            for sql_id, statement in SQL:
                if sql_id in {"SQL-023", "SQL-024", "SQL-025", "SQL-026", "SQL-027", "SQL-028", "SQL-029"}:
                    lock = _execute(cursor, f"MONITOR-LOCK-BEFORE-{sql_id[4:]}", LOCK_CHECK)
                    _validate_lock(lock)
                    output["monitoring_checks"].append(lock)
                    pressure = _execute(
                        cursor, f"MONITOR-PRESSURE-BEFORE-{sql_id[4:]}", PRESSURE_CHECK
                    )
                    _validate_pressure(pressure)
                    output["monitoring_checks"].append(pressure)

                record = _execute(cursor, sql_id, statement)
                if sql_id == "SQL-030":
                    _validate_identity(record)
                elif sql_id == "SQL-035":
                    _validate_guards(record)
                elif sql_id == "SQL-036":
                    _validate_lock(record)
                elif sql_id == "SQL-037":
                    _validate_pressure(record)
                elif sql_id.startswith("SQL-02") and sql_id != "SQL-019":
                    _parse_plan(record)
                output["statements"].append(record)
        output["completed"] = True
        return_code = 0
    except Exception as exc:
        output["stopped_reason"] = f"{type(exc).__name__}: {exc}"
        print(f"STOP: {output['stopped_reason']}", file=sys.stderr, flush=True)
        return_code = 1
    finally:
        if connection is not None:
            connection.close()
            output["connection_closed"] = True
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(json.dumps(output, indent=2, sort_keys=True), encoding="utf-8")
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
