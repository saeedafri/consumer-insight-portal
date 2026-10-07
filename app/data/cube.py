"""The cube: every answer × standard cut × cohort of a wave, counted once.

`cip_agg_cell` holds, per wave, the count, the base and the age/income
midpoint sums for every answer of every reportable question, for everyone and
for each current cohort, in total and by each standard cut. A standard view is
then one indexed read of tens of rows instead of a scan of the wave's answers
(the MDP lesson: the cost is rows fetched).

A cell stores the answer's map_key ("question:item:option", the harmoniser's
own key), never its concept: concept reads join cip_concept_map at read time,
so confirming a mapping never needs a rebuild. Cohort cells do depend on
mappings (a rule is written over concepts) — refresh_wave re-derives them.

The counts and bases are exactly repository.analyse's — tests prove it for
every question and cut.

    python -m app.data.cube --all          # every wave
    python -m app.data.cube --wave 2025-02-17
"""
from __future__ import annotations

import argparse
import logging
from typing import Optional, Sequence

from sqlalchemy import bindparam, text

from app.core.database import get_engine
from app.data import cohorts

log = logging.getLogger("cip.cube")

# Cuts whose values fit the cell key (each ≤ 40 characters).
CUBE_DIMS = ("total", "gender", "age_band", "generation", "income_band", "census_region", "urbanicity")


_COLUMNS = ("survey_id, cell_key, map_key, question_id, item_id, option_id, cohort_id, dim, dim_value,"
            " n, base_n, sum_age_mid, n_age_mid, sum_income_mid_k, n_income_mid")

# The wave's answers are read ONCE into a temporary table carrying every cut;
# each cut × cohort is then an aggregate over that table. Reading the answers
# per cut cost 78k primary-key lookups each time — 14 times per cohort.
_ROWS = """
    SELECT f.question_id AS qid, f.item_id AS iid, o.option_id AS oid, q.is_multi AS multi,
           a.value_code AS code, a.respondent_id AS rid, p.age_mid AS age, p.income_mid_k AS income,
           {cuts}
      FROM cip_answer a
      JOIN cip_field f ON f.field_id = a.field_id AND f.survey_id = :sid
      JOIN cip_question q ON q.question_id = f.question_id AND q.survey_id = :sid AND q.is_technical = 0
           AND q.is_virtual = 0
      LEFT JOIN cip_option o ON q.is_multi = 0 AND o.question_id = f.question_id AND o.value_code = a.value_code
      JOIN cip_respondent r ON r.respondent_id = a.respondent_id AND r.is_qualified = 1
      LEFT JOIN cip_profile p ON p.respondent_id = r.respondent_id
     WHERE a.survey_id = :sid AND a.value_code IS NOT NULL
       AND ((q.is_multi = 1 AND f.item_id IS NOT NULL)
            OR (q.is_multi = 0 AND q.qtype IN ('single', 'grid_single') AND o.option_id IS NOT NULL))"""
_CUTS = ", ".join(f"COALESCE(p.{d}, '') AS {d}" for d in CUBE_DIMS if d != "total")


def _value(dim: str) -> str:
    return "'Total'" if dim == "total" else f"x.{dim}"


def _cohort_join(cohort_id: Optional[int], alias: str = "x") -> str:
    if cohort_id is None:
        return ""
    return f" JOIN cip_respondent_cohort rc_{alias} ON rc_{alias}.respondent_id = {alias}.rid AND rc_{alias}.cohort_id = :cohort"


def _single_sql(dim: str, cohort_id: Optional[int]) -> str:
    """Single-choice questions and grid rows: base = who answered (per row)."""
    dv = _value(dim)
    return f"""
        INSERT INTO cip_agg_cell ({_COLUMNS})
        SELECT :sid,
               CONCAT(x.qid, ':', COALESCE(x.iid, 0), ':', x.oid, ':', :coh, ':', 0, ':', :dim, ':', {dv}),
               CONCAT(x.qid, ':', COALESCE(x.iid, 0), ':', x.oid),
               x.qid, x.iid, x.oid, :cohort, :dim, {dv},
               COUNT(*), SUM(COUNT(*)) OVER (PARTITION BY x.qid, x.iid, {dv}),
               SUM(x.age), COUNT(x.age), SUM(x.income), COUNT(x.income)
          FROM cip_tmp_cube x{_cohort_join(cohort_id)}
         WHERE x.multi = 0
         GROUP BY x.qid, x.iid, x.oid, {dv}"""


def _multi_sql(dim: str, cohort_id: Optional[int]) -> str:
    """Multi-select items: base = everyone who answered the question ("Total
    Answering"), so an item routed away from someone counts as not chosen."""
    dv, dv_y = _value(dim), _value(dim).replace("x.", "y.")
    return f"""
        INSERT INTO cip_agg_cell ({_COLUMNS})
        SELECT :sid,
               CONCAT(x.qid, ':', x.iid, ':', 0, ':', :coh, ':', 0, ':', :dim, ':', {dv}),
               CONCAT(x.qid, ':', x.iid, ':', 0),
               x.qid, x.iid, NULL, :cohort, :dim, {dv},
               SUM(CASE WHEN x.code = 1 THEN 1 ELSE 0 END), MAX(b.answered),
               SUM(CASE WHEN x.code = 1 THEN x.age END),
               SUM(CASE WHEN x.code = 1 AND x.age IS NOT NULL THEN 1 ELSE 0 END),
               SUM(CASE WHEN x.code = 1 THEN x.income END),
               SUM(CASE WHEN x.code = 1 AND x.income IS NOT NULL THEN 1 ELSE 0 END)
          FROM cip_tmp_cube x{_cohort_join(cohort_id)}
          JOIN (SELECT y.qid, {dv_y} AS dv, COUNT(DISTINCT y.rid) AS answered
                  FROM cip_tmp_cube2 y{_cohort_join(cohort_id, "y")}
                 WHERE y.multi = 1
                 GROUP BY y.qid, {dv_y}) b ON b.qid = x.qid AND b.dv = {dv}
         WHERE x.multi = 1
         GROUP BY x.qid, x.iid, {dv}"""


