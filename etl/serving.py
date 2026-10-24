"""The ETL's last step: the serving tables every user-facing screen reads (sql/005_serving.sql).

After a wave is loaded, verified and cubed, this turns its cube cells (qualified respondents, every
standard cut) into finished rows: labels, percentage, the prior-week and last-year comparison, and
flags that stop a reader comparing unlike bases. Screens then read one primary-key range per widget
and do no arithmetic. Nothing here knows about any particular screen.

It also keeps the cube's own input rows (each qualified answer with all six cuts) as srv_answer, so
a combined filter such as generation × gender is one small GROUP BY instead of a scan of the answers.

Significance is decided here, once, for every screen (flags sig_prior / sig_ly on a Total row): a two-sided
two-proportion z-test (pooled) of the row against the same answer in the prior week, and in the same week last
year, then Benjamini-Hochberg at a 5 % false-discovery rate over the wave's testable Total rows only. A row is
testable when both percentages are present, both bases are at least TEST_BASE, its base did not shift
(base_changed_*) and it is not a filler answer (None of these, Other -, Prefer not…; web/src/api.ts isFiller).
Untestable rows are left out of the correction (they never count as p = 1).

Every verified wave is served, however few people answered it: nothing is excluded (the user's rule, 23 Oct 2026).

    python -m etl.serving --wave 412      # one wave
    python -m etl.serving --all --jobs 4 --missing   # backfill verified waves not built yet, 4 at a time
"""
from __future__ import annotations

import argparse
import logging
import math
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from functools import lru_cache

from sqlalchemy import bindparam, inspect, text
from sqlalchemy.exc import OperationalError

from app.core.database import bulk_insert, get_engine
from app.data.cube import ANSWER_CUTS, ANSWER_ROWS, CUBE_DIMS
from app.data.harmonise import normalise_text

log = logging.getLogger("cip.serving")
SMALL_BASE = 50       # respondents: below this a percentage is flagged
BASE_SHIFT = 10.0     # points: a question's base share of qualified respondents moving more than this is a routing change
PRIOR_DAYS = 14       # a tracker's previous wave must be at most this old to count as "prior week"
YEAR_DAYS = (300, 430)   # an annual or ad hoc study's "last year": its family's latest wave this many days earlier
TEST_BASE = 30        # respondents on each side before a difference is tested (= app/data/payloads.TEST_BASE)
FDR = 0.05            # Benjamini-Hochberg false-discovery rate for sig_prior / sig_ly
FILLER = re.compile(r"^(none of (these|the above)|other\s*[-–(]|prefer not)", re.I)   # = web/src/api.ts isFiller
CUTS = tuple(d for d in CUBE_DIMS if d != "total")
RESULT_COLUMNS = ("survey_id", "qcode", "dim", "dim_value", "item_id", "option_id", "question_id", "qtype", "item_label",
                  "option_code", "option_label", "sort_order", "concept_option_id", "n", "base_n", "pct", "prior_pct",
                  "prior_base_n", "ly_pct", "ly_base_n", "flags")


def _day(value) -> date:
    return date.fromisoformat(str(value)[:10])   # MySQL returns a date, SQLite a string


@lru_cache(maxsize=None)
def schema_has(engine, table: str, column: str, member: str = "") -> bool:
    """Whether the database has this column (and this SET or ENUM member): code may run before sql/009 is applied,
    and MySQL rejects a value its column cannot hold. SQLite keeps SET and ENUM values as text."""
    found = {c["name"]: c["type"] for c in inspect(engine).get_columns(table)}
    if column not in found or not member or engine.dialect.name != "mysql":
        return column in found
    return member in (getattr(found[column], "values", None) or getattr(found[column], "enums", None) or ())


