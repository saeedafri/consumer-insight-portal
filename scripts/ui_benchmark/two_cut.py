"""Two-cut (e.g. generation × gender) on one wave, three ways, measured inside MySQL:

  raw         aggregate cip_answer at request time
  respondent  one row per qualified single-choice answer and per multi-select item chosen, plus one
              base row (iid 0) per respondent per multi question, with every cut on each row (the
              cube's own input rows, kept as a table); GROUP BY two cuts at request time
  pairs       every pair of cuts pre-counted by the ETL; one primary-key range read
  serving     today's one-cut srv_result read, for reference

Builds two prototype tables for one wave in cip_stg (tmp_two_cut_respondent, tmp_two_cut_pairs),
checks the two-cut numbers add up to srv_result, reports server time (EXPLAIN ANALYZE),
throughput (in-server loops from --sessions parallel sessions, no network), table size and
how many two-cut cells fall under the small-base line. Drops everything it made unless --keep.

    PYTHONPATH=. python scripts/ui_benchmark/two_cut.py --survey 412
"""
import argparse, itertools, re, statistics, threading, time

from sqlalchemy import create_engine, text

from app.core import config
from app.data.cube import ANSWER_ROWS

CUTS = ("gender", "age_band", "generation", "income_band", "census_region", "urbanicity")
SINGLE, MULTI = "XM3", "XM2"   # holiday shopping status; retailers (multi-select)
D1, D2 = "gender", "generation"   # stored in CUTS order
RESPONDENT, PAIRS = "tmp_two_cut_respondent", "tmp_two_cut_pairs"


def engine(pool):
    db = config.config.database("app")
    return create_engine(db.url, pool_size=pool, max_overflow=0,
                         connect_args=db.connect_args if hasattr(db, "connect_args") else {})


def build(conn, sid):
    conn.execute(text(f"DROP TABLE IF EXISTS {RESPONDENT}, {PAIRS}"))
    cuts = ", ".join(f"COALESCE(p.{d}, '') AS {d}" for d in CUTS)
    answers = ANSWER_ROWS.format(cuts=cuts)
    conn.execute(text(f"""
        CREATE TABLE {RESPONDENT} (id BIGINT AUTO_INCREMENT, PRIMARY KEY (survey_id, qid, id), KEY (id))
        SELECT {sid} AS survey_id, x.* FROM ({answers} AND (q.is_multi = 0 OR a.value_code = 1)) x"""), {"sid": sid})
    names = ", ".join(CUTS)
    conn.execute(text(f"""
        INSERT INTO {RESPONDENT} (survey_id, qid, iid, oid, multi, code, rid, {names})
        SELECT DISTINCT {sid}, qid, 0, NULL, 1, 0, rid, {names} FROM ({answers}) y WHERE y.multi = 1"""), {"sid": sid})
    conn.execute(text(f"""
        CREATE TABLE {PAIRS} (
            survey_id INT NOT NULL, qid INT NOT NULL, d1 VARCHAR(20) NOT NULL, d2 VARCHAR(20) NOT NULL,
            v1 VARCHAR(40) NOT NULL, v2 VARCHAR(40) NOT NULL, iid INT NOT NULL, oid INT NOT NULL,
            n INT NOT NULL, base_n INT NOT NULL,
            PRIMARY KEY (survey_id, qid, d1, d2, v1, v2, iid, oid))"""))
    for a, b in itertools.combinations(CUTS, 2):
        # multi base = the cell's iid-0 rows; single base = everyone in the cell who answered that row
        conn.execute(text(f"""
            INSERT INTO {PAIRS}
            SELECT survey_id, qid, '{a}', '{b}', v1, v2, iid, oid, n, base_n FROM (
              SELECT survey_id, qid, multi, {a} AS v1, {b} AS v2, COALESCE(iid, 0) AS iid, COALESCE(oid, 0) AS oid,
                     COUNT(*) AS n,
                     IF(multi = 1, SUM(IF(iid = 0, COUNT(*), 0)) OVER w, SUM(COUNT(*)) OVER w) AS base_n
                FROM {RESPONDENT} GROUP BY survey_id, qid, multi, iid, oid, {a}, {b}
              WINDOW w AS (PARTITION BY qid, IF(multi = 1, 0, iid), {a}, {b})) t
             WHERE NOT (multi = 1 AND iid = 0)"""))
    conn.execute(text(f"ANALYZE TABLE {RESPONDENT}, {PAIRS}"))


