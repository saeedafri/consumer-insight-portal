"""Phase 5: publications (frozen numbers) and the drift report.

See docs/superpowers/plans/2026-10-01-publications-phase5.md.
"""
from __future__ import annotations

import pytest
import sqlalchemy as sa

from app.data import cube, publications
from tests.test_phase3 import legacy  # noqa: F401  (pytest fixture)
from tests.test_phase4 import wave  # noqa: F401  (pytest fixture: B1 = Q1, B10 = Q2)


def definition(concept, **extra):
    return {"concept": concept, "waves": ["2025-02-17"], "cohort": None, "cut": "total",
            "pooled": True, "min_base": 0, **extra}


def as_map(cells):
    return {(c["row_key"], c["col_key"]): c for c in cells}


def test_a_pooled_publication_freezes_share_base_and_midpoint_averages(wave):  # noqa: F811
    engine, sid, b1, _ = wave
    cube.build_cube(sid)
    cells = as_map(publications.compute(definition(b1)))
    yes = cells[("Yes", "Total|pct")]
    assert (yes["n"], yes["base_n"], round(yes["value"], 6)) == (2, 3, round(2 / 3, 6))
    assert cells[("Yes", "Total|avg_age")]["value"] == pytest.approx((23.5 + 67.0) / 2)
    assert ("No", "Total|pct") in cells


def test_a_per_wave_publication_has_one_cell_per_wave(wave):  # noqa: F811
    engine, sid, b1, _ = wave
    cube.build_cube(sid)
    cells = as_map(publications.compute(definition(b1, pooled=False)))
    assert set(cells) == {("Yes", "2025-02-17|pct"), ("No", "2025-02-17|pct")}


def test_cells_under_the_minimum_base_are_suppressed(wave):  # noqa: F811
    engine, sid, b1, _ = wave
    cube.build_cube(sid)
    cells = publications.compute(definition(b1, min_base=30))
    assert cells and all(c["value"] is None for c in cells)


def test_a_definition_naming_what_does_not_exist_is_refused(wave):  # noqa: F811
    engine, sid, b1, _ = wave
    with pytest.raises(ValueError, match="NOPE"):
        publications.compute(definition("NOPE"))
    with pytest.raises(ValueError, match="2031-01-01"):
        publications.compute(definition(b1, waves=["2031-01-01"]))


def test_publishing_again_is_a_new_version_and_the_old_one_stays(wave):  # noqa: F811
    engine, sid, b1, _ = wave
    cube.build_cube(sid)
    first = publications.publish("BEAUTY_BOUGHT", "Bought beauty", definition(b1))
    second = publications.publish("BEAUTY_BOUGHT", "Bought beauty", definition(b1))
    listed = publications.list_publications()
    assert first != second and sorted(listed[listed.pub_code == "BEAUTY_BOUGHT"].version) == [1, 2]
    assert len(publications.cells(first)) == len(publications.cells(second)) > 0


def test_the_footnote_names_the_base_and_the_fieldwork_period(wave):  # noqa: F811
    engine, sid, b1, _ = wave
    cube.build_cube(sid)
    pid = publications.publish("BEAUTY_BOUGHT", "Bought beauty", definition(b1))
    note = publications.list_publications().set_index("publication_id").loc[pid, "footnote"]
    assert note == ("Base: 3 US respondents aged 18+, surveyed February 2025; 3 answered. "
                    "Averages use range midpoints. Source: Coresight Research.")


def status(frame):
    return dict(zip(zip(frame.row_key, frame.col_key), frame.status))


def test_unchanged_data_drifts_nowhere(wave):  # noqa: F811
    engine, sid, b1, _ = wave
    cube.build_cube(sid)
    pid = publications.publish("BEAUTY_BOUGHT", "Bought beauty", definition(b1))
    assert set(publications.drift(pid).status) == {"same"}


def test_a_changed_answer_is_flagged_moved_and_a_vanished_one_missing(wave):  # noqa: F811
    engine, sid, b1, _ = wave
    cube.build_cube(sid)
    pid = publications.publish("BEAUTY_BOUGHT", "Bought beauty", definition(b1))
    with engine.begin() as conn:            # R_3's "No" is withdrawn from the data
        conn.execute(sa.text("DELETE FROM cip_answer WHERE survey_id = :s AND value_code = 2 AND field_id ="
                             " (SELECT field_id FROM cip_field WHERE survey_id = :s AND field_name = 'Q1')"), {"s": sid})
    cube.build_cube(sid)
    report = publications.drift(pid)
    moved = report.set_index(["row_key", "col_key"]).loc[("Yes", "Total|pct")]
    assert moved.status == "moved" and round(moved.published, 4) == round(2 / 3, 4) and moved.now == 1.0
    assert status(report)[("No", "Total|pct")] == "missing"


def test_a_cell_that_did_not_exist_when_published_is_new(wave):  # noqa: F811
    engine, sid, b1, _ = wave
    cube.build_cube(sid)
    pid = publications.publish("BEAUTY_BOUGHT", "Bought beauty", definition(b1))
    with engine.begin() as conn:
        conn.execute(sa.text("DELETE FROM cip_publication_cell WHERE publication_id = :p AND row_key = 'No'"), {"p": pid})
    assert status(publications.drift(pid))[("No", "Total|pct")] == "new"


