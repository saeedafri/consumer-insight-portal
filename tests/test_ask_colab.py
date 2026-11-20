"""Regression checks for cases prepared and scored by scripts/colab/ask_cip_train.py."""
import json
from pathlib import Path
from shutil import copyfile
import subprocess
import sys
from types import SimpleNamespace

import pytest

from scripts.colab import ask_cip_train


def write_cases(path, entries):
    """Write the same JSON Lines format as the local exporter."""
    path.write_text("".join(json.dumps(item) + "\n" for item in entries), encoding="utf-8")
    return path


def test_prepare_removes_hidden_waves_and_their_question_metadata():
    data = {"qcode": "Q3", "waves": [[9, "2026-10-01", 1], [10, "2026-10-02", 2]],
            "versions": ["Private wording", "Approved wording"],
            "answers": [["", 1, "Private label"], ["", 2, "Approved label"]],
            "cuts": [["total", "Total"], ["gender", "Private cut"]],
            "w": [0, 1], "a": [0, 1], "c": [1, 0], "n": [5, 7], "b": [20, 30]}
    assert ask_cip_train.training_question(data, {11}) is None
    assert ask_cip_train.training_question(data, {10}) == {
        "qcode": "Q3", "waves": [[10, "2026-10-02", 1]], "versions": ["Approved wording"],
        "answers": [["", 2, "Approved label"]], "cuts": [["total", "Total"]],
        "w": [0], "a": [0], "c": [0], "n": [7], "b": [30]}


def test_prepare_requires_a_publication_with_verified_label_format(tmp_path):
    published = tmp_path / "api" / "v1"
    published.mkdir(parents=True)
    (tmp_path / "manifest.json").write_text('{"rules": {"cut_inventory": 1}}')
    output = tmp_path / "export"
    with pytest.raises(SystemExit, match="rules.answer_labels=1"):
        ask_cip_train.prepare(SimpleNamespace(train_published=published, test_published=published, output=output))
    assert not output.exists()


def test_reader_split_keeps_paraphrases_and_no_answer_labels_together(tmp_path):
    group = "one reviewed intent"
    assert ask_cip_train.normalize("Amazon  PRIME？") == ask_cip_train.normalize("amazon prime")
    item = {"question": "Does this exist?", "group": group, "split": "train", "candidates": ["Candidate"],
            "acceptable": [0], "no_answer": True}
    cases = tmp_path / "cases.jsonl"
    assert ask_cip_train.validate_splits(write_cases(cases, [item])) == {"train": 1}
    with pytest.raises(SystemExit, match="split leak"):
        ask_cip_train.validate_splits(write_cases(cases, [item, {**item, "question": "Was this asked?", "split": "test"}]))
    with pytest.raises(SystemExit, match="Invalid acceptable candidates"):
        ask_cip_train.validate_splits(write_cases(cases, [{**item, "acceptable": [1]}]))


def test_reader_report_separates_misses_abstentions_and_skipped_reader(tmp_path, monkeypatch):
    calls = {
        "baseline": {"rank": (2, 3), "unsupported": (1, 3), "missing": (0, 1)},
        "candidate": {"rank": (1, 3), "unsupported": (0, 4), "missing": (0, 1)},
    }
    monkeypatch.setattr(ask_cip_train, "onnx_reader", lambda name: (lambda q, _c: calls[name][q], 2))
    item = {"question": "rank", "split": "test", "country": "US", "kind": "share", "source": "reviewed",
            "candidates": ["First", "Second"], "acceptable": [1], "no_answer": False}
    cases = write_cases(tmp_path / "held-out.jsonl", [
        item,
        {**item, "question": "unsupported", "acceptable": [0], "no_answer": True},
        {**item, "question": "missing", "acceptable": []},
        {**item, "question": "bypassed", "candidates": [], "acceptable": []},
    ])
    report = ask_cip_train.evaluate(("baseline", "candidate"), cases)["test"]
    assert report["cases"] == 4
    assert report["reached_reader"] == 3
    assert report["answerable"] == 2
    assert report["candidate_present"] == 1
    assert report["baseline_unsupported_accepted"] == 1
    assert report["candidate_unsupported_accepted"] == 0
    assert report["candidate_correct"] == report["improved"] == 2


