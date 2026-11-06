"""Expected vs actual (etl/expectations.py) against the 7 Oct 2026 seasonal report it reproduces ("Seasonal Shopping,
4Q26"), and the rules that pair surveys and answers.

Real data (tests/fixtures/expectations_halloween_black_friday.json): the Halloween and Black Friday question files cut
to the surveys before and after each event and to the total, and the open Halloween spend answers (HW4) of the 3 Nov
2025 and 14 Sep 2026 surveys. The report's Expectations 2026 are one respondent fewer than CIP's 14 Sep 2026 survey
(401 against 402: one was removed after CIP loaded it), so those figures may differ by 0.1-0.3."""
import json
from datetime import date
from pathlib import Path

from etl import expectations
from etl.weekly_report import Question

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "expectations_halloween_black_friday.json").read_text())


def built() -> dict:
    """The events built from the fixture, by name."""
    questions = {code: Question(file) for code, file in FIXTURE["files"].items()}
    numbers = {(int(survey_id), "HW4"): values for survey_id, values in FIXTURE["spend"].items()}
    return {e["name"]: e for e in expectations.build(questions, numbers)["events"]}


def comparison(event: dict, expected: int, actual: int) -> dict:
    return next(c for c in event["comparisons"] if c["expected"]["survey_id"] == expected and c["actual"]["survey_id"] == actual)


def rows(compared: dict, code: str) -> dict:
    question = next(q for q in compared["questions"] if q["expected_code"] == code)
    return {row["label"]: (row["expected"], row["actual"]) for row in question["rows"]}


def test_halloween_expectations_2026_against_actual_2025_match_the_report():
    halloween = comparison(built()["Halloween"], 264, 443)
    spent = rows(halloween, "HW1")
    assert spent["I will spend on Halloween this year"] == (54.5, 49.6)                         # printed 54.4% and 49.6%
    assert spent["I will celebrate but will not spend on Halloween this year"] == (20.6, 29.4)  # 20.7% and 29.4%: 8.7 PPTs
    assert spent["I don't celebrate or spend on Halloween"] == (24.9, 21.0)                     # 24.9% and 21.0%
    spend = halloween["spend"]
    assert (spend["expected"]["median"], spend["actual"]["median"]) == (100, 65)               # "$100" and "$65"
    assert spend["expected"]["market_billions"] == 14.7                                         # "around $14.7 billion"
    net = next(q for q in halloween["questions"] if q["expected_code"] == "HW2")["net"]
    assert net["expected"] < 0 and round(abs(net["expected"] + 2.0), 1) <= 0.3                          # "net 2.0% expect to spend less"


def test_black_friday_expectations_2026_against_actual_2025_match_the_report():
    friday = comparison(built()["Black Friday"], 258, 452)
    assert rows(friday, "BF1") == {"Yes": (64.6, 46.8), "No": (35.4, 53.2)}                    # Figure 2, left
    assert sorted(rows(friday, "BF2").values()) == [(15.8, 19.6), (38.2, 50.3), (45.9, 30.2)]  # Figure 2, right: in store, online, both
    retailers = rows(friday, "BF5")
    assert retailers["Amazon"][0] == 73.4 and retailers["Walmart"][0] == 56.0                  # "a lead of 17.4 PPTs"
    question = next(q for q in friday["questions"] if q["expected_code"] == "BF2")
    assert (question["expected_base"], question["actual_base"]) == (259, 189)                  # the report's bases


def test_each_expectation_survey_is_compared_with_the_same_season_and_the_year_before():
    pairs = [(c["expected"]["survey_id"], c["actual"]["survey_id"], c["same_season"]) for c in built()["Halloween"]["comparisons"]]
    assert pairs == [(264, 443, False), (433, 443, True)]   # Sep 2026 against Nov 2025; Sep 2025 against Nov 2025


def test_a_reworded_multi_choice_list_pairs_by_position():
    celebrate = rows(comparison(built()["Halloween"], 433, 443), "HW5")
    assert "Pass out candy" in celebrate and "Passed out candy" not in celebrate   # shown once, under the expected wording
    question = next(q for q in comparison(built()["Halloween"], 433, 443)["questions"] if q["expected_code"] == "HW5")
    assert next(r["actual_label"] for r in question["rows"] if r["label"] == "Pass out candy") == "Passed out candy"


def test_net_scores_only_for_the_questions_listed():
    halloween = comparison(built()["Halloween"], 264, 443)
    assert [q["expected_code"] for q in halloween["questions"] if q["net"]] == ["HW2"]


def test_a_wave_far_from_the_event_belongs_to_neither_side():
    from tests.test_weekly_report import tiny_file
    question = Question(tiny_file([[(40, 100), (60, 100)]] * 3))
    question.days = [date(2026, 1, 12), date(2026, 9, 14), date(2026, 11, 2)]   # a January follow-up, before, after
    assert expectations.waves_around(question, "10-31", before=True) == [1]
    assert expectations.waves_around(question, "10-31", before=False) == [2]


def test_a_reordered_multi_choice_list_pairs_by_label():
    from tests.test_weekly_report import tiny_file
    before = tiny_file([[(10, 100), (20, 100)]], labels=("Candy", "Costumes"))
    after = tiny_file([[(30, 100), (40, 100)]], labels=("Costumes", "Candy"))
    for file in (before, after):
        file["answers"] = [[label, None, label] for _, _, label in file["answers"]]   # multi-choice: no codes
    pairs = expectations.pair_answers(Question(before), 0, Question(after), 0)
    assert pairs == [(0, 1), (1, 0)]


def test_a_code_reused_for_another_question_is_left_out():
    """M1 asked about mass merchants in Dec 2025 and about Memorial Day plans in Mar 2026: only the second is an
    expectation of Memorial Day (config/expectations.yml mentions: memorial day)."""
    from tests.test_weekly_report import tiny_file
    before = tiny_file([[(40, 100), (60, 100)]] * 2)
    before["waves"] = [[1, "2025-12-08", 1], [2, "2026-03-09", 2]]
    before["versions"] = ["Have you purchased from any of these mass merchandisers?", "Do you expect to spend money on Memorial Day 2026?"]
    before["qcode"] = "M1"
    after = tiny_file([[(30, 100), (70, 100)]])
    after["waves"] = [[3, "2026-06-01", 1]]
    after["versions"] = ["Did you spend money on Memorial Day 2026?"]
    after["qcode"] = "C4"
    numbers = {}
    memorial = next(e for e in expectations.build({"M1": Question(before), "C4": Question(after)}, numbers)["events"]
                    if e["name"] == "Memorial Day")
    assert [(c["expected"]["survey_id"], c["actual"]["survey_id"]) for c in memorial["comparisons"]] == [(2, 3)]


def test_an_outlook_question_gives_each_surveys_answers_and_net_more():
    """HX2 on 28 Sep 2026 as the report prints it: 12.5 + 19.0 ... "Net More: 4.6%" (made-up counts, same shares)."""
    from tests.test_weekly_report import tiny_file
    labels = ("Spend a lot less", "Spend slightly less", "Spend around the same", "Spend slightly more", "Spend a lot more", "Don't know")
    file = tiny_file([[(125, 1000), (125, 1000), (382, 1000), (190, 1000), (106, 1000), (72, 1000)]], labels)
    file["answers"] = [[label, code + 1, label] for code, (_, _, label) in enumerate(file["answers"])]
    found = expectations.outlook(Question(file), "Holiday spending")
    assert found["net"] == [4.6] and found["rows"][2]["values"] == [38.2] and found["bases"] == [1000]
