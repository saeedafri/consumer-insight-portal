"""Tests for api/ask_layout.py: one per answer type (01-template-spec.md section 4.4), each checking what the answer says
and draws, not only which survey question was picked: the country noun, the period, the group, the chart kind and the
headline's verb (rose or about the same, by the 95% test). The figures are small made-up surveys of 400 people; the
beauty figures are the checked sample set's (docs/research/ask-cip-rebuild-2026-11-27/mockups/samples.md)."""
import numpy as np

from api import ask_layout
from api.ask_figures import label_date

BEAUTY = {"family": "CSI-US", "text": "Have you purchased any beauty products (whether for men or women) in the past three months?",
          "name": "Recent beauty product purchases"}
NEWEST = "2026-11-23"


def figures(days, answers, people, bases=400, columns=(("total", "Total"),), grain=None, labels=None):
    """A fig as api/ask_figures.py compute returns it: people[p][c][a] with one base for every cell."""
    people = np.array(people, dtype=float)
    bases = np.full(people.shape, bases, dtype=float) if np.isscalar(bases) else np.array(bases, dtype=float)
    periods = [{"label": (labels or {}).get(d) or label_date(d), "from": d, "to": d, "waves": [i], "versions": [1]}
               for i, d in enumerate(days)]
    return {"periods": periods, "columns": list(columns), "answers": list(answers), "people": people, "bases": bases,
            "pct": 100 * people / bases, "grain": grain, "asked": list(days), "missing": []}


def test_t1_latest_value_against_the_survey_before():
    fig = figures(["2026-09-28"], ["Yes", "No"], [[[264, 139]]], 403)
    out = ask_layout.build(fig, BEAUTY, {"kind": "share", "when": []}, [0], "US", NEWEST, before=("6 Jul 2026", 63.6, False))
    assert out["type"] == "T1" and out["chart"]["kind"] == "columns" and out["chart"]["categories"] == ["Yes", "No"]
    assert out["lead"] == ("In the latest survey (28 Sep 2026), 65.5% of US adults bought beauty products in the past three months, "
                           "about the same as on 6 Jul 2026 (63.6%).")
    assert [c["label"] for c in out["cards"]] == ["Latest survey", "Since 6 Jul 2026", "Said no"] and out["cards"][1]["value"] == "About the same"
    assert out["survey"] == "Coresight US Consumer Survey" and out["source"] == "Coresight US Consumer Survey, 28 Sep 2026"


def test_t2_trend_says_a_real_rise_and_how_this_year_moved():
    days = ["2025-09-01", "2026-01-05", "2026-04-06", "2026-07-06", "2026-10-05"]
    fig = figures(days, ["Yes", "No"], [[[160, 240]], [[200, 200]], [[204, 196]], [[208, 192]], [[212, 188]]])
    out = ask_layout.build(fig, BEAUTY, {"kind": "trend", "when": [{"all": True}]}, [0], "US", NEWEST)
    assert out["type"] == "T2" and out["chart"]["kind"] == "line" and out["chart"]["dates"] == days
    assert "53.0% of US adults bought beauty products" in out["lead"] and "13.0 percentage points higher than in September 2025 (40.0%)" in out["lead"]
    assert "has stayed between 50.0% and 53.0% during 2026" in out["lead"] and out["cards"][2]["value"] == "Steady"
    assert out["cards"][1]["tone"] == "up"


def test_t3_groups_tied_with_the_top_are_named_together():
    columns = [("generation", g) for g in ("GenZ", "Millennial", "GenX", "Boomer")]
    fig = figures(["2026-09-28"], ["Yes", "No"], [[[43, 18], [80, 31], [76, 29], [64, 61]]], [[[61, 61], [111, 111], [105, 105], [125, 125]]], columns)
    out = ask_layout.build(fig, BEAUTY, {"kind": "share", "when": [], "cuts": {"generation": None}}, [0], "US", NEWEST)
    assert out["type"] == "T3" and out["chart"]["kind"] == "columns" and out["chart"]["categories"] == ["Gen Z", "Millennials", "Gen X", "Boomers"]
    assert out["lead"].startswith("In the latest survey (28 Sep 2026), Gen Z, Millennials and Gen X in the US were about equally likely")
    assert "Boomers were the least likely (51.2%)" in out["lead"] and out["cards"][2]["note"] == "A real gap"


