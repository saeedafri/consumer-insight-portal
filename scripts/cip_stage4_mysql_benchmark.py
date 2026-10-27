"""Stage 4 disposable-MySQL correctness and resource benchmark."""
from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing as mp
import resource
import statistics
import sys
import threading
import time
import tracemalloc
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable

import pymysql
import sqlalchemy as sa
from sqlalchemy import event, text
from sqlalchemy.exc import TimeoutError as PoolTimeout

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

HOST = "127.0.0.1"
PORT = 33306
DATABASE = "cip_test"
QUESTIONS = 30
OPTIONS = 5
SURVEY_SPECS = ((9101, 2_000), (9102, 10_000), (9103, 30_000))
URL = f"mysql+pymysql://root@{HOST}:{PORT}/{DATABASE}?charset=utf8mb4"
CURRENT_TRACED_LIMIT = 512 * 1024 * 1024
CURRENT_RSS_LIMIT = 1024 * 1024 * 1024


def raw_connection(autocommit: bool = True):
    return pymysql.connect(
        host=HOST,
        port=PORT,
        user="root",
        password="",
        database=DATABASE,
        charset="utf8mb4",
        autocommit=autocommit,
        connect_timeout=3,
        read_timeout=60,
        write_timeout=60,
        local_infile=False,
    )


def engine():
    return sa.create_engine(
        URL,
        pool_size=1,
        max_overflow=0,
        pool_timeout=2,
        pool_pre_ping=False,
        future=True,
    )


def batches(rows, size: int = 10_000):
    batch = []
    for row in rows:
        batch.append(row)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch


def qid(survey_id: int, question: int) -> int:
    return survey_id * 100 + question


def oid(survey_id: int, question: int, option: int) -> int:
    return survey_id * 10_000 + question * 10 + option


def rid(survey_id: int, respondent: int) -> int:
    return survey_id * 100_000 + respondent


def cut_values(respondent: int) -> tuple[str, ...]:
    return (
        "" if respondent % 97 == 0 else ("Male", "Female")[respondent % 2],
        "" if respondent % 89 == 0 else ("18-29", "30-44", "45-59", "60+")[respondent % 4],
        ("Gen Z", "Millennial", "Gen X", "Boomer")[respondent % 4],
        ("Under $25k", "$25k-$49k", "$50k-$99k", "$100k+")[respondent % 4],
        ("Northeast", "Midwest", "South", "West")[respondent % 4],
        ("Urban", "Suburban", "Rural")[respondent % 3],
    )


def reset() -> None:
    with raw_connection() as conn, conn.cursor() as cursor:
        cursor.execute("SELECT DATABASE(), VERSION(), @@collation_server, @@local_infile")
        database, version, collation, local_infile = cursor.fetchone()
        if (
            database != DATABASE
            or not version.startswith("8.")
            or collation != "utf8mb4_0900_ai_ci"
            or int(local_infile) != 0
        ):
            raise RuntimeError("refusing non-disposable or incorrectly configured target")
        cursor.execute("SET FOREIGN_KEY_CHECKS=0")
        cursor.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema=%s AND table_type='BASE TABLE'",
            (DATABASE,),
        )
        for (table,) in cursor.fetchall():
            cursor.execute(f"TRUNCATE TABLE `{table}`")
        cursor.execute("SET FOREIGN_KEY_CHECKS=1")