def queries(sid, single, multi):
    raw_from = f"""
          FROM cip_answer a
          JOIN cip_field f ON f.field_id = a.field_id
          JOIN cip_question q ON q.question_id = f.question_id AND q.survey_id = {sid} AND q.question_id = {{qid}}
          JOIN cip_respondent r ON r.respondent_id = a.respondent_id AND r.is_qualified = 1
          JOIN cip_profile p ON p.respondent_id = a.respondent_id
         WHERE a.survey_id = {sid} AND a.value_code IS NOT NULL"""
    return {
        "raw single": f"SELECT p.{D1}, p.{D2}, a.value_code, COUNT(*) {raw_from.format(qid=single)}"
                      f" GROUP BY p.{D1}, p.{D2}, a.value_code",
        "raw multi": f"SELECT p.{D1}, p.{D2}, f.item_id, SUM(a.value_code = 1), COUNT(*) {raw_from.format(qid=multi)}"
                     f" GROUP BY p.{D1}, p.{D2}, f.item_id",
        "respondent single": f"""
            SELECT {D1}, {D2}, oid, COUNT(*) AS n, SUM(COUNT(*)) OVER (PARTITION BY {D1}, {D2}) AS base_n
              FROM {RESPONDENT} WHERE survey_id = {sid} AND qid = {single} GROUP BY {D1}, {D2}, oid""",
        "respondent multi": f"""
            SELECT {D1}, {D2}, iid, COUNT(*) AS n, SUM(IF(iid = 0, COUNT(*), 0)) OVER (PARTITION BY {D1}, {D2}) AS base_n
              FROM {RESPONDENT} WHERE survey_id = {sid} AND qid = {multi} GROUP BY {D1}, {D2}, iid""",
        "pairs single": f"SELECT v1, v2, oid, n, base_n FROM {PAIRS} WHERE survey_id = {sid} AND qid = {single}"
                        f" AND d1 = '{D1}' AND d2 = '{D2}'",
        "pairs multi": f"SELECT v1, v2, iid, n, base_n FROM {PAIRS} WHERE survey_id = {sid} AND qid = {multi}"
                       f" AND d1 = '{D1}' AND d2 = '{D2}'",
        "serving (one cut)": f"SELECT dim_value, option_code, n, base_n, pct FROM srv_result"
                             f" WHERE survey_id = {sid} AND qcode = '{SINGLE}' AND dim = '{D1}'",
    }


def check(conn, sid):
    """Summed over the second cut, the two-cut counts and bases must equal srv_result's one-cut rows.
    Pair rows exist only where an answer was picked, so bases are summed once per cell, not per answer."""
    for qcode in (SINGLE, MULTI):
        args = {"s": sid, "q": qcode, "d1": D1, "d2": D2}
        pairs = f"""FROM {PAIRS} p JOIN cip_question q ON q.question_id = p.qid AND q.qcode = :q
                    WHERE p.survey_id = :s AND p.d1 = :d1 AND p.d2 = :d2 AND p.v1 <> ''"""
        counts = dict(((v, int(i), int(o)), int(n)) for v, i, o, n in conn.execute(text(
            f"SELECT p.v1, p.iid, p.oid, SUM(p.n) {pairs} GROUP BY p.v1, p.iid, p.oid"), args))
        bases = dict((v, int(b)) for v, b in conn.execute(text(
            f"SELECT v1, SUM(base_n) FROM (SELECT p.v1, p.v2, MAX(p.base_n) AS base_n {pairs}"
            " GROUP BY p.v1, p.v2) c GROUP BY v1"), args))
        rows = conn.execute(text("SELECT dim_value, item_id, option_id, n, base_n FROM srv_result"
                                 " WHERE survey_id = :s AND qcode = :q AND dim = :d1 AND n > 0"), args).all()
        same = sum(counts.get((v, int(i), int(o))) == n and bases.get(v) == b for v, i, o, n, b in rows)
        print(f"check vs srv_result ({qcode} by {D1}): {same}/{len(rows)} rows match (count and base)")


def server_ms(conn, sql, repeat=15):
    times = []
    for _ in range(repeat):
        plan = conn.execute(text("EXPLAIN ANALYZE " + sql)).scalar()
        times.append(float(re.search(r"actual time=[\d.]+\.\.([\d.]+)", plan).group(1)))
    return statistics.median(times)


