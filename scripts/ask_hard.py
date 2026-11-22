"""Scores Ask CIP on its hard test set (scripts/ask_hard.yml): multi-step analyst questions with figures worked out from
the raw weekly files by scripts/ask_hard_truth.py.

A case is right when Ask read the right survey question and every expected figure (and, for a test, the change in
points) appears in its answer, points or table, to one decimal; a refusal case is right when Ask gives no figures. It also says whether Ask read the right
survey questions (the plan's codes among the answer's sources). Results are split by what each case combines (`parts`),
so a gap shows where it is. Run by hand before and after any change to Ask's reading (step 1 of the Ask rebuild):
    python scripts/ask_hard.py [--published data/published/current/api/v1] [--out results.json]
"""
import argparse
import gzip
import json
import logging
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
logging.disable(logging.WARNING)
from api import ask_index, assistant  # noqa: E402


def said(found: dict) -> set[str]:
    """Every figure the answer shows, as one-decimal text: its sentences and its table."""
    text = " ".join(str(found.get(k) or "") for k in ("headline", "answer", "takeaway")) + " " + " ".join(found.get("points") or [])
    shown = {f"{float(x):.1f}" for x in re.findall(r"-?\d+(?:\.\d+)?", text.replace(",", ""))}
    for cells in (found.get("table") or {}).get("rows", []):
        shown |= {f"{float(c):.1f}" for c in cells[1:] if isinstance(c, (int, float))}
    return shown


DEMOGRAPHICS = {"D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8"}   # gender, age, … state: groups, not what is asked


def codes(plan: dict) -> set[str]:
    """The survey question codes a plan reads (ask, among, groups, steps), not demographics."""
    found = set()

    def walk(node):
        if isinstance(node, dict):
            if "q" in node and node["q"] not in DEMOGRAPHICS:
                found.add(str(node["q"]).upper())
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
    walk({k: v for k, v in plan.items() if k != "by"})
    return found


def score(case: dict, found: dict) -> dict:
    if "refuse" in case:
        right = found.get("mode") != "figures"
        return {"right": right, "share": float(right), "pick": None}
    wanted = [f"{r['pct']:.1f}" for r in case["expect"] if r.get("pct") is not None]
    wanted += [f"{r['points']:.1f}" for r in case["expect"] if "points" in r]
    shown = said(found) if found.get("mode") == "figures" else set()
    got = sum(w in shown for w in wanted)
    picked = {s.get("qcode", "").upper() for s in found.get("sources") or []}
    pick = bool(codes(case["plan"]) & picked) if codes(case["plan"]) else None   # a demographic breakdown has no code to read
    # a figure found in a table of the wrong question is luck, not an answer (a grid's other row matched once)
    return {"right": bool(wanted) and got == len(wanted) and pick is not False, "share": got / len(wanted) if wanted else 0.0,
            "pick": pick}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--published", type=Path, default=ROOT / "data" / "published" / "current" / "api" / "v1")
    ap.add_argument("--cases", type=Path, default=ROOT / "scripts" / "ask_hard.yml")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    waves = json.loads(gzip.decompress((args.published / "waves.json.gz").read_bytes()))
    index = ask_index.Index(args.published / "questions", waves)
    index.add_vectors()
    visible = {w["survey_id"] for w in waves}
    results, by_part, times = [], defaultdict(lambda: [0, 0]), []
    for case in yaml.safe_load(args.cases.read_text()):
        started = time.perf_counter()
        found = assistant.answer(case["question"], index, visible, True)
        times.append(time.perf_counter() - started)
        result = {"id": case["id"], "question": case["question"], **score(case, found), "mode": found.get("mode"),
                  "said": (found.get("headline") or found.get("answer") or "")[:240]}
        results.append(result)
        for part in case.get("parts", []):
            by_part[part][0] += result["right"]
            by_part[part][1] += 1
    right = sum(r["right"] for r in results)
    picks = [r["pick"] for r in results if r["pick"] is not None]
    times.sort()
    print(f"{right} of {len(results)} right ({right / len(results):.0%}); figures found {sum(r['share'] for r in results) / len(results):.0%}; "
          f"right question read {sum(picks)} of {len(picks)}; median {times[len(times) // 2] * 1000:.0f} ms, slowest {times[-1] * 1000:.0f} ms")
    for part, (good, total) in sorted(by_part.items(), key=lambda x: -x[1][1]):
        print(f"  {part:16} {good:3} of {total:3}")
    if args.out:
        args.out.write_text(json.dumps(results, indent=1))


if __name__ == "__main__":
    main()
