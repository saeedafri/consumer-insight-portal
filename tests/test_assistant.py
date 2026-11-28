"""Ask CIP (api/assistant.py, ask_reader, ask_index, ask_figures): the right question, the right periods, exact pooled
figures, only the waves a person may see, and no guess when nothing matches. A small survey made up here:

  CSI-US/tracker/XQ1  "Which of these retailers have you bought from in the past two weeks?", eight weekly waves
                      (Sep–Oct 2026), Total and generation, Amazon and Walmart, known counts
  CSI-US/tracker/Q14  a code reused for two different questions (GenAI at work; ways to save money)
"""
import gzip
import json

import numpy as np
import pytest

from api import ask_figures, ask_reader, assistant
from api.ask_index import Index, name_key

DATES = ["2026-09-07", "2026-09-14", "2026-09-21", "2026-09-28", "2026-10-05", "2026-10-12", "2026-10-19", "2026-10-26"]
AMAZON = [100, 110, 120, 130, 140, 150, 160, 170]   # people who chose Amazon in each wave, of 400
WALMART = [200] * 8


def question_file(waves, versions, answers, cuts, cells):
    w, c, a, n, b = zip(*cells)
    return {"qcode": "", "waves": waves, "versions": versions, "answers": answers, "cuts": cuts,
            "w": list(w), "c": list(c), "a": list(a), "n": list(n), "b": list(b)}


