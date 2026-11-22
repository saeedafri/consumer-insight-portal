"""Ask CIP v2 on Colab: more ways to say each survey question, a reader taught on lakhs of them, tested on lakhs more.

The one notebook (scripts/colab/ask_cip_v2.ipynb) runs these in order on a GPU runtime; each skips work already done, so
a disconnected run resumes. Every number Ask shows is still computed from the survey files: these steps only teach it
to find the right survey question for any wording (docs/research/Claude-Ask-architecture-2026-11-21.md).

    wordings   (this Mac, builds the bundle) one line per survey question wording: its text, name, answers, survey, asks
    expand     (GPU) an open model (Qwen3, by GPU size) writes PER analyst-style questions for each wording: doc2query,
               the vocabulary gap closed before anyone asks (Nogueira & Lin 2019)
    split      per wording, 60% become asks in config/ask_semantic.json (searched as Ask's second index, ask_index
               ASK_WEIGHT), 40% a question bank whose right answer is known: training and testing, never indexed
    embed      the asks' vectors, once, into Ask's vector cache (the shards and the replay reuse it)
    shards     ask_cip_train.py prepare over the bank in parallel processes, merged into one cases.jsonl
    teach      the shipped reader's scores on every case: the student learns from it as well as from the labels
    replay     the full Ask pipeline over the bank's held-out wordings (and the three real test sets) for a reader and
               a semantic layer: right-question accuracy by split and kind, lakhs of questions, parallel processes

Who calls it: the notebook; `wordings` by Claude on the Mac when the bundle is made. No paid model anywhere.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import random
import re
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "colab"))
BANK_FIELDS = ["question", "persona", "purpose", "kind", "country", "season", "name", "answer_key", "answer_question",
               "waves", "ms", "other_study", "understood", "got_key", "problem"]
STYLES = ("a 2-5 word keyword search", "a full question", "casual wording, as typed in a hurry, one small typo allowed",
          "about one answer option by its name", "about the top answers or a ranking", "for one group (Gen Z, millennials, "
          "boomers, women, men, high or low income, a region)", "for a time (latest, last month, this year, compared to "
          "last year, over time, trend)", "\"how is it doing\" or \"is it growing\" style")


def rows(path: Path):
    with (gzip.open(path, "rt", encoding="utf-8") if path.suffix == ".gz" else path.open(encoding="utf-8")) as source:
        for line in source:
            if line.strip():
                yield json.loads(line)


def plain(text: str) -> str:
    return " ".join(re.findall(r"[^\W_]+", text.lower()))


# a wording's answering instruction after its question ("? Select all that apply", "(select up to 3)"): the same question
# with and without it was counted wrong (Dollar Tree's online-grocery reasons, 22 Nov 2026)
INSTRUCTION = re.compile(r"(?:(?<=[?.])|\s\()\s*(?:please )?(?:select|choose|check|pick|mark)\b[^?]*$", re.I)


def same_question(one: str, other: str) -> bool:
    return plain(INSTRUCTION.sub("", one)) == plain(INSTRUCTION.sub("", other))


def wordings(args) -> None:
    """One line per survey question wording in the publication: what the model is told about it."""
    from api.ask_index import Index, digest
    waves = json.loads(gzip.decompress((args.published / "waves.json.gz").read_bytes()))
    index = Index(args.published / "questions", waves)
    seen: dict[str, dict] = {}
    for key, doc in sorted(index.docs.items(), key=lambda kd: -kd[1]["waves"]):   # the longest-running speaks for a wording
        entry = seen.setdefault(digest(doc["text"]), {"wkey": digest(doc["text"]), "text": doc["text"], "name": doc.get("name", ""),
                                                     "labels": doc.get("labels", [])[:20], "family": doc["family"],
                                                     "study": doc.get("title", ""), "first": doc["first"], "last": doc["last"],
                                                     "waves": doc["waves"], "cuts": sorted(doc.get("cuts", [])), "keys": [],
                                                     "asks": doc.get("asks", [])})
        entry["keys"].append(key)
    with gzip.open(args.out, "wt", encoding="utf-8") as out:
        for entry in seen.values():
            out.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"{len(seen)} wordings → {args.out}")


def prompt(entry: dict, per: int) -> str:
    china = entry["family"] == "CSI-CN"
    return (f"Survey question: \"{entry['text']}\"\nShort name: {entry['name'] or '-'}\n"
            f"Some answer options: {'; '.join(entry['labels'][:15]) or '-'}\n"
            f"Survey: {entry['study']}, {'China' if china else 'United States'}, asked {entry['waves']} time(s) from {entry['first']} to {entry['last']}.\n"
            f"Write {per} different questions a business analyst might type into a survey analytics tool that THIS survey "
            f"question answers. Spread them over these styles: {'; '.join(STYLES)}. "
            + ("Every question must mention China or Chinese consumers. " if china else "")
            + "Never copy the survey wording, never use survey codes, never ask for something this question cannot answer. "
              "Return only a JSON array of strings.")


def parse(text: str, limit: int) -> list[str]:
    """The questions in a model's reply: its JSON array, else its lines; numbering and quotes stripped, each once."""
    found = re.search(r"\[.*\]", text or "", re.S)
    try:
        items = json.loads(found.group(0)) if found else []
    except ValueError:
        items = []
    if not items:
        items = (text or "").splitlines()
    out, seen = [], set()
    for item in items:
        q = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", str(item)).strip().strip('",').strip()
        if 3 <= len(q) <= 200 and plain(q) and plain(q) not in seen:
            seen.add(plain(q))
            out.append(q)
    return out[:limit]


