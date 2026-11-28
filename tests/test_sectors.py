"""The Databank's sector tables (etl/sectors.py) against the Databank page they reproduce, and the rules that find a
sector's surveys and questions.

The first test uses real data: the Department stores surveys of Aug 2024 to Apr 2026 (tests/fixtures/
sectors_department_stores.json: their books cut to the sector's questions, and those question files cut to these
surveys and the total). The 2024-2025 surveys numbered their questions Q6, Q7…, the later ones DP1, DP2…"""
import json
from pathlib import Path

from etl import sectors
from etl.weekly_report import Question

FIXTURE = Path(__file__).parent / "fixtures" / "sectors_department_stores.json"
SECTORS = {s["name"]: s for s in sectors.settings()["sectors"]}
DEPARTMENT_STORES = SECTORS["Department stores"]


def build(fixture: dict) -> dict:
    """The Department stores sector built from the fixture's waves, books and question files (the other sectors have
    no survey there, so they are left out)."""
    files = {code: Question(file) for code, file in fixture["files"].items()}
    books = {int(survey_id): book for survey_id, book in fixture["books"].items()}
    built = sectors.build(books, fixture["waves"], files.get)["sectors"]
    assert [s["name"] for s in built] == ["Department stores"]
    return built[0]


def test_department_stores_match_the_databank_page_of_6_november_2026():
    sector = build(json.loads(FIXTURE.read_text()))
    assert [w["date"] for w in sector["waves"]] == ["2024-08-19", "2024-11-18", "2025-02-10", "2025-10-20", "2026-01-12", "2026-04-06"]
    assert sector["purchase"]["values"] == [58.6, 59.9, 61.0, 61.1, 61.3, 50.2]          # "% that purchased in this category"
    retailers = {row["label"]: row["values"] for row in sector["tables"][0]["rows"]}
    printed = {   # the Databank's "Retailers they purchased from", as printed
        "Kohl's": [50.0, 51.0, 52.6, 59.2, 48.0, 52.5], "Macy's": [44.9, 39.5, 45.3, 43.3, 40.7, 36.1],
        "JCPenney": [30.5, 28.0, 26.3, 31.0, 27.6, 27.7], "Nordstrom": [20.8, 13.2, 15.8, 19.2, 15.0, 16.8],
        "Dillards": [11.9, 12.3, 14.2, 16.7, 14.2, 10.9], "Neiman Marcus": [8.1, 5.3, 6.1, 10.6, 4.5, 6.9],
        "Bloomingdale's": [5.5, 4.5, 11.7, 7.3, 6.5, 8.4], "Saks Fifth Avenue": [6.8, 5.8, 6.1, 11.0, 5.3, 7.9],
        "Bergdorf Goodman": [4.7, 4.5, 1.6, 7.3, 4.5, 4.0]}
    assert {label: retailers[label] for label in printed} == printed
    assert next(iter(retailers)) == "Kohl's"                                                   # biggest in the newest survey first
    assert not any(label.lower().startswith("other") for label in retailers)                   # left out, as in the weekly report


def test_a_sectors_surveys_are_tagged_titled_or_named_and_a_parallel_panel_is_left_out():
    waves = [{"survey_id": 125, "wave_date": "2023-10-02", "title": "Shopping and Spending - inc Luxury + Dept stors + new Qs", "modules": []},
             {"survey_id": 1, "wave_date": "2023-12-16", "title": "Shopping and Spending - inc Luxury + Dept Stores- RIWI", "modules": []},
             {"survey_id": 2, "wave_date": "2023-12-18", "title": "Shopping and Spending - inc Luxury + Dept Stores", "modules": []},
             {"survey_id": 3, "wave_date": "2024-01-08", "title": "Shopping and Spending - inc Beauty", "modules": []},
             {"survey_id": 4, "wave_date": "2026-04-06", "title": "anything", "modules": ["Department stores"]}]
    assert [w["survey_id"] for w in sectors.sector_waves(waves, DEPARTMENT_STORES)] == [125, 2, 4]   # "Dept stors": a typo in Forsta
    clothing = {"survey_id": 380, "wave_date": "2022-02-07", "title": "Shopping and spending incl. clothing shopping and livestreaming", "modules": []}
    assert sectors.sector_waves([clothing], SECTORS["Clothing"]) == [clothing]
    # 13 Oct 2025 ran the footwear module (FW1-FW6, 212 buyers) under a title that names only luxury: config also_ran
    luxury_week = {"survey_id": 438, "wave_date": "2025-10-13", "title": "Shopping and Spending - inc Luxury + Holiday tracker", "modules": ["Luxury"]}
    assert sectors.sector_waves([luxury_week], SECTORS["Footwear"]) == [luxury_week]
    assert sectors.sector_waves([{**luxury_week, "survey_id": 9}], SECTORS["Footwear"]) == []