def _fill_rows(conn, survey_id: int) -> None:
    """The wave's answers with every cut, twice — MySQL cannot open one
    temporary table twice in a statement, and the multi base self-joins."""
    rows = _ROWS.format(cuts=_CUTS)
    for table in ("cip_tmp_cube", "cip_tmp_cube2"):
        conn.execute(text(f"CREATE TEMPORARY TABLE IF NOT EXISTS {table} AS {rows} AND 1 = 0"), {"sid": 0})
        conn.execute(text(f"DELETE FROM {table}"))
        conn.execute(text(f"INSERT INTO {table} {rows}"), {"sid": survey_id})


def build_cube(survey_id: int, cohort_ids: Optional[Sequence[Optional[int]]] = None, conn=None) -> int:
    """Replace the wave's cells — everything, or only the listed cohorts'
    (None in the list = everyone) — in the caller's transaction when one is
    given. Returns cells written."""
    if conn is None:
        with get_engine("etl").begin() as own:
            return build_cube(survey_id, cohort_ids, own)
    targets = list(cohort_ids) if cohort_ids is not None else \
        [None] + [c["cohort_id"] for c in cohorts.current_cohorts()]
    if cohort_ids is None:
        conn.execute(text("DELETE FROM cip_agg_cell WHERE survey_id = :sid"), {"sid": survey_id})
    else:
        conn.execute(text("DELETE FROM cip_agg_cell WHERE survey_id = :sid AND COALESCE(cohort_id, 0) IN :ids")
                     .bindparams(bindparam("ids", expanding=True)),
                     {"sid": survey_id, "ids": [c or 0 for c in targets] or [-1]})
    _fill_rows(conn, survey_id)
    written = 0
    for cohort_id in targets:
        params = {"sid": survey_id, "cohort": cohort_id, "coh": cohort_id or 0}
        for dim in CUBE_DIMS:
            for sql in (_single_sql(dim, cohort_id), _multi_sql(dim, cohort_id)):
                written += conn.execute(text(sql), {**params, "dim": dim}).rowcount
    return written


def refresh_cohorts(survey_id: int) -> int:
    """After a mapping decision: cohort rules are written over concepts, so
    re-derive every current cohort on the wave and rebuild the cells of those
    whose membership changed (or that have members but no cells). Everyone's
    cells never change — they join mappings at read time.

    One transaction: if the rebuild fails, the new memberships roll back with
    it, so the next attempt still sees the change."""
    signature = lambda conn, cid: tuple(conn.execute(text(
        "SELECT COUNT(*), COALESCE(SUM(respondent_id), 0) FROM cip_respondent_cohort"
        " WHERE cohort_id = :c AND survey_id = :s"), {"c": cid, "s": survey_id}).one())
    has_cells = lambda conn, cid: conn.execute(text(
        "SELECT 1 FROM cip_agg_cell WHERE survey_id = :s AND cohort_id = :c LIMIT 1"),
        {"s": survey_id, "c": cid}).first() is not None
    with get_engine("etl").begin() as conn:
        changed = []
        for c in cohorts.current_cohorts():
            before = signature(conn, c["cohort_id"])
            cohorts.derive(c["cohort_id"], [survey_id], conn)
            after = signature(conn, c["cohort_id"])
            if after != before or (after[0] and not has_cells(conn, c["cohort_id"])):
                changed.append(c["cohort_id"])
        # most decisions touch no cohort's questions: then nothing is rebuilt
        return build_cube(survey_id, changed, conn) if changed else 0


def refresh_wave(survey_id: int) -> int:
    """After a load: re-derive every current cohort on the wave, then rebuild
    all of its cells. The old cells go first, in their own commit — if the
    rebuild fails, readers fall back to the respondent-level engine instead of
    being served the previous load's numbers."""
    with get_engine("etl").begin() as conn:
        conn.execute(text("DELETE FROM cip_agg_cell WHERE survey_id = :sid"), {"sid": survey_id})
    with get_engine("etl").begin() as conn:
        for c in cohorts.current_cohorts():
            cohorts.derive(c["cohort_id"], [survey_id], conn)
        return build_cube(survey_id, None, conn)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s | %(message)s")
    ap = argparse.ArgumentParser(description="Build the cube (cip_agg_cell)")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="every wave, oldest first")
    group.add_argument("--wave", help="one wave label")
    args = ap.parse_args()
    with get_engine("etl").connect() as conn:
        sql = "SELECT survey_id, wave_label FROM cip_survey"
        rows = conn.execute(text(sql + (" WHERE wave_label = :w" if args.wave else "") + " ORDER BY wave_date, survey_id"),
                            {"w": args.wave}).all()
    for n, (sid, wave) in enumerate(rows, start=1):
        log.info("[%d/%d] %s survey_id=%s: %d cells", n, len(rows), wave, sid, build_cube(sid))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
