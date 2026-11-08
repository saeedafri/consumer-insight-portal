"""Ask CIP (api/assistant.py): answers only from cited portal figures; abstains without a source."""
import json
from types import SimpleNamespace

from api import assistant

BOOK = {"wave": {"wave_date": "2023-12-04", "title": "Shopping and Spending - inc Footwear"},
        "questions": [{"id": "Q13", "text": "Did you do any shopping on Cyber Monday this year?",
                       "groups": [{"label": "", "base": 400, "rows": [{"label": "Yes", "Total": 47.5}, {"label": "No", "Total": 52.5}]}]},
                      {"id": "Q99", "text": "Tiny question", "groups": [{"label": "", "base": 12, "rows": [{"label": "Yes", "Total": None}]}]}]}
search = lambda q, n: {"results": [{"survey_id": 135, "qcode": "Q13", "waves": 1}, {"survey_id": 135, "qcode": "Q99", "waves": 1}]
                       if "cyber" in q.lower() else []}   # noqa: E731


class Claude:
    def __init__(self, reply=None, error=None):
        self.reply, self.error, self.sent = reply, error, []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self.create))

    def create(self, **request):
        self.sent.append(request)
        if self.error:
            raise self.error
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=json.dumps(self.reply))])


def test_claude_answers_from_cited_sources_and_unknown_citations_are_dropped():
    claude = Claude({"answer": "47.5% shopped on Cyber Monday [S1].", "cited": ["S1", "S9"], "no_source": False})
    out = assistant.ask("Who shopped on Cyber Monday?", search, lambda sid: BOOK, client=claude)
    assert out["mode"] == "claude" and [s["id"] for s in out["sources"]] == ["S1"]
    sent = claude.sent[0]["messages"][0]["content"]
    assert "Yes: 47.5%" in sent and "Tiny question" not in sent          # groups under 30 are never sent or quoted


def test_an_answer_without_a_real_source_is_not_given():
    out = assistant.ask("Cyber Monday?", search, lambda sid: BOOK, client=Claude({"answer": "Probably most people.", "cited": [], "no_source": False}))
    assert out["no_source"] and out["sources"] == []


def test_without_claude_the_cited_figures_are_the_answer_and_nothing_matching_abstains():
    out = assistant.ask("cyber monday shopping", search, lambda sid: BOOK, client=Claude(error=RuntimeError("no credentials")))
    assert out["mode"] == "figures" and out["answer"] == "Q13 (2023-12-04, n=400): No 52.5%; Yes 47.5% [S1]"
    assert assistant.ask("weather in Paris", search, lambda sid: BOOK)["mode"] == "none"


def test_a_loose_search_match_that_shares_no_topic_word_is_not_a_source():
    anything = lambda q, n: search("cyber", n)   # noqa: E731  the search's fragment fallback returns something for any text
    assert assistant.ask("What is the weather on Mars?", anything, lambda sid: BOOK)["mode"] == "none"
    assert assistant.ask("How many people shopped on Cyber Monday?", anything, lambda sid: BOOK,
                         client=Claude(error=RuntimeError("no credentials")))["sources"][0]["qcode"] == "Q13"


def test_a_percentage_no_cited_source_lists_is_not_given():
    wrong = Claude({"answer": "Most people (62%) shopped on Cyber Monday [S1].", "cited": ["S1"], "no_source": False})
    out = assistant.ask("Who shopped on Cyber Monday?", search, lambda sid: BOOK, client=wrong)
    assert out["mode"] == "figures" and "62%" not in out["answer"] and "Yes 47.5%" in out["answer"]
    rounded = Claude({"answer": "About 48% shopped on Cyber Monday [S1].", "cited": ["S1"], "no_source": False})
    assert assistant.ask("Who shopped on Cyber Monday?", search, lambda sid: BOOK, client=rounded)["mode"] == "claude"
    thousands = Claude({"answer": "1,200% more shoppers [S1].", "cited": ["S1"], "no_source": False})
    assert assistant.ask("Who shopped on Cyber Monday?", search, lambda sid: BOOK, client=thousands)["mode"] == "figures"
    everyone = Claude({"answer": "47.5% said yes, out of 100% of respondents [S1].", "cited": ["S1"], "no_source": False})
    assert assistant.ask("Who shopped on Cyber Monday?", search, lambda sid: BOOK, client=everyone)["mode"] == "claude"


def test_claude_is_asked_with_a_timeout_shorter_than_nginx_waits(monkeypatch):
    made = {}
    monkeypatch.setattr("anthropic.Anthropic", lambda **kw: made.update(kw) or Claude({"answer": "47.5% [S1]", "cited": ["S1"], "no_source": False}))
    assistant.ask("Who shopped on Cyber Monday?", search, lambda sid: BOOK)
    assert made == {"timeout": 25, "max_retries": 0}   # one try: deploy/cip_proxy.conf gives up at 30 s