def expand(args) -> None:
    """PER questions for each wording from an open model on the GPU (vLLM), or a few made by rule (--model template:
    a dry run with no GPU). Resumes: wordings already in OUT are skipped."""
    done = {r["wkey"] for r in rows(args.out)} if args.out.exists() else set()
    todo = [e for e in rows(args.wordings) if e["wkey"] not in done][:args.limit or None]
    print(f"{len(done)} wordings done, {len(todo)} to write", flush=True)
    if not todo:
        return
    if args.model == "template":
        replies = [json.dumps([f"{e['name'] or e['text'][:60]}", f"{e['name'] or e['text'][:60]} latest",
                               f"{e['name'] or e['text'][:60]} by generation", f"How has {e['name'] or 'it'} changed over time?",
                               *[f"share who chose {a}" for a in e["labels"][:4]]]) for e in todo]
    else:
        import torch
        from vllm import LLM, SamplingParams
        memory = torch.cuda.get_device_properties(0).total_memory / 2 ** 30
        name = args.model if args.model != "auto" else "Qwen/Qwen3-14B" if memory >= 38 else "Qwen/Qwen3-8B" if memory >= 22 else "Qwen/Qwen3-4B"
        print(f"GPU {torch.cuda.get_device_name(0)} {memory:.0f} GB: {name}", flush=True)
        llm = LLM(model=name, dtype="bfloat16" if torch.cuda.is_bf16_supported() else "half", max_model_len=4096,
                  gpu_memory_utilization=0.9, seed=7)
        sampling = SamplingParams(temperature=0.8, top_p=0.95, max_tokens=3000, seed=7)
        messages = [[{"role": "system", "content": "You write the questions business analysts type, short and natural."},
                     {"role": "user", "content": prompt(e, args.per)}] for e in todo]
        replies = []
        for start in range(0, len(messages), 256):   # saved as it goes: a disconnect keeps the finished batches
            batch = llm.chat(messages[start:start + 256], sampling, chat_template_kwargs={"enable_thinking": False}, use_tqdm=False)
            part = [o.outputs[0].text for o in batch]
            with args.out.open("a", encoding="utf-8") as out:
                for entry, reply in zip(todo[start:start + 256], part):
                    out.write(json.dumps({"wkey": entry["wkey"], "questions": parse(reply, args.per)}, ensure_ascii=False) + "\n")
            print(f"{min(start + 256, len(todo))} of {len(todo)} wordings", flush=True)
        return
    with args.out.open("a", encoding="utf-8") as out:
        for entry, reply in zip(todo, replies):
            out.write(json.dumps({"wkey": entry["wkey"], "questions": parse(reply, args.per)}, ensure_ascii=False) + "\n")


