"""Ask CIP v6 without any AI API: the data for scripts/colab/train_search_model_v6.ipynb, and its score inside Ask.

    python scripts/ask_v6.py export ~/Downloads/cip-colab     # v6-train.json, v6-tests.json into that folder
    python scripts/ask_v6.py export-search ~/Downloads/cip-colab   # v8-search.json, v8-tests.json: the v8 notebook's data
    python scripts/ask_v6.py score replies.json golden        # Ask's score with these picks in the AI's place
    python scripts/ask_v6.py score replies.json bank          # the same on the big exam's 3,000 (seed 11)
    python scripts/ask_v6.py score replies.json golden --reader   # Ask as served: its reader (models/ask-reader) picks,
                                                                  # the replies stand in for the AI only where it is unsure

export: practice questions (catalogue asks, the checked Qwen practice questions, the off-topic ones; files in the folder,
as uploaded to Colab for v5) go through Ask, and the request Ask would send its AI is recorded instead of sent: the
question, the numbered candidate lines the AI reads, each candidate's survey key. The golden set and the big exam are
written apart (v6-tests.json) and never trained on.
score: the replies (the request's text → the AI's JSON, from the notebook) are given to Ask as its AI's, and the final
answer is scored as scripts/ask_golden.py scores it (golden) or as the big exam's key says (bank). Without --reader the
reader is off, so every request reaches the replies; with it, Ask runs as served (an empty {} file: the reader alone).
No OpenAI either way: the key is removed and api/ask_model.py call is replaced, so nothing reaches the network.
Run from the repo root with PYTHONPATH=. (14 Nov 2026: Qwen3-32B's picks scored 154 of 161 this way).
"""
from __future__ import annotations

import argparse
import collections
import csv
import gzip
import json
import os
import random
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from ask_golden import GOLDEN, score  # noqa: E402  (it reads the key from .env: removed below)

from api import ask_index, ask_model, ask_reader, assistant  # noqa: E402

BANK = ROOT / "docs/research/ask-question-bank.csv.gz"
FRESH = ROOT / "scripts" / "ask_fresh.yml"   # real staging questions, never tuned on (scripts/ask_golden.py --questions)
BANK_SAMPLE, BANK_SEED = 3000, 11   # the sample every round since v4 was tested on
PUBLISHED = ROOT / "data/published/current/api/v1"


def without_api(replies: dict | None, scratch: Path, reader: bool = False) -> dict:
    """Ask with no OpenAI: the key gone, the AI step recording its candidates (export) or answering from replies (score),
    Ask's own reader on or off. The record of the last AI step is returned (and refilled on each question)."""
    for name in list(os.environ):
        if name.upper() in ask_model.KEY_NAMES:
            os.environ.pop(name)
    last = {}

    def call(path, body, seconds=0):
        user = body["messages"][1]["content"]
        last["user"] = user
        if replies is None or user not in replies:
            raise RuntimeError("no AI here")   # plan() then returns None, as when the AI fails: the rules answer
        return {"choices": [{"message": {"content": replies[user]}}], "usage": {"prompt_tokens": 0, "completion_tokens": 0}}

    plan = ask_model.plan

    def recording_plan(question, candidates):
        last["candidates"] = candidates
        return plan(question, candidates)

    ask_model.call, ask_model.ready, ask_model.key, ask_model.plan = call, lambda: True, lambda: "none", recording_plan
    if not reader:   # every request reaches the AI step
        ask_model.reader = lambda: None
    ask_model.READINGS, ask_model.SPEND = scratch / "v6-readings.json", scratch / "v6-spend.json"
    ask_model.READINGS.unlink(missing_ok=True)   # never an earlier reading
    ask_index.LEARNED = assistant.LEARNED = scratch / "v6-no-learned.json"
    return last


def load_index():
    waves = json.loads(gzip.decompress((PUBLISHED / "waves.json.gz").read_bytes()))
    index = assistant.Index(PUBLISHED / "questions", waves)
    index.add_vectors()
    return index, {w["survey_id"] for w in waves}, {w["survey_id"]: w.get("country") or "US" for w in waves}


def bank_sample() -> list[dict]:
    rows = [r for r in csv.DictReader(gzip.open(BANK, "rt")) if r["country"] == "US"]
    return rows, random.Random(BANK_SEED).sample(rows, BANK_SAMPLE)


