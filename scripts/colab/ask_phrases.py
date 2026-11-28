"""Ask CIP's plain phrases (Phase 3 of the Ask rebuild, docs/research/ask-cip-rebuild-2026-11-27/PROMPT.md): one
sentence-ready phrase and one chart title per survey question wording, written once by an open model on Colab
(scripts/colab/ask_phrases.ipynb), never with the paid key. Ask's answer patterns then say "65.5% of US adults bought
beauty products in the past three months" instead of naming a code. Run by hand, before and after the Colab run:

    python scripts/colab/ask_phrases.py export --published <api/v1> [<api/v1> ...] --out ask_phrases_input.jsonl
    python scripts/colab/ask_phrases.py merge ask_phrases_out.jsonl   # adds "phrase" and "title" to config/ask_semantic.json

Keyed like config/ask_semantic.json (api/ask_index.py digest: one entry per wording, under any code), so it does not
depend on how wordings are joined into series. Written 27 Nov 2026.
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from api.ask_index import SEMANTIC, Index, digest  # noqa: E402

ANSWERS = 12   # answers shown to the model per wording: enough to see the kind of question, short enough for a T4


def export(published: list[Path], out: Path) -> None:
    """One line per distinct wording: its key, text, answers, business name and survey, from every publish given."""
    rows = {}
    for v1 in published:
        index = Index(v1 / "questions", json.loads(gzip.decompress((v1 / "waves.json.gz").read_bytes())))
        for doc in index.docs.values():
            rows.setdefault(digest(doc["text"]), {"key": digest(doc["text"]), "text": doc["text"], "answers": doc["labels"][:ANSWERS],
                                                  "name": doc.get("name", ""), "survey": doc.get("title", "")})
    out.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows.values()))
    print(f"{len(rows):,} wordings into {out}")


def merge(results: Path) -> None:
    """Adds each phrase the notebook's reviewer approved, with its title, to its wording's entry; an entry a person already
    corrected keeps its words."""
    semantic = json.loads(SEMANTIC.read_text())
    added = 0
    for line in results.read_text().splitlines():
        row = json.loads(line)
        entry = semantic.get(row["key"])
        if entry is not None and row.get("ok") and row.get("reviewed") and "phrase" not in entry:
            entry.update(phrase=row["phrase"], title=row["title"])
            added += 1
    SEMANTIC.write_text(json.dumps(semantic, indent=0, ensure_ascii=False, sort_keys=True))
    print(f"{added:,} phrases added to {SEMANTIC.name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    steps = parser.add_subparsers(dest="step", required=True)
    step = steps.add_parser("export")
    step.add_argument("--published", type=Path, nargs="+", default=[ROOT / "data" / "published" / "current" / "api" / "v1"])
    step.add_argument("--out", type=Path, default=Path("ask_phrases_input.jsonl"))
    steps.add_parser("merge").add_argument("results", type=Path)
    args = parser.parse_args()
    export(args.published, args.out) if args.step == "export" else merge(args.results)
