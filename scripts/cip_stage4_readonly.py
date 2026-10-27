"""Execute only the owner-approved Stage 4 staging EXPLAIN statements."""
from __future__ import annotations

import hashlib
import json
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pymysql
from pymysql.constants import SERVER_STATUS
from pymysql.cursors import DictCursor

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.core.config import Config


OUTPUT_PATH = REPO_ROOT / (
    "docs/performance/cip_staging_verification/evidence/"
    "STAGE4_STAGING_SANITIZED_RESULTS.json"
)
EXPECTED_DATABASE = "cip_stg"
EXPECTED_SERVER_HOST_HASH = "sha256:3c3485f00d05"
EXPECTED_ACCOUNT_HASH = "sha256:2837eb29d5ae"
MAX_THREADS_RUNNING = 8

IDENTITY_SQL = """SELECT VERSION() AS server_version,
       DATABASE() AS current_database,
       CURRENT_USER() AS authenticated_account,
       @@hostname AS server_hostname,
       @@port AS server_port,
       CONNECTION_ID() AS inspection_connection_id,
       @@session.autocommit AS session_autocommit,
       @@session.transaction_read_only AS transaction_read_only,
       @@session.max_execution_time AS max_execution_time_ms,
       @@session.lock_wait_timeout AS metadata_lock_wait_seconds,
       @@session.innodb_lock_wait_timeout AS row_lock_wait_seconds"""
GUARD_SQL = """SELECT @@session.autocommit AS session_autocommit,
       @@session.transaction_read_only AS transaction_read_only,
       @@session.max_execution_time AS max_execution_time_ms,
       @@session.lock_wait_timeout AS metadata_lock_wait_seconds,
       @@session.innodb_lock_wait_timeout AS row_lock_wait_seconds"""
LOCK_SQL = "SELECT IS_USED_LOCK('cip_etl') AS cip_etl_owner_connection_id"
PRESSURE_SQL = """SHOW GLOBAL STATUS
WHERE Variable_name IN (
    'Threads_connected', 'Threads_running', 'Connections',
    'Aborted_connects', 'Created_tmp_tables',
    'Created_tmp_disk_tables', 'Slow_queries', 'Questions', 'Uptime'
)"""

SQL_042 = """EXPLAIN FORMAT=JSON
SELECT c.dim_value AS segment, c.n, c.base_n, i.item_label,
       COALESCE(i.sort_order, 0) AS item_order, o.value_label,
       o.sort_order AS option_order, q.qtype, q.is_multi
FROM cip_stg.cip_agg_cell AS c
JOIN cip_stg.cip_question AS q ON q.question_id = c.question_id
LEFT JOIN cip_stg.cip_item AS i ON i.item_id = c.item_id
LEFT JOIN cip_stg.cip_option AS o ON o.option_id = c.option_id
WHERE c.survey_id = 262
  AND c.question_id = 7778
  AND c.dim = 'total'
  AND COALESCE(c.cohort_id, 0) = 0"""

SQL_045 = """EXPLAIN FORMAT=JSON
SELECT s.survey_id, s.wave_label, s.wave_date, s.platform,
       co.option_label AS answer, co.sort_order AS answer_order,
       c.n, c.base_n
FROM cip_stg.cip_concept_option AS co
JOIN cip_stg.cip_concept_map AS m
  ON m.concept_option_id = co.concept_option_id
 AND m.status = 'confirmed'
JOIN cip_stg.cip_agg_cell AS c
  ON c.survey_id = m.survey_id
 AND c.map_key = m.map_key
 AND c.cohort_id IS NULL
 AND c.dim = 'total'
JOIN cip_stg.cip_survey AS s
  ON s.survey_id = m.survey_id
 AND s.load_status = 'verified'
WHERE co.concept_id = 1"""


def _hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(str(value).encode()).hexdigest()[:12]


