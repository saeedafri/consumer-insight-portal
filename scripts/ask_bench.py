"""Ask CIP's test bench: thousands of questions generated from the published data, each checked against an answer
worked out here separately (plain loops over the raw question files, not api/ask_figures.py's code).

    python scripts/ask_bench.py                    # 10,000 questions, every kind, summary + the worst misses
    python scripts/ask_bench.py --count 1000 --seed 7 --show 40

Per question it checks: the survey question found (the target, or one with the same wording), the waves of each
period, and every figure of the answer the question names. It reports accuracy by how the question was worded and by
kind (share, count, top, trend by each grain, compare, by cut), speed (median, 95th percentile, slowest) and the
process's memory. The wordings go from easy (the survey's own text) to hard (a few topic words, a typo), so the
"about" accuracy shows what an analyst typing loosely would get. Run it after any change to api/ask_*.py.
"""
from __future__ import annotations

import argparse
import gzip
import json
import random
import re
import resource
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api import assistant  # noqa: E402
from api.ask_index import Index, stems  # noqa: E402

ROOT = Path(__file__).resolve().parents[1] / "data" / "published" / "current" / "api" / "v1"
GRAIN_WORDS = {"wave": "week by week", "biweek": "biweekly", "4week": "every 4 weeks", "month": "monthly",
               "quarter": "quarterly", "year": "yearly"}
SAME_QUESTION = 0.8   # shared words / all words: the same question reworded slightly under another code
CUT_WORDS = {"generation": "by generation", "gender": "by gender", "census_region": "by region", "income_band": "by income"}


def truth(raw: dict, waves: list[int], cut: tuple, answer: int) -> float | None:
    """people ÷ base for one answer over some waves and one cut, by plain loops over the published cells."""
    try:
        c = raw["cuts"].index(list(cut))
    except ValueError:
        return None
    people = base = 0
    for w, cc, a, n, b in zip(raw["w"], raw["c"], raw["a"], raw["n"], raw["b"]):
        if cc == c and a == answer and w in waves:
            if n is None:
                return None
            people, base = people + n, base + b
    return round(100 * people / base, 1) if base else None   # as every screen rounds


def typo(word: str, rng: random.Random) -> str:
    if len(word) < 6:
        return word
    i = rng.randrange(1, len(word) - 2)
    return word[:i] + word[i + 1] + word[i] + word[i + 2:]


def wordings(doc: dict, index: Index, rng: random.Random) -> dict[str, str]:
    """The question's subject said four ways: its own text, its rarest words, the rarest words plus a typo, and the
    rarest words with the answer named (filled in later)."""
    words = [w for w in dict.fromkeys(doc["text"].lower().replace("?", " ").split()) if len(w) > 3]
    rare = sorted(words, key=lambda w: -index.idf.get((stems(w) or [""])[0], 0))[:3]
    loose = " ".join(rare)
    return {"exact": doc["text"], "about": loose, "typo": " ".join(typo(w, rng) if i == 0 else w for i, w in enumerate(rare))}