def test_reader_calibration_uses_reviewed_development_cases(tmp_path):
    item = {"question": "share", "split": "dev", "source": "reviewed", "candidates": ["Correct"], "acceptable": [1]}
    cases = tmp_path / "calibration.jsonl"
    predict = lambda _q, _lines: (1, 2.0)
    assert ask_cip_train.calibrate(predict, write_cases(cases, [item] * 40)) == (2.0, 40)
    assert ask_cip_train.calibrate(predict, write_cases(cases, [{**item, "split": "test"}] * 40)) == (1_000_000.0, 0)


def pilot_input(tmp_path):
    """Set up the artifact names and metadata used by the CPU gate."""
    baseline = tmp_path / "ask-reader"
    baseline.mkdir()
    (baseline / "model_optimized.onnx").write_bytes(b"model-example")
    (baseline / "tokenizer.json").write_text('{"model": {}}')
    (baseline / "calibration.json").write_text('{"sure": 1.5}')
    return tmp_path / "cases.jsonl", baseline


def pilot_case(split, group, *, source="generated", no_answer=False):
    """Make an answerable or no-answer case that reaches the reader."""
    return {"question": f"Question {group}", "group": group, "split": split, "source": source,
            "country": "US", "kind": "share", "candidates": ["One candidate"],
            "no_answer": no_answer, "acceptable": [0] if no_answer else [1]}


def test_generated_input_stops_normal_colab_training_before_model_import(tmp_path):
    cases, baseline = pilot_input(tmp_path)
    write_cases(cases, [pilot_case("train", "train-1"), pilot_case("test", "test-1")])
    singleton = tmp_path / "content"
    singleton.mkdir()
    trainer = singleton / "ask_cip_train.py"
    copyfile(Path(ask_cip_train.__file__), trainer)
    # The standalone path has only two parents, unlike a checkout or pytest's temp folder.
    exec(compile(trainer.read_text(), "/content/ask_cip_train.py", "exec"),
         {"__file__": "/content/ask_cip_train.py", "__name__": "uploaded_trainer"})
    report_path = singleton / "preflight.json"
    common = ["--cases", str(cases), "--baseline", str(baseline)]
    # Python -S models the Colab upload before its training dependencies are installed.
    result = subprocess.run([sys.executable, "-S", str(trainer), "preflight", *common, "--output", str(report_path)],
                            capture_output=True, text=True, check=False)
    assert result.returncode == 2
    report = json.loads(report_path.read_text())
    assert not report["ready"] and report["mode"] == "quality"
    assert report["split_sizes"] == {"train": 1, "dev": 0, "test": 1, "future": 0}
    assert report["splits"]["test"]["target_in_candidates"] == 1
    assert report["baseline_artifacts"]["model_optimized.onnx"]["sha256"] == ask_cip_train.digest_file(baseline / "model_optimized.onnx")
    gated = subprocess.run([sys.executable, "-S", str(trainer), "train", *common,
                            "--output", str(tmp_path / "candidate")], capture_output=True, text=True, check=False)
    assert gated.returncode == 1 and "Training paused" in gated.stderr
    assert not (tmp_path / "candidate").exists()
    assert ask_cip_train.preflight(cases, baseline, compatibility_only=True)["ready"]


def test_quality_preflight_needs_both_reviewed_and_later_evidence(tmp_path):
    cases, baseline = pilot_input(tmp_path)
    items = [pilot_case("train", "train-1")]
    for split, count in ask_cip_train.MIN_REVIEWED_GROUPS.items():
        for index in range(count):
            item = pilot_case(split, f"{split}-{index}", source="reviewed", no_answer=index % 3 == 0)
            items.append({**item, "source_through": "2026-11-02" if split == "future" else "2026-10-01"})
    write_cases(cases, items)
    provenance = {"train_through": "2026-10-01", "test_through": "2026-11-02",
                  "cases_sha256": ask_cip_train.digest_file(cases)}
    (tmp_path / "dataset-report.json").write_text(json.dumps(provenance))
    report = ask_cip_train.preflight(cases, baseline)
    assert report["ready"] and report["later_reviewed_target_groups"] == 20
    write_cases(cases, [*items, pilot_case("train", "another-train")])
    mismatched = ask_cip_train.preflight(cases, baseline)
    assert not mismatched["ready"] and any("different case file" in reason for reason in mismatched["blocking_reasons"])
