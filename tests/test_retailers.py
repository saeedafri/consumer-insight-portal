"""etl/retailers.py: reach, pooled shopper profiles and sentiment from respondent bitsets, on two small made-up weeks
(bit k = respondent k). The real data was checked once by hand: a single week reproduces the book's q5 Walmart Total."""
from etl import retailers

EVERYONE = (1 << 40) - 1                     # 40 respondents a week
FIRST_HALF = (1 << 20) - 1                   # respondents 0-19


def week(walmart_food: int, walmart_nonfood: int, costco_food: int, ap8: bool = False) -> dict:
    """One week's people file, as retailers.read_people returns it."""
    questions = {
        "q4": {"rows": [[1, 0, "Walmart", None, None], [2, 0, "Costco", None, None], [9, 0, "None of these", None, None]],
               "bits": {(0, 0): EVERYONE, (1, 0): walmart_food, (2, 0): costco_food, (9, 0): 1 << 39}},
        "q5": {"rows": [[3, 0, "Walmart", None, None]], "bits": {(0, 0): EVERYONE, (3, 0): walmart_nonfood}},
    }
    if ap8:   # 10 asked about Walmart: 6 very or somewhat positive
        questions["AP8"] = {"rows": [[5, 1, "Walmart", 1, "Very positive"], [5, 2, "Walmart", 2, "Somewhat positive"], [5, 3, "Walmart", 3, "Neutral / no opinion"]],
                            "bits": {(5, 1): 0b111, (5, 2): 0b111000, (5, 3): 0b1111000000}}
    return {"questions": questions,
            "cuts": {"gender": {"Male": FIRST_HALF, "Female": EVERYONE ^ FIRST_HALF}, "generation": {"GenZ": EVERYONE},
                     "income_band": {"under $25,000": FIRST_HALF}}}


def test_each_week_keeps_counts_so_any_weeks_add_up():
    weeks = [({"survey_id": 1, "wave_date": "2026-10-26"}, week(FIRST_HALF, 0, 0b1)),
             ({"survey_id": 2, "wave_date": "2026-11-02"}, week(0, EVERYONE, 0b11, ap8=True))]
    doc = retailers.build(weeks)
    assert [(w["date"], w["n"]) for w in doc["weeks"]] == [("2026-10-26", 40), ("2026-11-02", 40)]
    weekly = doc["markets"][0]
    assert weekly["name"] == "Weekly retailers" and weekly["weeks"] == [0, 1] and weekly["asked"] == [40, 40]
    walmart, costco = weekly["retailers"]                    # biggest in the newest week first; "None of these" left out
    assert walmart["name"] == "Walmart" and costco["name"] == "Costco"
    assert walmart["weeks"]["0"][:3] == [20, 20, 0]          # shoppers, food, nonfood: 20 of 40 in the first week
    assert walmart["weeks"]["1"][:3] == [40, 0, 40]
    gender = len(retailers.settings()["profile"]["gender"])
    assert walmart["weeks"]["0"][3:3 + gender] == [20, 0]    # all 20 first-week shoppers are men
    assert walmart["weeks"]["1"][3:3 + gender] == [20, 20]
    # two weeks added: (20 + 40) of 80 shoppers, 40 of 60 men; the screen does this sum
    assert sum(walmart["weeks"][w][0] for w in "01") == 60 and sum(walmart["weeks"][w][3] for w in "01") == 40
    assert costco["weeks"]["0"][0] == 1 and costco["weeks"]["1"][0] == 2
    assert doc["weeks"][0]["profile"][:gender] == [20, 20]   # everyone, for reference
    assert walmart["sentiment"] == [["2026-11-02", 6, 10, "Clothing"]] and costco["sentiment"] is None   # 6 of 10 positive


