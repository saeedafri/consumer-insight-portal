"""The weekly report's numbers (etl/weekly_report.py) against the PDF report they reproduce, and each calculation alone.

The first test uses real data: the food-retailer question (q4) for the 16 weeks the 3 Nov 2026 report's Figure 6 needs
(tests/fixtures/weekly_report_q4.json, the total cut only). The others use small made-up files whose answers are
easy to work out by hand."""
import json
from pathlib import Path

from etl import weekly_report as report

FIXTURE = Path(__file__).parent / "fixtures" / "weekly_report_q4.json"


def test_the_food_retailer_table_matches_figure_6_of_the_3_november_2026_report():
    question = report.Question(json.loads(FIXTURE.read_text()))
    table = report.table(question, question.wave_of("2026-10-26"))
    walmart = next(row for row in table["rows"] if row["label"] == "Walmart")
    printed = [57.7, 59.3, 60.7, 61.1, 61.0, 61.2, 62.3, 61.7, 64.1, 63.9, 62.5, 63.8, 63.0]   # Figure 6, as printed
    assert all(round(abs(ours - theirs), 1) <= 0.1 for ours, theirs in zip(walmart["values"], printed))   # rounding only
    assert (walmart["week_change"], walmart["quarter_change"]) == (-0.8, 5.4)                    # (0.8) and 5.4 printed
    assert table["dates"][0] == "2026-08-03" and table["dates"][-1] == "2026-10-26"
    highlighted = {row["label"][:14] for row in table["rows"] if row["quarter_significant"]}
    assert highlighted == {"Walmart", "Amazon", "Dollar General", "Family Dollar"}               # the PDF's red figures
    assert table["rows"][0]["label"] == "Walmart"                                                 # biggest first
    assert not any(row["values"][-1] == 0.0 for row in table["rows"])   # answers of the code's older question are left out


def tiny_file(weeks: list[list[tuple[int, int]]], labels=("Yes", "No")) -> dict:
    """A question file with one cut (Total): weeks[k] is [(n, base) per answer] for the week k weeks after 5 Jan 2026."""
    from datetime import date, timedelta
    file = {"qcode": "t1", "waves": [], "versions": [], "answers": [[label, i, label] for i, label in enumerate(labels)],
            "cuts": [["total", "Total"]], "w": [], "c": [], "a": [], "n": [], "b": []}
    for k, answers in enumerate(weeks):
        file["waves"].append([k, (date(2026, 1, 5) + timedelta(weeks=k)).isoformat(), 1])
        for a, (n, base) in enumerate(answers):
            file["w"].append(k); file["c"].append(0); file["a"].append(a); file["n"].append(n); file["b"].append(base)
    return file


def test_a_rolling_average_needs_four_whole_weeks():
    assert report.rolling([10.0, 20.0, 30.0, 40.0]) == 25.0
    assert report.rolling([10.0, None, 30.0, 40.0]) is None        # a week not asked: no average, never a 3-week one
    assert report.rolling([10.0, 20.0]) is None


def test_a_missing_week_does_not_shift_the_others():
    weeks = [[(40, 100), (60, 100)]] * 5
    file = tiny_file(weeks)
    del file["waves"][2]                                           # 19 Jan never fielded: the dates jump a week
    keep = [k for k, w in enumerate(file["w"]) if w != 2]
    for key in ("w", "c", "a", "n", "b"):
        file[key] = [file[key][k] for k in keep]
    file["w"] = [w - 1 if w > 2 else w for w in file["w"]]
    question = report.Question(file)
    assert report.window(question, len(question.dates) - 1, 5) == [0, 1, None, 2, 3]


def test_the_one_week_and_three_month_changes_and_their_significance():
    # "Yes" sits at 20 % for 13 weeks, then 35 % for the last 4: a big three-month rise, a smaller one-week rise
    weeks = [[(80, 400), (320, 400)]] * 12 + [[(140, 400), (260, 400)]] * 4
    question = report.Question(tiny_file(weeks))
    yes = next(row for row in report.table(question, 15)["rows"] if row["label"] == "Yes")
    assert yes["values"][0] == 20.0 and yes["values"][-1] == 35.0
    assert yes["quarter_change"] == 15.0 and yes["quarter_significant"]
    assert yes["week_change"] == 3.8                    # the four-week averages: 35.0 against (20 + 35 * 3) / 4 = 31.25
    assert not yes["week_significant"]                    # tested on single weeks: last week and this week are both 35 %


