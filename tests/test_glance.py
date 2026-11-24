"""Home's "This week at a glance" (etl/glance.py): the six cards the research team asked for on 23 Nov 2026, picked
from the newest weekly wave's book, sector tables, weekly report and dashboards, each with its source badge and its
change badges. Figures from the 9 Nov 2026 wave."""
from etl import glance, sectors

WAVE = {"survey_id": 533, "wave_date": "2026-11-09", "qualified_n": 404, "dashboards": ["financial_health", "mass_warehouse"],
        "modules": ["Mass merchants / warehouse clubs", "Financial health", "Singles Day Retro"]}
MASS = {"name": "Mass merchants and warehouse clubs", "buyers": "mass merchant and warehouse club shoppers", "purchase": None,
        "waves": [{"survey_id": 9, "date": "2025-11-10", "respondents": 401}, {"survey_id": 256, "date": "2026-08-17", "respondents": 398},
                  {"survey_id": 533, "date": "2026-11-09", "respondents": 404}],
        "spend": {"question": "M4", "median": ["$101 - $200", "$101 - $200", "$201 - $300"]},
        "tables": [{"title": "Retailers", "bases": [401, 398, 404],
                    "rows": [{"label": "Walmart", "values": [70.0, 72.4, 72.8]}, {"label": "Target", "values": [31.0, 30.1, 33.4]}]},
                   {"title": "Categories", "bases": [355, 360, 369], "rows": [{"label": "Old answer", "values": [None, 70.0, None]},
                                                                              {"label": "Food or beverages (i.e., groceries)", "values": [None, 61.0, 60.4]}]}]}
MASS["cards"] = sectors.newest_cards(MASS)   # as etl/sectors.py writes them


def rows(*pairs):
    return [{"label": label, "Total": value, "prior": None, "flags": ""} for label, value in pairs]


def question(code, section, text, *pairs):
    return {"id": code, "section": section, "text": text, "groups": [{"rows": rows(*pairs)}]}


BOOK = {"questions": [
    question("q2", "Shopping and Spending", "Bought IN A STORE?", ("Food or beverages (i.e., groceries)", 71.8),
             ("Books, movies, music or video games", 16.1), ("Bags or luggage", 4.0), ("None of these", 5.2)),
    question("q3", "Shopping and Spending", "Bought ONLINE?", ("Food or beverages (i.e., groceries)", 26.5),
             ("Books, movies, music or video games (incl. digital purchases)", 15.8), ("Bags or luggage", 4.7), ("None of these", 20.8)),
    question("SD1", "Singles Day Retro", "Did you shop on Singles Day? Select one.", ("Yes", 23.5), ("No", 70.1), ("Don't know", 6.4)),
    {"id": "q6", "section": "Shopping and Spending", "text": "How have your expenses changed?", "groups": [
        {"label": "Insurance", "rows": rows(("Notable increase", 26.5), ("Significant increase", 17.8))},
        {"label": "Utilities", "rows": rows(("No meaningful change", 36.1), ("Notable increase", 31.4), ("Significant increase", 25.0))}]},
]}
BOOK["questions"][0]["groups"][0]["rows"][0]["prior"] = 67.5   # last week: groceries 67.5% in a store, 27.5% online
BOOK["questions"][1]["groups"][0]["rows"][0]["prior"] = 27.5
REPORT = {"three_points": [{"section": "Activities", "label": "Gone to a coffee-shop", "change": 9.1, "from": 29.8, "to": 38.9},
                           {"section": "Bought in store", "label": "Cosmetics, skincare or fragrance products", "change": 7.4,
                            "from": 19.3, "to": 26.7}],
          "sentiment": {"Personal finances": {"dates": ["2026-11-02", "2026-11-09"], "lines": {"Total": {"weekly": [-2.5, -0.7]}}}}}
HEALTH = {"title": "Consumer Financial Health", "highlights": [], "lists": {}, "prior_label": "prior wave",
          "tile_labels": {"savings_month": "Savings last under a month"},
          "tiles": {"savings_month": {"pct": 38.9, "vs_ly": 2.0, "vs_prior": -1.1, "flags": []}, "windfall": {"pct": 18.6}}}