def test_a_sector_counts_its_buyers_from_its_own_question_in_its_own_weeks():
    people = week(FIRST_HALF, 0, 0)
    people["questions"]["DP1"] = {"rows": [[0, 71, "", 1, "Yes"], [0, 72, "", 2, "No"]], "bits": {(0, 0): EVERYONE, (0, 71): 0b1111111111}}
    people["questions"]["DP2"] = {"rows": [[80, 0, "Macy's", None, None], [81, 0, "Kohl's", None, None]],
                                  "bits": {(0, 0): 0b1111111111, (80, 0): 0b111, (81, 0): 0b11111}}
    doc = retailers.build([({"survey_id": 1, "wave_date": "2026-10-26", "modules": ["Department stores"]}, people),
                           ({"survey_id": 2, "wave_date": "2026-11-02", "modules": []}, people)])   # not a sector week
    sector = next(m for m in doc["markets"] if m["name"] == "Department stores")
    assert sector["sector"] and sector["weeks"] == [0] and sector["asked"] == [10] and sector["bought"] == [10]
    assert sector["shoppers"] == "department store shoppers"   # config/sectors.yml buyers: the screen's chart and card titles
    kohls, macys = sector["retailers"]
    assert (kohls["name"], kohls["weeks"]["0"][0], macys["weeks"]["0"][0]) == ("Kohl's", 5, 3)   # of 10 buyers


def test_sentiment_comes_from_every_sector_grid_not_only_apparel():
    """16 Nov 2026: Costco and the dollar stores showed "not asked" because only the apparel grid (AP8) was read."""
    people = week(EVERYONE, 0, 0b11)
    people["questions"]["M3"] = {"rows": [[7, 1, "Costco", 1, "Very positive"], [7, 2, "Costco", 2, "Very negative"]],
                                 "bits": {(7, 1): 0b111, (7, 2): 0b1000}}   # 4 asked about Costco: 3 positive
    costco = next(r for r in retailers.build([({"survey_id": 1, "wave_date": "2026-11-09"}, people)])["markets"][0]["retailers"]
                  if r["name"] == "Costco")
    assert costco["sentiment"] == [["2026-11-09", 3, 4, "Mass merchants and warehouse clubs"]]


def test_two_grids_of_one_week_keep_a_figure_each_named_by_their_sector():
    """18 Aug 2025 asked the home furnishings and home improvement grids, both about Walmart: one figure per grid, so the
    screen can read a sector's own (it kept only the first)."""
    people = week(EVERYONE, 0, 0)
    for code, bits in (("HF4", 0b11), ("HI4", 0b1)):   # home furnishings: 2 asked, 2 positive; home improvement: 2 asked, 1 positive
        people["questions"][code] = {"rows": [[7, 1, "Walmart", 1, "Very positive"], [7, 2, "Walmart", 5, "Very negative"]],
                                     "bits": {(7, 1): bits, (7, 2): 0b11 ^ bits}}
    walmart = retailers.build([({"survey_id": 421, "wave_date": "2025-08-18"}, people)])["markets"][0]["retailers"][0]
    assert walmart["sentiment"] == [["2025-08-18", 2, 2, "Home furnishings"], ["2025-08-18", 1, 2, "Home improvement"]]


def test_a_sector_asked_of_every_adult_is_not_called_shoppers_and_a_named_survey_counts_as_its_week():
    """Mass merchants' M1 is asked of everyone; 18 Aug 2025 ran home furnishings under a home-improvement title
    (config/sectors.yml also_ran)."""
    people = week(EVERYONE, 0, 0)
    people["questions"]["M1"] = {"rows": [[90, 0, "Walmart", None, None]], "bits": {(0, 0): EVERYONE, (90, 0): FIRST_HALF}}
    people["questions"]["HF1"] = {"rows": [[0, 61, "", 1, "Yes"]], "bits": {(0, 0): EVERYONE, (0, 61): 0b111}}
    people["questions"]["HF2"] = {"rows": [[91, 0, "IKEA", None, None]], "bits": {(0, 0): 0b111, (91, 0): 0b1}}
    doc = retailers.build([({"survey_id": 421, "wave_date": "2025-08-18", "modules": ["Mass merchants / warehouse clubs", "Home improvement / DIY"]}, people)])
    markets = {m["name"]: m for m in doc["markets"]}
    assert (markets["Mass merchants and warehouse clubs"]["base"], markets["Mass merchants and warehouse clubs"]["shoppers"]) == ("adults asked", "adults")
    assert markets["Home furnishings"]["asked"] == [3] and markets["Home furnishings"]["shoppers"] == "home-furnishing buyers"