def test_significance_corrects_for_testing_many_answers():
    big = (400, 1600, 500, 1600)        # 25 % -> 31 %: real
    small = (400, 1600, 420, 1600)      # 25 % -> 26 %: noise
    assert report.significant([big, small]) == [True, False]
    assert report.significant([]) == []


def test_net_better_is_better_minus_worse_and_income_groups_add_their_bands():
    labels = ("Much worse", "Somewhat worse", "About the same", "Somewhat better", "Much better")
    file = tiny_file([[(10, 100), (20, 100), (30, 100), (25, 100), (15, 100)]], labels)
    file["cuts"] += [["income_band", "under $25,000"], ["income_band", "$25,000 - $49,999"]]
    for c, counts in ((1, (5, 5, 10, 10, 20)), (2, (20, 10, 10, 5, 5))):   # two bands of 50 people each
        for a, n in enumerate(counts):
            file["w"].append(0); file["c"].append(c); file["a"].append(a); file["n"].append(n); file["b"].append(50)
    question = report.Question(file)
    assert report.net(question, 0, [0]) == 10.0                         # (25 + 15) - (10 + 20)
    low = report.income_cuts(question)["<$50,000"]
    assert report.net(question, 0, low) == 0.0                         # (30 - 10 + 10 - 30) of 100: both bands together


def test_the_three_data_points_are_the_biggest_significant_moves_one_per_table():
    def row(label, change, significant):
        return {"label": label, "values": [20.0, 20.0 + change], "quarter_change": change, "quarter_significant": significant}
    tables = [{"name": "Food", "dates": ["a", "b"], "rows": [row("Walmart", 5.4, True), row("Amazon", 6.0, True)]},
              {"name": "Online", "dates": ["a", "b"], "rows": [row("Food", 5.6, True), row("Toys", 9.9, False)]},
              {"name": "Activities", "dates": ["a", "b"], "rows": [row("Dining out", -6.2, True)]},
              {"name": "In store", "dates": ["a", "b"], "rows": [row("Pets", 1.0, True)]}]
    points = report.three_points(tables)
    assert [(p["section"], p["label"], p["change"]) for p in points] == [
        ("Activities", "Dining out", -6.2), ("Food", "Amazon", 6.0), ("Online", "Food", 5.6)]


def test_margins_of_error_match_the_report_methodology():
    assert report.margin_of_error(400) == 4.9      # "maximum margin of error of ±4.9%" weekly
    assert report.margin_of_error(1600) == 2.4     # "±2.4%" for the four-week rolling average
    waves = [{"wave_date": f"2026-10-{d:02d}", "qualified_n": n} for d, n in ((5, 401), (12, 404), (19, 400), (26, 404))]
    method = report.methodology(waves, "2026-10-26")
    assert method["weeks"][0] == {"date": "2026-10-26", "respondents": 404} and method["weekly_margin"] == 4.9


def test_news_events_are_dated_text():
    events = report.news_events()
    assert events and all(isinstance(e["date"], str) and e["kind"] in ("economy", "retail") for e in events)


