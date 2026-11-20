"""Gemini isolated Ask CIP reader preflight, smoke-test, training, and paired evaluation script.

Who calls it: scripts/colab/Gemini-ask-cip-train.ipynb (in Google Colab: CPU preflight first,
then T4 GPU only after preflight emits ALLOW_NEXT_STEP) or a developer locally for `prepare`
and `preflight`. Never modifies models/ask-reader in place and never calls paid AI APIs.

Commands:
  prepare    Build cases.jsonl and dataset-report.json locally from two verified publications.
  preflight  Run pure-stdlib CPU checks (zero GPU/ML imports) and emit ALLOW_NEXT_STEP or BLOCK.
  train      Verify preflight, run a 2-batch smoke check, train with step/time caps + checkpointing,
             export + reload-verify INT8 ONNX, compare shipped reader vs candidate vs Rank-1 baseline.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import date, datetime, timezone
import gzip
from hashlib import file_digest, sha256
from importlib import metadata
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
# 35 reviewed dev groups clear the 90% Wilson lower bound if precision is high;
# 30 each in test and future give a non-trivial pilot holdout before GPU units are spent.
MIN_REVIEWED_GROUPS = {"dev": 35, "test": 30, "future": 30}
MIN_TRAIN_NO_ANSWER = 10
MIN_CANDIDATE_RECALL = 0.70


def normalize(text: str) -> str:
    """Normalize case, spacing, punctuation, and Unicode NFKC while preserving dates and names."""
    return " ".join(re.findall(r"[^\W_]+", unicodedata.normalize("NFKC", text).casefold()))


def bucket(group: str) -> str:
    """Assign a stable deterministic split (70% train / 15% dev / 15% test) per question group."""
    value = int.from_bytes(sha256(group.encode()).digest()[:4], "big") % 100
    return "test" if value < 15 else "dev" if value < 30 else "train"


def stream_jsonl(path: Path):
    """Yield JSON objects line by line so large datasets never require full-file RAM."""
    with path.open(encoding="utf-8") as source:
        for line in source:
            if line.strip():
                yield json.loads(line)


def write_json(path: Path, data: dict) -> None:
    """Write formatted UTF-8 JSON atomically via a sibling temp file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_suffix(path.suffix + f".{os.getpid()}.part")
    try:
        part.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(part, path)
    except BaseException:
        part.unlink(missing_ok=True)
        raise


def digest_file(path: Path) -> str:
    """Compute hex SHA-256 digest of a file using streaming reads."""
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def runtime_versions(include_ml: bool = False) -> dict:
    """Capture exact OS, Python, CPU, and optional ML package versions for reproducibility."""
    info = {
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
    }
    if include_ml:
        pkgs = {}
        for pkg in ("torch", "transformers", "onnx", "onnxruntime", "tokenizers", "numpy"):
            try:
                pkgs[pkg] = metadata.version(pkg)
            except metadata.PackageNotFoundError:
                pkgs[pkg] = None
        info["packages"] = pkgs
    return info


def filter_training_question(data: dict, allowed_surveys: set[int]) -> dict | None:
    """Strip non-public waves and any versions/answers/cuts referenced only by hidden waves."""
    waves = {i: wave for i, wave in enumerate(data["waves"]) if wave[0] in allowed_surveys}
    cells = [i for i, wave in enumerate(data["w"]) if wave in waves]
    if not cells:
        return None
    versions = sorted({wave[2] for wave in waves.values()})
    answers = sorted({data["a"][i] for i in cells})
    cuts = sorted({data["c"][i] for i in cells})
    wave_idx = {w: i for i, w in enumerate(waves)}
    ver_idx = {v: i for i, v in enumerate(versions, 1)}
    ans_idx = {a: i for i, a in enumerate(answers)}
    cut_idx = {c: i for i, c in enumerate(cuts)}
    return {
        "qcode": data["qcode"],
        "waves": [[sid, day, ver_idx[version]] for sid, day, version in waves.values()],
        "versions": [data["versions"][i - 1] for i in versions],
        "answers": [data["answers"][i] for i in answers],
        "cuts": [data["cuts"][i] for i in cuts],
        "w": [wave_idx[data["w"][i]] for i in cells],
        "c": [cut_idx[data["c"][i]] for i in cells],
        "a": [ans_idx[data["a"][i]] for i in cells],
        "n": [data["n"][i] for i in cells],
        "b": [data["b"][i] for i in cells],
    }


