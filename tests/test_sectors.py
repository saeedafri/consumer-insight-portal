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
DEPARTMENT_STORES = next(s for s in sectors.settings()["sectors"] if s["name"] == "Department stores")


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


def test_a_sectors_surveys_are_tagged_or_titled_and_a_parallel_panel_is_left_out():
    waves = [{"survey_id": 1, "wave_date": "2023-12-16", "title": "Shopping and Spending - inc Luxury + Dept Stores- RIWI", "modules": []},
             {"survey_id": 2, "wave_date": "2023-12-18", "title": "Shopping and Spending - inc Luxury + Dept Stores", "modules": []},
             {"survey_id": 3, "wave_date": "2024-01-08", "title": "Shopping and Spending - inc Beauty", "modules": []},
             {"survey_id": 4, "wave_date": "2026-04-06", "title": "anything", "modules": ["Department stores"]}]
    assert [w["survey_id"] for w in sectors.sector_waves(waves, DEPARTMENT_STORES)] == [2, 4]


def test_a_reused_code_is_told_apart_by_its_wording_and_coded_open_ends_are_skipped():
    drugstore = {"id": "DS1", "text": "Have you purchased from a drug store or pharmacy in the past three months?"}
    dollar = sectors.first_sentence("Have you purchased from a dollar store retailer in the past three months?")
    assert sectors.find({"questions": [drugstore]}, "DS1", dollar) is None                     # same code, other question
    older = {"id": "Q6", "text": "Have you purchased from a dollar store retailer in the past three months? Select one."}
    other = {"id": "Q6r5oe", "text": older["text"] + " — Other (please specify)", "coded": "frequency"}
    assert sectors.find({"questions": [other, older]}, "DS1", dollar) is older                 # by wording, open end skipped


def test_an_answer_spelled_differently_over_the_years_is_one_row():
    fixture = json.loads(FIXTURE.read_text())
    retailers = [row["label"] for row in build(fixture)["tables"][0]["rows"]]
    assert sum(label.replace("'", "") == "Dillards" for label in retailers) == 1
