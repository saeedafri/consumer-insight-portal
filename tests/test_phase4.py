"""Phase 4: cohorts (Deriver), cube (Aggregator), cube-first repository.

See docs/superpowers/plans/2026-10-01-cohorts-and-cube-phase4.md.
"""
from __future__ import annotations

import sqlalchemy as sa


def columns(engine, table):
    return {c["name"] for c in sa.inspect(engine).get_columns(table)}


def test_cube_cells_carry_their_map_key_and_midpoint_counts(csi_db):
    assert {"map_key", "n_age_mid", "n_income_mid"} <= columns(csi_db, "cip_agg_cell")
    assert "ix_agg_map" in {i["name"] for i in sa.inspect(csi_db).get_indexes("cip_agg_cell")}


import pytest

from app.data import cohorts, harmonise
from etl import legacy_dwh
from tests.test_phase3 import legacy  # noqa: F401  (pytest fixture: the Phase 3 legacy wave)


def concept_code(engine, sid, qcode):
    with engine.connect() as conn:
        return conn.execute(sa.text(
            "SELECT c.concept_code FROM cip_concept c JOIN cip_concept_map m ON m.concept_id = c.concept_id"
            " JOIN cip_question q ON q.question_id = m.question_id"
            " WHERE m.survey_id = :s AND q.qcode = :q AND m.concept_option_id IS NULL"), {"s": sid, "q": qcode}).scalar()


@pytest.fixture()
def wave(legacy):  # noqa: F811
    """B1 = Q1 (yes/no), B10 = Q2 (multi-select), age = Q3; R_1..R_3 complete."""
    sid = legacy_dwh.load_legacy("SV_T")
    return legacy, sid, concept_code(legacy, sid, "Q1"), concept_code(legacy, sid, "Q2")


def members(engine, cohort_id):
    with engine.connect() as conn:
        return sorted(r[0] for r in conn.execute(sa.text(
            "SELECT r.forsta_uuid FROM cip_respondent_cohort c JOIN cip_respondent r"
            " ON r.respondent_id = c.respondent_id WHERE c.cohort_id = :c"), {"c": cohort_id}))


def test_option_rule_selects_who_gave_that_answer(wave):
    engine, sid, b1, _ = wave
    cid = cohorts.define_cohort("BEAUTY_YES", "Bought beauty", {"concept": b1, "option": "yes"})
    assert cohorts.derive(cid) == 2
    assert members(engine, cid) == ["R_1", "R_2"]


def test_multi_option_rule_selects_who_ticked_the_item(wave):
    engine, sid, _, b10 = wave
    cid = cohorts.define_cohort("AMAZON", "Bought beauty on Amazon", {"concept": b10, "option": "amazon_com"})
    cohorts.derive(cid)
    assert members(engine, cid) == ["R_1"]


def test_not_asked_branch_is_decided_by_the_wave_not_the_respondent(wave):
    engine, sid, b1, b10 = wave
    rule = {"any": [{"concept": b1, "option": "yes"},
                    {"all": [{"concept": b1, "asked": False}, {"concept": b10, "answered": True}]}]}
    cid = cohorts.define_cohort("BEAUTY_SHOPPER", "Beauty shoppers", rule)
    cohorts.derive(cid)
    # B1 WAS asked in this wave, so R_3 (said No) stays out although the not-asked branch exists
    assert members(engine, cid) == ["R_1", "R_2"]


def test_a_wave_that_never_asked_falls_to_the_not_asked_branch(wave):
    engine, sid, b1, b10 = wave
    rule = {"all": [{"concept": b1, "asked": False}, {"concept": b10, "answered": True}]}
    cid = cohorts.define_cohort("NOT_ASKED", "x", rule)
    assert cohorts.derive(cid) == 0                       # asked here
    with engine.begin() as conn:                          # now pretend B1 was never linked in this wave
        conn.execute(sa.text("UPDATE cip_concept_map SET status = 'rejected' WHERE survey_id = :s AND concept_id ="
                             " (SELECT concept_id FROM cip_concept WHERE concept_code = :c)"), {"s": sid, "c": b1})
    assert members(engine, cid) == [] and cohorts.derive(cid) == 2   # R_1, R_2 answered B10