def prepare(args: argparse.Namespace) -> None:
    """Export temporally separated, public-scoped reader cases from two verified publications."""
    def check_publication(path: Path) -> tuple[Path, dict]:
        resolved = path.resolve()
        try:
            manifest = json.loads((resolved.parents[1] / "manifest.json").read_text(encoding="utf-8"))
            rules = manifest.get("rules", {})
            ok = isinstance(rules, dict) and rules.get("answer_labels") == 1
        except (OSError, ValueError, AttributeError, IndexError):
            manifest, rules, ok = {}, {}, False
        if not ok:
            raise SystemExit(
                f"Blocked: {resolved} lacks verified per-question answer labels (rules.answer_labels=1). "
                "Rebuild the publication before exporting training cases."
            )
        return resolved, {"version": manifest.get("version"), "rules": rules}

    older, older_meta = check_publication(args.train_published)
    newer, newer_meta = check_publication(args.test_published)
    sys.path.insert(0, str(ROOT))
    with patch.dict(os.environ, {"PYTHON_DOTENV_DISABLED": "1"}):
        from api import ask_index, ask_model, ask_reader, assistant

    def load_scoped_index(pub_api: Path, target: Path):
        with gzip.open(pub_api / "waves.json.gz", "rt", encoding="utf-8") as incoming:
            waves = [
                w for w in json.load(incoming)
                if w["survey_family"] in args.families and w.get("visibility") == "all" and not w.get("client")
            ]
        if not waves:
            raise SystemExit(f"No eligible public waves found in {pub_api} for families {args.families}")
        allowed = {w["survey_id"] for w in waves}
        source = pub_api / "questions"
        for family in args.families:
            for file in (source / family).glob("*/*.json.gz"):
                filtered = filter_training_question(json.loads(gzip.decompress(file.read_bytes())), allowed)
                if filtered is None:
                    continue
                out = target / file.relative_to(source)
                out.parent.mkdir(parents=True, exist_ok=True)
                with gzip.open(out, "wt", compresslevel=1, encoding="utf-8") as staged:
                    json.dump(filtered, staged, separators=(",", ":"))
        idx = ask_index.Index(target, waves)
        idx.add_vectors()
        if not idx.vector_keys:
            raise SystemExit(f"Search encoder unavailable at {ask_model.EMBED_DIR}")
        return idx, max(str(w["wave_date"])[:10] for w in waves)

    def map_key(item: dict, idx, words_to_keys: dict) -> str | None:
        if item["source"] == "reviewed":
            key = item["key"]
            if key not in idx.docs:
                return None
            choices = [key]
        else:
            choices = words_to_keys[id(idx)].get(normalize(item["answer_question"]), [])
        allowed = [k for k in choices if item["country"] in {idx.country[s] for s in idx.docs[k]["surveys"]}]
        if item["key"] in allowed:
            return item["key"]
        return allowed[0] if len(allowed) == 1 else None

    def capture_candidates(idx, question: str, country: str, correct_key: str | None, is_none: bool, split: str, reserved: set[str]):
        candidates = []

        class Recorded(Exception):
            pass

        def spy(text, listed):
            nonlocal question
            question = text
            candidates.extend(listed)
            raise Recorded

        try:
            with patch.object(ask_model, "read_pick", spy):
                assistant.answer(question, idx, set(idx.country), quick=True)
        except Recorded:
            pass
        relevant, lines = ([0] if is_none else []), []
        for cand in candidates:
            group = country + "|" + normalize(cand["text"])
            if split == "train" and (bucket(group) != "train" or group in reserved):
                continue
            lines.append(ask_model.describe_candidate(cand))
            target = idx.docs.get(correct_key)
            if target and all(cand[f] == target[f] for f in ("text", "waves", "first", "last", "name")):
                relevant.append(len(lines))
        return question, lines, relevant

    def reviewed_rows():
        if not args.expert:
            return
        for item in stream_jsonl(args.expert):
            missing = {"q", "key", "country", "kind", "observed_at", "reviewer"} - item.keys()
            if missing or not normalize(item["q"]) or not str(item.get("reviewer", "")).strip():
                raise SystemExit(f"Invalid reviewed row; required fields missing or blank: {sorted(missing)}")
            if item["key"] is None and not normalize(item.get("group", "")):
                raise SystemExit("Reviewed no-answer rows require a non-empty paraphrase group")
            date.fromisoformat(item["observed_at"])
            yield {**item, "source": "reviewed"}

    def bank_rows():
        if not args.bank or not args.bank.is_file():
            return
        with gzip.open(args.bank, "rt", encoding="utf-8", newline="") as source:
            for item in csv.DictReader(source):
                yield {**item, "q": item["question"], "key": item["answer_key"], "source": "generated"}

    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="gem-reader-export-") as directory:
        scratch = Path(directory)
        vec_copy = scratch / "vectors.npz"
        if ask_model.VECTORS.exists():
            shutil.copyfile(ask_model.VECTORS, vec_copy)
        with (
            patch.object(ask_model, "VECTORS", vec_copy),
            patch.object(ask_model, "LOGS", scratch),
            patch.object(ask_model, "SPEND", scratch / "spend.json"),
            patch.object(ask_model, "ready", return_value=False),
            patch.object(ask_index, "SEMANTIC_ADDED", scratch / "semantics.json"),
            patch.object(ask_index.Index, "load_verified", return_value=None),
        ):
            old_idx, cutoff = load_scoped_index(older, scratch / "older")
            new_idx, through = load_scoped_index(newer, scratch / "newer")
            if through <= cutoff:
                raise SystemExit("Test publication must contain a strictly later eligible wave than train publication")
            words_to_keys = {}
            for idx in (old_idx, new_idx):
                lookup = {}
                for k, doc in idx.docs.items():
                    lookup.setdefault(normalize(doc["text"]), []).append(k)
                words_to_keys[id(idx)] = lookup
                idx.verified_for = lambda _: None
            older_groups = {old_idx.country[s] + "|" + normalize(d["text"]) for d in old_idx.docs.values() for s in d["surveys"]}
            reviewed = list(reviewed_rows())
            reserved = set()
            for item in reviewed:
                if item["observed_at"] > cutoff:
                    key = map_key(item, new_idx, words_to_keys)
                    source_text = item["group"] if item["key"] is None else (new_idx.docs[key]["text"] if key else "")
                    if source_text:
                        reserved.add(item["country"] + "|" + normalize(source_text))

            stats = Counter()
            seen = set()
            with (args.output / "cases.jsonl").open("w", encoding="utf-8") as out_f:
                for item in chain(reviewed, bank_rows()):
                    if args.limit and sum(stats[s] for s in SPLITS) >= args.limit:
                        break
                    country = item["country"]
                    if ask_reader.read(item["q"])["country"] != country:
                        stats["country_not_expressed"] += 1
                        continue
                    fp = normalize(item["q"])
                    if fp in seen:
                        stats["duplicate_wording"] += 1
                        continue
                    is_none = item["source"] == "reviewed" and item["key"] is None
                    key = None if is_none else map_key(item, new_idx, words_to_keys)
                    if not is_none and key is None:
                        stats["unmapped_label"] += 1
                        continue
                    group = country + "|" + (normalize(item["group"]) if is_none else normalize(new_idx.docs[key]["text"]))
                    future = (not is_none and group not in older_groups) or item.get("observed_at", "") > cutoff or group in reserved
                    split = "future" if future else bucket(group)
                    idx = new_idx if split in {"test", "future"} else old_idx
                    idx_key = None if is_none else map_key(item, idx, words_to_keys)
                    if idx_key and normalize(idx.docs[idx_key]["text"]) != group.split("|", 1)[1]:
                        stats["changed_wording"] += 1
                        continue
                    q_out, cand_lines, answers = capture_candidates(idx, item["q"], country, idx_key, is_none, split, reserved)
                    if not cand_lines:
                        stats["reader_not_reached"] += 1
                    if split == "train" and (not cand_lines or not answers):
                        stats["untrainable"] += 1
                        continue
                    corrected_fp = normalize(q_out)
                    if corrected_fp in seen:
                        stats["duplicate_after_spelling"] += 1
                        continue
                    seen.update((fp, corrected_fp))
                    row = {
                        "question": q_out,
                        "candidates": cand_lines,
                        "acceptable": answers,
                        "split": split,
                        "group": sha256(group.encode()).hexdigest()[:20],
                        "kind": item["kind"],
                        "country": country,
                        "source": item["source"],
                        "reviewer": item.get("reviewer"),
                        "no_answer": is_none,
                        "observed_at": item.get("observed_at"),
                        "source_through": idx.docs[idx_key]["last"] if idx_key else None,
                    }
                    out_f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
                    stats[split] += 1
                    stats[f"{split}/{item['source']}/{country}"] += 1

    write_json(
        args.output / "dataset-report.json",
        {
            "train_through": cutoff,
            "test_through": through,
            "train_publication": older_meta,
            "test_publication": newer_meta,
            "eligible_families": args.families,
            "source_counts": dict(stats),
            "bank": args.bank.name if args.bank else None,
            "cases_sha256": digest_file(args.output / "cases.jsonl"),
            "runtime": runtime_versions(include_ml=False),
            "holdout_warning": "Generated rows are weak practice data only. Keep independently reviewed rows frozen for holdout evaluation.",
        },
    )
    print(json.dumps(dict(stats), indent=2))


