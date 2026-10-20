"""The ETL's last step: the serving tables every user-facing screen reads (sql/005_serving.sql).

After a wave is loaded, verified and cubed, this turns its cube cells (qualified respondents, every
standard cut) into finished rows: labels, percentage, the prior-week and last-year comparison, and
flags that stop a reader comparing unlike bases. Screens then read one primary-key range per widget
and do no arithmetic. Nothing here knows about any particular screen.

It also keeps the cube's own input rows (each qualified answer with all six cuts) as srv_answer, so
a combined filter such as generation × gender is one small GROUP BY instead of a scan of the answers.

    python -m etl.serving --wave 412      # one wave
    python -m etl.serving --all --jobs 4 --missing   # backfill verified waves not built yet, 4 at a time
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import bindparam, text
from sqlalchemy.exc import OperationalError

from app.core.database import get_engine
from app.data.cube import ANSWER_CUTS, ANSWER_ROWS, CUBE_DIMS

log = logging.getLogger("cip.serving")
SMALL_BASE = 50       # respondents: below this a percentage is flagged
BASE_SHIFT = 10.0     # points: a question's base share of qualified respondents moving more than this is a routing change
PRIOR_DAYS = 14       # a tracker's previous wave must be at most this old to count as "prior week"
CUTS = tuple(d for d in CUBE_DIMS if d != "total")


def _day(value) -> date:
    return date.fromisoformat(str(value)[:10])   # MySQL returns a date, SQLite a string


def comparison(conn, survey_id: int) -> dict:
    """The wave, its prior week and its same week last year (or why there is none)."""
    w = conn.execute(text("SELECT survey_id, survey_family, study_type, wave_date FROM cip_survey WHERE survey_id = :s"),
                     {"s": survey_id}).mappings().one()
    day = _day(w["wave_date"])
    pick = lambda lo, hi, latest: conn.execute(text(
        "SELECT survey_id FROM cip_survey WHERE survey_family = :f AND load_status = 'verified' AND survey_id <> :s"
        f" AND wave_date BETWEEN :lo AND :hi ORDER BY wave_date {'DESC' if latest else 'ASC'} LIMIT 1"),
        {"f": w["survey_family"], "s": survey_id, "lo": lo, "hi": hi}).scalar()
    prior = pick(day - timedelta(days=PRIOR_DAYS), day - timedelta(days=1), True) if w["study_type"] == "tracker" else None
    target = day - timedelta(days=364)
    ly = pick(target - timedelta(days=3), target + timedelta(days=3), False)
    if ly:
        status = "loaded"
    else:   # the week is in the Forsta register but never loaded (hibernated): say so, don't substitute
        missing = conn.execute(text(
            "SELECT 1 FROM cip_forsta_survey WHERE survey_id IS NULL AND launched_at BETWEEN :lo AND :hi LIMIT 1"),
            {"lo": target - timedelta(days=3), "hi": target + timedelta(days=4)}).first()
        status = "not_loaded" if missing and w["study_type"] == "tracker" else "none"
    qualified = {sid: n for sid, n in conn.execute(text(
        "SELECT survey_id, SUM(is_qualified) FROM cip_respondent WHERE survey_id IN :ids GROUP BY survey_id")
        .bindparams(bindparam("ids", expanding=True)), {"ids": [x for x in (survey_id, prior, ly) if x]})}
    return {**w, "wave_date": day, "prior": prior, "ly": ly, "ly_status": status,
            "qualified": {k: int(v or 0) for k, v in qualified.items()}}


def cube_rows(conn, survey_ids: list[int]) -> list[dict]:
    """Labelled cube cells for these waves: Total and every cut, technical and virtual questions left out."""
    return [dict(r) for r in conn.execute(text(
        "SELECT c.survey_id, c.question_id, q.qcode, q.qtype, COALESCE(c.item_id, 0) AS item_id,"
        "       COALESCE(c.option_id, 0) AS option_id, COALESCE(i.item_label, '') AS item_label,"
        "       o.value_code AS option_code, o.value_label AS option_label,"
        "       COALESCE(i.sort_order, 0) * 1000 + COALESCE(o.sort_order, 0) AS sort_order,"
        "       c.concept_option_id, c.dim, c.dim_value, c.n, c.base_n"
        "  FROM cip_agg_cell c"
        "  JOIN cip_question q ON q.question_id = c.question_id AND q.survey_id = c.survey_id"   # lets MySQL start
        "       AND q.survey_id IN :ids AND q.is_technical = 0 AND q.is_virtual = 0"                # from this wave's questions
        "  LEFT JOIN cip_item i ON i.item_id = c.item_id"
        "  LEFT JOIN cip_option o ON o.option_id = c.option_id"
        " WHERE c.survey_id IN :ids AND c.cohort_id IS NULL AND c.base_n > 0")
        .bindparams(bindparam("ids", expanding=True)), {"ids": survey_ids}).mappings()]


def _key(r: dict) -> tuple:
    return r["qcode"], r["item_label"], r["option_code"], r["dim"], r["dim_value"]


def rows_for(wave: dict, cells: list[dict]) -> list[dict]:
    """Finished serving rows: percentage, comparisons matched on question code + answer + cut, and flags."""
    by_wave: dict[int, dict] = {}
    for c in cells:
        by_wave.setdefault(c["survey_id"], {})[_key(c)] = c
    sid, q = wave["survey_id"], wave["qualified"]
    out = []
    for c in by_wave.get(sid, {}).values():
        row = {k: c[k] for k in ("survey_id", "qcode", "dim", "dim_value", "item_id", "option_id", "question_id", "qtype",
                                 "item_label", "option_code", "option_label", "sort_order", "concept_option_id", "n", "base_n")}
        row["pct"] = round(100 * c["n"] / c["base_n"], 3)
        flags = ["small_base"] if c["base_n"] < SMALL_BASE else []
        for name, other in (("prior", wave["prior"]), ("ly", wave["ly"])):
            match = by_wave.get(other, {}).get(_key(c)) if other else None
            row[f"{name}_pct"] = round(100 * match["n"] / match["base_n"], 3) if match else None
            row[f"{name}_base_n"] = match["base_n"] if match else None
            # the base share is only comparable on the same cut, so judge routing on Total
            total = by_wave.get(other, {}).get((c["qcode"], c["item_label"], c["option_code"], "total", "Total")) if match else None
            mine = by_wave[sid].get((c["qcode"], c["item_label"], c["option_code"], "total", "Total"))
            if total and mine and q.get(sid) and q.get(other) and \
                    abs(100 * mine["base_n"] / q[sid] - 100 * total["base_n"] / q[other]) > BASE_SHIFT:
                flags.append(f"base_changed_{name}")
        row["flags"] = ",".join(flags)
        out.append(row)
    return out


def build_wave(survey_id: int, attempts: int = 3) -> int:
    """Rebuild one wave's serving rows in one transaction; returns the row count. Retries a deadlock
    (MySQL 1213), which parallel builds of neighbouring waves can hit."""
    for attempt in range(1, attempts + 1):
        try:
            return _build_wave(survey_id)
        except OperationalError as exc:
            if attempt == attempts or getattr(exc.orig, "args", [None])[0] != 1213:
                raise
            log.warning("Deadlock building survey %s; retry %d", survey_id, attempt)
            time.sleep(attempt)


def _build_wave(survey_id: int) -> int:
    with get_engine("etl").begin() as conn:
        if conn.dialect.name == "mysql":   # no gap locks: parallel builds of other waves don't block this one
            conn.execute(text("SET TRANSACTION ISOLATION LEVEL READ COMMITTED"))
        wave = comparison(conn, survey_id)
        rows = rows_for(wave, cube_rows(conn, [x for x in (survey_id, wave["prior"], wave["ly"]) if x]))
        conn.execute(text("DELETE FROM srv_result WHERE survey_id = :s"), {"s": survey_id})
        conn.execute(text("DELETE FROM srv_wave WHERE survey_id = :s"), {"s": survey_id})
        conn.execute(text(
            "INSERT INTO srv_wave (survey_id, survey_family, study_type, wave_date, qualified_n, prior_survey_id,"
            " ly_survey_id, ly_status, rows_built) VALUES (:s, :f, :t, :d, :q, :p, :l, :ls, :r)"),
            {"s": survey_id, "f": wave["survey_family"] or "", "t": wave["study_type"] or "", "d": wave["wave_date"],
             "q": wave["qualified"].get(survey_id, 0), "p": wave["prior"], "l": wave["ly"], "ls": wave["ly_status"],
             "r": len(rows)})
        if rows:
            conn.execute(text(
                "INSERT INTO srv_result (survey_id, qcode, dim, dim_value, item_id, option_id, question_id, qtype,"
                " item_label, option_code, option_label, sort_order, concept_option_id, n, base_n, pct, prior_pct,"
                " prior_base_n, ly_pct, ly_base_n, flags) VALUES (:survey_id, :qcode, :dim, :dim_value, :item_id,"
                " :option_id, :question_id, :qtype, :item_label, :option_code, :option_label, :sort_order,"
                " :concept_option_id, :n, :base_n, :pct, :prior_pct, :prior_base_n, :ly_pct, :ly_base_n, :flags)"), rows)
        store_answers(conn, survey_id)
    return len(rows)


def store_answers(conn, survey_id: int) -> int:
    """Replace the wave's srv_answer rows: every qualified single-choice answer and every multi item
    chosen, plus one base row (item 0, option 0) per respondent per multi question answered. The
    rows are the cube's own, so any two-cut summed over one cut equals srv_result."""
    answers, cuts = ANSWER_ROWS.format(cuts=ANSWER_CUTS), ", ".join(CUTS)
    picked = ", ".join(f"x.{d}" for d in CUTS)
    insert = f"INSERT INTO srv_answer (survey_id, qcode, item_id, option_id, respondent_id, {cuts})"
    source = f"FROM ({answers}) x JOIN cip_question q ON q.question_id = x.qid"
    conn.execute(text("DELETE FROM srv_answer WHERE survey_id = :sid"), {"sid": survey_id})
    chosen = conn.execute(text(
        f"{insert} SELECT :sid, q.qcode, COALESCE(x.iid, 0), COALESCE(x.oid, 0), x.rid, {picked} {source}"
        " WHERE x.multi = 0 OR x.code = 1"), {"sid": survey_id}).rowcount
    bases = conn.execute(text(
        f"{insert} SELECT DISTINCT :sid, q.qcode, 0, 0, x.rid, {picked} {source} WHERE x.multi = 1"),
        {"sid": survey_id}).rowcount
    return chosen + bases


