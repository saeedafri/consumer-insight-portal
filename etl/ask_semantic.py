"""Ask Coresight's semantic layer: a business name, aliases, a topic and eight analysts' questions for every survey
question wording, written once by the small AI model, so Ask can answer a question that uses the name at once
(api/ask_index.py Index.names) and match other wording by meaning.

Who calls it: etl/ask_quality.py after_publish, at the end of every publish (etl/publish.py publish): only wordings no
earlier run has named are sent, ~$0.03 per 1,000, so a new survey's questions are named the day it is published. Kept
in logs/ask-semantic.json (on /home: a deploy keeps it). By hand:

    python -m etl.ask_semantic              # names every unnamed wording, and renames questions that share a name with
                                            # different ones (rename_shared), into config/ask_semantic.json (reviewed in git)
    python -m etl.ask_semantic --dry-run    # counts what would be sent, sends nothing

api/ask_index.py reads config/ask_semantic.json, and logs/ask-semantic.json over it (a publish's new names and renames).
People may correct a name in the config; one renamed on the server is in logs/ask-semantic.json, which wins.
"""
from __future__ import annotations

import argparse
import gzip
import json
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ENV = Path(__file__).resolve().parents[1] / ".env"
for line in ENV.read_text().splitlines() if ENV.exists() else []:
    if line.startswith("OPENAPI_KEY=") and not os.environ.get("OPENAPI_KEY"):
        os.environ["OPENAPI_KEY"] = line.split("=", 1)[1].strip().strip("'\"")

from api import ask_model  # noqa: E402
from api.ask_index import SEMANTIC, SEMANTIC_ADDED, Index, digest, read_json  # noqa: E402

log = logging.getLogger("cip.ask_semantic")
ROOT = Path(__file__).resolve().parents[1]
PUBLISHED = ROOT / "data" / "published" / "current" / "api" / "v1"
TOPICS = ["retailers", "shopping categories", "online and ecommerce", "grocery and food", "apparel", "beauty",
          "home", "holidays and events", "deals and promotions", "genai and technology", "health and glp-1",
          "personal finances", "economy and prices", "tariffs", "social media shopping", "travel and leisure",
          "demographics", "other"]
BATCH = 20   # 20 questions × 8 asks fit one reply
PARALLEL = 6   # batches sent at once: ~10 minutes for 2,000 wordings, not an hour
SCHEMA = {"type": "object", "additionalProperties": False, "required": ["rows"], "properties": {"rows": {"type": "array", "items": {
    "type": "object", "additionalProperties": False, "required": ["i", "name", "aliases", "topic", "asks"],
    "properties": {"i": {"type": "integer"}, "name": {"type": "string"}, "aliases": {"type": "array", "items": {"type": "string"}},
                   "topic": {"type": "string", "enum": TOPICS}, "asks": {"type": "array", "items": {"type": "string"}}}}}}}
SYSTEM = ("For each numbered consumer-survey question, give: name, what an analyst would call it in 2-6 words (e.g. "
          "'Amazon Prime membership', 'Nonfood retailers bought from'); aliases, 2-4 other short ways analysts say it; "
          "topic, one of the list; asks, 8 different short questions an analyst would type to get this question's figures "
          "(what share or how many, over time, by age or income, which are most common, about one named answer), "
          "varied wording, never the survey's own. Plain words, no numbers from the answers.")


RENAME_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["rows"], "properties": {"rows": {"type": "array", "items": {
    "type": "object", "additionalProperties": False, "required": ["g", "i", "name", "aliases"],
    "properties": {"g": {"type": "integer"}, "i": {"type": "integer"}, "name": {"type": "string"},
                   "aliases": {"type": "array", "items": {"type": "string"}}}}}}}
RENAME = ("Each numbered group below holds consumer-survey questions that were all given the same short name, though they ask "
          "different things. For every question (g = its group number, i = its position in the group: a = 0, b = 1), give a new name, what an "
          "analyst would call it in 2-6 words, that tells it apart from the others in its group (what is asked, the event, the "
          "retailer or the period), and 2-4 aliases. Plain words, no numbers from the answers.")
RENAME_BATCH = 10   # groups a request


def send(system: str, listing: str, schema: dict) -> list[dict]:
    """The small model's rows for one listing ([] on a failure: what is done is kept; the next run finishes)."""
    try:
        reply = ask_model.call("chat/completions", {
            "model": ask_model.model(), "temperature": 0, "max_tokens": 6000,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": listing}],
            "response_format": {"type": "json_schema", "json_schema": {"name": "names", "strict": True, "schema": schema}}},
            seconds=180)   # 20 questions at once: a minute or so, not a single question's few seconds
    except Exception as exc:   # noqa: BLE001
        log.warning("Ask names: a request failed: %s", type(exc).__name__)
        return []
    ask_model.charge(ask_model.model(), reply["usage"]["prompt_tokens"], reply["usage"]["completion_tokens"])
    return json.loads(reply["choices"][0]["message"]["content"])["rows"]


