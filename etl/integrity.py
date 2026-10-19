"""After every run: is the warehouse whole? Find what is broken, mend what can be rebuilt, report the rest.

Three kinds of check (all read-only until a fix runs):

  derived   a verified wave is missing rows the ETL derives from its answers (cube,
            search, tracker lines) — healed by rebuilding that wave's derived rows
  orphan    a derived or index row points at nothing — healed by deleting it
  base      something in the loaded data itself is wrong (duplicate respondents,
            a register row without its wave, a wave stuck loading, a closed survey
            not loaded for 3 days) — never touched automatically: reported, so a person decides
  watch     a survey the warehouse does not hold and the pipeline cannot fetch by itself
            (hibernated before it was loaded; no longer listed by Forsta) — logged every
            run as a warning, never fails the run: recovering it needs a person in Forsta

    python -m etl.integrity            # check and heal; exit 1 if anything is still wrong
    python -m etl.integrity --check    # report only

Every check is cheap (≤ 4 s on cip_stg, 23 M answers), so the scheduled run calls run() each time.
"""
from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Optional

from sqlalchemy import text

from app.core.database import get_engine

log = logging.getLogger("cip.integrity")


def rebuild_cube(survey_id: int) -> None:
    from app.data import cube
    cube.refresh_wave(survey_id)


def rebuild_search(survey_id: int) -> None:
    from etl.loaders import index_survey
    index_survey(survey_id, concepts=False)


def rebuild_lines(survey_id: int) -> None:
    from etl import tracker_line
    tracker_line.build(survey_id)


@dataclass
class Check:
    name: str
    kind: str                                  # derived · orphan · base · watch
    sql: str                                   # derived: survey ids · orphan, base: one count
    fix: Optional[Callable[[int], None]] = None
    delete: Optional[str] = None

# A wave with no reportable question (14, 16–19: Qualtrics, all text) has nothing to put in the cube.
REPORTABLE = ("EXISTS (SELECT 1 FROM cip_question q WHERE q.survey_id = s.survey_id AND q.is_technical = 0"
              " AND q.is_virtual = 0 AND (q.is_multi = 1 OR q.qtype IN ('single', 'grid_single')))")

CHECKS = [
    Check("verified wave without cube cells", "derived",
          "SELECT s.survey_id FROM cip_survey s WHERE s.load_status = 'verified' AND " + REPORTABLE +
          " AND NOT EXISTS (SELECT 1 FROM cip_agg_cell c WHERE c.survey_id = s.survey_id)", fix=rebuild_cube),
    Check("verified wave missing from search", "derived",
          "SELECT s.survey_id FROM cip_survey s WHERE s.load_status = 'verified'"
          " AND NOT EXISTS (SELECT 1 FROM cip_search x WHERE x.kind = 'survey' AND x.survey_id = s.survey_id)",
          fix=rebuild_search),
    Check("Forsta tracker wave without line-by-line rows", "derived",
          "SELECT s.survey_id FROM cip_survey s WHERE s.load_status = 'verified' AND s.platform = 'forsta'"
          " AND s.study_type = 'tracker'"
          " AND NOT EXISTS (SELECT 1 FROM cip_tracker_line t WHERE t.survey_id = s.survey_id)", fix=rebuild_lines),
    Check("tracker line without its respondent", "orphan",
          "SELECT COUNT(*) FROM cip_tracker_line t LEFT JOIN cip_respondent r ON r.respondent_id = t.respondent_id"
          " WHERE r.respondent_id IS NULL",
          delete="DELETE FROM cip_tracker_line WHERE respondent_id NOT IN (SELECT respondent_id FROM cip_respondent)"),
    Check("search row of a deleted wave", "orphan",
          "SELECT COUNT(*) FROM cip_search x LEFT JOIN cip_survey s ON s.survey_id = x.survey_id"
          " WHERE x.survey_id IS NOT NULL AND s.survey_id IS NULL",
          delete="DELETE FROM cip_search WHERE survey_id IS NOT NULL AND survey_id NOT IN (SELECT survey_id FROM cip_survey)"),
    Check("search row of a deleted question", "orphan",
          "SELECT COUNT(*) FROM cip_search x LEFT JOIN cip_question q ON q.question_id = x.question_id"
          " WHERE x.question_id IS NOT NULL AND q.question_id IS NULL",
          delete="DELETE FROM cip_search WHERE question_id IS NOT NULL"
                 " AND question_id NOT IN (SELECT question_id FROM cip_question)"),
    Check("search row of a deleted concept", "orphan",
          "SELECT COUNT(*) FROM cip_search x LEFT JOIN cip_concept c ON c.concept_id = x.concept_id"
          " WHERE x.concept_id IS NOT NULL AND c.concept_id IS NULL",
          delete="DELETE FROM cip_search WHERE concept_id IS NOT NULL"
                 " AND concept_id NOT IN (SELECT concept_id FROM cip_concept)"),
    Check("calendar row of a survey not in the register", "orphan",
          "SELECT COUNT(*) FROM cip_wave_module m LEFT JOIN cip_forsta_survey f ON f.forsta_path = m.forsta_path"
          " WHERE f.forsta_path IS NULL",
          delete="DELETE FROM cip_wave_module WHERE forsta_path NOT IN (SELECT forsta_path FROM cip_forsta_survey)"),
    Check("tracker line of an unqualified or other wave's respondent", "base",
          "SELECT COUNT(*) FROM cip_tracker_line t JOIN cip_respondent r ON r.respondent_id = t.respondent_id"
          " WHERE r.is_qualified = 0 OR r.survey_id <> t.survey_id"),
    Check("register row pointing at a missing wave", "base",
          "SELECT COUNT(*) FROM cip_forsta_survey f LEFT JOIN cip_survey s ON s.survey_id = f.survey_id"
          " WHERE f.survey_id IS NOT NULL AND s.survey_id IS NULL"),
    Check("register says loaded, wave not verified", "base",
          "SELECT COUNT(*) FROM cip_forsta_survey f LEFT JOIN cip_survey s ON s.survey_id = f.survey_id"
          " WHERE f.load_state = 'loaded' AND COALESCE(s.load_status, '') <> 'verified'"),
    Check("wave stuck loading", "base", "SELECT COUNT(*) FROM cip_survey WHERE load_status = 'loading'"),
    Check("verified wave without qualified respondents", "base",
          "SELECT COUNT(*) FROM cip_survey s WHERE s.load_status = 'verified' AND NOT EXISTS"
          " (SELECT 1 FROM cip_respondent r WHERE r.survey_id = s.survey_id AND r.is_qualified = 1)"),
    Check("duplicate Forsta respondent (uuid) in a wave", "base",
          "SELECT COUNT(*) FROM (SELECT survey_id, forsta_uuid FROM cip_respondent"
          " WHERE forsta_uuid IS NOT NULL AND forsta_uuid <> '' GROUP BY survey_id, forsta_uuid HAVING COUNT(*) > 1) d"),
    Check("same panelist qualified twice in a wave", "base",
          "SELECT COUNT(*) FROM (SELECT survey_id, respondent_key FROM cip_respondent"
          " WHERE respondent_key IS NOT NULL AND is_qualified = 1 GROUP BY survey_id, respondent_key HAVING COUNT(*) > 1) d"),
    Check("closed Forsta survey still not loaded after 3 days", "base",
          "SELECT COUNT(*) FROM cip_forsta_survey WHERE load_state IN ('due', 'failed') AND closed_at < :three_days_ago"),
    Check("closed Forsta survey hibernated before it was loaded — reactivate it in Forsta, the next run loads it",
          "watch", "SELECT COUNT(*) FROM cip_forsta_survey WHERE load_state = 'hibernated' AND survey_id IS NULL"),
    Check("Forsta survey no longer listed by Forsta and never loaded — ask Forsta to restore it", "watch",
          "SELECT COUNT(*) FROM cip_forsta_survey WHERE last_seen < :week_ago AND survey_id IS NULL"),
    Check("profile filed under another wave", "base",
          "SELECT COUNT(*) FROM cip_profile p JOIN cip_respondent r ON r.respondent_id = p.respondent_id"
          " WHERE r.survey_id <> p.survey_id"),
]


