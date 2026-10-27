"""Execute the final owner-approved SQL-046 and SQL-047 staging checks."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pymysql
from pymysql.constants import SERVER_STATUS
from pymysql.cursors import DictCursor

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.core.config import Config
from scripts import cip_stage4_readonly as guards


OUTPUT_PATH = REPO_ROOT / (
    "docs/performance/cip_staging_verification/evidence/"
    "FINAL_STAGING_SANITIZED_RESULTS.json"
)

SQL_046 = """EXPLAIN FORMAT=JSON
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
 AND (c.cohort_id IS NULL OR c.cohort_id = 0)
 AND c.dim = 'total'
JOIN cip_stg.cip_survey AS s
  ON s.survey_id = m.survey_id
 AND s.load_status = 'verified'
WHERE co.concept_id = 1"""

SQL_047 = """SELECT cell_id, survey_id
FROM cip_stg.cip_agg_cell
WHERE survey_id = 262
  AND cohort_id = 0
LIMIT 1"""


def main() -> int:
    output: dict[str, Any] = {
        "target": guards.EXPECTED_DATABASE,
        "approved": ["SQL-046", "SQL-047"],
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
        if (
            db.database != guards.EXPECTED_DATABASE
            or not db.host
            or not db.user
            or not db.password
        ):
            raise RuntimeError("configured staging target or credentials unavailable")
        ssl_args = db.connect_args.get("ssl")
        if ssl_args is None:
            raise RuntimeError("TLS configuration unavailable")
        connection = pymysql.connect(
            host=db.host,
            port=db.port,
            user=db.user,
            password=db.password,
            database=guards.EXPECTED_DATABASE,
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
                ("SAFETY-IDENTITY", guards.IDENTITY_SQL),
                ("SAFETY-READ-ONLY", "SET SESSION TRANSACTION READ ONLY"),
                ("SAFETY-SELECT-TIMEOUT", "SET SESSION max_execution_time = 5000"),
                ("SAFETY-MDL-TIMEOUT", "SET SESSION lock_wait_timeout = 3"),
                ("SAFETY-ROW-TIMEOUT", "SET SESSION innodb_lock_wait_timeout = 3"),
                ("SAFETY-VERIFY", guards.GUARD_SQL),
            ]
            for sql_id, statement in safety:
                result = guards._run(cursor, sql_id, statement)
                if sql_id == "SAFETY-IDENTITY":
                    guards._validate_identity(result)
                elif sql_id == "SAFETY-VERIFY":
                    guards._validate_guards(result)
                output["statements"].append(result)

            for sql_id, statement in (("SQL-046", SQL_046), ("SQL-047", SQL_047)):
                lock = guards._run(cursor, f"MONITOR-LOCK-BEFORE-{sql_id}", guards.LOCK_SQL)
                guards._validate_lock(lock)
                output["monitoring_checks"].append(lock)
                pressure = guards._run(
                    cursor,
                    f"MONITOR-PRESSURE-BEFORE-{sql_id}",
                    guards.PRESSURE_SQL,
                )
                guards._validate_pressure(pressure)
                output["monitoring_checks"].append(pressure)
                result = guards._run(cursor, sql_id, statement)
                if sql_id == "SQL-046":
                    guards._parse_plan(result)
                output["statements"].append(result)

            final_guard = guards._run(cursor, "SAFETY-FINAL", guards.GUARD_SQL)
            guards._validate_guards(final_guard)
            output["statements"].append(final_guard)
            output["open_transaction_after_checks"] = bool(
                connection.server_status & SERVER_STATUS.SERVER_STATUS_IN_TRANS
            )
            if output["open_transaction_after_checks"]:
                raise RuntimeError("transaction remained open after checks")
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