def recorder(index, visible: set[int], last: dict):
    """request(question): the request Ask would send its AI for a question (its text, the numbered lines it reads, each
    line's survey key and wording), or None when names, verified answers or the rules answer it with no AI step."""
    by_text = collections.defaultdict(list)
    for k, d in index.docs.items():
        by_text[d["text"]].append(k)

    def request(question):
        last.clear()
        assistant.answer(question, index, visible)
        cands = last.get("candidates")
        if not cands:   # names, learned or rules answered it: no AI step
            return None
        lines = last["user"].split("\n")[1:]   # the numbered lines exactly as sent
        keys = [next((k for k in by_text.get(c["text"], []) if index.docs[k]["waves"] == c["waves"] and index.docs[k]["first"] == c["first"]), None)
                for c in cands]
        return {"user": last["user"], "lines": lines, "keys": keys, "texts": [c["text"] for c in cands]}
    return request


def export(folder: Path, per: int) -> None:
    """v6-train.json and v6-tests.json into folder (see the top of this file)."""
    last = without_api(None, folder)
    index, visible, _ = load_index()
    request = recorder(index, visible, last)
    cat = json.loads((folder / "catalogue.json").read_text())
    v3, v4, qwen = (json.loads((folder / f).read_text()) for f in ("synthetic.json", "synthetic-v4.json", "qwen-v5.json"))
    rejected = {(t, k) for t, k in qwen["rejected"]}   # the practice questions the round-trip check removed (Part 18)
    golden = yaml.safe_load(GOLDEN.read_text())
    bank, sample = bank_sample()
    held_out = {g["q"].lower() for g in golden} | {q.lower() for q in cat.get("golden_none", [])} | {r["question"].lower() for r in bank}
    rng = random.Random(6)
    practice = []
    for d in cat["docs"]:   # up to `per` a survey question: two analysts' asks (real wording) first, then checked practice ones
        pool = list(dict.fromkeys(t for t in d["asks"][:6] + v3.get(d["key"], []) + v4.get(d["key"], [])
                                  if t and (t, d["key"]) not in rejected and t.lower() not in held_out))
        practice += [(t, d["key"]) for t in pool[:2] + rng.sample(pool[2:], max(0, min(len(pool) - 2, per - 2)))]
    practice += [(q, None) for q in qwen["offtopic"] if q.lower() not in held_out]   # "none of these" examples
    rng.shuffle(practice)
    train = [{"q": q, "source": k, **r} for q, k in practice if (r := request(q))]
    tests = {"golden": [{"q": g["q"], "want": g["want"], **r} for g in golden if (r := request(g["q"]))],
             "bank": [{"q": b["question"], "answer_key": b["answer_key"], **r} for b in sample if (r := request(b["question"]))]}
    head = {"system": ask_model.SYSTEM, "schema": ask_model.SCHEMA}
    (folder / "v6-train.json").write_text(json.dumps({**head, "items": train}))
    (folder / "v6-tests.json").write_text(json.dumps({**head, **tests}))
    print(f"{len(practice)} practice questions read · {len(train)} reach the AI step · tests: golden {len(tests['golden'])}, "
          f"big exam {len(tests['bank'])} of {BANK_SAMPLE}")


