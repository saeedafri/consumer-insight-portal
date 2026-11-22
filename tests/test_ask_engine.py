"""Checks Ask's plan engine (api/ask_engine.py) on a five-person published wave: a share of those asked, "any" that
skips "none of these", either/both/not, an age band from raw ages, a group split, a funnel, a top list, pooling two
weeks, the change test, and that a "None" answer counts as asked (the raw-file reader once dropped it)."""
import gzip
import json

from api import ask_engine


def bits(*seats: int) -> str:
    """A people.json bitset: respondent i is bit i, in hex."""
    return format(sum(1 << s for s in seats), "x")


def wave(folder, survey_id: int, xm1_yes: list[int]) -> None:
    people = {"weights": [1.0] * 5, "cuts": {}, "questions": {
        "XM1": {"rows": [[0, 1, "", 1, "Yes"], [0, 2, "", 2, "No"]], "bits": {"0,1": bits(*xm1_yes), "0,2": bits(*[s for s in range(4) if s not in xm1_yes])}},
        "D28": {"rows": [[11, 0, "ChatGPT", None, None], [12, 0, "Gemini", None, None], [19, 0, "Have not used AI in the last two weeks", None, None]],
                "bits": {"0,0": bits(0, 1, 2, 3, 4), "11,0": bits(0, 3), "12,0": bits(1, 3), "19,0": bits(2, 4)}},
        "D31": {"rows": [[0, 5, "", 1, "Have used GenAI to shop"], [0, 6, "", 2, "Will not use GenAI to shop"]], "bits": {"0,5": bits(0, 3), "0,6": bits(1)}},
        "D12": {"rows": [[0, 7, "", 1, "None"], [0, 8, "", 2, "A lot"]], "bits": {"0,7": bits(0, 1), "0,8": bits(2, 3, 4)}},
        "D2": {"rows": [[0, 9, "", 1, "Under 18"], [0, 10, "", 2, "25"], [0, 11, "", 3, "70 or more"]], "bits": {"0,9": bits(4), "0,10": bits(0, 1), "0,11": bits(2, 3)}}}}
    path = folder / "waves" / str(survey_id)
    path.mkdir(parents=True)
    (path / "people.json.gz").write_bytes(gzip.compress(json.dumps(people).encode()))


def test_the_engine_answers_plans_that_join_questions(tmp_path):
    wave(tmp_path, 1, [0, 1, 3])
    wave(tmp_path, 2, [0])
    ids = {"2026-11-09": 1, "2026-11-16": 2}
    one = lambda plan: ask_engine.run({"waves": ["2026-11-09"], **plan}, tmp_path, ids)   # noqa: E731
    figures = lambda plan: [(r["n"], r["base"]) for r in one(plan)]   # noqa: E731
    assert figures({"ask": {"q": "XM1", "is": ["Yes"]}}) == [(3, 4)]                              # of the 4 asked, not all 5
    assert figures({"ask": {"q": "XM1", "is": ["Yes"]}, "base": "all"}) == [(3, 5)]
    assert figures({"ask": {"q": "D28", "any": True}}) == [(3, 5)]                                # never "Have not used AI"
    assert figures({"ask": {"either": [{"q": "D28", "is": ["ChatGPT"]}, {"q": "D28", "is": ["Gemini"]}]}}) == [(3, 5)]
    assert figures({"ask": {"both": [{"q": "D28", "is": ["ChatGPT"]}, {"q": "D28", "is": ["Gemini"]}]}}) == [(1, 5)]
    assert figures({"ask": {"not": {"q": "XM1", "is": ["Yes"]}}}) == [(1, 4)]
    assert figures({"ask": {"q": "D12", "is": ["A lot"]}}) == [(3, 5)]                             # "None" is an answer: all 5 asked
    assert figures({"ask": {"q": "D2", "between": [55, 120]}}) == [(2, 5)]                         # "70 or more" counts; "Under 18" never
    assert figures({"among": {"q": "D28", "any": True}, "ask": {"q": "D31", "is": ["Have used"]}}) == [(2, 3)]
    split = one({"ask": {"q": "XM1", "is": ["Yes"]}, "by": {"groups": {"AI users": {"q": "D28", "any": True}, "others": {"not": {"q": "D28", "any": True}}}}})
    assert [(r["group"], r["n"], r["base"]) for r in split] == [("AI users", 3, 3), ("others", 0, 1)]
    chain = one({"op": "chain", "steps": [{"q": "D28", "any": True}, {"q": "D31", "is": ["Have used"]}, {"q": "XM1", "is": ["Yes"]}]})
    assert [(r["n"], r["base"]) for r in chain] == [(3, 5), (2, 3), (2, 2)]
    assert [r["label"] for r in one({"op": "top", "top": 2, "ask": {"q": "D28"}})] == ["ChatGPT", "Gemini"]
    pooled = ask_engine.run({"waves": ["2026-11-09", "2026-11-16"], "per": "pooled", "ask": {"q": "XM1", "is": ["Yes"]}}, tmp_path, ids)
    assert [(r["n"], r["base"]) for r in pooled] == [(4, 8)]
    change = ask_engine.run({"waves": ["2026-11-09", "2026-11-16"], "test": True, "ask": {"q": "XM1", "is": ["Yes"]}}, tmp_path, ids)[-1]
    assert change["points"] == -50.0 and 0 < change["p"] < 1


def test_a_wave_published_before_weights_is_sized_from_its_answers(tmp_path):
    wave(tmp_path, 1, [0, 1, 3])
    path = tmp_path / "waves" / "1" / "people.json.gz"
    people = json.loads(gzip.decompress(path.read_bytes()))
    del people["weights"]   # an older publication: no weights stored (the local preview's data, 22 Nov 2026)
    path.write_bytes(gzip.compress(json.dumps(people).encode()))
    ask_engine.people_of.cache_clear()
    assert ask_engine.size_of(people) == 5
    assert [(r["n"], r["base"]) for r in ask_engine.run({"waves": ["d"], "ask": {"q": "D28", "any": True}}, tmp_path, {"d": 1})] == [(3, 5)]