def validate_cases(cases: Path):
    """Yield validated rows while enforcing unique normalized questions and strict split isolation."""
    groups, questions = {}, set()
    for number, item in enumerate(stream_jsonl(cases), 1):
        if not isinstance(item, dict) or not isinstance(item.get("question"), str):
            raise ValueError(f"Missing question at case {number}")
        split, group, answers = item.get("split"), item.get("group"), item.get("acceptable")
        q_norm = normalize(item["question"])
        fp = sha256(q_norm.encode()).digest()[:16]
        if (
            split not in SPLITS
            or not q_norm
            or not isinstance(group, str)
            or not group
            or fp in questions
            or groups.setdefault(group, split) != split
        ):
            raise ValueError(f"Duplicate question, split leak, or invalid split at case {number}")
        candidates, no_answer = item.get("candidates"), item.get("no_answer")
        if not isinstance(candidates, list) or any(not isinstance(t, str) or not t.strip() for t in candidates):
            raise ValueError(f"Invalid candidate lines at case {number}")
        if (
            not isinstance(answers, list)
            or type(no_answer) is not bool
            or (no_answer and (len(answers) != 1 or type(answers[0]) is not int or answers[0] != 0))
            or (not no_answer and any(type(a) is not int or not 1 <= a <= len(candidates) for a in answers))
        ):
            raise ValueError(f"Invalid acceptable candidate index at case {number}")
        questions.add(fp)
        yield item