def split(args) -> None:
    """Per wording, 60% of its new questions become asks (the semantic file Ask reads), 40% the bank (CSV, as
    docs/research/ask-question-bank.csv.gz), never both; existing asks kept."""
    from api import ask_reader
    entries = {e["wkey"]: e for e in rows(args.wordings)}
    semantic = json.loads(args.semantic.read_text())
    rng, bank, added = random.Random(7), [], 0
    for line in rows(args.expanded):
        entry = entries.get(line["wkey"])
        if not entry:
            continue
        known = {plain(entry["text"]), *(plain(a) for a in entry["asks"])}
        fresh = [q for q in line["questions"] if plain(q) not in known]
        rng.shuffle(fresh)
        cut = round(len(fresh) * 0.6)
        record = semantic.setdefault(entry["wkey"], {"name": entry["name"], "aliases": [], "topic": "", "text": entry["text"]})
        record["asks"] = list(dict.fromkeys(record.get("asks", []) + fresh[:cut]))
        added += cut
        country = "CN" if entry["family"] == "CSI-CN" else "US"
        for q in fresh[cut:]:
            bank.append({**dict.fromkeys(BANK_FIELDS, ""), "question": q, "persona": "generated", "purpose": "v2",
                         "kind": ask_reader.read(q)["kind"], "country": country, "name": entry["name"],
                         "answer_key": entry["keys"][0], "answer_question": entry["text"], "waves": entry["waves"]})
    args.semantic_out.write_text(json.dumps(semantic, ensure_ascii=False, indent=0))
    with gzip.open(args.bank_out, "wt", encoding="utf-8", newline="") as out:
        writer = csv.DictWriter(out, BANK_FIELDS)
        writer.writeheader()
        writer.writerows(bank)
    print(f"{added} asks added → {args.semantic_out}; {len(bank)} bank questions → {args.bank_out}")


def embed(args) -> None:
    """Every survey question and ask embedded once into Ask's vector cache (api/ask_model.py VECTORS)."""
    from api.ask_index import Index
    waves = json.loads(gzip.decompress((args.published / "waves.json.gz").read_bytes()))
    started = time.time()
    index = Index(args.published / "questions", waves)
    index.add_vectors()
    print(f"{len(index.vector_keys)} questions, {0 if index.ask_vectors is None else len(index.ask_vectors)} asks with vectors "
          f"in {time.time() - started:.0f} s")


def shards(args) -> None:
    """ask_cip_train.py prepare over the bank in WORKERS processes (the reviewed file in each, so all reserve the same
    later groups), one cases.jsonl: a question in two shards (each reviewed one) is kept once; the report's counts summed."""
    bank = list(csv.DictReader(gzip.open(args.bank, "rt", encoding="utf-8")))
    random.Random(7).shuffle(bank)
    args.output.mkdir(parents=True, exist_ok=True)
    jobs = []
    for n in range(args.workers):
        part, out = args.output / f"bank-{n}.csv.gz", args.output / f"shard-{n}"
        if (out / "dataset-report.json").exists():
            continue
        with gzip.open(part, "wt", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, BANK_FIELDS)
            writer.writeheader()
            writer.writerows(bank[n::args.workers])
        command = [sys.executable, str(ROOT / "scripts/colab/ask_cip_train.py"), "prepare", "--train-published", str(args.train_published),
                   "--test-published", str(args.test_published), "--output", str(out), "--bank", str(part)]
        if args.expert:   # every shard: each reserves the groups reviewed after the cutoff, or a group leaks into train
            command += ["--expert", str(args.expert)]
        if out.exists():   # a shard stopped half-way: prepare wants a new folder
            subprocess.run(["rm", "-rf", str(out)], check=True)
        jobs.append(subprocess.Popen(command, stdout=open(args.output / f"shard-{n}.log", "w"), stderr=subprocess.STDOUT))
    for job in jobs:
        if job.wait():
            raise SystemExit(f"a shard failed: see {args.output}/shard-*.log")
    seen, reports = set(), []
    with (args.output / "cases.jsonl").open("w", encoding="utf-8") as merged:
        for n in range(args.workers):
            reports.append(json.loads((args.output / f"shard-{n}" / "dataset-report.json").read_text()))
            for case in rows(args.output / f"shard-{n}" / "cases.jsonl"):
                if plain(case["question"]) not in seen:
                    seen.add(plain(case["question"]))
                    merged.write(json.dumps(case, ensure_ascii=False, separators=(",", ":")) + "\n")
    from ask_cip_train import digest_file, write_json
    counts: dict[str, int] = {}
    for report in reports:
        for key, value in report["source_counts"].items():
            counts[key] = counts.get(key, 0) + value
    write_json(args.output / "dataset-report.json", {**reports[0], "source_counts": counts, "bank": args.bank.name,
                                                    "cases_sha256": digest_file(args.output / "cases.jsonl")})
    print(f"{len(seen)} cases → {args.output / 'cases.jsonl'}: {counts}")


