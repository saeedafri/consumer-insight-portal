# Schema v2 — Phase 1 (Additive Migration) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the CSI schema in `dwh_stg` (and every local SQLite copy) from v1 (19 tables) to v2 (29 tables + new columns and indexes), additively and idempotently, with every existing number unchanged.

**Architecture:** `sql/001_schema.sql` stays the single source of truth and describes v2 for fresh installs. A new `app/core/schema_upgrade.py` adds the v2 columns and indexes to an *existing* v1 database, checking the live catalogue first, so it is safe to re-run. `scripts/init_db.py` runs the upgrade first, then the SQL files. Nothing is dropped or renamed.

**Tech Stack:** Python 3.13, SQLAlchemy 2, PyMySQL, MySQL 8.0 (Azure Flexible, `dwh_stg`), SQLite (local copy and tests via `app/core/sqlite_compat.py`), pytest.

**Spec:** `docs/superpowers/specs/2026-09-29-survey-platform-design.md` (§5 Schema v2, §11 Phase 1)

**Out of scope for Phase 1:** the three new views (`v_csi_mapping_queue` arrives with the Harmoniser in Phase 2; `v_csi_concept_answers` and `v_csi_concept_cells` with the Deriver and cube in Phase 4). Views over empty tables would be untested guesses.

## Global Constraints

- Target database: `dwh_stg` on `csr-mysql8-flex-stg.mysql.database.azure.com`, account `dwh_app_access` (from `.env`, `STG_DB_*`).
- Every object prefixed `csi_`; charset `utf8mb4`, `COLLATE=utf8mb4_0900_ai_ci`, `ENGINE=InnoDB`.
- **Additive only:** no v1 column, index or table is dropped or renamed.
- `csi_survey`'s existing `UNIQUE KEY uq_survey` must stay the **first** unique key in its DDL (SQLite upserts use the first unique key as the conflict target — `sqlite_compat.conflict_targets`).
- No unique key may contain a nullable column (MySQL treats NULLs as distinct); use a computed `*_key` column instead.
- Legacy `dwh_sm*` tables are never written.
- **Never run `git commit` or `git push`** (repo rule: the user commits). Checkpoints below list the changed files instead.
- Naming: plain 1–4 word names, verb-first functions, no `*Manager`/`*Utils`; match surrounding code style.
- After the run on `dwh_stg`: `scripts/reconcile.py` must still report 667/667 (2026-09-21) and 788/788 (2026-09-28).

## Review Focus

1. **Migration run while a load is writing** — DDL on `csi_answer` would block or be blocked by the loader. Expected: the migration refuses to start if any `csi_load_log` row is `running`, unless `--force`. Test in Task 3.
2. **Fresh database with no tables** — the upgrade must be a no-op, not a crash, and the schema files then create v2 directly. Test in Task 3.
3. **Re-running the migration** — the second run must contain no DDL. Test in Task 3; checked again on `dwh_stg` in Task 5.
4. **SQLite upsert target** — after v2, re-loading the same wave locally must update, not duplicate, the `csi_survey` row. Test in Task 4.
5. **MySQL-only syntax** (`FULLTEXT`, `ENUM` in `ALTER`) cannot be exercised on SQLite — covered by the dry-run, real run and catalogue checks on `dwh_stg` in Task 5.

## File Map

| File | Change | Responsibility |
|---|---|---|
| `app/core/sqlite_compat.py` | modify | also drop `FULLTEXT KEY` lines; convert a single column definition |
| `app/core/database.py` | modify | `apply_sql(path, engine)` extracted from `run_sql_file` |
| `sql/001_schema.sql` | modify | v2 columns on 5 existing tables; 10 new tables |
| `tests/fixtures/schema_v1.sql` | create | frozen copy of today's v1 DDL, the upgrade test's starting point |
| `app/core/schema_upgrade.py` | create | v1 → v2 in place: plan, upgrade, install |
| `scripts/init_db.py` | modify | run `install()`; `--dry-run` prints the plan; `--force` |
| `etl/loaders.py` | modify | `upsert_survey` writes `platform` and `source_ref` |
| `tests/test_schema_v2.py` | create | all tests for this phase |
| `docs/…` | modify | spec clarifications, README status |

---

### Task 1: SQLite converter handles FULLTEXT keys and single column definitions

**Files:**
- Modify: `app/core/sqlite_compat.py`
- Test: `tests/test_schema_v2.py` (create)

**Interfaces:**
- Produces: `sqlite_compat.convert_column_def(defn: str) -> str` — a MySQL column definition (`"ENUM('a','b') NOT NULL DEFAULT 'a' COMMENT 'x'"`) rewritten for SQLite (`"TEXT NOT NULL DEFAULT 'a'"`).
- Produces: `convert_ddl()` now removes `FULLTEXT KEY name (...)` lines.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_schema_v2.py`:

```python
"""Schema v2, Phase 1: the additive migration.

See docs/superpowers/specs/2026-09-29-survey-platform-design.md §5.
"""
from __future__ import annotations

import sqlite3