def test_publish_writes_a_report_for_each_wave_that_asks_todays_questions(tmp_path, monkeypatch):
    """etl/publish.py calls weekly_report.publish after writing the question files: each tracker wave that asked the
    report's questions as worded today gets api/v1/waves/<id>/report.json.gz, read back as the portal reads it. The
    first week here is made to ask another question under the same code, as the tracker did before Jul 2025."""
    import gzip
    from etl import publish
    fixture = json.loads(FIXTURE.read_text())
    fixture["versions"] = ["Which, if any, of these categories have you purchased?", *fixture["versions"]]
    fixture["waves"] = [[w[0], w[1], 1 if k == 0 else w[2] + 1] for k, w in enumerate(fixture["waves"])]
    folder = tmp_path / "api/v1/questions/CSI-US/tracker"
    folder.mkdir(parents=True)
    for code in (section["question"] for section in report.settings()["sections"]):   # all read the food data here
        (folder / f"{code}.json.gz").write_bytes(gzip.compress(json.dumps({**fixture, "qcode": code}).encode()))
    waves = [{"survey_id": 100 + i, "wave_date": w[1], "survey_family": "CSI-US", "study_type": "tracker",
              "qualified_n": 400} for i, w in enumerate(fixture["waves"])]
    fixture_ids = {w[1]: w[0] for w in fixture["waves"]}
    for wave in waves:   # the fixture's own wave ids are its positions; the report looks waves up by date
        wave["survey_id"] = fixture_ids[wave["wave_date"]]
    (tmp_path / "api/v1/waves.json.gz").write_bytes(gzip.compress(json.dumps(waves).encode()))
    monkeypatch.setattr(report, "profile_cells", lambda ids: [
        {"survey_id": ids[-1], "qcode": "q4", "label": "Walmart", "n": 250, "age_sum": 11750, "age_n": 250,
         "income_sum": 23750, "income_n": 250}])
    assert report.publish(tmp_path, publish.write) > 0
    newest = waves[-1]["survey_id"]
    written = json.loads(gzip.decompress((tmp_path / f"api/v1/waves/{newest}/report.json.gz").read_bytes()))
    assert written["wave_date"] == "2026-10-26"
    assert written["three_points"] == []   # the first table week lacks its four weeks: no three-month change to rank
    assert written["profiles"] == [{"title": "Food shoppers", "rows": [{"label": "Walmart", "shoppers": 250, "age": 47, "income_k": 95}]}]
    assert not (tmp_path / f"api/v1/waves/{waves[0]['survey_id']}/report.json.gz").exists()   # asked another question
    listed = json.loads(gzip.decompress((tmp_path / "api/v1/reports.json.gz").read_bytes()))
    assert listed == [w["survey_id"] for w in waves[1:]]                                      # the menu link's list
    walmart = written["tables"][0]["trend"]["lines"]["Walmart"]                                # Figure 5's line
    assert len(walmart) == 53 and walmart[-1] == written["tables"][0]["rows"][0]["values"][-1]
    assert walmart[:3] == [None, None, None]   # the other question's week is never averaged in



def test_a_wave_fielded_off_its_monday_still_counts_as_its_week():
    """Tue 3 Sep 2024 was that week's wave: a table ending there must find it and the weeks before."""
    weeks = [[(40, 100), (60, 100)]] * 16
    file = tiny_file(weeks)
    file["waves"][-1][1] = "2026-04-21"   # the last wave fielded on a Tuesday, a day after its Monday
    question = report.Question(file)
    assert question.wave_of("2026-04-20") == 15
    assert len(report.table(question, 15)["rows"]) == 2


def test_two_waves_on_one_date_are_told_apart_by_id():
    file = tiny_file([[(40, 100), (60, 100)]] * 2)
    file["waves"][1][1] = file["waves"][0][1]   # two panels fielded the same day
    question = report.Question(file)
    assert (question.position(0), question.position(1)) == (0, 1)


def test_a_report_file_of_a_wave_no_longer_recent_is_removed(tmp_path, monkeypatch):
    old = tmp_path / "api/v1/waves/1/report.json.gz"
    old.parent.mkdir(parents=True)
    old.write_bytes(b"old")
    (tmp_path / "api/v1/waves.json.gz").write_bytes(__import__("gzip").compress(b"[]"))
    monkeypatch.setattr(report, "profile_cells", lambda ids: [])
    report.publish(tmp_path, lambda *a: 0)
    assert not old.exists()


def test_the_appendix_gives_worse_better_and_net_with_their_changes():
    labels = ("Much worse", "Somewhat worse", "About the same", "Somewhat better", "Much better")
    weeks = [[(10, 100), (10, 100), (40, 100), (20, 100), (20, 100)]] * 31   # 20 % worse, 40 % better every week
    question = report.Question(tiny_file(weeks, labels))
    data = report.appendix(question, 30)
    rows = {row["label"]: row for row in data["four_week"]["All respondents"]}
    assert len(data["dates"]) == 28 and rows["Total worse"]["values"][-1] == 20.0 and rows["Total better"]["values"][-1] == 40.0
    assert rows["Net better"]["values"][-1] == 20.0 and rows["Net better"]["week_change"] == 0.0
    assert data["weekly"][2]["four_week_change"] == 0.0
