-- ═══════════════════════════════════════════════════════════════════════════
-- Consumer Insight Portal (CIP) — STG (DWH) schema
-- Target: MySQL 8.0+ (Azure Database for MySQL Flexible Server)
-- Charset: utf8mb4 (survey text contains curly quotes, e.g. "Smith's")
--
-- 16 tables in 4 layers:
--   A. DEFINITION  — what was asked      (survey, group, question, row, option, variable)
--   B. FACT        — what people said    (respondent, profile, response)
--   C. AGGREGATE   — pre-computed tables (banner, segment, crosstab_run, crosstab_cell)
--   D. OPS         — how it got here     (ingest_run, ingest_reject, datafeed_state)
-- ═══════════════════════════════════════════════════════════════════════════

SET NAMES utf8mb4;

-- ───────────────────────────────────────────────────────────────────────────
-- A. DEFINITION LAYER  (sourced from Forsta /datamap)
-- ───────────────────────────────────────────────────────────────────────────

-- A1. One row per survey wave. Everything else hangs off this.
CREATE TABLE IF NOT EXISTS cip_survey (
  survey_id        INT UNSIGNED    NOT NULL AUTO_INCREMENT,
  forsta_host      VARCHAR(100)    NOT NULL COMMENT 'e.g. se1.decipherinc.com',
  forsta_path      VARCHAR(255)    NOT NULL COMMENT 'e.g. selfserve/58f/260908',
  survey_title     VARCHAR(500)    NOT NULL,
  survey_family    VARCHAR(100)    NULL COMMENT 'e.g. CSI-US — groups waves for trending',
  wave_label       VARCHAR(50)     NULL COMMENT 'e.g. 2026-09',
  wave_date        DATE            NULL COMMENT 'nominal field date, used for trend x-axis',
  field_start      DATETIME        NULL,
  field_end        DATETIME        NULL,
  country          CHAR(2)         NULL DEFAULT 'US',
  status           ENUM('draft','fielding','closed','archived') NOT NULL DEFAULT 'closed',
  datamap_hash     CHAR(64)        NULL COMMENT 'sha256 of datamap JSON; detects questionnaire change',
  created_at       TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at       TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (survey_id),
  UNIQUE KEY uq_survey_path (forsta_host, forsta_path),
  KEY ix_survey_family_wave (survey_family, wave_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='One row per Forsta survey wave.';

-- A2. Editorial grouping of questions into report modules.
--     Lets the portal show "Department Stores" / "BNPL" / "GLP-1" sections
--     instead of a flat list of 93 question codes.
CREATE TABLE IF NOT EXISTS cip_question_group (
  group_id         SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
  group_code       VARCHAR(40)     NOT NULL COMMENT 'e.g. DEPT_STORES',
  group_name       VARCHAR(150)    NOT NULL COMMENT 'e.g. Department Stores',
  is_system        TINYINT(1)      NOT NULL DEFAULT 0 COMMENT '1 = paradata/quota, hidden by default',
  display_order    SMALLINT        NOT NULL DEFAULT 0,
  PRIMARY KEY (group_id),
  UNIQUE KEY uq_group_code (group_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Report modules that questions are bucketed into.';

-- A3. One row per question as the analyst thinks of it (q1, DP7, CS1, D5...).
CREATE TABLE IF NOT EXISTS cip_question (
  question_id      INT UNSIGNED    NOT NULL AUTO_INCREMENT,
  survey_id        INT UNSIGNED    NOT NULL,
  group_id         SMALLINT UNSIGNED NULL,
  qcode            VARCHAR(50)     NOT NULL COMMENT 'Forsta question label: q1, DP7, CS1, D28r8oe',
  qtext            TEXT            NOT NULL COMMENT 'full question wording',
  qtext_short      VARCHAR(255)    NULL COMMENT 'analyst-friendly chart title',
  qtype            ENUM('single','multi','grid_single','grid_multi','numeric','text','datetime')
                                   NOT NULL,
  value_min        INT             NULL COMMENT 'from datamap "Values: 1-6"',
  value_max        INT             NULL,
  is_system        TINYINT(1)      NOT NULL DEFAULT 0 COMMENT '1 = record/uuid/vos/qtime/quota vars',
  is_multi_punch   TINYINT(1)      NOT NULL DEFAULT 0 COMMENT '1 = respondent may pick several',
  base_description VARCHAR(255)    NULL COMMENT 'e.g. "BNPL users in past 12 months"',
  display_order    SMALLINT        NOT NULL DEFAULT 0,
  created_at       TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (question_id),
  UNIQUE KEY uq_question (survey_id, qcode),
  KEY ix_question_group (group_id),
  CONSTRAINT fk_question_survey FOREIGN KEY (survey_id)
    REFERENCES cip_survey (survey_id) ON DELETE CASCADE,
  CONSTRAINT fk_question_group FOREIGN KEY (group_id)
    REFERENCES cip_question_group (group_id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='One row per question/variable family.';

-- A4. Statement rows inside a multi-punch list or grid.
--     e.g. q1r1 "Met up with friends"; DP7r3 = a retailer rated on a 1-5 scale.
CREATE TABLE IF NOT EXISTS cip_question_row (
  row_id           INT UNSIGNED    NOT NULL AUTO_INCREMENT,
  question_id      INT UNSIGNED    NOT NULL,
  row_code         VARCHAR(50)     NOT NULL COMMENT 'e.g. q1r1, DP7r3',
  row_label        VARCHAR(1000)   NOT NULL,
  row_label_short  VARCHAR(255)    NULL COMMENT 'trimmed label for axis ticks',
  is_exclusive     TINYINT(1)      NOT NULL DEFAULT 0 COMMENT '1 = "None of these" — exclude from ranking',
  is_other_specify TINYINT(1)      NOT NULL DEFAULT 0,
  display_order    SMALLINT        NOT NULL DEFAULT 0,
  PRIMARY KEY (row_id),
  UNIQUE KEY uq_question_row (question_id, row_code),
  CONSTRAINT fk_row_question FOREIGN KEY (question_id)
    REFERENCES cip_question (question_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Statement/item rows within a list or grid question.';

-- A5. The code -> label map for every coded answer.
--     Binary lists: 0=Unchecked, 1=Checked. Scales: 1=Much worse ... 6=Don't know.
CREATE TABLE IF NOT EXISTS cip_answer_option (
  option_id        INT UNSIGNED    NOT NULL AUTO_INCREMENT,
  question_id      INT UNSIGNED    NOT NULL,
  value_code       INT             NOT NULL,
  value_label      VARCHAR(500)    NOT NULL,
  is_nonresponse   TINYINT(1)      NOT NULL DEFAULT 0 COMMENT "1 = Don't know / Prefer not to say — excluded from Top-2-Box",
  net_group        VARCHAR(50)     NULL COMMENT 'e.g. TOP2, BOT2 — drives net calculations',
  display_order    SMALLINT        NOT NULL DEFAULT 0,
  PRIMARY KEY (option_id),
  UNIQUE KEY uq_answer_option (question_id, value_code),
  CONSTRAINT fk_option_question FOREIGN KEY (question_id)
    REFERENCES cip_question (question_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Code/label dictionary per question.';

-- A6. The physical column map: one row per column in the Forsta flat export.
--     This is the bridge between "q1r1" in a CSV header and the question model.
CREATE TABLE IF NOT EXISTS cip_variable (
  variable_id      INT UNSIGNED    NOT NULL AUTO_INCREMENT,
  survey_id        INT UNSIGNED    NOT NULL,
  question_id      INT UNSIGNED    NULL COMMENT 'NULL for pure paradata columns',
  row_id           INT UNSIGNED    NULL COMMENT 'set when the column is one row of a list/grid',
  variable_name    VARCHAR(100)    NOT NULL COMMENT 'exact export column header, e.g. q1r1, D2, uuid',
  storage_type     ENUM('code','numeric','text','datetime') NOT NULL,
  column_position  SMALLINT        NULL COMMENT 'ordinal in the export, for round-trip checks',
  PRIMARY KEY (variable_id),
  UNIQUE KEY uq_variable (survey_id, variable_name),
  KEY ix_variable_question (question_id),
  KEY ix_variable_row (row_id),
  CONSTRAINT fk_variable_survey FOREIGN KEY (survey_id)
    REFERENCES cip_survey (survey_id) ON DELETE CASCADE,
  CONSTRAINT fk_variable_question FOREIGN KEY (question_id)
    REFERENCES cip_question (question_id) ON DELETE CASCADE,
  CONSTRAINT fk_variable_row FOREIGN KEY (row_id)
    REFERENCES cip_question_row (row_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Flat-export column -> question/row mapping.';


-- ───────────────────────────────────────────────────────────────────────────
-- B. FACT LAYER  (sourced from Forsta /data — the "raw data" file)
-- ───────────────────────────────────────────────────────────────────────────

-- B1. One row per interview.
CREATE TABLE IF NOT EXISTS cip_respondent (
  respondent_id    BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  survey_id        INT UNSIGNED    NOT NULL,
  forsta_record    INT UNSIGNED    NOT NULL COMMENT 'Forsta [record] number',
  forsta_uuid      VARCHAR(64)     NULL     COMMENT 'Forsta [uuid] participant identifier',
  status_code      TINYINT         NULL     COMMENT '1 Terminated, 2 Overquota, 3 Qualified, 4 Partial',
  status_label     VARCHAR(30)     NULL,
  is_qualified     TINYINT(1)      NOT NULL DEFAULT 0 COMMENT 'status_code = 3; default analysis base',
  started_at       DATETIME        NULL,
  completed_at     DATETIME        NULL,
  interview_secs   INT             NULL     COMMENT 'from qtime',
  panel_source     VARCHAR(100)    NULL,
  sample_rid       VARCHAR(100)    NULL     COMMENT 'panel-provider respondent id',
  markers          VARCHAR(1000)   NULL     COMMENT 'raw Forsta marker string (quota buckets)',
  device_category  VARCHAR(50)     NULL,
  operating_system VARCHAR(100)    NULL,
  browser          VARCHAR(100)    NULL,
  last_seen_qcode  VARCHAR(50)     NULL     COMMENT 'from vdropout',
  ingest_run_id    BIGINT UNSIGNED NULL,
  ingested_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (respondent_id),
  UNIQUE KEY uq_respondent (survey_id, forsta_record),
  KEY ix_respondent_qualified (survey_id, is_qualified),
  KEY ix_respondent_completed (survey_id, completed_at),
  CONSTRAINT fk_respondent_survey FOREIGN KEY (survey_id)
    REFERENCES cip_survey (survey_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='One row per interview, incl. paradata.';

-- B2. Denormalised demographics — the columns the portal filters on constantly.
--     Derived from D1-D8/CS1 at load time so charts never join 8 EAV rows per person.
CREATE TABLE IF NOT EXISTS cip_respondent_profile (
  respondent_id    BIGINT UNSIGNED NOT NULL,
  survey_id        INT UNSIGNED    NOT NULL,
  gender           VARCHAR(40)     NULL COMMENT 'D1',
  age_years        SMALLINT        NULL COMMENT 'D2 resolved to a number',
  age_band         VARCHAR(20)     NULL COMMENT '18-29 / 30-44 / 45-60 / Over 60',
  generation       VARCHAR(20)     NULL COMMENT 'GenZ / Millennial / GenX / Boomer',
  relationship     VARCHAR(60)     NULL COMMENT 'D3',
  ethnicity        VARCHAR(60)     NULL COMMENT 'D4',
  income_band      VARCHAR(40)     NULL COMMENT 'D5',
  urbanicity       VARCHAR(20)     NULL COMMENT 'D6: Urban/Suburban/Rural',
  political        VARCHAR(120)    NULL COMMENT 'D7',
  state_name       VARCHAR(60)     NULL COMMENT 'D8',
  census_region    VARCHAR(20)     NULL COMMENT 'South/West/Northeast/Midwest, derived from D8',
  sentiment_income VARCHAR(40)     NULL COMMENT 'CS1 discretionary-income outlook',
  sentiment_economy VARCHAR(40)    NULL COMMENT 'CS2 economy outlook',
  weight           DECIMAL(10,6)   NOT NULL DEFAULT 1.000000 COMMENT 'reserved for future weighting',
  PRIMARY KEY (respondent_id),
  KEY ix_profile_cuts (survey_id, generation, gender, income_band),
  KEY ix_profile_region (survey_id, census_region),
  CONSTRAINT fk_profile_respondent FOREIGN KEY (respondent_id)
    REFERENCES cip_respondent (respondent_id) ON DELETE CASCADE,
  CONSTRAINT fk_profile_survey FOREIGN KEY (survey_id)
    REFERENCES cip_survey (survey_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Flattened demographic cuts for fast filtering.';

-- B3. The long/EAV answer fact. ~375 variables x N respondents per wave.
--     Long format is what makes arbitrary charting possible without DDL changes
--     when the questionnaire changes wave to wave.
CREATE TABLE IF NOT EXISTS cip_response (
  response_id      BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  respondent_id    BIGINT UNSIGNED NOT NULL,
  survey_id        INT UNSIGNED    NOT NULL COMMENT 'denormalised for partition/filter speed',
  variable_id      INT UNSIGNED    NOT NULL,
  value_code       INT             NULL COMMENT 'coded answer (0/1, 1-5, 1-54)',
  value_label      VARCHAR(500)    NULL COMMENT 'resolved label, denormalised for display',
  value_numeric    DECIMAL(18,4)   NULL COMMENT 'open numeric responses',
  value_text       TEXT            NULL COMMENT 'open-ended verbatims (…oe variables)',
  PRIMARY KEY (response_id),
  UNIQUE KEY uq_response (respondent_id, variable_id),
  KEY ix_response_var_code (survey_id, variable_id, value_code),
  KEY ix_response_respondent (respondent_id),
  CONSTRAINT fk_response_respondent FOREIGN KEY (respondent_id)
    REFERENCES cip_respondent (respondent_id) ON DELETE CASCADE,
  CONSTRAINT fk_response_variable FOREIGN KEY (variable_id)
    REFERENCES cip_variable (variable_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='One row per respondent x variable. The core fact table.';


-- ───────────────────────────────────────────────────────────────────────────
-- C. AGGREGATE LAYER  (the "filtered data" / cross-tab file)
-- ───────────────────────────────────────────────────────────────────────────

-- C1. A banner = one column group across the top of a cross-tab.
CREATE TABLE IF NOT EXISTS cip_banner (
  banner_id        INT UNSIGNED    NOT NULL AUTO_INCREMENT,
  survey_id        INT UNSIGNED    NOT NULL,
  banner_code      VARCHAR(50)     NOT NULL COMMENT 'e.g. AGE, GENDER, INCOME',
  banner_name      VARCHAR(500)    NOT NULL COMMENT 'header text, e.g. "What is your age group?"',
  source_qcode     VARCHAR(50)     NULL COMMENT 'question the banner is built from',
  display_order    SMALLINT        NOT NULL DEFAULT 0,
  PRIMARY KEY (banner_id),
  UNIQUE KEY uq_banner (survey_id, banner_code),
  CONSTRAINT fk_banner_survey FOREIGN KEY (survey_id)
    REFERENCES cip_survey (survey_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Cross-tab column groups (Gender, Age, Income, Region...).';

-- C2. A segment = one column. Carries the Forsta definition expression verbatim
--     so an analyst can audit exactly how "GenZ" was defined for that wave.
CREATE TABLE IF NOT EXISTS cip_segment (
  segment_id       INT UNSIGNED    NOT NULL AUTO_INCREMENT,
  banner_id        INT UNSIGNED    NOT NULL,
  survey_id        INT UNSIGNED    NOT NULL,
  segment_letter   VARCHAR(4)      NULL COMMENT 'stat-test letter: A, B, ... A1, N1',
  segment_label    VARCHAR(255)    NOT NULL COMMENT 'e.g. Male, GenZ, $50,000 - $99,999',
  definition_expr  VARCHAR(2000)   NULL COMMENT 'Forsta expression, e.g. (D2.ch12 or D2.ch10 ...)',
  base_n           INT             NULL COMMENT 'unweighted base from the Summary sheet',
  is_total         TINYINT(1)      NOT NULL DEFAULT 0,
  low_base_flag    ENUM('','*','**') NOT NULL DEFAULT '' COMMENT '* = caution, ** = too small to report',
  display_order    SMALLINT        NOT NULL DEFAULT 0,
  PRIMARY KEY (segment_id),
  UNIQUE KEY uq_segment (banner_id, segment_label),
  KEY ix_segment_survey (survey_id),
  CONSTRAINT fk_segment_banner FOREIGN KEY (banner_id)
    REFERENCES cip_banner (banner_id) ON DELETE CASCADE,
  CONSTRAINT fk_segment_survey FOREIGN KEY (survey_id)
    REFERENCES cip_survey (survey_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Cross-tab columns with their Forsta definitions and bases.';

-- C3. Header of a cross-tab run — the Summary sheet settings.
--     Matters because a percentage is meaningless without its base definition.
CREATE TABLE IF NOT EXISTS cip_crosstab_run (
  run_id           INT UNSIGNED    NOT NULL AUTO_INCREMENT,
  survey_id        INT UNSIGNED    NOT NULL,
  run_label        VARCHAR(255)    NOT NULL,
  respondent_base  VARCHAR(100)    NULL COMMENT 'e.g. "Qualified Only"',
  additional_filter VARCHAR(500)   NULL,
  table_set        VARCHAR(100)    NULL COMMENT 'e.g. "All"',
  percentage_base  VARCHAR(100)    NULL COMMENT 'e.g. "Total Answering"',
  stat_test_levels VARCHAR(100)    NULL COMMENT 'e.g. "None / None (z-test)"',
  date_range_start DATE            NULL,
  date_range_end   DATE            NULL,
  source_type      ENUM('api','excel') NOT NULL DEFAULT 'excel',
  source_file      VARCHAR(255)    NULL,
  is_current       TINYINT(1)      NOT NULL DEFAULT 1,
  created_at       TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (run_id),
  KEY ix_ctrun_survey (survey_id, is_current),
  CONSTRAINT fk_ctrun_survey FOREIGN KEY (survey_id)
    REFERENCES cip_survey (survey_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='One row per cross-tab export, with its base/filter settings.';

-- C4. The numbers. One row per cell of every cross-tab.
CREATE TABLE IF NOT EXISTS cip_crosstab_cell (
  cell_id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  run_id           INT UNSIGNED    NOT NULL,
  survey_id        INT UNSIGNED    NOT NULL,
  question_id      INT UNSIGNED    NOT NULL,
  row_id           INT UNSIGNED    NULL COMMENT 'NULL for single-punch questions',
  option_id        INT UNSIGNED    NULL COMMENT 'set for scale questions / grid scale points',
  segment_id       INT UNSIGNED    NOT NULL,
  stub_label       VARCHAR(1000)   NOT NULL COMMENT 'row label as printed, incl. Net/Mean/Count rows',
  stub_kind        ENUM('item','net','mean','count','base') NOT NULL DEFAULT 'item',
  pct              DECIMAL(9,6)    NULL COMMENT '0.527228 = 52.7%',
  count_n          INT             NULL COMMENT 'from the Counts sheet',
  base_n           INT             NULL,
  sig_against      VARCHAR(40)     NULL COMMENT 'stat-test letters this cell beats, e.g. "BD"',
  PRIMARY KEY (cell_id),
  UNIQUE KEY uq_cell (run_id, question_id, stub_label, segment_id),
  KEY ix_cell_lookup (survey_id, question_id, segment_id),
  KEY ix_cell_row (row_id),
  CONSTRAINT fk_cell_run FOREIGN KEY (run_id)
    REFERENCES cip_crosstab_run (run_id) ON DELETE CASCADE,
  CONSTRAINT fk_cell_question FOREIGN KEY (question_id)
    REFERENCES cip_question (question_id) ON DELETE CASCADE,
  CONSTRAINT fk_cell_segment FOREIGN KEY (segment_id)
    REFERENCES cip_segment (segment_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Pre-computed cross-tab cells: percentages, counts, bases, sig letters.';


-- ───────────────────────────────────────────────────────────────────────────
-- D. OPS LAYER
-- ───────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS cip_ingest_run (
  ingest_run_id    BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  survey_id        INT UNSIGNED    NULL,
  source_type      ENUM('api','excel','manual') NOT NULL,
  object_type      ENUM('datamap','data','crosstab','profile') NOT NULL,
  source_ref       VARCHAR(500)    NULL COMMENT 'endpoint URL or file name',
  records_read     INT             NOT NULL DEFAULT 0,
  records_loaded   INT             NOT NULL DEFAULT 0,
  records_rejected INT             NOT NULL DEFAULT 0,
  status           ENUM('running','success','partial','failed') NOT NULL DEFAULT 'running',
  error_text       TEXT            NULL,
  started_at       DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  finished_at      DATETIME        NULL,
  PRIMARY KEY (ingest_run_id),
  KEY ix_ingest_survey (survey_id, object_type, started_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Audit trail for every load. Nothing enters CIP without a row here.';

CREATE TABLE IF NOT EXISTS cip_ingest_reject (
  reject_id        BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  ingest_run_id    BIGINT UNSIGNED NOT NULL,
  record_ref       VARCHAR(200)    NULL COMMENT 'record no / sheet!cell',
  reason           VARCHAR(500)    NOT NULL,
  payload          JSON            NULL,
  PRIMARY KEY (reject_id),
  KEY ix_reject_run (ingest_run_id),
  CONSTRAINT fk_reject_run FOREIGN KEY (ingest_run_id)
    REFERENCES cip_ingest_run (ingest_run_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Rows that failed validation, kept for analyst review.';

CREATE TABLE IF NOT EXISTS cip_datafeed_state (
  feed_name        VARCHAR(100)    NOT NULL COMMENT 'Forsta datafeed identifier',
  survey_id        INT UNSIGNED    NULL,
  last_record      INT UNSIGNED    NULL COMMENT 'highest [record] loaded',
  last_completed   DATETIME        NULL COMMENT 'watermark for ?start= incremental pulls',
  last_ack_at      DATETIME        NULL,
  last_status      VARCHAR(50)     NULL,
  updated_at       TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (feed_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Watermarks so incremental pulls never re-read the whole survey.';
