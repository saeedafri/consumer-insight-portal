"""Build and score a small Ask CIP reader on approved published survey metadata.

Run prepare in the CIP checkout, preflight on CPU, then train with the same cases and
the current models/ask-reader folder. No command sends requests to a paid model.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import date
import gzip
from hashlib import file_digest, sha256
from itertools import chain
import json
from math import isfinite, sqrt
import os
from pathlib import Path
import platform
import random
import re
import shutil
import sys
import tempfile
import time
import unicodedata
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent.parent.parent
BASE_MODEL = "cross-encoder/ms-marco-MiniLM-L6-v2"
BASE_REVISION = "233902d25c440f23af6f7d6e94d2946bac0bee0a"
MAX_TOKENS = 192
SPLITS = ("train", "dev", "test", "future")
READER_FILES = ("model_optimized.onnx", "tokenizer.json", "calibration.json")
# Even perfect results need 35 distinct decisions to clear the existing 90% Wilson
# calibration bound. The test and future minimums justify a pilot, not a release.
MIN_REVIEWED_GROUPS = {"dev": 35, "test": 30, "future": 30}


def normalize(text):
    """Group spelling punctuation and Unicode differences without stripping place names or dates."""
    return " ".join(re.findall(r"[^\W_]+", unicodedata.normalize("NFKC", text).casefold()))


def bucket(group):
    """Keep all paraphrases of a source question in the same stable split."""
    value = int.from_bytes(sha256(group.encode()).digest()[:4], "big") % 100
    return "test" if value < 15 else "dev" if value < 30 else "train"


def rows(path):
    """Stream reviewed inputs or exported cases so the whole question bank need not fit in RAM."""
    with path.open(encoding="utf-8") as source:
        for line in source:
            if line.strip():
                yield json.loads(line)


def write_json(path, data):
    """Write a readable report beside the candidate."""
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def training_question(data, allowed):
    """Keep only authorized wave rows and metadata those rows actually reference."""
    waves = {i: wave for i, wave in enumerate(data["waves"]) if wave[0] in allowed}
    cells = [i for i, wave in enumerate(data["w"]) if wave in waves]
    if not cells:
        return None
    versions = sorted({wave[2] for wave in waves.values()})
    answers = sorted({data["a"][i] for i in cells})
    cuts = sorted({data["c"][i] for i in cells})
    wave_index = {w: i for i, w in enumerate(waves)}
    version_index = {v: i for i, v in enumerate(versions, 1)}
    answer_index = {a: i for i, a in enumerate(answers)}
    cut_index = {c: i for i, c in enumerate(cuts)}
    return {
        "qcode": data["qcode"],
        "waves": [[sid, day, version_index[version]] for sid, day, version in waves.values()],
        "versions": [data["versions"][i - 1] for i in versions],
        "answers": [data["answers"][i] for i in answers],
        "cuts": [data["cuts"][i] for i in cuts],
        "w": [wave_index[data["w"][i]] for i in cells],
        "c": [cut_index[data["c"][i]] for i in cells],
        "a": [answer_index[data["a"][i]] for i in cells],
        "n": [data["n"][i] for i in cells],
        "b": [data["b"][i] for i in cells],
    }


def prepare(args):
    """Record the shipping reader's candidate lines locally, using two approved publications."""
    def publication(path):
        """Pin the generation and check that reused codes keep their own answer labels."""
        path = path.resolve()
        try:
            rules = json.loads((path.parents[1] / "manifest.json").read_text(encoding="utf-8")).get("rules", {})
            fixed_labels = rules.get("answer_labels") == 1
        except (OSError, ValueError, AttributeError, IndexError):
            fixed_labels = False
        if not fixed_labels:
            raise SystemExit(f"Rebuild the publication for {path} before exporting training cases. "
                             "Its manifest must confirm the per-question answer label fix (rules.answer_labels=1).")
        return path

    older = publication(args.train_published)
    newer = publication(args.test_published)
    sys.path.insert(0, str(ROOT))
    with patch.dict(os.environ, {"PYTHON_DOTENV_DISABLED": "1"}):
        from api import ask_index, ask_model, ask_reader, assistant

    def load(path, target):
        with gzip.open(path / "waves.json.gz", "rt") as incoming:
            waves = [w for w in json.load(incoming) if w["survey_family"] in args.families
                     and w.get("visibility") == "all" and not w.get("client")]
        if not waves:
            raise SystemExit(f"No eligible waves in {path}")
        allowed = {w["survey_id"] for w in waves}
        source = path / "questions"
        for family in args.families:
            for file in (source / family).glob("*/*.json.gz"):
                filtered = training_question(json.loads(gzip.decompress(file.read_bytes())), allowed)
                if filtered is None:
                    continue
                out = target / file.relative_to(source)
                out.parent.mkdir(parents=True, exist_ok=True)
                with gzip.open(out, "wt", compresslevel=1, encoding="utf-8") as staged:
                    json.dump(filtered, staged, separators=(",", ":"))
        index = ask_index.Index(target, waves)
        index.add_vectors()
        if not index.vector_keys:
            raise SystemExit(f"Search encoder missing or unusable: {ask_model.EMBED_DIR}")
        return index, max(str(w["wave_date"])[:10] for w in waves)

    def key_for(item, index):
        """A generated item must resolve to the same survey wording and country in this snapshot."""
        if item["source"] == "reviewed":
            key = item["key"]
            if key not in index.docs:
                return None
            choices = [key]
        else:
            wanted = normalize(item["answer_question"])
            choices = words_to_keys[id(index)].get(wanted, [])
        allowed = [key for key in choices if item["country"] in
                   {index.country[s] for s in index.docs[key]["surveys"]}]
        if item["key"] in allowed:
            return item["key"]
        return allowed[0] if len(allowed) == 1 else None

    def record(index, question, country, correct_key, none, split, also=()):
        """The question as Ask's reader sees it, its candidate lines, and which of them are right: the reviewed key and
        any the reviewer marked also right (the same question another year), so a twin is never taught as wrong."""
        candidates = []

        def capture(text, listed):
            nonlocal question
            question = text
            candidates.extend(listed)
            raise Recorded

        class Recorded(Exception):
            pass

        try:
            with patch.object(ask_model, "read_pick", capture):
                assistant.answer(question, index, set(index.country), quick=True)
        except Recorded:
            pass
        relevant, lines = ([0] if none else []), []
        targets = [index.docs[k] for k in (correct_key, *also) if k in index.docs]
        for candidate in candidates:
            group = country + "|" + normalize(candidate["text"])
            if split == "train" and (bucket(group) != "train" or group in reserved):
                continue
            lines.append(ask_model.describe_candidate(candidate))
            if any(all(candidate[f] == target[f] for f in ("text", "waves", "first", "last", "name")) for target in targets):
                relevant.append(len(lines))
        return question, lines, relevant

    def review_inputs():
        if args.expert:
            for item in rows(args.expert):
                required = {"q", "key", "country", "kind", "observed_at"}
                missing = required - item.keys()
                if missing or not normalize(item["q"]):
                    raise SystemExit(f"Invalid reviewed label. Missing fields: {sorted(missing)}")
                if item["key"] is None and not normalize(item.get("group", "")):
                    raise SystemExit("A reviewed no-answer row needs a group shared by its paraphrases")
                date.fromisoformat(item["observed_at"])
                yield {**item, "source": "reviewed"}

    def practice_inputs():
        with gzip.open(args.bank, "rt", encoding="utf-8", newline="") as source:
            for item in csv.DictReader(source):
                yield {**item, "q": item["question"], "key": item["answer_key"], "source": "generated"}

    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="cip-reader-export-") as directory:
        scratch = Path(directory)
        vector_copy = scratch / "vectors.npz"
        if ask_model.VECTORS.exists():
            shutil.copyfile(ask_model.VECTORS, vector_copy)
        with (
            patch.object(ask_model, "VECTORS", vector_copy),
            patch.object(ask_model, "LOGS", scratch),
            patch.object(ask_model, "SPEND", scratch / "spend.json"),
            patch.object(ask_model, "ready", return_value=False),
            patch.object(ask_index, "SEMANTIC_ADDED", scratch / "semantics.json"),
            patch.object(ask_index.Index, "load_verified", return_value=None),
        ):
            old, cutoff = load(older, scratch / "older")
            new, through = load(newer, scratch / "newer")
            if through <= cutoff:
                raise SystemExit("The test publication must contain a later eligible wave")
            words_to_keys = {}
            for index in (old, new):
                lookup = {}
                for key, doc in index.docs.items():
                    lookup.setdefault(normalize(doc["text"]), []).append(key)
                words_to_keys[id(index)] = lookup
                index.verified_for = lambda _: None
            older_groups = {old.country[s] + "|" + normalize(d["text"]) for d in old.docs.values() for s in d["surveys"]}
            reviewed = list(review_inputs())
            reserved = set()
            for item in reviewed:
                if item["observed_at"] > cutoff:
                    key = key_for(item, new)
                    source_text = item["group"] if item["key"] is None else new.docs[key]["text"] if key else ""
                    if source_text:
                        reserved.add(item["country"] + "|" + normalize(source_text))

            stats = Counter()
            seen = set()
            with (args.output / "cases.jsonl").open("w", encoding="utf-8") as output:
                for item in chain(reviewed, practice_inputs()):
                    if args.limit and sum(stats[k] for k in ("train", "dev", "test", "future")) >= args.limit:
                        break
                    country = item["country"]
                    if ask_reader.read(item["q"])["country"] != country:
                        stats["country_not_expressed"] += 1
                        continue
                    fingerprint = normalize(item["q"])
                    if fingerprint in seen:
                        stats["duplicate_wording"] += 1
                        continue
                    none = item["source"] == "reviewed" and item["key"] is None
                    key = None if none else key_for(item, new)
                    if not none and key is None:
                        stats["unmapped_label"] += 1
                        continue
                    group = country + "|" + (normalize(item["group"]) if none else normalize(new.docs[key]["text"]))
                    appeared = group in older_groups
                    future = (not none and not appeared) or item.get("observed_at", "") > cutoff or group in reserved
                    split = "future" if future else bucket(group)
                    index = new if split in {"test", "future"} else old
                    index_key = None if none else key_for(item, index)
                    if index_key and normalize(index.docs[index_key]["text"]) != group.split("|", 1)[1]:
                        stats["changed_wording"] += 1
                        continue
                    question, candidates, answers = record(index, item["q"], country, index_key, none, split,
                                                           () if none else item.get("also", ()))
                    if not candidates:
                        stats["reader_not_reached"] += 1
                    if split == "train" and (not candidates or not answers):
                        stats["untrainable"] += 1
                        continue
                    corrected = normalize(question)
                    if corrected in seen:
                        stats["duplicate_after_spelling"] += 1
                        continue
                    seen.update((fingerprint, corrected))
                    data = {"question": question, "candidates": candidates, "acceptable": answers, "split": split,
                            "group": sha256(group.encode()).hexdigest()[:20], "kind": item["kind"],
                            "country": country, "source": item["source"], "no_answer": none,
                            "observed_at": item.get("observed_at"),
                            "source_through": index.docs[index_key]["last"] if index_key else None}
                    output.write(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n")
                    stats[split] += 1
                    stats[f"{split}/{item['source']}/{country}"] += 1
    write_json(args.output / "dataset-report.json", {"train_through": cutoff, "test_through": through,
        "eligible_families": args.families, "source_counts": dict(stats), "bank": args.bank.name,
        "cases_sha256": digest_file(args.output / "cases.jsonl"),
        "holdout_warning": "Generated questions and existing semantic aliases are weak evidence. Reserve new reviewed cases for release."})
    print(dict(stats))


def onnx_reader(folder):
    """Call the same single-threaded ONNX reader format as Ask CIP."""
    import numpy as np
    import onnxruntime
    from tokenizers import Tokenizer

    settings = json.loads((folder / "calibration.json").read_text())
    tokens = Tokenizer.from_file(str(folder / "tokenizer.json"))
    tokens.enable_truncation(settings.get("length", MAX_TOKENS))
    pad = settings.get("pad_token", "[PAD]")
    tokens.enable_padding(pad_id=tokens.token_to_id(pad) or 0, pad_token=pad)
    opts = onnxruntime.SessionOptions()
    opts.intra_op_num_threads = opts.inter_op_num_threads = 1
    model = onnxruntime.InferenceSession(str(folder / "model_optimized.onnx"), opts, providers=["CPUExecutionProvider"])
    inputs = {i.name for i in model.get_inputs()}

    def predict(question, candidates):
        if not candidates:
            return 0, 0.0
        pairs = tokens.encode_batch([(question, line) for line in candidates])
        values = {"input_ids": "ids", "attention_mask": "attention_mask", "token_type_ids": "type_ids"}
        feed = {name: np.asarray([getattr(pair, field) for pair in pairs], dtype=np.int64)
                for name, field in values.items() if name in inputs}
        scores = model.run(None, feed)[0].reshape(-1)
        if len(scores) != len(candidates) or not np.isfinite(scores).all():
            raise ValueError("Reader must return one finite score per candidate")
        logits = np.concatenate([[0.0], scores])
        best, second = np.argsort(-logits)[:2]
        return int(best), float(logits[best] - logits[second])

    return predict, float(settings["sure"])


def validated_cases(cases):
    """Yield cases after checking JSONL shape, question uniqueness, and group isolation."""
    groups, questions = {}, set()
    for number, item in enumerate(rows(cases), 1):
        if not isinstance(item, dict) or not isinstance(item.get("question"), str):
            raise ValueError(f"Missing question at case {number}")
        split, group, answers = item.get("split"), item.get("group"), item.get("acceptable")
        question = normalize(item["question"])
        fingerprint = sha256(question.encode()).digest()[:16]
        if (split not in SPLITS or not question or not isinstance(group, str) or not group
                or fingerprint in questions or groups.setdefault(group, split) != split):
            raise ValueError(f"Duplicate question, split leak or invalid split at case {number}")
        candidates, no_answer = item.get("candidates"), item.get("no_answer")
        if not isinstance(candidates, list) or any(not isinstance(text, str) or not text.strip() for text in candidates):
            raise ValueError(f"Invalid candidate lines at case {number}")
        if (not isinstance(answers, list) or type(no_answer) is not bool
                or no_answer and (len(answers) != 1 or type(answers[0]) is not int or answers[0] != 0)
                or not no_answer and any(type(answer) is not int or not 1 <= answer <= len(candidates) for answer in answers)):
            raise ValueError(f"Invalid acceptable candidates at case {number}")
        questions.add(fingerprint)
        yield item


def validate_splits(cases):
    """Count cases by split and preserve the command-line error for invalid inputs."""
    try:
        return Counter(item["split"] for item in validated_cases(cases))
    except ValueError as error:
        raise SystemExit(str(error)) from error


def preflight(cases, baseline, *, compatibility_only=False):
    """Check evidence and identify input artifacts without importing training libraries."""
    dataset_path = cases.with_name("dataset-report.json")
    splits = {split: Counter() for split in SPLITS}
    reviewed = {split: set() for split in SPLITS}
    later_groups = set()
    blocking = []
    artifacts = {}
    dataset = {}
    cases_sha256 = None
    cutoff = through = None
    try:
        cases_sha256 = digest_file(cases)
        if dataset_path.is_file():
            source = json.loads(dataset_path.read_text(encoding="utf-8"))
            if not isinstance(source, dict):
                raise ValueError("dataset-report.json must be an object.")
            dataset = {field: source[field] for field in ("train_through", "test_through", "cases_sha256")
                       if field in source}
            if dataset.get("cases_sha256") not in (None, cases_sha256):
                raise ValueError("dataset-report.json describes a different case file.")
            if dataset.get("train_through") and dataset.get("test_through"):
                cutoff = date.fromisoformat(dataset["train_through"])
                through = date.fromisoformat(dataset["test_through"])
        for item in validated_cases(cases):
            if item.get("source") not in ("generated", "reviewed") or not item.get("country") or not item.get("kind"):
                raise ValueError("Every case needs its reviewed/generated source, country and kind.")
            split = item["split"]
            stats = splits[split]
            reached = bool(item["candidates"])
            usable = bool(reached and item["acceptable"])
            stats["cases"] += 1
            stats["candidate_pairs"] += len(item["candidates"])
            stats["reader_reached"] += reached
            stats["target_in_candidates"] += usable and not item["no_answer"]
            stats["no_answer"] += item["no_answer"]
            stats["unusable"] += not usable
            if item["source"] == "reviewed":
                stats["reviewed_cases"] += 1
                if usable:
                    reviewed[split].add(item["group"])
                    stats["reviewed_usable"] += 1
                    stats["reviewed_no_answer"] += item["no_answer"]
                    stats["reviewed_target_in_candidates"] += not item["no_answer"]
                    if split == "future" and cutoff and through and item.get("source_through") and not item["no_answer"]:
                        if cutoff < date.fromisoformat(item["source_through"]) <= through:
                            later_groups.add(item["group"])

    except (OSError, TypeError, ValueError) as error:
        blocking.append(f"Case evidence could not be validated. {error}")

    for name in READER_FILES:
        path = baseline / name
        try:
            size = path.stat().st_size
            if not path.is_file() or not size:
                raise ValueError("file is missing or empty")
            if name.endswith(".json"):
                content = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(content, dict):
                    raise ValueError("expected a JSON object")
                if name == "calibration.json" and not isfinite(float(content.get("sure", "nan"))):
                    raise ValueError("expected a finite reader threshold")
                if name == "tokenizer.json" and not isinstance(content.get("model"), dict):
                    raise ValueError("expected a tokenizer model")
            artifacts[name] = {"bytes": size, "sha256": digest_file(path)}
        except (OSError, TypeError, ValueError) as error:
            blocking.append(f"Shipped reader artifact {name} could not be validated. {error}")

    train = splits["train"]
    if not train["cases"] - train["unusable"]:
        blocking.append("Add training cases with a reachable target or a reviewed no-answer decision.")
    if not any(splits[s]["reader_reached"] for s in ("test", "future")):
        blocking.append("Add held-out cases that reach the reader.")
    if not compatibility_only:
        if not cutoff or not through or through <= cutoff or dataset.get("cases_sha256") != cases_sha256:
            blocking.append("Regenerate the cases with prepare to bind them to earlier and later publication dates.")
        for split, minimum in MIN_REVIEWED_GROUPS.items():
            if len(reviewed[split]) < minimum:
                blocking.append(f"{split} needs at least {minimum} distinct reviewed groups usable by the reader; found {len(reviewed[split])}.")
        for split in ("dev", "test"):
            if not (splits[split]["reviewed_target_in_candidates"] and splits[split]["reviewed_no_answer"]):
                blocking.append(f"{split} needs both reviewed answerable targets and no-answer examples that reach the reader.")
        if not later_groups:
            blocking.append("future needs a reviewed answerable target present in the candidates and backed by a later publication.")

    for split, stats in splits.items():
        stats["reviewed_usable_groups"] = len(reviewed[split])
    return {"ready": not blocking, "mode": "compatibility-only" if compatibility_only else "quality",
            "blocking_reasons": blocking, "cases_sha256": cases_sha256, "dataset": dataset,
            "baseline_artifacts": artifacts, "split_sizes": {split: stats["cases"] for split, stats in splits.items()},
            "splits": {split: dict(stats) for split, stats in splits.items()}, "later_reviewed_target_groups": len(later_groups),
            "scope": "CPU input checks for a reader experiment. Quality and latency still need independent replay."}


def evaluate(paths, cases):
    """Score the current and candidate readers on exactly the same rows and report misses separately."""
    import numpy as np

    baseline, baseline_sure = onnx_reader(paths[0])
    candidate, candidate_sure = onnx_reader(paths[1])
    stats, timings = {}, {}
    for item in rows(cases):
        if item["split"] == "train":
            continue
        results = []
        for run in (baseline, candidate) if item["candidates"] else ():
            started = time.perf_counter()
            pick, lead = run(item["question"], item["candidates"])
            results.append((pick, lead, (time.perf_counter() - started) * 1_000))
        for slice_name in (item["split"], f"{item['split']}/{item['source']}/{item['country']}/{item['kind']}"):
            counts = stats.setdefault(slice_name, Counter())
            times = timings.setdefault(slice_name, [[], []])
            counts["cases"] += 1
            counts["reached_reader"] += bool(item["candidates"])
            counts["answerable"] += bool(item["candidates"]) and not item["no_answer"]
            counts["candidate_present"] += bool(item["acceptable"]) and not item["no_answer"]
            counts["no_answer"] += bool(item["candidates"]) and item["no_answer"]
            if not results:
                continue
            for i, (pick, lead, elapsed) in enumerate(results):
                name = ("baseline", "candidate")[i]
                sure = (baseline_sure, candidate_sure)[i]
                right = pick in item["acceptable"]
                counts[f"{name}_correct"] += right
                if not item["no_answer"]:
                    counts[f"{name}_answerable_correct"] += right
                counts[f"{name}_false_answer"] += pick != 0 and not right
                counts[f"{name}_unsupported_accepted"] += item["no_answer"] and pick != 0
                counts[f"{name}_abstained"] += pick == 0
                if lead >= sure:
                    counts[f"{name}_confident"] += 1
                    counts[f"{name}_confident_correct"] += right
                times[i].append(elapsed)
            before, after = [p in item["acceptable"] for p, _, _ in results]
            counts["improved"] += after and not before
            counts["regressed"] += before and not after
    return {name: {**c, **{f"{model}_p95_ms": round(float(np.percentile(t, 95)), 2) if t else None
                         for model, t in zip(("baseline", "candidate"), timings[name])}} for name, c in stats.items()}


def calibrate(reader, cases):
    """Choose a lead threshold using only reviewed development rows and a conservative precision bound."""
    evidence = []
    for item in rows(cases):
        if item["split"] == "dev" and item["source"] == "reviewed" and item["candidates"]:
            pick, lead = reader(item["question"], item["candidates"])
            evidence.append((lead, pick in item["acceptable"]))
    evidence.sort(reverse=True)
    minimum = 1_000_000.0
    right = 0
    for count, (lead, correct) in enumerate(evidence, 1):
        right += correct
        if count < 30 or (count < len(evidence) and evidence[count][0] == lead):
            continue
        proportion = right / count
        z = 1.96
        lower = (proportion + z**2 / (2 * count) - z * sqrt(
            proportion * (1 - proportion) / count + z**2 / (4 * count**2)
        )) / (1 + z**2 / count)
        if lower >= 0.9:
            minimum = lead
    return minimum, len(evidence)


def train(args):
    """Fine-tune one CPU-serving student with a fixed zero logit for no matching survey question."""
    evidence = preflight(args.cases, args.baseline, compatibility_only=args.compatibility_only)
    if not evidence["ready"]:
        raise SystemExit("Training paused. " + " ".join(evidence["blocking_reasons"]))
    if args.output.exists():
        raise SystemExit("The candidate folder already exists. Choose an empty destination or use the existing result.")

    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    from onnxruntime.quantization import QuantType, quantize_dynamic

    cpu = args.cpu or args.compatibility_only
    if not cpu and not torch.cuda.is_available():
        raise SystemExit("Choose a GPU Colab runtime or pass --cpu to train on the CPU.")
    device = "cpu" if cpu else "cuda"
    if device == "cpu":
        torch.set_num_threads(1)
    # Check the shipped reader before downloading the training model or using the GPU.
    example = next(item for item in rows(args.cases) if item["candidates"])
    onnx_reader(args.baseline)[0](example["question"], example["candidates"])
    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    write_json(args.output / "preflight-report.json", evidence)
    torch.manual_seed(17)
    revision = args.revision or (BASE_REVISION if args.base_model == BASE_MODEL else None)
    tok = AutoTokenizer.from_pretrained(args.base_model, revision=revision)
    model = AutoModelForSequenceClassification.from_pretrained(args.base_model, revision=revision, num_labels=1).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-5)

    def make_batch(batch):
        query = [row["question"] for row in batch for _ in row["candidates"]]
        candidates = [line for row in batch for line in row["candidates"]]
        return tok(query, candidates, truncation=True, max_length=MAX_TOKENS, padding=True, return_tensors="pt").to(device)

    def steps(epoch):
        # Shuffle windows so millions of prepared rows can be read sequentially from disk.
        generator = random.Random(17 + epoch)
        pending = []
        for case in rows(args.cases):
            if case["split"] == "train" and case["acceptable"] and case["candidates"]:
                pending.append(case)
            if len(pending) >= 32 * args.batch:
                generator.shuffle(pending)
                yield from (pending[n:n + args.batch] for n in range(0, len(pending), args.batch))
                pending = []
        generator.shuffle(pending)
        yield from (pending[n:n + args.batch] for n in range(0, len(pending), args.batch))

    for epoch in range(args.epochs):
        model.train()
        total_loss = batches = 0
        for batch in steps(epoch):
            scores = model(**make_batch(batch)).logits.flatten()
            losses = []
            for row, logits in zip(batch, scores.split([len(item["candidates"]) for item in batch])):
                logits = torch.cat((scores.new_zeros(1), logits)).float()
                truths = logits[row["acceptable"]]
                losses.append(torch.logsumexp(logits, 0) - torch.logsumexp(truths, 0))
            loss = torch.stack(losses).mean()
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            total_loss += loss.item()
            batches += 1
        if not batches:
            raise SystemExit("No trainable rows. Widen the eligible dataset and inspect dataset-report.json.")
        print(f"epoch {epoch + 1}: {batches} batches, mean loss {total_loss / batches:.4f}", flush=True)

    model.cpu().eval()
    tok.save_pretrained(args.output)
    sample = tok(["What share shopped?"], ["Where did consumers shop?"], return_tensors="pt")
    names = list(sample.keys())
    # Matching dynamic dimensions allow Ask to run a variable number and length of candidates.
    with tempfile.TemporaryDirectory(prefix="cip-onnx-") as folder:
        plain = Path(folder) / "reader.onnx"
        torch.onnx.export(model, (), str(plain), kwargs=dict(sample), input_names=names, output_names=["logits"],
                          dynamic_axes={**{n: {0: "items", 1: "tokens"} for n in names}, "logits": {0: "items"}},
                          opset_version=17, dynamo=False)
        quantize_dynamic(plain, args.output / "model_optimized.onnx", weight_type=QuantType.QInt8)

    calibration = {"length": MAX_TOKENS, "sure": 1_000_000.0, "pad_token": tok.pad_token,
                   "made": Path(args.base_model).name, "revision": revision or model.config._commit_hash, "epochs": args.epochs}
    write_json(args.output / "calibration.json", calibration)
    # Unreviewed practice cases must not make the candidate seem safe to bypass a model check.
    fitted, reviewed_cases = calibrate(onnx_reader(args.output)[0], args.cases)
    write_json(args.output / "calibration.json", {**calibration, "sure": fitted, "reviewed_dev_cases": reviewed_cases})
    report = evaluate((args.baseline, args.output), args.cases)
    write_json(args.output / "paired-report.json", {"resource": device, "trained_epochs": args.epochs,
        "host": platform.platform(), "torch": str(torch.__version__),
        "model_bytes": (args.output / "model_optimized.onnx").stat().st_size,
        "cases_sha256": evidence["cases_sha256"], "split_sizes": evidence["split_sizes"], "slices": report,
        "baseline_sha256": evidence["baseline_artifacts"]["model_optimized.onnx"]["sha256"], "mode": evidence["mode"],
        "scope": "Fixed candidate lists and CPU ONNX timing; run full Ask replay before any promotion."})
    print(json.dumps({k: v for k, v in report.items() if "/" not in k}, indent=2))