def teacher_setup(baseline: str) -> None:
    global SCORE
    from ask_cip_train import onnx_reader
    SCORE = onnx_reader(Path(baseline))[0].score


def teacher_scores(case: dict) -> list[float] | None:
    return [round(float(x), 4) for x in SCORE(case["question"], case["candidates"])] if case["candidates"] else None


def teach(args) -> None:
    """The shipped reader's logits (none first) on each case with candidates, in WORKERS processes: the student's second
    target (ask_cip_train.py train --teacher-weight)."""
    from ask_cip_train import digest_file, write_json
    cases = list(rows(args.cases))
    with ProcessPoolExecutor(args.workers, initializer=teacher_setup, initargs=(str(args.baseline),)) as pool:
        scores = list(pool.map(teacher_scores, cases, chunksize=256))
    out = args.cases.with_name("cases-taught.jsonl")
    with out.open("w", encoding="utf-8") as stream:
        for case, score in zip(cases, scores):
            if score is not None:
                case["teacher"] = score
            stream.write(json.dumps(case, ensure_ascii=False, separators=(",", ":")) + "\n")
    out.replace(args.cases)   # the same cases, a teacher added: the report's digest follows them
    report = args.cases.with_name("dataset-report.json")
    write_json(report, {**json.loads(report.read_text()), "cases_sha256": digest_file(args.cases)})
    print(f"{sum(s is not None for s in scores)} of {len(cases)} cases taught")


def worker_setup(published: str, semantic: str) -> None:
    global INDEX, VISIBLE
    from api import ask_index
    ask_index.SEMANTIC = Path(semantic)
    ask_index.SEMANTIC_ADDED = Path("/nonexistent")
    waves = json.loads(gzip.decompress((Path(published) / "waves.json.gz").read_bytes()))
    INDEX = ask_index.Index(Path(published) / "questions", waves)
    INDEX.add_vectors()
    INDEX.verified_for = lambda _: None
    VISIBLE = {w["survey_id"] for w in waves}


def ask_one(item: dict) -> dict:
    """One bank question through the whole of Ask (quick, no AI): right when it answers from the generator's question or
    one with the same wording."""
    from api import assistant
    started = time.perf_counter()
    try:
        found = assistant.answer(item["question"], INDEX, VISIBLE, True)
    except Exception as exc:   # noqa: BLE001  counted, never stops a lakh-question run
        return {**item, "got": None, "right": False, "error": type(exc).__name__, "ms": 0}
    got = found["sources"][0]["key"] if found.get("mode") == "figures" and found.get("sources") else None
    right = got in INDEX.docs and same_question(INDEX.docs[got]["text"], item["answer_question"])
    return {**item, "got": got, "right": right, "ms": round(1000 * (time.perf_counter() - started))}