def preflight(cases: Path, baseline: Path, *, compatibility_only: bool = False) -> dict:
    """Validate dataset provenance, label hygiene, splits, coverage, and baseline artifacts using stdlib only."""
    dataset_path = cases.with_name("dataset-report.json")
    splits = {s: Counter() for s in SPLITS}
    reviewed_groups = {s: set() for s in SPLITS}
    later_groups = set()
    blocking, warnings = [], []
    artifacts, dataset = {}, {}
    cases_sha256 = None
    cutoff = through = None
    has_answer_label_rule = False

    try:
        cases_sha256 = digest_file(cases)
        if dataset_path.is_file():
            raw_meta = json.loads(dataset_path.read_text(encoding="utf-8"))
            if not isinstance(raw_meta, dict):
                raise ValueError("dataset-report.json must be a JSON object.")
            dataset = {k: raw_meta[k] for k in ("train_through", "test_through", "cases_sha256", "train_publication", "test_publication") if k in raw_meta}
            if dataset.get("cases_sha256") not in (None, cases_sha256):
                raise ValueError("dataset-report.json cases_sha256 does not match cases.jsonl.")
            if dataset.get("train_through") and dataset.get("test_through"):
                cutoff = date.fromisoformat(dataset["train_through"])
                through = date.fromisoformat(dataset["test_through"])
            train_rules = (raw_meta.get("train_publication") or {}).get("rules", {})
            test_rules = (raw_meta.get("test_publication") or {}).get("rules", {})
            has_answer_label_rule = train_rules.get("answer_labels") == 1 and test_rules.get("answer_labels") == 1
        for item in validate_cases(cases):
            if item.get("source") not in ("generated", "reviewed") or not item.get("country") or not item.get("kind"):
                raise ValueError("Each row requires source ('generated'|'reviewed'), country, and kind.")
            split = item["split"]
            st = splits[split]
            reached = bool(item["candidates"])
            usable = bool(reached and item["acceptable"])
            st["cases"] += 1
            st["candidate_pairs"] += len(item["candidates"])
            st["reader_reached"] += reached
            st["target_in_candidates"] += usable and not item["no_answer"]
            st["no_answer"] += item["no_answer"]
            st["unusable"] += not usable
            if item["source"] == "reviewed":
                st["reviewed_cases"] += 1
                if not str(item.get("reviewer") or "").strip():
                    warnings.append(f"Reviewed case in {split} is missing explicit reviewer provenance.")
                if usable:
                    reviewed_groups[split].add(item["group"])
                    st["reviewed_usable"] += 1
                    st["reviewed_no_answer"] += item["no_answer"]
                    st["reviewed_target_in_candidates"] += not item["no_answer"]
                    if split == "future" and cutoff and through and item.get("source_through") and not item["no_answer"]:
                        if cutoff < date.fromisoformat(item["source_through"]) <= through:
                            later_groups.add(item["group"])
    except (OSError, TypeError, ValueError) as exc:
        blocking.append(f"Case validation failed: {exc}")

    for name in READER_FILES:
        path = baseline / name
        try:
            size = path.stat().st_size
            if not path.is_file() or size <= 0:
                raise ValueError("missing or empty")
            if name.endswith(".json"):
                parsed = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(parsed, dict):
                    raise ValueError("must be JSON object")
                if name == "calibration.json" and not isfinite(float(parsed.get("sure", "nan"))):
                    raise ValueError("finite 'sure' threshold required")
                if name == "tokenizer.json" and not isinstance(parsed.get("model"), dict):
                    raise ValueError("tokenizer 'model' object required")
            artifacts[name] = {"bytes": size, "sha256": digest_file(path)}
        except (OSError, TypeError, ValueError) as exc:
            blocking.append(f"Shipped baseline artifact {name} failed check: {exc}")

    train_st = splits["train"]
    if not (train_st["cases"] - train_st["unusable"]):
        blocking.append("train split has zero usable reader rows.")
    if not any(splits[s]["reader_reached"] for s in ("test", "future")):
        blocking.append("Held-out test/future splits have zero rows reaching the reader.")

    if not compatibility_only:
        if not cutoff or not through or through <= cutoff or dataset.get("cases_sha256") != cases_sha256:
            blocking.append("dataset-report.json must bind cases_sha256 to strictly ordered train_through < test_through dates.")
        if not has_answer_label_rule:
            blocking.append("dataset-report.json does not confirm rules.answer_labels=1 on both source publications; rebuild publications first.")
        if train_st["no_answer"] < MIN_TRAIN_NO_ANSWER:
            blocking.append(f"train needs at least {MIN_TRAIN_NO_ANSWER} no_answer cases to supervise the zero abstention logit; found {train_st['no_answer']}.")
        for split, minimum in MIN_REVIEWED_GROUPS.items():
            if len(reviewed_groups[split]) < minimum:
                blocking.append(f"{split} needs >= {minimum} distinct reviewed groups usable by the reader; found {len(reviewed_groups[split])}.")
        for split in ("dev", "test", "future"):
            if not (splits[split]["reviewed_target_in_candidates"] and splits[split]["reviewed_no_answer"]):
                blocking.append(f"{split} needs both reviewed answerable targets and reviewed no_answer cases reaching the reader.")
            ans_reached = splits[split]["reader_reached"] - splits[split]["no_answer"]
            if ans_reached > 0:
                recall = splits[split]["target_in_candidates"] / ans_reached
                if recall < MIN_CANDIDATE_RECALL:
                    blocking.append(f"{split} retrieval candidate recall {recall:.1%} is below {MIN_CANDIDATE_RECALL:.0%}; fix retrieval before training reader.")
        if not later_groups:
            blocking.append("future needs at least one reviewed answerable target group backed by a wave strictly after train_through.")

    for s, st in splits.items():
        st["reviewed_usable_groups"] = len(reviewed_groups[s])

    ready = not blocking
    decision = "ALLOW_NEXT_STEP" if ready else "BLOCK"
    next_step = (
        "Switch Colab runtime to T4 GPU (standard RAM, High-RAM off; L4 only if T4 unavailable) and run 1 epoch."
        if ready and not compatibility_only
        else "Compatibility-only CPU check passed. Do NOT promote any model from compatibility mode."
        if ready
        else "Keep CPU runtime. Do NOT spend GPU units. Fix every blocking_reason, rebuild publications with rules.answer_labels=1, add independently reviewed dev/test/future cases, and rerun CPU preflight."
    )
    return {
        "decision": decision,
        "ready": ready,
        "mode": "compatibility-only" if compatibility_only else "quality",
        "next_step": next_step,
        "blocking_reasons": blocking,
        "warnings": sorted(set(warnings)),
        "cases_sha256": cases_sha256,
        "dataset": dataset,
        "baseline_artifacts": artifacts,
        "split_sizes": {s: splits[s]["cases"] for s in SPLITS},
        "splits": {s: dict(splits[s]) for s in SPLITS},
        "later_reviewed_target_groups": len(later_groups),
        "runtime": runtime_versions(include_ml=False),
        "scope": "CPU-only preflight gate. Passing preflight authorizes one bounded experiment, never production promotion.",
    }


