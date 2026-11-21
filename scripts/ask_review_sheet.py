"""The research team's review sheet for retraining Ask CIP's reader, and its reading back.

    python scripts/ask_review_sheet.py build --out reports/ask-review-sheet.xlsx [--asks] [--generated 140] [--written-on 2026-11-09]
    python scripts/ask_review_sheet.py read reports/ask-review-sheet.xlsx --out reports/ask-reviewed.jsonl

build: one row a question: the real asks typed in a browser (cip_access_log, --asks: a read of the database), the
researched set (scripts/ask_researched.yml), the misses' wordings (scripts/ask_review_questions.yml), questions no
survey asks (scripts/ask_review_none.yml) and generated questions Ask gets wrong (scripts/ask_bench.py's, seed 11; the
bench scores seed 7). --written-on dates the generated and no-answer rows, which are not asks: the training
publication's newest wave, so the trainer splits them into train, dev and test; the real asks, the researched set and
the reworded misses keep the day they were asked or written, after it, so they test the "future" split. Each row shows Ask's answer and
the five candidates its reader chose between; a reviewer marks the right one, "None" or another code. The golden and
fresh sets' questions are always left out: they are the release exam.
read: the marked sheet as the `--expert` file of scripts/colab/ask_cip_train.py prepare, one JSON object a line.
Plan and roles: docs/research/Claude-Ask-reader-retraining-plan-2026-11-21.md.
"""
from __future__ import annotations

import argparse
import gzip
import json
import random
import re
import sys
from datetime import date
from pathlib import Path
from unittest.mock import patch

import yaml
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

PUBLISHED = ROOT / "data" / "published" / "current" / "api" / "v1"
CHOICES = 5
ANSWERS = [str(n) for n in range(1, CHOICES + 1)] + ["Pick", "None", "Other"]
# visible columns, then the hidden ones the read step needs
HEAD = ["No.", "Question", "Where it came from", "Ask answered from", *[f"Choice {n}" for n in range(1, CHOICES + 1)],
        "Right answer", "Other question code", "Also right (choice numbers)", "Note",
        "country", "kind", "observed_at", "pick key", *[f"key {n}" for n in range(1, CHOICES + 1)]]
FILL = PatternFill("solid", start_color="FFF2CC")   # the cells a reviewer fills
FONT = Font(name="Arial", size=10)