def seed() -> dict[str, Any]:
    reset()
    started = time.perf_counter()
    with raw_connection(autocommit=False) as conn, conn.cursor() as cursor:
        cursor.executemany(
            "INSERT INTO cip_survey "
            "(survey_id,forsta_host,forsta_path,title,survey_family,wave_label,wave_date,platform,source_ref,study_type,load_status) "
            "VALUES (%s,'local',%s,'Stage 4 synthetic','STAGE4',%s,%s,'forsta',%s,'tracker','verified')",
            [
                (sid, f"stage4/{sid}", f"2026-02-{index + 1:02d}", f"2026-02-{index + 1:02d}", f"stage4/{sid}")
                for index, (sid, _) in enumerate(SURVEY_SPECS)
            ],
        )
        cursor.execute(
            "INSERT INTO cip_concept (concept_id,concept_code,concept_name,qtype) "
            "VALUES (1,'STAGE4','Stage 4 concept','single')"
        )
        cursor.executemany(
            "INSERT INTO cip_concept_option "
            "(concept_option_id,concept_id,option_code,option_label,sort_order) VALUES (%s,1,%s,%s,%s)",
            [(option, str(option), f"Option {option}", option) for option in range(1, OPTIONS + 1)],
        )
        cursor.executemany(
            "INSERT INTO cip_cohort_def (cohort_id,cohort_code,version,cohort_name,rule_json) "
            "VALUES (%s,%s,1,%s,JSON_OBJECT())",
            [(cohort, f"C{cohort}", f"Cohort {cohort}") for cohort in range(1, 201)],
        )

        for wave_index, (sid, respondents) in enumerate(SURVEY_SPECS):
            cursor.executemany(
                "INSERT INTO cip_question "
                "(question_id,survey_id,qcode,qtext,qtype,is_multi,sort_order) "
                "VALUES (%s,%s,%s,%s,'single',0,%s)",
                [
                    (qid(sid, question), sid, f"Q{question:03d}", f"Synthetic question {question}", question)
                    for question in range(1, QUESTIONS + 1)
                ],
            )
            cursor.executemany(
                "INSERT INTO cip_option (option_id,question_id,value_code,value_label,sort_order) "
                "VALUES (%s,%s,%s,%s,%s)",
                [
                    (oid(sid, question, option), qid(sid, question), option, f"Option {option}", option)
                    for question in range(1, QUESTIONS + 1)
                    for option in range(1, OPTIONS + 1)
                ],
            )
            cursor.execute(
                "INSERT INTO srv_wave "
                "(survey_id,survey_family,study_type,wave_date,qualified_n,rows_built) "
                "SELECT survey_id,survey_family,study_type,wave_date,%s,0 "
                "FROM cip_survey WHERE survey_id=%s",
                (respondents, sid),
            )
            cursor.executemany(
                "INSERT INTO srv_result "
                "(survey_id,qcode,dim,dim_value,item_id,option_id,question_id,qtype,item_label,option_code,option_label,"
                "sort_order,n,base_n,pct) "
                "VALUES (%s,%s,'total','Total',0,%s,%s,'single','',%s,%s,%s,%s,%s,%s)",
                [
                    (
                        sid,
                        f"Q{question:03d}",
                        oid(sid, question, option),
                        qid(sid, question),
                        option,
                        f"Option {option}",
                        option,
                        respondents // OPTIONS,
                        respondents,
                        100 / OPTIONS,
                    )
                    for question in range(1, QUESTIONS + 1)
                    for option in range(1, OPTIONS + 1)
                ],
            )
            rows = (
                (
                    sid,
                    f"Q{question:03d}",
                    0,
                    oid(sid, question, 1 + (respondent + question) % OPTIONS),
                    rid(sid, respondent),
                    *cut_values(respondent),
                )
                for respondent in range(respondents, 0, -1)
                for question in range(1, QUESTIONS + 1)
            )
            for batch in batches(rows):
                cursor.executemany(
                    "INSERT INTO srv_answer "
                    "(survey_id,qcode,item_id,option_id,respondent_id,gender,age_band,generation,income_band,census_region,urbanicity) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    batch,
                )

            question = 1
            option = 1
            map_key = f"{qid(sid, question)}:0:{oid(sid, question, option)}"
            cursor.execute(
                "INSERT INTO cip_concept_map "
                "(survey_id,map_key,question_id,option_id,concept_id,concept_option_id,status,method) "
                "VALUES (%s,%s,%s,%s,1,1,'confirmed','manual')",
                (sid, map_key, qid(sid, question), oid(sid, question, option)),
            )
            for cohort in (None, 0, *range(1, 201)):
                count = 10 if cohort is None else (4 if cohort == 0 else 2)
                base = 100 if cohort is None else (40 if cohort == 0 else 20)
                cohort_key = "null" if cohort is None else str(cohort)
                cursor.execute(
                    "INSERT INTO cip_agg_cell "
                    "(survey_id,cell_key,map_key,question_id,option_id,cohort_id,dim,dim_value,n,base_n) "
                    "VALUES (%s,%s,%s,%s,%s,%s,'total','Total',%s,%s)",
                    (
                        sid,
                        f"stage4:{sid}:{cohort_key}",
                        map_key,
                        qid(sid, question),
                        oid(sid, question, option),
                        cohort,
                        count,
                        base,
                    ),
                )
        conn.commit()
    return {
        "seed_seconds": round(time.perf_counter() - started, 6),
        "surveys": [
            {"survey_id": sid, "respondents": respondents, "srv_answer_rows": respondents * QUESTIONS}
            for sid, respondents in SURVEY_SPECS
        ],
        "total_srv_answer_rows": sum(respondents * QUESTIONS for _, respondents in SURVEY_SPECS),
    }


