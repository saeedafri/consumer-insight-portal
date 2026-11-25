"""Home's "This week at a glance" (etl/glance.py): the six cards the research team asked for on 23 Nov 2026, per weekly
survey, picked from the newest wave's book, sector tables, weekly report and dashboards, each with its source badge
and its change badges. Figures from the US wave of 9 Nov 2026 and the China week of 9 Nov 2026 (Baidu)."""
from etl import glance, sectors

US, CHINA = ({s["name"]: s for s in glance.settings()["surveys"]}[name] for name in ("US", "China"))   # config/glance.yml

WAVE = {"survey_id": 533, "wave_date": "2026-11-09", "prior_date": "2026-11-02", "qualified_n": 404, "dashboards": ["financial_health", "mass_warehouse"],
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
    built = glance.build(US, WAVE, BOOK, [MASS], REPORT, {"financial_health": HEALTH})
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
    assert gap["link"].startswith("/channels?market=US&w=")
    assert outlook["changes"] == [{"d": 1.8, "label": "vs last week"}]
    assert outlook["note"].endswith("next 12 months. 56.4% say utilities went up in the past year")


def test_without_an_event_the_monthly_topic_shows_with_its_tile_badges_then_the_sectors_median_spend():
    quiet = {**WAVE, "modules": WAVE["modules"][:2]}
    topic = glance.build(US, quiet, BOOK, [MASS], REPORT, {"financial_health": HEALTH})["cards"][2]
    assert (topic["badge"], topic["title"], topic["value"]) == ("Monthly topic", "Consumer Financial Health: Savings last under a month", "38.9%")
    assert topic["note"] == "could cover their bills for less than a month from savings"   # the tile's `say` (config/dashboards.yml)
    assert [(c["d"], c["label"]) for c in topic["changes"]] == [(2.0, "vs LY"), (-1.1, "vs prior wave")]
    spend = glance.build(US, quiet, BOOK, [MASS], REPORT, {})["cards"][2]
    assert (spend["badge"], spend["title"], spend["value"]) == ("Mass merchants and warehouse clubs", "Median spend", "$201 - $300")


def test_online_answers_with_a_note_pair_with_their_store_answer_and_a_week_without_files_loses_only_those_cards():
    books_only = {"questions": [question("q2", "S", "?", ("Books, movies, music or video games", 30.0), ("Bags or luggage", 4.0)),
                                question("q3", "S", "?", ("Books, movies, music or video games (incl. digital purchases)", 2.0),
                                         ("Bags or luggage", 4.7))]}
    built = glance.build(US, {**WAVE, "modules": []}, books_only, [], None, {})
    assert built["cards"][:4] == [None] * 4 and built["cards"][5] is None                  # empty slots keep the rows
    assert (built["cards"][4]["value"], built["cards"][4]["changes"]) == ("Books, movies, music or video games", [])   # no last week


def test_two_sectors_in_one_week_the_title_names_first_leads():
    week = {**WAVE, "survey_id": 530, "title": "Shopping and Spending - inc Off Price + Dollar Stores + Holiday Tracker"}
    dollar, off = ({**MASS, "name": name, "waves": [{**w, "survey_id": 530} for w in MASS["waves"]]} for name in ("Dollar stores", "Off-price"))
    assert glance.build(US, week, BOOK, [dollar, off], REPORT, {})["sector"] == "Off-price"


CN_WAVE = {"survey_id": 724, "wave_date": "2026-11-09", "prior_date": "2026-10-26", "qualified_n": 550, "modules": [], "dashboards": []}


def cn_rows(*rows):
    """Book rows from (answer, this week %, the survey before's %, flags)."""
    return [{"label": label, "Total": now, "prior": before, "flags": flags} for label, now, before, flags in rows]


CN_BOOK = {"questions": [   # the China week of 9 Nov 2026 against 26 Oct (no survey on 2 Nov), Baidu's figures
    {"id": "Q1", "section": "Shopping and Spending", "text": "Spending on everyday goods and dining, next two weeks?", "groups": [{"rows": cn_rows(
        ("Decrease a lot", 10.5, 12.5, ""), ("Decrease somewhat", 24.0, 25.8, ""), ("Stay the same", 50.0, 46.7, ""),
        ("Increase somewhat", 13.6, 12.5, ""), ("Increase a lot", 1.8, 2.4, ""))}]},
    {"id": "Q4", "section": "Shopping and Spending", "text": "Activities in the past two weeks?", "groups": [{"rows": cn_rows(
        ("Spent time in nature", 31.5, 33.6, ""), ("Watched TV/short videos/livestreams", 39.3, 41.5, ""),
        ("Took part in sports (e.g., marathons, soccer, frisbee)", 10.9, 18.9, "sig_prior,sig_ly"), ("Other (please specify)", 0.2, 0.4, ""))}]},
    {"id": "Q5", "section": "Shopping and Spending", "text": "Bought in physical stores?", "groups": [{"rows": cn_rows(
        ("Household essentials", 44.9, 44.5, ""), ("Apparel, footwear and other fashion products", 30.7, 37.1, ""),
        ("Books, music, movies and video games", 4.7, 9.8, "sig_prior"), ("None of the above", 0.7, 1.1, ""))}]},
    {"id": "Q6", "section": "Shopping and Spending", "text": "Bought online?", "groups": [{"rows": cn_rows(
        ("Personal care products", 39.5, 38.5, ""), ("Household essentials", 20.7, 24.2, ""),
        ("Apparel, footwear and other fashion products", 32.9, 33.3, ""), ("Books, music, movies and video games", 7.6, 12.2, ""),
        ("None of the above", 1.3, 1.5, ""))}]},
]}
CN_REPORT = {"three_points": [], "sentiment": {"Personal finances": {"dates": ["2026-10-26", None, "2026-11-09"],
                                                                     "lines": {"Total": {"weekly": [37.5, None, 44.4]}}}}}


def test_the_china_survey_has_its_own_six_cards_against_the_survey_before_it():
    built = glance.build(CHINA, CN_WAVE, CN_BOOK, [], CN_REPORT, {})
    assert (built["name"], built["sector"]) == ("China", None)
    assert [(c["badge"], c["value"]) for c in built["cards"]] == [
        ("Activities", "Watched TV/short videos/livestreams"), ("Bought online", "Personal care products"),
        ("Spending plans", "-19.1"),                     # 15.4% will spend more, 34.5% less
        ("Since the last survey", "-5.1 pts"),           # the report moved nothing over four weeks: the significant move since
                                                         # 26 Oct in store or online (not the sports activity, -8.0)
        ("In store vs online", "Household essentials"), ("Consumer sentiment", "+44.4")]
    activity, online, plans, change, gap, outlook = built["cards"]
    assert activity["note"] == "39.3% of adults in China, past two weeks" and activity["changes"][0]["label"] == "vs Oct 26"
    assert plans["changes"] == [{"d": 4.3, "label": "vs Oct 26"}]                 # -23.4 on 26 Oct
    assert change["note"] == "Books, music, movies and video games: from 9.8% on Oct 26 to 4.7% on Nov 9, a significant change"
    assert gap["changes"] == [{"d": 3.9, "label": "vs Oct 26"}]
    assert gap["link"] == "/channels?market=CN&w=724&c=Household%20essentials" and gap["feature"] == "channels"   # on China
    assert outlook["changes"] == [{"d": 6.9, "label": "vs Oct 26"}]               # the week before had no survey
    assert outlook["note"] == "net optimism: % positive minus % negative, next 12 months"


def test_a_change_badge_says_last_week_only_when_the_survey_before_was_seven_days_earlier():
    assert glance.compare_label("2026-11-16", "2026-11-23") == "vs last week"
    assert glance.compare_label("2026-10-26", "2026-11-09") == "vs Oct 26"           # no survey on 2 Nov
    assert glance.compare_label(None, "2026-11-09") == "vs the survey before"        # its day unknown: no guess