def make(doc: dict, raw: dict, index: Index, rng: random.Random) -> dict | None:
    """One generated question with what a right answer must say."""
    versions = set(doc.get("versions") or range(1, 999))
    waves = [(i, w) for i, w in enumerate(raw["waves"]) if w[2] in versions and w[0] in index_waves]
    if not waves:
        return None
    dates = [w[1] for _, w in waves]
    labels = [f"{item}: {label}" if item and item != label else label for item, _, label in raw["answers"]]
    usable = [i for i, lab in enumerate(labels) if 3 <= len(lab) <= 60 and not assistant.SKIP.match(lab)
              and truth(raw, [waves[-1][0]], ("total", "Total"), i) is not None]
    if not usable:
        return None
    answer = rng.choice(usable)
    say = wordings(doc, index, rng)
    style = rng.choice(["exact", "about", "about", "typo", "named"])
    subject = say["about"] + " " + labels[answer] if style == "named" else say["exact" if style == "exact" else style]
    kinds = ["share", "count", "top"] + (["trend", "compare", "prior", "lastn", "month", "year"] if len(waves) > 1 else []) + ["cut"]
    kind = rng.choice(kinds)
    cut = ("total", "Total")
    named = labels[answer]
    if kind == "share":
        text, picked = f"what percentage chose {named} for {subject} in the latest wave", [[waves[-1][0]]]
    elif kind == "count":
        text, picked = f"how many people answered {named} to {subject} in the latest wave", [[waves[-1][0]]]
    elif kind == "top":
        text, picked = f"top answers for {subject} in the latest wave", [[waves[-1][0]]]
        named = None
    elif kind == "prior":
        text, picked = f"what share said {named} for {subject} in the previous wave", [[waves[-2][0]]]
    elif kind == "compare":
        text, picked = f"compare the first wave and the latest wave: {named} for {subject}", [[waves[0][0]], [waves[-1][0]]]
    elif kind == "lastn":
        n = rng.choice([2, 4, 8])
        newest = date.fromisoformat(dates[-1])
        lo = str(newest - timedelta(days=7 * n - 1))
        text, picked = f"{named} for {subject} over the last {n} weeks", [[i for i, w in waves if w[1] >= lo]]
    elif kind == "month":
        month = rng.choice(sorted({d[:7] for d in dates}))
        name = date.fromisoformat(month + "-01").strftime("%B %Y")
        text, picked = f"{named} for {subject} in {name}", [[i for i, w in waves if w[1][:7] == month]]
    elif kind == "year":
        year = rng.choice(sorted({d[:4] for d in dates}))
        text, picked = f"{named} for {subject} in {year}", [[i for i, w in waves if w[1][:4] == year]]
    elif kind == "cut":
        present = [tuple(c) for c in raw["cuts"] if c[0] in CUT_WORDS]
        if not present:
            return None
        cut = rng.choice(present)
        text, picked = f"{named} for {subject} {CUT_WORDS[cut[0]]} in the latest wave", [[waves[-1][0]]]
    else:   # trend at a grain
        grain = rng.choice(list(GRAIN_WORDS))
        text = f"{named} for {subject} {GRAIN_WORDS[grain]} over all waves"
        picked = None   # the series' grouping is checked by its first and last period's figures
        kind = f"trend:{grain}"
    expect = [truth(raw, p, cut, answer) for p in picked] if picked else None
    return {"text": text, "key": doc["key"], "doc_text": doc["text"], "style": style, "kind": kind, "answer": labels[answer],
            "named": named, "cut": cut, "expect": expect, "waves": [[raw["waves"][i][0] for i in p] for p in picked] if picked else None}


def check(case: dict, found: dict, raw: dict) -> tuple[bool, bool, str]:
    """(found the right question, figures right, why not). A question with the same wording elsewhere counts as found;
    its figures are checked only when it is the very question asked about."""
    if found["mode"] != "figures":
        return False, False, "no answer"
    source = found["sources"][0]
    if source["key"] != case["key"]:   # the same question under another code (Q14 → G3) or family counts as found
        a, b = (set(re.findall(r"[a-z0-9]+", t.lower())) for t in (source["question"], case["doc_text"]))
        same = len(a & b) / max(len(a | b), 1) >= SAME_QUESTION
        return same, same, "" if same else f"found {source['qcode']}: {source['question'][:80]}"
    table = found["table"]
    if case["kind"] == "top":   # the first answer listed must be the biggest, at its true figure
        row = table["rows"][0] if table["rows"] else None
        labels = [f"{item}: {label}" if item and item != label else label for item, _, label in raw["answers"]]
        if row is None or row[0] not in labels:
            return True, False, "no top answer"
        want = truth(raw, case["waves"][0] and [i for i, w in enumerate(raw["waves"]) if w[0] in case["waves"][0]], ("total", "Total"), labels.index(row[0]))
        return True, row[1] is not None and want is not None and abs(row[1] - want) < 0.051, f"top {row} vs {want}"
    row = next((r for r in table["rows"] if r[0] == case["answer"]), None)
    if row is None:
        return True, False, "answer not in table"
    if case["expect"] is None:
        return True, any(v is not None for v in row[1:]), "trend has no figures"
    columns = len(found["table"]["head"]) - 1
    if case["cut"] != ("total", "Total"):
        heads = found["table"]["head"][1:]
        at = [i for i, h in enumerate(heads) if h.endswith(f"· {case['cut'][1]}")]
        values = [row[1 + i] for i in at]
    else:
        values = row[1:1 + columns]
    want = [e for e in case["expect"]]
    ok = len(values) == len(want) and all((v is None and w is None) or (v is not None and w is not None and abs(v - w) < 0.051)
                                          for v, w in zip(values, want))
    return True, ok, "" if ok else f"figures {values} != {want}"