from app.core import sqlite_compat


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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_schema_v2.py -v`
Expected: `test_fulltext_keys_are_dropped_for_sqlite` FAILS (sqlite3 syntax error near "FULLTEXT"); `test_column_definition_is_converted_for_sqlite` FAILS with `AttributeError: … has no attribute 'convert_column_def'`.

- [ ] **Step 3: Implement**

In `app/core/sqlite_compat.py`, add to the docstring's list the line
`    FULLTEXT KEY lines                        dropped (no SQLite equivalent)`
then, below `_KEY_LINE`, add:

```python
_FULLTEXT_LINE = re.compile(r"^\s*FULLTEXT\s+KEY\s+\w+\s*\([^)]*\),?\s*$", re.I | re.M)
```

In `convert_ddl`, directly after `s = _KEY_LINE.sub("", s)`, add:

```python
    s = _FULLTEXT_LINE.sub("", s)
```

At the end of the module, add:

```python
def convert_column_def(defn: str) -> str:
    """One MySQL column definition, as written after ADD COLUMN, for SQLite."""
    s = _COMMENT.sub("", defn)
    s = _ENUM.sub("TEXT", s)
    s = _UNSIGNED.sub(r"\1", s)
    s = _TINYINT_LEN.sub("TINYINT", s)
    s = _ON_UPDATE_TS.sub("", s)
    return " ".join(s.split())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_schema_v2.py -v`
Expected: 2 passed.

- [ ] **Step 5: Checkpoint (no commit)**

Run: `git status --short` — expected changes: `app/core/sqlite_compat.py`, `tests/test_schema_v2.py`.

---

### Task 2: v2 DDL for fresh installs

**Files:**
- Create: `tests/fixtures/schema_v1.sql` (copy, before any edit)
- Modify: `app/core/database.py` (extract `apply_sql`)
- Modify: `sql/001_schema.sql`
- Test: `tests/test_schema_v2.py`

**Interfaces:**
- Consumes: Task 1's `FULLTEXT` handling.
- Produces: `database.apply_sql(path: str | Path, engine: Engine) -> int` — applies one `.sql` file to the given engine (converting for SQLite), returns statements applied. `run_sql_file(path, role)` becomes `apply_sql(path, get_engine(role))`.
- Produces: the v2 table and column names below, used by Tasks 3–5.

- [ ] **Step 1: Freeze the v1 schema before touching it**

Run:
```bash
mkdir -p tests/fixtures && cp sql/001_schema.sql tests/fixtures/schema_v1.sql
```
Expected: `grep -c "CREATE TABLE" tests/fixtures/schema_v1.sql` prints `19`.

- [ ] **Step 2: Write the failing test**

Append to `tests/test_schema_v2.py`:

```python
from pathlib import Path

import sqlalchemy as sa

from app.core.database import apply_sql

REPO = Path(__file__).resolve().parents[1]
SCHEMA = REPO / "sql" / "001_schema.sql"
VIEWS = REPO / "sql" / "002_views.sql"
SEED = REPO / "sql" / "003_seed_topics.sql"
SCHEMA_V1 = REPO / "tests" / "fixtures" / "schema_v1.sql"

NEW_TABLES = {
    "csi_concept", "csi_concept_option", "csi_concept_map",
    "csi_weight_scheme", "csi_weight",
    "csi_cohort_def", "csi_respondent_cohort",
    "csi_agg_cell",
    "csi_publication", "csi_publication_cell",
}
NEW_COLUMNS = {
    "csi_survey": {"platform", "source_ref", "study_type", "load_status", "language"},
    "csi_respondent": {"respondent_key", "quality_flag"},
    "csi_profile": {"age_mid", "income_mid_k"},
    "csi_load_log": {"archive_uri", "archive_sha256"},
}


def sqlite_engine(tmp_path, name: str) -> sa.Engine:
    engine = sa.create_engine(f"sqlite:///{tmp_path / name}", future=True)
    with engine.connect() as conn:
        conn.execute(sa.text("PRAGMA foreign_keys=ON"))
    return engine


def columns(engine: sa.Engine) -> dict[str, set[str]]:
    insp = sa.inspect(engine)
    return {t: {c["name"] for c in insp.get_columns(t)}
            for t in insp.get_table_names() if t.startswith("csi_")}


def test_fresh_v2_schema_has_every_table_and_column(tmp_path):
    engine = sqlite_engine(tmp_path, "fresh.db")
    for path in (SCHEMA, VIEWS, SEED):
        apply_sql(path, engine)
    cols = columns(engine)
    assert len(cols) == 29
    assert NEW_TABLES <= set(cols)
    for table, wanted in NEW_COLUMNS.items():
        assert wanted <= cols[table], f"{table} missing {wanted - cols[table]}"
```

- [ ] **Step 3: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_schema_v2.py::test_fresh_v2_schema_has_every_table_and_column -v`
Expected: FAIL with `ImportError: cannot import name 'apply_sql'`.

- [ ] **Step 4: Extract `apply_sql` in `app/core/database.py`**

Replace the body of `run_sql_file` so the file reads:

