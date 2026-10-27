"""Offline synthetic benchmark for the publisher's two srv_answer reads."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import resource
import socket
import statistics
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def blocked(*args, **kwargs):
    raise RuntimeError("network is disabled for this benchmark")


socket.socket.connect = blocked
socket.socket.connect_ex = blocked
socket.socket.sendto = blocked
socket.create_connection = blocked
for name in (
    "ANTHROPIC_API_KEY", "APP_DB_PASSWORD", "APP_DB_USER", "CIP_NGINX_URL",
    "CIP_PUBLISH_BACKUP_URL", "EMAIL_PASSWORD", "FORSTA_API_KEY", "STG_DB_HOST",
    "STG_DB_NAME", "STG_DB_PASSWORD", "STG_DB_USER", "TEAMS_WEBHOOK_URL",
):
    os.environ[name] = ""
os.environ["APP_ENV"] = "LOCAL"


def percentile(samples: list[float], p: float) -> float:
    ordered = sorted(samples)
    return ordered[min(len(ordered) - 1, int((len(ordered) - 1) * p))]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--label", required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.source_root.resolve()))

    import sqlalchemy as sa
    from app.data import payloads

    with tempfile.TemporaryDirectory(prefix="cip-reaudit-bench-") as temp:
        path = Path(temp) / "bench.db"
        engine = sa.create_engine(f"sqlite:///{path}", future=True)
        with engine.begin() as conn:
            conn.exec_driver_sql("""CREATE TABLE srv_answer (
                survey_id INTEGER, respondent_id INTEGER, qcode TEXT, item_id INTEGER, option_id INTEGER,
                gender TEXT, age_band TEXT, generation TEXT, income_band TEXT, census_region TEXT, urbanicity TEXT)""")
            conn.exec_driver_sql("""CREATE TABLE srv_result (
                survey_id INTEGER, qcode TEXT, item_id INTEGER, option_id INTEGER, item_label TEXT,
                option_code TEXT, option_label TEXT, sort_order INTEGER, flags TEXT,
                concept_option_id INTEGER, question_id INTEGER, dim TEXT)""")
            conn.exec_driver_sql("CREATE TABLE cip_question (question_id INTEGER PRIMARY KEY, qtext TEXT)")

        next_question = 1

        def seed(survey_id: int, respondents: int, questions: int) -> None:
            nonlocal next_question
            answer_rows = []
            result_rows = []
            question_rows = []
            for q in range(questions):
                qid = next_question
                next_question += 1
                qcode = f"Q{q:03d}"
                question_rows.append((qid, f"Synthetic question {q}"))
                for option in (1, 2):
                    result_rows.append((survey_id, qcode, 0, option, "", str(option), f"Option {option}",
                                        option, "", None, qid, "total"))
                for rid in range(respondents):
                    option = 1 + ((rid + q) % 2)
                    answer_rows.append((survey_id, survey_id * 10_000_000 + rid, qcode, 0, option,
                                        ("Male", "male", "Mále")[rid % 3],
                                        ("18-29", "30-44", None)[rid % 3],
                                        ("GenZ", "Millennial")[rid % 2],
                                        ("Low", "High", "")[rid % 3],
                                        ("Northeast", "South")[rid % 2],
                                        ("Urban", "Rural")[rid % 2]))
            with engine.begin() as conn:
                conn.exec_driver_sql("INSERT INTO cip_question VALUES (?, ?)", question_rows)
                conn.exec_driver_sql("INSERT INTO srv_result VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", result_rows)
                conn.exec_driver_sql("INSERT INTO srv_answer VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", answer_rows)

        query_counts = {"srv_answer": 0, "total": 0}

        def count_sql(_conn, _cursor, statement, _parameters, _context, _executemany):
            query_counts["total"] += 1
            if " from srv_answer " in f" {' '.join(statement.lower().split())} ":
                query_counts["srv_answer"] += 1

        sa.event.listen(engine, "before_cursor_execute", count_sql)

        def one(survey_id: int) -> tuple[str, int]:
            with engine.connect() as conn:
                if hasattr(payloads, "respondent_answers"):
                    answers = payloads.respondent_answers(conn, [survey_id])
                    cuts = payloads.question_cuts(conn, [survey_id])
                    people = payloads.people(conn, survey_id, answer_rows=answers)
                else:
                    cuts = payloads.question_cuts(conn, [survey_id])
                    people = payloads.people(conn, survey_id)
            digest = hashlib.sha256()
            size = 0
            for key in sorted(cuts):
                body = payloads.encode(cuts[key])
                digest.update(body)
                size += len(body)
            body = payloads.encode(people)
            digest.update(body)
            size += len(body)
            return digest.hexdigest(), size

        sizes = [(250, 10), (1000, 20), (2500, 30)]
        size_results = []
        for survey_id, (respondents, questions) in enumerate(sizes, 1):
            seed(survey_id, respondents, questions)
            one(survey_id)
            samples = []
            errors = 0
            before = dict(query_counts)
            digest = ""
            result_bytes = 0
            for _ in range(5):
                started = time.perf_counter()
                try:
                    digest, result_bytes = one(survey_id)
                except Exception:
                    errors += 1
                samples.append(time.perf_counter() - started)
            size_results.append({
                "respondents": respondents,
                "questions": questions,
                "answer_rows": respondents * questions,
                "samples": len(samples),
                "median_s": round(statistics.median(samples), 6),
                "p95_s": round(percentile(samples, 0.95), 6),
                "min_s": round(min(samples), 6),
                "max_s": round(max(samples), 6),
                "srv_answer_queries_per_sample": (query_counts["srv_answer"] - before["srv_answer"]) / len(samples),
                "sql_queries_per_sample": (query_counts["total"] - before["total"]) / len(samples),
                "result_bytes": result_bytes,
                "output_sha256": digest,
                "errors": errors,
            })

        concurrency_ids = []
        for survey_id in range(101, 105):
            seed(survey_id, 1000, 20)
            concurrency_ids.append(survey_id)
        concurrency = []
        for jobs in (1, 2, 4):
            with ThreadPoolExecutor(max_workers=jobs) as pool:
                list(pool.map(one, concurrency_ids))
            samples = []
            errors = 0
            hashes = []
            for _ in range(3):
                started = time.perf_counter()
                try:
                    with ThreadPoolExecutor(max_workers=jobs) as pool:
                        hashes = [value[0] for value in pool.map(one, concurrency_ids)]
                except Exception:
                    errors += 1
                samples.append(time.perf_counter() - started)
            concurrency.append({
                "jobs": jobs,
                "samples": len(samples),
                "median_s": round(statistics.median(samples), 6),
                "p95_s": round(percentile(samples, 0.95), 6),
                "output_sha256": hashlib.sha256("".join(hashes).encode()).hexdigest(),
                "errors": errors,
            })

        print(json.dumps({
            "label": args.label,
            "source_head": "6f978b0595b2c71c064991ae10b832514637a0da",
            "dataset": "synthetic SQLite; result_bytes are payload bytes, not MySQL wire bytes",
            "sizes": size_results,
            "concurrency": concurrency,
            "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        }, indent=2))


if __name__ == "__main__":
    main()