index_waves: set[int] = set()
RAWS: dict[str, dict] = {}


def raws_for(key: str, index: Index) -> dict:
    file = index.docs[key]["file"]
    if file not in RAWS:
        RAWS[file] = json.loads(gzip.decompress((ROOT / "questions" / f"{file}.json.gz").read_bytes()))
    return RAWS[file]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--count", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--show", type=int, default=25)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    waves = json.loads(gzip.decompress((ROOT / "waves.json.gz").read_bytes()))
    index_waves.update(w["survey_id"] for w in waves)
    started = time.perf_counter()
    index = Index(ROOT / "questions", waves)
    built = time.perf_counter() - started
    raws = RAWS
    docs = list(index.docs.values())
    cases = []
    while len(cases) < args.count:
        doc = rng.choice(docs)
        raw = raws.get(doc["file"]) or raws.setdefault(doc["file"], json.loads(gzip.decompress((ROOT / "questions" / f"{doc['file']}.json.gz").read_bytes())))
        case = make(doc, raw, index, rng)
        if case:
            cases.append(case)
    visible = set(index_waves)
    times, by_style, by_kind, misses = [], defaultdict(Counter), defaultdict(Counter), []
    for case in cases:
        t = time.perf_counter()
        found = assistant.answer(case["text"], index, visible)
        times.append((time.perf_counter() - t) * 1000)
        q_ok, f_ok, why = check(case, found, raws_for(case["key"], index))
        for table, key in ((by_style, case["style"]), (by_kind, case["kind"])):
            table[key]["asked"] += 1
            table[key]["question"] += q_ok
            table[key]["figures"] += f_ok
            table[key]["top5"] += q_ok or any(s["key"] == case["key"] for s in found.get("suggestions", []))
        if not f_ok:
            misses.append((case["style"], case["kind"], case["text"][:140], why))
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (2**20 if sys.platform == "darwin" else 2**10)
    times.sort()
    print(f"Index: {len(index.docs):,} questions built in {built:.2f} s · {len(cases):,} questions asked")
    print(f"Speed: median {statistics.median(times):.1f} ms · 95th percentile {times[int(len(times) * .95)]:.1f} ms · "
          f"slowest {times[-1]:.1f} ms · peak memory {rss:.0f} MB (this whole process)")
    for title, table in (("By wording", by_style), ("By kind", by_kind)):
        print(f"\n{title:<18}{'asked':>7}{'right question':>16}{'in first 5 shown':>18}{'right figures':>15}")
        for key, c in sorted(table.items()):
            print(f"{key:<18}{c['asked']:>7}{100 * c['question'] / c['asked']:>15.1f}%{100 * c['top5'] / c['asked']:>17.1f}%"
                  f"{100 * c['figures'] / c['asked']:>14.1f}%")
    total = Counter()
    for c in by_kind.values():
        total.update(c)
    print(f"\n{'All':<18}{total['asked']:>7}{100 * total['question'] / total['asked']:>15.1f}%"
          f"{100 * total['top5'] / total['asked']:>17.1f}%{100 * total['figures'] / total['asked']:>14.1f}%")
    print(f"\nMisses ({len(misses):,}), a sample:")
    for style, kind, text, why in rng.sample(misses, min(args.show, len(misses))):
        print(f"  [{style}/{kind}] {text}\n      → {why}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