def test_changed_rule_is_a_new_version_and_the_old_one_stops_being_current(wave):
    engine, sid, b1, _ = wave
    first = cohorts.define_cohort("BEAUTY_YES", "Bought beauty", {"concept": b1, "option": "yes"})
    assert cohorts.define_cohort("BEAUTY_YES", "Bought beauty", {"concept": b1, "option": "yes"}) == first
    second = cohorts.define_cohort("BEAUTY_YES", "Bought beauty", {"concept": b1, "option": "no"})
    assert second != first
    assert [c["version"] for c in cohorts.current_cohorts() if c["cohort_code"] == "BEAUTY_YES"] == [2]


def test_unknown_concept_or_option_is_refused_by_name(wave):
    _, _, b1, _ = wave
    with pytest.raises(ValueError, match="NOPE"):
        cohorts.define_cohort("X", "x", {"concept": "NOPE", "option": "yes"})
    with pytest.raises(ValueError, match="maybe"):
        cohorts.define_cohort("X", "x", {"concept": b1, "option": "maybe"})


from app.data import cube, repository


def strip(fn):
    return getattr(fn, "__wrapped__", fn)


def engine_frame(sid, qid, dim, criteria=()):
    return strip(repository.analyse)(sid, qid, criteria, None if dim == "total" else dim).reset_index(drop=True)


def reportable(engine, sid):
    with engine.connect() as conn:
        return [r[0] for r in conn.execute(sa.text(
            "SELECT question_id FROM cip_question WHERE survey_id = :s AND is_technical = 0"
            " AND qtype IN ('single', 'multi', 'grid_single')"), {"s": sid})]


def test_cube_equals_the_engine_for_every_question_and_cut(wave):
    engine, sid, _, _ = wave
    cube.build_cube(sid)
    for qid in reportable(engine, sid):
        for dim in cube.CUBE_DIMS:
            want = engine_frame(sid, qid, dim).to_dict("records")
            assert repository.analyse_cube(sid, qid, None, None if dim == "total" else dim).to_dict("records") == want, (qid, dim)


def test_cube_equals_the_engine_on_a_grid_and_a_multi_select(csi_db, tmp_path):
    from etl import qualtrics_export
    from tests.test_phase3 import qualtrics_file
    sid = qualtrics_export.ingest_export(qualtrics_file(tmp_path), "2025-05-12")
    cube.build_cube(sid)
    for qid in reportable(csi_db, sid):
        for dim in ("total", "census_region"):
            want = engine_frame(sid, qid, dim).to_dict("records")
            assert repository.analyse_cube(sid, qid, None, None if dim == "total" else dim).to_dict("records") == want, (qid, dim)


def test_cube_equals_the_engine_within_a_cohort(wave):
    engine, sid, b1, _ = wave
    cid = cohorts.define_cohort("BEAUTY_YES", "Bought beauty", {"concept": b1, "option": "yes"})
    cohorts.derive(cid)
    cube.build_cube(sid)
    crit = ({"kind": "cohort", "cohort_id": cid},)
    for qid in reportable(engine, sid):
        assert repository.analyse_cube(sid, qid, cid, "age_band").to_dict("records") == \
            engine_frame(sid, qid, "age_band", crit).to_dict("records"), qid


def test_cube_keeps_midpoint_sums_and_counts(wave):
    engine, sid, _, _ = wave
    cube.build_cube(sid)
    with engine.connect() as conn:
        row = conn.execute(sa.text(
            "SELECT c.n, c.sum_age_mid, c.n_age_mid FROM cip_agg_cell c JOIN cip_question q ON q.question_id = c.question_id"
            " JOIN cip_option o ON o.option_id = c.option_id"
            " WHERE c.survey_id = :s AND q.qcode = 'Q1' AND o.value_label = 'Yes' AND c.dim = 'total'"
            " AND c.cohort_id IS NULL"), {"s": sid}).one()
    assert (row.n, float(row.sum_age_mid), row.n_age_mid) == (2, 23.5 + 67.0, 2)


def test_rebuilding_a_wave_replaces_its_cells(wave):
    engine, sid, _, _ = wave
    first = cube.build_cube(sid)
    assert first > 0 and cube.build_cube(sid) == first
    with engine.connect() as conn:
        assert conn.execute(sa.text("SELECT COUNT(*) FROM cip_agg_cell WHERE survey_id = :s"), {"s": sid}).scalar() == first


def question_id(sid, qcode):
    frame = strip(repository.question_lookup)(sid)
    return int(frame[frame.qcode == qcode].question_id.iloc[0])


