"""Ask Coresight's analyst test: questions worded the way analysts type them, each with the survey questions that answer
it, run through the whole pipeline (api/assistant.py: retrieval, the model when OPENAPI_KEY is set, the figures).

    python scripts/ask_analyst_test.py              # every question, a line each, then the score and the model spend

Checks per question: the survey question found is one of the right ones; there is a figure; there is a chart; a question
asking for a trend gets one over more than one period; a cut asked for is shown; nothing matches a question no survey
asks. Run against data/published/current (the local copy) after any change to api/ask_*.py or the model prompt.
"""
from __future__ import annotations

import gzip
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
for line in (Path(__file__).resolve().parents[1] / ".env").read_text().splitlines() if (Path(__file__).resolve().parents[1] / ".env").exists() else []:
    if line.startswith(("OPENAPI_KEY=", "OPENAI_API_KEY=")) and not os.environ.get(line.split("=")[0]):
        os.environ[line.split("=")[0]] = line.split("=", 1)[1].strip().strip("'\"")

from api import ask_model, assistant  # noqa: E402
from api.ask_index import Index  # noqa: E402

ROOT = Path(__file__).resolve().parents[1] / "data" / "published" / "current" / "api" / "v1"
NONE = None   # no survey asks it: the answer must say so
# (question, codes that answer it, what else to check: trend / cut:<dim> / none)
QUESTIONS = [
    ("What share bought from Amazon in the latest wave?", {"q5", "q4"}, ""),
    ("What share bought from Amazon in all waves?", {"q5", "q4"}, "trend"),
    ("How many people have subscribed to Amazon Prime?", {"EC6", "BD5", "G22", "Q17"}, ""),
    ("Amazon Prime membership over time", {"EC6", "BD5", "G22", "Q17"}, "trend"),
    ("Walmart shoppers over time", {"q5", "q4"}, "trend"),
    ("Top food retailers last 8 weeks", {"q4"}, ""),
    ("Top nonfood retailers this week", {"q5"}, ""),
    ("Which retailers do Gen Z prefer?", {"q5", "q4", "AP4", "AP3"}, "cut:generation"),
    ("Target food shoppers by income", {"q4"}, "cut:income_band"),
    ("Walmart vs Target nonfood shoppers by generation", {"q5"}, "cut:generation"),
    ("Costco shoppers", {"q5", "q4", "M1"}, ""),
    ("Dollar General shoppers monthly", {"q5", "q4"}, "trend"),
    ("What did people buy online last month?", {"q3"}, ""),
    ("What categories are people buying in store?", {"q2"}, ""),
    ("Online grocery buying trend", {"q3", "G4", "G1", "G2"}, "trend"),
    ("What activities have people done in the past two weeks?", {"q1"}, ""),
    ("How many people went to a restaurant recently?", {"q1"}, ""),
    ("Dining out trend by quarter", {"q1"}, "trend"),
    ("How is consumer confidence trending?", {"CS2", "CS1"}, "trend"),
    ("Do people expect their finances to get better or worse?", {"CS1"}, ""),
    ("Economy outlook every 4 weeks", {"CS2"}, "trend"),
    ("Personal finances outlook by income", {"CS1"}, "cut:income_band"),
    ("What share of people use GenAI?", {"G3", "G6", "D31", "G1", "D24", "D25", "G2", "G5"}, ""),
    ("GenAI use for shopping, monthly", {"D31", "G6A"}, "trend"),
    ("Have people heard of AI?", {"G1"}, ""),
    ("What worries people about GenAI?", {"G8", "D27", "Q19", "Q18", "Q22"}, ""),
    ("Do younger people use GenAI more?", {"G6", "G3", "D31", "G6A", "G1"}, "cut:generation"),
    ("How many people take GLP-1 drugs?", {"GP1"}, ""),
    ("How has GLP-1 usage changed monthly", {"GP1"}, "trend"),
    ("Why do people take GLP-1 medication?", {"GP2"}, ""),
    ("How worried are people about tariffs?", {"TF3", "T3"}, ""),
    ("What impact do tariffs have on people personally?", {"TF1", "T1"}, ""),
    ("Have people changed shopping to avoid tariffs?", {"TF5", "TF6"}, ""),
    ("Tariff impact on the economy yearly", {"TF2", "T2"}, "trend"),
    ("Holiday shopping progress by generation", {"XM3"}, "cut:generation"),
    ("What share of women started holiday shopping", {"XM3"}, "cut:gender"),
    ("Compare the first and latest wave of holiday shopping progress", {"XM3"}, ""),
    ("Top holiday retailers", {"XM2"}, ""),
    ("What are people buying for the holidays?", {"XM1A", "XM1"}, ""),
    ("Did people shop on Black Friday?", {"BFR1", "BF1"}, ""),
    ("Black Friday shopping plans", {"BF1", "BF2", "BF3"}, ""),
    ("Did people buy from Amazon during Big Deal Days?", {"BD2", "BD1"}, ""),
    ("Prime Day purchases", {"PDR1", "APR1", "PD1", "PDR2", "APR3", "PDR4"}, ""),
    ("How are gas prices affecting spending?", {"D15", "D14"}, ""),
    ("Gas price impact trend in 2026", {"D15", "D14"}, "trend"),
    ("Who bought beauty products in the past three months?", {"BT1"}, ""),
    ("Top beauty retailers", {"BT13"}, ""),
    ("Clothing purchase rate", {"AP1"}, ""),
    ("Which apparel retailers do people buy from?", {"AP3"}, ""),
    ("Warehouse club shoppers", {"M1"}, ""),
    ("Social media platforms used for shopping", {"SC2", "SC5"}, ""),
    ("Department store shoppers", {"DP1", "DP2"}, ""),
    ("Dollar store shoppers", {"DS1", "DS2"}, ""),
    ("Holiday spending expectations", {"HX1", "HX2", "SP1", "HX3", "HX4"}, ""),
    ("Expected holiday financial situation", {"HX5"}, ""),
    ("Amazon in 2025 vs 2026", {"q5", "q4"}, ""),
    ("Walmart in October 2026", {"q5", "q4"}, ""),
    ("How many people own a submarine?", NONE, "none"),
    ("Bitcoin investments", NONE, "none"),
    ("What is the capital of France?", NONE, "none"),
]