def rebuild_dependants(survey_id: int) -> list[int]:
    """Waves that compare against this one (next week; next year's same week) get it now. A failure is
    logged, never fatal: this wave is already loaded, and theirs stay as they were."""
    with get_engine("app").connect() as conn:
        w = conn.execute(text("SELECT survey_family, wave_date FROM cip_survey WHERE survey_id = :s"),
                         {"s": survey_id}).one()
        day = _day(w.wave_date)
        ids = [r[0] for r in conn.execute(text(   # only the next fortnight and next year's same week can point here
            "SELECT survey_id FROM srv_wave WHERE survey_family = :f AND survey_id <> :s"
            " AND (wave_date BETWEEN :a AND :b OR wave_date BETWEEN :c AND :d)"),
            {"f": w.survey_family, "s": survey_id, "a": day + timedelta(days=1), "b": day + timedelta(days=PRIOR_DAYS),
             "c": day + timedelta(days=361), "d": day + timedelta(days=367)})]
    rebuilt = []
    for sid in ids:
        try:
            with get_engine("app").connect() as conn:
                wave = comparison(conn, sid)
            if survey_id in (wave["prior"], wave["ly"]):
                build_wave(sid)
                rebuilt.append(sid)
        except Exception:
            log.exception("Serving rows for survey %s not rebuilt; they stay as they were", sid)
    return rebuilt


