"""Ask Coresight's golden test: the questions in scripts/ask_golden.yml, run through the whole pipeline
(api/assistant.py: retrieval, the model when OPENAPI_KEY is set, the figures), each scored step by step.

    python scripts/ask_golden.py              # every question, a line each, then the score per step and the model spend
    python scripts/ask_golden.py --only 20    # the first 20 (a quick check)
    python scripts/ask_golden.py --quick      # the Ask page's first answer: by meaning and rules, no model
    python scripts/ask_golden.py --questions scripts/ask_fresh.yml   # the fresh test: real staging questions, never tuned on

Run before every push to staging, after any change to api/ask_*.py, the model prompt or config/ask_semantic.json.
A repeat costs nothing: the model's readings are kept in logs/ask-readings.json.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for line in (ROOT / ".env").read_text().splitlines() if (ROOT / ".env").exists() else []:
    if line.startswith("OPENAPI_KEY=") and not os.environ.get("OPENAPI_KEY"):
        os.environ["OPENAPI_KEY"] = line.split("=", 1)[1].strip().strip("'\"")

from api import ask_model, assistant  # noqa: E402
from api.ask_index import Index  # noqa: E402

PUBLISHED = ROOT / "data" / "published" / "current" / "api" / "v1"
GOLDEN = ROOT / "scripts" / "ask_golden.yml"


def score(item: dict, found: dict, countries: dict) -> list[str]:
    """What is wrong with one answer (empty when right): the country, the question found, a figure, a chart, the check."""
    if item["want"] == "none":
        return [] if found["mode"] != "figures" else [f"answered from {found['sources'][0]['qcode']}"]   # "choose" is not an answer either
    if found["mode"] != "figures":
        return ["no answer"]
    text = found["sources"][0]["question"].lower()
    problems = [] if any(w in text for w in item["want"]) else [f"wrong question: {text[:70]}"]
    country = countries.get(found["sources"][0]["survey_id"], "US")
    if country != item.get("country", "US"):   # a US question answered from China's waves, or the other way round
        problems.append(f"{country} survey")
    if not found.get("chart"):
        problems.append("no chart")
    check = item.get("check")
    if check == "trend" and found["chart"]["type"] != "line":
        problems.append("no trend")
    if check == "cut" and len(found["chart"]["series"]) < 2 and "among" not in found["headline"]:
        problems.append("cut not shown")
    if check == "top" and len(found["chart"]["categories"]) < 3:
        problems.append("no ranked list")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--only", type=int, default=0)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--questions", type=Path, default=GOLDEN, help="another question file in the same format (scripts/ask_fresh.yml)")
    ap.add_argument("--published", type=Path, default=PUBLISHED, help="another publish's api/v1 (staging's data, built with etl.publish --root)")
    args = ap.parse_args()
    golden = yaml.safe_load(args.questions.read_text())[:args.only or None]
    waves = json.loads(gzip.decompress((args.published / "waves.json.gz").read_bytes()))
    index = Index(args.published / "questions", waves)
    index.add_vectors()
    print(f"Model {'off (quick)' if args.quick else 'on (' + ask_model.model() + ')' if ask_model.ready() else 'off (rules only)'} · {len(golden)} questions\n")
    visible = {w["survey_id"] for w in waves}
    countries = {w["survey_id"]: w.get("country") or "US" for w in waves}
    before = ask_model.spent()["usd"]
    right, times = 0, []
    for item in golden:
        started = time.perf_counter()
        found = assistant.answer(item["q"], index, visible, args.quick)
        times.append(time.perf_counter() - started)
        problems = score(item, found, countries)
        right += not problems
        code = found["sources"][0]["qcode"] if found["sources"] else "-"
        print(f"{'ok  ' if not problems else 'MISS'} {times[-1]:4.1f}s {item['q'][:60]:<60} → {code:<6} {found.get('understood', '-'):<8} {'; '.join(problems)}")
    print(f"\n{right} of {len(golden)} right ({right / len(golden):.0%}) · median {sorted(times)[len(times) // 2]:.3f} s, "
          f"slowest {max(times):.3f} s · "
          f"model spend this run ${ask_model.spent()['usd'] - before:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