def payload_digest(value: Any) -> str:
    from app.data import payloads

    return hashlib.sha256(payloads.encode(value)).hexdigest()


def _session_bytes(conn) -> int:
    return int(conn.exec_driver_sql("SHOW SESSION STATUS LIKE 'Bytes_sent'").one()[1])


def _rss_bytes() -> int:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform == "darwin" else value * 1024)


def _measure_child(kind: str, survey_id: int, output_queue) -> None:
    from app.data import payloads
    from scripts.cip_stage3_mysql_benchmark import baseline_people

    function: Callable = baseline_people if kind == "baseline" else payloads.people
    eng = engine()
    statements = []

    def record(_conn, _cursor, statement, _parameters, _context, _executemany):
        normalized = " ".join(statement.lower().split())
        if " from srv_answer " in f" {normalized} " or " from srv_result " in f" {normalized} ":
            statements.append(normalized)

    event.listen(eng, "before_cursor_execute", record)
    error = None
    try:
        with eng.connect() as conn:
            before_bytes = _session_bytes(conn)
            tracemalloc.start()
            started = time.perf_counter()
            output = function(conn, survey_id)
            wall = time.perf_counter() - started
            traced_peak = tracemalloc.get_traced_memory()[1]
            tracemalloc.stop()
            after_bytes = _session_bytes(conn)
        result = {
            "kind": kind,
            "survey_id": survey_id,
            "wall_s": round(wall, 6),
            "traced_peak_bytes": traced_peak,
            "process_peak_rss_bytes": _rss_bytes(),
            "bytes_sent_delta": after_bytes - before_bytes,
            "output_bytes": len(payloads.encode(output)),
            "sha256": payload_digest(output),
            "application_selects": len(statements),
            "srv_answer_selects": sum(" from srv_answer " in f" {sql} " for sql in statements),
            "srv_result_selects": sum(" from srv_result " in f" {sql} " for sql in statements),
            "pool_checked_out_after": eng.pool.checkedout(),
        }
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        result = {"kind": kind, "survey_id": survey_id, "error": error}
    finally:
        event.remove(eng, "before_cursor_execute", record)
        eng.dispose()
    output_queue.put(result)


def measure(kind: str, survey_id: int) -> dict[str, Any]:
    context = mp.get_context("spawn")
    output_queue = context.Queue()
    process = context.Process(target=_measure_child, args=(kind, survey_id, output_queue))
    process.start()
    process.join(180)
    if process.is_alive():
        process.terminate()
        process.join(10)
        raise RuntimeError(f"{kind} survey {survey_id} exceeded 180 seconds")
    if process.exitcode != 0:
        raise RuntimeError(f"{kind} survey {survey_id} exited {process.exitcode}")
    result = output_queue.get(timeout=5)
    if "error" in result:
        raise RuntimeError(result["error"])
    return result


def summarize(samples: list[dict[str, Any]]) -> dict[str, Any]:
    def metric(name: str) -> dict[str, Any]:
        values = [sample[name] for sample in samples]
        return {
            "values": values,
            "median": statistics.median(values),
            "min": min(values),
            "max": max(values),
        }

    return {
        "samples": len(samples),
        "wall_s": metric("wall_s"),
        "traced_peak_bytes": metric("traced_peak_bytes"),
        "process_peak_rss_bytes": metric("process_peak_rss_bytes"),
        "bytes_sent_delta": metric("bytes_sent_delta"),
        "output_bytes": sorted({sample["output_bytes"] for sample in samples}),
        "hashes": sorted({sample["sha256"] for sample in samples}),
        "application_selects": sorted({sample["application_selects"] for sample in samples}),
        "srv_answer_selects": sorted({sample["srv_answer_selects"] for sample in samples}),
        "srv_result_selects": sorted({sample["srv_result_selects"] for sample in samples}),
        "pool_checked_out_after": sorted({sample["pool_checked_out_after"] for sample in samples}),
    }


