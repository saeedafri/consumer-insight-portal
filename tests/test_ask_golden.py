"""Test the exact Ask evaluation run by scripts/ask_golden.py, using made-up survey evidence."""
import gzip
import json
import sys

import pytest
import yaml

from api import ask_index, ask_model, assistant
from scripts import ask_golden


@pytest.fixture()
def exact_case():
    """One independently specified wave and answer from a 24-of-60 aggregate."""
    return {"q": "What share bought online in the latest wave?", "visible_survey_ids": [5], "expect": {
        "mode": "figures",
        "source": {"qcode": "Q2", "survey_id": 5},
        "scope": {"country": "US", "kind": "share", "when": [{"latest": 1}]},
        "cells": [{"column": "9 Nov 2026", "answer": "Online", "share": 40.0, "base": 60}],
    }}


@pytest.fixture()
def response():
    """Use the actual assistant response keys and deliberately different per-row bases."""
    return {"mode": "figures", "sources": [{"qcode": "Q2", "survey_id": 5}],
            "plan": {"country": "US", "kind": "share", "when": [{"latest": 1}]},
            "table": {"head": ["Answer", "9 Nov 2026"], "rows": [["In store", 90.0], ["Online", 40.0]],
                      "cell_bases": [[100], [60]], "bases": [100]}}


def test_strict_compares_the_selected_cell_and_its_own_base(exact_case, response):
    """A summary base cannot substitute for an answer cell's denominator."""
    ask_golden.check_evidence(exact_case)
    assert ask_golden.score_exact(exact_case["expect"], response, {5}) == []
    response["table"]["cell_bases"][1][0] = 100
    assert "60" in ask_golden.score_exact(exact_case["expect"], response, {5})[0]
    response["table"]["cell_bases"][1][0] = 60
    response["table"]["rows"][1][1] = 40.1
    assert "40.1" in ask_golden.score_exact(exact_case["expect"], response, {5})[0]


def test_strict_requires_exact_source_scope_and_heading(exact_case, response):
    """A plausible table is still wrong for another survey, country, filter or period."""
    response["sources"][0]["survey_id"] = 8
    response["sources"][0]["qcode"] = "Q3"
    response["plan"]["when"] = [{"latest": 4}]
    response["table"]["head"][1] = "16 Nov 2026"
    problems = ask_golden.score_exact(exact_case["expect"], response, {5})
    assert any("visible waves" in problem for problem in problems)
    assert any("source.survey_id" in problem for problem in problems)
    assert any("source.qcode" in problem for problem in problems)
    assert any("scope.when" in problem for problem in problems)
    assert any("no unique table cell" in problem for problem in problems)


def test_strict_distinguishes_no_answer_and_ambiguity():
    """Unsupported questions and ambiguous questions have separate expected decisions."""
    assert ask_golden.score_exact({"mode": "none"}, {"mode": "none"}, set()) == []
    assert ask_golden.score_exact({"mode": "choose"}, {"mode": "choose"}, set()) == []
    assert ask_golden.score_exact({"mode": "none"}, {"mode": "choose"}, set())


def test_strict_refuses_cases_without_evidence(tmp_path, monkeypatch, capsys):
    """Reject a legacy case before opening the publication or contacting any model."""
    cases = tmp_path / "cases.yml"
    cases.write_text("- q: What is the moon made of?\n  want: none\n")
    monkeypatch.setattr(sys, "argv", ["ask_golden", "--strict", "--questions", str(cases)])
    with pytest.raises(SystemExit, match="2"):
        ask_golden.main()
    assert "case 1: expect.mode" in capsys.readouterr().err


def test_strict_cli_scores_local_answers_and_fails_regressions(tmp_path, monkeypatch, exact_case, response):
    """Run the command's complete scoring path without model, data or cache side effects."""
    cases = tmp_path / "cases.yml"
    cases.write_text(yaml.safe_dump([exact_case]))
    (tmp_path / "waves.json.gz").write_bytes(gzip.compress(json.dumps([{"survey_id": 5}, {"survey_id": 8}]).encode()))
    monkeypatch.setattr(sys, "argv", ["ask_golden", "--strict", "--questions", str(cases), "--published", str(tmp_path)])
    monkeypatch.setattr(ask_index, "Index", lambda *args: object())
    monkeypatch.setattr(ask_golden, "add_isolated_vectors", lambda index: None)
    monkeypatch.setattr(ask_model, "spent", lambda: {"usd": 0})

    def answer(question, index, shown, quick):
        """Verify the CLI dispatches local quick answers for the case's selected waves."""
        assert shown == {5} and quick
        return response

    monkeypatch.setattr(assistant, "answer", answer)
    assert ask_golden.main() == 0
    response["table"]["cell_bases"][1][0] = 601
    assert ask_golden.main() == 1


def test_misses_count_by_stem_and_four_outcomes():
    # the real set is 115 stems with scripted suffixes, and an ask-back holding the right question is not a wrong answer
    assert ask_golden.stem("Top beauty retailers by income") == ask_golden.stem("Top beauty retailers in all Waves?") == "top beauty retailers"
    index = type("Index", (), {"docs": {"k": {"text": "Have you purchased any beauty products?"}}})()
    item = {"q": "beauty buyers", "want": ["beauty products"]}
    assert ask_golden.outcome(item, {"mode": "figures"}, [], index) == "right"
    assert ask_golden.outcome(item, {"mode": "choose", "suggestions": [{"key": "k"}]}, ["no answer"], index) == "asked back"
    assert ask_golden.outcome(item, {"mode": "figures"}, ["wrong question"], index) == "wrong"
    assert ask_golden.outcome(item, {"mode": "none"}, ["no answer"], index) == "no answer"