def comparison(conn, survey_id: int) -> dict:
    """The wave, its prior week and its same week last year (or why there is none). An annual or ad hoc study has no
    prior week; its last year is the family's latest wave YEAR_DAYS earlier, since annual studies do not field on the
    same week each year."""
    w = conn.execute(text("SELECT survey_id, survey_family, study_type, wave_date, platform, source_ref, field_end"
                          " FROM cip_survey WHERE survey_id = :s"), {"s": survey_id}).mappings().one()
    day = _day(w["wave_date"])
    pick = lambda lo, hi, latest: conn.execute(text(
        "SELECT survey_id FROM cip_survey s WHERE survey_family = :f AND load_status = 'verified' AND survey_id <> :s"
        f" AND wave_date BETWEEN :lo AND :hi ORDER BY wave_date {'DESC' if latest else 'ASC'} LIMIT 1"),
        {"f": w["survey_family"], "s": survey_id, "lo": lo, "hi": hi}).scalar()
    prior = pick(day - timedelta(days=PRIOR_DAYS), day - timedelta(days=1), True) if w["study_type"] == "tracker" else None
    target = day - timedelta(days=364)
    if w["study_type"] == "tracker":
        ly = pick(target - timedelta(days=3), target + timedelta(days=3), False)
    else:
        ly = pick(day - timedelta(days=YEAR_DAYS[1]), day - timedelta(days=YEAR_DAYS[0]), True)
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
            "qualified": {k: int(v or 0) for k, v in qualified.items()},
            # loaded while Forsta still had it open (etl/forsta_etl.fielded): reloaded, and so final, once it closes
            "in_field": w["platform"] == "forsta" and not w["field_end"]}


def cube_rows(conn, survey_ids: list[int]) -> list[dict]:
    """Labelled cube cells for these waves: Total and every cut, technical and virtual questions left out, each with
    its question's normalised wording (read once per question, not once per cell) and its harmonised answer (a
    confirmed cip_concept_map row on the cell's map_key; the cube itself never stores one). A cut's blank value
    (respondents with no profile: the wave never asked it) is not a segment, so it is left out."""
    wording = {qid: normalise_text(t) for qid, t in conn.execute(text(
        "SELECT question_id, qtext FROM cip_question WHERE survey_id IN :ids").bindparams(bindparam("ids", expanding=True)),
        {"ids": survey_ids})}
    return [{**r, "qtext": wording.get(r["question_id"], "")} for r in conn.execute(text(
        "SELECT c.survey_id, c.question_id, q.qcode, q.qtype, COALESCE(c.item_id, 0) AS item_id,"
        "       COALESCE(c.option_id, 0) AS option_id, COALESCE(i.item_label, '') AS item_label,"
        "       o.value_code AS option_code, o.value_label AS option_label,"
        "       COALESCE(i.sort_order, 0) * 1000 + COALESCE(o.sort_order, 0) AS sort_order,"
        "       COALESCE(c.concept_option_id, m.concept_option_id) AS concept_option_id, c.dim, c.dim_value, c.n, c.base_n"
        "  FROM cip_agg_cell c"
        "  JOIN cip_question q ON q.question_id = c.question_id AND q.survey_id = c.survey_id"   # lets MySQL start
        "       AND q.survey_id IN :ids AND q.is_technical = 0 AND q.is_virtual = 0"                # from this wave's questions
        "  LEFT JOIN cip_item i ON i.item_id = c.item_id"
        "  LEFT JOIN cip_option o ON o.option_id = c.option_id"
        "  LEFT JOIN cip_concept_map m ON m.survey_id = c.survey_id AND m.map_key = c.map_key AND m.status = 'confirmed'"
        "       AND m.concept_option_id IS NOT NULL"
        " WHERE c.survey_id IN :ids AND c.cohort_id IS NULL AND c.base_n > 0 AND (c.dim = 'total' OR c.dim_value <> '')")
        .bindparams(bindparam("ids", expanding=True)), {"ids": survey_ids}).mappings()]


def _own(c: dict) -> tuple:
    """A cell's identity within its wave: two items of one question may share a label (survey 97 Q7)."""
    return c["question_id"], c["item_id"], c["option_id"], c["dim"], c["dim_value"]


def _label(c: dict) -> tuple:
    return c["qcode"], normalise_text(c["item_label"]), c["option_code"], c["dim"], c["dim_value"]


def _concept(c: dict):
    return c["concept_option_id"] and (c["concept_option_id"], c["dim"], c["dim_value"])


