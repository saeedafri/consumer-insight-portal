"""Ask Coresight's naming after a publish (etl/ask_semantic.py): questions that share a name but ask different things are
renamed apart, questions alike keep sharing it, and nothing is sent twice. The model is faked: no network."""
import json
from types import SimpleNamespace

from etl import ask_semantic


def test_questions_sharing_a_name_are_renamed_apart_once(tmp_path, monkeypatch):
    docs = {"econ": {"text": "Is the economy better or worse?", "labels": ["Better", "Worse"], "asks": ["a"], "area": "economy and prices"},
            "econ-2024": {"text": "Is the economy better or worse? (2024)", "labels": ["Better", "Worse"], "asks": [], "area": ""},
            "prices": {"text": "How will the pace of price rises change?", "labels": ["Faster", "Slower"], "asks": [], "area": ""}}
    index = SimpleNamespace(docs=docs, ambiguous={"economic outlook"}, names={"economic outlook": ["econ", "econ-2024", "prices"]},
                            alike=lambda a, b: {a, b} <= {"econ", "econ-2024"} or a == b)
    sent = []
    monkeypatch.setattr(ask_semantic.ask_model, "ready", lambda: True)
    monkeypatch.setattr(ask_semantic, "send", lambda system, listing, schema: sent.append(listing) or [
        {"g": 0, "i": 0, "name": "Economy better or worse", "aliases": ["Economic sentiment"]},
        {"g": 0, "i": 1, "name": "Pace of price rises", "aliases": ["Inflation expectations"]}])
    into = tmp_path / "ask-semantic.json"
    assert ask_semantic.rename_shared(index, into) == 3   # both economy questions, and the price question
    names = {v["text"]: v["name"] for v in json.loads(into.read_text()).values()}
    assert names["Is the economy better or worse?"] == names["Is the economy better or worse? (2024)"] == "Economy better or worse"
    assert names["How will the pace of price rises change?"] == "Pace of price rises"
    assert "a. Is the economy better or worse?" in sent[0] and "b. How will the pace" in sent[0] and "(2024)" not in sent[0]
    assert ask_semantic.rename_shared(index, into) == 0 and len(sent) == 1   # renamed once: never sent again