def extraction_benchmarks(samples: int) -> list[dict[str, Any]]:
    results = []
    for survey_id, respondents in SURVEY_SPECS:
        baseline = [measure("baseline", survey_id) for _ in range(samples)]
        current = [measure("current", survey_id) for _ in range(samples)]
        baseline_summary = summarize(baseline)
        current_summary = summarize(current)
        parity = baseline_summary["hashes"] == current_summary["hashes"]
        limits_passed = (
            current_summary["traced_peak_bytes"]["max"] <= CURRENT_TRACED_LIMIT
            and current_summary["process_peak_rss_bytes"]["max"] <= CURRENT_RSS_LIMIT
        )
        if not parity or not limits_passed:
            raise AssertionError(
                f"extraction contract failed for survey {survey_id}: parity={parity}, limits={limits_passed}"
            )
        results.append(
            {
                "survey_id": survey_id,
                "respondents": respondents,
                "srv_answer_rows": respondents * QUESTIONS,
                "baseline": baseline_summary,
                "current": current_summary,
                "exact_output_parity": parity,
                "current_memory_limits": {
                    "traced_limit_bytes": CURRENT_TRACED_LIMIT,
                    "rss_limit_bytes": CURRENT_RSS_LIMIT,
                    "passed": limits_passed,
                },
            }
        )
    return results


class InjectedStreamFailure(RuntimeError):
    pass


def exception_cleanup_test() -> dict[str, Any]:
    from app.data import payloads

    eng = engine()
    tracked = None
    raised = False

    class FailingResult:
        def __init__(self, inner):
            self.inner = inner
            self.closed = False

        def __iter__(self):
            for index, row in enumerate(self.inner, start=1):
                if index == 5_000:
                    raise InjectedStreamFailure("injected MySQL stream failure")
                yield row

        def close(self):
            self.inner.close()
            self.closed = True

    class ConnectionProxy:
        def __init__(self, inner):
            self.inner = inner

        def execute(self, statement, params):
            nonlocal tracked
            result = self.inner.execute(statement, params)
            if tracked is None and "srv_answer" in str(statement):
                tracked = FailingResult(result)
                return tracked
            return result

    try:
        with eng.connect() as conn:
            try:
                payloads.people(ConnectionProxy(conn), SURVEY_SPECS[-1][0])
            except InjectedStreamFailure:
                raised = True
            connection_reusable = conn.execute(text("SELECT 1")).scalar() == 1
        checked_out = eng.pool.checkedout()
    finally:
        eng.dispose()
    result = {
        "raised": raised,
        "result_closed": bool(tracked and tracked.closed),
        "connection_reusable": connection_reusable,
        "pool_checked_out_after": checked_out,
    }
    if result != {
        "raised": True,
        "result_closed": True,
        "connection_reusable": True,
        "pool_checked_out_after": 0,
    }:
        raise AssertionError(f"stream exception cleanup failed: {result}")
    return result


def connection_limit_test() -> dict[str, Any]:
    eng = sa.create_engine(
        URL,
        pool_size=4,
        max_overflow=0,
        pool_timeout=0.4,
        pool_pre_ping=False,
        future=True,
    )
    barrier = threading.Barrier(4)

    def hold(_index: int) -> str:
        try:
            with eng.connect() as conn:
                conn.execute(text("SELECT 1")).scalar()
                barrier.wait(timeout=2)
                time.sleep(0.8)
                return "connected"
        except PoolTimeout:
            return "timeout"

    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            outcomes = list(pool.map(hold, range(8)))
        result = {
            "pool_size": 4,
            "max_overflow": 0,
            "attempts": 8,
            "connected": outcomes.count("connected"),
            "timed_out": outcomes.count("timeout"),
            "pool_checked_out_after": eng.pool.checkedout(),
        }
    finally:
        eng.dispose()
    if result != {
        "pool_size": 4,
        "max_overflow": 0,
        "attempts": 8,
        "connected": 4,
        "timed_out": 4,
        "pool_checked_out_after": 0,
    }:
        raise AssertionError(f"connection limit failed: {result}")
    return result


CONCEPT_SQL = """SELECT c.cohort_id, c.n, c.base_n
FROM cip_concept_option co
JOIN cip_concept_map m ON m.concept_option_id=co.concept_option_id AND m.status='confirmed'
JOIN cip_agg_cell c ON c.survey_id=m.survey_id AND c.map_key=m.map_key
 AND c.dim='total' AND {predicate}
JOIN cip_survey s ON s.survey_id=m.survey_id AND s.load_status='verified'
WHERE co.concept_id=1"""


