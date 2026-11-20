"""Ask CIP's golden test: the questions in scripts/ask_golden.yml, run through the whole pipeline
(api/assistant.py: retrieval, the model when OPENAPI_KEY is set, the figures), each scored step by step.

    python scripts/ask_golden.py              # every question, a line each, then the score per step and the model spend
    python scripts/ask_golden.py --only 20    # the first 20 (a quick check)
    python scripts/ask_golden.py --quick      # the Ask page's first answer: by meaning and rules, no model
    python scripts/ask_golden.py --questions scripts/ask_fresh.yml   # the fresh test: real staging questions, never tuned on
    python scripts/ask_golden.py --strict --questions exact.yml --published snapshot/api/v1

Strict cases have q and expect.mode (figures, choose or none). A figures case also needs expect.source
with qcode and survey_id, expect.scope with country and any other expected plan fields, and expect.cells
with one or more {column, answer, share, base} entries. Author these independently from the expected survey
results. Optional visible_survey_ids restricts the waves the case can use. Strict mode uses the local quick path.

Run before every push to staging, after any change to api/ask_*.py, the model prompt or config/ask_semantic.json.
A repeat costs nothing: the model's readings are kept in logs/ask-readings.json.
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

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


def check_evidence(item: dict) -> None:
    """Reject underspecified strict fixtures before scoring or opening the publication."""
    expected = item.get("expect") if isinstance(item, dict) else None
    if not isinstance(expected, dict) or expected.get("mode") not in ("figures", "choose", "none"):
        raise ValueError("expect.mode must be figures, choose or none")
    if not isinstance(item.get("q"), str) or not item["q"].strip():
        raise ValueError("q must be a nonempty question")
    if "visible_survey_ids" in item and (not isinstance(item["visible_survey_ids"], list) or any(
        type(survey_id) is not int or survey_id <= 0 for survey_id in item["visible_survey_ids"]
    )):
        raise ValueError("visible_survey_ids must be a list of positive integers")
    if expected["mode"] != "figures":
        if set(expected) != {"mode"}:
            raise ValueError("choose and none cases take only expect.mode")
        return
    source, scope, cells = (expected.get(key) for key in ("source", "scope", "cells"))
    if not isinstance(source, dict) or not isinstance(source.get("qcode"), str) or not source["qcode"].strip() \
            or type(source.get("survey_id")) is not int or source["survey_id"] <= 0:
        raise ValueError("expect.source needs qcode and a positive survey_id")
    if not isinstance(scope, dict) or not isinstance(scope.get("country"), str) or not scope["country"].strip():
        raise ValueError("expect.scope needs country")
    if not isinstance(cells, list) or not cells:
        raise ValueError("expect.cells needs at least one expected answer cell")
    seen = set()
    for cell in cells:
        if not isinstance(cell, dict) or set(cell) != {"column", "answer", "share", "base"} or any(
            not isinstance(cell[key], str) or not cell[key].strip() for key in ("column", "answer")
        ):
            raise ValueError("each expected cell needs a column heading, answer label, share and base")
        share, base = cell["share"], cell["base"]
        if (share is not None or base is not None) and (
            type(share) not in (int, float) or not 0 <= share <= 100 or type(base) is not int or base <= 0
        ):
            raise ValueError("expected share and base must be a percentage and a positive count, or both null")
        identity = (cell["column"], cell["answer"])
        if identity in seen:
            raise ValueError(f"duplicate expected cell {identity}")
        seen.add(identity)


def score_exact(expected: dict, found: dict, visible: set[int]) -> list[str]:
    """Compare the decision, selected source and plan, and independently specified table cells."""
    mode = found.get("mode")
    if mode != expected["mode"]:
        return [f"mode {mode!r}, expected {expected['mode']!r}"]
    sources = found.get("sources") or []
    if mode != "figures":
        return ["non-figure reply has sources or a figure table"] if sources or found.get("table") else []
    if not sources:
        return ["no figure source"]
    problems = ["source is outside the case's visible waves"] if any(s.get("survey_id") not in visible for s in sources) else []
    plan = found.get("plan") or {}
    for name, actual, wanted in (("source", sources[0], expected["source"]), ("scope", plan, expected["scope"])):
        for key, value in wanted.items():
            if key not in actual or actual[key] != value:
                problems.append(f"{name}.{key} {actual.get(key)!r}, expected {value!r}")

    table = found.get("table") or {}
    headings = table.get("head", [])[1:]
    rows = table.get("rows", [])
    bases = table.get("cell_bases", [])
    if len(rows) != len(bases) or any(len(row) != len(headings) + 1 or len(base_row) != len(headings)
                                    for row, base_row in zip(rows, bases)):
        return [*problems, "invalid table or missing per-cell bases"]
    for cell in expected["cells"]:
        column, answer = cell["column"], cell["answer"]
        matching_rows = [i for i, row in enumerate(rows) if row[0] == answer]
        if len(matching_rows) != 1 or headings.count(column) != 1:
            problems.append(f"no unique table cell for {answer!r} under {column!r}")
            continue
        row, col = matching_rows[0], headings.index(column)
        share, base = rows[row][col + 1], bases[row][col]
        wanted_share = cell["share"]
        share_matches = share is None if wanted_share is None else (
            type(share) in (int, float) and math.isclose(share, wanted_share, rel_tol=0, abs_tol=1e-9)
        )
        if not share_matches or type(base) is not type(cell["base"]) or base != cell["base"]:
            problems.append(f"{answer!r} under {column!r} has share/base {share!r}/{base!r}, expected {wanted_share!r}/{cell['base']!r}")
    return problems


def add_isolated_vectors(index) -> None:
    """Reuse model vectors without letting a fixture prune the portal's vector cache."""
    from api import ask_model

    original_cache = ask_model.VECTORS
    with tempfile.TemporaryDirectory(prefix="cip-ask-eval-") as folder:
        ask_model.VECTORS = Path(folder) / original_cache.name
        try:
            if original_cache.is_file():
                shutil.copyfile(original_cache, ask_model.VECTORS)
            index.add_vectors()
        finally:
            ask_model.VECTORS = original_cache