def plain(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def real_asks() -> list[tuple[str, str]]:
    """Distinct questions typed in a browser, with the day first asked: the question text and day only, no person."""
    from sqlalchemy import text
    from shared.core.database import get_engine
    with get_engine("app").connect() as conn:
        rows = conn.execute(text("SELECT target, MIN(ts) FROM cip_access_log WHERE action = 'ask' AND target IS NOT NULL "
                                 "AND user_agent LIKE 'Mozilla%' GROUP BY target ORDER BY MIN(ts)")).fetchall()
    return [(q, str(day)[:10]) for q, day in rows]


def describe(doc: dict) -> str:
    return f"{doc['qcode']} · {doc.get('name') or ''} — “{doc['text'][:140]}” · {doc['waves']} waves, last {doc['last']}"


def build(args) -> None:
    from api import ask_model, ask_reader, assistant
    from api.ask_index import Index
    waves = json.loads(gzip.decompress((args.published / "waves.json.gz").read_bytes()))
    index = Index(args.published / "questions", waves)
    index.add_vectors()
    visible = {w["survey_id"] for w in waves}
    by_line = {(d["text"], d["waves"], d["first"], d["last"]): k for k, d in index.docs.items()}
    exam = {plain(i["q"]) for f in ("ask_golden.yml", "ask_fresh.yml") for i in yaml.safe_load((ROOT / "scripts" / f).read_text())}
    today = str(date.today())

    asked: list[tuple[str, str, str]] = []   # question, where from, observed_at
    if args.asks:
        asked += [(q, "Analyst ask on staging", day) for q, day in real_asks()]
    asked += [(i["q"], "Researched set", "2026-11-20") for i in yaml.safe_load((ROOT / "scripts/ask_researched.yml").read_text())]
    asked += [(q, "A miss, reworded", today) for q in yaml.safe_load((ROOT / "scripts/ask_review_questions.yml").read_text())]
    asked += [(q, "No survey asks this (written)", args.written_on) for q in yaml.safe_load((ROOT / "scripts/ask_review_none.yml").read_text())]

    def read(question: str) -> tuple[dict, list[str]]:
        seen: list[dict] = []
        real = ask_model.read_pick
        with patch.object(ask_model, "read_pick", lambda q, listed: seen.extend(listed) or real(q, listed)):
            found = assistant.answer(question, index, visible, True)
        return found, [by_line.get((c["text"], c["waves"], c["first"], c["last"])) for c in seen]

    rows, done = [], set(exam)
    for question, origin, day in asked:
        if plain(question) in done or len(plain(question)) < 3:
            continue
        done.add(plain(question))
        found, keys = read(question)
        if not any(keys):   # matched by a stored name or a verified answer: the reader never chose, nothing to teach it
            continue
        rows.append((question, origin, day, found, [k for k in keys if k][:CHOICES]))
    if args.generated:   # generated wordings Ask gets wrong, its target shown so the reviewer can confirm or correct it
        import ask_bench
        ask_bench.index_waves.update(visible)
        rng, docs, misses = random.Random(11), list(index.docs.values()), 0
        while misses < args.generated:
            doc = rng.choice(docs)
            case = ask_bench.make(doc, ask_bench.raws_for(doc["key"], index), index, rng)
            if not case or plain(case["text"]) in done:
                continue
            found, keys = read(case["text"])
            pick = found["sources"][0]["key"] if found.get("sources") else None
            # right, the same wording under another code (not the reader's mistake), or no reader choice at all
            if pick == case["key"] or (pick and plain(index.docs[pick]["text"]) == plain(case["doc_text"])) or not any(keys):
                continue
            done.add(plain(case["text"]))
            keys = [k for k in keys if k][:CHOICES]
            if case["key"] not in keys:   # the generator's answer always among the choices, last
                keys = keys[:CHOICES - 1] + [case["key"]]
            rows.append((case["text"], f"Generated (its answer: {index.docs[case['key']]['qcode']})", args.written_on, found, keys))
            misses += 1

    book = Workbook()
    sheet = book.active
    sheet.title = "Review"
    sheet.append(HEAD)
    for number, (question, origin, day, found, keys) in enumerate(rows, start=1):
        pick = found["sources"][0]["key"] if found.get("mode") == "figures" and found.get("sources") else None
        reading = ask_reader.read(question)
        sheet.append([number, question, origin, describe({**index.docs[pick], "key": pick}) if pick else "No answer: " + found.get("answer", "")[:120],
                      *[describe(index.docs[k]) for k in keys] + [""] * (CHOICES - len(keys)), None, None, None, None,
                      reading["country"], reading["kind"], day, pick, *keys + [None] * (CHOICES - len(keys))])
    style(sheet, len(rows))
    guide(book.create_sheet("How to fill", 0))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    book.save(args.out)
    print(f"{len(rows)} questions → {args.out}")


def style(sheet, count: int) -> None:
    """Readable columns, the reviewer's cells shaded, a list to pick the answer from, the key columns hidden."""
    widths = [6, 44, 22, 48] + [48] * CHOICES + [14, 16, 16, 30]
    for column, cells in enumerate(sheet.iter_cols(min_row=1, max_row=count + 1), start=1):
        letter = cells[0].column_letter
        if column <= len(widths):
            sheet.column_dimensions[letter].width = widths[column - 1]
        else:
            sheet.column_dimensions[letter].hidden = True
        for cell in cells:
            cell.font = Font(name="Arial", size=10, bold=cell.row == 1)
            cell.alignment = Alignment(wrap_text=True, vertical="top")
            if 10 <= column <= 13 and cell.row > 1:
                cell.fill = FILL
    choose = DataValidation(type="list", formula1='"' + ",".join(ANSWERS) + '"', allow_blank=True)
    sheet.add_data_validation(choose)
    choose.add(f"J2:J{count + 1}")
    sheet.freeze_panes = "C2"


def guide(sheet) -> None:
    lines = [
        ("How to fill the Review tab", True),
        ("Each row is a question someone might type into Ask CIP. Read it, then the five survey questions Ask's reader chose between (Choice 1-5).", False),
        ("Fill only the shaded columns:", False),
        ("Right answer: the number of the choice that answers the question; Pick when Ask's own answer (column D) is right; None when no survey question answers it; Other when the right one is not listed.", False),
        ("Other question code: with Other, the survey question code (for example q3 or TF3).", False),
        ("Also right: other choices that answer it just as well, for example the same question asked in another year: their numbers, such as 2,4.", False),
        ("Note: anything the team should know. Leave a row blank to skip it.", False),
        ("Example row (realistic values):", True),
        ("Question: Share of Gen Z buying clothing online · Right answer: 3 (q3 · Online purchases categories) · Other question code: (blank) · Also right: (blank) · Note: q3 has Gen Z figures every week", False),
        ("Questions from the golden and fresh test sets are never in this sheet: they decide whether the new reader ships.", False),
    ]
    sheet.column_dimensions["A"].width = 140
    for row, (text, bold) in enumerate(lines, start=1):
        cell = sheet.cell(row=row, column=1, value=text)
        cell.font = Font(name="Arial", size=11 if bold else 10, bold=bold)
        cell.alignment = Alignment(wrap_text=True)


def read(args) -> None:
    """The marked rows as reviewed labels: {q, key, also, country, kind, observed_at, group}; key null for None."""
    from api.ask_index import Index
    sheet = load_workbook(args.sheet, read_only=True)["Review"]
    head = None
    labels, problems, skipped = [], [], 0
    codes: dict[tuple[str, str], str] = {}
    for values in sheet.iter_rows(values_only=True):
        if head is None:
            head = list(values)
            continue
        row = dict(zip(head, values))
        answer = str(row["Right answer"] or "").strip()
        if not answer:
            skipped += 1
            continue
        keys = [row[f"key {n}"] for n in range(1, CHOICES + 1)]
        if answer not in ANSWERS:
            problems.append(f"row {row['No.']}: Right answer “{answer}” is not one of {', '.join(ANSWERS)}")
            continue
        if answer == "Other":
            if not codes:
                waves = json.loads(gzip.decompress((args.published / "waves.json.gz").read_bytes()))
                index = Index(args.published / "questions", waves)
                for k, d in sorted(index.docs.items(), key=lambda kv: kv[1]["waves"]):   # the longest-running last: it wins
                    codes[(d["family"], d["qcode"].lower())] = k
            family = "CSI-CN" if row["country"] == "CN" else "CSI-US"
            key = codes.get((family, str(row["Other question code"] or "").strip().lower()))
            if not key:
                problems.append(f"row {row['No.']}: Other needs a question code the published data has, got “{row['Other question code']}”")
                continue
        else:
            key = None if answer == "None" else row["pick key"] if answer == "Pick" else keys[int(answer) - 1]
            if answer not in ("None", "Pick") and not key:
                problems.append(f"row {row['No.']}: choice {answer} is empty")
                continue
        also = [keys[int(n) - 1] for n in re.findall(r"\d", str(row["Also right (choice numbers)"] or "")) if 1 <= int(n) <= CHOICES and keys[int(n) - 1]]
        labels.append({"q": row["Question"], "key": key, "also": [k for k in also if k != key], "country": row["country"],
                       "kind": row["kind"], "observed_at": str(row["observed_at"])[:10], "group": plain(row["Question"])})
    for problem in problems:
        print(problem)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("".join(json.dumps(label, ensure_ascii=False) + "\n" for label in labels), encoding="utf-8")
    print(f"{len(labels)} reviewed, {skipped} left blank, {len(problems)} to fix → {args.out}")
    if problems:
        sys.exit(1)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = ap.add_subparsers(dest="command", required=True)
    made = commands.add_parser("build")
    made.add_argument("--out", type=Path, required=True)
    made.add_argument("--asks", action="store_true", help="add the questions typed on staging (reads cip_access_log)")
    made.add_argument("--generated", type=int, default=140, help="generated questions Ask gets wrong")
    made.add_argument("--written-on", default=str(date.today()), help="the date of the generated and no-answer rows")
    marked = commands.add_parser("read")
    marked.add_argument("sheet", type=Path)
    marked.add_argument("--out", type=Path, required=True)
    for command in (made, marked):
        command.add_argument("--published", type=Path, default=PUBLISHED)
    args = ap.parse_args()
    (build if args.command == "build" else read)(args)


if __name__ == "__main__":
    main()