def rename_shared(index: Index, into: Path) -> int:
    """Gives questions that share a name but ask different things a name each (index.ambiguous: "Economic outlook" was
    both the economy and the pace of price rises), so Ask can answer them as verified; returns how many were renamed.
    Questions alike keep sharing (the same question in two studies). Each group is sent once: a renamed question is
    marked and never sent again, so a name the model could not tell apart costs nothing more."""
    if not ask_model.ready():
        return 0
    added = read_json(into)
    groups = []   # per shared name: one survey question per kind of question under it, each with every alike holder
    for pattern in sorted(index.ambiguous):
        kinds: list[list[str]] = []
        for key in index.names[pattern]:
            home = next((g for g in kinds if index.alike(g[0], key)), None)
            home.append(key) if home else kinds.append([key])
        if len(kinds) > 1 and not all(added.get(digest(index.docs[g[0]]["text"]), {}).get("renamed") for g in kinds):
            groups.append(kinds)
    if not groups:
        return 0
    batches = [groups[start:start + RENAME_BATCH] for start in range(0, len(groups), RENAME_BATCH)]
    listings = ["\n".join(f"Group {g}:\n" + "\n".join(f"  {chr(97 + i)}. {index.docs[kind[0]]['text'][:160]} | "
                                                     f"{'; '.join(a[:20] for a in index.docs[kind[0]]['labels'][:4])}"
                                                     for i, kind in enumerate(kinds)) for g, kinds in enumerate(batch)) for batch in batches]
    renamed = 0
    with ThreadPoolExecutor(PARALLEL) as pool:
        for batch, rows in zip(batches, pool.map(lambda listing: send(RENAME, listing, RENAME_SCHEMA), listings)):
            for row in rows:
                if 0 <= row["g"] < len(batch) and 0 <= row["i"] < len(batch[row["g"]]):
                    for key in batch[row["g"]][row["i"]]:   # every alike holder takes the new name
                        doc = index.docs[key]
                        h = digest(doc["text"])
                        added[h] = {**{"topic": doc.get("area", ""), "asks": doc.get("asks", []), "text": doc["text"][:120]}, **added.get(h, {}),
                                    "name": row["name"].strip()[:80], "aliases": [a.strip()[:60] for a in row["aliases"][:4]], "renamed": True}
                        renamed += 1
            into.write_text(json.dumps(added, indent=0, ensure_ascii=False, sort_keys=True))
    log.info("Ask names: %d questions sharing a name with different questions renamed into %s", renamed, into.name)
    return renamed


def name_new(index: Index, into: Path) -> int:
    """Names every wording in the index that config/ask_semantic.json and logs/ask-semantic.json both lack, into `into`;
    returns how many. Nothing is sent without a key or over the month's model budget (api/ask_model.py ready)."""
    known = {**read_json(SEMANTIC_ADDED), **read_json(SEMANTIC)}
    todo = list({digest(d["text"]): d for d in index.docs.values() if "asks" not in known.get(digest(d["text"]), {})}.items())
    if not todo or not ask_model.ready():
        return 0
    added = read_json(into)

    named = 0
    parts = [todo[start:start + BATCH] for start in range(0, len(todo), BATCH)]
    with ThreadPoolExecutor(PARALLEL) as pool:
        listings = ["\n".join(f"{i}. {d['text'][:160]} | {'; '.join(a[:20] for a in d.get('labels', [])[:4])}" for i, (_, d) in enumerate(part)) for part in parts]
        for part, rows in zip(parts, pool.map(lambda listing: send(SYSTEM + " Topics: " + ", ".join(TOPICS), listing, SCHEMA), listings)):
            for row in rows:
                if 0 <= row["i"] < len(part):
                    h, d = part[row["i"]]
                    added[h] = {"name": row["name"].strip()[:80], "aliases": [a.strip()[:60] for a in row["aliases"][:4]],
                                "topic": row["topic"], "text": d["text"][:120], **added.get(h, {}),   # a name already there stays
                                "asks": [a.strip()[:120] for a in row["asks"][:8]]}
                    named += 1
            into.write_text(json.dumps(added, indent=0, ensure_ascii=False, sort_keys=True))
    log.info("Ask names: %d new question wordings named into %s", named, into.name)
    return named


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--published", type=Path, default=ROOT / "data" / "published" / "current" / "api" / "v1")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s | %(message)s")
    index = Index(args.published / "questions", json.loads(gzip.decompress((args.published / "waves.json.gz").read_bytes())))
    unnamed = sum(not d["name"] for d in index.docs.values())
    print(f"{len(index.docs):,} questions, {unnamed:,} without a name")
    if args.dry_run:
        return 0
    before = ask_model.spent()["usd"]
    print(f"Named {name_new(index, SEMANTIC):,}, renamed {rename_shared(index, SEMANTIC):,} sharing a name with different "
          f"questions · cost ${ask_model.spent()['usd'] - before:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