def test_the_six_cards_of_the_week_in_the_order_asked_each_with_its_badge():
    built = glance.build(WAVE, BOOK, [MASS], REPORT, {"financial_health": HEALTH})
    assert built["sector"] == "Mass merchants and warehouse clubs"
    assert [(c["badge"], c["title"], c["value"]) for c in built["cards"]] == [
        ("Mass merchants and warehouse clubs", "Leading retailer", "Walmart"),
        ("Mass merchants and warehouse clubs", "Top category", "Food or beverages (i.e., groceries)"),   # newest survey's answer
        ("New this week", "Singles Day Retro", "23.5%"),                      # a retro beats the monthly topic; never a "No"
        ("Weekly report", "Biggest change: Bought in store", "+7.4 pts"),     # food, nonfood, store, online only: not Activities
        ("In store vs online", "Widest gap: in store vs online", "Food or beverages (i.e., groceries)"),
        ("Consumer sentiment", "Personal finances outlook", "-0.7")]
    leader, product, _, _, gap, outlook = built["cards"]
    assert leader["note"] == "72.8% of all adults, past three months"                     # M1 is asked of everyone
    assert product["note"] == "60.4% of mass merchant and warehouse club shoppers, past three months"   # M2 only of them
    assert leader["changes"] == [{"d": 2.8, "label": "vs LY"}, {"d": 0.4, "label": "vs Aug 17"}]       # like the glance tiles
    assert product["changes"] == [{"d": -0.6, "label": "vs Aug 17"}]                       # not asked a year ago
    assert leader["link"] == "/sectors?sector=Mass%20merchants%20and%20warehouse%20clubs&tab=Retailers"
    assert gap["changes"] == [{"d": 5.3, "label": "vs last week"}]                         # 45.3 pts now, 40.0 last week
    assert outlook["changes"] == [{"d": 1.8, "label": "vs last week"}]
    assert outlook["note"].endswith("next 12 months. 56.4% say utilities went up in the past year")


def test_without_an_event_the_monthly_topic_shows_with_its_tile_badges_then_the_sectors_median_spend():
    quiet = {**WAVE, "modules": WAVE["modules"][:2]}
    topic = glance.build(quiet, BOOK, [MASS], REPORT, {"financial_health": HEALTH})["cards"][2]
    assert (topic["badge"], topic["title"], topic["value"]) == ("Monthly topic", "Consumer Financial Health: Savings last under a month", "38.9%")
    assert topic["note"] == "could cover their bills for less than a month from savings"   # the tile's `say` (config/dashboards.yml)
    assert [(c["d"], c["label"]) for c in topic["changes"]] == [(2.0, "vs LY"), (-1.1, "vs prior wave")]
    spend = glance.build(quiet, BOOK, [MASS], REPORT, {})["cards"][2]
    assert (spend["badge"], spend["title"], spend["value"]) == ("Mass merchants and warehouse clubs", "Median spend", "$201 - $300")


def test_online_answers_with_a_note_pair_with_their_store_answer_and_a_week_without_files_loses_only_those_cards():
    books_only = {"questions": [question("q2", "S", "?", ("Books, movies, music or video games", 30.0), ("Bags or luggage", 4.0)),
                                question("q3", "S", "?", ("Books, movies, music or video games (incl. digital purchases)", 2.0),
                                         ("Bags or luggage", 4.7))]}
    built = glance.build({**WAVE, "modules": []}, books_only, [], None, {})
    assert built["cards"][:4] == [None] * 4 and built["cards"][5] is None                  # empty slots keep the rows
    assert (built["cards"][4]["value"], built["cards"][4]["changes"]) == ("Books, movies, music or video games", [])   # no last week


def test_two_sectors_in_one_week_the_title_names_first_leads():
    week = {**WAVE, "survey_id": 530, "title": "Shopping and Spending - inc Off Price + Dollar Stores + Holiday Tracker"}
    dollar, off = ({**MASS, "name": name, "waves": [{**w, "survey_id": 530} for w in MASS["waves"]]} for name in ("Dollar stores", "Off-price"))
    assert glance.build(week, BOOK, [dollar, off], REPORT, {})["sector"] == "Off-price"
