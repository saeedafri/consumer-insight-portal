"""scripts/colab/ask_cip_v2.py: the model's replies read back, and each wording's new questions split into asks and a
bank that never overlap (a question that is both would let the test see its own answer)."""
import csv
import gzip
import json
from types import SimpleNamespace

from scripts.colab import ask_cip_v2 as v2


def test_a_reply_is_read_as_a_json_array_or_as_lines_each_question_once():
    assert v2.parse('Sure! ["GLP-1 use by generation", "Is Ozempic use growing?", "glp-1 use by generation"]', 10) == \
        ["GLP-1 use by generation", "Is Ozempic use growing?"]
    assert v2.parse("1. Top retailers latest\n2) Walmart vs Target\n- \"Amazon shoppers\"", 2) == ["Top retailers latest", "Walmart vs Target"]


def test_split_gives_each_new_question_to_the_asks_or_the_bank_never_both(tmp_path):
    wording = {"wkey": "w1", "text": "Which retailers have you bought from?", "name": "Retailers", "labels": [], "family": "CSI-US",
               "study": "", "first": "2026-01-05", "last": "2026-11-09", "waves": 40, "cuts": [], "keys": ["CSI-US/tracker/q5"],
               "asks": ["Where do people shop?"]}
    with gzip.open(tmp_path / "w.jsonl.gz", "wt") as out:
        out.write(json.dumps(wording) + "\n")
    asked = [f"retailer question {n}" for n in range(10)] + ["Where do people shop?"]   # an existing ask is not new
    (tmp_path / "e.jsonl").write_text(json.dumps({"wkey": "w1", "questions": asked}) + "\n")
    (tmp_path / "s.json").write_text("{}")
    v2.split(SimpleNamespace(wordings=tmp_path / "w.jsonl.gz", expanded=tmp_path / "e.jsonl", semantic=tmp_path / "s.json",
                             semantic_out=tmp_path / "out.json", bank_out=tmp_path / "bank.csv.gz"))
    asks = json.loads((tmp_path / "out.json").read_text())["w1"]["asks"]
    bank = [r["question"] for r in csv.DictReader(gzip.open(tmp_path / "bank.csv.gz", "rt"))]
    assert len(asks) == 6 and len(bank) == 4 and not set(asks) & set(bank)   # 60% of the 10 new ones are asks
    assert "Where do people shop?" not in bank
