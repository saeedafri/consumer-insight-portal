"""Disposable MySQL 8 correctness/performance benchmark for CIP Stage 3."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import statistics
import sys
import tempfile
import threading
import time
import tracemalloc
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pymysql
import sqlalchemy as sa
from sqlalchemy import bindparam, event, text
from sqlalchemy.exc import TimeoutError as PoolTimeout

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

HOST = "127.0.0.1"
PORT = 33306
DATABASE = "cip_test"
SURVEYS = (9001, 9002, 9003, 9004)
RESPONDENTS = 2000
QUESTIONS = 20
SINGLE_QUESTIONS = 18
OPTION_COUNT = 5
CUTS = ("gender", "age_band", "generation", "income_band", "census_region", "urbanicity")
URL = f"mysql+pymysql://root@{HOST}:{PORT}/{DATABASE}?charset=utf8mb4"


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
        read_timeout=30,
        write_timeout=30,
        local_infile=False,
    )


def engine(pool_size: int = 4, max_overflow: int = 0, pool_timeout: float = 2):
    return sa.create_engine(
        URL,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=pool_timeout,
        pool_pre_ping=True,
        future=True,
    )


def batches(rows, size: int = 5000):
    batch = []
    for row in rows:
        batch.append(row)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch


def reset() -> None:
    with raw_connection() as conn, conn.cursor() as cursor:
        cursor.execute("SELECT DATABASE(), VERSION(), @@collation_server")
        database, version, collation = cursor.fetchone()
        if database != DATABASE or not version.startswith("8.") or collation != "utf8mb4_0900_ai_ci":
            raise RuntimeError("refusing non-disposable or non-MySQL-8 target")
        cursor.execute("SET FOREIGN_KEY_CHECKS=0")
        cursor.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema=%s AND table_type='BASE TABLE'",
            (DATABASE,),
        )
        for (table,) in cursor.fetchall():
            cursor.execute(f"TRUNCATE TABLE `{table}`")
        cursor.execute("DROP TABLE IF EXISTS stage3_answer_seed")
        cursor.execute("SET FOREIGN_KEY_CHECKS=1")


def qid(survey_id: int, question: int) -> int:
    return survey_id * 100 + question


def oid(survey_id: int, question: int, code: int) -> int:
    return survey_id * 10000 + question * 10 + code


def iid(survey_id: int, question: int) -> int:
    return survey_id * 100 + question


def fid(survey_id: int, question: int) -> int:
    return survey_id * 100 + question


def rid(survey_id: int, respondent: int) -> int:
    return survey_id * 10000 + respondent


def cut_values(respondent: int) -> tuple[str, ...]:
    return (
        ("Male", "Female")[respondent % 2],
        ("18-29", "30-44", "45-59", "60+")[respondent % 4],
        ("Gen Z", "Millennial", "Gen X", "Boomer")[respondent % 4],
        ("Under $25k", "$25k-$49k", "$50k-$99k", "$100k+")[respondent % 4],
        ("Northeast", "Midwest", "South", "West")[respondent % 4],
        ("Urban", "Suburban", "Rural")[respondent % 3],
    )


def option_label(code: int) -> str:
    return {1: "Café", 2: "Male", 3: "Option Three", 4: "Option Four", 5: "Option Five"}[code]


def answer_label(respondent: int, code: int) -> str:
    if respondent % 37 == 0:
        return f"Custom-{respondent}-{code}"
    if code == 1:
        return "cafe"
    if code == 2:
        return "male   "
    return option_label(code)


def seed() -> dict:
    reset()
    with raw_connection(autocommit=False) as conn, conn.cursor() as cursor:
        cursor.executemany(
            "INSERT INTO cip_survey "
            "(survey_id,forsta_host,forsta_path,title,survey_family,wave_label,wave_date,platform,source_ref,study_type,load_status) "
            "VALUES (%s,'local',%s,'Synthetic','SYNTH',%s,%s,'forsta',%s,'tracker','verified')",
            [(sid, f"p{sid}", f"2026-01-{index + 1:02d}", f"2026-01-{index + 1:02d}", f"p{sid}")
             for index, sid in enumerate(SURVEYS)],
        )
        cursor.execute(
            "INSERT INTO cip_concept (concept_id,concept_code,concept_name,qtype) "
            "VALUES (1,'SYNTH','Synthetic concept','single')"
        )
        cursor.executemany(
            "INSERT INTO cip_concept_option "
            "(concept_option_id,concept_id,option_code,option_label,sort_order) VALUES (%s,1,%s,%s,%s)",
            [(code, str(code), option_label(code), code) for code in range(1, OPTION_COUNT + 1)],
        )
        cursor.executemany(
            "INSERT INTO cip_cohort_def (cohort_id,cohort_code,version,cohort_name,rule_json) "
            "VALUES (%s,%s,1,%s,JSON_OBJECT())",
            [(cohort, f"C{cohort}", f"Cohort {cohort}") for cohort in range(1, 30)],
        )

        for sid in SURVEYS:
            cursor.executemany(
                "INSERT INTO cip_question "
                "(question_id,survey_id,qcode,qtext,qtype,is_multi,sort_order) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                [
                    (
                        qid(sid, q), sid, f"Q{q:03d}", f"Synthetic question {q}",
                        "single" if q <= SINGLE_QUESTIONS else "multi",
                        0 if q <= SINGLE_QUESTIONS else 1, q,
                    )
                    for q in range(1, QUESTIONS + 1)
                ],
            )
            cursor.executemany(
                "INSERT INTO cip_item (item_id,question_id,item_code,item_label,sort_order) "
                "VALUES (%s,%s,%s,%s,1)",
                [(iid(sid, q), qid(sid, q), f"Q{q:03d}R1", f"Item {q}")
                 for q in range(SINGLE_QUESTIONS + 1, QUESTIONS + 1)],
            )
            cursor.executemany(
                "INSERT INTO cip_option (option_id,question_id,value_code,value_label,sort_order) "
                "VALUES (%s,%s,%s,%s,%s)",
                [(oid(sid, q, code), qid(sid, q), code, option_label(code), code)
                 for q in range(1, SINGLE_QUESTIONS + 1)
                 for code in range(1, OPTION_COUNT + 1)],
            )
            cursor.executemany(
                "INSERT INTO cip_field "
                "(field_id,survey_id,question_id,item_id,field_name,value_type,col_position) "
                "VALUES (%s,%s,%s,%s,%s,'code',%s)",
                [(fid(sid, q), sid, qid(sid, q), None if q <= SINGLE_QUESTIONS else iid(sid, q),
                  f"Q{q:03d}", q) for q in range(1, QUESTIONS + 1)],
            )
            for batch in batches(
                (
                    (rid(sid, respondent), sid, respondent, 1)
                    for respondent in range(1, RESPONDENTS + 1)
                )
            ):
                cursor.executemany(
                    "INSERT INTO cip_respondent (respondent_id,survey_id,record_no,is_qualified) VALUES (%s,%s,%s,%s)",
                    batch,
                )
            cursor.execute(
                "INSERT INTO srv_wave "
                "(survey_id,survey_family,study_type,wave_date,qualified_n,rows_built) "
                "SELECT survey_id,survey_family,study_type,wave_date,%s,0 FROM cip_survey WHERE survey_id=%s",
                (RESPONDENTS, sid),
            )

            for q in range(1, SINGLE_QUESTIONS + 1):
                for code in range(1, OPTION_COUNT + 1):
                    map_key = f"{qid(sid, q)}:0:{oid(sid, q, code)}"
                    cursor.execute(
                        "INSERT INTO cip_concept_map "
                        "(survey_id,map_key,question_id,option_id,concept_id,concept_option_id,status,method) "
                        "VALUES (%s,%s,%s,%s,1,%s,'confirmed','manual')",
                        (sid, map_key, qid(sid, q), oid(sid, q, code), code),
                    )
                    cursor.execute(
                        "INSERT INTO srv_result "
                        "(survey_id,qcode,dim,dim_value,item_id,option_id,question_id,qtype,item_label,option_code,option_label,sort_order,n,base_n,pct) "
                        "VALUES (%s,%s,'total','Total',0,%s,%s,'single','',%s,%s,%s,400,%s,20.000)",
                        (sid, f"Q{q:03d}", oid(sid, q, code), qid(sid, q), code, option_label(code), code, RESPONDENTS),
                    )
            for q in range(SINGLE_QUESTIONS + 1, QUESTIONS + 1):
                cursor.execute(
                    "INSERT INTO srv_result "
                    "(survey_id,qcode,dim,dim_value,item_id,option_id,question_id,qtype,item_label,option_code,option_label,sort_order,n,base_n,pct) "
                    "VALUES (%s,%s,'total','Total',%s,0,%s,'multi',%s,NULL,NULL,1,1000,%s,50.000)",
                    (sid, f"Q{q:03d}", iid(sid, q), qid(sid, q), f"Item {q}", RESPONDENTS),
                )

            srv_rows = (
                (
                    sid, f"Q{q:03d}", 0 if q <= SINGLE_QUESTIONS else iid(sid, q),
                    oid(sid, q, 1 + (respondent + q) % OPTION_COUNT) if q <= SINGLE_QUESTIONS else 0,
                    rid(sid, respondent), *cut_values(respondent),
                )
                for respondent in range(1, RESPONDENTS + 1)
                for q in range(1, QUESTIONS + 1)
            )
            for batch in batches(srv_rows):
                cursor.executemany(
                    "INSERT INTO srv_answer "
                    "(survey_id,qcode,item_id,option_id,respondent_id,gender,age_band,generation,income_band,census_region,urbanicity) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    batch,
                )

        answer_rows = (
            (
                rid(SURVEYS[0], respondent), SURVEYS[0], fid(SURVEYS[0], q),
                1 + (respondent + q) % OPTION_COUNT if q <= SINGLE_QUESTIONS else 1,
                answer_label(respondent, 1 + (respondent + q) % OPTION_COUNT)
                if q <= SINGLE_QUESTIONS else
                (f"Custom-item-{respondent}" if respondent % 37 == 0 else f"item {q}   "),
            )
            for respondent in range(1, RESPONDENTS + 1)
            for q in range(1, QUESTIONS + 1)
        )
        for batch in batches(answer_rows):
            cursor.executemany(
                "INSERT INTO cip_answer "
                "(respondent_id,survey_id,field_id,value_code,value_label) VALUES (%s,%s,%s,%s,%s)",
                batch,
            )

        dim_values = {
            "total": ("Total",),
            "gender": ("Male", "Female"),
            "age_band": ("18-29", "30-44", "45-59", "60+"),
            "generation": ("Gen Z", "Millennial", "Gen X", "Boomer"),
            "income_band": ("Under $25k", "$25k-$49k", "$50k-$99k", "$100k+"),
            "census_region": ("Northeast", "Midwest", "South", "West"),
            "urbanicity": ("Urban", "Suburban", "Rural"),
        }
        agg_rows = []
        sid = SURVEYS[0]
        for q in range(1, SINGLE_QUESTIONS + 1):
            for code in range(1, OPTION_COUNT + 1):
                map_key = f"{qid(sid, q)}:0:{oid(sid, q, code)}"
                for cohort in (None, *range(1, 30)):
                    for dim, values in dim_values.items():
                        for value in values:
                            cell_key = f"{qid(sid,q)}:0:{oid(sid,q,code)}:{cohort or 0}:0:{dim}:{value}"
                            agg_rows.append((sid, cell_key, map_key, qid(sid, q), oid(sid, q, code), cohort, dim, value, 20, 100))
                            if len(agg_rows) == 5000:
                                cursor.executemany(
                                    "INSERT INTO cip_agg_cell "
                                    "(survey_id,cell_key,map_key,question_id,option_id,cohort_id,dim,dim_value,n,base_n) "
                                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                                    agg_rows,
                                )
                                agg_rows = []
        if agg_rows:
            cursor.executemany(
                "INSERT INTO cip_agg_cell "
                "(survey_id,cell_key,map_key,question_id,option_id,cohort_id,dim,dim_value,n,base_n) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                agg_rows,
            )
        cursor.execute("CREATE TABLE stage3_answer_seed AS SELECT answer_id,value_label FROM cip_answer")
        conn.commit()
    return {"surveys": len(SURVEYS), "srv_answer_rows": len(SURVEYS) * RESPONDENTS * QUESTIONS,
            "cip_answer_rows": RESPONDENTS * QUESTIONS}


BASELINE_CLEANUP = """UPDATE cip_answer a JOIN cip_field f ON f.field_id = a.field_id
LEFT JOIN cip_option o ON o.question_id = f.question_id AND o.value_code = a.value_code
LEFT JOIN cip_item i ON i.item_id = f.item_id
SET a.value_label = NULL
WHERE a.survey_id = %s AND a.value_label = COALESCE(o.value_label, i.item_label)"""

OPTION_CLEANUP = """UPDATE cip_answer a JOIN cip_field f ON f.field_id = a.field_id
JOIN cip_option o ON o.question_id = f.question_id AND o.value_code = a.value_code
SET a.value_label = NULL
WHERE a.survey_id = %s AND a.value_label = o.value_label"""

ITEM_CLEANUP = """UPDATE cip_answer a JOIN cip_field f ON f.field_id = a.field_id
JOIN cip_item i ON i.item_id = f.item_id
LEFT JOIN cip_option o ON o.question_id = f.question_id AND o.value_code = a.value_code
SET a.value_label = NULL
WHERE a.survey_id = %s AND o.option_id IS NULL AND a.value_label = i.item_label"""


def restore_labels(cursor) -> None:
    cursor.execute(
        "UPDATE cip_answer a JOIN stage3_answer_seed s ON s.answer_id=a.answer_id "
        "SET a.value_label=s.value_label"
    )


def label_digest(cursor) -> str:
    cursor.execute("SELECT answer_id,value_label FROM cip_answer ORDER BY answer_id")
    digest = hashlib.sha256()
    for answer_id, label in cursor:
        digest.update(json.dumps([answer_id, label], ensure_ascii=False).encode())
    return digest.hexdigest()


def benchmark_cleanup(samples: int) -> dict:
    output = {}
    for name, statements in (
        ("before", (BASELINE_CLEANUP,)),
        ("candidate", (OPTION_CLEANUP, ITEM_CLEANUP)),
    ):
        times, counts, hashes = [], [], []
        with raw_connection(autocommit=False) as conn, conn.cursor() as cursor:
            for _ in range(samples):
                restore_labels(cursor)
                conn.commit()
                started = time.perf_counter()
                count = 0
                for statement in statements:
                    count += cursor.execute(statement, (SURVEYS[0],))
                conn.commit()
                times.append(time.perf_counter() - started)
                counts.append(count)
                hashes.append(label_digest(cursor))
        output[name] = metrics(times) | {"updated_rows": counts, "hashes": sorted(set(hashes))}
    output["parity"] = output["before"]["hashes"] == output["candidate"]["hashes"]
    return output


def payload_digest(value) -> str:
    from app.data import payloads
    return hashlib.sha256(payloads.encode(value)).hexdigest()


def baseline_people(conn, survey_id: int) -> dict:
    """Pre-Stage-3 implementation retained only as the benchmark control."""
    from collections import defaultdict
    from app.data.harmonise import normalise_text
    from etl.serving import CUTS as APP_CUTS

    rows = conn.execute(text(
        f"SELECT respondent_id,qcode,item_id,option_id,{', '.join(APP_CUTS)} "
        "FROM srv_answer WHERE survey_id=:s"
    ), {"s": survey_id}).all()
    seat = {respondent_id: index for index, respondent_id in enumerate(sorted({row[0] for row in rows}))}
    bits: dict = defaultdict(int)
    cuts: dict = {dim: defaultdict(int) for dim in APP_CUTS}
    seen = set()
    for row in rows:
        bit = 1 << seat[row[0]]
        bits[(row[1], row[2], row[3])] |= bit
        if row[0] not in seen:
            seen.add(row[0])
            for dim, value in zip(APP_CUTS, row[4:]):
                if value not in (None, ""):
                    cuts[dim][value] |= bit
    questions = {}
    for answer in conn.execute(text(
        "SELECT r.qcode,r.item_id,r.option_id,r.item_label,r.option_code,r.option_label,q.qtext "
        "FROM srv_result r JOIN cip_question q ON q.question_id=r.question_id "
        "WHERE r.survey_id=:s AND r.dim='total' ORDER BY r.qcode,r.sort_order"
    ), {"s": survey_id}):
        question = questions.setdefault(
            answer[0], {"text": normalise_text(answer[6]), "rows": [], "bits": {}}
        )
        question["rows"].append(list(answer[1:6]))
    for (qcode, item, option), value in bits.items():
        if qcode in questions:
            questions[qcode]["bits"][f"{item},{option}"] = format(value, "x")
    return {
        "cuts": {dim: {value: format(found, "x") for value, found in values.items()} for dim, values in cuts.items()},
        "questions": questions,
    }


def candidate_people(conn, survey_id: int) -> dict:
    from collections import defaultdict
    from app.data.harmonise import normalise_text
    from etl.serving import CUTS as APP_CUTS

    statement = text(
        f"SELECT respondent_id,qcode,item_id,option_id,{', '.join(APP_CUTS)} "
        "FROM srv_answer WHERE survey_id=:s"
    ).execution_options(stream_results=True, max_row_buffer=1000)
    respondents = set()
    members: dict = defaultdict(set)
    cuts: dict = {dim: defaultdict(set) for dim in APP_CUTS}
    seen = set()
    for row in conn.execute(statement, {"s": survey_id}):
        respondents.add(row[0])
        members[(row[1], row[2], row[3])].add(row[0])
        if row[0] not in seen:
            seen.add(row[0])
            for dim, value in zip(APP_CUTS, row[4:]):
                if value not in (None, ""):
                    cuts[dim][value].add(row[0])
    seat = {respondent_id: index for index, respondent_id in enumerate(sorted(respondents))}

    def mask(found: set[int]) -> int:
        out = 0
        for respondent_id in found:
            out |= 1 << seat[respondent_id]
        return out

    bits = {key: mask(found) for key, found in members.items()}
    cuts = {dim: {value: mask(found) for value, found in values.items()} for dim, values in cuts.items()}
    questions = {}
    for answer in conn.execute(text(
        "SELECT r.qcode,r.item_id,r.option_id,r.item_label,r.option_code,r.option_label,q.qtext "
        "FROM srv_result r JOIN cip_question q ON q.question_id=r.question_id "
        "WHERE r.survey_id=:s AND r.dim='total' ORDER BY r.qcode,r.sort_order"
    ), {"s": survey_id}):
        question = questions.setdefault(
            answer[0], {"text": normalise_text(answer[6]), "rows": [], "bits": {}}
        )
        question["rows"].append(list(answer[1:6]))
    for (qcode, item, option), value in bits.items():
        if qcode in questions:
            questions[qcode]["bits"][f"{item},{option}"] = format(value, "x")
    return {
        "cuts": {dim: {value: format(bits, "x") for value, bits in values.items()} for dim, values in cuts.items()},
        "questions": questions,
    }


def measured_people(function, samples: int) -> dict:
    timings, peaks, hashes = [], [], []
    eng = engine()
    try:
        for _ in range(samples):
            tracemalloc.start()
            started = time.perf_counter()
            with eng.connect() as conn:
                output = function(conn, SURVEYS[0])
            timings.append(time.perf_counter() - started)
            peaks.append(tracemalloc.get_traced_memory()[1])
            tracemalloc.stop()
            hashes.append(payload_digest(output))
    finally:
        eng.dispose()
    return metrics(timings) | {"peak_python_bytes": peaks, "hashes": sorted(set(hashes))}


WAVE_BASELINE = """SELECT c.question_id,c.n,c.base_n,i.item_label,i.left_label,i.right_label,
COALESCE(i.sort_order,0),o.value_label,COALESCE(o.sort_order,0)
FROM cip_agg_cell c
JOIN cip_question q ON q.question_id=c.question_id AND q.is_virtual=0
LEFT JOIN cip_item i ON i.item_id=c.item_id
LEFT JOIN cip_option o ON o.option_id=c.option_id
WHERE c.survey_id=%s AND c.dim='total' AND c.cohort_id IS NULL"""

WAVE_CANDIDATE = """SELECT c.question_id,c.n,c.base_n,i.item_label,i.left_label,i.right_label,
COALESCE(i.sort_order,0),o.value_label,COALESCE(o.sort_order,0)
FROM cip_question q
JOIN cip_agg_cell c ON c.question_id=q.question_id AND c.survey_id=q.survey_id
  AND c.survey_id=%s AND c.dim='total' AND c.cohort_id IS NULL