def _index(cells: list[dict]) -> dict:
    """Each wave's cells by identity, by harmonised answer and by code + answer label; a concept or label key that
    two cells of one wave share points at neither (None), so it never matches."""
    out: dict[int, dict] = {}
    for c in cells:
        w = out.setdefault(c["survey_id"], {"own": {}, "concept": {}, "label": {}})
        w["own"][_own(c)] = c
        for kind, key in (("concept", _concept(c)), ("label", _label(c))):
            if key:
                w[kind][key] = None if key in w[kind] else c
    return out


def counterpart(waves: dict, mine: int, other, c: dict):
    """The same answer and cut in another wave: by harmonised answer when both have one, else by code, answer label
    and answer code when that is unique in both waves."""
    w = waves.get(other)
    if not w:
        return None
    if _concept(c) and w["concept"].get(_concept(c)):
        return w["concept"][_concept(c)]
    return w["label"].get(_label(c)) if waves[mine]["label"].get(_label(c)) is c else None


def same_question(a: dict, b: dict) -> bool:
    """Two waves' cells under one question code are the same question: the same wording, or answers harmonised to
    the same concept (a reworded question someone linked). Codes are reused for new topics (Q13 was footwear one
    week and Cyber Monday the next), so a matching code and answer label alone prove nothing."""
    if a["concept_option_id"] and a["concept_option_id"] == b["concept_option_id"]:
        return True
    return a["qtext"] == b["qtext"]   # cube_rows normalised them


def rows_for(wave: dict, cells: list[dict]) -> list[dict]:
    """Finished serving rows: one per cube cell of the wave, with its percentage, the same answer in the prior and
    last-year waves (counterpart, and same_question), flags, and the significance flags (module docstring)."""
    waves = _index(cells)
    sid, q = wave["survey_id"], wave["qualified"]
    total = lambda w, c: waves[w]["own"].get((*_own(c)[:3], "total", "Total"))   # noqa: E731
    out = []
    for c in waves.get(sid, {"own": {}})["own"].values():
        row = {k: c[k] for k in ("survey_id", "qcode", "dim", "dim_value", "item_id", "option_id", "question_id", "qtype",
                                 "item_label", "option_code", "option_label", "sort_order", "concept_option_id", "n", "base_n")}
        row["pct"] = round(100 * c["n"] / c["base_n"], 3)
        flags = ["small_base"] if c["base_n"] < SMALL_BASE else []
        for name, other in (("prior", wave["prior"]), ("ly", wave["ly"])):
            match = counterpart(waves, sid, other, c) if other else None
            if match and not same_question(c, match):
                flags.append(f"wording_changed_{name}")
                match = None
            row[f"{name}_pct"] = round(100 * match["n"] / match["base_n"], 3) if match else None
            row[f"{name}_base_n"] = match["base_n"] if match else None
            row[f"{name}_n"] = match["n"] if match else None   # for the significance test; not a column
            # the base share is only comparable on the same cut, so judge routing on Total
            theirs, mine = (total(other, match), total(sid, c)) if match else (None, None)
            if theirs and mine and q.get(sid) and q.get(other) and \
                    abs(100 * mine["base_n"] / q[sid] - 100 * theirs["base_n"] / q[other]) > BASE_SHIFT:
                flags.append(f"base_changed_{name}")
        row["flags"] = ",".join(flags)
        out.append(row)
    mark_significant(out)
    return out


def p_value(n1: int, base1: int, n2: int, base2: int) -> float:
    """Two-sided p of the pooled two-proportion z-test (as web/src/stats.ts pValue)."""
    pooled = (n1 + n2) / (base1 + base2)
    se = math.sqrt(pooled * (1 - pooled) * (1 / base1 + 1 / base2))
    return math.erfc(abs(n1 / base1 - n2 / base2) / se / math.sqrt(2)) if se > 0 else 1.0


def survives(ps: list[float], q: float = FDR) -> list[bool]:
    """Benjamini-Hochberg: which of these p-values survive a false-discovery rate of q."""
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    cut = max((k for k, i in enumerate(order, 1) if ps[i] <= k / len(ps) * q), default=0)
    keep = [False] * len(ps)
    for k, i in enumerate(order, 1):
        keep[i] = k <= cut
    return keep