```python
def apply_sql(path, engine: Engine) -> int:
    """Apply one .sql file to `engine`. On SQLite the MySQL DDL is converted on
    the fly (see sqlite_compat) so there is only one schema file to maintain."""
    raw = open(path, "r", encoding="utf-8").read()
    statements = sqlite_compat.split_statements(raw)
    is_sqlite = engine.dialect.name == "sqlite"

    applied = 0
    with engine.begin() as conn:
        for stmt in statements:
            for out in (sqlite_compat.convert_ddl(stmt) if is_sqlite else [stmt]):
                if not out:
                    continue
                conn.execute(text(out))
                applied += 1
        if is_sqlite:
            for idx in sqlite_compat.index_statements(raw):
                conn.execute(text(idx))
                applied += 1
    logger.info("Applied %s (%d statements, dialect=%s)",
                path, applied, "sqlite" if is_sqlite else "mysql")
    return applied


def run_sql_file(path: str, role: str = "etl") -> None:
    """Apply a .sql migration with the engine for `role`."""
    apply_sql(path, get_engine(role))
```

- [ ] **Step 5: Add the v2 columns to existing tables in `sql/001_schema.sql`**

Update the header comment's table count to `29 tables` and add the new groups
(`HARMONISATION`, `WEIGHTS`, `COHORTS`, `AGGREGATES`, `PUBLICATIONS`) to its list.

In `CREATE TABLE IF NOT EXISTS csi_survey`, after the `datamap_hash` line, add:

```sql
  platform      ENUM('forsta','qualtrics','surveymonkey') NOT NULL DEFAULT 'forsta'
                                                   COMMENT 'which platform fielded the wave',
  source_ref    VARCHAR(255) NULL                  COMMENT 'Forsta path, Qualtrics SV_ id or SurveyMonkey id',
  study_type    ENUM('tracker','annual','adhoc') NOT NULL DEFAULT 'tracker',
  load_status   ENUM('loading','verified','failed','superseded') NOT NULL DEFAULT 'verified'
                                                   COMMENT 'only verified waves are shown',
  language      VARCHAR(10)  NOT NULL DEFAULT 'en',
```

and **after** the existing `UNIQUE KEY uq_survey (...)` line (it must stay first), add:

```sql
  UNIQUE KEY uq_survey_source (platform, source_ref, wave_label),
```

In `csi_respondent`, after `dropout_qcode`, add:

```sql
  respondent_key CHAR(64)       NULL              COMMENT 'sha256 of the panel respondent id — never the id itself',
  quality_flag   VARCHAR(40)    NULL              COMMENT 'speeder, straightliner, duplicate …',
```

and after `KEY ix_respondent_completed (...)`, add:

```sql
  KEY ix_respondent_key (survey_id, respondent_key),
```

In `csi_profile`, after `outlook_economy`, add:

```sql
  age_mid           DECIMAL(6,2)  NULL             COMMENT 'midpoint of the age band, for averages',
  income_mid_k      DECIMAL(10,4) NULL             COMMENT 'midpoint of the income band, $000',
```

In `csi_answer`, after `KEY ix_answer_respondent (respondent_id),`, add:

```sql
  KEY ix_answer_cover (survey_id, field_id, value_code, respondent_id),
  FULLTEXT KEY ft_answer_text (value_text),
```

(`ix_answer_cover` lets item incidence and cohort joins be answered from the index alone; the v1 `ix_answer_field` stays — additive only.)

In `csi_load_log`, after `error_text`, add:

```sql
  archive_uri    VARCHAR(1000)   NULL             COMMENT 'untouched source file or payload in Blob',
  archive_sha256 CHAR(64)        NULL,
```

- [ ] **Step 6: Add the 10 new tables to `sql/001_schema.sql`**

Insert this block after the `csi_load_state` table and before the `DYNAMIC SURVEY SUPPORT` section:

