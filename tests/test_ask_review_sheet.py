"""scripts/ask_review_sheet.py read: a reviewer's marks become the reviewed labels scripts/colab/ask_cip_train.py trains on."""
import json
from types import SimpleNamespace

import pytest
from openpyxl import Workbook

from scripts import ask_review_sheet as sheet


def marked(tmp_path, answers):
    """A Review tab with one row a (Right answer, Also right) pair; choice n holds key Kn, Ask's pick key P."""
    book = Workbook()
    review = book.active
    review.title = "Review"
    review.append(sheet.HEAD)
    for number, (answer, also) in enumerate(answers, start=1):
        row = dict.fromkeys(sheet.HEAD)
        row.update({"No.": number, "Question": f"Question {number}?", "Right answer": answer, "Also right (choice numbers)": also,
                    "country": "US", "kind": "share", "observed_at": "2026-11-21", "pick key": "P",
                    **{f"key {n}": f"K{n}" for n in range(1, sheet.CHOICES + 1)}})
        review.append([row[h] for h in sheet.HEAD])
    book.save(tmp_path / "marked.xlsx")
    return SimpleNamespace(sheet=tmp_path / "marked.xlsx", out=tmp_path / "reviewed.jsonl", published=tmp_path)


def test_marks_become_reviewed_labels(tmp_path):
    args = marked(tmp_path, [("2", "1, 3"), ("None", None), ("Pick", None), (None, None)])
    sheet.read(args)
    labels = [json.loads(line) for line in args.out.read_text().splitlines()]
    assert [(x["key"], x["also"]) for x in labels] == [("K2", ["K1", "K3"]), (None, []), ("P", [])]   # the blank row skipped
    assert labels[1]["group"] == "question 2"   # a None row carries the group its paraphrases share


def test_a_mark_that_is_not_a_choice_stops_the_read(tmp_path):
    with pytest.raises(SystemExit):
        sheet.read(marked(tmp_path, [("9", None)]))
