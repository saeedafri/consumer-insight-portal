"""Ask Coresight's quality check: every question an analyst, a portal user or a client might ask about a survey question
(its latest figure, trend, each cut its data holds, periods compared, top answers, one answer, its season), written from
the survey question itself so the right answer is known before Ask is asked, then scored.

Who calls it: etl/publish.py publish, after every publish (after_publish): the surveys no check has seen yet are named
(etl/ask_semantic.py) and checked, newest first, at low priority; the result per survey is kept in logs/ask-quality.json
and shown to admins (GET /api/v1/admin/ask/quality, the Logs page). By hand, the whole catalogue (research, ~15 min):

    python -m etl.ask_quality --published <api/v1>             # ~50,000 questions → docs/research/ask-question-bank.csv.gz
    python -m etl.ask_quality --published <api/v1> --sample 5000   # the same 5,000 every run: a change measured in a minute

"Verified" answers are the ones Ask gives from a survey question's stored name (api/ask_index.py Index.named); they
must be right 99% of the time or more. Who asks what: docs/research/ask-question-bank.md.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import logging
import os
import random
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from api import assistant  # noqa: E402
from api import ask_model  # noqa: E402
from api.ask_index import SEMANTIC_ADDED, Index, name_key  # noqa: E402
from etl import ask_semantic  # noqa: E402

log = logging.getLogger("cip.ask_quality")
REPORT = ask_model.LOGS / "ask-quality.json"   # one entry per survey checked, newest first
NEW_PER_RUN = 6   # surveys checked after one publish (~10 s each on staging's one CPU); older ones by hand (--surveys)
MISSES_KEPT = 20  # wrong answers listed per survey for the admin to read

OUT = ROOT / "docs" / "research" / "ask-question-bank.csv.gz"   # gzip: 14 MB as plain CSV
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
    ("client", "momentum", "trend", "trend", "Has \u201c{l}\u201d grown for {n} since {since}?"),
    ("client", "year on year", "compare", "years", "How did {n} change from {first} to {last}?"),
]
NOT_AN_ANSWER = re.compile(r"\bother\b|don.t know|not sure|\bnone\b|prefer not|n/a", re.I)   # never the answer a question names
HELD_OUT = 6   # asks Ask is given; the rest are the test
SAME_QUESTION = 0.6   # share of words in common (Jaccard) at which two studies asked the same question (IN2 and CSI-US grocery changes)


def fits(needs: str, doc: dict, season: str, label: str, cuts: set[str]) -> bool:
    """Whether a template makes sense for this survey question: the history, years, answers or cut it needs are there."""
    if needs.startswith("cut:"):
        return needs[4:] in cuts
    return {"": True, "trend": doc["waves"] >= 3, "two": doc["waves"] >= 2, "years": doc["first"][:4] != doc["last"][:4],
            "top": len(doc["labels"]) >= 3, "season": bool(season), "answer": bool(label)}[needs]


def build(index: Index, held: dict[str, list[str]], keys: set[str] | None = None) -> list[dict]:
    """The bank: every template that fits each survey question, then its held-out paraphrases (held: the asks Ask is not
    given, see main), distinct wording, each with the survey question that answers it."""
    rows, seen = [], set()
    for key, doc in sorted(index.docs.items()):
        if keys is not None and key not in keys:
            continue
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
        filled = [(*f, name) for f in filled] + [("paraphrase", "held-out wording", "latest", ask.rstrip(), "") for ask in held.get(key, [])]
        for persona, purpose, kind, question, named in filled:
            question += " in China" if country == "CN" else ""
            if question.lower() in seen:
                continue
            seen.add(question.lower())
            rows.append({"question": question, "persona": persona, "purpose": purpose, "kind": kind, "country": country,
                         "season": season, "name": named, "answer_key": key, "answer_question": doc["text"], "waves": doc["waves"]})
    return rows


def score(row: dict, found: dict, index: Index) -> str:
    """What is wrong with Ask's answer (empty when right): the survey question (its own or the same wording in another
    study counts), the country, and the shape the kind needs."""
    if found["mode"] == "choose":
        return "asked to choose"   # not shown as an answer: the person picks the survey question (counted apart)
    if found["mode"] != "figures":
        return "no answer"
    source = found["sources"][0]
    got = index.docs.get(source["key"], {})
    if row["name"] and name_key(row["name"]) in index.name_keys.get(source["key"], ()):
        pass   # the question gives only the name, and the survey question Ask used carries that name: one of the right answers
    elif source["key"] != row["answer_key"] and got.get("text", "").lower() != row["answer_question"].lower():
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


def prepare(index: Index, hold_out: bool) -> dict[str, list[str]]:
    """Gets an index ready to be scored: which stored names each survey question carries (score), and with hold_out, the
    asks Ask is not given (an honest test of wording it has never seen: it searches with the first six of each question's
    eight, and is tested on the last two; production uses all eight, so this slightly understates it)."""
    index.name_keys = {}
    for pattern, keys in index.names.items():
        for k in keys:
            index.name_keys.setdefault(k, set()).add(pattern)
    held = {key: doc["asks"][HELD_OUT:] for key, doc in index.docs.items()} if hold_out else {}
    for doc in index.docs.values():
        doc["asks"] = doc["asks"][:HELD_OUT] if hold_out else doc["asks"]
    return held


def ask_all(index: Index, rows: list[dict], visible: set[int]) -> None:
    """Asks Ask every row's question (the quick answer, as the page shows it first) and scores it, in place."""
    for row in rows:
        started = time.perf_counter()
        found = assistant.answer(row["question"], index, visible, quick=True)
        row["ms"] = round((time.perf_counter() - started) * 1000, 1)
        row["other_study"] = ""
        row["understood"] = found.get("understood", "")
        row["margin"] = found.get("margin")
        row["got_key"] = found["sources"][0]["key"] if found["sources"] else ""
        row["problem"] = score(row, found, index)