```sql
-- ───────────────────────────────────────────────────────────────────────────
-- HARMONISATION — the same question across waves and platforms
-- A grid is stored as one concept per grid row, sharing a concept_group.
-- ───────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS csi_concept (
  concept_id    INT UNSIGNED      NOT NULL AUTO_INCREMENT,
  concept_code  VARCHAR(80)       NOT NULL COMMENT 'BEAUTY_RETAILER_3M',
  concept_name  VARCHAR(255)      NOT NULL,
  concept_group VARCHAR(80)       NULL     COMMENT 'rows of one grid share a group',
  topic_id      SMALLINT UNSIGNED NULL,
  qtype         ENUM('single','multi','grid_single','grid_multi','numeric','text','datetime') NOT NULL,
  description   VARCHAR(1000)     NULL,
  created_at    TIMESTAMP         NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (concept_id),
  UNIQUE KEY uq_concept (concept_code),
  KEY ix_concept_group (concept_group),
  CONSTRAINT fk_concept_topic FOREIGN KEY (topic_id)
    REFERENCES csi_topic (topic_id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Canonical questions, stable across waves and platforms.';

CREATE TABLE IF NOT EXISTS csi_concept_option (
  concept_option_id INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  concept_id        INT UNSIGNED  NOT NULL,
  option_code       VARCHAR(80)   NOT NULL COMMENT 'amazon',
  option_label      VARCHAR(500)  NOT NULL COMMENT 'Amazon.com',
  sort_order        SMALLINT      NOT NULL DEFAULT 0,
  midpoint          DECIMAL(12,4) NULL     COMMENT 'numeric midpoint of a band: 23.5, 74.9995',
  net_group         VARCHAR(50)   NULL     COMMENT 'TOP2, ANY_DRUGSTORE',
  is_nonresponse    TINYINT(1)    NOT NULL DEFAULT 0,
  PRIMARY KEY (concept_option_id),
  UNIQUE KEY uq_concept_option (concept_id, option_code),
  CONSTRAINT fk_coption_concept FOREIGN KEY (concept_id)
    REFERENCES csi_concept (concept_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Canonical answers, with band midpoints.';

CREATE TABLE IF NOT EXISTS csi_concept_map (
  map_id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  survey_id         INT UNSIGNED    NOT NULL,
  map_key           VARCHAR(80)     NOT NULL COMMENT 'question_id:item_id:option_id, 0 when absent',
  question_id       INT UNSIGNED    NOT NULL,
  item_id           INT UNSIGNED    NULL,
  option_id         INT UNSIGNED    NULL,
  concept_id        INT UNSIGNED    NOT NULL,
  concept_option_id INT UNSIGNED    NULL,
  status            ENUM('proposed','confirmed','rejected') NOT NULL DEFAULT 'proposed',
  method            ENUM('exact_text','similar_text','manual') NOT NULL,
  confidence        DECIMAL(5,4)    NULL,
  evidence          VARCHAR(1000)   NULL     COMMENT 'why the harmoniser proposed it',
  reviewed_by       VARCHAR(200)    NULL,
  reviewed_at       DATETIME        NULL,
  created_at        TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (map_id),
  UNIQUE KEY uq_concept_map (survey_id, map_key),
  KEY ix_map_question (survey_id, question_id),
  KEY ix_map_concept_option (concept_option_id),
  KEY ix_map_status (status),
  CONSTRAINT fk_map_survey FOREIGN KEY (survey_id)
    REFERENCES csi_survey (survey_id) ON DELETE CASCADE,
  CONSTRAINT fk_map_question FOREIGN KEY (question_id)
    REFERENCES csi_question (question_id) ON DELETE CASCADE,
  CONSTRAINT fk_map_item FOREIGN KEY (item_id)
    REFERENCES csi_item (item_id) ON DELETE CASCADE,
  CONSTRAINT fk_map_option FOREIGN KEY (option_id)
    REFERENCES csi_option (option_id) ON DELETE CASCADE,
  CONSTRAINT fk_map_concept FOREIGN KEY (concept_id)
    REFERENCES csi_concept (concept_id) ON DELETE CASCADE,
  CONSTRAINT fk_map_coption FOREIGN KEY (concept_option_id)
    REFERENCES csi_concept_option (concept_option_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Wave question/item/option -> canonical concept, proposed or confirmed.';

-- ───────────────────────────────────────────────────────────────────────────
-- WEIGHTS — supported, none applied yet
-- ───────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS csi_weight_scheme (
  scheme_id   INT UNSIGNED NOT NULL AUTO_INCREMENT,
  survey_id   INT UNSIGNED NOT NULL,
  scheme_code VARCHAR(60)  NOT NULL COMMENT 'CENSUS_AGE_GENDER_REGION',
  method      VARCHAR(100) NULL     COMMENT 'raking, cell, …',
  targets     JSON         NULL,
  description VARCHAR(500) NULL,
  created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (scheme_id),
  UNIQUE KEY uq_weight_scheme (survey_id, scheme_code),
  CONSTRAINT fk_wscheme_survey FOREIGN KEY (survey_id)
    REFERENCES csi_survey (survey_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Named weighting schemes, per wave.';

CREATE TABLE IF NOT EXISTS csi_weight (
  respondent_id BIGINT UNSIGNED NOT NULL,
  scheme_id     INT UNSIGNED    NOT NULL,
  weight        DECIMAL(12,6)   NOT NULL,
  PRIMARY KEY (respondent_id, scheme_id),
  KEY ix_weight_scheme (scheme_id),
  CONSTRAINT fk_weight_respondent FOREIGN KEY (respondent_id)
    REFERENCES csi_respondent (respondent_id) ON DELETE CASCADE,
  CONSTRAINT fk_weight_scheme FOREIGN KEY (scheme_id)
    REFERENCES csi_weight_scheme (scheme_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='One weight per respondent per scheme.';

-- ───────────────────────────────────────────────────────────────────────────
-- COHORTS — analyst rules made data ("Beauty shopper")
-- ───────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS csi_cohort_def (
  cohort_id   INT UNSIGNED      NOT NULL AUTO_INCREMENT,
  cohort_code VARCHAR(60)       NOT NULL COMMENT 'BEAUTY_SHOPPER',
  version     SMALLINT UNSIGNED NOT NULL DEFAULT 1,
  cohort_name VARCHAR(200)      NOT NULL,
  rule_json   JSON              NOT NULL COMMENT 'any/all over concepts; see the spec §5.4',
  base_note   VARCHAR(500)      NULL,
  owner_email VARCHAR(200)      NULL,
  is_current  TINYINT(1)        NOT NULL DEFAULT 1,
  created_at  TIMESTAMP         NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (cohort_id),
  UNIQUE KEY uq_cohort_def (cohort_code, version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Named, versioned respondent rules.';

CREATE TABLE IF NOT EXISTS csi_respondent_cohort (
  cohort_id     INT UNSIGNED    NOT NULL,
  respondent_id BIGINT UNSIGNED NOT NULL,
  survey_id     INT UNSIGNED    NOT NULL,
  PRIMARY KEY (cohort_id, respondent_id),
  KEY ix_rcohort_survey (cohort_id, survey_id),
  KEY ix_rcohort_respondent (respondent_id),
  CONSTRAINT fk_rcohort_cohort FOREIGN KEY (cohort_id)
    REFERENCES csi_cohort_def (cohort_id) ON DELETE CASCADE,
  CONSTRAINT fk_rcohort_respondent FOREIGN KEY (respondent_id)
    REFERENCES csi_respondent (respondent_id) ON DELETE CASCADE,
  CONSTRAINT fk_rcohort_survey FOREIGN KEY (survey_id)
    REFERENCES csi_survey (survey_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Materialised cohort membership.';

-- ───────────────────────────────────────────────────────────────────────────
-- AGGREGATES — pre-computed cells for the portal's standard views
-- ───────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS csi_agg_cell (
  cell_id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  survey_id         INT UNSIGNED    NOT NULL,
  cell_key          VARCHAR(200)    NOT NULL COMMENT 'question:item:option:cohort:scheme:dim:value',
  question_id       INT UNSIGNED    NOT NULL,
  item_id           INT UNSIGNED    NULL,
  option_id         INT UNSIGNED    NULL,
  concept_option_id INT UNSIGNED    NULL,
  cohort_id         INT UNSIGNED    NULL     COMMENT 'NULL = all qualified respondents',
  scheme_id         INT UNSIGNED    NULL     COMMENT 'NULL = unweighted',
  dim               VARCHAR(30)     NOT NULL COMMENT 'total, gender, age_band, …',
  dim_value         VARCHAR(120)    NOT NULL,
  n                 INT             NOT NULL,
  base_n            INT             NOT NULL,
  n_weighted        DECIMAL(14,4)   NULL,
  base_weighted     DECIMAL(14,4)   NULL,
  sum_age_mid       DECIMAL(14,4)   NULL,
  sum_income_mid_k  DECIMAL(16,4)   NULL,
  built_at          TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (cell_id),
  UNIQUE KEY uq_agg_cell (survey_id, cell_key),
  KEY ix_agg_concept (concept_option_id, cohort_id, dim, survey_id),
  KEY ix_agg_question (survey_id, question_id, dim),
  CONSTRAINT fk_agg_survey FOREIGN KEY (survey_id)
    REFERENCES csi_survey (survey_id) ON DELETE CASCADE,
  CONSTRAINT fk_agg_question FOREIGN KEY (question_id)
    REFERENCES csi_question (question_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Pre-computed counts per wave x answer x cut x cohort.';

-- ───────────────────────────────────────────────────────────────────────────
-- PUBLICATIONS — frozen deliverables, with drift detection
-- ───────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS csi_publication (
  publication_id INT UNSIGNED      NOT NULL AUTO_INCREMENT,
  pub_code       VARCHAR(80)       NOT NULL COMMENT 'BEAUTY_RETAILER_PROFILE',
  version        SMALLINT UNSIGNED NOT NULL DEFAULT 1,
  pub_name       VARCHAR(255)      NOT NULL,
  owner_email    VARCHAR(200)      NULL,
  definition     JSON              NOT NULL COMMENT 'waves, concepts, cohort, break, scheme, min base',
  footnote       VARCHAR(2000)     NULL,
  destination    VARCHAR(1000)     NULL     COMMENT 'where it was delivered, e.g. SharePoint URL',
  status         ENUM('draft','published','withdrawn') NOT NULL DEFAULT 'draft',
  published_at   DATETIME          NULL,
  created_at     TIMESTAMP         NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (publication_id),
  UNIQUE KEY uq_publication (pub_code, version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='A delivered chart or table, frozen at a version.';

CREATE TABLE IF NOT EXISTS csi_publication_cell (
  cell_id        BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  publication_id INT UNSIGNED    NOT NULL,
  row_key        VARCHAR(250)    NOT NULL,
  col_key        VARCHAR(250)    NOT NULL,
  n              INT             NULL,
  base_n         INT             NULL,
  value          DECIMAL(18,6)   NULL,
  PRIMARY KEY (cell_id),
  UNIQUE KEY uq_publication_cell (publication_id, row_key, col_key),
  CONSTRAINT fk_pcell_publication FOREIGN KEY (publication_id)
    REFERENCES csi_publication (publication_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='The frozen numbers of a publication.';
```