def digest_file(path):
    """Identify the exact split file used for repeat runs."""
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def main():
    """Select local export, CPU preflight, or training."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="step", required=True)
    export = commands.add_parser("prepare")
    export.add_argument("--train-published", type=Path, required=True)
    export.add_argument("--test-published", type=Path, required=True)
    export.add_argument("--output", type=Path, required=True)
    export.add_argument("--expert", type=Path)
    export.add_argument("--bank", type=Path, default=ROOT / "docs/research/ask-question-bank.csv.gz")
    export.add_argument("--families", nargs="+", default=["CSI-US", "CSI-CN"])
    export.add_argument("--limit", type=int, default=0)
    check = commands.add_parser("preflight")
    fit = commands.add_parser("train")
    for command in (check, fit):
        for field in ("cases", "baseline", "output"):
            command.add_argument(f"--{field}", type=Path, required=True)
        command.add_argument("--compatibility-only", action="store_true", help="Permit a CPU-only run to check model and export compatibility.")
    fit.add_argument("--epochs", type=int, default=1)
    fit.add_argument("--batch", type=int, default=4)
    fit.add_argument("--base-model", default=BASE_MODEL)
    fit.add_argument("--revision")
    fit.add_argument("--cpu", action="store_true")
    args = parser.parse_args()
    if args.step == "prepare":
        if args.limit < 0:
            parser.error("--limit must be zero or positive")
        prepare(args)
    elif args.step == "preflight":
        report = preflight(args.cases, args.baseline, compatibility_only=args.compatibility_only)
        write_json(args.output, report)
        print(json.dumps(report, indent=2))
        if not report["ready"]:
            raise SystemExit(2)
    else:
        if min(args.epochs, args.batch) < 1:
            parser.error("--epochs and --batch must be positive")
        train(args)


if __name__ == "__main__":
    main()
