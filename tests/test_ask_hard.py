"""Checks the hard test set's own calculator (scripts/ask_hard_truth.py) on a five-person wave, so a wrong expected
figure cannot slip into scripts/ask_hard.yml: shares of those asked, either/both, "any" without "none", age bands
and a chain where each step is a share of the step before."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ask_hard_truth as truth  # noqa: E402

WAVE = {"data": pd.DataFrame({
    "XM1": ["Yes", "Yes", "No", "Yes", None],
    "D28r1: ChatGPT": [1, 0, 0, 1, 0], "D28r8: Other (please specify)": [0, 1, 0, 0, 0],
    "D28r9: Have not used AI": [0, 0, 1, 0, 1],
    "D31": ["Have used GenAI to shop", "Will not use", None, "Have used GenAI to shop", None],
    "D33": ["Yes", None, None, "No", None],
    "D2": ["25", "70 or more", "40", "Under 18", "33"]}),
    "codes": {"XM1": {"multi": False, "columns": {"": "XM1"}},
              "D28": {"multi": True, "columns": {"ChatGPT": "D28r1: ChatGPT", "Other (please specify)": "D28r8: Other (please specify)",
                                                 "Have not used AI": "D28r9: Have not used AI"}},
              "D31": {"multi": False, "columns": {"": "D31"}}, "D33": {"multi": False, "columns": {"": "D33"}},
              "D2": {"multi": False, "columns": {"": "D2"}}}}


def test_the_calculator_counts_like_an_analyst():
    waves = {"2026-11-16": WAVE}
    share = lambda plan: truth.run({"waves": ["2026-11-16"], **plan}, waves)[0]   # noqa: E731
    assert (share({"ask": {"q": "XM1", "is": ["Yes"]}})["n"], share({"ask": {"q": "XM1", "is": ["Yes"]}})["base"]) == (3, 4)   # of those asked
    assert share({"ask": {"q": "D28", "any": True}})["n"] == 3                     # ChatGPT or Other, never "Have not used"
    assert share({"ask": {"either": [{"q": "XM1", "is": ["Yes"]}, {"q": "D28", "is": ["ChatGPT"]}]}})["n"] == 3
    assert share({"ask": {"both": [{"q": "XM1", "is": ["Yes"]}, {"q": "D28", "is": ["ChatGPT"]}]}})["n"] == 2
    assert share({"ask": {"q": "D2", "between": [55, 120]}})["n"] == 1             # "70 or more" counts; "Under 18" never
    assert share({"ask": {"q": "D2", "between": [18, 34]}})["n"] == 2
    steps = truth.run({"waves": ["2026-11-16"], "op": "chain", "steps": [
        {"q": "D28", "any": True, "say": "AI users"}, {"q": "D31", "is": ["Have used"], "say": "GenAI shoppers"},
        {"q": "D33", "is": ["Yes"], "say": "bought"}]}, waves)
    assert [(s["n"], s["base"]) for s in steps] == [(3, 5), (2, 3), (1, 2)]