- [ ] **Step 7: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_schema_v2.py -v`
Expected: 3 passed.

- [ ] **Step 8: Run the whole suite — v1 behaviour must be unchanged**

Run: `APP_ENV=LOCAL LOCAL_SQLITE_PATH=data/csi_local.db .venv/bin/python -m pytest -q`
Expected: all pass (53 before this phase + 3 new).

- [ ] **Step 9: Checkpoint (no commit)**

`git status --short` — expected: `app/core/database.py`, `sql/001_schema.sql`, `tests/fixtures/schema_v1.sql`, `tests/test_schema_v2.py`, plus Task 1's files.

---

### Task 3: In-place upgrade of an existing v1 database

**Files:**
- Create: `app/core/schema_upgrade.py`
- Test: `tests/test_schema_v2.py`

**Interfaces:**
- Consumes: `sqlite_compat.convert_column_def` (Task 1), `database.apply_sql` (Task 2).
- Produces:
  - `schema_upgrade.plan(engine: Engine) -> list[str]` — the statements that would bring this database to v2 (empty of DDL when already v2).
  - `schema_upgrade.install(engine: Engine, dry_run: bool = False, force: bool = False) -> list[str]` — refuses while a load is running (raises `RuntimeError`) unless `force`; runs the plan, then `001_schema.sql`, `002_views.sql`, `003_seed_topics.sql`; returns what it ran (or would run).
  - `schema_upgrade.SQL_FILES: list[Path]` — the ordered schema files.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_schema_v2.py`:

