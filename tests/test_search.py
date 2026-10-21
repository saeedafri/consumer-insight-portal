"""Question search (api/search.py): typos, synonyms, answer labels and partial words all find the question."""
from api.search import SearchIndex

DOCS = [
    {"qcode": "XM3", "text": "What is the current status of your holiday shopping?", "answers": "Not yet started · Still shopping",
     "titles": "Shopping and Spending + Holiday Tracker", "last": "2026-10-12"},
    {"qcode": "XM2", "text": "From which retailers did you make holiday-related purchases?", "answers": "Walmart · Amazon · Target",
     "titles": "Holiday Tracker", "last": "2026-10-12"},
    {"qcode": "BN2", "text": "Have you used buy now pay later services in the past month?", "answers": "Yes · No",
     "titles": "Financial health", "last": "2026-06-01"},
    {"qcode": "D14", "text": "Have higher gasoline prices prompted you to reduce your spending?", "answers": "Yes · No",
     "titles": "Macro and Gas Prices", "last": "2026-10-12"},
]
SYNONYMS = [["holiday", "christmas", "gift"], ["bnpl", "buy now pay later", "klarna"], ["gas", "gasoline", "fuel"]]
index = SearchIndex(DOCS, SYNONYMS)
codes = lambda q: [d["qcode"] for d in index.search(q)["results"]]


def test_words_stems_and_codes():
    assert codes("shopping status")[0] == "XM3"
    assert codes("retailer purchases") == ["XM2"]          # porter stem: retailers, purchases
    assert codes("xm3") == ["XM3"]


def test_typos_are_corrected_and_reported():
    found = index.search("holidy shoping")
    assert found["results"][0]["qcode"] == "XM3"
    assert "holidy → holiday" in found["understood"]["corrected"]


def test_synonyms_and_phrases():
    assert set(codes("christmas")) == {"XM3", "XM2"}
    assert codes("klarna") == ["BN2"]                       # phrase synonym: buy now pay later
    assert codes("fuel prices") == ["D14"]


def test_answer_labels_partial_words_and_nothing():
    assert codes("walmart") == ["XM2"]
    assert codes("gasol")[0] == "D14"                       # prefix / fragment
    assert index.search("zzzz qqqq")["results"] == []
    assert index.search('"; DROP TABLE words; --')["results"] == []   # operators in user text are harmless