def found(conn, check: Check) -> list[int]:
    """Survey ids (derived) or [count] — empty when the check passes."""
    now = datetime.now()
    params = {k: v for k, v in {"three_days_ago": now - timedelta(days=3), "week_ago": now - timedelta(days=7)}.items()
              if f":{k}" in check.sql}
    if check.kind == "derived":
        return [int(sid) for (sid,) in conn.execute(text(check.sql), params)]
    count = int(conn.execute(text(check.sql), params).scalar() or 0)
    return [count] if count else []


def run(heal: bool = True, waves: int = 20) -> list[str]:
    """Every check, mending what is derived; returns what is still wrong ([] = whole).
    At most `waves` rebuilds per check per run, so a mass gap heals over several runs."""
    eng = get_engine("etl")
    left = []
    for check in CHECKS:
        with eng.connect() as conn:
            hits = found(conn, check)
        if not hits:
            continue
        what = f"{check.name}: " + (f"survey_id {hits[:10]}" if check.kind == "derived" else
                                     f"{hits[0]} surveys" if check.kind == "watch" else f"{hits[0]} rows")
        if check.kind == "watch":
            log.warning("Integrity (watch): %s", what)
            continue
        if not heal or check.kind == "base":
            log.warning("Integrity: %s", what)
            left.append(what)
            continue
        log.warning("Integrity: %s — healing", what)
        try:
            if check.delete:
                with eng.begin() as conn:
                    conn.execute(text(check.delete))
            else:
                for survey_id in hits[:waves]:
                    check.fix(survey_id)
        except Exception as exc:
            log.exception("Integrity: healing %r failed", check.name)
            left.append(f"{what} (healing failed: {type(exc).__name__}: {str(exc)[:300]})")
            continue
        with eng.connect() as conn:
            still = found(conn, check)
        if still:
            left.append(f"{what} (still wrong after healing)")
        else:
            log.info("Integrity: healed %s", check.name)
    return left


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s | %(message)s")
    ap = argparse.ArgumentParser(description="Check (and heal) the CIP warehouse")
    ap.add_argument("--check", action="store_true", help="report only, change nothing")
    left = run(heal=not ap.parse_args().check)
    for line in left:
        print(line)
    print("whole" if not left else f"{len(left)} problem(s)")
    return 1 if left else 0


if __name__ == "__main__":
    raise SystemExit(main())