def export_search(folder: Path, train: Path) -> None:
    """v8-search.json and v8-tests.json into folder, for scripts/colab/train_search_model_v8.ipynb: every survey question
    as the search reads it (wording with answers and topic, its analysts' asks, its standing), the golden, fresh and
    big-exam questions with the survey questions that answer them, the practice questions with their checked labels
    (v7-train.json: none of the tests), today's thresholds (bge-small's scale), and the requests Ask would send its AI
    for the three tests, which a new reader is scored on."""
    last = without_api(None, folder)
    index, visible, _ = load_index()
    keys = index.vector_keys
    docs = [{"key": k, "text": index.docs[k]["text"], "embed": index.embed_text[k], "asks": index.docs[k].get("asks", []),
             "waves": index.docs[k]["waves"], "standing": round(float(s), 5)} for k, s in zip(keys, index.standing)]

    def subject(question):   # what Ask's search embeds (api/assistant.py answer): the question's subject, else itself
        question = index.correct_spelling(" ".join(question.split())[:500])
        about = ask_reader.read(question)["about"]
        return about if len(about) >= 3 else question

    def answering(want):   # the golden format's phrases: every survey question whose wording has one is a right answer
        return None if want == "none" else sorted(k for k in keys if any(w in index.docs[k]["text"].lower() for w in want))

    def bank_right(b):   # the big exam's key, the same wording, or the same question in the study it names
        other = {o.strip() for o in b["other_study"].split(";") if o.strip()}
        return sorted(k for k in keys if k == b["answer_key"] or index.docs[k]["text"].lower() == b["answer_question"].lower()
                      or f"{index.docs[k]['family']} {index.docs[k]['qcode']}" in other)

    golden, fresh = (yaml.safe_load(p.read_text()) for p in (GOLDEN, FRESH))
    _, bank = bank_sample()
    tests = {"golden": [{"q": g["q"], "subject": subject(g["q"]), "right": answering(g["want"])} for g in golden],
             "fresh": [{"q": g["q"], "subject": subject(g["q"]), "right": answering(g["want"])} for g in fresh],
             "bank": [{"q": b["question"], "subject": subject(b["question"]), "right": bank_right(b)} for b in bank]}
    items = json.loads(train.read_text())["items"]
    practice = [{"q": i["q"], "subject": subject(i["q"]), "key": i["keys"][i["label"]]} for i in items
                if isinstance(i["label"], int) and i["label"] >= 0 and i["keys"][i["label"]] in index.docs]
    scale = {"near_floor": assistant.NEAR_FLOOR, "gate": float(ask_model.calibration().get("gate", 0.04)),
             "verified_near": ask_index.VERIFIED_NEAR, "ask_weight": ask_index.ASK_WEIGHT, "standing": ask_index.STANDING,
             "area_boost": ask_index.AREA_BOOST}
    (folder / "v8-search.json").write_text(json.dumps({"docs": docs, "tests": tests, "practice": practice, "bge_small": scale}))
    request = recorder(index, visible, last)
    reads = {"golden": [{"q": g["q"], "want": g["want"], **r} for g in golden if (r := request(g["q"]))],
             "fresh": [{"q": g["q"], "want": g["want"], **r} for g in fresh if (r := request(g["q"]))],
             "bank": [{"q": b["question"], "answer_key": b["answer_key"], **r} for b in bank if (r := request(b["question"]))]}
    (folder / "v8-tests.json").write_text(json.dumps({"system": ask_model.SYSTEM, "schema": ask_model.SCHEMA, **reads}))
    print(f"{len(docs)} survey questions ({sum(len(d['asks']) for d in docs)} asks) · {len(practice)} practice questions · tests: "
          + ", ".join(f"{t} {len(tests[t])} ({len(reads[t])} reach the AI step)" for t in tests))


def score_replies(replies_file: Path, test: str, reader: bool) -> None:
    """Ask's final answers with the replies in the AI's place: right of the golden set or the big-exam sample."""
    replies = json.loads(replies_file.read_text())
    last = without_api(replies, replies_file.parent, reader)
    index, visible, countries = load_index()
    asked = without = right = 0
    if test == "golden":
        items = yaml.safe_load(GOLDEN.read_text())
        for g in items:
            last.clear()
            right += not score(g, assistant.answer(g["q"], index, visible), countries)
            asked += "user" in last
            without += "user" in last and last["user"] not in replies
    else:
        _, items = bank_sample()
        for b in items:
            last.clear()
            a = assistant.answer(b["question"], index, visible)
            src = (a.get("sources") or [{}])[0]
            other = {o.strip() for o in b["other_study"].split(";") if o.strip()}
            got = src.get("key")
            same = a.get("mode") == "figures" and got and (got == b["answer_key"] or src.get("question", "").lower() == b["answer_question"].lower()
                                                           or f"{index.docs[got]['family']} {index.docs[got]['qcode']}" in other)
            ok = bool(same) and not (b["kind"] == "cut" and not a["plan"]["cuts"]) and not (b["kind"] == "trend" and len((a.get("table") or {}).get("head", [])) < 3)
            right += ok
            asked += "user" in last
            without += "user" in last and last["user"] not in replies
    print(f"{replies_file.name} on {test}: right {right} of {len(items)} ({right / len(items):.1%}) · AI step reached {asked}, "
          f"of which without a reply {without} (the reader's pick, or the rules, answered those)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="do", required=True)
    e = sub.add_parser("export")
    e.add_argument("folder", type=Path)
    e.add_argument("--per", type=int, default=4, help="practice questions per survey question")
    x = sub.add_parser("export-search")
    x.add_argument("folder", type=Path)
    x.add_argument("--train", type=Path, default=Path("~/Downloads/cip-colab/v7-train.json"), help="the practice questions, labelled")
    s = sub.add_parser("score")
    s.add_argument("replies", type=Path)
    s.add_argument("test", choices=("golden", "bank"))
    s.add_argument("--reader", action="store_true", help="Ask's own reader on: the replies only where it is unsure")
    args = ap.parse_args()
    assistant.GATE = -1.0   # always the best answer: no "which did you mean?" in a score
    if args.do == "export":
        export(args.folder.expanduser(), args.per)
    elif args.do == "export-search":
        export_search(args.folder.expanduser(), args.train.expanduser())
    else:
        score_replies(args.replies, args.test, args.reader)
    return 0


if __name__ == "__main__":
    sys.exit(main())