def throughput(eng, name, sql, sessions, loops):
    proc = "bench_" + re.sub(r"\W", "_", name)
    with eng.begin() as conn:
        conn.execute(text(f"DROP PROCEDURE IF EXISTS {proc}"))
        conn.execute(text(f"""
            CREATE PROCEDURE {proc}(IN loops INT) BEGIN
              DECLARE i INT DEFAULT 0;
              WHILE i < loops DO SELECT /*+ NO_MERGE(t) */ COUNT(*) INTO @rows FROM ({sql}) t; SET i = i + 1; END WHILE;
            END"""))
    try:
        def run():
            with eng.connect() as conn:
                conn.execute(text(f"CALL {proc}(:n)"), {"n": loops})
        threads = [threading.Thread(target=run) for _ in range(sessions)]
        start = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        return sessions * loops / (time.perf_counter() - start)
    finally:
        with eng.begin() as conn:
            conn.execute(text(f"DROP PROCEDURE IF EXISTS {proc}"))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--survey", type=int, default=412)
    p.add_argument("--sessions", type=int, default=16)
    p.add_argument("--keep", action="store_true")
    a = p.parse_args()
    sid, eng = a.survey, engine(a.sessions)
    with eng.connect() as conn:
        qid = dict(conn.execute(text("SELECT qcode, question_id FROM cip_question WHERE survey_id = :s AND qcode IN (:a, :b)"),
                                {"s": sid, "a": SINGLE, "b": MULTI}).all())
        waves = conn.execute(text("SELECT COUNT(*) FROM srv_wave")).scalar()
    t = time.perf_counter()
    with eng.begin() as conn:
        build(conn, sid)
    print(f"built prototype tables for wave {sid} in {time.perf_counter() - t:.1f} s")
    try:
        with eng.connect() as conn:
            check(conn, sid)
            count = lambda sql: conn.execute(text(sql), {"s": sid}).scalar()
            # scale this wave to all waves by its share of the table each one is made from
            answers = count("SELECT COUNT(*) FROM cip_answer WHERE survey_id = :s") / count("SELECT COUNT(*) FROM cip_answer")
            serving = count("SELECT COUNT(*) FROM srv_result WHERE survey_id = :s") / count("SELECT COUNT(*) FROM srv_result")
            for table, share in ((RESPONDENT, answers), (PAIRS, serving), ("srv_result", serving)):
                rows, mb = conn.execute(text(
                    "SELECT COUNT(*), (SELECT (data_length + index_length) / 1e6 FROM information_schema.tables"
                    f" WHERE table_schema = DATABASE() AND table_name = '{table}') FROM {table}"
                    f"{' WHERE survey_id = :s' if table == 'srv_result' else ''}"), {"s": sid}).one()
                if table == "srv_result":
                    mb *= serving
                print(f"size {table:<24} this wave {rows:>8,} rows {mb:6.1f} MB"
                      f"  → all {waves} waves ≈ {rows / share / 1e6:5.1f} M rows, {mb / share / 1e3:4.2f} GB")
            cells = conn.execute(text(f"""
                SELECT COUNT(*), SUM(base_n < 50), SUM(base_n < 30) FROM
                  (SELECT qid, d1, d2, v1, v2, iid, MAX(base_n) AS base_n FROM {PAIRS} WHERE v1 <> '' AND v2 <> ''
                    GROUP BY qid, d1, d2, v1, v2, iid) c""")).one()
            print(f"two-cut cells: {cells[0]:,}; base under 50: {cells[1] / cells[0]:.0%}; under 30: {cells[2] / cells[0]:.0%}")
            print(f"{D1} × {D2} bases for {SINGLE}:", conn.execute(text(
                f"SELECT v1, v2, MAX(base_n) FROM {PAIRS} WHERE survey_id = :s AND qid = :q AND d1 = :d1 AND d2 = :d2"
                " GROUP BY v1, v2 ORDER BY v1, v2"), {"s": sid, "q": qid[SINGLE], "d1": D1, "d2": D2}).all())
            sqls = queries(sid, qid[SINGLE], qid[MULTI])
            print(f"\n{'query':<20}{'rows':>6}{'server p50':>13}{'queries/s':>12}  ({a.sessions} sessions, in MySQL)")
            for name, sql in sqls.items():
                rows = len(conn.execute(text(sql)).all())
                ms = server_ms(conn, sql, 5 if name.startswith("raw") else 15)
                loops = max(3, min(2000, int(4000 / max(ms, 0.05) / a.sessions)))
                qps = throughput(eng, name, sql, a.sessions, loops)
                print(f"{name:<20}{rows:>6}{ms:>10.2f} ms{qps:>12,.0f}", flush=True)
    finally:
        if not a.keep:
            with eng.begin() as conn:
                conn.execute(text(f"DROP TABLE IF EXISTS {RESPONDENT}, {PAIRS}"))
            print("dropped prototype tables")


if __name__ == "__main__":
    main()
