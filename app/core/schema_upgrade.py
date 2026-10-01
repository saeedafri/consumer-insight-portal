"""Bring a CSI database to schema v2, in place, safely re-runnable.

`sql/001_schema.sql` describes v2 for a fresh install. A database created
under v1 already has its tables, so CREATE TABLE IF NOT EXISTS skips them and
their new columns never arrive. This module adds exactly what is missing,
after checking the live catalogue, and nothing else: no v1 object is dropped
or renamed. See docs/superpowers/specs/2026-09-29-survey-platform-design.md §5.
"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.core import sqlite_compat
from app.core.database import apply_sql

SQL_DIR = Path(__file__).resolve().parents[2] / "sql"
SQL_FILES = [SQL_DIR / "001_schema.sql", SQL_DIR / "002_views.sql",
             SQL_DIR / "003_seed_topics.sql"]

# NOT NULL: MySQL lets repeated NULLs through a unique key, and source_ref is
# part of the wave identity (uq_survey_source).
SOURCE_REF = "VARCHAR(255) NOT NULL DEFAULT ''"

# (table, column, MySQL definition) — the v2 columns on v1 tables
COLUMNS: list[tuple[str, str, str]] = [
    ("csi_survey", "platform",
     "ENUM('forsta','qualtrics','surveymonkey') NOT NULL DEFAULT 'forsta'"),
    ("csi_survey", "source_ref", SOURCE_REF),
    ("csi_survey", "study_type", "ENUM('tracker','annual','adhoc') NOT NULL DEFAULT 'tracker'"),
    ("csi_survey", "load_status",
     "ENUM('loading','verified','failed','superseded') NOT NULL DEFAULT 'verified'"),
    ("csi_survey", "language", "VARCHAR(10) NOT NULL DEFAULT 'en'"),
    ("csi_respondent", "respondent_key", "CHAR(64) NULL"),
    ("csi_respondent", "quality_flag", "VARCHAR(40) NULL"),
    ("csi_profile", "age_mid", "DECIMAL(6,2) NULL"),
    ("csi_profile", "income_mid_k", "DECIMAL(10,4) NULL"),
    ("csi_load_log", "archive_uri", "VARCHAR(1000) NULL"),
    ("csi_load_log", "archive_sha256", "CHAR(64) NULL"),
    ("csi_concept", "match_text", "VARCHAR(2000) NULL"),
    ("csi_agg_cell", "map_key", "VARCHAR(40) NULL"),
    ("csi_agg_cell", "n_age_mid", "INT NULL"),
    ("csi_agg_cell", "n_income_mid", "INT NULL"),
]

# v1 waves all came from Forsta: their path is their source reference.
# Runs before the unique key below, so no row enters it with a NULL.
BACKFILL = ["UPDATE csi_survey SET source_ref = forsta_path WHERE source_ref IS NULL OR source_ref = ''"]

# Columns that must be NOT NULL but may exist NULL-able from an earlier run.
NOT_NULL: list[tuple[str, str, str]] = [("csi_survey", "source_ref", SOURCE_REF)]

# (table, index, kind, columns)
INDEXES: list[tuple[str, str, str, str]] = [
    ("csi_survey", "uq_survey_source", "UNIQUE", "platform, source_ref, wave_label"),
    ("csi_respondent", "ix_respondent_key", "INDEX", "survey_id, respondent_key"),
    ("csi_answer", "ix_answer_cover", "INDEX", "survey_id, field_id, value_code, respondent_id"),
    ("csi_answer", "ft_answer_text", "FULLTEXT", "value_text"),
    ("csi_agg_cell", "ix_agg_map", "INDEX", "survey_id, map_key, cohort_id, dim"),
]


def plan(engine: Engine) -> list[str]:
    """Statements that bring this database to v2. Tables that do not exist
    yet are skipped — the schema files create them already at v2."""
    insp = inspect(engine)
    is_sqlite = engine.dialect.name == "sqlite"
    tables = set(insp.get_table_names())
    statements: list[str] = []

    for table, column, definition in COLUMNS:
        if table not in tables:
            continue
        if column not in {c["name"] for c in insp.get_columns(table)}:
            defn = sqlite_compat.convert_column_def(definition) if is_sqlite else definition
            statements.append(f"ALTER TABLE {table} ADD COLUMN {column} {defn}")

    if "csi_survey" in tables:
        statements += BACKFILL

    nullable = {t: {c["name"]: c["nullable"] for c in insp.get_columns(t)}
                for t in {t for t, _, _ in NOT_NULL} & tables}
    statements += tighten_statements(nullable, is_sqlite)

    for table, name, kind, cols in INDEXES:
        if table not in tables or name in {i["name"] for i in insp.get_indexes(table)}:
            continue
        if is_sqlite:
            if kind == "FULLTEXT":
                continue                      # no SQLite equivalent; search is MySQL-only
            unique = "UNIQUE " if kind == "UNIQUE" else ""
            statements.append(f"CREATE {unique}INDEX {name} ON {table} ({cols})")
        else:
            key = {"UNIQUE": "UNIQUE KEY", "FULLTEXT": "FULLTEXT KEY"}.get(kind, "KEY")
            statements.append(f"ALTER TABLE {table} ADD {key} {name} ({cols})")
    return statements


def tighten_statements(nullable: dict[str, dict[str, bool]], is_sqlite: bool) -> list[str]:
    """MODIFY a NULL-able column to its NOT NULL definition, after the backfill.
    SQLite cannot change nullability in place; its copies take the rule from
    001 when rebuilt."""
    if is_sqlite:
        return []
    return [f"ALTER TABLE {table} MODIFY COLUMN {column} {definition}"
            for table, column, definition in NOT_NULL
            if nullable.get(table, {}).get(column)]


def install(engine: Engine, dry_run: bool = False, force: bool = False) -> list[str]:
    """Upgrade in place, then apply the schema files. Refuses while a load is
    writing: DDL on csi_answer and a running load would block each other."""
    if "csi_load_log" in inspect(engine).get_table_names() and not force:
        with engine.connect() as conn:
            running = conn.execute(text(
                "SELECT COUNT(*) FROM csi_load_log WHERE status = 'running'")).scalar()
        if running:
            raise RuntimeError(
                f"{running} load is running (csi_load_log.status = 'running'). "
                "Wait for it, or mark a stale run failed, or pass --force.")

    statements = plan(engine)
    if dry_run:
        return statements + [f"-- apply {p.name}" for p in SQL_FILES]
    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))
    for path in SQL_FILES:
        apply_sql(path, engine)
    return statements
