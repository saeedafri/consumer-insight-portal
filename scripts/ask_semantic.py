"""Ask Coresight's semantic layer: a business name, aliases, a topic and analysts' questions for every survey question,
written once.

    python scripts/ask_semantic.py              # adds the questions not yet named or without asks; prints the cost
    python scripts/ask_semantic.py --dry-run    # counts what would be sent, sends nothing

Why: what an analyst types ("Amazon Prime membership", "nonfood retailers") rarely matches a survey's wording ("Do you
have an Amazon Prime membership/access to Prime membership?"). Snowflake, Databricks and Cube all found a semantic layer
lifts accuracy more than a bigger model (research, 11 Nov 2026). The names are written by the cheap model 40 questions
a request (~$0.03 per 1,000 questions) and kept in config/ask_semantic.json by the hash of each question's wording, so
a later publish only names the new ones. People may edit the file: a corrected name or alias is used as it stands.
api/ask_index.py reads it: names and aliases are searched and embedded, and the model is shown the name.
asks: eight questions an analyst would type to get the question's figures (the "semantic router" pattern, research
12 Nov 2026). api/ask_index.py embeds each on the server, so a new question is matched to the nearest asks in a few
milliseconds with no model call. Written for 2,002 wordings for about $0.15 once; a name already there is kept.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
ENV = Path(__file__).resolve().parents[1] / ".env"
for line in ENV.read_text().splitlines() if ENV.exists() else []:
    if line.startswith("OPENAPI_KEY=") and not os.environ.get("OPENAPI_KEY"):
        os.environ["OPENAPI_KEY"] = line.split("=", 1)[1].strip().strip("'\"")

from api import ask_model  # noqa: E402
from api.ask_index import digest  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SEMANTIC = ROOT / "config" / "ask_semantic.json"
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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    from api.ask_index import Index
    waves = json.loads(gzip.decompress((PUBLISHED / "waves.json.gz").read_bytes()))
    index = Index(PUBLISHED / "questions", waves)
    known = json.loads(SEMANTIC.read_text()) if SEMANTIC.exists() else {}
    todo = {digest(d["text"]): d for d in index.docs.values() if "asks" not in known.get(digest(d["text"]), {})}
    todo = list(todo.items())
    tokens = sum(len(d["text"]) // 4 + 25 for _, d in todo)   # in; ~130 out each
    print(f"{len(index.docs):,} questions, {len(known):,} already named, {len(todo):,} to name (~{tokens:,} tokens in)")
    if args.dry_run or not todo:
        return 0
    before = ask_model.spent()["usd"]

    def send(part: list) -> dict | None:
        """One batch's reply, None on a failure (what is done is kept; run again to finish)."""
        listing = "\n".join(f"{i}. {d['text'][:160]} | {'; '.join(a[:20] for a in d.get('labels', [])[:4])}" for i, (_, d) in enumerate(part))
        try:
            reply = ask_model.call("chat/completions", {
                "model": ask_model.model(), "temperature": 0, "max_tokens": 6000,
                "messages": [{"role": "system", "content": SYSTEM + " Topics: " + ", ".join(TOPICS)}, {"role": "user", "content": listing}],
                "response_format": {"type": "json_schema", "json_schema": {"name": "names", "strict": True, "schema": SCHEMA}}},
                seconds=180)   # 20 questions at once: a minute or so, not a single question's few seconds
        except Exception as exc:   # noqa: BLE001
            print(f"  a batch failed: {type(exc).__name__}")
            return None
        ask_model.charge(ask_model.model(), reply["usage"]["prompt_tokens"], reply["usage"]["completion_tokens"])
        return reply

    parts = [todo[start:start + BATCH] for start in range(0, len(todo), BATCH)]
    with ThreadPoolExecutor(PARALLEL) as pool:
        for done, (part, reply) in enumerate(zip(parts, pool.map(send, parts)), start=1):
            for row in json.loads(reply["choices"][0]["message"]["content"])["rows"] if reply else []:
                if 0 <= row["i"] < len(part):
                    h, d = part[row["i"]]
                    known[h] = {"name": row["name"].strip()[:80], "aliases": [a.strip()[:60] for a in row["aliases"][:4]],
                                "topic": row["topic"], "text": d["text"][:120], **known.get(h, {}),   # a name already there stays
                                "asks": [a.strip()[:120] for a in row["asks"][:8]]}
            SEMANTIC.write_text(json.dumps(known, indent=0, ensure_ascii=False, sort_keys=True))
            print(f"  {done:,} of {len(parts):,} batches · ${ask_model.spent()['usd'] - before:.4f} so far", flush=True)
    print(f"Done: {len(known):,} named · cost ${ask_model.spent()['usd'] - before:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
