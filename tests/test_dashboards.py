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


def test_last_year_by_the_databank_rule_is_the_same_wave_number_of_last_season():
    prior, ly = dashboards.comparisons(WAVES, WAVES[3], "same_wave_number")
    assert prior["survey_id"] == 266 and ly["survey_id"] == 240                # wave 3 2025 (27 Oct), loaded


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


def test_monthly_topic_last_year_is_the_nearest_wave_about_a_year_earlier():
    topic = [{"survey_id": s, "season": None, "series_wave_no": n, "launched_on": d, "qualified": 400}
             for s, n, d in [(433, 4, date(2025, 9, 29)), (440, 5, date(2025, 10, 27)), (258, 16, date(2026, 8, 31)), (235, 17, date(2026, 9, 28))]]
    prior, ly = dashboards.comparisons(topic, topic[3], "nearest_year_ago")
    assert prior["survey_id"] == 258 and ly["survey_id"] == 433
    assert dashboards.comparisons(topic, topic[1], "nearest_year_ago")[1] is None   # nothing within a month of a year ago


def test_significance_matches_the_two_proportion_z_test():
    assert dashboards.significant(55.0, 400, 45.0, 400)          # 10 pts on 400 each: p ≈ 0.005
    assert not dashboards.significant(52.0, 400, 50.0, 400)      # 2 pts: noise
    assert not dashboards.significant(50.0, 0, 40.0, 400)


def test_takeaways_mention_only_significant_comparable_changes():
    cfg = {"tiles": [{"code": "hurts", "label": "Tariffs hurt me", "head": "Tariffs", "say": "say tariffs hurt them"}],
           "lists": [], "segments": []}
    row = {"metric_code": "hurts", "segment": "Total", "rank_no": 0, "label": "x", "pct": 44.0, "base_n": 400,
           "prior_pct": 60.0, "prior_base_n": 400, "ly_pct": 43.0, "ly_base_n": 400, "flags": "", "sig": {"prior"}}
    assert dashboards.takeaways([row], cfg) == ["Tariffs: 44% say tariffs hurt them (down 16.0 pts vs the previous wave; 43% a year ago)."]
    assert dashboards.takeaways([{**row, "sig": set()}], cfg) == ["Tariffs: 44% say tariffs hurt them (43% a year ago)."]   # the ETL's flag, not a test here
    assert dashboards.takeaways([{**row, "sig": None}], cfg) == [   # a wave built before the flags: one test, said so
        "Tariffs: 44% say tariffs hurt them (down 16.0 pts vs the previous wave, single comparison; 43% a year ago)."]
    row["flags"] = "base_changed_prior"
    assert dashboards.takeaways([row], cfg) == ["Tariffs: 44% say tariffs hurt them (43% a year ago)."]