def _safe(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return value


def _run(cursor: DictCursor, sql_id: str, statement: str) -> dict[str, Any]:
    started = time.perf_counter()
    cursor.execute(statement)
    rows = cursor.fetchall() if cursor.description else []
    result = {
        "sql_id": sql_id,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
        "row_count": len(rows),
        "affected_rows": 0 if cursor.description else max(cursor.rowcount, 0),
        "rows": [{key: _safe(value) for key, value in row.items()} for row in rows],
        "status": "ok",
    }
    print(f"{sql_id}: ok ({result['elapsed_ms']:.3f} ms, {len(rows)} rows)", flush=True)
    return result


def _validate_identity(result: dict[str, Any]) -> None:
    row = result["rows"][0]
    if row["current_database"] != EXPECTED_DATABASE:
        raise RuntimeError("unexpected database")
    if "azure" not in str(row["server_version"]).lower():
        raise RuntimeError("unexpected server product")
    if _hash(row["server_hostname"]) != EXPECTED_SERVER_HOST_HASH:
        raise RuntimeError("server identity differs from Stage 1-3")
    if _hash(row["authenticated_account"]) != EXPECTED_ACCOUNT_HASH:
        raise RuntimeError("account identity differs from Stage 1-3")
    if int(row["server_port"]) != 3306 or int(row["session_autocommit"]) != 1:
        raise RuntimeError("unexpected port or autocommit state")
    row["server_hostname"] = EXPECTED_SERVER_HOST_HASH
    row["authenticated_account"] = EXPECTED_ACCOUNT_HASH
    row["inspection_connection_id"] = _hash(row["inspection_connection_id"])


def _validate_guards(result: dict[str, Any]) -> None:
    row = result["rows"][0]
    actual = tuple(
        int(row[name])
        for name in (
            "session_autocommit",
            "transaction_read_only",
            "max_execution_time_ms",
            "metadata_lock_wait_seconds",
            "row_lock_wait_seconds",
        )
    )
    if actual != (1, 1, 5000, 3, 3):
        raise RuntimeError(f"session guard mismatch: {actual}")


def _validate_lock(result: dict[str, Any]) -> None:
    if result["rows"][0]["cip_etl_owner_connection_id"] is not None:
        raise RuntimeError("cip_etl lock is held")


def _validate_pressure(result: dict[str, Any]) -> None:
    values = {row["Variable_name"]: int(row["Value"]) for row in result["rows"]}
    if values.get("Threads_running", MAX_THREADS_RUNNING + 1) > MAX_THREADS_RUNNING:
        raise RuntimeError("Threads_running exceeds approved limit")


def _parse_plan(result: dict[str, Any]) -> None:
    result["rows"] = [{"plan": json.loads(result["rows"][0]["EXPLAIN"])}]


def main() -> int:
    output: dict[str, Any] = {
        "target": EXPECTED_DATABASE,
        "approved": ["SQL-042", "SQL-045"],
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
            raise RuntimeError("configured staging target or credentials unavailable")
        ssl_args = db.connect_args.get("ssl")
        if ssl_args is None:
            raise RuntimeError("TLS configuration unavailable")
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
            safety = [
                ("SAFETY-IDENTITY", IDENTITY_SQL),
                ("SAFETY-READ-ONLY", "SET SESSION TRANSACTION READ ONLY"),
                ("SAFETY-SELECT-TIMEOUT", "SET SESSION max_execution_time = 5000"),
                ("SAFETY-MDL-TIMEOUT", "SET SESSION lock_wait_timeout = 3"),
                ("SAFETY-ROW-TIMEOUT", "SET SESSION innodb_lock_wait_timeout = 3"),
                ("SAFETY-VERIFY", GUARD_SQL),
            ]
            for sql_id, statement in safety:
                result = _run(cursor, sql_id, statement)
                if sql_id == "SAFETY-IDENTITY":
                    _validate_identity(result)
                elif sql_id == "SAFETY-VERIFY":
                    _validate_guards(result)
                output["statements"].append(result)

            for sql_id, statement in (("SQL-042", SQL_042), ("SQL-045", SQL_045)):
                lock = _run(cursor, f"MONITOR-LOCK-BEFORE-{sql_id}", LOCK_SQL)
                _validate_lock(lock)
                output["monitoring_checks"].append(lock)
                pressure = _run(cursor, f"MONITOR-PRESSURE-BEFORE-{sql_id}", PRESSURE_SQL)
                _validate_pressure(pressure)
                output["monitoring_checks"].append(pressure)
                result = _run(cursor, sql_id, statement)
                _parse_plan(result)
                output["statements"].append(result)

            final_guard = _run(cursor, "SAFETY-FINAL", GUARD_SQL)
            _validate_guards(final_guard)
            output["statements"].append(final_guard)
            output["open_transaction_after_plans"] = bool(
                connection.server_status & SERVER_STATUS.SERVER_STATUS_IN_TRANS
            )
            if output["open_transaction_after_plans"]:
                raise RuntimeError("transaction remained open after plans")
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