def main() -> int:
    """Run the selected cases and fail the process when a strict regression is found."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--only", type=int, default=0)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--strict", action="store_true", help="require independent exact evidence for every case and use only the local quick path")
    ap.add_argument("--questions", type=Path, default=GOLDEN, help="another question file in the same format (scripts/ask_fresh.yml)")
    ap.add_argument("--published", type=Path, default=PUBLISHED, help="another publish's api/v1 (staging's data, built with etl.publish --root)")
    args = ap.parse_args()
    loaded = yaml.safe_load(args.questions.read_text())
    if not isinstance(loaded, list) or not loaded or args.only < 0:
        ap.error("expected a nonempty list of questions and a nonnegative --only limit")
    golden = loaded[:args.only or None]
    if args.strict:
        for number, item in enumerate(golden, start=1):
            try:
                check_evidence(item)
            except ValueError as exc:
                ap.error(f"case {number}: {exc}")
        if __name__ == "__main__":
            os.environ["PYTHON_DOTENV_DISABLED"] = "1"
    elif not args.quick and not os.environ.get("OPENAPI_KEY") and (ROOT / ".env").exists():
        for line in (ROOT / ".env").read_text().splitlines():
            if line.startswith("OPENAPI_KEY="):
                os.environ["OPENAPI_KEY"] = line.split("=", 1)[1].strip().strip("'\"")
                break
    from api import ask_model, assistant
    from api.ask_index import Index

    quick = args.quick or args.strict
    waves = json.loads(gzip.decompress((args.published / "waves.json.gz").read_bytes()))
    visible = {w["survey_id"] for w in waves}
    if args.strict:
        for number, item in enumerate(golden, start=1):
            unknown = set(item.get("visible_survey_ids", ())) - visible
            if unknown:
                ap.error(f"case {number}: visible_survey_ids includes unpublished IDs {sorted(unknown)}")
    index = Index(args.published / "questions", waves)
    if args.strict:
        add_isolated_vectors(index)
    else:
        index.add_vectors()
    print(f"Model {'off (quick)' if quick else 'on (' + ask_model.model() + ')' if ask_model.ready() else 'off (rules only)'} · {len(golden)} questions\n")
    countries = {w["survey_id"]: w.get("country") or "US" for w in waves}
    before = ask_model.spent()["usd"]
    right, times = 0, []
    for item in golden:
        started = time.perf_counter()
        shown = set(item["visible_survey_ids"]) if args.strict and "visible_survey_ids" in item else visible
        found = assistant.answer(item["q"], index, shown, quick)
        times.append(time.perf_counter() - started)
        problems = score_exact(item["expect"], found, shown) if args.strict else score(item, found, countries)
        right += not problems
        code = found["sources"][0]["qcode"] if found["sources"] else "-"
        print(f"{'ok  ' if not problems else 'MISS'} {times[-1]:4.1f}s {item['q'][:60]:<60} → {code:<6} {found.get('understood', '-'):<8} {'; '.join(problems)}")
    print(f"\n{right} of {len(golden)} right ({right / len(golden):.0%}) · median {sorted(times)[len(times) // 2]:.3f} s, "
          f"slowest {max(times):.3f} s · "
          f"model spend this run ${ask_model.spent()['usd'] - before:.4f}")
    return int(args.strict and right != len(golden))


if __name__ == "__main__":
    sys.exit(main())
