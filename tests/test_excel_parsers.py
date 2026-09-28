"""Parser unit tests. Point CIP_TEST_RAW / CIP_TEST_XTAB at real exports to run
the integration assertions; without them the pure-function tests still run.

    pytest tests/
"""
from __future__ import annotations

import os

import pytest

from etl import excel_parsers as xp
from etl.loaders import classify_group, short_label

RAW = os.getenv("CIP_TEST_RAW")
XTAB = os.getenv("CIP_TEST_XTAB")


def test_normalise_label_cell():
    assert xp.normalise_label_cell("NO TO: Gone to a bar") == (0, "Gone to a bar")
    assert xp.normalise_label_cell("Gone to a bar") == (1, "Gone to a bar")
    assert xp.normalise_label_cell(None) == (None, None)
    assert xp.normalise_label_cell("  ") == (None, None)


def test_classify_group():
    assert classify_group("DP4") == "DEPT_STORES"
    assert classify_group("BN7") == "BNPL"
    assert classify_group("GP10") == "GLP1"
    assert classify_group("D31") == "AI_GENAI"
    assert classify_group("D5") == "DEMOGRAPHICS"
    assert classify_group("CS1") == "SENTIMENT"
    assert classify_group("qtime") == "PARADATA"


def test_short_label():
    assert short_label("a  b\n c") == "a b c"
    assert len(short_label("x" * 500, 120)) == 120


@pytest.mark.skipif(not RAW, reason="set CIP_TEST_RAW")
def test_parse_datamap_real_file():
    questions = xp.parse_datamap(RAW)
    codes = {q.qcode for q in questions}
    assert {"q1", "DP7", "BN1", "GP6", "D5"} <= codes
    q1 = next(q for q in questions if q.qcode == "q1")
    assert q1.is_multi_punch and len(q1.rows) >= 15


@pytest.mark.skipif(not XTAB, reason="set CIP_TEST_XTAB")
def test_parse_crosstab_real_file():
    settings, defs = xp.parse_crosstab_summary(XTAB)
    assert settings.get("Percentage Base")
    assert any(d.label == "Total" for d in defs)
    segments = xp.parse_banner(XTAB)
    assert len(segments) >= 30
    cells = list(xp.iter_crosstab_cells(XTAB, segments))
    assert len(cells) > 1000