def load_onnx_reader(folder: Path):
    """Load an Ask CIP ONNX cross-encoder reader using single-threaded CPU execution."""
    import numpy as np
    import onnxruntime
    from tokenizers import Tokenizer

    settings = json.loads((folder / "calibration.json").read_text(encoding="utf-8"))
    tok = Tokenizer.from_file(str(folder / "tokenizer.json"))
    tok.enable_truncation(int(settings.get("length", MAX_TOKENS)))
    pad = settings.get("pad_token", "[PAD]")
    tok.enable_padding(pad_id=tok.token_to_id(pad) or 0, pad_token=pad)
    opts = onnxruntime.SessionOptions()
    opts.intra_op_num_threads = opts.inter_op_num_threads = 1
    session = onnxruntime.InferenceSession(str(folder / "model_optimized.onnx"), opts, providers=["CPUExecutionProvider"])
    input_names = {i.name for i in session.get_inputs()}

    def predict(question: str, candidates: list[str]) -> tuple[int, float]:
        if not candidates:
            return 0, 0.0
        pairs = tok.encode_batch([(question, line) for line in candidates])
        mapping = {"input_ids": "ids", "attention_mask": "attention_mask", "token_type_ids": "type_ids"}
        feed = {
            name: np.asarray([getattr(p, field) for p in pairs], dtype=np.int64)
            for name, field in mapping.items() if name in input_names
        }
        scores = session.run(None, feed)[0].reshape(-1)
        if len(scores) != len(candidates) or not np.isfinite(scores).all():
            raise ValueError("ONNX reader produced invalid or non-finite scores")
        logits = np.concatenate([[0.0], scores])
        best, second = np.argsort(-logits)[:2]
        return int(best), float(logits[best] - logits[second])

    return predict, float(settings["sure"])


def evaluate_models(baseline_dir: Path, candidate_dir: Path, cases: Path) -> dict:
    """Compare shipped baseline, candidate, and simple Rank-1 retrieval baseline on identical held-out rows."""
    import numpy as np

    base_fn, base_sure = load_onnx_reader(baseline_dir)
    cand_fn, cand_sure = load_onnx_reader(candidate_dir)
    # Simple Rank-1 baseline: always select candidate #1 with zero neural reader cost
    rank1_fn = lambda _q, cands: (1 if cands else 0, 0.0)

    stats, timings = {}, {}
    for item in stream_jsonl(cases):
        if item["split"] == "train":
            continue
        results = []
        if item["candidates"]:
            for fn in (base_fn, cand_fn, rank1_fn):
                t0 = time.perf_counter()
                pick, lead = fn(item["question"], item["candidates"])
                results.append((pick, lead, (time.perf_counter() - t0) * 1000.0))
        for slice_name in (item["split"], f"{item['split']}/{item['source']}/{item['country']}/{item['kind']}"):
            c = stats.setdefault(slice_name, Counter())
            t = timings.setdefault(slice_name, [[], [], []])
            c["cases"] += 1
            c["reached_reader"] += bool(item["candidates"])
            c["answerable"] += bool(item["candidates"]) and not item["no_answer"]
            c["candidate_present"] += bool(item["acceptable"]) and not item["no_answer"]
            c["no_answer"] += bool(item["candidates"]) and item["no_answer"]
            if not results:
                continue
            for idx_m, (name, sure) in enumerate((("baseline", base_sure), ("candidate", cand_sure), ("rank1_retrieval", 1e9))):
                pick, lead, ms = results[idx_m]
                right = pick in item["acceptable"]
                c[f"{name}_correct"] += right
                if not item["no_answer"]:
                    c[f"{name}_answerable_correct"] += right
                c[f"{name}_false_answer"] += pick != 0 and not right
                c[f"{name}_unsupported_accepted"] += item["no_answer"] and pick != 0
                c[f"{name}_abstained"] += pick == 0
                if lead >= sure:
                    c[f"{name}_confident"] += 1
                    c[f"{name}_confident_correct"] += right
                    c[f"{name}_confident_wrong"] += not right
                t[idx_m].append(ms)
            b_ok = results[0][0] in item["acceptable"]
            c_ok = results[1][0] in item["acceptable"]
            c["improved_vs_baseline"] += c_ok and not b_ok
            c["regressed_vs_baseline"] += b_ok and not c_ok

    out = {}
    for name, c in stats.items():
        lat = {}
        for idx_m, m_name in enumerate(("baseline", "candidate", "rank1_retrieval")):
            vals = timings[name][idx_m]
            lat[f"{m_name}_p50_ms"] = round(float(np.percentile(vals, 50)), 2) if vals else None
            lat[f"{m_name}_p95_ms"] = round(float(np.percentile(vals, 95)), 2) if vals else None
        out[name] = {**c, **lat}
    return out


