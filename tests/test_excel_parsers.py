"""Parser unit tests. Point CSI_TEST_RAW / CSI_TEST_XTAB at real exports to run
the integration assertions; without them the pure-function tests still run.

    pytest tests/
"""
from __future__ import annotations

import os

import pytest

from etl import excel_parsers as xp
from etl.loaders import classify_group, short_label

RAW = os.getenv("CSI_TEST_RAW")
XTAB = os.getenv("CSI_TEST_XTAB")
# These assertions are facts of the 09/21/26 questionnaire (DP, BN, GP modules).
WAVE_0921 = pytest.mark.skipif(
    "09_21_26" not in f"{RAW}{XTAB}", reason="asserts the 09/21/26 modules")


def test_normalise_label_cell():
    assert xp.normalise_label_cell("NO TO: Gone to a bar") == (0, "Gone to a bar")
    assert xp.normalise_label_cell("Gone to a bar") == (1, "Gone to a bar")
    assert xp.normalise_label_cell(None) == (None, None)
    assert xp.normalise_label_cell("  ") == (None, None)


def test_classify_group():
    """Topic rules are per survey family — see config/survey_map.yml."""
    assert classify_group("DP4", family="CSI-US") == "DEPT_STORES"
    assert classify_group("BN7", family="CSI-US") == "BNPL"
    assert classify_group("GP10", family="CSI-US") == "GLP1"
    assert classify_group("D31", family="CSI-US") == "AI_GENAI"
    assert classify_group("D5", family="CSI-US") == "DEMOGRAPHICS"
    assert classify_group("CS1", family="CSI-US") == "SENTIMENT"
    # technical variables are recognised whatever the survey
    assert classify_group("qtime") == "TECHNICAL"


def test_short_label():
    assert short_label("a  b\n c") == "a b c"
    assert len(short_label("x" * 500, 120)) == 120


@pytest.mark.skipif(not RAW, reason="set CSI_TEST_RAW")
@WAVE_0921
def test_parse_datamap_real_file():
    questions = xp.parse_datamap(RAW)
    codes = {q.qcode for q in questions}
    assert {"q1", "DP7", "BN1", "GP6", "D5"} <= codes
    q1 = next(q for q in questions if q.qcode == "q1")
    assert q1.is_multi and len(q1.rows) >= 15


@pytest.mark.skipif(not XTAB, reason="set CSI_TEST_XTAB")
def test_parse_crosstab_real_file():
    settings, defs = xp.parse_crosstab_summary(XTAB)
    assert settings.get("Percentage Base")
    assert any(d.label == "Total" for d in defs)
    segments = xp.parse_banner(XTAB)
    assert len(segments) >= 30
    cells = list(xp.iter_crosstab_cells(XTAB, segments))
    assert len(cells) > 1000


def test_answer_base_recovery():
    """count / pct recovers the denominator Forsta actually divided by."""
    assert xp._answer_base(16, 0.07207207) == 222   # DP2, department-store buyers
    assert xp._answer_base(46, 0.34586466) == 133   # BN2, BNPL users
    assert xp._answer_base(16, 0.22535211) == 71    # GP8, GLP-1 users
    # unrecoverable at 0% — must be None, never the segment size
    assert xp._answer_base(0, 0.0) is None
    assert xp._answer_base(None, 0.5) is None


@pytest.mark.skipif(not XTAB, reason="set CSI_TEST_XTAB")
@WAVE_0921
def test_routed_questions_have_their_own_base():
    """Routed questions must not inherit the 404 segment size."""
    segments = xp.parse_banner(XTAB)
    cells = [c for c in xp.iter_crosstab_cells(XTAB, segments)
             if c["seg_label"] == "Total" and c["stub_type"] == "item"]
    bases = {}
    for c in cells:
        if c["answer_base_n"]:
            bases.setdefault(c["qcode"], set()).add(c["answer_base_n"])
    assert bases["q1"] == {404}     # asked of everyone
    assert bases["DP2"] == {222}    # department-store buyers
    assert bases["BN2"] == {133}    # BNPL users
    assert bases["GP8"] == {71}     # GLP-1 users
    assert bases["DJ3"] == {186}
    assert bases["D15"] == {260}
    # every cell still reports the segment size separately
    assert {c["segment_base_n"] for c in cells} == {404}


@pytest.mark.skipif(not XTAB, reason="set CSI_TEST_XTAB")
@WAVE_0921
def test_grid_questions_keep_one_row_per_item_and_scale_point():
    """DP7 rates 9 retailers on a 5-point scale; GP6 rates 21 categories on 4.

    Forsta prints these as a run of sub-tables, so the scale labels repeat.
    Keyed on the stub alone they collide and most rows are lost.
    """
    segments = xp.parse_banner(XTAB)
    cells = [c for c in xp.iter_crosstab_cells(XTAB, segments) if c["seg_label"] == "Total"]
    by_q = {}
    for c in cells:
        by_q.setdefault(c["qcode"], []).append(c)

    assert len(by_q["DP7"]) == 9 * 5
    assert len({c["item_label"] for c in by_q["DP7"]}) == 9
    assert len(by_q["GP6"]) == 21 * 4
    assert len({c["item_label"] for c in by_q["GP6"]}) == 21
    # a flat question has no sub-items
    assert {c["item_label"] for c in by_q["q1"]} == {None}


@pytest.mark.skipif(not XTAB, reason="set CSI_TEST_XTAB")
@WAVE_0921
def test_grid_items_carry_their_own_base():
    """Only people who shop a retailer rate it, so each row has its own base."""
    segments = xp.parse_banner(XTAB)
    cells = [c for c in xp.iter_crosstab_cells(XTAB, segments)
             if c["qcode"] == "DP7" and c["seg_label"] == "Total"]
    bases = {c["item_label"]: c["answer_base_n"] for c in cells if c["answer_base_n"]}
    assert bases["Bergdorf Goodman"] == 16
    assert bases["Bloomingdale's"] == 22
    assert max(bases.values()) < 404      # never the wave base


def test_clean_text_folds_non_breaking_spaces():
    """The 09/28 datamap labels HX1 'Spent\xa0a lot less…'; the raw export uses
    a normal space. Unfolded, 333 of 403 HX1 answers loaded with no code."""
    assert xp.clean_text("Spent\xa0a lot  less\n") == "Spent a lot less"
    assert xp.normalise_label_cell("NO TO:\xa0Gone to a bar") == (0, "Gone to a bar")