def _plan_tables(value: Any) -> list[dict[str, Any]]:
    found = []
    if isinstance(value, dict):
        if isinstance(value.get("table"), dict):
            found.append(value["table"])
        for child in value.values():
            found.extend(_plan_tables(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(_plan_tables(child))
    return found


def cohort_predicates(samples: int) -> dict[str, Any]:
    predicates = {
        "old_coalesce": "COALESCE(c.cohort_id,0)=0",
        "current_is_null": "c.cohort_id IS NULL",
        "compatibility_or": "(c.cohort_id IS NULL OR c.cohort_id=0)",
        "positive_cohort": "c.cohort_id=1",
    }
    output = {}
    with raw_connection() as conn, conn.cursor() as cursor:
        for name, predicate in predicates.items():
            sql = CONCEPT_SQL.format(predicate=predicate)
            cursor.execute(sql)
            cursor.fetchall()
            timings = []
            hashes = []
            rows_seen = []
            for _ in range(samples):
                started = time.perf_counter()
                cursor.execute(sql)
                rows = sorted(cursor.fetchall(), key=lambda row: (-1 if row[0] is None else row[0]))
                timings.append(time.perf_counter() - started)
                hashes.append(hashlib.sha256(json.dumps(rows, default=str).encode()).hexdigest())
                rows_seen.append(rows)
            cursor.execute("EXPLAIN FORMAT=JSON " + sql)
            plan = json.loads(cursor.fetchone()[0])
            cell = next(table for table in _plan_tables(plan) if table.get("table_name") == "c")
            output[name] = {
                "predicate": predicate,
                "rows": rows_seen[0],
                "row_count": len(rows_seen[0]),
                "n_sum": sum(row[1] for row in rows_seen[0]),
                "hashes": sorted(set(hashes)),
                "median_s": statistics.median(timings),
                "min_s": min(timings),
                "max_s": max(timings),
                "plan": plan,
                "cell_access": {
                    key: cell.get(key)
                    for key in (
                        "access_type",
                        "key",
                        "used_key_parts",
                        "rows_examined_per_scan",
                        "rows_produced_per_join",
                        "filtered",
                    )
                },
            }
    if output["old_coalesce"]["hashes"] != output["compatibility_or"]["hashes"]:
        raise AssertionError("compatibility predicate did not preserve old zero/NULL behavior")
    if output["old_coalesce"]["hashes"] == output["current_is_null"]["hashes"]:
        raise AssertionError("legacy zero fixture failed to expose the old/new behavior difference")
    return output


def public_repository_contract() -> dict[str, Any]:
    from app.core import database
    from app.data import repository

    eng = engine()
    database._engines["app"] = eng
    try:
        repository.concept_trend.clear()
        everyone = repository.concept_trend(1, None)
        repository.concept_trend.clear()
        positive = repository.concept_trend(1, 1)
        result = {
            "everyone_n": sorted(set(int(value) for value in everyone.n)),
            "everyone_base_n": sorted(set(int(value) for value in everyone.base_n)),
            "positive_n": sorted(set(int(value) for value in positive.n)),
            "positive_base_n": sorted(set(int(value) for value in positive.base_n)),
            "everyone_rows": len(everyone),
            "positive_rows": len(positive),
        }
        if result != {
            "everyone_n": [14],
            "everyone_base_n": [100],
            "positive_n": [2],
            "positive_base_n": [20],
            "everyone_rows": len(SURVEY_SPECS),
            "positive_rows": len(SURVEY_SPECS),
        }:
            raise AssertionError(f"repository cohort contract failed: {result}")
        return result
    finally:
        repository.concept_trend.clear()
        database._engines.clear()
        eng.dispose()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--predicate-samples", type=int, default=20)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.samples < 1 or args.predicate_samples < 1:
        raise ValueError("sample counts must be positive")
    result = {
        "environment": {
            "target": f"{HOST}:{PORT}/{DATABASE}",
            "synthetic": True,
            "notification_transports": "not imported or invoked",
        },
        "seed": seed(),
        "cohort_predicates": cohort_predicates(args.predicate_samples),
        "repository_contract": public_repository_contract(),
        "stream_exception_cleanup": exception_cleanup_test(),
        "connection_limit": connection_limit_test(),
        "extraction": extraction_benchmarks(args.samples),
        "errors": [],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(
        json.dumps(
            {
                "seed": result["seed"],
                "cohort_rows": {
                    name: value["rows"] for name, value in result["cohort_predicates"].items()
                },
                "stream_exception_cleanup": result["stream_exception_cleanup"],
                "connection_limit": result["connection_limit"],
                "extraction": [
                    {
                        "survey_id": row["survey_id"],
                        "srv_answer_rows": row["srv_answer_rows"],
                        "exact_output_parity": row["exact_output_parity"],
                        "current_traced_peak": row["current"]["traced_peak_bytes"]["max"],
                        "current_rss_peak": row["current"]["process_peak_rss_bytes"]["max"],
                    }
                    for row in result["extraction"]
                ],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