def test_suppressed_cells_stay_quiet(wave):  # noqa: F811
    engine, sid, b1, _ = wave
    cube.build_cube(sid)
    pid = publications.publish("BEAUTY_BOUGHT", "Bought beauty", definition(b1, min_base=30))
    assert set(publications.drift(pid).status) == {"same"}


def test_drift_reports_a_definition_that_no_longer_resolves(wave):  # noqa: F811
    engine, sid, b1, _ = wave
    cube.build_cube(sid)
    pid = publications.publish("BEAUTY_BOUGHT", "Bought beauty", definition(b1))
    with engine.begin() as conn:
        conn.execute(sa.text("UPDATE cip_survey SET wave_label = '2025-02-18' WHERE survey_id = :s"), {"s": sid})
    report = publications.drift(pid)
    assert list(report.status) == ["error"] and "2025-02-17" in report.detail.iloc[0]


def test_the_summary_counts_moved_cells_per_publication(wave):  # noqa: F811
    engine, sid, b1, _ = wave
    cube.build_cube(sid)
    publications.publish("BEAUTY_BOUGHT", "Bought beauty", definition(b1))
    summary = publications.drift_summary()
    assert summary.set_index("pub_code").loc["BEAUTY_BOUGHT", ["moved", "missing", "new"]].tolist() == [0, 0, 0]


def test_the_footnote_names_the_cohort_by_its_own_name(wave):  # noqa: F811
    from app.data import cohorts
    engine, sid, b1, _ = wave
    cohorts.define_cohort("BEAUTY_YES", "Beauty shoppers", {"concept": b1, "option": "yes"})
    cube.refresh_wave(sid)
    note = publications.footnote(definition(b1, cohort="BEAUTY_YES"))
    assert "2 beauty shoppers answered." in note


def test_an_unchanged_cell_shows_no_change_not_float_noise(wave):  # noqa: F811
    engine, sid, b1, _ = wave
    cube.build_cube(sid)
    pid = publications.publish("BEAUTY_BOUGHT", "Bought beauty", definition(b1))
    assert set(publications.drift(pid).delta.dropna()) == {0.0}


# ── final-review fixes ─────────────────────────────────────────────────────
def rename_option(engine, concept_code, old, new):
    with engine.begin() as conn:
        conn.execute(sa.text("UPDATE cip_concept_option SET option_label = :new WHERE option_label = :old AND concept_id ="
                             " (SELECT concept_id FROM cip_concept WHERE concept_code = :c)"),
                     {"new": new, "old": old, "c": concept_code})


def test_a_long_answer_label_does_not_drift_on_unchanged_data(wave):  # noqa: F811
    engine, sid, b1, _ = wave
    rename_option(engine, b1, "Yes", "Yes, " + "and more " * 40)
    cube.build_cube(sid)
    pid = publications.publish("LONG", "Long label", definition(b1))
    assert set(publications.drift(pid).status) == {"same"}


def test_two_answers_with_the_same_label_are_refused_by_name(wave):  # noqa: F811
    engine, sid, b1, _ = wave
    rename_option(engine, b1, "No", "YES")
    cube.build_cube(sid)
    with pytest.raises(ValueError, match="YES"):
        publications.publish("DUP", "Duplicate labels", definition(b1))


def test_a_monthly_wave_label_still_gets_a_footnote(wave):  # noqa: F811
    engine, sid, b1, _ = wave
    with engine.begin() as conn:
        conn.execute(sa.text("UPDATE cip_survey SET wave_label = '2025-02' WHERE survey_id = :s"), {"s": sid})
    cube.build_cube(sid)
    assert "surveyed February 2025" in publications.footnote(definition(b1, waves=["2025-02"]))


def test_the_footnote_gives_the_table_base_not_only_the_sample(wave):  # noqa: F811
    from app.data import cohorts
    engine, sid, b1, _ = wave
    cohorts.define_cohort("BEAUTY_YES", "Beauty shoppers", {"concept": b1, "option": "yes"})
    cube.refresh_wave(sid)
    note = publications.footnote(definition(b1, cohort="BEAUTY_YES"))
    assert note.startswith("Base: 3 US respondents aged 18+, surveyed February 2025; 2 beauty shoppers answered.")


def test_averages_of_a_tiny_group_are_suppressed_and_hidden_counts_are_blank(wave):  # noqa: F811
    engine, sid, b1, _ = wave
    cube.build_cube(sid)
    cells = as_map(publications.compute(definition(b1, min_base=2)))        # base 3 ≥ 2, but "No" was 1 person
    assert cells[("No", "Total|avg_age")]["value"] is None
    assert cells[("Yes", "Total|avg_age")]["value"] is not None
    suppressed = as_map(publications.compute(definition(b1, min_base=30)))
    assert all(c["n"] is None for c in suppressed.values())


def test_a_code_already_used_by_another_publication_is_refused(wave):  # noqa: F811
    engine, sid, b1, _ = wave
    cube.build_cube(sid)
    publications.publish("BEAUTY_Q1", "Beauty — Q1", definition(b1))
    with pytest.raises(ValueError, match="already"):
        publications.publish("BEAUTY_Q1", "Beauty Q1", definition(b1))
    with pytest.raises(ValueError, match="code"):
        publications.publish("", "(no letters)", definition(b1))
