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
    assert "170 of 400" in found["answer"] and found["chart"]["type"] in ("bar", "donut")


def test_a_month_pools_its_waves_exactly(index):
    found = assistant.answer("Amazon retailers bought in October 2026", index, EVERYONE)
    assert figure(found, "Amazon") == [round(100 * sum(AMAZON[4:]) / 1600, 1)]  # four October waves: 620 of 1,600


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


def test_a_reused_code_is_two_questions_each_with_its_own_answers(index):
    work = assistant.answer("allowed to use generative AI tools at work", index, EVERYONE)
    save = assistant.answer("ways to save money", index, EVERYONE)
    assert work["sources"][0]["key"] != save["sources"][0]["key"]
    assert [r[0] for r in work["table"]["rows"]] == ["Yes", "No"] and figure(work, "Yes") == [20.0]
    assert [r[0] for r in save["table"]["rows"]] == ["Coupons", "Store brands"]


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
    assert "among GenZ" in found["answer"] and figure(found, "Amazon") == [85.0]


def test_an_empty_index_is_built_again(tmp_path, index):
    assistant.INDEX.update(version="v", index=Index(tmp_path / "nothing", []))   # built before a deploy restored the files
    assert assistant.index_for(index.root, "v", []).docs == {}                   # still nothing there: still empty
    assert assistant.index_for(index.root, "v", [{"survey_id": 100 + i, "wave_date": d, "title": "", "modules": []}
                                                for i, d in enumerate(DATES)]).docs


def test_a_question_not_asked_then_never_borrows_an_unrelated_one(index):
    found = assistant.answer("ways to save money in October 2026", index, EVERYONE)   # Q14 asked only in September
    assert found["mode"] == "none" and "was not asked in the period" in found["answer"]


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


def test_an_analysts_ask_brings_its_question_nearer(index):
    """Retrieval joins a question's own closeness with its nearest ask's (ASK_WEIGHT): 0.7 × 0.5 + 0.3 × 1.0 = 0.65
    beats 0.7 × 0.6 + 0.3 × 0.6 = 0.60."""
    import numpy as np
    keys = list(index.docs)[:2]
    index.vector_keys, index.area_vectors = keys, None
    index.vectors = np.array([[0.5, 0.866], [0.6, 0.8]], np.float32)       # closeness to (1, 0): 0.5 and 0.6
    index.ask_vectors, index.ask_owner = np.array([[1.0, 0.0]], np.float32), np.array([0], np.int32)   # an ask of the first, 1.0
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
    assistant.LEARNED.write_text(json.dumps([{k: v for k, v in saved.items() if k != "key"}]))
    index.load_verified()
    assert not any(v.get("learned") for v in index.verified)   # a learned entry without its key is never guessed from its code


def test_a_learned_answer_gives_way_to_a_sure_reader_and_stands_for_an_unsure_one(index, monkeypatch):
    if index.vectors is None:
        pytest.skip("search model not downloaded (deploy/ask-model-download.py)")
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


def test_a_misspelt_retailer_is_put_right_and_other_words_are_left_alone(tmp_path, index, monkeypatch):
    from api import ask_index
    monkeypatch.setattr(ask_index, "BRAND_WAVES", 8)   # the test retailer list has 8 waves; the real ones 15 or more
    waves = [{"survey_id": 100 + i, "wave_date": d, "title": "Shopping and Spending", "modules": []} for i, d in enumerate(DATES)]
    again = Index(tmp_path / "questions", waves)
    assert again.brand_words == ["amazon", "walmart"]   # the retailer list's answers, not Q14's (no "retailer" in its wording)
    assert again.correct_spelling("Walmrt shoppers") == "Walmart shoppers"
    assert again.correct_spelling("What share bought from Amazon in the latest wave?") == "What share bought from Amazon in the latest wave?"


def test_a_retailer_and_a_time_alone_is_the_retailer_list_even_when_the_ai_picks_a_question_naming_it(tmp_path, index, monkeypatch):
    if index.vectors is None:
        pytest.skip("search model not downloaded (deploy/ask-model-download.py)")
    (tmp_path / "questions" / "CSI-US" / "tracker" / "PM1.json.gz").write_bytes(gzip.compress(json.dumps(question_file(
        [[107, DATES[7], 1]], ["Do you have an Amazon Prime membership?"], [["", 1, "Yes"], ["", 2, "No"]],
        [["total", "Total"]], [(0, 0, 0, 120, 400), (0, 0, 1, 280, 400)])).encode()))
    waves = [{"survey_id": 100 + i, "wave_date": d, "title": "Shopping and Spending", "modules": []} for i, d in enumerate(DATES)]
    again = Index(tmp_path / "questions", waves)
    again.add_vectors()
    monkeypatch.setattr(assistant, "TREND_FROM", 1)   # XQ1's 8 waves count as long-running (the real lists: 195)
    monkeypatch.setattr(assistant.ask_model, "ready", lambda: True)
    monkeypatch.setattr(assistant.ask_model, "plan", lambda q, c: {   # the AI picks the question with Amazon in its wording
        "pick": next(x["number"] for x in c if "Prime" in x["text"]), "alt": None, "focus": [], "kind": "share",
        "grain": "auto", "cut": "none", "period": "all"})
    assert assistant.answer("Amazon in October 2026", again, EVERYONE)["sources"][0]["qcode"] == "XQ1"
    assert assistant.answer("How many have Amazon Prime?", again, EVERYONE)["sources"][0]["qcode"] == "PM1"


def test_the_reader_scores_none_of_these_as_zero_and_gives_its_lead(monkeypatch):
    from api import ask_model

    class Words:   # the tokenizer's shape: ids, mask and type ids for each pair
        def encode_batch(self, pairs):
            return [type("Coded", (), {"ids": [1, 2], "attention_mask": [1, 1], "type_ids": [0, 1]})() for _ in pairs]

    class Session:
        def __init__(self, logits):
            self.logits = logits

        def run(self, names, feed):
            return [np.array(self.logits, np.float32).reshape(-1, 1)]

    candidates = [{"number": n, "text": t, "name": "", "waves": 9, "first": "2024-01-01", "last": "2026-11-01", "answers": []}
                  for n, t in ((4, "a"), (7, "b"))]
    monkeypatch.setattr(ask_model, "reader", lambda: (Words(), Session([1.0, 3.5]), {}))
    assert ask_model.read_pick("q", candidates) == (7, pytest.approx(2.5))   # its number, ahead of the next by 2.5
    monkeypatch.setattr(ask_model, "reader", lambda: (Words(), Session([-1.0, -3.0]), {}))
    assert ask_model.read_pick("q", candidates) == (None, pytest.approx(1.0))   # both under "none of these" (0)


def test_dont_know_with_a_curly_apostrophe_is_left_out_like_a_straight_one():
    # survey files spell it both ways; the curly one was ranked as an answer and read as a specific answer (13 Nov 2026)
    assert assistant.SKIP.match("Don’t know") and assistant.GENERIC.match("Don’t know / not sure")