def concept_id(engine, code):
    with engine.connect() as conn:
        return conn.execute(sa.text("SELECT concept_id FROM cip_concept WHERE concept_code = :c"), {"c": code}).scalar()


def test_analyse_answers_from_the_cube_when_it_can(wave):
    engine, sid, _, _ = wave
    cube.build_cube(sid)
    qid = question_id(sid, "Q1")
    reads = []
    listener = lambda conn, cur, stmt, *args: reads.append(stmt)
    sa.event.listen(engine, "before_cursor_execute", listener)
    frame = strip(repository.analyse)(sid, qid, (), "age_band")
    sa.event.remove(engine, "before_cursor_execute", listener)
    assert any("cip_agg_cell" in s for s in reads) and not any("cip_answer" in s for s in reads)
    assert not frame.empty


def test_a_cohort_criterion_reads_the_same_from_cube_and_engine(wave):
    engine, sid, b1, _ = wave
    cid = cohorts.define_cohort("BEAUTY_YES", "Bought beauty", {"concept": b1, "option": "yes"})
    cohorts.derive(cid)
    cube.build_cube(sid)
    crit = ({"kind": "cohort", "cohort_id": cid},)
    forced_engine = crit + ({"kind": "profile", "dimension": "gender", "values": []},)   # a no-op criterion
    for qcode in ("Q1", "Q2"):
        qid = question_id(sid, qcode)
        assert strip(repository.analyse)(sid, qid, crit, None).to_dict("records") == \
            strip(repository.analyse)(sid, qid, forced_engine, None).to_dict("records")


def test_concept_trend_reads_every_wave_through_the_mapping(wave):
    engine, sid, b1, _ = wave
    cube.build_cube(sid)
    trend = strip(repository.concept_trend)(concept_id(engine, b1))
    assert set(trend.wave_label) == {"2025-02-17"}
    assert trend.set_index("answer").n.to_dict() == {"Yes": 2, "No": 1}
    assert set(trend.base_n) == {3}


def test_concept_pooled_stacks_waves_and_averages_midpoints(wave):
    engine, sid, b1, _ = wave
    cube.build_cube(sid)
    pooled = strip(repository.concept_pooled)(concept_id(engine, b1), [sid])
    yes = pooled[pooled.answer == "Yes"].iloc[0]
    assert (yes.n, yes.base_n, yes.avg_age) == (2, 3, (23.5 + 67.0) / 2)


def test_loading_a_wave_builds_its_cube(legacy):  # noqa: F811
    sid = legacy_dwh.load_legacy("SV_T")
    with legacy.connect() as conn:
        assert conn.execute(sa.text("SELECT COUNT(*) FROM cip_agg_cell WHERE survey_id = :s"), {"s": sid}).scalar() > 0


def test_loading_an_export_builds_its_cube(csi_db, tmp_path):
    from etl import qualtrics_export
    from tests.test_phase3 import qualtrics_file
    sid = qualtrics_export.ingest_export(qualtrics_file(tmp_path), "2025-05-12")
    with csi_db.connect() as conn:
        assert conn.execute(sa.text("SELECT COUNT(*) FROM cip_agg_cell WHERE survey_id = :s"), {"s": sid}).scalar() > 0


def test_a_mapping_decision_refreshes_only_the_cohorts_of_that_wave(wave):
    engine, sid, b1, _ = wave
    cid = cohorts.define_cohort("BEAUTY_YES", "Bought beauty", {"concept": b1, "option": "yes"})
    cube.refresh_wave(sid)
    everyone = lambda: count_cells(engine, sid, "IS NULL")
    before_all = everyone()
    assert count_cells(engine, sid, f"= {cid}") > 0
    with engine.begin() as conn:                           # an analyst un-links B1 in this wave
        conn.execute(sa.text("UPDATE cip_concept_map SET status = 'rejected' WHERE survey_id = :s AND concept_id ="
                             " (SELECT concept_id FROM cip_concept WHERE concept_code = :c)"), {"s": sid, "c": b1})
    cube.refresh_cohorts(sid)
    assert members(engine, cid) == [] and count_cells(engine, sid, f"= {cid}") == 0
    assert everyone() == before_all


def count_cells(engine, sid, cohort_clause):
    with engine.connect() as conn:
        return conn.execute(sa.text(f"SELECT COUNT(*) FROM cip_agg_cell WHERE survey_id = :s AND cohort_id {cohort_clause}"),
                            {"s": sid}).scalar()