def mark_significant(rows: list[dict]) -> None:
    """Add sig_prior / sig_ly to the wave's Total rows that move significantly (the rule: module docstring)."""
    for name in ("prior", "ly"):
        tested = [r for r in rows if r["dim"] == "total" and r[f"{name}_pct"] is not None
                  and r["base_n"] >= TEST_BASE and (r[f"{name}_base_n"] or 0) >= TEST_BASE
                  and f"base_changed_{name}" not in r["flags"].split(",")
                  and not FILLER.match(str(r["option_label"] or r["item_label"] or "").strip())]
        ps = [p_value(r["n"], r["base_n"], r[f"{name}_n"], r[f"{name}_base_n"]) for r in tested]
        for r, keep in zip(tested, survives(ps)):
            if keep:
                r["flags"] = ",".join(filter(None, (r["flags"], f"sig_{name}")))


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
    engine = get_engine("etl")
    sig, in_field = schema_has(engine, "srv_result", "flags", "sig_ly"), schema_has(engine, "srv_wave", "in_field")
    with engine.begin() as conn:
        if conn.dialect.name == "mysql":   # no gap locks: parallel builds of other waves don't block this one
            conn.execute(text("SET TRANSACTION ISOLATION LEVEL READ COMMITTED"))
        wave = comparison(conn, survey_id)
        rows = rows_for(wave, cube_rows(conn, [x for x in (survey_id, wave["prior"], wave["ly"]) if x]))
        if not sig:   # sql/009 not applied yet: srv_result.flags cannot hold them
            for r in rows:
                r["flags"] = ",".join(f for f in r["flags"].split(",") if f and not f.startswith("sig_"))
        drop_wave(conn, survey_id)
        conn.execute(text(
            "INSERT INTO srv_wave (survey_id, survey_family, study_type, wave_date, qualified_n, prior_survey_id,"
            f" ly_survey_id, ly_status, rows_built{', in_field' if in_field else ''})"
            f" VALUES (:s, :f, :t, :d, :q, :p, :l, :ls, :r{', :inf' if in_field else ''})"),
            {"s": survey_id, "f": wave["survey_family"] or "", "t": wave["study_type"] or "", "d": wave["wave_date"],
             "q": wave["qualified"].get(survey_id, 0), "p": wave["prior"], "l": wave["ly"], "ls": wave["ly_status"],
             "r": len(rows), "inf": int(wave["in_field"])})
        bulk_insert(conn, "srv_result", RESULT_COLUMNS, (tuple(r[c] for c in RESULT_COLUMNS) for r in rows))
        store_answers(conn, survey_id)
    return len(rows)


def drop_wave(conn, survey_id: int) -> None:
    """The wave's serving rows gone (each table by name: SQLite only cascades with foreign keys switched on)."""
    for table in ("srv_answer", "srv_result", "srv_wave"):
        conn.execute(text(f"DELETE FROM {table} WHERE survey_id = :s"), {"s": survey_id})


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
        ids = [r[0] for r in conn.execute(text(   # only the next fortnight and next year (YEAR_DAYS) can point here
            "SELECT survey_id FROM srv_wave WHERE survey_family = :f AND survey_id <> :s"
            " AND (wave_date BETWEEN :a AND :b OR wave_date BETWEEN :c AND :d)"),
            {"f": w.survey_family, "s": survey_id, "a": day + timedelta(days=1), "b": day + timedelta(days=PRIOR_DAYS),
             "c": day + timedelta(days=YEAR_DAYS[0]), "d": day + timedelta(days=YEAR_DAYS[1])})]
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
            + " ORDER BY s.wave_date DESC, s.survey_id DESC"))]   # newest first: the waves people open come back first
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
    if not (a.wave or a.all):
        p.print_help()
        return 1
    from etl.loaders import etl_lock
    with etl_lock():
        if a.wave:
            print(f"survey {a.wave}: {build_wave(a.wave)} serving rows")
        else:
            print(f"{build_all(a.jobs, a.missing)} serving rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
