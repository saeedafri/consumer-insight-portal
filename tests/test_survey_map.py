"""The survey-agnostic layer: a new wave must load without a code change."""
from __future__ import annotations

from types import SimpleNamespace

from etl import survey_map as sm


def Q(qcode, qtext=""):
    return SimpleNamespace(qcode=qcode, qtext=qtext)


# ── topics ─────────────────────────────────────────────────────────────────
def test_known_questionnaire_classifies_by_code():
    assert sm.classify_topic("DP4", family="CSI-US") == "DEPT_STORES"
    assert sm.classify_topic("BN7", family="CSI-US") == "BNPL"
    assert sm.classify_topic("GP10", family="CSI-US") == "GLP1"
    assert sm.classify_topic("D31", family="CSI-US") == "AI_GENAI"
    assert sm.classify_topic("CS1", family="CSI-US") == "SENTIMENT"


def test_technical_variables_are_flagged_for_any_survey():
    for code in ("record", "uuid", "qtime", "vdropout", "vqtable1"):
        assert sm.classify_topic(code, family="ANYTHING") == "TECHNICAL"
        assert sm.is_technical(sm.classify_topic(code))


def test_unknown_module_falls_back_rather_than_failing():
    """A module nobody has written a rule for must still load."""
    assert sm.classify_topic("ZZ9", "Do you own a pet iguana?", family="NEW-SURVEY") \
        == "UNCLASSIFIED"


def test_wording_rescues_a_renamed_demographic():
    """Even with an unrecognised code, the wording routes it sensibly."""
    assert sm.classify_topic("X99", "What is your gender?", family="NEW-SURVEY") \
        == "DEMOGRAPHICS"


# ── demographic resolution ─────────────────────────────────────────────────
def test_profile_map_uses_config_for_a_known_family():
    questions = [Q("D1", "What is your gender?"), Q("D5", "What was your total household income last year?")]
    resolved = sm.resolve_profile_map(questions, family="CSI-US")
    assert resolved["gender"] == "D1"
    assert resolved["income_band"] == "D5"


def test_profile_map_auto_detects_for_an_unknown_family():
    """Different codes, same questions — the wording is enough."""
    questions = [Q("GEN", "What is your gender?"),
                 Q("INC", "What was your total household income last year?"),
                 Q("AGE", "What is your age?")]
    resolved = sm.resolve_profile_map(questions, family="SOMETHING-NEW")
    assert resolved == {"gender": "GEN", "income_band": "INC", "age": "AGE"}


def test_profile_map_omits_what_it_cannot_find():
    resolved = sm.resolve_profile_map([Q("Z1", "Do you like cheese?")], family="NEW")
    assert resolved == {}


# ── derived values ─────────────────────────────────────────────────────────
def test_age_bands_and_generations():
    assert sm.age_band(25) == "18-29"
    assert sm.age_band(52) == "45-60"
    assert sm.generation(25) == "GenZ"
    assert sm.generation(35) == "Millennial"
    assert sm.generation(70) == "Boomer"
    assert sm.age_band(None) is None


def test_census_region_accepts_codes_and_names():
    assert sm.census_region("CT") == "Northeast"
    assert sm.census_region("Connecticut") == "Northeast"
    assert sm.census_region("tx") == "South"
    assert sm.census_region("Nowhere") is None


def test_parse_age_handles_label_formats():
    assert sm.parse_age("34") == 34
    assert sm.parse_age("Under 18") == 17   # under-age, outside every band
    assert sm.parse_age(None) is None
    assert sm.parse_age("Prefer not to say") is None
