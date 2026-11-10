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


def test_reach_pools_weeks_and_profiles_buyers():
    weeks = [({"survey_id": 1, "wave_date": "2026-10-26"}, week(FIRST_HALF, 0, 0b1)),
             ({"survey_id": 2, "wave_date": "2026-11-02"}, week(0, EVERYONE, 0b11, ap8=True))]
    doc = retailers.build(weeks)
    newest = doc["weeks"][0]
    assert (newest["date"], newest["from"], newest["weeks"], newest["respondents"]) == ("2026-11-02", "2026-10-26", 2, 80)
    walmart, costco = doc["retailers"]                      # biggest reach first; "None of these" left out
    assert walmart["name"] == "Walmart" and costco["name"] == "Costco"
    assert walmart["reach"]["any"][0] == 75.0                # (20 + 40) of 80 across the two weeks
    assert walmart["reach"]["food"][0] == 25.0 and walmart["reach"]["nonfood"][0] == 50.0
    assert walmart["buyers"][0] == 60
    assert walmart["profile"][0]["gender"] == [66.7, 33.3]   # 20 + 20 men, 0 + 20 women of 60 buyers
    assert walmart["profile"][0]["income"][0] == 66.7
    assert costco["buyers"][0] == 3 and costco["profile"][0] is None   # under min_buyers: no profile
    assert doc["everyone"][0]["gender"] == [50.0, 50.0]
    assert walmart["sentiment"] == {"positive": 60.0, "n": 10, "date": "2026-11-02"} and costco["sentiment"] is None
    assert doc["weeks"][1]["weeks"] == 1 and walmart["reach"]["any"][1] == 50.0   # the older week has nothing before it