def replay(args) -> None:
    """The bank through Ask with this reader and semantic file, in WORKERS processes: accuracy overall, by split (the
    reader's train/dev/test buckets, ask_cip_train.py bucket) and by kind; the three real test sets through
    scripts/ask_golden.py too. Writes REPORT and every miss."""
    from ask_cip_train import bucket, normalize
    os.environ.update(CIP_ASK_READER_DIR=str(args.reader), CIP_ASK_SEMANTIC=str(args.semantic))
    bank = list(csv.DictReader(gzip.open(args.bank, "rt", encoding="utf-8")))
    random.Random(11).shuffle(bank)
    bank = bank[:args.limit or None]
    started = time.time()
    with ProcessPoolExecutor(args.workers, initializer=worker_setup, initargs=(str(args.published), str(args.semantic))) as pool:
        results = list(pool.map(ask_one, bank, chunksize=64))
    report: dict = {"reader": str(args.reader), "semantic": str(args.semantic), "questions": len(results),
                    "seconds": round(time.time() - started)}
    for name, test in [("all", lambda r: True)] + [(s, lambda r, s=s: bucket(r["country"] + "|" + normalize(r["answer_question"])) == s)
                                                    for s in ("train", "dev", "test")]:
        chosen = [r for r in results if test(r)]
        report[name] = {"questions": len(chosen), "right": sum(r["right"] for r in chosen),
                        "share": round(sum(r["right"] for r in chosen) / max(1, len(chosen)), 4)}
    for kind in sorted({r["kind"] for r in results}):
        chosen = [r for r in results if r["kind"] == kind]
        report[f"kind/{kind}"] = round(sum(r["right"] for r in chosen) / max(1, len(chosen)), 4)
    for sheet in ("ask_golden.yml", "ask_fresh.yml", "ask_researched.yml"):
        done = subprocess.run([sys.executable, str(ROOT / "scripts/ask_golden.py"), "--quick", "--questions", str(ROOT / "scripts" / sheet),
                               "--published", str(args.published)], capture_output=True, text=True,
                              env={**os.environ, "PYTHON_DOTENV_DISABLED": "1"})
        report[sheet] = next((line for line in done.stdout.splitlines() if "right (" in line), done.stderr[-300:])
    args.report.write_text(json.dumps(report, indent=1))
    with gzip.open(args.report.with_suffix(".misses.jsonl.gz"), "wt", encoding="utf-8") as out:
        for r in results:
            if not r["right"]:
                out.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(json.dumps(report, indent=1))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    steps = ap.add_subparsers(dest="step", required=True)
    s = steps.add_parser("wordings"); s.add_argument("--published", type=Path, required=True); s.add_argument("--out", type=Path, required=True)
    s = steps.add_parser("expand"); s.add_argument("wordings", type=Path); s.add_argument("--out", type=Path, required=True)
    s.add_argument("--per", type=int, default=48); s.add_argument("--model", default="auto"); s.add_argument("--limit", type=int, default=0)
    s = steps.add_parser("split")
    for name in ("wordings", "expanded", "semantic", "semantic-out", "bank-out"):
        s.add_argument(f"--{name}", type=Path, required=True)
    s = steps.add_parser("embed"); s.add_argument("--published", type=Path, required=True)
    s = steps.add_parser("shards")
    for name in ("bank", "train-published", "test-published", "output"):
        s.add_argument(f"--{name}", type=Path, required=True)
    s.add_argument("--expert", type=Path); s.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    s = steps.add_parser("teach"); s.add_argument("--cases", type=Path, required=True); s.add_argument("--baseline", type=Path, required=True)
    s.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    s = steps.add_parser("replay")
    for name in ("bank", "published", "reader", "semantic", "report"):
        s.add_argument(f"--{name}", type=Path, required=True)
    s.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1)); s.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    {"wordings": wordings, "expand": expand, "split": split, "embed": embed, "shards": shards, "teach": teach, "replay": replay}[args.step](args)


if __name__ == "__main__":
    main()