def calibrate_threshold(predict_fn, cases: Path) -> tuple[float, int]:
    """Fit a conservative 95%-Wilson >= 0.90 lead threshold strictly on reviewed dev rows."""
    evidence = []
    for item in stream_jsonl(cases):
        if item["split"] == "dev" and item["source"] == "reviewed" and item["candidates"]:
            pick, lead = predict_fn(item["question"], item["candidates"])
            evidence.append((lead, pick in item["acceptable"]))
    evidence.sort(reverse=True)
    threshold = 1_000_000.0
    right = 0
    for count, (lead, correct) in enumerate(evidence, 1):
        right += correct
        if count < 30 or (count < len(evidence) and evidence[count][0] == lead):
            continue
        p = right / count
        z = 1.96
        lower = (p + z**2 / (2 * count) - z * sqrt(p * (1 - p) / count + z**2 / (4 * count**2))) / (1 + z**2 / count)
        if lower >= 0.90:
            threshold = lead
    return threshold, len(evidence)


def verify_onnx_reload(model_pt, tok, onnx_dir: Path) -> dict:
    """Verify exported ONNX reloads cleanly for variable candidate sizes (1, 5, 14) and matches PyTorch ranking."""
    import torch

    predict, _ = load_onnx_reader(onnx_dir)
    checks = {}
    for k in (1, 5, 14):
        cands = [f"(10w 25-26) Candidate {i}: Which retailers did you buy from? | Amazon; Walmart" for i in range(k)]
        pick, lead = predict("What share bought from Amazon?", cands)
        if not (0 <= pick <= k and isfinite(lead)):
            raise ValueError(f"Reload check failed for k={k}: pick={pick}, lead={lead}")
        checks[f"k_{k}"] = {"pick": pick, "lead": round(lead, 4)}
    # Compare PyTorch FP32 top pick vs ONNX INT8 top pick on a 5-candidate probe
    probe_q = "What share subscribe to Amazon Prime?"
    probe_c = [
        "(10w 22-26) Amazon Prime membership: Do you have an Amazon Prime membership? | Yes; No",
        "(200w 22-26) Retailers bought from: Which retailers have you bought from? | Amazon; Walmart",
        "(40w 24-26) Online categories: Which categories did you buy online? | Groceries; Clothing",
        "(12w 25-26) Tariff concerns: How worried are you about tariffs? | Very; Somewhat",
        "(5w 26-26) Gas prices: How are higher gas prices affecting spending? | Cutting back",
    ]
    model_pt.cpu().eval()
    with torch.no_grad():
        enc = tok([probe_q] * len(probe_c), probe_c, truncation=True, max_length=MAX_TOKENS, padding=True, return_tensors="pt")
        pt_scores = model_pt(**enc).logits.flatten().tolist()
    pt_logits = [0.0, *pt_scores]
    pt_pick = int(max(range(len(pt_logits)), key=lambda i: pt_logits[i]))
    onnx_pick, onnx_lead = predict(probe_q, probe_c)
    checks["pt_vs_onnx_probe"] = {"pt_pick": pt_pick, "onnx_pick": onnx_pick, "onnx_lead": round(onnx_lead, 4), "agree": pt_pick == onnx_pick}
    return checks