def check_surveys(published: Path, ids: list[int]) -> list[dict]:
    """One report per survey: its questions, how many have a stored name, every question the bank asks about them, how
    many Ask got right, and how many of its verified answers (from a stored name) were right."""
    waves = json.loads(gzip.decompress((published / "waves.json.gz").read_bytes()))
    index = Index(published / "questions", waves)
    index.add_vectors()
    prepare(index, hold_out=False)
    visible = {w["survey_id"] for w in waves}
    reports = []
    for wave in [w for w in waves if w["survey_id"] in ids]:
        keys = {k for k, d in index.docs.items() if wave["survey_id"] in d["surveys"]}
        rows = build(index, {}, keys)
        ask_all(index, rows, visible)
        verified = [r for r in rows if r["understood"] == "named"]
        reports.append({"survey_id": wave["survey_id"], "wave_date": str(wave["wave_date"])[:10], "title": wave.get("title", ""),
                        "checked": datetime.now(timezone.utc).isoformat(timespec="seconds"), "questions": len(keys),
                        "named": sum(bool(index.docs[k]["name"]) for k in keys), "asked": len(rows),
                        "right": sum(not r["problem"] for r in rows), "verified": len(verified),
                        "verified_right": sum(not r["problem"] for r in verified),
                        "misses": [{"question": r["question"], "problem": r["problem"], "verified": r["understood"] == "named"}
                                   for r in rows if r["problem"]][:MISSES_KEPT]})
    return reports


def after_publish(out: Path) -> None:
    """After a publish (etl/publish.py publish): names the new survey questions, then checks the surveys no check has
    seen, newest first, at low priority so the site keeps its speed. A failure is logged; the publish stands."""
    os.nice(10)
    published = out / "api" / "v1"
    waves = json.loads(gzip.decompress((published / "waves.json.gz").read_bytes()))
    index = Index(published / "questions", waves)
    if ask_semantic.name_new(index, SEMANTIC_ADDED) + ask_semantic.rename_shared(index, SEMANTIC_ADDED):
        log.info("Ask names changed: the API's index picks them up at its next build")
    done = json.loads(REPORT.read_text()) if REPORT.exists() else []
    seen = {r["survey_id"] for r in done}
    todo = [w["survey_id"] for w in sorted(waves, key=lambda w: str(w["wave_date"]), reverse=True) if w["survey_id"] not in seen][:NEW_PER_RUN]
    if not todo:
        return
    reports = check_surveys(published, todo)
    REPORT.write_text(json.dumps(sorted(reports + done, key=lambda r: r["wave_date"], reverse=True), indent=0))
    for r in reports:
        log.info("Ask check %s (%s): %d of %d right, verified %d of %d", r["survey_id"], r["wave_date"], r["right"], r["asked"],
                 r["verified_right"], r["verified"])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--published", type=Path, default=ROOT / "data" / "published" / "current" / "api" / "v1")
    ap.add_argument("--no-score", action="store_true")
    ap.add_argument("--without-names", action="store_true", help="score Ask without the stored name table, to measure what it adds")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--sample", type=int, default=0, help="score this many rows, the same ones every run (±0.6 pts at 5,000), to measure a change fast")
    ap.add_argument("--surveys", type=int, nargs="*", help="check these surveys as after a publish, into logs/ask-quality.json")
    args = ap.parse_args()
    if args.surveys:
        reports = check_surveys(args.published, args.surveys)
        kept = [r for r in (json.loads(REPORT.read_text()) if REPORT.exists() else []) if r["survey_id"] not in args.surveys]
        REPORT.write_text(json.dumps(sorted(reports + kept, key=lambda r: r["wave_date"], reverse=True), indent=0))
        for r in reports:
            print(f"{r['survey_id']} {r['wave_date']}: {r['right']} of {r['asked']} right · verified {r['verified_right']} of {r['verified']}")
        return 0
    waves = json.loads(gzip.decompress((args.published / "waves.json.gz").read_bytes()))
    index = Index(args.published / "questions", waves)
    held = prepare(index, hold_out=True)
    rows = build(index, held)
    if args.sample:
        rows = random.Random(12).sample(rows, args.sample)
    if not args.no_score:
        index.add_vectors()
        if args.without_names:
            index.names = {}
        ask_all(index, rows, {w["survey_id"] for w in waves})
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(args.out, "wt", newline="") as f:
        out = csv.DictWriter(f, fieldnames=list(rows[0]))
        out.writeheader()
        out.writerows(rows)
    print(f"{len(rows)} questions from {len(index.docs)} survey questions → {args.out}")
    if not args.no_score:
        right = sum(not r["problem"] for r in rows)
        times = sorted(r["ms"] for r in rows)
        print(f"  of them from the same question in another study: {sum(bool(r['other_study']) and not r['problem'] for r in rows)}")
        print(f"Ask, quick: {right} of {len(rows)} right ({right / len(rows):.1%}) · median {times[len(times) // 2]} ms, 95th {times[int(len(times) * .95)]} ms")
        shown = [r for r in rows if r["problem"] != "asked to choose"]
        print(f"  answers shown: {len(shown)} of {len(rows)} ({len(shown) / len(rows):.1%}), right {sum(not r['problem'] for r in shown) / max(len(shown), 1):.1%}"
              f" · asked to choose {len(rows) - len(shown)}")
        named = [r for r in rows if r["understood"] == "named"]
        print(f"  verified (from a stored name): {sum(not r['problem'] for r in named)} of {len(named)} right")
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
