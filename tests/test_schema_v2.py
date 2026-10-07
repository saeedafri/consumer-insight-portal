"""Schema v2, Phase 1: the additive migration.

See docs/superpowers/specs/2026-09-29-survey-platform-design.md §5.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
import sqlalchemy as sa

from app.core import database, schema_upgrade, sqlite_compat
from app.core.database import apply_sql


def test_fulltext_keys_are_dropped_for_sqlite():
    stmt = (
        "CREATE TABLE IF NOT EXISTS t (\n"
        "  id INT NOT NULL,\n"
        "  body TEXT NULL,\n"
        "  PRIMARY KEY (id),\n"
        "  FULLTEXT KEY ft_body (body)\n"
        ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
    )
    out = sqlite_compat.convert_ddl(stmt)[0]
    assert "FULLTEXT" not in out.upper()
    sqlite3.connect(":memory:").execute(out)          # must be valid SQLite


def test_column_definition_is_converted_for_sqlite():
    defn = "ENUM('forsta','qualtrics') NOT NULL DEFAULT 'forsta' COMMENT 'source platform'"
    assert sqlite_compat.convert_column_def(defn) == "TEXT NOT NULL DEFAULT 'forsta'"
    assert sqlite_compat.convert_column_def("INT UNSIGNED NULL") == "INT NULL"


REPO = Path(__file__).resolve().parents[1]
SCHEMA = REPO / "sql" / "001_schema.sql"
VIEWS = REPO / "sql" / "002_views.sql"
SEED = REPO / "sql" / "003_seed_topics.sql"
SCHEMA_V1 = REPO / "tests" / "fixtures" / "schema_v1.sql"

NEW_TABLES = {
    "cip_concept", "cip_concept_option", "cip_concept_map",
    "cip_weight_scheme", "cip_weight",
    "cip_cohort_def", "cip_respondent_cohort",
    "cip_agg_cell",
    "cip_publication", "cip_publication_cell",
}
NEW_COLUMNS = {
    "cip_survey": {"platform", "source_ref", "study_type", "load_status", "language"},
    "cip_respondent": {"respondent_key", "quality_flag"},
    "cip_profile": {"age_mid", "income_mid_k"},
    "cip_load_log": {"archive_uri", "archive_sha256"},
}


def sqlite_engine(tmp_path, name: str) -> sa.Engine:
    engine = sa.create_engine(f"sqlite:///{tmp_path / name}", future=True)
    with engine.connect() as conn:
        conn.execute(sa.text("PRAGMA foreign_keys=ON"))
    return engine


def columns(engine: sa.Engine) -> dict[str, set[str]]:
    insp = sa.inspect(engine)
    return {t: {c["name"] for c in insp.get_columns(t)}
            for t in insp.get_table_names() if t.startswith("cip_")}


def test_fresh_v2_schema_has_every_table_and_column(tmp_path):
    engine = sqlite_engine(tmp_path, "fresh.db")
    for path in (SCHEMA, VIEWS, SEED):
        apply_sql(path, engine)
    cols = columns(engine)
    assert len(cols) == 31            # + cip_forsta_survey, cip_search (Oct 2026)
    assert NEW_TABLES <= set(cols)
    for table, wanted in NEW_COLUMNS.items():
        assert wanted <= cols[table], f"{table} missing {wanted - cols[table]}"


def v1_database(tmp_path, name: str = "v1.db") -> sa.Engine:
    """A database exactly as v1 left it, with one real wave in it."""
    engine = sqlite_engine(tmp_path, name)
    apply_sql(SCHEMA_V1, engine)
    with engine.begin() as conn:
        conn.execute(sa.text(
            "INSERT INTO cip_survey (forsta_host, forsta_path, title, wave_label, status)"
            " VALUES ('se1.decipherinc.com', 'selfserve/58f/260908', 'Shopping and Spending',"
            " '2026-09-21', 'closed')"))
    return engine


def test_install_upgrades_v1_to_exactly_v2(tmp_path):
    upgraded = v1_database(tmp_path)
    schema_upgrade.install(upgraded)

    fresh = sqlite_engine(tmp_path, "fresh.db")
    schema_upgrade.install(fresh)

    assert columns(upgraded) == columns(fresh)
    with upgraded.connect() as conn:
        row = conn.execute(sa.text(
            "SELECT platform, source_ref, load_status, study_type FROM cip_survey")).one()
    assert tuple(row) == ("forsta", "selfserve/58f/260908", "verified", "tracker")


def test_second_install_changes_nothing(tmp_path):
    engine = v1_database(tmp_path)
    schema_upgrade.install(engine)
    again = schema_upgrade.plan(engine)
    assert not [s for s in again if s.lstrip().upper().startswith(("ALTER", "CREATE"))]


def test_plan_on_an_empty_database_is_harmless(tmp_path):
    engine = sqlite_engine(tmp_path, "empty.db")
    assert not [s for s in schema_upgrade.plan(engine) if s.startswith("ALTER")]


def test_install_refuses_while_a_load_is_running(tmp_path):
    engine = v1_database(tmp_path)
    with engine.begin() as conn:
        conn.execute(sa.text(
            "INSERT INTO cip_load_log (source_type, object_type, status)"
            " VALUES ('excel', 'data', 'running')"))
    with pytest.raises(RuntimeError, match="load is running"):
        schema_upgrade.install(engine)
    schema_upgrade.install(engine, force=True)          # the operator's override
    assert "platform" in columns(engine)["cip_survey"]


def test_dry_run_writes_nothing(tmp_path):
    engine = v1_database(tmp_path)
    planned = schema_upgrade.install(engine, dry_run=True)
    assert any("ADD COLUMN platform" in s for s in planned)
    assert "platform" not in columns(engine)["cip_survey"]


def test_upsert_survey_records_platform_and_updates_in_place(tmp_path, monkeypatch):
    engine = sqlite_engine(tmp_path, "upsert.db")
    schema_upgrade.install(engine)
    database._install_sqlite_translation(engine)
    monkeypatch.setitem(database._engines, "etl", engine)
    from etl.loaders import upsert_survey

    first = upsert_survey(host="se1.decipherinc.com", path="selfserve/58f/260908",
                          title="Shopping and Spending", wave_label="2026-09-28")
    again = upsert_survey(host="se1.decipherinc.com", path="selfserve/58f/260908",
                          title="Shopping and Spending (retitled)", wave_label="2026-09-28")
    legacy = upsert_survey(host="qualtrics", path="SV_0IHGTy1GPAlUsGa",
                           title="Beauty + Shrink", wave_label="2025-02-17",
                           platform="qualtrics", source_ref="SV_0IHGTy1GPAlUsGa")

    assert first == again != legacy
    with engine.connect() as conn:
        rows = conn.execute(sa.text(
            "SELECT survey_id, platform, source_ref, title FROM cip_survey ORDER BY survey_id")).all()
    assert [tuple(r)[1:] for r in rows] == [
        ("forsta", "selfserve/58f/260908", "Shopping and Spending (retitled)"),
        ("qualtrics", "SV_0IHGTy1GPAlUsGa", "Beauty + Shrink"),
    ]


def test_same_wave_from_a_different_host_updates_the_same_row(tmp_path, monkeypatch):
    """The wave's identity is platform + source_ref + wave (spec §5.1). Changing
    FORSTA_HOST between loads must update that wave, not crash the load."""
    engine = sqlite_engine(tmp_path, "hosts.db")
    schema_upgrade.install(engine)
    database._install_sqlite_translation(engine)
    monkeypatch.setitem(database._engines, "etl", engine)
    from etl.loaders import upsert_survey

    first = upsert_survey(host="se1.decipherinc.com", path="selfserve/58f/260908",
                          title="Shopping and Spending", wave_label="2026-09-28")
    moved = upsert_survey(host="se2.decipherinc.com", path="selfserve/58f/260908",
                          title="Shopping and Spending", wave_label="2026-09-28")
    assert moved == first
    with engine.connect() as conn:
        assert conn.execute(sa.text("SELECT COUNT(*), MAX(forsta_host) FROM cip_survey")).one() \
            == (1, "se2.decipherinc.com")


def test_source_ref_cannot_be_null_so_uniqueness_always_holds(tmp_path):
    """MySQL lets repeated NULLs through a unique key. An insert that bypasses
    upsert_survey must still collide, not create a silent duplicate wave."""
    engine = sqlite_engine(tmp_path, "notnull.db")
    schema_upgrade.install(engine)
    insert = sa.text("INSERT INTO cip_survey (forsta_host, forsta_path, title, wave_label)"
                     " VALUES (:host, 'p', 't', '2026-10-05')")
    with engine.begin() as conn:
        conn.execute(insert, {"host": "a"})
    with pytest.raises(sa.exc.IntegrityError):
        with engine.begin() as conn:
            conn.execute(insert, {"host": "b"})


def test_upgrade_tightens_a_nullable_source_ref_on_mysql():
    """dwh_stg received source_ref as NULL-able before this rule; the upgrade
    backfills it, then makes it NOT NULL. SQLite cannot alter nullability in
    place, so its copies get the rule from 001 when rebuilt."""
    nullable = {"cip_survey": {"source_ref": True}}
    assert schema_upgrade.tighten_statements(nullable, is_sqlite=False) == [
        "ALTER TABLE cip_survey MODIFY COLUMN source_ref VARCHAR(255) NOT NULL DEFAULT ''"]
    assert schema_upgrade.tighten_statements(nullable, is_sqlite=True) == []
    assert schema_upgrade.tighten_statements({"cip_survey": {"source_ref": False}},
                                             is_sqlite=False) == []


def test_csi_tables_are_renamed_to_cip_keeping_their_data(tmp_path):
    """The portal's tables were csi_ (Consumer Survey Index) until Oct 2026;
    install() renames them to cip_ in place — data, keys and all."""
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'old.db'}", future=True)
    schema_upgrade.install(engine)
    with engine.begin() as conn:
        conn.execute(sa.text("INSERT INTO cip_survey (forsta_host, forsta_path, title, wave_label)"
                             " VALUES ('h', 'p', 'Shopping and Spending', '2026-09-21')"))
        for view in [v for v in sa.inspect(engine).get_view_names() if v.startswith("v_cip_")]:
            conn.execute(sa.text(f"DROP VIEW {view}"))
        for table in [t for t in sa.inspect(engine).get_table_names() if t.startswith("cip_")]:
            conn.execute(sa.text(f"ALTER TABLE {table} RENAME TO {'csi_' + table[4:]}"))
    assert "csi_survey" in sa.inspect(engine).get_table_names()
    schema_upgrade.install(engine)
    insp = sa.inspect(sa.create_engine(f"sqlite:///{tmp_path / 'old.db'}", future=True))
    assert not [t for t in insp.get_table_names() if t.startswith("csi_")]
    assert "v_cip_survey_health" in insp.get_view_names() and not [v for v in insp.get_view_names() if "csi" in v]
    with engine.connect() as conn:
        assert conn.execute(sa.text("SELECT title FROM cip_survey")).scalar() == "Shopping and Spending"
    assert not [s for s in schema_upgrade.plan(engine) if "RENAME" in s.upper()]