def test_a_survey_that_asked_only_the_purchase_question_is_left_out():
    """Footwear 1 Jun 2026 and Home furnishings 11 Aug 2025 asked the purchase question, but none of the follow-ups were
    answered: a column of dashes. The fixture's newest survey cut to its purchase question stands in for them."""
    fixture = json.loads(FIXTURE.read_text())
    fixture["books"]["487"]["questions"] = [q for q in fixture["books"]["487"]["questions"] if q["id"] == "DP1"]
    assert [w["date"] for w in build(fixture)["waves"]][-1] == "2026-01-12"


def test_a_reused_code_is_told_apart_by_its_wording_and_coded_open_ends_are_skipped():
    drugstore = {"id": "DS1", "text": "Have you purchased from a drug store or pharmacy in the past three months?"}
    dollar = {sectors.first_sentence("Have you purchased from a dollar store retailer in the past three months?")}
    assert sectors.find({"questions": [drugstore]}, "DS1", dollar) is None                     # same code, other question
    older = {"id": "Q6", "text": "Have you purchased from a dollar store retailer in the past three months? Select one."}
    other = {"id": "Q6r5oe", "text": older["text"] + " — Other (please specify)", "coded": "frequency"}
    assert sectors.find({"questions": [other, older]}, "DS1", dollar) is older                 # by wording, open end skipped


def test_a_question_asked_in_other_words_is_found_by_its_older_wording():
    """Beauty, 20 Feb 2023: its retailer question (Q9, 300 buyers) said "retailers", not "retailers or platforms"."""
    q9 = {"id": "Q9", "text": "Which, if any, of the following retailers have you purchased beauty products from in the past three "
                              "months (whether in-store or online)? Select all that apply."}
    newest = sectors.first_sentence("Which, if any, of the following retailers or platforms have you purchased beauty products from "
                                    "in the past three months (whether in-store or online)?")
    older = {sectors.first_sentence(text) for text in SECTORS["Beauty"]["older_wordings"]["BT13"]}
    assert sectors.find({"questions": [q9]}, "BT13", {newest}) is None
    assert sectors.find({"questions": [q9]}, "BT13", {newest} | older) is q9


def test_an_answer_spelled_differently_over_the_years_is_one_row():
    fixture = json.loads(FIXTURE.read_text())
    retailers = [row["label"] for row in build(fixture)["tables"][0]["rows"]]
    assert sum(label.replace("'", "") == "Dillards" for label in retailers) == 1


def test_median_spend_is_the_band_the_middle_buyer_falls_in_by_amount_not_by_list_order():
    """M4 on 9 Nov 2026 (369 mass merchant shoppers), its book rows in the book's order: below $201 adds up to 34.5%,
    with $201 - $300 to 54.6%, so the middle shopper spent $201 - $300; "Cannot remember" counts nowhere."""
    book = [("More than $500", 26.0), ("$301 - $500", 17.3), ("$201 - $300", 20.1), ("$101 - $200", 17.1),
            ("$50 - $100", 9.8), ("Less than $50", 7.6), ("Cannot remember", 2.2)]
    assert sectors.median_band([{"label": label, "Total": share} for label, share in book]) == "$201 - $300"
    assert sectors.median_band([{"label": label, "Total": None} for label, _ in book]) is None    # every figure hidden
    assert sectors.median_band([{"label": "Prices were lower", "Total": 40.0}]) is None           # not a spend question


def test_average_spend_is_estimated_from_exact_counts_with_an_open_top_band_at_its_floor():
    """Clothing, 2 Nov 2026 (AP9, 301 asked): 296 gave a band, (24 x 25.5 + 41 x 75.5 + … + 18 x 500) / 296 = $214.49,
    "More than $500" counted at $500 and "Cannot remember" nowhere, as Ask estimates an average (api/ask_figures.py
    middle). The book's % rounded to 0.1 gave $215 (the E2E check of 28 Nov 2026). The labels are the book's: a reused
    code's question file can carry another survey's labels under the same answer code."""
    book = [("$1 - $50", 24), ("$51 - $100", 41), ("$101 - $150", 55), ("$151 - $200", 38), ("$201 - $250", 35), ("$251 - $300", 30),
            ("$301 - $350", 20), ("$351 - $400", 18), ("$401 - $450", 6), ("$451 - $500", 11), ("More than $500", 18), ("Cannot remember", 5)]
    rows = [{"label": label, "code": code, "Total": round(100 * n / 301, 1)} for code, (label, n) in enumerate(book, 1)]
    question = Question({"qcode": "AP9", "waves": [[532, "2026-11-02", 1]], "cuts": [["total", "Total"]],
                         "answers": [["", code, f"another survey's answer {code}"] for code in range(1, 13)],
                         "w": [0] * 12, "c": [0] * 12, "a": list(range(12)), "n": [n for _, n in book], "b": [301] * 12})
    assert sectors.average_spend(rows, question, 0) == 214
    assert sectors.average_spend([{"label": "Prices were lower", "code": 1, "Total": 40.0}], question, 0) is None   # not a spend question