def test_a_decision_that_leaves_a_cohort_unchanged_does_not_rebuild_its_cells(wave):
    engine, sid, b1, _ = wave
    cid = cohorts.define_cohort("BEAUTY_YES", "Bought beauty", {"concept": b1, "option": "yes"})
    cube.refresh_wave(sid)
    ids = lambda: sorted(r[0] for r in engine.connect().execute(sa.text(
        "SELECT cell_id FROM cip_agg_cell WHERE survey_id = :s AND cohort_id = :c"), {"s": sid, "c": cid}))
    before = ids()
    assert cube.refresh_cohorts(sid) == 0 and ids() == before


# ── final-review fixes ─────────────────────────────────────────────────────
def test_a_criterion_follows_the_cohort_to_its_new_version(wave):
    engine, sid, b1, _ = wave
    v1 = cohorts.define_cohort("BEAUTY_YES", "Bought beauty", {"concept": b1, "option": "yes"})
    cohorts.derive(v1)
    crit = ({"kind": "cohort", "cohort_code": "BEAUTY_YES"},)
    v2 = cohorts.define_cohort("BEAUTY_YES", "Bought beauty", {"concept": b1, "option": "no"})
    cohorts.derive(v2)
    cube.build_cube(sid)
    qid = question_id(sid, "Q1")
    assert strip(repository.analyse)(sid, qid, crit, None).set_index("answer").n.to_dict() == {"No": 1}
    assert members(engine, v1) == []                    # the retired version keeps nothing


def test_sync_builds_the_cohort_cells_it_derives(wave, tmp_path):
    engine, sid, b1, _ = wave
    config = tmp_path / "cohorts.yml"
    config.write_text(f"cohorts:\n  - code: BEAUTY_YES\n    name: Bought beauty\n    rule: {{concept: {b1}, option: 'yes'}}\n")
    [cid] = cohorts.sync(config)
    assert count_cells(engine, sid, f"= {cid}") > 0


def test_a_failed_cohort_rebuild_leaves_memberships_and_cells_consistent(wave, monkeypatch):
    engine, sid, b1, _ = wave
    cid = cohorts.define_cohort("BEAUTY_YES", "Bought beauty", {"concept": b1, "option": "yes"})
    cube.refresh_wave(sid)
    with engine.begin() as conn:
        conn.execute(sa.text("UPDATE cip_concept_map SET status = 'rejected' WHERE survey_id = :s AND concept_id ="
                             " (SELECT concept_id FROM cip_concept WHERE concept_code = :c)"), {"s": sid, "c": b1})
    real = cube._single_sql
    monkeypatch.setattr(cube, "_single_sql", lambda *a: (_ for _ in ()).throw(RuntimeError("VPN dropped")))
    with pytest.raises(RuntimeError):
        cube.refresh_cohorts(sid)
    monkeypatch.setattr(cube, "_single_sql", real)
    assert members(engine, cid) == ["R_1", "R_2"]          # rolled back with the cells
    cube.refresh_cohorts(sid)                              # and the retry still sees the change
    assert members(engine, cid) == [] and count_cells(engine, sid, f"= {cid}") == 0


def test_a_failed_full_rebuild_leaves_no_stale_cells_behind(wave, monkeypatch):
    engine, sid, _, _ = wave
    cube.build_cube(sid)
    monkeypatch.setattr(cube, "_multi_sql", lambda *a: (_ for _ in ()).throw(RuntimeError("VPN dropped")))
    with pytest.raises(RuntimeError):
        cube.refresh_wave(sid)
    assert count_cells(engine, sid, "IS NULL") == 0        # readers fall back to the engine


def test_answered_on_a_grid_row_means_that_row(csi_db, tmp_path):
    from etl import qualtrics_export
    from tests.test_phase3 import qualtrics_file
    sid = qualtrics_export.ingest_export(qualtrics_file(tmp_path), "2025-05-12")
    with csi_db.connect() as conn:
        cvs_row = conn.execute(sa.text(
            "SELECT c.concept_code FROM cip_concept c JOIN cip_concept_map m ON m.concept_id = c.concept_id"
            " JOIN cip_item i ON i.item_id = m.item_id WHERE m.survey_id = :s AND i.item_label = 'CVS'"
            " AND m.concept_option_id IS NULL"), {"s": sid}).scalar()
    cid = cohorts.define_cohort("RATED_CVS", "Rated CVS", {"concept": cvs_row, "answered": True})
    cohorts.derive(cid)
    assert members(csi_db, cid) == ["R_a"]                 # R_b rated Amazon only


