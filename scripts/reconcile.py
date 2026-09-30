"""Prove the loaded data: recompute every published Total from raw answers.

    python scripts/reconcile.py            # every wave in the database
    python scripts/reconcile.py --wave 2026-09-28

For each question Forsta tabulated, the portal's own answer engine
(repository.analyse, unfiltered) must give the same percentage as the
cross-tab cell Forsta published, and every banner column (Male, GenZ,
Northeast, …) must have the same size as the matching demographic cohort. A mismatch means the load or the engine is
wrong — the portal would show a number the client's report does not.
Exit code 1 on any mismatch.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.data.repository as repo  # noqa: E402
from app.core.database import query_df  # noqa: E402
from etl.legacy_dwh import reconcile_legacy  # noqa: E402

TOLERANCE = 0.0005  # Forsta rounds nothing, but allow float noise


def published(survey_id: int):
    return query_df(
        """
        SELECT q.question_id, q.qcode, q.qtype, q.is_multi,
               c.item_label, c.stub_label, c.pct
          FROM csi_crosstab c
          JOIN csi_crosstab_run r ON r.run_id = c.run_id AND r.is_current = 1
          JOIN csi_segment s ON s.segment_id = c.segment_id AND s.is_total = 1
          JOIN csi_question q ON q.question_id = c.question_id
         WHERE c.survey_id = :sid AND c.stub_type = 'item' AND c.pct IS NOT NULL
           AND q.is_technical = 0
        """,
        {"sid": survey_id},
    )


def reconcile(survey_id: int) -> tuple[int, int, list[str]]:
    pub = published(survey_id)
    checked = matched = 0
    problems: list[str] = []
    for (qid, qcode, qtype), cells in pub.groupby(["question_id", "qcode", "qtype"]):
        ours = repo.analyse(survey_id, int(qid), ())
        mine = dict(zip(ours["answer"], ours["pct"])) if not ours.empty else {}
        for c in cells.itertuples():
            key = f"{c.item_label} — {c.stub_label}" if str(qtype).startswith("grid") and not c.is_multi and c.item_label else c.stub_label
            checked += 1
            got = mine.get(key)
            if got is None and float(c.pct) == 0:
                matched += 1          # nobody chose it, so there is no row to compute
            elif got is not None and abs(float(got) - float(c.pct)) <= TOLERANCE:
                matched += 1
            else:
                problems.append(f"{qcode:10} {key[:60]:60} published {float(c.pct):.4f}  ours {got}")
    return checked, matched, problems


# Profile columns derived from one source question.
DERIVED = {"age": ["age_band", "generation"], "state_name": ["state_name", "census_region"]}

# Differences that are Forsta's, not ours — reported, not failed.
KNOWN = {
    "South": "Forsta's region banner omits Maryland; the portal uses US Census regions",
    "Midwest": "Forsta's region banner omits Missouri; the portal uses US Census regions",
}


def reconcile_banner(survey_id: int) -> tuple[int, list[str], list[str]]:
    """Banner columns vs the demographic cohorts the filters build. A column is
    matched through the question its Forsta definition uses ('(CS1.r1)' -> CS1),
    because CS1 and CS2 share the same labels."""
    dims_by_q: dict[str, list[str]] = {}
    for dim, qcode in query_df(
        "SELECT dimension, qcode FROM csi_profile_map WHERE survey_id = :sid", {"sid": survey_id}
    ).itertuples(index=False):
        dims_by_q.setdefault(qcode, []).extend(DERIVED.get(dim, [dim]))

    def cohort(dim: str, value: str) -> int:
        return int(query_df(
            f"""SELECT COUNT(*) AS n FROM csi_profile p
                  JOIN csi_respondent r ON r.respondent_id = p.respondent_id
                 WHERE p.survey_id = :sid AND r.is_qualified = 1 AND p.{dim} = :v""",
            {"sid": survey_id, "v": value},
        ).n.iloc[0])

    segments = query_df(
        "SELECT seg_label, seg_base_n, seg_definition FROM csi_segment "
        "WHERE survey_id = :sid AND is_total = 0",
        {"sid": survey_id},
    )
    checked, problems, notes = 0, [], []
    for seg in segments.itertuples():
        m = re.match(r"\W*(\w+?)\.", seg.seg_definition or "")
        dims = [d for d in dims_by_q.get(m.group(1) if m else "", []) if d in repo.PROFILE_DIMENSIONS]
        ours = next((n for n in (cohort(d, seg.seg_label) for d in dims) if n), None)
        if ours is None:
            continue              # a banner built from a survey answer, not a demographic
        checked += 1
        if ours == seg.seg_base_n:
            continue
        line = f"banner {seg.seg_label:20} published n={seg.seg_base_n}  ours n={ours}"
        if seg.seg_label in KNOWN:
            notes.append(f"{line}  ({KNOWN[seg.seg_label]})")
        else:
            problems.append(line)
    return checked, problems, notes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wave")
    args = ap.parse_args()
    # call the functions directly, outside the Streamlit cache
    for name in ("analyse", "list_surveys"):
        setattr(repo, name, getattr(repo, name).__wrapped__)

    surveys = repo.list_surveys()
    if args.wave:
        surveys = surveys[surveys.wave_label == args.wave]
    bad = 0
    for s in surveys.itertuples():
        ref = query_df("SELECT platform, source_ref FROM csi_survey WHERE survey_id = :s",
                       {"s": int(s.survey_id)}).iloc[0]
        if ref.platform != "forsta":
            if str(ref.source_ref).startswith("xlsx:"):
                print(f"{s.wave_label}  {s.title}\n  no published source to reconcile against")
                continue
            checked, problems = reconcile_legacy(int(s.survey_id))
            bad += len(problems)
            print(f"{s.wave_label}  {s.title}\n  {checked - len(problems)}/{checked}"
                  " legacy answers match the source")
            for p in problems[:40]:
                print("   ✗", p)
            continue
        checked, matched, problems = reconcile(int(s.survey_id))
        seg_checked, seg_problems, seg_notes = reconcile_banner(int(s.survey_id))
        problems += seg_problems
        bad += len(problems)
        print(f"{s.wave_label}  {s.title}\n  {matched}/{checked} published cells reproduced"
              f"\n  {seg_checked - len(seg_problems) - len(seg_notes)}/{seg_checked} banner columns"
              f" match their cohort, {len(seg_notes)} known Forsta difference(s)")
        for note in seg_notes:
            print("   ≠", note)
        for p in problems[:40]:
            print("   ✗", p)
        if len(problems) > 40:
            print(f"   … {len(problems) - 40} more")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