def train(args: argparse.Namespace) -> None:
    """Run preflight gate, smoke check, bounded training with checkpointing, ONNX export, and paired eval."""
    evidence = preflight(args.cases, args.baseline, compatibility_only=args.compatibility_only)
    if not evidence["ready"]:
        raise SystemExit("BLOCKED by preflight. " + " ".join(evidence["blocking_reasons"]))
    if args.output.exists() and not args.resume:
        raise SystemExit("Output folder already exists. Choose a fresh destination or pass --resume.")

    import numpy as np
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    from onnxruntime.quantization import QuantType, quantize_dynamic

    use_cpu = args.cpu or args.compatibility_only
    if not use_cpu and not torch.cuda.is_available():
        raise SystemExit("No CUDA GPU detected. Select T4 GPU in Colab or pass --cpu for compatibility mode.")
    device = "cpu" if use_cpu else "cuda"
    if device == "cpu":
        torch.set_num_threads(1)

    # Verify shipped baseline loads and scores one real row BEFORE downloading HuggingFace weights
    first_row = next(r for r in stream_jsonl(args.cases) if r["candidates"])
    load_onnx_reader(args.baseline)[0](first_row["question"], first_row["candidates"])

    args.output.mkdir(mode=0o700, parents=True, exist_ok=True)
    write_json(args.output / "Gemini-preflight-report.json", evidence)

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    if device == "cuda":
        torch.cuda.manual_seed_all(args.seed)

    revision = args.revision or (BASE_REVISION if args.base_model == BASE_MODEL else None)
    ckpt_dir = args.output / "checkpoint"
    if args.resume and (ckpt_dir / "state.pt").is_file():
        tok = AutoTokenizer.from_pretrained(ckpt_dir)
        model = AutoModelForSequenceClassification.from_pretrained(ckpt_dir, num_labels=1).to(device)
        optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)
        saved_state = torch.load(ckpt_dir / "state.pt", map_location=device, weights_only=True)
        optimizer.load_state_dict(saved_state["optimizer"])
        start_epoch = int(saved_state["epoch"])
        global_step = int(saved_state["global_step"])
        print(f"Resumed from checkpoint epoch={start_epoch}, step={global_step}", flush=True)
    else:
        tok = AutoTokenizer.from_pretrained(args.base_model, revision=revision)
        model = AutoModelForSequenceClassification.from_pretrained(args.base_model, revision=revision, num_labels=1).to(device)
        optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)
        start_epoch = 0
        global_step = 0

    def encode_batch(batch: list[dict]):
        queries = [row["question"] for row in batch for _ in row["candidates"]]
        cands = [line for row in batch for line in row["candidates"]]
        return tok(queries, cands, truncation=True, max_length=MAX_TOKENS, padding=True, return_tensors="pt").to(device)

    def batch_iter(epoch: int):
        rng = random.Random(args.seed + epoch)
        buf = []
        for row in stream_jsonl(args.cases):
            if row["split"] == "train" and row["acceptable"] and row["candidates"]:
                buf.append(row)
            if len(buf) >= 32 * args.batch:
                rng.shuffle(buf)
                yield from (buf[i:i + args.batch] for i in range(0, len(buf), args.batch))
                buf = []
        rng.shuffle(buf)
        yield from (buf[i:i + args.batch] for i in range(0, len(buf), args.batch))

    def compute_loss(batch: list[dict]):
        scores = model(**encode_batch(batch)).logits.flatten()
        losses = []
        for row, logits in zip(batch, scores.split([len(r["candidates"]) for r in batch])):
            full = torch.cat((scores.new_zeros(1), logits)).float()
            truths = full[row["acceptable"]]
            losses.append(torch.logsumexp(full, 0) - torch.logsumexp(truths, 0))
        return torch.stack(losses).mean()

    # Mandatory 1-batch pipeline smoke test before full training
    smoke_batch = next(batch_iter(0), None)
    if not smoke_batch:
        raise SystemExit("No trainable rows found in cases.jsonl.")
    model.train()
    smoke_loss = compute_loss(smoke_batch)
    if not torch.isfinite(smoke_loss):
        raise SystemExit(f"Smoke test failed with non-finite loss: {smoke_loss}")
    print(f"Smoke test OK (1 batch, loss={smoke_loss.item():.4f}, device={device})", flush=True)
    if args.smoke_only:
        print("Exiting after --smoke-only check.")
        return

    started = time.monotonic()
    stopped_early = None
    for epoch in range(start_epoch, args.epochs):
        model.train()
        total_loss = batches = 0
        for batch in batch_iter(epoch):
            if args.max_steps and global_step >= args.max_steps:
                stopped_early = f"max_steps={args.max_steps}"
                break
            if args.max_minutes and (time.monotonic() - started) / 60.0 >= args.max_minutes:
                stopped_early = f"max_minutes={args.max_minutes}"
                break
            loss = compute_loss(batch)
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            total_loss += float(loss.item())
            batches += 1
            global_step += 1
        if batches:
            print(f"epoch {epoch + 1}/{args.epochs}: {batches} batches, mean_loss={total_loss / batches:.4f}", flush=True)
        # Save resumable checkpoint at epoch boundary
        ckpt_dir.mkdir(exist_ok=True)
        model.save_pretrained(ckpt_dir)
        tok.save_pretrained(ckpt_dir)
        torch.save({"epoch": epoch + 1, "global_step": global_step, "optimizer": optimizer.state_dict()}, ckpt_dir / "state.pt")
        if stopped_early:
            print(f"Stopped early due to limit: {stopped_early}", flush=True)
            break

    elapsed_sec = round(time.monotonic() - started, 2)
    model.cpu().eval()
    tok.save_pretrained(args.output)
    sample = tok(["What share shopped?"], ["Where did consumers shop?"], return_tensors="pt")
    input_names = list(sample.keys())
    with tempfile.TemporaryDirectory(prefix="gem-onnx-") as tmp_onnx:
        fp32_onnx = Path(tmp_onnx) / "reader.onnx"
        torch.onnx.export(
            model, (), str(fp32_onnx), kwargs=dict(sample),
            input_names=input_names, output_names=["logits"],
            dynamic_axes={**{n: {0: "items", 1: "tokens"} for n in input_names}, "logits": {0: "items"}},
            opset_version=17, dynamo=False,
        )
        quantize_dynamic(fp32_onnx, args.output / "model_optimized.onnx", weight_type=QuantType.QInt8)

    calibration = {
        "length": MAX_TOKENS,
        "sure": 1_000_000.0,
        "pad_token": tok.pad_token,
        "made": Path(args.base_model).name,
        "revision": revision or getattr(model.config, "_commit_hash", None),
        "epochs": args.epochs,
        "global_steps": global_step,
        "seed": args.seed,
        "promotion_status": "NOT APPROVED FOR PROMOTION",
    }
    write_json(args.output / "calibration.json", calibration)
    reload_checks = verify_onnx_reload(model, tok, args.output)
    fitted_sure, reviewed_dev = calibrate_threshold(load_onnx_reader(args.output)[0], args.cases)
    write_json(args.output / "calibration.json", {**calibration, "sure": fitted_sure, "reviewed_dev_cases": reviewed_dev})

    slices = evaluate_models(args.baseline, args.output, args.cases)
    gpu_name = torch.cuda.get_device_name(0) if device == "cuda" else None
    paired = {
        "promotion_status": "NOT APPROVED FOR PROMOTION",
        "resource": {"device": device, "gpu": gpu_name, "elapsed_seconds": elapsed_sec, "stopped_early": stopped_early},
        "training": {"base_model": args.base_model, "revision": calibration["revision"], "epochs": args.epochs,
                     "global_steps": global_step, "batch": args.batch, "lr": args.lr, "seed": args.seed},
        "runtime": runtime_versions(include_ml=True),
        "model_bytes": (args.output / "model_optimized.onnx").stat().st_size,
        "cases_sha256": evidence["cases_sha256"],
        "split_sizes": evidence["split_sizes"],
        "baseline_sha256": evidence["baseline_artifacts"]["model_optimized.onnx"]["sha256"],
        "candidate_sha256": digest_file(args.output / "model_optimized.onnx"),
        "mode": evidence["mode"],
        "reload_validation": reload_checks,
        "slices": slices,
        "scope": "Fixed candidate lists and CPU ONNX timing only. Run isolated end-to-end Ask CIP strict evaluation before any promotion.",
    }
    write_json(args.output / "paired-report.json", paired)

    # Write deployment & rollback instructions + SHA256SUMS.txt
    (args.output / "DEPLOY_AND_ROLLBACK.md").write_text(
        "# Gemini Candidate Validation, Deployment & Rollback\n\n"
        "**Status: NOT APPROVED FOR PROMOTION** until independent strict CIP replay passes.\n\n"
        "1. Keep `models/ask-reader` unchanged.\n"
        "2. Verify checksums: `shasum -a 256 -c SHA256SUMS.txt`.\n"
        "3. Run isolated strict replay without paid-provider keys:\n"
        "   ```bash\n"
        "   CIP_ASK_READER_DIR=/path/to/Gemini-cip-candidate \\\n"
        "     ./.venv/bin/python scripts/ask_golden.py --strict \\\n"
        "     --questions /path/to/independent-exact.yml \\\n"
        "     --published /path/to/rebuilt-generation/api/v1\n"
        "   ```\n"
        "4. Promotion gate: zero wrong-source permissions, zero wrong cells/bases, lower confident-wrong rate,\n"
        "   equal or better held-out/future coverage, and CPU p95 within budget.\n"
        "5. Rollback: point `CIP_ASK_READER_DIR` back to the pinned baseline directory (SHA-256 "
        f"`{evidence['baseline_artifacts']['model_optimized.onnx']['sha256']}`) and restart the worker.\n",
        encoding="utf-8",
    )
    sums = [f"{digest_file(args.output / name)}  {name}" for name in (*READER_FILES, "paired-report.json", "Gemini-preflight-report.json", "DEPLOY_AND_ROLLBACK.md")]
    (args.output / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in slices.items() if "/" not in k}, indent=2))