def test_a_mapping_confirmed_after_the_cube_was_built_joins_the_trend(wave):
    engine, sid, b1, _ = wave
    cube.build_cube(sid)
    cells = count_cells(engine, sid, "IS NULL")
    concept = concept_id(engine, b1)
    with engine.begin() as conn:                           # turn B1 back into a waiting proposal
        qid = conn.execute(sa.text("SELECT question_id FROM cip_question WHERE survey_id = :s AND qcode = 'Q1'"),
                           {"s": sid}).scalar()
        conn.execute(sa.text("DELETE FROM cip_concept_map WHERE survey_id = :s AND question_id = :q"
                             " AND concept_option_id IS NOT NULL"), {"s": sid, "q": qid})
        conn.execute(sa.text("UPDATE cip_concept_map SET status = 'proposed' WHERE survey_id = :s AND question_id = :q"),
                     {"s": sid, "q": qid})
    assert strip(repository.concept_trend)(concept).empty
    harmonise.confirm(sid, qid, None, concept, "analyst@coresight.com")
    assert set(strip(repository.concept_trend)(concept).wave_label) == {"2025-02-17"}
    assert count_cells(engine, sid, "IS NULL") == cells


def test_two_surveys_of_one_wave_are_one_point_on_the_trend(wave):
    engine, sid, b1, _ = wave
    with engine.begin() as conn:                           # a second panel fielded the same week
        for table, cols in (("dwh_smsurveydetail", "'SV_T2', title, date_created, response_count, isvalid"),):
            conn.execute(sa.text(f"INSERT INTO {table} SELECT {cols} FROM {table} WHERE id = 'SV_T'"))
        conn.execute(sa.text("INSERT INTO dwh_smquestion SELECT id || '2', family, title, srt1, srt2, 'SV_T2' FROM dwh_smquestion WHERE survey_id = 'SV_T'"))
        conn.execute(sa.text("INSERT INTO dwh_smanswer SELECT id || '2', srt, title, question_id || '2', 'SV_T2' FROM dwh_smanswer WHERE survey_id = 'SV_T'"))
        conn.execute(sa.text("INSERT INTO dwh_smresponse SELECT id || '2', response_status, date_filled, total_time_spent, 'SV_T2' FROM dwh_smresponse WHERE survey_id = 'SV_T'"))
        conn.execute(sa.text("INSERT INTO dwh_smresponseqa (answer_text, question_text, answer_othertext, question_id, response_id, answer_id, survey_id)"
                             " SELECT answer_text, question_text, answer_othertext, question_id || '2', response_id || '2', answer_id || '2', 'SV_T2'"
                             " FROM dwh_smresponseqa WHERE survey_id = 'SV_T'"))
    legacy_dwh.load_legacy("SV_T2")
    cube.build_cube(sid)
    trend = strip(repository.concept_trend)(concept_id(engine, b1))
    assert len(trend[trend.answer == "Yes"]) == 1
    assert trend[trend.answer == "Yes"].iloc[0][["n", "base_n"]].tolist() == [4, 6]


def test_a_standard_view_is_one_read(wave):
    engine, sid, _, _ = wave
    cube.build_cube(sid)
    qid = question_id(sid, "Q1")
    reads = []
    listener = lambda conn, cur, stmt, *args: reads.append(stmt)
    sa.event.listen(engine, "before_cursor_execute", listener)
    strip(repository.analyse)(sid, qid, (), "age_band")
    sa.event.remove(engine, "before_cursor_execute", listener)
    assert len(reads) == 1, reads


def test_the_read_only_engine_costs_one_round_trip_per_query(monkeypatch):
    """Pre-ping (SELECT 1) and the rollback on return each cost ~250 ms from
    India; the read role needs neither (the MDP read engine, CLAUDE.md)."""
    from app.core import database
    from app.core.config import DatabaseConfig
    monkeypatch.setattr(database.config, "database",
                        lambda role: DatabaseConfig(host="db.example", port=3306, database="x", user="u", password="p"))
    monkeypatch.setattr(database, "_engines", {})
    engine = database.get_engine("app")
    assert engine.pool._pre_ping is False
    assert engine.dialect._on_connect_isolation_level == "AUTOCOMMIT"
