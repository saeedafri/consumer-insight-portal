"""Prove the loaded data against its source.

    python scripts/reconcile.py            # every wave in the database
    python scripts/reconcile.py --wave 2026-09-28

Forsta waves are re-read from the Forsta API (GET only) and every answer is
compared with what is stored; legacy waves (Qualtrics, SurveyMonkey) are
compared with the dwh_sm* tables they were loaded from. A wave loaded from a
one-off export (`xlsx:` source) has no source left to compare against.
Exit code 1 on any difference.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import query_df  # noqa: E402
from etl.legacy_dwh import reconcile_legacy  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wave")
    args = ap.parse_args()
    surveys = query_df(
        "SELECT survey_id, wave_label, title, platform, source_ref FROM cip_survey"
        " WHERE load_status = 'verified'" + (" AND wave_label = :w" if args.wave else "") +
        " ORDER BY wave_date, survey_id", {"w": args.wave})
    bad = 0
    for s in surveys.itertuples():
        if str(s.source_ref).startswith("xlsx:"):
            print(f"{s.wave_label}  {s.title}\n  no source left to reconcile against")
            continue
        if s.platform == "forsta":
            from etl.forsta_etl import reconcile_survey
            checked, problems = reconcile_survey(int(s.survey_id))
        else:
            checked, problems = reconcile_legacy(int(s.survey_id))
        bad += len(problems)
        print(f"{s.wave_label}  {s.title}\n  {checked - len(problems)}/{checked} answers match the source")
        for p in problems[:40]:
            print("   ✗", p)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