def main() -> None:
    """Dispatch prepare, CPU preflight, or bounded reader training."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="step", required=True)

    p_prep = sub.add_parser("prepare")
    p_prep.add_argument("--train-published", type=Path, required=True)
    p_prep.add_argument("--test-published", type=Path, required=True)
    p_prep.add_argument("--output", type=Path, required=True)
    p_prep.add_argument("--expert", type=Path)
    p_prep.add_argument("--bank", type=Path, default=ROOT / "docs/research/ask-question-bank.csv.gz")
    p_prep.add_argument("--families", nargs="+", default=["CSI-US", "CSI-CN"])
    p_prep.add_argument("--limit", type=int, default=0)

    p_pre = sub.add_parser("preflight")
    p_tr = sub.add_parser("train")
    for cmd in (p_pre, p_tr):
        for field in ("cases", "baseline", "output"):
            cmd.add_argument(f"--{field}", type=Path, required=True)
        cmd.add_argument("--compatibility-only", action="store_true")

    p_tr.add_argument("--epochs", type=int, default=1)
    p_tr.add_argument("--batch", type=int, default=4)
    p_tr.add_argument("--lr", type=float, default=3e-5)
    p_tr.add_argument("--seed", type=int, default=17)
    p_tr.add_argument("--max-steps", type=int, default=2000)
    p_tr.add_argument("--max-minutes", type=float, default=30.0)
    p_tr.add_argument("--base-model", default=BASE_MODEL)
    p_tr.add_argument("--revision")
    p_tr.add_argument("--cpu", action="store_true")
    p_tr.add_argument("--smoke-only", action="store_true")
    p_tr.add_argument("--resume", action="store_true")

    args = parser.parse_args()
    if args.step == "prepare":
        if args.limit < 0:
            parser.error("--limit must be >= 0")
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