LEFT JOIN cip_item i ON i.item_id=c.item_id
LEFT JOIN cip_option o ON o.option_id=c.option_id
WHERE q.survey_id=%s AND q.is_virtual=0"""

CONCEPT_BASELINE = """SELECT c.survey_id,c.dim_value,co.option_label,c.n,c.base_n
FROM cip_concept_option co
JOIN cip_concept_map m ON m.concept_option_id=co.concept_option_id AND m.status='confirmed'
JOIN cip_agg_cell c ON c.survey_id=m.survey_id AND c.map_key=m.map_key
 AND c.dim='total' AND COALESCE(c.cohort_id,0)=0
JOIN cip_survey s ON s.survey_id=m.survey_id AND s.load_status='verified'
WHERE co.concept_id=1"""

CONCEPT_CANDIDATE = """SELECT c.survey_id,c.dim_value,co.option_label,c.n,c.base_n
FROM cip_concept_option co
JOIN cip_concept_map m ON m.concept_option_id=co.concept_option_id AND m.status='confirmed'
JOIN cip_agg_cell c ON c.survey_id=m.survey_id AND c.map_key=m.map_key
 AND c.cohort_id IS NULL AND c.dim='total'
JOIN cip_survey s ON s.survey_id=m.survey_id AND s.load_status='verified'
WHERE co.concept_id=1"""


def sql_digest(rows) -> str:
    return hashlib.sha256(json.dumps(sorted([list(row) for row in rows]), default=str).encode()).hexdigest()


def benchmark_query(statement: str, params: tuple, samples: int) -> dict:
    times, hashes, row_counts = [], [], []
    with raw_connection() as conn, conn.cursor() as cursor:
        cursor.execute(statement, params)
        cursor.fetchall()
        for _ in range(samples):
            started = time.perf_counter()
            cursor.execute(statement, params)
            rows = cursor.fetchall()
            times.append(time.perf_counter() - started)
            hashes.append(sql_digest(rows))
            row_counts.append(len(rows))
        cursor.execute("EXPLAIN FORMAT=JSON " + statement, params)
        plan = json.loads(cursor.fetchone()[0])
    return metrics(times) | {"hashes": sorted(set(hashes)), "row_counts": row_counts, "plan": plan}


GROUP_SQL = """SELECT survey_id,qcode,item_id,option_id,gender,age_band,generation,income_band,census_region,urbanicity,COUNT(*)
FROM srv_answer WHERE survey_id=%s
GROUP BY survey_id,qcode,item_id,option_id,gender,age_band,generation,income_band,census_region,urbanicity"""
EXTRACT_SQL = """SELECT respondent_id,qcode,item_id,option_id,gender,age_band,generation,income_band,census_region,urbanicity
FROM srv_answer WHERE survey_id=%s"""


def publisher_sql_concurrency(jobs: int) -> dict:
    def run(sid: int):
        with raw_connection() as conn, conn.cursor() as cursor:
            cursor.execute(GROUP_SQL, (sid,))
            grouped = cursor.fetchall()
            cursor.execute(EXTRACT_SQL, (sid,))
            digest = hashlib.sha256()
            count = 0
            for row in cursor:
                digest.update(json.dumps(row, default=str).encode())
                count += 1
            return sid, len(grouped), count, digest.hexdigest()

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        results = sorted(pool.map(run, SURVEYS))
    return {"jobs": jobs, "wall_s": round(time.perf_counter() - started, 6), "results": results}


def pool_limit_test() -> dict:
    eng = engine(pool_size=2, max_overflow=2, pool_timeout=0.4)
    barrier = threading.Barrier(4)

    def hold(index: int):
        try:
            with eng.connect() as conn:
                conn.execute(text("SELECT 1")).scalar()
                if index < 4:
                    barrier.wait(timeout=2)
                    time.sleep(0.8)
                return "connected"
        except PoolTimeout:
            return "timeout"

    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(hold, range(8)))
    eng.dispose()
    return {"outcomes": outcomes, "connected": outcomes.count("connected"), "timeouts": outcomes.count("timeout")}


def transaction_failure_test() -> dict:
    with raw_connection(autocommit=False) as conn, conn.cursor() as cursor:
        cursor.execute("SELECT value_label FROM cip_answer ORDER BY answer_id LIMIT 1")
        before = cursor.fetchone()[0]
        try:
            cursor.execute("UPDATE cip_answer SET value_label='SHOULD_ROLL_BACK' WHERE survey_id=%s LIMIT 1", (SURVEYS[0],))
            cursor.execute("INSERT INTO table_that_does_not_exist VALUES (1)")
            conn.commit()
        except Exception:
            conn.rollback()
        cursor.execute("SELECT value_label FROM cip_answer ORDER BY answer_id LIMIT 1")
        after = cursor.fetchone()[0]
    return {"before": before, "after": after, "rolled_back": before == after}


def lock_timeout_test() -> dict:
    owner = raw_connection(autocommit=False)
    waiter = raw_connection(autocommit=False)
    code = None
    started = time.perf_counter()
    try:
        with owner.cursor() as cursor:
            cursor.execute(
                "UPDATE cip_answer SET value_label=value_label WHERE survey_id=%s ORDER BY answer_id LIMIT 1",
                (SURVEYS[0],),
            )
        with waiter.cursor() as cursor:
            cursor.execute("SET SESSION innodb_lock_wait_timeout=1")
            try:
                cursor.execute(
                    "UPDATE cip_answer SET value_label='LOCK_TEST' WHERE survey_id=%s ORDER BY answer_id LIMIT 1",
                    (SURVEYS[0],),
                )
            except pymysql.MySQLError as exc:
                code = exc.args[0]
                waiter.rollback()
    finally:
        owner.rollback()
        waiter.close()
        owner.close()
    return {"mysql_error": code, "elapsed_s": round(time.perf_counter() - started, 6), "passed": code == 1205}


def published_digest(root: Path) -> tuple[str, int]:
    digest, size = hashlib.sha256(), 0
    for path in sorted(root.rglob("*.json.gz")):
        body = gzip.decompress(path.read_bytes())
        digest.update(str(path.relative_to(root)).encode())
        digest.update(body)
        size += len(body)
    return digest.hexdigest(), size


def full_publisher(jobs: int) -> dict:
    from app.core import database
    from etl import publish

    eng = engine(pool_size=4, max_overflow=0, pool_timeout=2)
    database._engines["app"] = eng
    database._engines["etl"] = eng
    with tempfile.TemporaryDirectory(prefix=f"cip-mysql-publish-{jobs}-") as raw:
        root = Path(raw)
        started = time.perf_counter()
        built = publish.build(root, jobs=jobs)
        wall = time.perf_counter() - started
        digest, size = published_digest(built)
    eng.dispose()
    database._engines.clear()
    return {"jobs": jobs, "wall_s": round(wall, 6), "sha256": digest, "bytes": size}


def publisher_failure_cleanup() -> dict:
    from app.core import database
    from app.data import payloads
    from etl import publish

    eng = engine(pool_size=4, max_overflow=0, pool_timeout=2)
    database._engines["app"] = eng
    database._engines["etl"] = eng
    original = payloads.question_cuts

    def fail(conn, ids, qcode=None):
        if ids and ids[0] == SURVEYS[1]:
            raise RuntimeError("injected synthetic publisher failure")
        return original(conn, ids, qcode)

    with tempfile.TemporaryDirectory(prefix="cip-mysql-publish-failure-") as raw:
        root = Path(raw)
        payloads.question_cuts = fail
        raised = False
        try:
            publish.build(root, jobs=4)
        except RuntimeError:
            raised = True
        finally:
            payloads.question_cuts = original
        leftovers = [path.name for path in root.glob(".build-*")]
    eng.dispose()
    database._engines.clear()
    return {"raised": raised, "partial_builds": leftovers, "clean": raised and not leftovers}


def metrics(samples: list[float]) -> dict:
    ordered = sorted(samples)
    return {
        "samples_s": [round(value, 6) for value in samples],
        "median_s": round(statistics.median(samples), 6),
        "p95_s": round(ordered[min(len(ordered) - 1, int(0.95 * (len(ordered) - 1)))], 6),
        "min_s": round(min(samples), 6),
        "max_s": round(max(samples), 6),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--seed", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    seeded = seed() if args.seed else {}
    with raw_connection() as conn, conn.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM srv_answer")
        seeded["srv_answer_rows"] = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM cip_answer")
        seeded["cip_answer_rows"] = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM cip_agg_cell")
        seeded["cip_agg_cell_rows"] = cursor.fetchone()[0]
        seeded["surveys"] = len(SURVEYS)
    from app.data import payloads

    result = {
        "label": args.label,
        "mysql": "8.4",
        "target": f"{HOST}:{PORT}/{DATABASE}",
        "synthetic": True,
        "seed": seeded,
        "cleanup": benchmark_cleanup(args.samples),
        "people": {
            "before": measured_people(baseline_people, args.samples),
            "current": measured_people(payloads.people, args.samples),
            "candidate": measured_people(candidate_people, args.samples),
        },
        "wave_report": {
            "before": benchmark_query(WAVE_BASELINE, (SURVEYS[0],), args.samples),
            "candidate": benchmark_query(WAVE_CANDIDATE, (SURVEYS[0], SURVEYS[0]), args.samples),
        },
        "concept_trend": {
            "before": benchmark_query(CONCEPT_BASELINE, (), args.samples),
            "candidate": benchmark_query(CONCEPT_CANDIDATE, (), args.samples),
        },
        "publisher_sql": [publisher_sql_concurrency(jobs) for jobs in (1, 2, 4)],
        "publisher_full": [full_publisher(jobs) for jobs in (1, 2, 4)],
        "publisher_failure": publisher_failure_cleanup(),
        "pool_limit": pool_limit_test(),
        "transaction_failure": transaction_failure_test(),
        "lock_timeout": lock_timeout_test(),
    }
    result["people"]["parity"] = (
        result["people"]["before"]["hashes"]
        == result["people"]["current"]["hashes"]
        == result["people"]["candidate"]["hashes"]
    )
    result["wave_report"]["parity"] = result["wave_report"]["before"]["hashes"] == result["wave_report"]["candidate"]["hashes"]
    result["concept_trend"]["parity"] = result["concept_trend"]["before"]["hashes"] == result["concept_trend"]["candidate"]["hashes"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({
        "label": args.label,
        "cleanup_parity": result["cleanup"]["parity"],
        "people_parity": result["people"]["parity"],
        "wave_report_parity": result["wave_report"]["parity"],
        "concept_trend_parity": result["concept_trend"]["parity"],
        "publisher_hashes": [row["sha256"] for row in result["publisher_full"]],
        "publisher_failure_clean": result["publisher_failure"]["clean"],
        "pool": result["pool_limit"],
        "transaction_rolled_back": result["transaction_failure"]["rolled_back"],
        "lock_timeout_passed": result["lock_timeout"]["passed"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