```python
import pytest

from app.core import schema_upgrade


def v1_database(tmp_path, name: str = "v1.db") -> sa.Engine:
    """A database exactly as v1 left it, with one real wave in it."""
    engine = sqlite_engine(tmp_path, name)
    apply_sql(SCHEMA_V1, engine)
    with engine.begin() as conn:
        conn.execute(sa.text(
            "INSERT INTO csi_survey (forsta_host, forsta_path, title, wave_label, status)"
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
            "SELECT platform, source_ref, load_status, study_type FROM csi_survey")).one()
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
            "INSERT INTO csi_load_log (source_type, object_type, status)"
            " VALUES ('excel', 'data', 'running')"))
    with pytest.raises(RuntimeError, match="load is running"):
        schema_upgrade.install(engine)
    schema_upgrade.install(engine, force=True)          # the operator's override
    assert "platform" in columns(engine)["csi_survey"]


def test_dry_run_writes_nothing(tmp_path):
    engine = v1_database(tmp_path)
    planned = schema_upgrade.install(engine, dry_run=True)
    assert any("ADD COLUMN platform" in s for s in planned)
    assert "platform" not in columns(engine)["csi_survey"]
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_schema_v2.py -v`
Expected: the five new tests FAIL with `ImportError: cannot import name 'schema_upgrade'`.

- [ ] **Step 3: Implement `app/core/schema_upgrade.py`**

```python
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

# (table, column, MySQL definition) — the v2 columns on v1 tables
COLUMNS: list[tuple[str, str, str]] = [
    ("csi_survey", "platform",
     "ENUM('forsta','qualtrics','surveymonkey') NOT NULL DEFAULT 'forsta'"),
    ("csi_survey", "source_ref", "VARCHAR(255) NULL"),
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
]

# v1 waves all came from Forsta: their path is their source reference.
# Runs before the unique key below, so no row enters it with a NULL.
BACKFILL = ["UPDATE csi_survey SET source_ref = forsta_path WHERE source_ref IS NULL"]

# (table, index, kind, columns)
INDEXES: list[tuple[str, str, str, str]] = [
    ("csi_survey", "uq_survey_source", "UNIQUE", "platform, source_ref, wave_label"),
    ("csi_respondent", "ix_respondent_key", "INDEX", "survey_id, respondent_key"),
    ("csi_answer", "ix_answer_cover", "INDEX", "survey_id, field_id, value_code, respondent_id"),
    ("csi_answer", "ft_answer_text", "FULLTEXT", "value_text"),
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_schema_v2.py -v`
Expected: 8 passed.

- [ ] **Step 5: Checkpoint (no commit)**

`git status --short` — adds `app/core/schema_upgrade.py`.

---

### Task 4: Wire it in — `init_db.py` and the survey upsert

**Files:**
- Modify: `scripts/init_db.py`
- Modify: `etl/loaders.py` (`upsert_survey`)
- Test: `tests/test_schema_v2.py`

**Interfaces:**
- Consumes: `schema_upgrade.install(engine, dry_run, force)` (Task 3).
- Produces: `upsert_survey(host, path, title, survey_family=None, wave_label=None, wave_date=None, datamap_payload=None, platform="forsta", source_ref=None) -> int` — `source_ref` defaults to `path`. Existing callers keep working unchanged.
- Produces: `python scripts/init_db.py [--dry-run] [--force]`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_schema_v2.py`:

```python
from app.core import database


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
            "SELECT survey_id, platform, source_ref, title FROM csi_survey ORDER BY survey_id")).all()
    assert [tuple(r)[1:] for r in rows] == [
        ("forsta", "selfserve/58f/260908", "Shopping and Spending (retitled)"),
        ("qualtrics", "SV_0IHGTy1GPAlUsGa", "Beauty + Shrink"),
    ]
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_schema_v2.py::test_upsert_survey_records_platform_and_updates_in_place -v`
Expected: FAIL with `TypeError: upsert_survey() got an unexpected keyword argument 'platform'`.

- [ ] **Step 3: Update `upsert_survey` in `etl/loaders.py`**

Change the signature and the INSERT (keep everything else as it is):

```python
def upsert_survey(
    host: str,
    path: str,
    title: str,
    survey_family: Optional[str] = None,
    wave_label: Optional[str] = None,
    wave_date: Optional[str] = None,
    datamap_payload: Any = None,
    platform: str = "forsta",
    source_ref: Optional[str] = None,
) -> int:
```

```python
    sql = text(
        """
        INSERT INTO csi_survey
            (forsta_host, forsta_path, title, survey_family, wave_label, wave_date,
             datamap_hash, platform, source_ref)
        VALUES (:host, :path, :title, :family, :wave, :wave_date, :digest,
                :platform, :source_ref)
        ON DUPLICATE KEY UPDATE
            title = VALUES(title),
            survey_family = COALESCE(VALUES(survey_family), survey_family),
            wave_label = COALESCE(VALUES(wave_label), wave_label),
            wave_date = COALESCE(VALUES(wave_date), wave_date),
            datamap_hash = COALESCE(VALUES(datamap_hash), datamap_hash),
            platform = VALUES(platform),
            source_ref = VALUES(source_ref),
            survey_id = LAST_INSERT_ID(survey_id)
        """
    )
