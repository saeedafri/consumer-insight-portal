"""Ask Coresight's question bank: about 10,000 questions an analyst, a portal user or a client might type, each written
from one real survey question in the published catalogue, so its right answer is known before it is asked.

    python scripts/ask_question_bank.py --published <api/v1>            # write the bank, then score Ask against all of it
    python scripts/ask_question_bank.py --published <api/v1> --no-score # only write the bank

Written to docs/research/ask-question-bank.csv (one row a question: who asks it, what for, the survey question that
answers it, and, once scored, what Ask answered and how long it took). Who asks what comes from the research in
docs/research/ask-question-bank.md. Run by hand when the catalogue or Ask changes; it is the large test behind
scripts/ask_golden.py, and the list a verified-answer table (exact wording answered at once) would be built from.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from api import assistant  # noqa: E402
from api.ask_index import Index  # noqa: E402

OUT = ROOT / "docs" / "research" / "ask-question-bank.csv"
SEASONS = ["back-to-school", "black friday", "cyber monday", "christmas", "holiday", "thanksgiving", "halloween", "easter",
           "valentine", "mother's day", "father's day", "prime day", "super bowl", "memorial day", "fourth of july", "summer"]
# (persona, purpose, kind the answer must show, needs, wording). needs: trend = asked in 3+ waves, years = asked in two
# calendar years, top = 3+ answers, season = the question names a season. {n} the question's name, {l} its first answer.
TEMPLATES = [
    ("analyst", "latest figure", "latest", "", "{N}: latest wave, with the base"),
    ("analyst", "trend", "trend", "trend", "{N} trend, every wave since {since}"),
    ("analyst", "cut", "cut", "cut:generation", "{N} by generation"),
    ("analyst", "cut", "cut", "cut:income_band", "{N} by household income"),
    ("analyst", "cut", "cut", "cut:census_region", "{N} by region"),
    ("analyst", "cut", "cut", "cut:gender", "{N} by gender"),
    ("analyst", "cut", "cut", "cut:age_band", "{N} by age group"),
    ("analyst", "cut", "cut", "cut:urbanicity", "{N}: urban, suburban and rural"),
    ("analyst", "cut", "cut", "cut:generation", "{N} among Gen Z vs Boomers"),
    ("analyst", "cut", "cut", "cut:gender", "{N} among women"),
    ("analyst", "compare periods", "compare", "years", "{N}, {first} vs {last}"),
    ("analyst", "compare periods", "compare", "two", "{N}: latest vs previous wave"),
    ("analyst", "trend by grain", "trend", "trend", "{N} by quarter"),
    ("analyst", "trend by grain", "trend", "trend", "{N} by month"),
    ("analyst", "ranking", "top", "top", "Top answers for {n}"),
    ("analyst", "count", "latest", "answer", "How many people chose \u201c{l}\u201d for {n}?"),
    ("user", "latest figure", "latest", "", "What do consumers say about {n}?"),
    ("user", "latest figure", "latest", "", "Tell me about {n}"),
    ("user", "one answer", "latest", "answer", "What share chose \u201c{l}\u201d for {n}?"),
    ("user", "trend", "trend", "trend", "{N}: rising or falling?"),
    ("user", "season", "latest", "season", "{N} for {season} {last}"),
    ("user", "one year", "latest", "", "{N} in {last}"),
    ("client", "decision", "latest", "", "Should we act on {n}? Show the latest numbers"),
    ("client", "target audience", "cut", "cut:generation", "Which generation over-indexes on \u201c{l}\u201d for {n}?"),
    ("client", "target audience", "cut", "cut:gender", "Are women or men more likely to choose \u201c{l}\u201d for {n}?"),
    ("client", "target audience", "cut", "cut:census_region", "Is {n} different in the South vs the West?"),
    ("client", "momentum", "trend", "trend", "Has \u201c{l}\u201d grown since {since}?"),
    ("client", "year on year", "compare", "years", "How did {n} change from {first} to {last}?"),
]
NOT_AN_ANSWER = re.compile(r"\bother\b|don.t know|not sure|\bnone\b|prefer not|n/a", re.I)   # never the answer a question names
SAME_QUESTION = 0.6   # share of words in common (Jaccard) at which two studies asked the same question (IN2 and CSI-US grocery changes)


def fits(needs: str, doc: dict, season: str, label: str, cuts: set[str]) -> bool:
    """Whether a template makes sense for this survey question: the history, years, answers or cut it needs are there."""
    if needs.startswith("cut:"):
        return needs[4:] in cuts
    return {"": True, "trend": doc["waves"] >= 3, "two": doc["waves"] >= 2, "years": doc["first"][:4] != doc["last"][:4],
            "top": len(doc["labels"]) >= 3, "season": bool(season), "answer": bool(label)}[needs]


def build(index: Index) -> list[dict]:
    """The bank: every template that fits each survey question, then its eight paraphrases (config/ask_semantic.json asks,
    held out: the name table never sees them), distinct wording, each with the survey question that answers it."""
    rows, seen = [], set()
    for key, doc in sorted(index.docs.items()):
        name = (doc.get("name") or doc["text"][:80]).strip().rstrip("?.")
        text = f"{doc['text']} {name}".lower()
        season = next((s for s in SEASONS if s in text), "")
        label = next((a for a in (l.split(": ")[-1] for l in doc["labels"]) if not NOT_AN_ANSWER.search(a)), "")[:70]
        country = index.country.get(doc["surveys"][-1], "US")
        cuts = {c[0] for c in json.loads(gzip.decompress((index.root / f"{doc['file']}.json.gz").read_bytes()))["cuts"]}
        filled = [(persona, purpose, kind, wording.format(
            N=name[0].upper() + name[1:], n=name[0].lower() + name[1:], l=label, first=doc["first"][:4], last=doc["last"][:4],
            since=time.strftime("%b %Y", time.strptime(doc["first"], "%Y-%m-%d")), season=season))
            for persona, purpose, kind, needs, wording in TEMPLATES if fits(needs, doc, season, label, cuts)]
        filled += [("paraphrase", "held-out wording", "latest", ask.rstrip()) for ask in doc.get("asks", [])]
        for persona, purpose, kind, question in filled:
            question += " in China" if country == "CN" else ""
            if question.lower() in seen:
                continue
            seen.add(question.lower())
            rows.append({"question": question, "persona": persona, "purpose": purpose, "kind": kind, "country": country,
                         "season": season, "answer_key": key, "answer_question": doc["text"], "waves": doc["waves"]})
    return rows


def score(row: dict, found: dict, index: Index) -> str:
    """What is wrong with Ask's answer (empty when right): the survey question (its own or the same wording in another
    study counts), the country, and the shape the kind needs."""
    if found["mode"] != "figures":
        return "no answer"
    source = found["sources"][0]
    got = index.docs.get(source["key"], {})
    if source["key"] != row["answer_key"] and got.get("text", "").lower() != row["answer_question"].lower():
        mine, theirs = (set(re.findall(r"[a-z0-9]+", t.lower())) for t in (row["answer_question"], got.get("text", "")))
        if len(mine & theirs) / max(len(mine | theirs), 1) < SAME_QUESTION:
            return f"wrong question: {source['qcode']} {source['question'][:60]}"
        row["other_study"] = f"{got.get('family')} {source['qcode']}"   # the same question in another study: right, but which study is a choice
    if index.country.get(source["survey_id"], "US") != row["country"]:
        return "wrong country"
    chart = found.get("chart") or {}
    if row["kind"] == "trend" and chart.get("type") != "line":
        return "no trend"
    if row["kind"] == "cut" and len(chart.get("series", [])) < 2 and "among" not in found.get("headline", ""):
        return "cut not shown"
    return ""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--published", type=Path, default=ROOT / "data" / "published" / "current" / "api" / "v1")
    ap.add_argument("--no-score", action="store_true")
    ap.add_argument("--without-names", action="store_true", help="score Ask without the stored name table, to measure what it adds")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    waves = json.loads(gzip.decompress((args.published / "waves.json.gz").read_bytes()))
    index = Index(args.published / "questions", waves)
    rows = build(index)
    if not args.no_score:
        index.add_vectors()
        if args.without_names:
            index.names = {}
        visible = {w["survey_id"] for w in waves}
        for i, row in enumerate(rows):
            started = time.perf_counter()
            found = assistant.answer(row["question"], index, visible, quick=True)
            row["ms"] = round((time.perf_counter() - started) * 1000, 1)
            row["other_study"] = ""
            row["understood"] = found.get("understood", "")
            row["got_key"] = found["sources"][0]["key"] if found["sources"] else ""
            row["problem"] = score(row, found, index)
            if i % 1000 == 0:
                print(f"{i} of {len(rows)}", flush=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as f:
        out = csv.DictWriter(f, fieldnames=list(rows[0]))
        out.writeheader()
        out.writerows(rows)
    print(f"{len(rows)} questions from {len(index.docs)} survey questions → {args.out}")
    if not args.no_score:
        right = sum(not r["problem"] for r in rows)
        times = sorted(r["ms"] for r in rows)
        print(f"  of them from the same question in another study: {sum(bool(r['other_study']) and not r['problem'] for r in rows)}")
        print(f"Ask, quick: {right} of {len(rows)} right ({right / len(rows):.1%}) · median {times[len(times) // 2]} ms, 95th {times[int(len(times) * .95)]} ms")
        named = [r for r in rows if r["understood"] == "named"]
        print(f"  answered from the stored names: {len(named)}, right {sum(not r['problem'] for r in named)}")
        for group in ("persona", "kind", "country"):
            for value in sorted({r[group] for r in rows}):
                part = [r for r in rows if r[group] == value]
                print(f"  {group} {value}: {sum(not r['problem'] for r in part)} of {len(part)} ({sum(not r['problem'] for r in part) / len(part):.1%})")
        kinds: dict[str, int] = {}
        for r in rows:
            if r["problem"]:
                kinds[re.sub(r":.*", "", r["problem"])] = kinds.get(re.sub(r":.*", "", r["problem"]), 0) + 1
        print("  wrong:", kinds)
    return 0


if __name__ == "__main__":
    sys.exit(main())