@pytest.fixture()
def index(tmp_path):
    root = tmp_path / "questions" / "CSI-US" / "tracker"
    root.mkdir(parents=True)
    cells = []
    for i in range(8):
        cells += [(i, 0, 0, AMAZON[i], 400), (i, 0, 1, WALMART[i], 400),
                  (i, 1, 0, AMAZON[i] // 2, 100), (i, 1, 1, 50, 100),    # GenZ: half of Amazon's buyers, of 100
                  (i, 2, 0, 40, 100), (i, 2, 1, 60, 100)]                 # Millennial: 40 of 100
    (root / "XQ1.json.gz").write_bytes(gzip.compress(json.dumps(question_file(
        [[100 + i, d, 1] for i, d in enumerate(DATES)],
        ["Which of these retailers have you bought from in the past two weeks?"],
        [["", 1, "Amazon"], ["", 2, "Walmart"]], [["total", "Total"], ["generation", "GenZ"], ["generation", "Millennial"]], cells)).encode()))
    reused = [(0, 0, 0, 80, 400), (0, 0, 1, 320, 400), (1, 0, 2, 300, 400), (1, 0, 3, 100, 400)]
    (root / "Q14.json.gz").write_bytes(gzip.compress(json.dumps(question_file(
        [[100, DATES[0], 1], [101, DATES[1], 2]],
        ["Are you allowed to use generative AI tools at work?", "Which of these ways to save money do you use?"],
        [["", 1, "Yes"], ["", 2, "No"], ["", 3, "Coupons"], ["", 4, "Store brands"]], [["total", "Total"]], reused)).encode()))
    waves = [{"survey_id": 100 + i, "wave_date": d, "title": "Shopping and Spending", "modules": []} for i, d in enumerate(DATES)]
    index = Index(tmp_path / "questions", waves)
    index.add_vectors()
    return index


EVERYONE = {100 + i for i in range(8)}


def figure(answer: dict, label: str, column: int = 1) -> list:
    return next(r for r in answer["table"]["rows"] if r[0] == label)[column:]


def test_the_latest_wave_is_people_over_base(index):
    found = assistant.answer("What share bought from Amazon in the latest wave?", index, EVERYONE)
    assert found["mode"] == "figures" and found["sources"][0]["qcode"] == "XQ1"
    assert figure(found, "Amazon") == [42.5]                                    # 170 of 400
    assert found["table"]["cell_bases"] == [[400], [400]]
    assert found["scope"] == {"country": "US", "period": "26 Oct 2026", "waves": 1, "base": 400}
    assert "170 of 400" in found["answer"] and found["chart"]["type"] in ("bar", "donut")


def test_the_source_history_reflects_only_visible_waves(index):
    found = assistant.answer("What share bought from Amazon in the latest wave?", index, {107}, key="CSI-US/tracker/XQ1")
    assert "asked in 1 wave" in found["source_line"]
    assert "7 Sep 2026" not in found["source_line"]
    assert found["scope"]["waves"] == 1


def test_a_historical_answer_links_to_the_code_that_its_wave_used(tmp_path):
    root = tmp_path / "CSI-US" / "tracker"
    root.mkdir(parents=True)
    words = "Which retailers have you bought from?"
    for sid, day, code in [(100, DATES[0], "OLD10"), (101, DATES[-1], "NEW20")]:
        data = question_file([[sid, day, 1]], [words], [["", 1, "Amazon"]], [["total", "Total"]], [(0, 0, 0, 100, 400)])
        (root / f"{code}.json.gz").write_bytes(gzip.compress(json.dumps(data).encode()))
    waves = [{"survey_id": 100, "wave_date": DATES[0]}, {"survey_id": 101, "wave_date": DATES[-1]}]
    index = Index(tmp_path, waves)
    result = assistant.answer("What share bought from Amazon in September 2026?", index, {100, 101}, key="CSI-US/tracker/NEW20")
    assert figure(result, "Amazon") == [25.0]
    assert result["sources"][0]["link"] == "/w/100/questions/OLD10"
    assert result["sources"][0]["qcode"] == "OLD10"


def test_a_calculation_that_finishes_after_cache_reset_stays_uncached(index, monkeypatch):
    def calculate(*_, **__):   # ask() passes the market by name
        with assistant.ANSWERS_LOCK:
            assistant.clear_answers()
        return {"mode": "none", "answer": "Test"}

    monkeypatch.setattr(assistant, "answer", calculate)
    assert assistant.ask("A question", index, EVERYONE, "all")["answer"] == "Test"
    assert not assistant.ANSWERS


def test_ask_count_cache_skips_over_budget_and_duplicate_entries(index, monkeypatch):
    from api import ask_index

    monkeypatch.setattr(ask_index, "COUNT_CACHE_MB", 0)
    item = {column: np.zeros(20, dtype=np.int32) for column in "wcanb"}
    index.keep("first", item)
    assert index.cached_bytes == 0 and not index.cache
    monkeypatch.setattr(ask_index, "COUNT_CACHE_MB", 1)
    index.keep("first", item)
    index.keep("first", item)
    assert index.cached_bytes == sum(column.nbytes for column in item.values())
    assert index.cache["first"] is item


def test_grid_answers_show_their_own_bases_and_hide_suppressed_cells():
    fig = {"periods": [{"label": "Latest wave"}], "columns": [("gender", "Female"), ("gender", "Male")],
           "answers": ["Store A", "Store B", "Store C"], "grain": None,
           "pct": np.array([[[100.0, 70.0, 68.8], [np.nan, 40.0, 60.0]]]),
           "bases": np.array([[[3, 10, 16], [2, 15, 15]]])}
    table = assistant.figure_table(fig, [0, 1, 2])
    assert table["rows"] == [["Store A", 100.0, None], ["Store B", 70.0, 40.0], ["Store C", 68.8, 60.0]]
    assert table["cell_bases"] == [[3, None], [10, 15], [16, 15]]
    assert table["bases"] == [0, 15]
    assert assistant.chart(fig, [0, 1, 2])["bases"] == {"Male": 15}


def test_a_month_pools_its_waves_exactly(index):
    found = assistant.answer("Amazon retailers bought in October 2026", index, EVERYONE)
    assert figure(found, "Amazon") == [round(100 * sum(AMAZON[4:]) / 1600, 1)]  # four October waves: 620 of 1,600


@pytest.mark.parametrize(("question", "reason"), [
    ("What share of Gen Z women by income bought from Amazon?", "at most two kinds of group"),
    ("What share of Gen Z women bought from Amazon?", "not published for this survey question"),   # no cut files here
    ("What was the median amount spent at Amazon?", "cannot calculate"),
    ("Did tariffs cause shoppers to dine out less?", "cannot establish what caused"),
    ("Do you know how many people bought groceries online who also bought them in-store?", "people who did both things"),
    ("How many people shopped at both Amazon and Walmart?", "people who did both things"),
    ("Compare retailers bought in Q4 2026 vs Q1 2027", "one of the periods you named"),
    ("What share bought from Amazon in 2030?", "did not ask this"),
    ("What share of women bought from Amazon?", "demographic group is unavailable"),
    ("Compare Gen Z and Boomers who bought from Amazon", "demographic group is unavailable"),
])
def test_ask_does_not_substitute_for_unsupported_evidence(index, question, reason):
    found = assistant.answer(question, index, EVERYONE, quick=True, key="CSI-US/tracker/XQ1")
    assert found["mode"] == "none" and reason in found["answer"]
    assert found["table"] is None and not found["sources"]


@pytest.mark.parametrize("question", [
    "What unweighted share bought from Amazon?",
    "What un-weighted share bought from Amazon?",
    "Do not use survey weights. What share bought from Amazon?",
])
def test_ask_still_answers_an_explicitly_unweighted_request(index, question):
    found = assistant.answer(question, index, EVERYONE, key="CSI-US/tracker/XQ1")
    assert found["weighting"] == "unweighted" and figure(found, "Amazon") == [42.5]


@pytest.mark.parametrize(("question", "mode"), [
    ("Compare Gen Z who bought from Amazon in September 2026 vs November 2026", "none"),
    ("Compare Costco among Millennials in September 2026 vs November 2026", "none"),
    ("Monthly trend for Millennials shopping in September 2026 vs November 2026", "figures"),
])
def test_named_group_comparisons_require_figures_but_trends_allow_gaps(tmp_path, question, mode):
    root = tmp_path / "CSI-US" / "tracker"
    root.mkdir(parents=True)
    waves = [[100, DATES[0], 1], [101, "2026-11-09", 1]]
    published = question_file(waves, ["Which retailers have you bought from?"], [["", 1, "Amazon"], ["", 2, "Costco"]],
                              [["total", "Total"], ["generation", "GenZ"], ["generation", "Millennial"]],
                              [(0, 0, 0, 100, 400), (1, 0, 0, 150, 400), (1, 1, 0, 60, 100),
                               (0, 2, 0, 33, 100), (1, 2, 0, 30, 100), (1, 2, 1, 70, 100)])
    with gzip.open(root / "XQ1.json.gz", "wt") as outgoing:
        json.dump(published, outgoing)
    index = Index(tmp_path, [{"survey_id": sid, "wave_date": day} for sid, day, _ in waves])
    found = assistant.answer(question, index, {100, 101}, key="CSI-US/tracker/XQ1")
    assert found["mode"] == mode
    if mode == "none":
        assert "no reportable figures" in found["answer"]
        assert found["table"] is None and not found["sources"]
    else:
        assert figure(found, "Amazon") == [33.0, None, 30.0]


def test_each_grain_groups_waves_by_the_calendar(index):
    dates = DATES
    assert ask_figures.group(list(range(8)), dates, "month") == [[0, 1, 2, 3], [4, 5, 6, 7]]
    assert ask_figures.group(list(range(8)), dates, "biweek") == [[0, 1], [2, 3], [4, 5], [6, 7]]   # from the newest back
    assert ask_figures.group(list(range(8)), dates, "4week") == [[0, 1, 2, 3], [4, 5, 6, 7]]
    found = assistant.answer("Amazon retailers bought biweekly", index, EVERYONE)
    assert found["chart"]["type"] == "line"
    assert figure(found, "Amazon") == [round(100 * (AMAZON[k] + AMAZON[k + 1]) / 800, 1) for k in (0, 2, 4, 6)]


def test_last_n_weeks_and_a_comparison(index):
    found = assistant.answer("Amazon retailers bought over the last 2 weeks", index, EVERYONE)
    assert figure(found, "Amazon") == [round(100 * (160 + 170) / 800, 1)]
    found = assistant.answer("compare the first wave and the latest wave: Amazon retailers bought", index, EVERYONE)
    assert figure(found, "Amazon") == [25.0, 42.5] and "significant" in found["answer"]


def test_a_cut_shows_each_of_its_values(index):
    found = assistant.answer("Amazon retailers bought by generation in the latest wave", index, EVERYONE)
    assert found["chart"]["type"] == "grouped"
    assert figure(found, "Amazon") == [85.0, 40.0]                              # GenZ 85 of 100 (170 // 2), Millennial 40


def test_survey_wording_and_named_days_are_not_periods():
    assert ask_reader.read("retailers bought from in the past two weeks")["when"] == []
    assert ask_reader.read("Valentine's Day 2025 spending")["when"] == []
    assert ask_reader.read("Amazon in 2025")["when"] == [{"year": 2025}]
    assert ask_reader.read("Amazon 2025 vs 2026")["when"] == [{"year": 2025}, {"year": 2026}]
    assert ask_reader.read("Amazon last 8 weeks")["when"] == [{"last": 8, "unit": "week"}]
    plan = ask_reader.read("GenAI use quarterly by gender")
    assert plan["grain"] == "quarter" and plan["cuts"] == {"gender": "all"} and plan["kind"] == "trend"
    assert ask_reader.read("How many people bought Amazon prime in all Waves")["kind"] == "trend"   # not one pooled count


def test_a_reused_code_is_two_questions_each_with_its_own_answers(index):
    work = assistant.answer("allowed to use generative AI tools at work", index, EVERYONE)
    save = assistant.answer("ways to save money", index, EVERYONE)
    assert work["sources"][0]["key"] != save["sources"][0]["key"]
    assert [r[0] for r in work["table"]["rows"]] == ["Yes", "No"] and figure(work, "Yes") == [20.0]
    assert [r[0] for r in save["table"]["rows"]] == ["Coupons", "Store brands"]
    # each wave's answers only chose those waves: not held afterwards, in the parts or the questions (review of 15 Nov 2026)
    assert not any("wave_answers" in entry for entry in [*index.parts.values(), *index.docs.values()])


def test_only_the_waves_a_person_may_see(index):
    found = assistant.answer("What share bought from Amazon in the latest wave?", index, {100, 101})
    assert figure(found, "Amazon") == [27.5]                                    # the newest wave they see: 110 of 400
    assert assistant.answer("Amazon retailers bought", index, set())["mode"] == "none"


def test_nothing_matching_is_said_never_guessed(index):
    found = assistant.answer("How many people own a submarine?", index, EVERYONE)
    assert found["mode"] == "none" and found["chart"] is None and "%" not in found["answer"]


def test_every_charted_figure_is_one_of_the_computed_figures(index):
    for q in ("Amazon retailers bought monthly", "top retailers in the latest wave", "Amazon by generation", "Amazon 2026"):
        found = assistant.answer(q, index, EVERYONE)
        computed = {v for row in found["table"]["rows"] for v in row[1:]}
        assert all(v in computed for s in found["chart"]["series"] for v in s["data"] if v is not None), q


def test_a_question_mostly_about_words_no_survey_uses_is_not_answered(index):
    found = assistant.answer("bitcoin submarine Amazon", index, EVERYONE)   # mostly unknown words: the closest, never a guess
    assert found["mode"] == "none" and found["chart"] is None and found["suggestions"]


def test_the_first_and_latest_wave_are_two_periods_oldest_first(index):
    plan = ask_reader.read("Compare the first and latest wave of Amazon retailers")
    assert plan["when"] == [{"first": 1}, {"latest": 1}]
    found = assistant.answer("Amazon retailers bought in October 2026 vs September 2026", index, EVERYONE)
    assert [p for p in found["table"]["head"][1:]] == ["7 Sep 2026 – 28 Sep 2026", "5 Oct 2026 – 26 Oct 2026"]   # oldest first


def test_one_cut_value_is_named_in_the_answer(index):
    found = assistant.answer("Amazon retailers bought among Gen Z in the latest wave", index, EVERYONE)
    assert "among Gen Z" in found["answer"] and figure(found, "Amazon") == [85.0]


def test_an_empty_index_is_built_again(tmp_path, index):
    assistant.INDEX.update(version="v", index=Index(tmp_path / "nothing", []))   # built before a deploy restored the files
    assert assistant.index_for(index.root, "v", []).docs == {}                   # still nothing there: still empty
    assert assistant.index_for(index.root, "v", [{"survey_id": 100 + i, "wave_date": d, "title": "", "modules": []}
                                                for i, d in enumerate(DATES)]).docs


def test_a_question_not_asked_then_never_borrows_an_unrelated_one(index):
    found = assistant.answer("ways to save money in October 2026", index, EVERYONE)   # Q14 asked only in September
    assert found["mode"] == "none" and "did not ask this in the period" in found["answer"]


def test_a_dollar_question_loaded_without_its_amounts_is_never_quoted(tmp_path):
    """Q22 "How much, in dollars, do you expect to spend on Thanksgiving?": its typed amounts were never loaded, so its
    one answer is "$", chosen by everyone. Ask must not answer "100% answered $" (12 Nov 2026, staging)."""
    root = tmp_path / "questions" / "CSI-US" / "tracker"
    root.mkdir(parents=True)
    (root / "Q22.json.gz").write_bytes(gzip.compress(json.dumps(question_file(
        [[100, DATES[0], 1]], ["How much, in dollars, do you expect to spend on Thanksgiving this year?"],
        [["", 1, "$"]], [["total", "Total"]], [(0, 0, 0, 258, 258)])).encode()))
    index = Index(tmp_path / "questions", [{"survey_id": 100, "wave_date": DATES[0], "title": "Shopping", "modules": []}])
    assert index.docs == {}
    assert assistant.answer("How much will people spend on Thanksgiving?", index, {100})["mode"] == "none"


def test_event_questions_answer_only_questions_naming_an_event():
    assert assistant.EVENT.search("from which retailers did you make holiday-related purchases?")
    assert assistant.EVENT.search("prime day purchases") and assistant.EVENT.search("back-to-school plans")
    assert not assistant.EVENT.search("walmart shoppers over time") and not assistant.EVENT.search("wholesale clubs")


def test_the_openai_key_is_found_whatever_case_its_setting_is_typed_in(monkeypatch):
    from api import ask_model
    for name in ask_model.KEY_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("open_api_key", "sk-test")
    assert ask_model.key_name() == "open_api_key" and ask_model.key() == "sk-test"


def test_a_refused_key_sends_no_call_for_a_while_and_health_says_why(tmp_path, monkeypatch):
    """OpenAI's 429 (no credit, staging 15 Nov 2026) turns the AI off for PAUSE_SECONDS: no unsure question waits on it."""
    import urllib.error
    from api import ask_model
    monkeypatch.setenv("OPENAPI_KEY", "sk-test")
    monkeypatch.setattr(ask_model, "SPEND", tmp_path / "spend.json")
    monkeypatch.setattr(ask_model, "READINGS", tmp_path / "readings.json")
    monkeypatch.setattr(ask_model, "REFUSED", {"until": 0.0, "code": None})
    calls = []

    def refuse(request, timeout):   # OpenAI's answer to a key with no credit left
        calls.append(1)
        raise urllib.error.HTTPError(request.full_url, 429, "Too Many Requests", {}, None)

    monkeypatch.setattr(ask_model.urllib.request, "urlopen", refuse)
    line = {"number": 1, "text": "Which retailers have you bought from?", "waves": 9, "first": "2025-01-01", "last": "2026-11-01", "answers": ["Amazon"]}
    assert ask_model.ready() and ask_model.plan("Amazon shoppers", [line]) is None
    assert not ask_model.ready() and "HTTP 429: no credit" in ask_model.status()["why_off"]
    assert ask_model.plan("Walmart shoppers", [line]) is None and len(calls) == 1   # none sent while paused
    ask_model.REFUSED["until"] = 0.0   # the pause is over: tried again
    assert ask_model.ready() and ask_model.status()["why_off"] is None


def test_an_analysts_ask_brings_its_question_nearer(index):
    """Retrieval joins a question's own closeness with its nearest ask's (ASK_WEIGHT): 0.7 × 0.5 + 0.3 × 1.0 = 0.65
    beats 0.7 × 0.6 + 0.3 × 0.6 = 0.60."""
    import numpy as np
    keys = list(index.docs)[:2]
    index.vector_keys, index.area_vectors = keys, None
    index.vectors = np.array([[0.5, 0.866], [0.6, 0.8]], np.float32)       # closeness to (1, 0): 0.5 and 0.6
    index.ask_vectors, index.ask_owner, index.ask_row = np.array([[1.0, 0.0]], np.float32), np.array([0], np.int32), np.array([0], np.int32)   # an ask of the first, 1.0
    index.standing = np.zeros(2, np.float32)
    found = index.retrieve("anything", {}, 2, None, np.array([1.0, 0.0], np.float32))
    assert [f["key"] for f in found[:2]] == keys and found[0]["near"] == pytest.approx(0.65, abs=1e-3)


def test_the_local_model_puts_questions_alike_in_meaning_closer():
    from api import ask_model
    if ask_model.encoder() is None:
        pytest.skip("search model not downloaded (deploy/ask-model-download.py)")
    v = ask_model.embed(["Amazon shoppers", "people who bought from Amazon", "the capital of France"])
    assert v.shape == (3, 384) and abs(float(v[0] @ v[0]) - 1) < 1e-4 and v[0] @ v[1] > v[0] @ v[2] + 0.1


def test_a_quick_answer_needs_no_model_and_asks_for_its_check(index, monkeypatch):
    from api import ask_model
    if ask_model.encoder() is None:
        pytest.skip("search model not downloaded (deploy/ask-model-download.py)")
    monkeypatch.setattr(ask_model, "ready", lambda: True)
    monkeypatch.setattr(ask_model, "plan", lambda *a: pytest.fail("the quick answer called the model"))
    found = assistant.answer("Amazon shoppers over time", index, EVERYONE, quick=True)
    assert found["mode"] == "figures" and found["understood"] == "meaning" and found["check"] is True


def test_a_question_reads_only_its_countrys_waves_and_marks_a_small_base(tmp_path):
    for family, sid, amazon, base, country in (("CSI-US", 100, 170, 400, "US"), ("CSI-CN", 900, 9, 30, "CN")):
        root = tmp_path / "questions" / family / "tracker"
        root.mkdir(parents=True)
        (root / "XQ1.json.gz").write_bytes(gzip.compress(json.dumps(question_file(
            [[sid, DATES[-1], 1]], ["Which of these retailers have you bought from in the past two weeks?"],
            [["", 1, "Amazon"]], [["total", "Total"]], [(0, 0, 0, amazon, base)])).encode()))
    waves = [{"survey_id": 100, "wave_date": DATES[-1], "title": "US", "modules": [], "country": "US"},
             {"survey_id": 900, "wave_date": DATES[-1], "title": "China", "modules": [], "country": "CN"}]
    index = Index(tmp_path / "questions", waves)
    index.add_vectors()
    us = assistant.answer("What share bought from Amazon?", index, {100, 900})
    china = assistant.answer("What share of Chinese consumers bought from Amazon?", index, {100, 900})
    assert us["sources"][0]["family"] == "CSI-US" and figure(us, "Amazon") == [42.5]
    assert china["sources"][0]["family"] == "CSI-CN" and figure(china, "Amazon") == [30.0]
    assert "small base" not in us["answer"] and "as few as 30 respondents" in china["answer"]   # config/methodology.yml: under 50
    followed = assistant.answer("What share bought from Amazon over time", index, {100, 900}, key="CSI-CN/tracker/XQ1")
    assert followed["sources"][0]["family"] == "CSI-CN"   # a follow-up names no country: its key's, not the US


def test_market_both_asks_back_for_a_question_both_surveys_ask(tmp_path):
    # 27 Nov 2026 (the manager's decision): with the market set to Both, a question the US and China surveys both ask is
    # asked back with each survey's latest date; one only the US asks is answered at once; one market answers from it
    economy = "And thinking about the economy overall over the next 12 months, do you think things will be better or worse?"
    files = (("CSI-US", "CS2", 100, economy, ["Much better", "Much worse"]),
             ("CSI-CN", "Q9", 900, "What are your expectations for the economy over the next 12 months?", ["Positive", "Negative"]),
             ("CSI-US", "BT1", 100, "Have you purchased any beauty products in the past three months?", ["Yes", "No"]))
    for family, code, sid, text, answers in files:
        root = tmp_path / "questions" / family / "tracker"
        root.mkdir(parents=True, exist_ok=True)
        (root / f"{code}.json.gz").write_bytes(gzip.compress(json.dumps({**question_file(
            [[sid, DATES[-1], 1]], [text], [["", 1, answers[0]], ["", 2, answers[1]]], [["total", "Total"]],
            [(0, 0, 0, 150, 400), (0, 0, 1, 250, 400)]), "codes": [code]}).encode()))
    waves = [{"survey_id": 100, "wave_date": DATES[-1], "title": "US", "modules": [], "country": "US"},
             {"survey_id": 900, "wave_date": DATES[-2], "title": "China", "modules": [], "country": "CN"}]
    index = Index(tmp_path / "questions", waves)
    index.add_vectors()
    both = assistant.ask("What do people expect for the economy over the next 12 months?", index, {100, 900}, "all", True, market="both")
    assert both["mode"] == "choose" and [m["market"] for m in both["markets"]] == ["US", "CN"]
    assert both["markets"][1]["label"] == f"China results (latest {ask_figures.label_date(DATES[-2])})"
    china = assistant.ask("What do people expect for the economy over the next 12 months?", index, {100, 900}, "all", True, market="CN")
    assert china["mode"] == "figures" and china["sources"][0]["family"] == "CSI-CN"
    beauty = assistant.ask("Did people buy beauty products?", index, {100, 900}, "all", True, market="both")
    assert beauty["mode"] == "figures" and beauty["sources"][0]["family"] == "CSI-US"


def test_follow_ups_offer_each_countrys_own_groups_and_china_by_city_tier():
    # 28 Nov 2026 (01 G17): China has no generations; its chips are age group, city tier and monthly income
    assert [label for _, _, label in assistant.FOLLOW_CUTS["CN"]] == ["By age group", "By city tier", "By monthly income"]
    assert ask_reader.read("Economy outlook by city tier")["cuts"] == {"urbanicity": "all"}


def test_no_survey_names_the_subject(index):
    found = assistant.ask("How many people own a submarine?", index, EVERYONE, "all", True, market="both")
    assert found["mode"] == "none" and found["answer"].startswith("None of our surveys asks whether people own a submarine.")


def test_asks_are_answered_by_words_while_the_vectors_are_built(index):
    index.vectors = index.verified_vectors = None   # api/assistant.py index_for: add_vectors still running after a deploy
    found = assistant.answer("What share bought from Amazon in the latest wave?", index, EVERYONE)
    assert found["sources"][0]["qcode"] == "XQ1" and figure(found, "Amazon") == [42.5]


def test_a_question_using_a_stored_name_is_answered_from_it_with_its_own_cut(index):
    index.names = {name_key("Recent retailer purchases"): ["CSI-US/tracker/XQ1"]}   # the analyst name, as config/ask_semantic.json gives it
    found = assistant.answer("Should we act on recent retailer purchases by generation? Show the latest numbers", index, EVERYONE, quick=True)
    assert found["understood"] == "named" and found["sources"][0]["qcode"] == "XQ1" and len(found["chart"]["series"]) >= 2
    assert index.named("Holiday spending 2025", EVERYONE) == (None, False)   # a year in a name is part of it, never dropped


def test_since_a_month_and_household_income_are_read():
    assert ask_reader.read("Has Yes grown since Aug 2025?")["when"] == [{"from": "2025-08-01", "to": "9999-12-31"}]
    assert ask_reader.read("Spending by household income")["cuts"] == {"income_band": "all"}
    last_year = {"last": 1, "unit": "year", "previous": True}
    assert ask_reader.read("How has sentiment changed since last year?")["when"] == [last_year, {"latest": 1}]   # not 2024 vs 2025
    assert ask_reader.read("Spending last year")["when"] == [last_year]


def test_a_question_too_close_to_call_asks_which_was_meant(index, monkeypatch):
    if index.vectors is None:   # the margin is a closeness in meaning: it needs the local search model
        pytest.skip("search model not downloaded (deploy/ask-model-download.py)")
    found = assistant.answer("What share bought from Amazon in the latest wave?", index, EVERYONE, quick=True)
    assert found["mode"] == "figures" and found["margin"] is not None   # by meaning, with how far it beat the next question
    monkeypatch.setattr(assistant, "GATE", found["margin"] + 0.01)      # closer than the gate: never a silent guess
    unsure = assistant.answer("What share bought from Amazon in the latest wave?", index, EVERYONE, quick=True)
    assert unsure["mode"] == "choose" and unsure["sources"] == [] and unsure["suggestions"][0]["qcode"] == "XQ1"


def test_a_question_the_ai_settled_is_answered_at_once_next_time_with_no_ai(index, monkeypatch):
    if index.vectors is None:   # matched by closeness in meaning: it needs the local search model
        pytest.skip("search model not downloaded (deploy/ask-model-download.py)")
    calls = []
    monkeypatch.setattr(assistant.ask_model, "ready", lambda: True)
    monkeypatch.setattr(assistant.ask_model, "plan", lambda q, c: calls.append(q) or {
        "pick": next(i for i, x in enumerate(c) if "retailers" in x["text"]), "alt": None, "focus": [], "kind": "share",
        "grain": "auto", "cut": "none", "period": "latest"})
    question = "What share bought from Amazon in the latest wave?"
    settled = assistant.ask(question, index, EVERYONE, "all", quick=False)   # the page's check: the AI reads it
    assert settled["understood"] == "model" and settled["sources"][0]["qcode"] == "XQ1" and len(calls) == 1
    again = assistant.ask(question, index, EVERYONE, "someone else", quick=True)   # another person, the quick answer
    assert again["understood"] == "learned" and again["sources"][0]["qcode"] == "XQ1" and len(calls) == 1 and not again["check"]
    saved = json.loads(assistant.LEARNED.read_text())[-1]   # kept by key: 115 codes are reused by other studies (q2, D14),
    assert saved["key"] == settled["sources"][0]["key"]     # and by code alone 13 golden answers came back wrong (13 Nov 2026)
    model = assistant.ask_model.model
    monkeypatch.setattr(assistant.ask_model, "model", lambda: "another-model")   # a new AI: the last one's readings are not reused
    index.load_verified()
    assert not any(v.get("learned") for v in index.verified)
    monkeypatch.setattr(assistant.ask_model, "model", model)
    assistant.LEARNED.write_text(json.dumps([{k: v for k, v in saved.items() if k not in ("key", "text")}]))   # its code alone
    index.load_verified()
    assert not any(v.get("learned") for v in index.verified)   # a learned entry without its key is never guessed from its code


def test_the_same_person_asking_again_gets_the_learned_answer_not_the_kept_quick_one(index, monkeypatch):
    """The quick answer kept from before the AI check settled the question is not shown again: the same wording showed it,
    then the check replaced it, every time (15 Nov 2026)."""
    if index.vectors is None:
        pytest.skip("search model not downloaded (deploy/ask-model-download.py)")
    monkeypatch.setattr(assistant.ask_model, "ready", lambda: True)
    monkeypatch.setattr(assistant.ask_model, "plan", lambda q, c: {
        "pick": next(i for i, x in enumerate(c) if "retailers" in x["text"]), "alt": None, "focus": [], "kind": "share",
        "grain": "auto", "cut": "none", "period": "latest"})
    question = "What share bought from Amazon in the latest wave?"
    assert assistant.ask(question, index, EVERYONE, "all", quick=True)["check"]   # the quick answer, kept; the page checks it
    assert assistant.ask(question, index, EVERYONE, "all", quick=False)["understood"] == "model"   # the AI settles it: learned
    again = assistant.ask(question, index, EVERYONE, "all", quick=True)
    assert again["understood"] == "learned" and not again["check"]


def test_saving_a_verified_answer_keeps_the_others_and_never_writes_over_a_file_it_cannot_read(index, tmp_path, monkeypatch):
    """A file it could not read was saved over with the one new answer: every admin's verified answer lost (15 Nov 2026)."""
    monkeypatch.setattr(assistant.ask_model, "LOGS", tmp_path)
    saved = tmp_path / "ask-verified.json"
    assistant.save_verified({"question": "Amazon shoppers", "code": "XQ1", "key": "CSI-US/tracker/XQ1"}, index)
    assistant.save_verified({"question": "Walmart shoppers", "code": "XQ1", "key": "CSI-US/tracker/XQ1"}, index)
    assert [v["question"] for v in json.loads(saved.read_text())] == ["Amazon shoppers", "Walmart shoppers"]
    saved.write_text('[{"question": "Amazon shoppers", "code": "XQ1"')   # half a file: a kill mid-write
    with pytest.raises(ValueError, match="cannot be read"):
        assistant.save_verified({"question": "Target shoppers", "code": "XQ1", "key": "CSI-US/tracker/XQ1"}, index)
    assert saved.read_text() == '[{"question": "Amazon shoppers", "code": "XQ1"'   # left for an admin to repair


def test_an_answer_from_before_the_search_vectors_is_not_kept(index):
    """In the minutes after a deploy, before add_vectors has run, keywords alone answer: such an answer was kept until the
    next publish (15 Nov 2026)."""
    if index.vectors is None:
        pytest.skip("search model not downloaded (deploy/ask-model-download.py)")
    vectors, index.vectors, index.settled = index.vectors, None, False   # index_for's background build still running
    assistant.ask("Amazon shoppers over time", index, EVERYONE, "all")
    assert not assistant.ANSWERS
    index.vectors = vectors
    assistant.ask("Amazon shoppers over time", index, EVERYONE, "all")
    assert len(assistant.ANSWERS) == 1
    index.vectors, index.settled = None, True   # a build that ended with none (no search model): answers are kept
    assistant.ask("Walmart shoppers over time", index, EVERYONE, "all")
    assert len(assistant.ANSWERS) == 2


def test_a_verified_answer_beats_a_stored_name_and_an_ai_saved_one_does_not(index, tmp_path, monkeypatch):
    from api import ask_index
    if index.vectors is None:
        pytest.skip("search model not downloaded (deploy/ask-model-download.py)")
    q14 = next(k for k in index.docs if "Q14" in k)
    index.names[name_key("Retailer purchases")] = [q14]   # a stored name that points elsewhere (EC4's, 14 Nov 2026)
    assert assistant.answer("Retailer purchases", index, EVERYONE, quick=True)["sources"][0]["key"] == q14
    reviewed = tmp_path / "ask_verified.yml"
    reviewed.write_text('- {question: "Retailer purchases", code: XQ1, kind: share, period: latest}\n')
    monkeypatch.setattr(ask_index, "VERIFIED", reviewed)
    index.load_verified()
    checked = assistant.answer("Retailer purchases", index, EVERYONE, quick=True)
    assert checked["understood"] == "verified" and checked["sources"][0]["qcode"] == "XQ1"   # the admin's check wins
    reviewed.write_text("")
    assistant.LEARNED.write_text(json.dumps([{"question": "Retailer purchases", "key": "CSI-US/tracker/XQ1", "family": "CSI-US",
                                              "kind": "share", "model": assistant.ask_model.model()}]))
    index.load_verified()
    assert assistant.answer("Retailer purchases", index, EVERYONE, quick=True)["sources"][0]["key"] == q14   # the AI's does not


def test_a_saved_answer_whose_key_a_publish_renumbered_is_found_again_by_its_wording(index):
    if index.vectors is None:
        pytest.skip("search model not downloaded (deploy/ask-model-download.py)")
    text = index.docs["CSI-US/tracker/XQ1"]["text"]   # a new survey reusing the code would make it XQ1#1: the old key is gone
    assistant.LEARNED.write_text(json.dumps([{"question": "Who bought from which retailer?", "key": "CSI-US/tracker/XQ1#7",
                                              "text": text, "family": "CSI-US", "kind": "top", "model": assistant.ask_model.model()}]))
    index.load_verified()
    assert [v["key"] for v in index.verified if v.get("learned")] == ["CSI-US/tracker/XQ1"]


def test_a_learned_answer_gives_way_to_a_sure_reader_and_stands_for_an_unsure_one(index, monkeypatch):
    if index.vectors is None:
        pytest.skip("search model not downloaded (deploy/ask-model-download.py)")
    monkeypatch.setattr(assistant, "lacking", lambda *a: ([], 0, False))   # the forced pick is off-subject on purpose: the flow is tested
    question = "What share bought from Amazon in the latest wave?"
    monkeypatch.setattr(assistant.ask_model, "ready", lambda: True)
    monkeypatch.setattr(assistant.ask_model, "plan", lambda q, c: {
        "pick": next(i for i, x in enumerate(c) if "retailers" in x["text"]), "alt": None, "focus": [], "kind": "share",
        "grain": "auto", "cut": "none", "period": "latest"})
    assistant.ask(question, index, EVERYONE, "all")   # the AI settles it on XQ1: learned
    lead = {"now": assistant.READER_SURE + 1}
    monkeypatch.setattr(assistant.ask_model, "read_pick", lambda q, c: (next(x["number"] for x in c if "save money" in x["text"]), lead["now"]))
    sure = assistant.answer(question, index, EVERYONE, quick=True)
    assert sure["understood"] == "reader" and sure["sources"][0]["qcode"] == "Q14"
    lead["now"] = assistant.READER_SURE - 1
    unsure = assistant.answer(question, index, EVERYONE, quick=True)
    assert unsure["understood"] == "learned" and unsure["sources"][0]["qcode"] == "XQ1"



def test_the_reader_picks_and_the_ai_is_asked_only_when_the_reader_is_unsure(index, monkeypatch):
    if index.vectors is None:
        pytest.skip("search model not downloaded (deploy/ask-model-download.py)")
    monkeypatch.setattr(assistant, "lacking", lambda *a: ([], 0, False))   # the forced pick is off-subject on purpose: the flow is tested
    question = "What share bought from Amazon in the latest wave?"
    calls, lead = [], {"now": 3.0}
    monkeypatch.setattr(assistant.ask_model, "ready", lambda: True)
    monkeypatch.setattr(assistant.ask_model, "plan", lambda q, c: calls.append(q) or {
        "pick": next(x["number"] for x in c if "retailers" in x["text"]), "alt": None, "focus": [], "kind": "share",
        "grain": "auto", "cut": "none", "period": "latest"})
    monkeypatch.setattr(assistant.ask_model, "read_pick", lambda q, c: (next(x["number"] for x in c if "save money" in x["text"]), lead["now"]))
    sure = assistant.answer(question, index, EVERYONE)
    assert sure["understood"] == "reader" and sure["sources"][0]["qcode"] == "Q14" and not calls   # sure: no AI call
    lead["now"] = assistant.READER_SURE - 0.5
    quick = assistant.answer(question, index, EVERYONE, quick=True)
    assert quick["understood"] == "reader" and quick["check"] is True and not calls   # unsure: shown at once, the AI asked after
    checked = assistant.answer(question, index, EVERYONE)
    assert checked["understood"] == "model" and checked["sources"][0]["qcode"] == "XQ1" and len(calls) == 1
    monkeypatch.setattr(assistant.ask_model, "plan", lambda q, c: None)   # no key (or the AI failed): the reader's pick stands
    assert assistant.answer(question, index, EVERYONE)["sources"][0]["qcode"] == "Q14"
    # a reader's pick using every subject word stands over the AI's pick missing one, and over its "none of these"
    monkeypatch.setattr(assistant, "lacking", lambda plan, key, *rest: (["amazon"] if key.endswith("/XQ1") else [], 1, False))
    monkeypatch.setattr(assistant.ask_model, "plan", lambda q, c: {
        "pick": next(x["number"] for x in c if "retailers" in x["text"]), "alt": None, "focus": [], "kind": "share",
        "grain": "auto", "cut": "none", "period": "latest"})
    assert assistant.answer(question, index, EVERYONE)["sources"][0]["qcode"] == "Q14"
    monkeypatch.setattr(assistant.ask_model, "plan", lambda q, c: {
        "pick": None, "alt": None, "focus": [], "kind": "share", "grain": "auto", "cut": "none", "period": "latest"})
    assert assistant.answer(question, index, EVERYONE)["sources"][0]["qcode"] == "Q14"


def test_a_misspelt_retailer_is_put_right_and_other_words_are_left_alone(tmp_path, index, monkeypatch):
    from api import ask_index
    monkeypatch.setattr(ask_index, "BRAND_WAVES", 8)   # the test retailer list has 8 waves; the real ones 15 or more
    waves = [{"survey_id": 100 + i, "wave_date": d, "title": "Shopping and Spending", "modules": []} for i, d in enumerate(DATES)]
    again = Index(tmp_path / "questions", waves)
    assert again.brand_words == ["amazon", "walmart"]   # the retailer list's answers, not Q14's (no "retailer" in its wording)
    assert again.correct_spelling("Walmrt shoppers") == "Walmart shoppers"
    assert again.correct_spelling("What share bought from Amazon in the latest wave?") == "What share bought from Amazon in the latest wave?"


@pytest.fixture()
def with_prime(tmp_path, index, monkeypatch):
    """The test index with a Prime membership question (PM1) beside the retailer list (XQ1), whose 8 waves count as
    long-running here (the real lists: 195)."""
    if index.vectors is None:
        pytest.skip("search model not downloaded (deploy/ask-model-download.py)")
    (tmp_path / "questions" / "CSI-US" / "tracker" / "PM1.json.gz").write_bytes(gzip.compress(json.dumps(question_file(
        [[107, DATES[7], 1]], ["Do you have an Amazon Prime membership?"], [["", 1, "Yes"], ["", 2, "No"]],
        [["total", "Total"]], [(0, 0, 0, 120, 400), (0, 0, 1, 280, 400)])).encode()))
    waves = [{"survey_id": 100 + i, "wave_date": d, "title": "Shopping and Spending", "modules": []} for i, d in enumerate(DATES)]
    again = Index(tmp_path / "questions", waves)
    again.add_vectors()
    monkeypatch.setattr(assistant, "TREND_FROM", 1)
    return again


def test_a_retailer_and_a_time_alone_is_the_retailer_list_even_when_the_ai_picks_a_question_naming_it(with_prime, monkeypatch):
    monkeypatch.setattr(assistant.ask_model, "ready", lambda: True)
    monkeypatch.setattr(assistant.ask_model, "plan", lambda q, c: {   # the AI picks the question with Amazon in its wording
        "pick": next(x["number"] for x in c if "Prime" in x["text"]), "alt": None, "focus": [], "kind": "share",
        "grain": "auto", "cut": "none", "period": "all"})
    assert assistant.answer("Amazon in October 2026", with_prime, EVERYONE)["sources"][0]["qcode"] == "XQ1"
    assert assistant.answer("How many have Amazon Prime?", with_prime, EVERYONE)["sources"][0]["qcode"] == "PM1"


def test_a_name_the_question_says_in_full_is_not_a_shorter_answer_in_the_lists(with_prime, monkeypatch):
    """"bought Amazon prime" is the Prime membership question, whose wording says "Amazon Prime", not "Amazon" among the
    retailer list's answers: the list went first and the reader, sure, took it (fresh set, 15 Nov 2026)."""
    monkeypatch.setattr(assistant.ask_model, "read_pick", lambda q, c: (c[0]["number"], 9.0))   # a sure reader taking the first line
    assert assistant.answer("How many people bought Amazon prime?", with_prime, EVERYONE)["sources"][0]["qcode"] == "PM1"
    assert assistant.answer("How many people bought from Amazon?", with_prime, EVERYONE)["sources"][0]["qcode"] == "XQ1"
    full = frozenset({"amazon prime", "dollar general"})
    assert assistant.focus("Do Amazon Prime members also buy from Amazon?", ["Walmart", "Amazon"], full) == [1]   # said alone too
    assert assistant.focus("Dollar General shoppers", ["Target", "Dollar General"], full) == [1]   # the whole name is the answer


def test_the_reader_scores_none_of_these_as_zero_and_gives_its_lead(monkeypatch):
    from api import ask_model

    class Words:   # the tokenizer's shape: ids, mask and type ids for each pair
        def encode_batch(self, pairs):
            return [type("Coded", (), {"ids": [1, 2], "attention_mask": [1, 1], "type_ids": [0, 1]})() for _ in pairs]

    class Session:
        def __init__(self, logits, inputs=("input_ids", "attention_mask", "token_type_ids")):
            self.logits, self.inputs = logits, inputs

        def get_inputs(self):
            return [type("Input", (), {"name": n})() for n in self.inputs]

        def run(self, names, feed):
            assert set(feed) == set(self.inputs)   # only the inputs the model has
            return [np.array(self.logits, np.float32).reshape(-1, 1)]

    candidates = [{"number": n, "text": t, "name": "", "waves": 9, "first": "2024-01-01", "last": "2026-11-01", "answers": []}
                  for n, t in ((4, "a"), (7, "b"))]
    monkeypatch.setattr(ask_model, "reader", lambda: (Words(), Session([1.0, 3.5]), {}))
    assert ask_model.read_pick("q", candidates) == (7, pytest.approx(2.5))   # its number, ahead of the next by 2.5
    monkeypatch.setattr(ask_model, "reader", lambda: (Words(), Session([-1.0, -3.0]), {}))
    assert ask_model.read_pick("q", candidates) == (None, pytest.approx(1.0))   # both under "none of these" (0)
    modern = Session([1.0, 3.5], inputs=("input_ids", "attention_mask"))   # a ModernBERT reader: no token type ids
    monkeypatch.setattr(ask_model, "reader", lambda: (Words(), modern, {}))
    assert ask_model.read_pick("q", candidates)[0] == 7


def test_a_search_model_is_pooled_and_cut_as_its_calibration_says(monkeypatch):
    from api import ask_model

    class Words:   # two texts of three tokens, the second padded after two
        def encode_batch(self, texts):
            return [type("Coded", (), {"ids": [1, 2, 3], "attention_mask": [1, 1, 1 - i]})() for i, _ in enumerate(texts)]

    class Session:
        def get_inputs(self):
            return [type("Input", (), {"name": n})() for n in ("input_ids", "attention_mask")]

        def run(self, names, feed):   # each token's vector: [position + 1, 10 × text, 1, 0]
            return [np.array([[[p + 1, 10 * t, 1, 0] for p in range(3)] for t in range(2)], np.float32)]

    unit = lambda v: np.array(v, np.float32) / np.linalg.norm(v)
    for settings, first, second in (({}, [1, 0, 1, 0], [1, 10, 1, 0]),                         # cls: the first token
                                    ({"pooling": "last"}, [3, 0, 1, 0], [2, 10, 1, 0]),        # the last real token
                                    ({"pooling": "mean"}, [2, 0, 1, 0], [1.5, 10, 1, 0])):      # the real tokens' mean
        monkeypatch.setattr(ask_model, "encoder", lambda: (Words(), Session(), settings))
        out = ask_model.embed(["a", "b"])
        assert np.allclose(out[0], unit(first)) and np.allclose(out[1], unit(second))
    monkeypatch.setattr(ask_model, "encoder", lambda: (Words(), Session(), {"dims": 2}))
    assert ask_model.embed(["a", "b"]).shape == (2, 2)   # Matryoshka: the first "dims" numbers kept
    monkeypatch.setattr(ask_model, "calibration", lambda: {"query_prefix": "query: ", "doc_prefix": "passage: "})
    assert ask_model.as_query("Amazon") == "query: Amazon" and ask_model.as_survey_question("Q5") == "passage: Q5"


def test_dont_know_with_a_curly_apostrophe_is_left_out_like_a_straight_one():
    # survey files spell it both ways; the curly one was ranked as an answer and read as a specific answer (13 Nov 2026)
    assert assistant.SKIP.match("Don’t know") and assistant.GENERIC.match("Don’t know / not sure")


def test_a_share_and_a_period_are_said_as_people_say_them():
    assert assistant.say_share(67.2) == "About two in three (67.2%)"
    assert assistant.say_share(50.0) == "Half (50.0%)" and assistant.say_share(44.1) == "44.1%"
    assert assistant.say_period("9 Nov 2026") == "on 9 Nov 2026" and assistant.say_period("Nov 2026") == "in Nov 2026"
    assert assistant.say_period("9 Oct 2023 – 28 Sep 2026") == "over 9 Oct 2023 – 28 Sep 2026"


def test_the_chart_fits_the_figures_as_the_dataviz_forms_say():
    def fig(pct, answers, periods=1, columns=(("total", "Total"),), grain=None):
        return {"pct": np.array(pct, float), "bases": np.full(np.shape(pct), 400), "answers": answers, "columns": list(columns),
                "grain": grain, "periods": [{"label": f"P{p + 1}"} for p in range(periods)]}
    yes_no = fig([[[60, 40]], [[55, 45]], [[67, 33]]], ["Yes", "No"], periods=3, grain="month")
    assert [s["name"] for s in assistant.chart(yes_no, [0, 1])["series"]] == ["Yes"]   # the other line only mirrors it
    three = fig([[[20, 30, 50]], [[25, 30, 45]], [[30, 30, 40]]], ["Better", "Worse", "Same"], periods=3, grain="month")
    assert [s["name"] for s in assistant.chart(three, [0, 1])["series"]] == ["Better", "Worse"]   # two of three: both real
    first_latest = fig([[[30, 70]], [[44, 56]]], ["Started", "Not started"], periods=2)
    assert assistant.chart(first_latest, [0, 1])["type"] == "dumbbell"                 # two periods compared
    assert assistant.chart({**first_latest, "grain": "quarter"}, [0, 1])["type"] == "line"   # a trend that has two
    assert assistant.chart(fig([[[50, 30, 20]]], ["A", "B", "C"]), [0])["type"] == "split"   # one whole, few parts
    many = fig([[[20, 15, 15, 10, 10, 10, 10, 10]]], list("ABCDEFGH"))
    assert assistant.chart(many, [0])["type"] == "bar"                                 # too many parts: ranked bars
    groups = (("generation", "GenZ"), ("generation", "Boomer"))
    stacked = assistant.chart(fig([[[60, 40], [30, 70]]], ["Yes", "No"], columns=groups), [0])
    assert stacked["type"] == "stacked" and stacked["categories"] == ["GenZ", "Boomer"]   # a single choice by a cut
    assert stacked["bases"] == {"GenZ": 400, "Boomer": 400}                            # each group's n, shown beside it
    four = tuple(("income_band", f"I{i}") for i in range(4))
    grid = fig([[[40, 35, 30, 25, 20]] * 4], list("ABCDE"), columns=four)
    assert assistant.chart(grid, [0])["type"] == "heatmap"                            # many answers by many groups


def test_the_glance_never_names_a_small_group_and_says_a_lead_or_a_most_common_answer():
    def fig(pct, bases, answers, columns):
        pct, bases = np.array(pct, float), np.array(bases, float)
        return {"pct": pct, "bases": bases, "people": pct * bases / 100, "answers": answers, "columns": columns,
                "periods": [{"label": "9 Nov 2026"}], "grain": None}
    by_generation = fig([[[60, 40], [30, 70], [90, 10]]], [[[200] * 2, [150] * 2, [30] * 2]], ["Yes", "No"],
                        [("generation", "GenZ"), ("generation", "Boomer"), ("generation", "Silent")])
    doc = {"text": "Did gas prices make you spend less?", "name": "Gas prices reducing spending"}
    glance = assistant.brief({"kind": "share"}, by_generation, doc, [0])
    assert [t["label"] for t in glance["tiles"]] == ["Highest: GenZ", "Lowest: Boomer", "Gap"]   # Silent: 30 people
    assert glance["tiles"][0]["note"] == "Gas prices reducing spending: yes, 9 Nov 2026"         # a yes says what to
    assert glance["tiles"][2] == {"label": "Gap", "value": "30.0 pts", "note": "GenZ vs Boomer, significant"}
    assert glance["takeaway"] == ("Gen Z are about twice as likely as Boomers to say yes to “Gas prices reducing spending”: "   # the verdict
                                  "60.0% against 30.0% on 9 Nov 2026 (groups under 50 people not compared).")   # first, then its figures
    total = [("total", "Total")]
    split = fig([[[50, 30, 20]]], [[[400] * 3]], ["A", "B", "C"], total)
    assert assistant.brief({"kind": "share"}, split, doc, [0, 1])["takeaway"] == "The most common answer on 9 Nov 2026 is A (50.0%), ahead of B (30.0%)."
    listed = assistant.brief({"kind": "share"}, fig([[[50, 30, 45]]], [[[400] * 3]], ["A", "B", "C"], total), doc, [0, 1])
    assert listed["takeaway"] == "A leads on 9 Nov 2026 at 50.0%, well ahead of B (30.0%)."    # several each: a lead of 10+ points
    named = fig([[[20, 30, 50]]], [[[400] * 3]], ["Better", "Worse", "Same"], total)       # two named, “Same” first of all
    assert assistant.brief({"kind": "share"}, named, doc, [0, 1], True)["takeaway"] == "Worse is at 30.0% on 9 Nov 2026, Better at 20.0%."
    scale = assistant.brief({"kind": "share"}, named, doc, [2])   # nothing named: a better/worse scale said as its net
    assert scale["takeaway"] == "More said “worse” than “better”: 30.0% worse, 20.0% better on 9 Nov 2026."
    plain = fig([[[50, 50]]], [[[400] * 2]], ["Yes", "No"], total)
    doc = {"text": "How much did you spend on Prime Day?", "name": "Previous year's Prime Day spending", "key": "K",
           "cuts": {"generation": []}, "waves": 5}
    follow = assistant.follow_ups({"cuts": {}}, plain, doc, [0])
    assert [f["question"] for f in follow] == ["How much did you spend on Prime Day by generation",
                                               "How much did you spend on Prime Day over time"]   # the name's period left out
    assert assistant.follow_ups({"cuts": {}}, plain, {**doc, "text": "How much did you spend on Prime Day last year?"}, [0]) == []


def test_an_answer_leads_with_tiles_a_takeaway_and_follow_ups_that_come_back_to_it(index):
    found = assistant.answer("What share bought from Amazon in all waves?", index, EVERYONE)
    amazon = next(r for r in found["table"]["rows"] if r[0] == "Amazon")
    assert found["tiles"][0]["value"] == assistant.fmt(amazon[-1]) and found["tiles"][1]["label"].startswith("Change since")
    assert "up" in found["takeaway"] and found["takeaway"].startswith("Amazon:")
    follow = next(f for f in found["next"] if f["question"].endswith("by generation"))
    assert follow["key"] == "CSI-US/tracker/XQ1"
    again = assistant.answer(follow["question"], index, EVERYONE, key=follow["key"])
    assert again["sources"][0]["key"] == "CSI-US/tracker/XQ1" and set(again["plan"]["cuts"]) == {"generation"}
    other = next(k for k in index.docs if k != "CSI-US/tracker/XQ1")
    question = "What share bought from Amazon in all waves?"
    assert assistant.ask(question, index, EVERYONE, "all")["sources"][0]["key"] == "CSI-US/tracker/XQ1"
    assert assistant.ask(question, index, EVERYONE, "all", key=other)["sources"][0]["key"] == other   # not the kept answer
    later = {s for s in EVERYONE if s not in index.docs[other]["surveys"]}   # waves where the other question was not asked
    ignored = assistant.answer(question, index, later, key=other)   # the key ignored: found and read as any question
    assert ignored["sources"][0]["key"] == "CSI-US/tracker/XQ1" and ignored["understood"] != "named"


def test_spelling_is_put_right_for_survey_words_and_name_starts_and_valid_words_stay(with_prime):
    """"subcription" and "Ama Prime" found nothing on staging (13 Nov 2026); a survey word with an ending ("noted",
    "having") is never "corrected", as "having" became "behaving" once (15 Nov 2026)."""
    fix = with_prime.correct_spelling
    assert fix("How many Ama Prime members") == "How many Amazon Prime members"   # a short start before a two-word name
    assert fix("Amazon membrship") == "Amazon membership"                          # a survey word, same start, one letter off
    assert fix("Who noted it while having retailers") == "Who noted it while having retailers"
    # an English word the search model knows whole is never a typo ("monkey" was "money"), and a typo is never put
    # right to a synonym's stem ("Fridya" was "Frida", from friday): review of 15 Nov 2026
    assert fix("A monkey bought it on Black Fridya") == "A monkey bought it on Black Fridya"


def test_an_answer_to_a_corrected_question_says_so_and_typing_offers_questions_by_name(with_prime):
    """The Ask box's suggestions while typing (assistant.suggest) and the corrected question on the answer (15 Nov 2026)."""
    answered = assistant.ask("Ama Prime membership", with_prime, EVERYONE, "all")
    assert answered["corrected"] == "Amazon Prime membership"
    offer = assistant.suggest("ama prim", with_prime, EVERYONE)   # each word typed is the start of one of the name's
    assert offer["corrected"] is None and [s["key"] for s in offer["suggestions"]][:1] == ["CSI-US/tracker/PM1"]
    assert assistant.suggest("Ama Prime memb", with_prime, EVERYONE)["corrected"] == "Amazon Prime memb"
    assert assistant.suggest("ama prim", with_prime, {999})["suggestions"] == []   # only questions this person may see
    retailers = assistant.suggest("retailers bought", with_prime, {100, 101})["suggestions"]   # XQ1: 8 waves, 2 seen
    assert [s["waves"] for s in retailers if s["qcode"] == "XQ1"] == [2]


def test_a_kept_ai_reading_requires_the_same_model_and_evidence(tmp_path, monkeypatch):
    """An older model's reading turned the reader's right answer wrong ("Satisfaction with shopping in AI platforms":
    D34 → GA2, review of 15 Nov 2026): readings are kept per model and prompt."""
    from api import ask_model
    monkeypatch.setattr(ask_model, "READINGS", tmp_path / "readings.json")
    monkeypatch.setattr(ask_model, "ready", lambda: False)   # no call: only a kept reading can answer
    line = {"number": 1, "text": "Which retailers have you bought from?", "waves": 9, "first": "2025-01-01", "last": "2026-11-01", "answers": ["Amazon"]}
    monkeypatch.setattr(ask_model, "model", lambda: "gpt-4o-mini")
    question = "How many bought from Amazon?"
    memo = ask_model.reading_key("gpt-4o-mini", f"{question}\n1. {ask_model.describe_candidate(line)}")
    (tmp_path / "readings.json").write_text(json.dumps({memo: {"pick": 1, "alt": None, "focus": [], "kind": "share", "grain": "auto",
                                                               "cut": "none", "period": "all"}}))
    assert ask_model.plan(question, [line])["pick"] == 1
    assert ask_model.plan("What share bought from Amazon?", [line]) is None
    assert ask_model.plan(question, [{**line, "answers": ["Costco"]}]) is None
    monkeypatch.setattr(ask_model, "model", lambda: "gpt-4.1-mini")   # another model: its own reading, not the kept one
    assert ask_model.plan(question, [line]) is None


def test_provider_timeout_with_malformed_cache_uses_the_local_answer(index, tmp_path, monkeypatch):
    from api import ask_model
    if index.vectors is None:
        pytest.skip("search model not downloaded")
    path = tmp_path / "readings.json"
    path.write_text("[]")
    monkeypatch.setattr(ask_model, "READINGS", path)
    monkeypatch.setattr(ask_model, "ready", lambda: True)
    calls = []

    def timeout(*_):
        calls.append(1)
        raise TimeoutError

    monkeypatch.setattr(ask_model, "call", timeout)
    found = assistant.answer("Amazon shoppers over time", index, EVERYONE)
    assert calls == [1]
    assert found["mode"] in ("figures", "choose") and found.get("understood") != "model"
    assert path.read_text() == "[]"


def test_this_quarter_a_bare_month_and_right_now_are_read_from_todays_calendar(monkeypatch):
    # 20 Nov 2026: "this quarter" fell back to every wave, "October vs September" named no period, "right now" stayed a
    # search word and pushed the economy question below a match
    class Today(ask_reader.date):
        @classmethod
        def today(cls):
            return cls(2026, 11, 20)
    monkeypatch.setattr(ask_reader, "date", Today)
    read = lambda q: ask_reader.read(q)["when"]   # noqa: E731
    assert read("Amazon this quarter") == [{"quarter": (2026, 4)}]
    assert read("Walmart last quarter") == [{"quarter": (2026, 3)}]
    assert read("Prime members year to date") == [{"from": "2026-01-01", "to": "2026-11-20"}]
    assert read("Online shopping in October vs September") == [{"month": (2026, 10)}, {"month": (2026, 9)}]
    assert read("December holiday spending in December") == [{"month": (2025, 12)}]   # not yet this year: the last one
    assert read("Q4 holiday spending") == [{"quarter": (2026, 4)}]
    assert read("How many people may buy online?") == [] and read("What may happen in March?") == [{"month": (2026, 3)}]
    assert read("How do people feel about the economy right now?") == [{"latest": 1}]


def test_an_acronym_no_survey_uses_gets_no_stand_in_figure(index):
    found = assistant.answer("How many people bought from Amazon on OTT?", index, EVERYONE)
    assert found["mode"] == "none" and "OTT" in found["answer"]
    assert assistant.answer("HOW MANY PEOPLE BOUGHT FROM AMAZON IN THE LATEST WAVE", index, EVERYONE)["mode"] == "figures"


def test_no_period_and_a_group_reads_the_newest_wave_that_has_the_group(tmp_path):
    root = tmp_path / "questions" / "CSI-US" / "tracker"
    root.mkdir(parents=True)
    cells = [(i, 0, 0, 100, 400) for i in range(8)] + [(i, 1, 0, 30, 100) for i in range(7)]   # newest wave: no Gen Z
    (root / "XQ2.json.gz").write_bytes(gzip.compress(json.dumps(question_file(
        [[100 + i, d, 1] for i, d in enumerate(DATES)], ["Have you bought clothing online in the past two weeks?"],
        [["", 1, "Yes"]], [["total", "Total"], ["generation", "GenZ"]], cells)).encode()))
    waves = [{"survey_id": 100 + i, "wave_date": d, "title": "Shopping and Spending", "modules": []} for i, d in enumerate(DATES)]
    found = Index(tmp_path / "questions", waves)
    fig = ask_figures.compute(found.counts(next(iter(found.docs))), ask_reader.read("Gen Z buying clothing online"), EVERYONE)
    genz = next(i for i, (_, value) in enumerate(fig["columns"]) if value == "GenZ")
    assert fig["asked"][-1] == DATES[-2] and round(float(fig["pct"][0, genz, 0]), 1) == 30.0   # 19 Oct, Gen Z 30 of 100


def test_a_renumbered_verified_key_finds_its_wording_in_the_same_file(index, tmp_path, monkeypatch):
    # staging, 20 Nov 2026: "CSI-US/tracker/Q19#53" was renumbered when wordings joined its file, and the code alone gave
    # AP14, a question once asked as Q19; the same file's wording sharing the question's words is the one meant
    from api import ask_index, ask_model
    listed = tmp_path / "verified.yml"
    listed.write_text('- {question: "Which ways to save money do people use?", key: "CSI-US/tracker/Q14#9", code: Q14, kind: top, period: latest}\n'
                      '- {question: "Favourite colour of cars", key: "CSI-US/tracker/Q14#7", code: Q14, kind: share, period: latest}\n')
    monkeypatch.setattr(ask_index, "VERIFIED", listed)
    monkeypatch.setattr(ask_model, "question_vectors", lambda texts, prune=False: {k: ask_index.np.ones(384, ask_index.np.float32) for k in texts})
    index.load_verified()
    assert [v["key"] for v in index.verified] == [k for k, d in index.docs.items() if "save money" in d["text"]]
    assert index.unresolved == ["Favourite colour of cars"]   # no wording shares its words: reported, never a guess


def test_a_group_the_pick_lacks_is_read_from_a_near_equal_question_that_has_it(tmp_path):
    # 20 Nov 2026: "Gen Z buying clothing online" read a one-wave study without Gen Z figures and said the group was
    # unavailable; the weekly question, a near-equal match, has them
    root = tmp_path / "questions"
    (root / "APPAREL_STUDY" / "annual").mkdir(parents=True)
    (root / "CSI-US" / "tracker").mkdir(parents=True)
    (root / "APPAREL_STUDY" / "annual" / "q3.json.gz").write_bytes(gzip.compress(json.dumps(question_file(
        [[90, "2026-04-20", 1]], ["Have you been buying clothing online?"], [["", 1, "Yes"], ["", 2, "No"]],
        [["total", "Total"], ["generation", "Millennial"]], [(0, 0, 0, 300, 400), (0, 0, 1, 100, 400), (0, 1, 0, 60, 100)])).encode()))
    (root / "CSI-US" / "tracker" / "XQ3.json.gz").write_bytes(gzip.compress(json.dumps(question_file(
        [[100 + i, d, 1] for i, d in enumerate(DATES)], ["Which categories have you bought online in the past two weeks?"],
        [["", 1, "Clothing"], ["", 2, "Groceries"]], [["total", "Total"], ["generation", "GenZ"]],
        [(i, c, a, 30 + a, 100) for i in range(8) for c in (0, 1) for a in (0, 1)])).encode()))
    waves = [{"survey_id": 90, "wave_date": "2026-04-20", "title": "Apparel", "modules": [], "survey_family": "APPAREL_STUDY", "study_type": "annual"}] + \
            [{"survey_id": 100 + i, "wave_date": d, "title": "Shopping and Spending", "modules": []} for i, d in enumerate(DATES)]
    found = assistant.answer("Share of Gen Z buying clothing online", Index(root, waves), {90} | EVERYONE)
    assert found["mode"] == "figures" and found["sources"][0]["qcode"] == "XQ3"


def test_a_verified_key_whose_number_now_names_another_wording_moves_to_its_own(index, tmp_path, monkeypatch):
    # 20 Nov 2026: regrouping a file's wordings gave Q19#53 to the back-to-school retailers; the stored key exists but is
    # not the reviewed question's wording any more
    from api import ask_index, ask_model
    keys = [k for k in index.docs if k.startswith("CSI-US/tracker/Q14")]
    other = next(k for k in keys if "save money" not in index.docs[k]["text"])
    listed = tmp_path / "verified.yml"
    listed.write_text(f'- {{question: "Which ways to save money do people use?", key: "{other}", code: Q14, kind: top, period: latest}}\n')
    monkeypatch.setattr(ask_index, "VERIFIED", listed)
    monkeypatch.setattr(ask_model, "question_vectors", lambda texts, prune=False: {k: ask_index.np.ones(384, ask_index.np.float32) for k in texts})
    index.load_verified()
    assert [v["key"] for v in index.verified] == [k for k in keys if "save money" in index.docs[k]["text"]]


def test_ask_reads_only_a_files_own_waves_of_a_wording(tmp_path):
    # 20 Nov 2026: the cross-code join gave Q10_1's four-week activities wording 211 borrowed waves, and Ask took Q10_1
    # for the activities question; the borrowed waves are the other file's, joined by Ask itself
    root = tmp_path / "questions" / "CSI-US" / "tracker"
    root.mkdir(parents=True)
    data = question_file([[100 + i, d, 1] for i, d in enumerate(DATES)], ["Which of these have you done in the past two weeks?"],
                         [["", 1, "Met friends"]], [["total", "Total"]], [(i, 0, 0, 100, 400) for i in range(8)])
    (root / "XQ9.json.gz").write_bytes(gzip.compress(json.dumps({**data, "codes": ["XQ1"], "borrowed": [104, 105, 106, 107]}).encode()))
    waves = [{"survey_id": 100 + i, "wave_date": d, "title": "Shopping and Spending", "modules": []} for i, d in enumerate(DATES)]
    doc = next(iter(Index(tmp_path / "questions", waves).docs.values()))
    assert doc["surveys"] == [100, 101, 102, 103] and doc["last"] == DATES[3]


def test_wordings_join_by_their_own_words_never_by_a_shared_frame_or_across_holidays():
    # 20 Nov 2026: "Which, if any, of these … in the past two weeks?" joined the activities, food-retailer and online
    # questions, and "Thanksgiving 2024" joined "Easter 2025"
    from api.ask_index import wording_groups
    assert wording_groups(["Which, if any, of these have you done in the past two weeks? Select all that apply or None of these.",
                           "And which, if any, of these categories have you purchased ONLINE in the past two weeks?",
                           "Which, if any, of these retailers have you bought any FOOD products from in the past two weeks?"]) == [[1], [2], [3]]
    holiday = "How do you expect your {} spending to compare to last year? Think about all spending."
    assert wording_groups([holiday.format("Thanksgiving 2024"), holiday.format("Easter 2025"), holiday.format("Thanksgiving 2025")]) == [[1, 3], [2]]
    assert wording_groups(["Which categories have you purchased ONLINE in the past two weeks?",
                           "Which categories have you purchased online in the past two weeks (i.e., groceries)?"]) == [[1, 2]]


def test_only_the_same_question_joins_never_a_chain_of_half_alike_ones():
    # 27 Nov 2026: Q10's footwear, online, department-store and beauty questions each shared half their words with the one
    # before, so Ask's beauty trend began with footwear (Aug 2022, 54.8%) and peaked on "bought anything online" (88.8%)
    from api.ask_index import wording_groups
    asked = "Have you purchased any {} in the past three months?"
    assert wording_groups([asked.format("footwear"), asked.format("products online"),
                           asked.format("products from a department store") + " (whether online or in-store)",
                           asked.format("beauty products (whether for men or women)")]) == [[1], [2], [3], [4]]
    # an expectation is not what happened, and one product is not another
    assert wording_groups(["What is the main reason you expect to spend more this Halloween?",
                           "What is the main reason you spent more this Halloween?"]) == [[1], [2]]
    care = "Which of the following are most important to you when selecting the {} products you buy? (select up to three)"
    assert wording_groups([care.format("hair care"), care.format("skin care")]) == [[1], [2]]
    assert wording_groups(["Which of the following have you heard of? Select all that apply", "Have you heard of Web 3?"]) == [[1], [2]]
    # the code review's pairs (27 Nov 2026): a word that changes what is asked never joins
    for one, other in [("How did you shop before the pandemic?", "How did you shop after the pandemic?"),
                       ("Did you spend more than $100 on gifts?", "Did you spend more than $500 on gifts?"),
                       ("Do you anticipate spending more this holiday season?", "Did you spend more this holiday season?"),
                       ("Have you used GenAI tools?", "Have you used GenAI tools for shopping?"),
                       ("Looking back, how did your spending compare?", "Looking forward, how will your spending compare?")]:
        assert wording_groups([one, other]) == [[1], [2]], one
    assert wording_groups(["Have you bought footwear in the past three months?", "Have you bought footwear in the past 3 months?"]) == [[1, 2]]
    # most answers shared, or as many answers: a different list of answers is a different question
    assert wording_groups(["Which do you use?", "Which do you use?"], [{"tiktok", "instagram", "none"}, {"walmart", "target"}]) == [[1], [2]]
    # a lead-in, a year or "generative AI" for "GenAI" leaves one series
    assert wording_groups(["Are you allowed to use generative AI tools at work?", "Are you allowed to use GenAI tools at work?",
                           "On a different topic, are you allowed to use GenAI tools at work?"]) == [[1, 2, 3]]
    assert wording_groups(["Now we would like to focus on your holiday shopping (gifts, decorations, etc). What is the current "
                           "status of your holiday shopping?", "What is the current status of your holiday shopping?"]) == [[1, 2]]
    assert wording_groups(["How did your spending for the 2022 holiday season compare to 2021?",
                           "Looking back, how did your spending for the 2023 holiday season compare to 2022?"]) == [[1, 2]]


def test_which_with_most_ranks_and_most_people_does_not():
    assert ask_reader.read("Which retailers do people shop at most?")["kind"] == "top"
    assert ask_reader.read("What do most people think about tariffs?")["kind"] == "share"


def test_the_answer_leads_with_its_finding_but_a_named_group_keeps_its_name(index):
    everyone = assistant.answer("Amazon retailers bought in the latest wave", index, EVERYONE)
    assert everyone["headline"] == everyone["takeaway"]
    group = assistant.answer("Top retailers among Gen Z in the latest wave", index, EVERYONE)
    assert "among" in group["headline"] and group["headline"] != group["takeaway"]


def test_a_pick_that_misses_the_subject_is_not_an_answer(index):
    key = "CSI-US/tracker/XQ1"   # the retailers question: "Fed rate cuts" picked the gas-prices question this way
    assert assistant.unasked({"about": "fed rate cuts"}, key, index) == ["fed", "rate", "cuts"]
    assert assistant.unasked({"about": "amazon walmart"}, key, index) == []
    assert assistant.unasked({"about": "amazon fed"}, key, index) == []   # one unknown word alone: a typo or a synonym
    assert assistant.unasked({"about": "immigration"}, key, index) == ["immigration"]   # but not as the whole subject


def test_a_dashboard_name_answers_its_answers_summed():
    counts = {"answers": [["", 1, "Not yet started"], ["", 2, "Still shopping"], ["", 3, "Finished shopping"], ["", 4, "Do not make holiday purchases"]]}
    nets = [("Not started", [1]), ("Started", [2, 3]), ("Finished", [3])]
    fresh = lambda: {"pct": np.array([[[41.0, 44.0, 8.0, 7.0]]]), "people": np.array([[[164, 176, 32, 28]]]),   # noqa: E731
                     "bases": np.full((1, 1, 4), 400), "answers": [a[2] for a in counts["answers"]]}
    fig = fresh()
    started = assistant.add_net("What share started holiday shopping?", fig, counts, nets)
    assert fig["answers"][started] == "Started (Still shopping + Finished shopping)"
    assert fig["pct"][0, 0, started] == 52.0 and fig["people"][0, 0, started] == 208   # people summed, not shares
    assert assistant.add_net("How many have not started?", fresh(), counts, nets) == 0          # the most specific name
    assert assistant.add_net("Who hasn't started yet?", fresh(), counts, nets) == 0
    assert assistant.add_net("Holiday retailers", fresh(), counts, nets) is None


def test_the_reader_reads_named_groups_as_their_cut():
    assert ask_reader.by_cut("Do Gen Z shop on Amazon more than boomers?") == "Do shop on Amazon more than ? by generation"
    assert ask_reader.by_cut("Amazon in the South") == "Amazon in by region"
    assert ask_reader.by_cut("Amazon by generation") == "Amazon by generation"


def test_a_pick_using_none_of_the_subject_is_not_an_answer(index):
    key = "CSI-US/tracker/XQ1"   # "saving more money" was answered from the gas-prices question this way
    assert assistant.unasked({"about": "generative tools"}, key, index) == ["generative", "tools"]   # words of another question
    assert assistant.unasked({"about": "amazon tools"}, key, index) == []                           # one of two: it stands


def test_an_old_question_says_when_it_was_last_asked(index, monkeypatch):
    found = assistant.answer("What share bought from Amazon in the latest wave?", index, EVERYONE)
    assert "Last asked" not in found["headline"]
    monkeypatch.setattr(index, "newest", "2028-01-03")
    found = assistant.answer("What share bought from Amazon in the latest wave?", index, EVERYONE)
    assert found["headline"].endswith(" Last asked 26 Oct 2026.")


def test_a_typed_follow_up_is_read_with_the_question_before_it(index):
    key, before = "CSI-US/tracker/XQ1", "Amazon retailers bought in the latest wave"
    assert assistant.follow_on("What about Gen Z?", before, key, index) == ("amazon retailers bought in the latest wave among gen z", key)
    assert assistant.follow_on("what about Walmart?", "Amazon retailers bought among gen z", key, index)[0] == "Walmart retailers bought among gen z"
    assert assistant.follow_on("and by generation?", "Amazon retailers bought among gen z", key, index)[0] == "amazon retailers bought by generation"
    assert assistant.follow_on("and millennials?", "Amazon retailers bought among gen z", key, index)[0] == "amazon retailers bought among gen z among millennials"
    assert assistant.follow_on("Which ways to save money do people use?", before, key, index) == ("Which ways to save money do people use?", None)
    found = assistant.ask("What about Gen Z?", index, EVERYONE, "all", previous=before, previous_key=key)
    assert found["asked_as"].endswith("among gen z") and figure(found, "Amazon") == [85.0]   # 170 // 2 of 100


def test_two_named_answers_by_a_cut_are_compared_group_by_group(index):
    found = assistant.answer("Amazon and Walmart by generation in the latest wave", index, EVERYONE)
    assert found["chart"]["categories"] == ["Walmart", "Amazon"]
    # GenZ: Amazon 85%, Walmart 50%; Millennial: Walmart 60%, Amazon 40%
    assert found["takeaway"] == ("“Walmart” is ahead of “Amazon” in 1 of 2 generation groups on 26 Oct 2026; "
                                 "the widest gap is 35.0 points among GenZ, where “Amazon” leads.")


def test_a_group_with_no_figures_in_the_period_is_not_a_column(tmp_path):
    root = tmp_path / "questions" / "CSI-US" / "tracker"
    root.mkdir(parents=True)
    cells = [(0, 0, 0, 40, 100), (0, 1, 0, 10, 50), (1, 0, 0, 50, 100), (1, 2, 0, 30, 60)]   # the old band: first wave only
    (root / "XQ2.json.gz").write_bytes(gzip.compress(json.dumps(question_file(
        [[100, DATES[0], 1], [101, DATES[1], 1]], ["Which retailers have you bought from?"], [["", 1, "Amazon"]],
        [["total", "Total"], ["income_band", "$0-$9,999"], ["income_band", "under $25,000"]], cells)).encode()))
    waves = [{"survey_id": 100 + i, "wave_date": d, "title": "Shopping", "modules": []} for i, d in enumerate(DATES[:2])]
    fig = ask_figures.compute(Index(tmp_path / "questions", waves).counts("CSI-US/tracker/XQ2"),
                              ask_reader.read("Amazon by income in the latest wave"), {100, 101})
    assert fig["columns"] == [["income_band", "under $25,000"]] and fig["pct"][0, 0, 0] == 50.0


def test_a_summary_question_is_a_line_from_each_overview_question(index, monkeypatch):
    monkeypatch.setattr(assistant, "REPORT", {"family": "CSI-US", "net_words": {"positive": ["coupons"], "negative": ["store brands"]},
                                              "ask_overview": [{"question": "XQ1", "name": "Retailers"}, {"question": "Q14", "name": "Saving", "net": True}]})
    found = assistant.answer("Summarize this week", index, EVERYONE)
    assert [o["name"] for o in found["overview"]] == ["Retailers", "Saving"]
    assert found["overview"][1]["text"] == "net better +50.0 (75.0% better, 25.0% worse)"   # 300 and 100 of 400
    assert [s["id"] for s in found["sources"]] == ["S1", "S2"]
    assert "overview" not in assistant.answer("Summarize Amazon retailers", index, EVERYONE)   # a subject: asked as any question


def test_a_weighted_question_weighs_each_respondent_for_any_group(index, tmp_path):
    # wave 107: four respondents (bits 0-3), Amazon chosen by 0 and 1, the first two Gen Z; weights 3, 1, 1, 1
    people = {"cuts": {"generation": {"GenZ": "3", "Millennial": "c"}},
              "questions": {"XQ1": {"rows": [[1, 0, "Amazon", None, None], [2, 0, "Walmart", None, None]],
                                    "bits": {"0,0": "f", "1,0": "3", "2,0": "c"}}}, "weights": [3.0, 1.0, 1.0, 1.0]}
    (tmp_path / "waves" / "107").mkdir(parents=True)
    (tmp_path / "waves" / "107" / "people.json.gz").write_bytes(gzip.compress(json.dumps(people).encode()))
    found = assistant.answer("What is the Census-weighted share who bought from Amazon in the latest wave?", index, EVERYONE)
    assert found["weighting"] == "weighted" and figure(found, "Amazon") == [66.7]   # (3 + 1) of 6; 42.5% unweighted
    assert found["notes"][-1].startswith("Census-weighted")
    by_generation = assistant.answer("Amazon in the latest wave by generation", index, EVERYONE, weighted=True)
    assert figure(by_generation, "Amazon") == [100.0, 0.0]   # every weighted Gen Z chose it, no Millennial
    earlier = assistant.answer("Amazon in the first wave", index, EVERYONE, weighted=True)
    assert earlier["weighting"] == "unweighted" and "no respondent file" in earlier["notes"][-1]


def test_weights_are_raked_from_a_respondent_file_published_before_them(tmp_path):
    people = {"cuts": {"gender": {"Male": "1", "Female": "e"}}, "questions": {}}   # 1 man, 3 women; Census 49 / 51
    (tmp_path / "people.json.gz").write_bytes(gzip.compress(json.dumps(people).encode()))
    weights = assistant.weights_of(tmp_path / "people.json.gz")
    assert len(weights) == 4 and round(weights[0] / weights[1], 2) == round(49 / 1 / (51 / 3), 2)


def test_one_wave_says_how_it_moved_since_the_wave_before(index):
    found = assistant.answer("What share bought from Amazon in the latest wave?", index, EVERYONE)
    # 170 of 400 against 160 of 400 the week before: +2.5 points, not significant at 95%
    assert found["takeaway"].endswith("That is about the same as on 19 Oct 2026 (40.0%) for Amazon.")   # +2.5 points, not significant
    assert found["tiles"][-1] == {"label": "Change since 19 Oct 2026", "value": "+2.5 pts", "note": "not significant"}


def test_two_kinds_of_group_are_read_from_the_cross_tab_files(index, tmp_path):
    answers = [{"item_id": 1, "option_id": 0, "item_label": "Amazon", "option_code": None, "option_label": None, "sort_order": 1, "flags": ""}]
    # item 0 option 0: answered the question; one row a respondent group: gender, age, generation, income, region, urbanicity, count
    counts = [[0, 0, "Female", "18-29", "GenZ", "", "West", "Urban", 60], [1, 0, "Female", "18-29", "GenZ", "", "West", "Urban", 45],
              [0, 0, "Male", "18-29", "GenZ", "", "West", "Urban", 40], [1, 0, "Male", "18-29", "GenZ", "", "West", "Urban", 10]]
    (tmp_path / "waves" / "107" / "cuts").mkdir(parents=True)
    (tmp_path / "waves" / "107" / "cuts" / "XQ1.json.gz").write_bytes(gzip.compress(json.dumps({"answers": answers, "counts": counts}).encode()))
    found = assistant.answer("What share of Gen Z women bought from Amazon?", index, EVERYONE)
    assert found["headline"] == "75.0% of Gen Z women said Amazon on 26 Oct 2026 (45 of 60)."
    both = assistant.answer("Amazon by generation and gender", index, EVERYONE)
    assert both["table"]["head"] == ["Answer", "GenZ · Female", "GenZ · Male"] and both["table"]["rows"] == [["Amazon", 75.0, 25.0]]


def test_a_free_ai_check_nvidia_or_gemini_is_on_only_when_chosen_and_never_capped_by_openai_spend(monkeypatch, tmp_path):
    from api import ask_model
    for name in ask_model.KEY_NAMES + ask_model.NVIDIA_NAMES + ask_model.GEMINI_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("NVIDIA-API", "nvapi-test")   # the user's .env spells it so
    monkeypatch.delenv("CIP_ASK_MODEL", raising=False)
    monkeypatch.delenv("CIP_ASK_PROVIDER", raising=False)
    assert not ask_model.ready()   # never on by itself: it answered worse than no AI (21 Nov 2026)
    monkeypatch.setenv("CIP_ASK_PROVIDER", "nvidia")
    monkeypatch.setattr(ask_model, "SPEND", tmp_path / "spend.json")
    (tmp_path / "spend.json").write_text(json.dumps({"month": __import__("time").strftime("%Y-%m"), "usd": 9.0, "calls": 1}))
    assert ask_model.nvidia() and ask_model.model() == ask_model.NVIDIA_MODEL and ask_model.ready()
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")   # an OpenAI key wins, and its cap counts
    assert not ask_model.nvidia() and ask_model.model() == "gpt-4o-mini" and not ask_model.ready()
    monkeypatch.setenv("GEMINI_API_KEY", "AIza-test")
    assert ask_model.model() == "gpt-4o-mini"   # Gemini's key alone changes nothing
    monkeypatch.setenv("CIP_ASK_PROVIDER", "gemini")   # chosen, it goes before OpenAI's key and is free of its cap
    assert ask_model.gemini() and ask_model.model() == ask_model.GEMINI_MODEL and ask_model.ready()


def test_how_an_analyst_asks_is_not_the_subject(index):
    key = "CSI-US/tracker/XQ1"   # "holiday shopping retailers list" lost the reader's right pick for lacking "list"
    assert assistant.lacking({"about": "retailers list"}, key, index)[0] == []


def test_high_and_low_income_are_income_groups():
    plan = ask_reader.read("Thanksgiving spending for high income shoppers")
    assert plan["cuts"] == {"income_band": "all"} and plan["merge"] == {"High income ($100,000 or more)": (100_000, 10**9)}
    assert "income" not in plan["about"] and "high" not in plan["about"]
    assert ask_reader.read("low-income grocery spending")["merge"] == {"Low income (under $50,000)": (0, 50_000)}


def test_last_month_on_a_question_not_asked_then_shows_its_latest_figures_said_so(index):
    found = assistant.answer("ways to save money last month", index, EVERYONE)   # Q14 asked only in September
    assert found["mode"] == "figures" and found["notes"][0] == "Not asked in the last month: these are its latest figures."
    assert figure(found, "Coupons") == [75.0]   # its latest wave: 300 of 400


def test_a_best_match_is_flagged_unsure_and_a_chosen_question_is_not(index):
    assert assistant.answer("ways to save money", index, EVERYONE)["unsure"]   # by meaning: the page offers others up front
    assert not assistant.answer("Amazon shoppers", index, EVERYONE, key="CSI-US/tracker/XQ1")["unsure"]   # the one chosen


def test_a_day_is_its_survey_week_and_a_range_keeps_every_month_between():
    assert ask_reader.read("In the 16 Nov 2026 survey, what share are currently using a GLP-1 drug?")["when"] == \
        [{"from": "2026-11-10", "to": "2026-11-16"}]   # not all of November, and "currently" adds no second period
    assert ask_reader.read("GLP-1 use from 14 Sep 2026 to 16 Nov 2026")["when"] == [{"from": "2026-09-08", "to": "2026-11-16"}]
    assert ask_reader.read("July 4th celebration activities by generation")["when"] == []   # the holiday, not 4 July
    assert ask_reader.read("Who chose “Target Circle Week (July 9-15, 2023)”?")["when"] == []   # an answer's own name
    assert ask_reader.read("Amazon in Nov 2026")["when"] == [{"month": (2026, 11)}]


def test_named_income_groups_are_merged_and_survey_counts_are_periods():
    plan = ask_reader.read("Walmart food shoppers in each income group (low, $50,000-$99,999, high)")
    assert plan["merge"] == {"Low income (under $50,000)": (0, 50_000), "Middle income ($50,000-$99,999)": (50_000, 100_000),
                             "High income ($100,000 or more)": (100_000, 10**9)}   # dollar ranges: any wave's bands fit
    assert [ask_figures.income_floor(b) for b in ("under $25,000", "$100,000-$124,999", "$200,000+", "prefer not to say")] == [0, 100_000, 200_000, None]
    assert plan["about"] == "walmart food"
    assert ask_reader.read("Walmart in each of the 10 surveys, oldest first")["when"] == [{"last": 10, "unit": "wave"}]
    assert ask_reader.read("Amazon in the last 4 surveys pooled")["kind"] == "share"


def test_merged_groups_sum_their_people(index):
    plan = {**ask_reader.read("Amazon in the latest wave"), "cuts": {"generation": ["GenZ", "Millennial"]},
            "merge": {"Under 45": ["GenZ", "Millennial"]}}
    fig = ask_figures.compute(index.counts("CSI-US/tracker/XQ1"), plan, EVERYONE)
    assert fig["columns"] == [["generation", "Under 45"]] and fig["pct"][-1, 0, 0] == 62.5   # (85 + 40) of 200


def test_any_answer_and_the_sides_of_a_scale_are_totals():
    fig = {"answers": ["Food", "Toys", "None of these"], "pct": np.array([[[30.0, 20.0, 20.0]]]),
           "people": np.array([[[120, 80, 80]]]), "bases": np.full((1, 1, 3), 400)}
    added = assistant.any_answer("bought anything online", fig)
    assert fig["answers"][added].startswith("Any")
    assert fig["pct"][0, 0, -1] == 80.0   # everyone but None of these
    scale = {"answers": ["Much worse", "Somewhat worse", "About the same", "Somewhat better", "Much better"],
             "pct": np.array([[[14.0, 28.0, 30.0, 19.0, 9.0]]]), "people": np.array([[[56, 112, 120, 76, 36]]]),
             "bases": np.full((1, 1, 5), 400)}
    better, worse = assistant.side_answers("better or worse?", scale)
    assert (scale["pct"][0, 0, better], scale["pct"][0, 0, worse]) == (28.0, 42.0)


def test_among_counts_a_question_only_among_another_answer(index, tmp_path):
    waves = tmp_path / "waves" / "107"
    waves.mkdir(parents=True)   # four people: Amazon and Walmart; Walmart; Amazon; neither answered
    people = {"cuts": {}, "weights": [1, 1, 1, 1], "questions": {"XQ1": {"text": "", "rows": [[1, 1, "", "1", "Amazon"], [1, 2, "", "2", "Walmart"]],
                                                                         "bits": {"1,1": format(0b101, "x"), "1,2": format(0b011, "x")}}}}
    (waves / "people.json.gz").write_bytes(gzip.compress(json.dumps(people).encode()))
    counts = index.counts("CSI-US/tracker/XQ1")
    counts["sources"] = {107: ("XQ1", "")}
    fig = ask_figures.compute(counts, ask_reader.read("Amazon in the latest wave"), EVERYONE)
    out = assistant.among_figures(fig, counts, {"text": "Walmart shoppers", "key": "CSI-US/tracker/XQ1", "labels": ["Walmart"]}, index)
    assert out["columns"] == [["total", "Among Walmart shoppers"]] and out["pct"][0, 0, 0] == 50.0   # 1 of the 2 Walmart shoppers


def test_a_significance_question_gets_yes_or_no_with_the_test():
    fig = {"answers": ["Yes"], "periods": [{"label": "16 Nov 2026"}], "columns": [["gender", "Male"], ["gender", "Female"]],
           "pct": np.array([[[19.0], [12.5]]]), "people": np.array([[[38], [25]]]), "bases": np.array([[[200], [200]]])}
    assert assistant.tested(fig, 0).startswith("No clear difference between men and women")   # p = 0.074, as the raw rows give


def test_the_lead_repeats_what_the_analyst_asked_with_the_figure():
    assert assistant.subject_of("In the 16 Nov survey, what share bought anything ONLINE in the past two weeks?") == \
        "bought anything online in the past two weeks"
    assert assistant.subject_of("Do people have Amazon Prime?") == "have Amazon Prime"
    assert assistant.subject_of("Walmart vs Target") is None   # no "who did what": the brief's lead stays


def test_how_a_verdict_is_asked_is_never_a_missing_subject(index):
    assert assistant.unasked({"about": "amazon doing lately"}, "CSI-US/tracker/XQ1", index) == []   # "How is Amazon doing lately?"


def test_how_many_use_a_list_with_no_answer_named_is_anyone_who_used_one():
    fig = {"answers": ["ChatGPT", "Gemini", "Have not used AI"], "pct": np.array([[[42.0, 35.0, 29.0]]]),
           "people": np.array([[[168, 140, 116]]]), "bases": np.full((1, 1, 3), 400)}
    added = assistant.any_answer("How many people use generative AI?", fig, named=False)
    assert fig["pct"][0, 0, added] == 71.0   # everyone but the 29.0% who used none
    assert assistant.any_answer("How many people use ChatGPT?", fig, named=True) is None   # a tool named: that tool


def test_a_long_answer_is_named_by_its_lead_words_only_once_the_question_is_chosen():
    labels = ["Food or beverages (i.e., groceries)", "Clothing, footwear or fashion accessories", "Pet products"]
    assert assistant.focus("Millennials who bought clothing online", labels) == []   # never to choose a question
    assert assistant.focus("Millennials who bought clothing online", labels, loose=True) == [1]
    assert assistant.focus("share who bought groceries online", labels, loose=True) == [0]   # its "i.e." name


def test_among_reads_a_select_all_answer_from_its_item(index, tmp_path):
    waves = tmp_path / "waves" / "107"
    waves.mkdir(parents=True)   # a select-all list stores each answer as an item: [item, 0, "Walmart", None, None]
    people = {"cuts": {}, "weights": [1, 1, 1, 1], "questions": {"XQ1": {"text": "", "rows": [[1, 0, "Amazon", None, None], [2, 0, "Walmart", None, None]],
                                                                         "bits": {"0,0": format(0b1111, "x"), "1,0": format(0b101, "x"), "2,0": format(0b011, "x")}}}}
    (waves / "people.json.gz").write_bytes(gzip.compress(json.dumps(people).encode()))
    counts = index.counts("CSI-US/tracker/XQ1")
    counts["sources"] = {107: ("XQ1", "")}
    fig = ask_figures.compute(counts, ask_reader.read("Amazon in the latest wave"), EVERYONE)
    out = assistant.among_figures(fig, counts, {"text": "Walmart shoppers", "key": "CSI-US/tracker/XQ1", "labels": ["Walmart"]}, index)
    assert out["pct"][0, 0, 0] == 50.0   # Amazon among the 2 Walmart shoppers; matched by item it was nobody (22 Nov 2026)


def test_a_respondent_file_question_is_found_in_any_case():
    people = {"questions": {"q5": {"rows": [], "bits": {}}}}
    assert assistant.question_in(people, "Q5") is people["questions"]["q5"]   # weighted answers fell back on staging


def test_a_pick_one_of_two_exercise_is_never_an_answer_and_two_groups_read_as_people():
    assert assistant.best_of_pairs({"labels": ["Inflation worries me: This one", "Theft worries me: This one"]})
    assert not assistant.best_of_pairs({"labels": ["Yes", "No"]})
    assert assistant.said_as("generation", "GenZ", "gender", "Female") == "Gen Z women"
    assert assistant.said_as("gender", "Female", "census_region", "South") == "women in the South"


def test_not_likely_is_never_on_the_likely_side_and_how_many_use_reads_the_likely_ones():
    fig = {"answers": ["Very likely", "Somewhat likely", "Not likely", "Never"], "pct": np.array([[[10.0, 17.0, 40.0, 33.0]]]),
           "people": np.array([[[40, 68, 160, 132]]]), "bases": np.full((1, 1, 4), 400)}
    (likely,) = assistant.side_answers("How many people use BNPL?", fig)
    assert fig["pct"][0, 0, likely] == 27.0   # Very + Somewhat, never Not likely


def test_each_week_asked_is_one_figure_per_week_with_changes_from_the_real_counts():
    # ChatGPT's 40-question answer key (22 Nov 2026): "in each of the four survey weeks" pooled them into one 51.3%
    assert ask_reader.read("What share had started holiday shopping in each of the four survey weeks?")["grain"] == "wave"
    across = ask_reader.read("How do in-platform purchasing and purchase satisfaction compare across the AI shopping waves?")
    assert across["grain"] == "wave" and "ai shopping" in across["about"]
    assert ask_reader.read("Across all 10 surveys pooled, share who bought from Amazon")["grain"] is None
    fig = {"grain": "wave", "periods": [{"label": d} for d in ("26 Oct 2026", "2 Nov 2026", "9 Nov 2026", "16 Nov 2026")],
           "pct": np.array([[[42.6]], [[58.8]], [[52.2]], [[51.7]]]), "people": np.array([[[172]], [[237]], [[211]], [[209]]]),
           "bases": np.array([[[404]], [[403]], [[404]], [[404]]])}
    assert round(assistant.exact(fig, 3, 0, 0) - assistant.exact(fig, 0, 0, 0), 1) == 9.2   # 9.1 from the rounded shares
    assert assistant.week_by_week(fig, [("Started", [42.6, 58.8, 52.2, 51.7])]) == \
        "Week by week (26 Oct, 2 Nov, 9 Nov, 16 Nov 2026): 42.6%, 58.8%, 52.2%, 51.7%."
    assert assistant.week_by_week({**fig, "grain": "month"}, [("Started", [1, 2, 3, 4])]) == ""


def test_analyst_wording_keeps_its_subject_groups_and_periods():
    asked = ask_reader.read("Which five retailers were most used by holiday purchasers?")
    assert "retailers" in asked["about"] and asked["top"] == 5   # "which … most" took "five retailers were" with it
    assert ask_reader.read("What were the five most commonly purchased categories?")["top"] == 5
    weekly = ask_reader.read("What is the latest started-shopping percentage, and is its weekly change significant?")
    assert weekly["when"] == [{"latest": 2}, {"latest": 1}]
    assert ask_reader.read("How many respondents are in this survey?")["when"] == [{"latest": 1}]
    dollars = ask_reader.read("Gas cuts across households earning below $50,000, $50,000-$99,999, and $100,000 or more")
    assert len(dollars["merge"]) == 3 and dollars["cuts"] == {"income_band": "all"}


def test_tool_use_with_no_tool_named_is_anyone_who_used_one():
    fig = {"answers": ["ChatGPT", "Gemini", "Have not used AI in the last two weeks"], "pct": np.array([[[45.0, 30.0, 30.0]]]),
           "people": np.array([[[180, 120, 120]]]), "bases": np.full((1, 1, 3), 400)}
    any_use = assistant.any_answer("How does recent AI-tool use compare across these waves?", fig, named=False)
    assert fig["pct"][0, 0, any_use] == 70.0
    assert assistant.any_answer("Which AI tools do people use most?", fig, named=False) is None


def test_a_weighted_change_is_tested_on_the_unweighted_shares():
    fig = {"periods": [{"label": "9 Nov 2026"}, {"label": "16 Nov 2026"}], "columns": [["total", "All"]], "answers": ["Started"],
           "pct": np.array([[[51.6]], [[51.4]]]), "tested": np.array([[[52.2]], [[51.7]]]),
           "people": np.array([[[208.5]], [[207.7]]]), "bases": np.array([[[404]], [[404]]])}
    assert "p = 0.887" in assistant.tested(fig, 0)   # the weighted people gave p = 1.000


def test_a_holiday_question_keeps_its_weeks_before_the_holiday(tmp_path):
    # "Will you spend on Halloween?" answers "I will spend…" before the holiday and "I spent…" after; checked against the
    # newest week alone, the earlier weeks left every entry (282 weeks of 112 questions, found by the hard test set)
    root = tmp_path / "questions" / "CSI-US" / "tracker"
    root.mkdir(parents=True)
    (root / "HW1.json.gz").write_bytes(gzip.compress(json.dumps(question_file(
        [[100, DATES[0], 1], [101, DATES[1], 2]],
        ["Will you spend on or celebrate Halloween this year?", "Did you spend on or celebrate Halloween this year?"],
        [["", 1, "I will spend on Halloween this year"], ["", 2, "I won't spend"], ["", 3, "I spent on Halloween this year"], ["", 4, "I did not spend"]],
        [["total", "Total"]], [(0, 0, 0, 240, 400), (0, 0, 1, 160, 400), (1, 0, 2, 200, 400), (1, 0, 3, 200, 400)])).encode()))
    waves = [{"survey_id": 100 + i, "wave_date": d, "title": "Shopping and Spending", "modules": []} for i, d in enumerate(DATES[:2])]
    halloween = Index(tmp_path / "questions", waves).docs["CSI-US/tracker/HW1"]
    assert halloween["surveys"] == [100, 101]


def test_a_question_is_searched_part_by_part_in_the_weeks_it_names():
    from api import ask_plan
    assert ask_plan.parts("Among GLP-1 users on 16 Nov, what share bought footwear?")[1:] == ["GLP-1 users on 16 Nov", "what share bought footwear"]
    ids = {"2026-11-02": 1, "2026-11-09": 2, "2026-11-16": 3}
    assert ask_plan.weeks("What share bought footwear on 16 Nov 2026?", ids) == {3}
    assert ask_plan.weeks("Footwear buyers over the last 2 waves", ids) == {2, 3}
    assert ask_plan.weeks("Who buys footwear?", ids) is None


def test_the_plan_filler_reads_groups_weeks_and_list_items():
    from api import ask_plan
    assert ask_plan.demographic("women") == {"q": "D1", "is": ["Female"]}
    assert ask_plan.demographic("55 and older") == {"q": "D2", "between": [55, 120]}
    assert ask_plan.demographic("under-30s") == {"q": "D2", "between": [18, 29]}
    assert ask_plan.demographic("$100,000 or more")["q"] == "D5"
    assert list(ask_plan.age_bands("by age: 18-34, 35-54, 55+")) == ["18-34", "35-54", "55+"]
    a, _, b, _ = ask_plan.sides("What share of women used AI", "men?")
    assert (a, b) == ("women", "men")
    # a list answer said in other words; nothing when two tie
    assert ask_plan.items("In-store grocery purchasing", ["Pet products", "Food or beverages (i.e., groceries)"]) == ["Food or beverages (i.e., groceries)"]
    assert ask_plan.items("Going to a bar", ["Gone to a bar", "Gone to a gym"]) == ["Gone to a bar"]
    assert ask_plan.items("shopping", ["Holiday shopping", "Grocery shopping"]) == []
    # a funnel's "GenAI shopping" and a group's "GenAI shoppers" are those who have done it (read as anyone asked on staging)
    genai = ["Have used GenAI to shop", "Plan to use GenAI to shop within the next six months", "Will not use GenAI to shop"]
    assert ask_plan.items("GenAI shopping", genai) == ask_plan.items("GenAI shoppers", genai) == ["Have used GenAI to shop"]
    # a bare count of weeks, "get worse", group nouns and age bands are never a subject no survey asks (held-out set);
    # counts that survey names say stay ("in the past two weeks")
    assert ask_reader.read("Expecting personal finances to get worse, each week of the last four")["about"] == "expecting personal finances worse"
    assert "buyers" not in ask_reader.read("Home-improvement buyers among 18-34s")["about"].split()
    assert "two" in ask_reader.read("Recent activities in past two weeks")["about"].split()
    # a question's own recall period is wording, not a time; a day named is the time
    ids = {"2026-11-02": 1, "2026-11-09": 2, "2026-11-16": 3}
    assert ask_plan.weeks("Used ChatGPT in the last two weeks, 16 Nov 2026?", ids) == {3}
    assert ask_plan.weeks("GLP-1 use in every week of the last 2", ids) == {2, 3}


def test_a_median_or_average_of_dollar_bands_is_worked_out_from_the_counts():
    answers = ["Less than $100", "$100-$299", "$300-$499", "$4,000+", "Don't know"]
    fig = {"answers": answers, "periods": [{"label": "7 Sep 2026"}], "columns": [["total", "total"]],
           "people": np.array([[[10, 20, 30, 40, 99]]])}   # "Don't know" left out: 100 gave an amount, the 50th is in $300-$499
    assert ask_figures.middle(fig) == [(0, "$300-$499", round((10 * 50 + 20 * 199.5 + 30 * 399.5 + 40 * 4000) / 100))]
    assert ask_figures.middle({**fig, "answers": ["Yes", "No", "Maybe", "Never", "Other"]}) == []   # not amounts: nothing


def test_a_named_period_is_said_by_the_dates_not_repeated_as_what_people_did():
    assert assistant.subject_of("What share bought groceries online in October vs September?") == "bought groceries online"
    assert assistant.subject_of("What share bought groceries online in September vs October 2026?") == "bought groceries online"
    assert assistant.subject_of("What share bought anything online in the past two weeks?") == "bought anything online in the past two weeks"


def test_did_x_cause_people_to_do_y_answers_what_people_reported(monkeypatch):
    calls = []
    real = assistant.answer

    def fake(question, *args, **kwargs):
        if not question.lower().startswith("did "):
            calls.append(question)
            return {"mode": "figures", "notes": [], "answer": "45.5% said Spend less on non-essentials",
                    "sources": [{"question": "How have you changed your shopping to avoid the impact of tariffs?"}]}
        return real(question, *args, **kwargs)
    monkeypatch.setattr(assistant, "answer", fake)
    class Spelling:
        def correct_spelling(self, text):
            return text
    found = assistant.answer("Did the tariffs cause people to spend less?", Spelling(), set(), True)
    assert calls == ["tariffs spend less?"] and found["notes"][0].startswith("What people said about tariffs")
    calls.clear()   # a period after it is the period, not part of what tariffs changed ("latest wave", real set, 28 Nov 2026)
    found = assistant.answer("Did the tariffs cause people to spend less? latest wave", Spelling(), set(), True)
    assert found["notes"][0].startswith("What people said about tariffs")


def test_vs_last_year_stays_a_period_when_an_unused_answer_says_last_year(tmp_path):
    # a code's file holds every answer it was reused for: "Much more than last year", never offered here, dropped the
    # period from "Walmart vs last year" (Phase 4, 28 Nov 2026)
    root = tmp_path / "questions" / "CSI-US" / "tracker"
    root.mkdir(parents=True)
    dates = ["2025-10-06", "2025-10-13", "2026-10-05", "2026-10-12"]
    cells = [(i, 0, a, n, 400) for i in range(4) for a, n in ((0, 100 + 10 * i), (1, 200))]
    (root / "XQ1.json.gz").write_bytes(gzip.compress(json.dumps(question_file(
        [[100 + i, d, 1] for i, d in enumerate(dates)], ["Which of these retailers have you bought from in the past two weeks?"],
        [["", 1, "Amazon"], ["", 2, "Walmart"], ["", 3, "Much more than last year"]], [["total", "Total"]], cells)).encode()))
    waves = [{"survey_id": 100 + i, "wave_date": d, "title": "Shopping and Spending", "modules": []} for i, d in enumerate(dates)]
    found = assistant.answer("Amazon shoppers vs last year", Index(tmp_path / "questions", waves), {100, 101, 102, 103})
    assert len(found["plan"]["when"]) == 2 and found["layout"]["type"] == "T5"


def test_an_amount_asked_is_answered_from_a_question_in_dollar_bands(index, monkeypatch, tmp_path):
    if index.vectors is None:
        pytest.skip("search model not downloaded (deploy/ask-model-download.py)")
    root = tmp_path / "questions" / "CSI-US" / "tracker"   # beside the fixture's questions: a holiday budget in bands
    bands = ["$1-$99", "$100-$299", "$300-$499", "$500 or more"]
    (root / "HB1.json.gz").write_bytes(gzip.compress(json.dumps(question_file(
        [[107, DATES[7], 1]], ["What is your estimated total budget for holiday spending this year?"],
        [["", i + 1, b] for i, b in enumerate(bands)], [["total", "Total"]],
        [(0, 0, i, n, 400) for i, n in enumerate((50, 150, 120, 80))])).encode()))
    waves = [{"survey_id": 100 + i, "wave_date": d, "title": "Shopping and Spending", "modules": []} for i, d in enumerate(DATES)]
    again = Index(tmp_path / "questions", waves)
    again.add_vectors()
    # the reader takes another question ("median holiday spend" took the spending-change one, then refused)
    monkeypatch.setattr(assistant.ask_model, "read_pick", lambda q, c: (next(x["number"] for x in c if "budget" not in x["text"]), 0.5))
    found = assistant.answer("What was the median holiday spend?", again, EVERYONE, quick=True)
    assert found["sources"][0]["qcode"] == "HB1" and found["layout"]["type"] == "T8"
    assert not assistant.ASKS_AMOUNT.search("What does this mean for Amazon shoppers?")   # not an amount: no move
    assert assistant.ASKS_AMOUNT.search("average holiday budget") and assistant.ASKS_AMOUNT.search("typical amount spent on gifts")


def test_an_unsure_pick_gives_way_only_to_a_question_found_by_meaning_about_as_near(index, monkeypatch):
    if index.vectors is None:
        pytest.skip("search model not downloaded (deploy/ask-model-download.py)")
    xq1, q14 = index.docs["CSI-US/tracker/XQ1"], next(d for k, d in index.docs.items() if "Q14" in k and "save" in d["text"])
    monkeypatch.setattr(assistant, "lacking", lambda plan, key, *rest: (["worry"] if key == xq1["key"] else [], 1, False))
    monkeypatch.setattr(assistant.ask_model, "read_pick", lambda q, c: (next(x["number"] for x in c if "retailers" in x["text"]), 0.5))
    shown = {"q14": {**q14}}   # found by its words alone ("cutting back on dining out" went to "why spend less on clothing?")
    monkeypatch.setattr(index, "retrieve", lambda *a, **k: [{**xq1, "near": 0.80}, shown["q14"]])
    question = "What share bought from Amazon in the latest wave?"   # lacking (above) says XQ1 misses "worry"
    assert assistant.answer(question, index, EVERYONE, quick=True)["sources"][0]["qcode"] == "XQ1"
    shown["q14"] = {**q14, "near": 0.79}   # found by meaning, within NEAR_SWAP: it uses every specific word
    assert assistant.answer(question, index, EVERYONE, quick=True)["sources"][0]["qcode"] == "Q14"
    shown["q14"] = {**q14, "near": 0.70}   # much further: the reader's pick stands
    assert assistant.answer(question, index, EVERYONE, quick=True)["sources"][0]["qcode"] == "XQ1"


def test_how_a_change_is_asked_is_not_the_subject(index):
    key = "CSI-US/tracker/XQ1"   # "gas prices affecting consumer spending", "Walmart gaining or losing shoppers"
    assert assistant.unasked({"about": "amazon affecting consumer"}, key, index) == []
    assert assistant.unasked({"about": "walmart gaining losing"}, key, index) == []


def test_respondents_of_one_week_are_never_followed_into_another(index):
    for question in ("Which respondents in the 9 Nov survey also answered the 16 Nov survey?",   # hard set H129
                     "Which of the 9 Nov respondents also answered on 2 Nov?"):                    # held-out-2 Y029
        found = assistant.answer(question, index, EVERYONE)
        assert found["mode"] == "none" and found["answer"].startswith("Each week's survey asks different people")
    assert not assistant.FOLLOWED.search("who also answered yes to q5?")   # an answer, not another week
    assert not assistant.FOLLOWED.search("which retailers did gen z also shop at?")


def test_a_weekly_question_opens_by_month_and_others_by_survey():
    from datetime import date, timedelta
    weeks = [str(date(2026, 1, 5) + timedelta(weeks=i)) for i in range(16)]   # 16 weekly surveys, January to April
    assert ask_figures.auto_grain(list(range(16)), weeks) == "month"
    assert ask_figures.auto_grain(list(range(8)), weeks) == "wave"             # two months only: each survey
    months = [f"{2024 + i // 12}-{i % 12 + 1:02d}-01" for i in range(20)]   # monthly surveys: each survey while readable
    assert ask_figures.auto_grain(list(range(20)), months) == "wave"
    years = [str(date(2021, 1, 4) + timedelta(weeks=i)) for i in range(260)]  # five years of weeks: still by month
    assert ask_figures.auto_grain(list(range(260)), years) == "month"