def test_t3_income_bands_become_three_groups():
    bands = ["under $25,000", "$25,000 - $49,999", "$50,000 - $99,999", "$100,000 - $149,999", "$150,000 - $199,999", "$200,000 or greater", "prefer not to say"]
    people = [[[30, 30], [50, 50], [70, 30], [40, 10], [20, 5], [20, 5], [5, 5]]]
    bases = [[[60, 60], [100, 100], [100, 100], [50, 50], [25, 25], [25, 25], [10, 10]]]
    fig = figures(["2026-09-28"], ["Yes", "No"], people, bases, [("income_band", b) for b in bands])
    out = ask_layout.build(fig, BEAUTY, {"kind": "share", "when": []}, [0], "US", NEWEST)
    assert out["chart"]["categories"] == ["Under $50k", "$50k-$99k", "$100k+"] and out["chart"]["series"][0]["data"] == [50.0, 70.0, 80.0]
    assert "adults in households earning $50k-$99k and $100k+ were about equally likely" in out["lead"]


def test_t4_ranked_list_leads_with_its_top_answer_drawn_as_bars():
    doc = {"family": "CSI-US", "text": "Which retailers have you bought beauty products from?", "name": "Beauty product retailers"}
    fig = figures(["2026-09-28"], ["Walmart", "Amazon.com", "Target", "None of these"], [[[172, 130, 90, 40]]], 403)   # more than one answer each: over 100%
    out = ask_layout.build(fig, doc, {"kind": "top", "when": []}, [0, 1, 2], "US", NEWEST)
    assert out["type"] == "T4" and out["chart"]["kind"] == "bars" and "None of these" not in out["chart"]["categories"]
    assert out["lead"].startswith("In the latest survey (28 Sep 2026), Walmart was the most common answer: 42.7% of US adults")
    assert out["notes"] == ["People could choose more than one answer, so the shares add up to more than 100%."]


def test_t5_two_periods_says_up_only_when_real():
    fig = figures(["2025-11-03", "2026-11-02"], ["Yes", "No"], [[[120, 280]], [[180, 220]]])
    out = ask_layout.build(fig, BEAUTY, {"kind": "change", "compare": True, "when": [{}, {}]}, [0], "US", NEWEST)
    assert out["type"] == "T5" and out["chart"]["kind"] == "paired"
    assert out["lead"] == "On 2 Nov 2026, 45.0% of US adults bought beauty products in the past three months, up 15.0 percentage points from 3 Nov 2025 (30.0%)."


def test_t11_a_scale_in_china_says_its_sides_and_the_country():
    doc = {"family": "CSI-CN", "text": "What are your expectations for the economy over the next 12 months?"}
    fig = figures(["2026-11-09"], ["Positive", "Negative", "Same as now", "Don't know"], [[[308, 75, 146, 21]]], 550)
    out = ask_layout.build(fig, doc, {"kind": "share", "when": []}, [0], "CN", NEWEST)
    assert out["type"] == "T11" and out["chart"]["kind"] == "columns" and out["chart"]["sides"][:2] == ["positive", "negative"]
    assert out["lead"] == "In the latest survey (9 Nov 2026), more adults in China said positive (56.0%) than negative (13.6%)."
    assert out["cards"][2]["value"] == "+42.4 pts" and out["survey"] == "Coresight China Consumer Survey"


def test_an_old_question_says_when_it_was_last_asked():
    fig = figures(["2024-05-13"], ["Yes", "No"], [[[200, 200]]])
    out = ask_layout.build(fig, BEAUTY, {"kind": "share", "when": []}, [0], "US", NEWEST)
    assert out["lead"].startswith("When last asked (13 May 2024), 50.0% of US adults")


def test_market_named_country_and_china_twins():
    # the market selector (27 Nov 2026): a country the question names wins over it; China's twins are listed in config
    from api import assistant
    assert assistant.named_country("Are Chinese consumers positive about the economy?") == "CN"
    assert assistant.named_country("Do Americans expect the economy to improve?") == "US"
    assert assistant.named_country("Did people buy beauty products?") is None
    assert assistant.TWINS["Q9"] == "CS2" and assistant.MARKET_NAMES["CN"] == "China"


def test_t8_an_amount_in_ranges_says_its_middle_and_average():
    doc = {"family": "CSI-US", "text": "How much did you spend on beauty products in the past three months?", "name": "Beauty spending"}
    fig = figures(["2026-09-28"], ["$1 - $25", "$26 - $50", "$51 - $75", "More than $100"], [[[80, 120, 100, 100]]])
    out = ask_layout.build(fig, doc, {"kind": "share", "when": []}, [0], "US", NEWEST, middle=("$26 - $50", 70))
    assert out["type"] == "T8" and out["chart"]["categories"] == ["$1 - $25", "$26 - $50", "$51 - $75", "More than $100"]
    assert out["lead"] == ("In the latest survey (28 Sep 2026), the middle answer among US adults was $26 - $50; "
                           "the average was about $70 (worked out from the ranges people chose).")


