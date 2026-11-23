"""Checks the plan writer's training-pair builder (scripts/ask_plan_pairs.py) on its own functions, no data or model: a
hand-written plan becomes the model's compact form, codes become candidate numbers, the answers the model sees always
include the plan's own (cut the same way in the plan), and a scale's one side is found for a net."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ask_plan_pairs as pairs  # noqa: E402


def test_a_plan_becomes_the_models_compact_form_with_candidate_numbers():
    plan = {"waves": ["2026-11-16"], "among": {"q": "D28", "any": True}, "ask": {"q": "D31", "is": ["Have used GenAI to shop"]},
            "by": {"groups": {"18-34": {"q": "D2", "between": [18, 34]}, "55+": {"q": "D2", "between": [55, 120]}, "women": {"q": "D1", "is": ["Female"]}}}}
    model = pairs.to_model(plan)
    assert model == {"op": "share", "ask": {"q": "D31", "a": ["Have used GenAI to shop"]}, "among": {"q": "D28", "any": 1},
                     "by": [{"name": "18-34", "c": {"demo": "age:18-34"}}, {"name": "55+", "c": {"demo": "age:55+"}},
                            {"name": "women", "c": {"demo": "sex:F"}}]}
    assert pairs.codes_in(model) == ["D31", "D28"]   # demographics are never candidates
    assert pairs.numbered(model, {"D31": 4, "D28": 2})["ask"]["q"] == 4
    funnel = pairs.to_model({"op": "chain", "steps": [{"q": "D28", "any": True}, {"not": {"q": "D33", "is": ["Yes"]}}]})
    assert funnel == {"op": "chain", "steps": [{"q": "D28", "any": 1}, {"not": {"q": "D33", "a": ["Yes"]}}]}


def test_the_model_always_sees_the_answers_its_plan_names():
    answers = [f"Answer number {i} with a long label that runs past forty characters" for i in range(10)]
    shown = pairs.visible(answers, [answers[8]])
    assert len(shown) == pairs.ANSWERS and shown[0] == answers[8][:pairs.ANSWER_CHARS]   # the 9th answer, first, cut to 40
    plan = pairs.shorten({"op": "share", "ask": {"q": "X1", "a": [answers[8]]}})
    assert plan["ask"]["a"][0] in shown   # the plan names it exactly as the model sees it
    assert pairs.answers_used({"ask": {"both": [{"q": "A", "a": ["x"]}, {"q": "B", "a": ["y"]}]}}) == {"A": ["x"], "B": ["y"]}


def test_a_net_takes_one_side_of_a_scale_never_its_negation():
    assert pairs.scale_pair({"answers": ["Much better", "Somewhat better", "About the same", "Somewhat worse", "Much worse"]}) == \
        ["Much better", "Somewhat better"]
    assert pairs.scale_pair({"answers": ["Very likely", "Somewhat likely", "Not likely"]}) == ["Very likely", "Somewhat likely"]
    assert pairs.scale_pair({"answers": ["Yes", "No"]}) is None