```

and add to the parameter dict passed to `conn.execute(sql, {...})`:

```python
                "platform": platform, "source_ref": source_ref or path,
```

- [ ] **Step 4: Update `scripts/init_db.py`**

Replace the file with:

```python
"""Create or upgrade the CSI schema in the STG (DWH) database.

    python scripts/init_db.py            # upgrade in place, then apply schema + views + seed
    python scripts/init_db.py --dry-run  # print what would run
    python scripts/init_db.py --force    # run even though csi_load_log shows a running load
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core import schema_upgrade              # noqa: E402
from app.core.config import config               # noqa: E402
from app.core.database import get_engine, healthcheck  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="ignore a csi_load_log row stuck in 'running'")
    args = ap.parse_args()

    print(f"Environment: {config.environment.value}")
    ok, msg = healthcheck("etl")
    print(f"Database:    {msg}")
    if not ok:
        print("\nCannot connect. Fill in STG_DB_* in .env — see .env.example.")
        return 1

    try:
        ran = schema_upgrade.install(get_engine("etl"), dry_run=args.dry_run, force=args.force)
    except RuntimeError as exc:
        print(f"\nRefused: {exc}")
        return 2
    for statement in ran:
        print(("[dry-run] " if args.dry_run else "applied   ") + statement)
    print("\nDone. 004_grants.sql is intentionally NOT applied — hand it to the DBA.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run the phase tests and the full suite**

Run: `.venv/bin/python -m pytest tests/test_schema_v2.py -v`
Expected: 9 passed.

Rebuild the local copy through the new path and run everything:
```bash
export APP_ENV=LOCAL LOCAL_SQLITE_PATH=data/csi_local.db
rm -f data/csi_local.db
.venv/bin/python scripts/init_db.py
.venv/bin/python -m etl.run_pipeline --source excel --raw ~/Downloads/"Raw Data 09_21_26.xlsx" --crosstab ~/Downloads/"Cross Tabs 09_21_26.xlsx" --wave 2026-09-21
.venv/bin/python -m etl.run_pipeline --source excel --raw ~/Downloads/"raw data 09-28-2026 2.xlsx" --crosstab ~/Downloads/"Shopping and Spending - inc Beauty + Holiday + Inflation + Cross tab 09-28- 2026  2.xlsx" --wave 2026-09-28
.venv/bin/python scripts/reconcile.py
CSI_TEST_RAW=~/Downloads/"Raw Data 09_21_26.xlsx" CSI_TEST_XTAB=~/Downloads/"Cross Tabs 09_21_26.xlsx" .venv/bin/python -m pytest -q
```
Expected: reconcile prints `667/667` and `788/788`; pytest all pass (62 = 53 + 9).

- [ ] **Step 6: Checkpoint (no commit)**

`git status --short` — adds `scripts/init_db.py`, `etl/loaders.py`.

---

### Task 5: Apply to `dwh_stg` and prove nothing moved

**Files:** none changed — an operational run. Needs VPN; confirm TCP first.

**Interfaces:**
- Consumes: `scripts/init_db.py` (Task 4), `scripts/reconcile.py` (existing).

- [ ] **Step 1: Pre-flight — reachability and no load running**

```bash
nc -z -G 5 csr-mysql8-flex-stg.mysql.database.azure.com 3306 && echo TCP_OK
.venv/bin/python scripts/test_connection.py
```
Expected: `TCP_OK`; `✓ connected (MySQL 8.0.45-azure)` as `dwh_app_access` on `dwh_stg`. If TCP fails, reconnect the VPN and stop.

- [ ] **Step 2: Record the before-state**

```bash
.venv/bin/python - <<'EOF' | tee /tmp/csi_before.txt
import sys; sys.path.insert(0, ".")
from app.core.database import get_engine
from sqlalchemy import text
with get_engine("etl").connect() as c:
    q = lambda s: c.execute(text(s)).scalar()
    print("tables", q("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='dwh_stg' AND table_name LIKE 'csi\\_%' AND table_type='BASE TABLE'"))
    for t in ["csi_survey", "csi_question", "csi_field", "csi_respondent", "csi_profile", "csi_answer", "csi_crosstab"]:
        print(t, q(f"SELECT COUNT(*) FROM {t}"))
    print("running_loads", q("SELECT COUNT(*) FROM csi_load_log WHERE status='running'"))
EOF
```
Expected: `tables 19`, `csi_survey 2`, `csi_respondent 807`, `csi_crosstab 68680`, `running_loads 0`. If `running_loads` > 0, find out why before continuing.

- [ ] **Step 3: Dry run**

Run: `.venv/bin/python scripts/init_db.py --dry-run`
Expected: 11 `ALTER TABLE … ADD COLUMN …` lines, 1 `UPDATE csi_survey SET source_ref …`, 4 `ALTER TABLE … ADD … KEY …` lines (`uq_survey_source`, `ix_respondent_key`, `ix_answer_cover`, `ft_answer_text`), then `-- apply 001_schema.sql`, `002_views.sql`, `003_seed_topics.sql`.

- [ ] **Step 4: Run it**

Run: `time .venv/bin/python scripts/init_db.py`
Expected: every statement printed as `applied`, `Done.`; exit 0. (`ix_answer_cover` and the FULLTEXT key each rebuild part of `csi_answer`, ~300k rows — expect under a minute over the VPN.)

- [ ] **Step 5: Verify the after-state**

Re-run the Step 2 script into `/tmp/csi_after.txt` and compare:
```bash
diff /tmp/csi_before.txt /tmp/csi_after.txt
```
Expected: exactly one difference — `tables 19` → `tables 29`. Every row count identical.

Then check the catalogue:
```bash
.venv/bin/python - <<'EOF'
import sys; sys.path.insert(0, ".")
from app.core.database import get_engine
from sqlalchemy import text
with get_engine("etl").connect() as c:
    print(c.execute(text("SELECT survey_id, platform, source_ref, load_status FROM csi_survey")).all())
    print(c.execute(text("SELECT index_name, index_type FROM information_schema.statistics WHERE table_schema='dwh_stg' AND index_name IN ('uq_survey_source','ix_respondent_key','ix_answer_cover','ft_answer_text') GROUP BY index_name, index_type")).all())
EOF
```
Expected: both waves `('forsta', 'selfserve/58f/260908', 'verified')`; four indexes, `ft_answer_text` of type `FULLTEXT`.

- [ ] **Step 6: Re-run is a no-op**

Run: `.venv/bin/python scripts/init_db.py --dry-run`
Expected: no `ALTER` lines — only the backfill `UPDATE` and the `-- apply …` lines.

- [ ] **Step 7: Every published number still reproduces**

Run: `.venv/bin/python scripts/reconcile.py; echo "exit=$?"`
Expected: `667/667` (2026-09-21), `788/788` (2026-09-28), 36/38 banner columns with the 2 known Forsta differences, `exit=0`.

- [ ] **Step 8: The portal still works on `dwh_stg`**

Restart the portal (`lsof -ti :8502 | xargs kill; .venv/bin/streamlit run app/main.py --server.port 8502`), open `http://localhost:8502/`, `/analysis`, `/crosstabs`, `/trends`, `/data-health` in the browser pane. Expected: every page renders, no "error" text, header shows `connected (MySQL 8.0.45-azure)`; Overview shows 403 qualified for 2026-09-28.

---

### Task 6: Documentation

**Files:**
- Modify: `docs/superpowers/specs/2026-09-29-survey-platform-design.md`
- Modify: `docs/02-schema-design.md` (top of file)
- Modify: `README.md` (Status table)

- [ ] **Step 1: Record the clarifications this plan made in the spec**

In §5.3 of the spec, change `csi_weight | … respondent_id, scheme_code, weight` to `respondent_id, scheme_id, weight` (a foreign key to `csi_weight_scheme`). In §5.4, change `csi_respondent_cohort | … cohort_code, version` to `cohort_id` (which identifies code + version). In §5.2 add one line: *"A grid is stored as one concept per grid row; rows of one grid share `concept_group`."* In §5.2/§5.5 add: *"Unique keys use a computed `map_key` / `cell_key` because MySQL allows repeated NULLs in unique indexes."* In §5.1 add: *"`load_status` defaults to `verified` until the Phase 3 loader sets `loading` → `verified`."*

- [ ] **Step 2: Point the v1 schema doc at v2**

Add under the title of `docs/02-schema-design.md`:
`> Schema v2 (29 tables) is live in dwh_stg — see docs/superpowers/specs/2026-09-29-survey-platform-design.md §5. This document describes the 19 v1 tables, all of which v2 keeps unchanged.`

- [ ] **Step 3: README status**

In `README.md`'s Status table, change the Database row to:
`| Database | **dwh_stg**, account dwh_app_access — schema v2: 29 csi_ tables + 8 v_csi_ views (Phase 1 of the survey platform design) |`

- [ ] **Step 4: Final checkpoint (no commit)**

Run: `git status --short`
Expected changed/new files, and only these:
```
M  README.md
M  app/core/database.py
M  app/core/sqlite_compat.py
A  app/core/schema_upgrade.py
M  docs/02-schema-design.md
M  docs/superpowers/specs/2026-09-29-survey-platform-design.md
M  etl/loaders.py
M  scripts/init_db.py
M  sql/001_schema.sql
A  tests/fixtures/schema_v1.sql
A  tests/test_schema_v2.py
```
Hand this list to the user for their commit.
