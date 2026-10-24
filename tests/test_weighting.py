"""Census weighting (etl/weighting.py): raking hits every margin's share and keeps the average weight at 1."""
from etl.weighting import rake


def test_raking_matches_each_margin_and_averages_one():
    people = {i: {"gender": g, "region": r} for i, (g, r) in enumerate(
        [("Male", "South")] * 30 + [("Female", "South")] * 40 + [("Male", "West")] * 10 + [("Female", "West")] * 20)}
    w = rake(people, {"gender": {"Male": 50, "Female": 50}, "region": {"South": 60, "West": 40}})
    share = lambda k, v: sum(w[i] for i, p in people.items() if p[k] == v) / sum(w.values())
    assert abs(share("gender", "Male") - 0.5) < 1e-4 and abs(share("region", "West") - 0.4) < 1e-4
    assert abs(sum(w.values()) / len(w) - 1) < 1e-9


def test_missing_values_sit_out_their_margin_and_no_profile_means_no_weighting():
    people = {1: {"gender": "Male"}, 2: {"gender": "Female"}, 3: {"gender": "Female"}, 4: {"gender": None}}
    w = rake(people, {"gender": {"Male": 50, "Female": 50}})
    assert abs(w[1] - 2 * w[2]) < 1e-6                      # one man stands for as many as two women
    assert rake({1: {"gender": None}}, {"gender": {"Male": 50, "Female": 50}}) == {1: 1.0}


def test_weights_are_trimmed():
    people = {i: {"gender": "Male" if i == 0 else "Female"} for i in range(100)}
    w = rake(people, {"gender": {"Male": 50, "Female": 50}}, trim=(0.2, 5.0))
    assert max(w.values()) / (sum(w.values()) / len(w)) <= 5.0 + 1e-6