def main() -> int:
    waves = json.loads(gzip.decompress((ROOT / "waves.json.gz").read_bytes()))
    started = time.perf_counter()
    index = Index(ROOT / "questions", waves)
    print(f"Index: {len(index.docs):,} questions in {time.perf_counter() - started:.1f} s · model "
          f"{'on (' + ask_model.model() + ')' if ask_model.ready() else 'off (rules only)'}\n")
    visible = {w["survey_id"] for w in waves}
    before = ask_model.spent()["usd"]
    right = 0
    times = []
    for question, codes, check in QUESTIONS:
        t = time.perf_counter()
        found = assistant.answer(question, index, visible)
        times.append(time.perf_counter() - t)
        source = found["sources"][0] if found["sources"] else {}
        got = set(found.get("codes") or ([source["qcode"]] if source else []))
        problems = []
        if codes is NONE:
            if found["mode"] != "none":
                problems.append(f"answered from {source.get('qcode')}")
        else:
            if not got & codes:
                problems.append(f"question {source.get('qcode', '-')} not in {sorted(codes)}")
            if found["mode"] != "figures" or "%" not in (found.get("headline") or ""):
                problems.append("no figure")
            if not found.get("chart"):
                problems.append("no chart")
            if check == "trend" and (not found.get("chart") or found["chart"]["type"] != "line"):
                problems.append("no trend")
            if check.startswith("cut:") and not any(len(found.get("table", {}).get("head", [])) > 2 for _ in [0]) and "among" not in (found.get("headline") or "") and "By " not in found["answer"]:
                problems.append("cut not shown")
        right += not problems
        mark = "ok " if not problems else "MISS"
        print(f"{mark} {times[-1]:4.1f}s {question[:62]:<62} → {source.get('qcode', '-'):<6} "
              f"{(found['chart'] or {}).get('type', '-'):<7} {'; '.join(problems)}")
    print(f"\n{right} of {len(QUESTIONS)} right · median {sorted(times)[len(times) // 2]:.1f} s · "
          f"model spend this run ${ask_model.spent()['usd'] - before:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