def test_t12_china_age_groups_name_the_country():
    doc = {"family": "CSI-CN", "text": "What are your expectations for the economy over the next 12 months?", "name": "Economic outlook"}
    columns = [("age_band", a) for a in ("18-25", "26-41", "42-57")]
    fig = figures(["2026-11-09"], ["Positive", "Negative"], [[[40, 10], [120, 30], [30, 20]]], [[[80, 80], [200, 200], [100, 100]]], columns)
    out = ask_layout.build(fig, doc, {"kind": "share", "when": []}, [0], "CN", NEWEST)
    assert "adults in China aged 18-25 and 26-41 were about equally likely" in out["lead"] and out["chart"]["categories"] == ["18-25", "26-41", "42-57"]


def test_a_line_offers_periods_by_how_often_it_is_asked_and_marks_an_unusual_reading():
    days = ["2026-01-05", "2026-02-02", "2026-03-02", "2026-03-30", "2026-04-27", "2026-05-25"]
    fig = figures(days, ["Yes", "No"], [[[200, 200]], [[204, 196]], [[300, 100]], [[202, 198]], [[206, 194]], [[200, 200]]])
    out = ask_layout.build(fig, BEAUTY, {"kind": "trend", "when": [{"all": True}]}, [0], "US", NEWEST)
    assert out["chart"]["grains"] == ["Each survey", "Monthly", "Quarterly", "Yearly"] and out["chart"]["ranges"] == []
    assert out["chart"]["unusual"] == [{"date": "2026-03-02", "label": "Unusual high: 75.0% (Mar 2026)"}]
    quarterly = figures(["2024-03-04", "2024-06-03", "2024-09-02", "2024-12-02", "2025-03-03", "2025-06-02"], ["Yes", "No"], [[[200, 200]]] * 6)
    assert ask_layout.periods_offered(quarterly) == {"grains": ["Quarterly", "Yearly"], "grain": "", "ranges": ["Last 12 months", "Since 2024"]}


def test_the_excel_export_carries_a_native_chart_of_its_figures():
    # 27 Nov 2026 (the manager): Ask's Excel holds the chart and the numbers, not the table alone
    import io
    from openpyxl import load_workbook
    from api import exports
    spec = exports.check_book({"name": "ask", "sheets": [
        {"title": "Answer", "header": ["Survey", "Bought beauty products"], "rows": [["5 Sep 2022", 68.9], ["28 Sep 2026", 65.5]],
         "notes": ["How have beauty purchases changed over time?"], "unit": "%", "chart": "line"},
        {"title": "Every survey result", "header": ["Answer", "28 Sep 2026"], "rows": [["Yes", 65.5]], "notes": ["Every survey"], "unit": "%"}]})
    book = load_workbook(io.BytesIO(exports.build_xlsx(spec)))
    assert book.sheetnames == ["Answer", "Every survey result"]
    assert len(book["Answer"]._charts) == 1 and not book["Every survey result"]._charts


def test_one_group_asked_for_is_named_with_its_country():
    # the spec review (28 Nov 2026): "Did Gen Z buy beauty products?" read as everyone's figure
    fig = figures(["2026-09-28"], ["Yes", "No"], [[[43, 18]]], 61, columns=(("generation", "GenZ"),))
    out = ask_layout.build(fig, BEAUTY, {"kind": "share", "when": [], "cuts": {"generation": ["GenZ"]}}, [0], "US", NEWEST)
    assert "70.5% of Gen Z adults in the US bought beauty products" in out["lead"]


def test_a_why_question_is_recognised():
    from api import assistant
    assert assistant.WHY.match("Why did beauty purchases drop?") and assistant.WHY.match("What caused the fall in sentiment?")
    assert not assistant.WHY.match("Which retailers do people use?")


def test_t6_t20_worked_out_groups_are_compared_and_tested():
    two = ask_layout.compared_rows([("GenAI shoppers", 62.5, 45, 72), ("other AI users", 56.8, 113, 199)],
                                   "have made holiday purchases in the last seven days", "In the latest survey (23 Nov 2026)", "T6")
    assert two["lead"] == ("In the latest survey (23 Nov 2026), 62.5% of GenAI shoppers have made holiday purchases in the last seven days, "
                           "compared with 56.8% of other AI users, a difference that could be chance.")
    assert two["chart"]["kind"] == "columns" and two["cards"][2]["value"] == "+5.7 pts"
    many = ask_layout.compared_rows([("Gen Z women", 45.0, 45, 100), ("Gen Z men", 44.0, 44, 100), ("Boomer women", 20.0, 20, 100)],
                                    "chose Amazon", "In the surveys of 2 Nov 2026 – 23 Nov 2026", "T20")
    assert "Gen Z women and Gen Z men were about equally likely" in many["lead"] and "Boomer women the least likely (20.0%)" in many["lead"]


