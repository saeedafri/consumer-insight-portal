"""Stress the real database with the query one screen widget needs, three ways, at rising concurrency.

  raw      aggregate the answer table at request time (the "MySQL + Streamlit, just show it" habit)
  cube     read the pre-aggregated cube and do the joins and percentages at request time
  serving  read the ETL's finished rows (srv_result): one primary-key range, nothing to compute

Each connection runs its query back-to-back for --seconds. Reports queries/s and latency; the
network round trip (SELECT 1) is measured first so the database's own time can be separated.
Read-only.

    PYTHONPATH=. python scripts/ui_benchmark/db_stress.py --survey 412 --levels 1,8,32,64 --seconds 20
"""
import argparse, statistics, threading, time

from sqlalchemy import create_engine, text

from app.core import config

QUESTION, DIM = "XM3", "generation"   # one widget: holiday-shopping status by generation

QUERIES = {
    "raw": """
        SELECT p.generation, a.value_code, COUNT(*) AS n
          FROM cip_answer a
          JOIN cip_field f ON f.field_id = a.field_id
          JOIN cip_question q ON q.question_id = f.question_id AND q.survey_id = :s AND q.qcode = :q
          JOIN cip_respondent r ON r.respondent_id = a.respondent_id AND r.is_qualified = 1
          JOIN cip_profile p ON p.respondent_id = a.respondent_id
         WHERE a.survey_id = :s
         GROUP BY p.generation, a.value_code""",
    "cube": """
        SELECT c.dim_value, o.value_code, o.value_label, c.n, c.base_n, ROUND(100 * c.n / c.base_n, 1) AS pct
          FROM cip_agg_cell c
          JOIN cip_question q ON q.question_id = c.question_id AND q.survey_id = c.survey_id AND q.qcode = :q
          LEFT JOIN cip_option o ON o.option_id = c.option_id
         WHERE c.survey_id = :s AND c.dim = :d AND c.cohort_id IS NULL""",
    "serving": """
        SELECT dim_value, option_code, option_label, n, base_n, pct, prior_pct, ly_pct, flags
          FROM srv_result WHERE survey_id = :s AND qcode = :q AND dim = :d""",
}


def engine(pool):
    db = config.config.database("app")
    return create_engine(db.url, pool_size=pool, max_overflow=0, pool_pre_ping=False,
                         connect_args=db.connect_args if hasattr(db, "connect_args") else {})


def run(eng, sql, params, workers, seconds):
    latencies, stop = [], time.perf_counter() + seconds
    lock = threading.Lock()

    def loop():
        with eng.connect() as conn:
            mine = []
            while time.perf_counter() < stop:
                t = time.perf_counter()
                conn.execute(text(sql), params).all()
                mine.append(time.perf_counter() - t)
        with lock:
            latencies.extend(mine)

    threads = [threading.Thread(target=loop) for _ in range(workers)]
    start = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    lat = sorted(latencies)
    pick = lambda q: lat[min(len(lat) - 1, int(q * len(lat)))] * 1000
    return len(lat) / (time.perf_counter() - start), statistics.median(lat) * 1000, pick(.95), pick(.99)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--survey", type=int, default=412)
    p.add_argument("--levels", default="1,8,32,64")
    p.add_argument("--seconds", type=int, default=20)
    p.add_argument("--only", default="serving,cube,raw")
    a = p.parse_args()
    levels = [int(x) for x in a.levels.split(",")]
    eng = engine(max(levels))
    params = {"s": a.survey, "q": QUESTION, "d": DIM}
    _, rtt, _, _ = run(eng, "SELECT 1", {}, 1, 5)
    print(f"network round trip (SELECT 1, 1 connection): p50={rtt:.1f} ms", flush=True)
    for name in a.only.split(","):
        with eng.connect() as conn:
            rows = len(conn.execute(text(QUERIES[name]), params).all())
        for n in levels:
            qps, p50, p95, p99 = run(eng, QUERIES[name], params, n, a.seconds)
            print(f"{name:<8} conns={n:<3} rows={rows:<3} qps={qps:8.1f}  p50={p50:7.1f}ms p95={p95:7.1f}ms p99={p99:7.1f}ms"
                  f"  db_time_p50≈{max(p50 - rtt, 0):6.1f}ms", flush=True)


if __name__ == "__main__":
    main()
