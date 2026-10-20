"""The sample dashboard's backend builder (api/dashboards.py): its comparison rules: which wave is "prior week" and "last year", and the flags
that stop a reader comparing unlike bases (the 2026 Holiday XM1 routing change, wave 2 → 3)."""
from datetime import date

from api import dashboards

CFG = {"small_base": 50}
WAVES = [
    {"survey_id": None, "season": 2025, "series_wave_no": 1, "launched_on": date(2025, 10, 13), "qualified": None},
    {"survey_id": 240, "season": 2025, "series_wave_no": 3, "launched_on": date(2025, 10, 27), "qualified": 402},
    {"survey_id": 266, "season": 2026, "series_wave_no": 2, "launched_on": date(2026, 10, 5), "qualified": 401},
    {"survey_id": 412, "season": 2026, "series_wave_no": 3, "launched_on": date(2026, 10, 12), "qualified": 404},
]


def test_prior_is_previous_wave_and_last_year_is_same_calendar_week():
    prior, ly = dashboards.comparisons(WAVES, WAVES[3])
    assert prior["survey_id"] == 266
    assert ly["launched_on"] == date(2025, 10, 13) and ly["survey_id"] is None   # hibernated: reported, not skipped


def test_routing_change_is_flagged_and_small_bases_are_marked():
    wave, prior = WAVES[3], WAVES[2]
    row = dashboards.metric("bought_7d", "BOUGHT", (125, 404), (92, 149), None, (wave, prior, None), CFG)
    assert round(row["pct"], 1) == 30.9 and round(row["prior_pct"], 1) == 61.7
    assert row["flags"] == "base_changed_prior,ly_missing"    # 149/401 asked last week vs 404/404 now
    small = dashboards.metric("started_by_generation", "GenZ", (20, 42), (19, 40), None, (wave, prior, None), CFG, "GenZ")
    assert small["flags"].startswith("small_base") and "base_changed_prior" not in small["flags"]


def test_share_sums_answer_codes_over_the_question_base():
    cube = {(412, "XM3", "total", "Total"): {"base": 404, "built_at": None, "answers": {"1": 222, "2": 117, "3": 32, "4": 33}}}
    assert dashboards.share(cube, WAVES[3], "XM3", [2, 3]) == (149, 404)        # started = still shopping + finished
    assert dashboards.share(cube, WAVES[0], "XM3", [1]) is None                 # wave not loaded
