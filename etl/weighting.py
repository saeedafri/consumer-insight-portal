"""Census weighting: one weight per qualified respondent of a wave, raked to US adult shares (config/weighting.yml).

Raking (iterative proportional fitting) adjusts the weights margin by margin (gender, then age, then region) until
each matches its Census share, repeating until nothing moves. A respondent with no value on a margin is left out of
that margin. Weights are then trimmed so no one counts more than trim_high (or less than trim_low) times the
average, and rescaled so they average 1: the weighted base of a wave equals its respondent count. Trimming comes
last, so a hard-to-reach group can stay a little short of its share.

Weighted figures are an alternative view: the portal shows unweighted by default, matching Forsta and the team's
Excel files, and the significance flags are always tested on the unweighted counts.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from sqlalchemy import text

TARGETS = Path(__file__).resolve().parents[1] / "config" / "weighting.yml"


@lru_cache(maxsize=1)
def targets() -> dict:
    return yaml.safe_load(TARGETS.read_text())


def rake(people: dict[int, dict], margins: dict, trim: tuple[float, float] = (0.2, 5.0), rounds: int = 50) -> dict[int, float]:
    """{respondent: {margin: value}} → {respondent: weight}, averaging 1."""
    weights = {rid: 1.0 for rid in people}
    if not weights:
        return weights
    for _ in range(rounds):
        moved = 0.0
        for margin, shares in margins.items():
            known = [rid for rid, p in people.items() if p.get(margin) in shares]
            # a margin covers only its groups that have someone in this wave: their shares are rescaled to 100 %
            present = {v: s for v, s in shares.items() if any(people[rid][margin] == v for rid in known)}
            if not present:
                continue
            total = sum(weights[rid] for rid in known)
            scale = sum(present.values())
            have = {v: 0.0 for v in present}
            for rid in known:
                have[people[rid][margin]] += weights[rid]
            for rid in known:
                factor = present[people[rid][margin]] / scale * total / have[people[rid][margin]]
                moved = max(moved, abs(factor - 1))
                weights[rid] *= factor
        if moved < 1e-6:
            break
    low, high = trim
    for _ in range(rounds):   # trim, rescale to average 1, again until every weight sits inside the bounds
        mean = sum(weights.values()) / len(weights)
        weights = {rid: w / mean for rid, w in weights.items()}
        if all(low - 1e-9 <= w <= high + 1e-9 for w in weights.values()):
            break
        weights = {rid: min(max(w, low), high) for rid, w in weights.items()}
    return weights


def wave_weights(conn, survey_id: int) -> dict[int, float]:
    """The wave's qualified respondents and their Census weights."""
    config = targets()
    margins = config["margins"]
    rows = conn.execute(text(
        f"SELECT r.respondent_id, {', '.join(f'p.{m}' for m in margins)} FROM cip_respondent r"
        " LEFT JOIN cip_profile p ON p.respondent_id = r.respondent_id WHERE r.survey_id = :s AND r.is_qualified = 1"),
        {"s": survey_id}).all()
    people = {r[0]: dict(zip(margins, r[1:])) for r in rows}
    return rake(people, margins, (config["trim_low"], config["trim_high"]))
