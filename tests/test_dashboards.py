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


def test_each_list_carries_its_heading_for_the_trackers_excel_tabs():
    """The tracker's Excel names a list's tab by its heading (Top platforms), not its code (top): 27 Nov 2026."""
    board = dashboards.payload({"dashboard_code": "social_commerce", "wave": None, "prior": None, "ly": None, "waves": [],
                                "cube_built_at": None}, [])
    assert board["list_heads"]["top"] == "Top platforms" and set(board["list_heads"]) == set(board["lists"])


def test_a_published_dashboard_file_gains_its_list_headings_at_the_next_publish(tmp_path):
    """A stored build has no headings until its tracker's next week is built; write_views gives them at the next
    publish or deploy (27 Nov 2026), and leaves a file that already has them alone."""
    import gzip
    import json
    from etl.publish import write
    path = tmp_path / "api/v1/dashboards/social_commerce/1.json.gz"
    path.parent.mkdir(parents=True)
    path.write_bytes(gzip.compress(json.dumps({"title": "Social Commerce", "lists": {"top": []}}).encode()))
    assert dashboards.name_lists(tmp_path, write) > 0
    doc = json.loads(gzip.decompress(path.read_bytes()))
    assert doc["list_heads"]["top"] == "Top platforms" and doc["title"] == "Social Commerce"
    assert dashboards.name_lists(tmp_path, write) == 0


def test_each_figure_is_rounded_once_from_its_counts():
    """28 Nov 2026 check: 46 of 342 (13.4503%) showed 13.4 after rounding to 3 decimals and then 1; a change of 50/404
    against 118/401 showed -17.0 (the 3-decimal values' difference), exact -17.05."""
    wave, prior = WAVES[3], WAVES[2]
    row = dashboards.metric("shop_used", "Have shopped with GenAI", (46, 342), (118, 401), None, (wave, prior, None), CFG)
    board = dashboards.payload({"dashboard_code": "genai", "wave": wave, "prior": prior, "ly": None, "waves": [], "cube_built_at": None}, [row])
    assert board["tiles"]["shop_used"]["pct"] == 13.5
    row = dashboards.metric("shop_used", "Have shopped with GenAI", (50, 404), (118, 401), None, (wave, prior, None), CFG)
    board = dashboards.payload({"dashboard_code": "genai", "wave": wave, "prior": prior, "ly": None, "waves": [], "cube_built_at": None}, [row])
    assert board["tiles"]["shop_used"]["vs_prior"] == -17.1


class Questions:
    """A database connection that answers meanings()' one query: (survey_id, qcode, qtype, value code, label)."""
    def __init__(self, rows):
        self.rows = rows

    def execute(self, *_):
        return self.rows


def test_glp1_compares_each_question_with_the_last_week_that_asked_it(monkeypatch):
    """28 Nov 2026 check. GLP-1's 10 Nov 2025 (446) reused GP2-GP5 for other questions (GP4, GP5 single-choice): its
    lists showed option codes ("2: 48.4%"), and 16 Nov 2026 (688) took it as last year, so every list row read "last
    year 0.0%" (+45.3 pts). Now 446 is no wave of the tracker, last year is 20 Oct 2025 (441, which asked them all),
    an answer last year did not offer has no comparison (GenAI's Claude), and a figure whose question the previous
    wave skipped compares with the one before and names it (Tariffs' 26 Oct 2026 asked only IN1 and IN2)."""
    def wave(sid, day):
        return {"survey_id": sid, "season": None, "series_wave_no": 0, "launched_on": date.fromisoformat(day),
                "wave_date": date.fromisoformat(day), "qualified": 400}
    monkeypatch.setattr(dashboards, "series", lambda conn, module: [
        wave(441, "2025-10-20"), wave(446, "2025-11-10"), wave(265, "2026-09-21"), wave(415, "2026-10-19"), wave(688, "2026-11-16")])
    usual = [("GP1", "single", 1, "Yes"), ("GP2", "single", 1, "Weight loss"), ("GP3", "single", 4, "Less"),
             ("GP4", "multi", None, None), ("GP5", "multi", None, None)]
    questions = [(sid, *q) for sid in (441, 265, 688) for q in usual] + [(415, *usual[0])] + [
        (446, "GP2", "single", 1, "Fewer items"), (446, "GP4", "single", 1, "Less than $100"), (446, "GP5", "single", 1, "Yes, definitely")]
    nutrition, vitamins = "I am paying more attention to the nutritional content", "I have started taking more vitamins and supplements"
    def cell(base, **answers):
        return {"base": base, "built_at": "2026-11-26 17:23:00", "flags": {}, "answers": answers}
    cube = {(441, "GP5", "total", "Total"): cell(75, **{nutrition: 27}), (265, "GP5", "total", "Total"): cell(70, **{nutrition: 28}),
            (688, "GP5", "total", "Total"): cell(64, **{nutrition: 29, vitamins: 20}),
            (446, "GP5", "total", "Total"): cell(62, **{"1": 18, "2": 30, "3": 14}),
            (415, "GP1", "total", "Total"): cell(401, **{"1": 60}), (688, "GP1", "total", "Total"): cell(404, **{"1": 64})}
    monkeypatch.setattr(dashboards, "cells", lambda conn, ids, *_: {k: c for k, c in cube.items() if k[0] in ids})
    conn = Questions(questions)

    header, rows = dashboards.compute(conn, "glp1", 688)
    assert (header["prior"]["survey_id"], header["ly"]["survey_id"]) == (415, 441)
    board = dashboards.payload(header, rows)
    top, second = board["lists"]["changes"]
    assert (top["label"], top["pct"], top["ly_pct"], top["vs_ly"]) == (nutrition, 45.3, 36.0, 9.3)
    assert top["prior_week"] == "2026-09-21" and top["vs_prior"] == 5.3   # 415 asked GP1 only: GP5 compares with 265
    assert (second["label"], second["ly_pct"], second["vs_ly"]) == (vitamins, None, None)   # not offered in 441: not 0 %
    assert board["tiles"]["using"]["prior_week"] is None and board["wave"]["wave_no"] == 4   # 446 is not counted
    assert board["takeaways"][1] == (f"Since starting: {nutrition} (45%), {vitamins} (31%) are the top changes among users (n=64).")
    # (before: "Biggest significant move vs last year: ... vitamins ... (+31.2 pts" against a 0 % it never had)
    assert dashboards.compute(conn, "glp1", 446)[1] == []   # its own lists are left out: nothing to publish