def test_t7_and_series_and_top_rows():
    both = ask_layout.single_row(("result", 7.7, 31, 404), "bought both online and in store", "In the survey of 16 Nov 2026", "US adults",
                                 [("Bought online", 80.0, 323, 404), ("Bought in store", 60.0, 242, 404)])
    assert both["type"] == "T7" and [c["value"] for c in both["cards"]] == ["7.7%", "80.0%", "60.0%"]
    weeks = ask_layout.series_rows([("2026-11-02", 21.0, 58, 276), ("2026-11-23", 26.6, 72, 271)], "have used GenAI to shop", "recent AI users in the US", "2026-11-23")
    assert weeks["lead"] == ("In the latest survey (23 Nov 2026), 26.6% of recent AI users in the US have used GenAI to shop, "
                             "about the same as on 2 Nov 2026 (21.0%).")
    top = ask_layout.ranked_rows([("Walmart", 60.0, 120, 200), ("Target", 30.0, 60, 200)], "In the latest survey (23 Nov 2026)", "Gen Z adults in the US")
    assert top["lead"].endswith("Walmart was the most common answer among Gen Z adults in the US (60.0%), ahead of Target (30.0%).")


def test_t9_a_grid_compares_its_items_positive_sides():
    answers = ["Amazon: Very positive", "Amazon: Somewhat positive", "Amazon: Negative", "Walgreens: Very positive", "Walgreens: Somewhat positive",
               "Walgreens: Negative", "Aerie: Very positive", "Aerie: Negative"]
    fig = figures(["2026-11-23"], answers, [[[60, 27, 13, 40, 36, 24, 4, 1]]], [[[100, 100, 100, 100, 100, 100, 5, 5]]])
    out = ask_layout.build(fig, {"family": "CSI-US", "text": "How do you feel about each?"}, {"kind": "share", "when": []}, [0], "US", NEWEST)
    assert out["type"] == "T9" and out["chart"]["categories"] == ["Amazon", "Walgreens"]   # Aerie: 5 people, left out
    assert out["lead"] == "In the latest survey (23 Nov 2026), Amazon had the most positive views (87.0%) and Walgreens the fewest (76.0%)."


def test_three_groups_whose_gap_could_be_chance_are_never_both_highest_and_lowest():
    out = ask_layout.compared_rows([("Gen Z", 42.0, 42, 100), ("Millennials", 40.0, 40, 100), ("Gen X", 38.0, 38, 100)], "chose Amazon",
                                   "In the latest survey (23 Nov 2026)", "T3")
    assert out["lead"] == ("In the latest survey (23 Nov 2026), Gen Z, Millennials and Gen X were about equally likely to say they chose "
                           "Amazon (38.0% to 42.0%); the differences could be chance.")


def test_t15_why_gives_the_reading_and_the_surveys_either_side():
    days = ["2025-10-27", "2026-01-19", "2026-04-13"]
    fig = figures(days, ["Yes", "No"], [[[275, 127]], [[250, 150]], [[257, 145]]], [[[402, 402]], [[400, 400]], [[402, 402]]])
    out = ask_layout.around(fig, BEAUTY, 0, "US adults", 1)
    assert out["lead"] == ("The surveys record what people did and said, not why. On 19 Jan 2026, 62.5% of US adults bought beauty products in the "
                           "past three months; the survey before was 68.4% (27 Oct 2025) and the one after 63.9% (13 Apr 2026). The fall from "
                           "27 Oct 2025 could be chance, and it was the same question, asked the same way.")
    assert [c["label"] for c in out["cards"]] == ["That reading", "Survey before", "Survey after"]


def test_t11_a_scale_over_time_shows_its_net_and_how_it_moved():
    days = ["2025-10-06", "2026-03-02", "2026-06-01", "2026-09-07"]
    answers = ["Much better", "Somewhat better", "About the same", "Somewhat worse", "Much worse"]
    fig = figures(days, answers, [[[40, 60, 100, 120, 80]], [[40, 60, 100, 120, 80]], [[42, 60, 100, 118, 80]], [[40, 62, 100, 118, 80]]])
    out = ask_layout.build(fig, {"family": "CSI-US", "text": "Will the economy be better or worse?"}, {"kind": "trend", "when": [{"all": True}]}, [0], "US", NEWEST)
    assert out["type"] == "T11" and [c["label"] for c in out["cards"]] == ["Net now", "Net since Oct 2025", "During 2026"]
    assert out["cards"][1]["value"] == "About the same" and out["cards"][2]["value"] == "Steady"