def build_all(jobs: int = 1, missing_only: bool = False) -> int:
    """Backfill every verified wave. Waves don't depend on each other's serving rows (comparisons read the
    cube), so they can be built in parallel."""
    with get_engine("app").connect() as conn:
        ids = [r[0] for r in conn.execute(text(
            "SELECT s.survey_id FROM cip_survey s WHERE s.load_status = 'verified'"
            + (" AND NOT EXISTS (SELECT 1 FROM srv_wave w WHERE w.survey_id = s.survey_id)" if missing_only else "")
            + " ORDER BY s.wave_date, s.survey_id"))]
    total, start = 0, time.perf_counter()
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        for i, n in enumerate(pool.map(build_wave, ids), 1):
            total += n
            if i % 20 == 0 or i == len(ids):
                log.info("Serving rows: %d / %d waves, %d rows, %.0f s", i, len(ids), total, time.perf_counter() - start)
    return total


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s | %(message)s")
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--wave", type=int)
    p.add_argument("--all", action="store_true")
    p.add_argument("--jobs", type=int, default=1)
    p.add_argument("--missing", action="store_true", help="only waves with no serving rows yet")
    a = p.parse_args()
    if a.wave:
        print(f"survey {a.wave}: {build_wave(a.wave)} serving rows")
        return 0
    if a.all:
        print(f"{build_all(a.jobs, a.missing)} serving rows")
        return 0
    p.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
