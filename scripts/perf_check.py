"""Time the three speed targets of the survey platform design (§1 goal 4),
P95 over repeated uncached runs, against whatever database .env points at:

    standard view       one question × one standard cut, one wave     < 1 s
    ad-hoc cohort       two arbitrary criteria, one wave (engine)     < 3 s
    five-wave stack     one concept pooled over five waves            < 5 s

    python scripts/perf_check.py [--runs 20]

Run from the office network over the VPN — that round trip is the target.
Exit code 1 if any target is missed.
"""
from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.data.repository as repo  # noqa: E402
from app.core.database import query_df  # noqa: E402

BEAUTY_BOUGHT = "BT1_A88981"          # "Have you purchased any beauty products … past three months?"
BEAUTY_WAVES = ("2024-06-03", "2024-08-26", "2024-11-25", "2025-02-17", "2025-05-12")


def uncached(fn):
    return getattr(fn, "__wrapped__", fn)


def p95(times: list[float]) -> float:
    return statistics.quantiles(times, n=20)[-1] if len(times) >= 2 else times[0]


def timed(action, runs: int) -> list[float]:
    out = []
    for _ in range(runs):
        started = time.perf_counter()
        action()
        out.append(time.perf_counter() - started)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=20)
    runs = ap.parse_args().runs

    concept = int(query_df("SELECT concept_id FROM csi_concept WHERE concept_code = :c",
                           {"c": BEAUTY_BOUGHT}).concept_id.iloc[0])
    waves = query_df(
        "SELECT DISTINCT m.survey_id, s.wave_label FROM csi_concept_map m JOIN csi_survey s ON s.survey_id = m.survey_id"
        " WHERE m.concept_id = :c AND m.status = 'confirmed' AND m.concept_option_id IS NULL ORDER BY s.wave_label", {"c": concept})
    stack = waves[waves.wave_label.isin(BEAUTY_WAVES)].survey_id.astype(int).tolist()
    one = int(waves[waves.wave_label == "2025-02-17"].survey_id.iloc[0])
    question = int(query_df(
        "SELECT m.question_id FROM csi_concept_map m WHERE m.survey_id = :s AND m.concept_id = :c"
        " AND m.concept_option_id IS NULL AND m.status = 'confirmed'", {"s": one, "c": concept}).question_id.iloc[0])
    target_multi = int(query_df(
        "SELECT question_id FROM csi_question WHERE survey_id = :s AND is_multi = 1 AND is_technical = 0"
        " ORDER BY sort_order LIMIT 1", {"s": one}).question_id.iloc[0])
    item = int(query_df("SELECT item_id FROM csi_item WHERE question_id = :q ORDER BY sort_order LIMIT 1",
                        {"q": target_multi}).item_id.iloc[0])
    adhoc = ({"kind": "profile", "dimension": "gender", "values": ["Female"]},
             {"kind": "item", "ids": [item]})

    checks = [
        ("standard view (cube, age-band break)", 1.0,
         lambda: uncached(repo.analyse)(one, question, (), "age_band")),
        ("ad-hoc cohort, one wave (engine)", 3.0,
         lambda: uncached(repo.analyse)(one, target_multi, adhoc, "generation")),
        (f"five-wave stack ({len(stack)} waves pooled)", 5.0,
         lambda: uncached(repo.concept_pooled)(concept, stack, None, "age_band")),
    ]
    missed = 0
    for name, target, action in checks:
        action()                                               # warm the connection pool
        times = timed(action, runs)
        worst = p95(times)
        ok = worst < target
        missed += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {name:42} P50 {statistics.median(times):5.2f}s  "
              f"P95 {worst:5.2f}s  (target < {target:.0f}s, {runs} runs)")
    return 1 if missed else 0


if __name__ == "__main__":
    sys.exit(main())
