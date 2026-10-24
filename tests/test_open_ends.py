"""Open-ended coding (etl/open_ends.py): repeated answers become themes; Claude's coding is checked before use."""
import json

import pytest

from app.data.payloads import open_group
from etl.open_ends import NOTHING, OTHER, by_claude, by_frequency


def test_answers_two_people_gave_become_themes_and_private_details_never_do():
    themes, codes = by_frequency(["Walmart", "walmart.", "Wal-mart", "Target", "target", "n/a", "Costco", "bob@x.com"])
    assert themes == ["Walmart", "Target", NOTHING, OTHER]
    assert codes == [0, 0, 0, 1, 1, 2, 3, 2]   # an email address is removed, so it reads as blank


class Reply:
    def __init__(self, body):
        self.content = [type("Block", (), {"type": "text", "text": json.dumps(body)})()]


class Claude:
    def __init__(self, body):
        self.messages = type("Messages", (), {"create": lambda _, **kw: Reply(body)})()


def test_claude_coding_is_used_only_when_it_covers_every_answer():
    assert by_claude("Why?", ["cheaper", "price"], Claude({"themes": ["Price"], "codes": [0, 0]})) == (["Price"], [0, 0])
    with pytest.raises(ValueError):
        by_claude("Why?", ["cheaper", "price"], Claude({"themes": ["Price"], "codes": [0]}))


def test_a_coded_question_charts_each_theme_as_a_share_of_those_who_answered():
    group = open_group({"themes": ["Walmart", OTHER], "codes": {"1": 0, "2": 0, "3": 1}}, {1: ["Male"], 2: ["Female"], 3: ["Male"]})
    assert group["base"] == 3 and group["bases"] == {"Total": 3, "Male": 2, "Female": 1}
    walmart = group["rows"][0]
    assert walmart["label"] == "Walmart" and walmart["Total"] == 66.7 and walmart["Male"] == 50.0 and walmart["Female"] == 100.0
