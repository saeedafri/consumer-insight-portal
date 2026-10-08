-- ═══════════════════════════════════════════════════════════════════════════
-- Consumer Insight Portal — CSI schema
-- Target:   MySQL 8.0+  ·  database `dwh_stg` on the Coresight STG server
-- Prefix:   csi_   (views v_csi_)
-- Charset:  utf8mb4 — retailer names contain curly apostrophes (Smith's)
--
-- 29 tables, simple names, in nine groups (schema v2):
--
--   DEFINITION  cip_survey · cip_topic · cip_question · cip_item
--               cip_option · cip_field              — what was asked
--   DATA        cip_respondent · cip_profile · cip_answer
--                                                   — what people said
--   TABULATION  cip_banner · cip_segment · cip_crosstab_run · cip_crosstab
--                                                   — the published numbers
--   LOADING     cip_load_log · cip_load_error · cip_load_state
--                                                   — how it got here
--   HARMONISATION cip_concept · cip_concept_option · cip_concept_map
--                                                   — the same question across waves
--   WEIGHTS     cip_weight_scheme · cip_weight
--   COHORTS     cip_cohort_def · cip_respondent_cohort
--   AGGREGATES  cip_agg_cell                        — the portal's speed layer
--   PUBLICATIONS cip_publication · cip_publication_cell
--   SUPPORT     cip_profile_map · cip_auth_session · cip_saved_view
--
-- Spec: docs/superpowers/specs/2026-09-29-survey-platform-design.md §5
-- ═══════════════════════════════════════════════════════════════════════════

SET NAMES utf8mb4;

-- ───────────────────────────────────────────────────────────────────────────
-- DEFINITION
-- ───────────────────────────────────────────────────────────────────────────

-- One row per survey wave.
CREATE TABLE IF NOT EXISTS cip_survey (
  survey_id     INT UNSIGNED NOT NULL AUTO_INCREMENT,
  forsta_host   VARCHAR(100) NOT NULL              COMMENT 'se1.decipherinc.com',
  forsta_path   VARCHAR(255) NOT NULL              COMMENT 'selfserve/58f/260908',
  title         VARCHAR(500) NOT NULL,
  survey_family VARCHAR(100) NULL                  COMMENT 'CSI-US — groups waves for trending',
  wave_label    VARCHAR(50)  NOT NULL              COMMENT 'fielding week, 2026-09-28',
  wave_date     DATE         NULL,
  field_start   DATETIME     NULL,
  field_end     DATETIME     NULL,
  country       CHAR(2)      NULL DEFAULT 'US',
  status        ENUM('draft','fielding','closed','archived') NOT NULL DEFAULT 'closed',
  datamap_hash  CHAR(64)     NULL                  COMMENT 'sha256 of the datamap; detects questionnaire change',
  platform      ENUM('forsta','qualtrics','surveymonkey') NOT NULL DEFAULT 'forsta'
                                                   COMMENT 'which platform fielded the wave',
  source_ref    VARCHAR(255) NOT NULL DEFAULT ''   COMMENT 'Forsta path, Qualtrics SV_ id or SurveyMonkey id',
  study_type    ENUM('tracker','annual','adhoc') NOT NULL DEFAULT 'tracker',
  load_status   ENUM('loading','verified','failed','superseded') NOT NULL DEFAULT 'verified'
                                                   COMMENT 'only verified waves are shown',
  language      VARCHAR(10)  NOT NULL DEFAULT 'en',
  sample_source VARCHAR(50)  NULL                  COMMENT 'Forsta sample source id (panel), e.g. 114',
  total_n       INT          NULL                  COMMENT 'all respondents incl. terminates/overquota',
  tags          VARCHAR(500) NULL                  COMMENT 'Forsta tags, e.g. Weekly consumer tracker',
  created_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (survey_id),
  -- One Forsta project is re-fielded weekly with rotating modules, so the wave
  -- is part of the identity. Keyed on path alone, a second week would merge
  -- into the first and overwrite respondents that share a record number.
  -- The wave's identity (spec §5.1). Listed first: SQLite upserts target the
  -- first unique key, so both engines resolve a reload to the same row.
  UNIQUE KEY uq_survey_source (platform, source_ref, wave_label),
  UNIQUE KEY uq_survey (forsta_host, forsta_path, wave_label),
  KEY ix_survey_family (survey_family, wave_date),
  KEY ix_survey_pick (load_status, study_type, wave_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Survey waves.';

-- Report modules: Department Stores, BNPL, GLP-1, Demographics, ...
CREATE TABLE IF NOT EXISTS cip_topic (
  topic_id      SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
  topic_code    VARCHAR(40)  NOT NULL              COMMENT 'DEPT_STORES',
  topic_name    VARCHAR(150) NOT NULL              COMMENT 'Department Stores',
  is_technical  TINYINT(1)   NOT NULL DEFAULT 0    COMMENT '1 = paradata/quota, hidden by default',
  sort_order    SMALLINT     NOT NULL DEFAULT 0,
  PRIMARY KEY (topic_id),
  UNIQUE KEY uq_topic (topic_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Editorial grouping of questions.';

-- One row per question as an analyst names it: q1, DP7, BN3, CS1.
CREATE TABLE IF NOT EXISTS cip_question (
  question_id   INT UNSIGNED NOT NULL AUTO_INCREMENT,
  survey_id     INT UNSIGNED NOT NULL,
  topic_id      SMALLINT UNSIGNED NULL,
  qcode         VARCHAR(50)  NOT NULL              COMMENT 'q1, DP7, BN3',
  qtext         TEXT         NOT NULL,
  qtext_short   VARCHAR(255) NULL                  COMMENT 'chart title',
  qtype         ENUM('single','multi','grid_single','grid_multi','numeric','text','datetime') NOT NULL,
  value_min     INT          NULL,
  value_max     INT          NULL,
  is_technical  TINYINT(1)   NOT NULL DEFAULT 0,
  is_virtual    TINYINT(1)   NOT NULL DEFAULT 0    COMMENT 'Forsta flag v: derived (vos, vbrowser…), not asked',
  is_multi      TINYINT(1)   NOT NULL DEFAULT 0    COMMENT '1 = respondent may pick several',
  -- ── routing: the reason this schema exists in the form it does ──────────
  -- Most questions in this survey are conditional. DP2 is asked only of
  -- department-store buyers (222 of 404), BN2 only of BNPL users (133),
  -- GP8 only of GLP-1 users (71). Charting any of them against the wave base
  -- understates them by 2-6x, so the base travels WITH the question.
  base_n        INT          NULL                  COMMENT 'respondents who reached this question',
  base_desc     VARCHAR(255) NULL                  COMMENT 'e.g. "Bought from a department store in past 3 months"',
  asked_if      VARCHAR(500) NULL                  COMMENT 'routing condition, when known',
  sort_order    SMALLINT     NOT NULL DEFAULT 0,
  PRIMARY KEY (question_id),
  UNIQUE KEY uq_question (survey_id, qcode),
  KEY ix_question_topic (topic_id),
  CONSTRAINT fk_question_survey FOREIGN KEY (survey_id)
    REFERENCES cip_survey (survey_id) ON DELETE CASCADE,
  CONSTRAINT fk_question_topic FOREIGN KEY (topic_id)
    REFERENCES cip_topic (topic_id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Questions, with their own answering base.';

-- Statement rows inside a list or grid: q1r1, DP7r3.
CREATE TABLE IF NOT EXISTS cip_item (
  item_id       INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  question_id   INT UNSIGNED  NOT NULL,
  item_code     VARCHAR(50)   NOT NULL             COMMENT 'q1r1, DP7r3',
  item_label    VARCHAR(1000) NOT NULL,
  item_short    VARCHAR(255)  NULL                 COMMENT 'trimmed for axis ticks',
  is_exclusive  TINYINT(1)    NOT NULL DEFAULT 0   COMMENT '1 = "None of these" — drop from rankings',
  is_other      TINYINT(1)    NOT NULL DEFAULT 0   COMMENT '1 = Other (please specify)',
  left_label    VARCHAR(500)  NULL                 COMMENT 'bipolar row: the statement code 1 means',
  right_label   VARCHAR(500)  NULL                 COMMENT 'bipolar row: the statement code 2 means',
  sort_order    SMALLINT      NOT NULL DEFAULT 0,
  PRIMARY KEY (item_id),
  UNIQUE KEY uq_item (question_id, item_code),
  CONSTRAINT fk_item_question FOREIGN KEY (question_id)
    REFERENCES cip_question (question_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='List items and grid rows.';

-- Code -> label dictionary. 0/1 for lists; 1-5 scales; 1-51 for state.
CREATE TABLE IF NOT EXISTS cip_option (
  option_id      INT UNSIGNED NOT NULL AUTO_INCREMENT,
  question_id    INT UNSIGNED NOT NULL,
  value_code     INT          NOT NULL,
  value_label    VARCHAR(500) NOT NULL,
  is_nonresponse TINYINT(1)   NOT NULL DEFAULT 0   COMMENT "Don't know / Prefer not to say — excluded from Top-2-Box",
  net_group      VARCHAR(50)  NULL                 COMMENT 'TOP2 / BOT2 for net calculations',
  sort_order     SMALLINT     NOT NULL DEFAULT 0,
  PRIMARY KEY (option_id),
  UNIQUE KEY uq_option (question_id, value_code),
  CONSTRAINT fk_option_question FOREIGN KEY (question_id)
    REFERENCES cip_question (question_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Answer codes and their labels.';

-- One row per column in the Forsta flat export. 375 rows for the 09/21/26 wave,
-- matching the export's 375 columns exactly. This is the loader's map.
CREATE TABLE IF NOT EXISTS cip_field (
  field_id     INT UNSIGNED NOT NULL AUTO_INCREMENT,
  survey_id    INT UNSIGNED NOT NULL,
  question_id  INT UNSIGNED NULL,
  item_id      INT UNSIGNED NULL                   COMMENT 'set when the column is one row of a list/grid',
  field_name   VARCHAR(100) NOT NULL               COMMENT 'exact export header: q1r1, D2, uuid',
  value_type   ENUM('code','numeric','text','datetime') NOT NULL,
  col_position SMALLINT     NULL,
  PRIMARY KEY (field_id),
  UNIQUE KEY uq_field (survey_id, field_name),
  KEY ix_field_question (question_id),
  KEY ix_field_item (item_id),
  CONSTRAINT fk_field_survey FOREIGN KEY (survey_id)
    REFERENCES cip_survey (survey_id) ON DELETE CASCADE,
  CONSTRAINT fk_field_question FOREIGN KEY (question_id)
    REFERENCES cip_question (question_id) ON DELETE CASCADE,
  CONSTRAINT fk_field_item FOREIGN KEY (item_id)
    REFERENCES cip_item (item_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Export column -> question/item map.';


-- ───────────────────────────────────────────────────────────────────────────
-- DATA
-- ───────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS cip_respondent (
  respondent_id  BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  survey_id      INT UNSIGNED    NOT NULL,
  record_no      INT UNSIGNED    NOT NULL          COMMENT 'Forsta [record]',
  forsta_uuid    VARCHAR(64)     NULL,
  status_code    TINYINT         NULL              COMMENT '1 Terminated 2 Overquota 3 Qualified 4 Partial',
  status_label   VARCHAR(30)     NULL,
  is_qualified   TINYINT(1)      NOT NULL DEFAULT 0 COMMENT 'default analysis base',
  started_at     DATETIME        NULL,
  completed_at   DATETIME        NULL,
  interview_secs INT             NULL,
  panel_source   VARCHAR(100)    NULL,
  sample_rid     VARCHAR(100)    NULL,
  markers        VARCHAR(1000)   NULL              COMMENT 'quota buckets as Forsta records them',
  device         VARCHAR(50)     NULL,
  os             VARCHAR(100)    NULL,
  browser        VARCHAR(100)    NULL,
  dropout_qcode  VARCHAR(50)     NULL,
  respondent_key CHAR(64)       NULL              COMMENT 'sha256 of the panel respondent id — never the id itself',
  quality_flag   VARCHAR(40)    NULL              COMMENT 'speeder, straightliner, duplicate …',
  load_id        BIGINT UNSIGNED NULL,
  loaded_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (respondent_id),
  UNIQUE KEY uq_respondent (survey_id, record_no),
  KEY ix_respondent_qualified (survey_id, is_qualified),
  KEY ix_respondent_completed (survey_id, completed_at),
  KEY ix_respondent_key (survey_id, respondent_key),
  CONSTRAINT fk_respondent_survey FOREIGN KEY (survey_id)
    REFERENCES cip_survey (survey_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='One row per interview.';

-- Demographics flattened out of D1-D8/CS1/CS2 so a filter is one indexed join
-- rather than eight lookups in cip_answer.
CREATE TABLE IF NOT EXISTS cip_profile (
  respondent_id     BIGINT UNSIGNED NOT NULL,
  survey_id         INT UNSIGNED    NOT NULL,
  gender            VARCHAR(40)   NULL             COMMENT 'D1',
  age_years         SMALLINT      NULL             COMMENT 'D2 resolved to a number',
  age_band          VARCHAR(20)   NULL             COMMENT '18-29 / 30-44 / 45-60 / Over 60',
  generation        VARCHAR(20)   NULL             COMMENT 'GenZ / Millennial / GenX / Boomer',
  relationship      VARCHAR(60)   NULL             COMMENT 'D3',
  ethnicity         VARCHAR(60)   NULL             COMMENT 'D4',
  income_band       VARCHAR(40)   NULL             COMMENT 'D5',
  urbanicity        VARCHAR(20)   NULL             COMMENT 'D6',
  political         VARCHAR(120)  NULL             COMMENT 'D7',
  state_name        VARCHAR(60)   NULL             COMMENT 'D8',
  census_region     VARCHAR(20)   NULL             COMMENT 'derived from D8',
  outlook_income    VARCHAR(40)   NULL             COMMENT 'CS1',
  outlook_economy   VARCHAR(40)   NULL             COMMENT 'CS2',
  age_mid           DECIMAL(6,2)  NULL             COMMENT 'midpoint of the age band, for averages',
  income_mid_k      DECIMAL(10,4) NULL             COMMENT 'midpoint of the income band, $000',
  weight            DECIMAL(10,6) NOT NULL DEFAULT 1.000000 COMMENT 'reserved; these waves are unweighted',
  PRIMARY KEY (respondent_id),
  KEY ix_profile_cuts (survey_id, generation, gender, income_band),
  KEY ix_profile_region (survey_id, census_region),
  CONSTRAINT fk_profile_respondent FOREIGN KEY (respondent_id)
    REFERENCES cip_respondent (respondent_id) ON DELETE CASCADE,
  CONSTRAINT fk_profile_survey FOREIGN KEY (survey_id)
    REFERENCES cip_survey (survey_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Demographic cuts, one row per respondent.';

-- The fact table. One row per respondent x field.
-- Long rather than wide: the questionnaire changes every wave (375 fields this
-- one), so new questions become new rows, never a schema migration.
CREATE TABLE IF NOT EXISTS cip_answer (
  answer_id     BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  respondent_id BIGINT UNSIGNED NOT NULL,
  survey_id     INT UNSIGNED    NOT NULL           COMMENT 'denormalised for filter speed',
  field_id      INT UNSIGNED    NOT NULL,
  value_code    INT             NULL               COMMENT '0/1, 1-5, 1-54',
  value_label   VARCHAR(500)    NULL               COMMENT 'resolved label, denormalised for display',
  value_number  DECIMAL(18,4)   NULL               COMMENT 'open numeric',
  value_text    TEXT            NULL               COMMENT 'open-ended verbatim',
  PRIMARY KEY (answer_id),
  UNIQUE KEY uq_answer (respondent_id, field_id),
  KEY ix_answer_respondent (respondent_id),
  KEY ix_answer_cover (survey_id, field_id, value_code, respondent_id),
  FULLTEXT KEY ft_answer_text (value_text),
  CONSTRAINT fk_answer_respondent FOREIGN KEY (respondent_id)
    REFERENCES cip_respondent (respondent_id) ON DELETE CASCADE,
  CONSTRAINT fk_answer_field FOREIGN KEY (field_id)
    REFERENCES cip_field (field_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Every answer, long format. ~151k rows per wave.';


-- ───────────────────────────────────────────────────────────────────────────
-- TABULATION
-- ───────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS cip_banner (
  banner_id   INT UNSIGNED NOT NULL AUTO_INCREMENT,
  survey_id   INT UNSIGNED NOT NULL,
  banner_code VARCHAR(50)  NOT NULL                COMMENT 'AGE, GENDER, INCOME',
  banner_name VARCHAR(500) NOT NULL                COMMENT 'header text as printed',
  source_q    VARCHAR(50)  NULL                    COMMENT 'question the banner is built from',
  sort_order  SMALLINT     NOT NULL DEFAULT 0,
  PRIMARY KEY (banner_id),
  UNIQUE KEY uq_banner (survey_id, banner_code),
  CONSTRAINT fk_banner_survey FOREIGN KEY (survey_id)
    REFERENCES cip_survey (survey_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Cross-tab column groups.';

CREATE TABLE IF NOT EXISTS cip_segment (
  segment_id     INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  banner_id      INT UNSIGNED  NOT NULL,
  survey_id      INT UNSIGNED  NOT NULL,
  seg_letter     VARCHAR(4)    NULL                COMMENT 'stat-test letter A..N1',
  seg_label      VARCHAR(255)  NOT NULL            COMMENT 'Male, GenZ, $50,000 - $99,999',
  seg_definition VARCHAR(2000) NULL                COMMENT 'Forsta expression, kept verbatim so a wave is auditable',
  seg_base_n     INT           NULL                COMMENT 'segment size — NOT the denominator of a routed question',
  is_total       TINYINT(1)    NOT NULL DEFAULT 0,
  low_base       ENUM('','*','**') NOT NULL DEFAULT '' COMMENT '* caution, ** too small to report',
  sort_order     SMALLINT      NOT NULL DEFAULT 0,
  PRIMARY KEY (segment_id),
  UNIQUE KEY uq_segment (banner_id, seg_label),
  KEY ix_segment_survey (survey_id),
  CONSTRAINT fk_segment_banner FOREIGN KEY (banner_id)
    REFERENCES cip_banner (banner_id) ON DELETE CASCADE,
  CONSTRAINT fk_segment_survey FOREIGN KEY (survey_id)
    REFERENCES cip_survey (survey_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Cross-tab columns with their Forsta definitions.';

-- The Summary-sheet settings. A percentage without these is not defensible.
CREATE TABLE IF NOT EXISTS cip_crosstab_run (
  run_id          INT UNSIGNED NOT NULL AUTO_INCREMENT,
  survey_id       INT UNSIGNED NOT NULL,
  run_label       VARCHAR(255) NOT NULL,
  respondent_base VARCHAR(100) NULL                COMMENT '"Qualified Only"',
  extra_filter    VARCHAR(500) NULL,
  table_set       VARCHAR(100) NULL,
  pct_base        VARCHAR(100) NULL                COMMENT '"Total Answering" — see cip_crosstab.answer_base_n',
  stat_test       VARCHAR(100) NULL,
  date_from       DATE         NULL,
  date_to         DATE         NULL,
  source_type     ENUM('api','excel') NOT NULL DEFAULT 'excel',
  source_file     VARCHAR(255) NULL,
  is_current      TINYINT(1)   NOT NULL DEFAULT 1,
  created_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (run_id),
  KEY ix_run_survey (survey_id, is_current),
  CONSTRAINT fk_run_survey FOREIGN KEY (survey_id)
    REFERENCES cip_survey (survey_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='One row per cross-tab export, with its base and filter settings.';

-- Every cell of every cross-tab.
--
-- Two different bases live here and must never be confused:
--   seg_base_n    on cip_segment — how many people are in the column (404 Total)
--   answer_base_n here           — how many ANSWERED this question (222 for DP2)
-- Forsta prints the first in the header and divides by the second. Storing
-- only the printed one would overstate every routed question's base by up to 6x.
CREATE TABLE IF NOT EXISTS cip_crosstab (
  crosstab_id   BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  run_id        INT UNSIGNED    NOT NULL,
  survey_id     INT UNSIGNED    NOT NULL,
  question_id   INT UNSIGNED    NOT NULL,
  item_id       INT UNSIGNED    NULL,
  option_id     INT UNSIGNED    NULL,
  segment_id    INT UNSIGNED    NOT NULL,
  item_label    VARCHAR(500)    NULL               COMMENT 'grid sub-item, e.g. the retailer being rated in DP7',
  stub_label    VARCHAR(1000)   NOT NULL           COMMENT 'row label as printed',
  stub_key      VARCHAR(600)    NOT NULL           COMMENT 'item_label|stub_label — unique within a table',
  stub_type     ENUM('item','net','mean','count','base') NOT NULL DEFAULT 'item',
  pct           DECIMAL(9,6)    NULL               COMMENT '0.527228 = 52.7%',
  count_n       INT             NULL,
  answer_base_n INT             NULL               COMMENT 'the true denominator: count_n / pct',
  sig_letters   VARCHAR(40)     NULL               COMMENT 'segments this cell significantly beats',
  PRIMARY KEY (crosstab_id),
  UNIQUE KEY uq_crosstab (run_id, question_id, stub_key, segment_id),
  KEY ix_crosstab_lookup (survey_id, question_id, segment_id),
  KEY ix_crosstab_item (item_id),
  CONSTRAINT fk_crosstab_run FOREIGN KEY (run_id)
    REFERENCES cip_crosstab_run (run_id) ON DELETE CASCADE,
  CONSTRAINT fk_crosstab_question FOREIGN KEY (question_id)
    REFERENCES cip_question (question_id) ON DELETE CASCADE,
  CONSTRAINT fk_crosstab_segment FOREIGN KEY (segment_id)
    REFERENCES cip_segment (segment_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Cross-tab cells: percentage, count, true base, significance.';


-- ───────────────────────────────────────────────────────────────────────────
-- LOADING
-- ───────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS cip_load_log (
  load_id     BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  survey_id   INT UNSIGNED    NULL,
  source_type ENUM('api','excel','manual') NOT NULL,
  object_type ENUM('datamap','data','crosstab','profile') NOT NULL,
  source_ref  VARCHAR(500)    NULL                 COMMENT 'endpoint URL or file name',
  rows_read   INT             NOT NULL DEFAULT 0,
  rows_loaded INT             NOT NULL DEFAULT 0,
  rows_bad    INT             NOT NULL DEFAULT 0,
  status      ENUM('running','success','partial','failed') NOT NULL DEFAULT 'running',
  error_text  TEXT            NULL,
  archive_uri    VARCHAR(1000)   NULL             COMMENT 'untouched source file or payload in Blob',
  archive_sha256 CHAR(64)        NULL,
  started_at  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  finished_at DATETIME        NULL,
  PRIMARY KEY (load_id),
  KEY ix_load_survey (survey_id, object_type, started_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Audit trail. Nothing enters CSI without a row here.';

CREATE TABLE IF NOT EXISTS cip_load_error (
  error_id   BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  load_id    BIGINT UNSIGNED NOT NULL,
  record_ref VARCHAR(200)    NULL                  COMMENT 'record number or sheet!cell',
  reason     VARCHAR(500)    NOT NULL,
  payload    JSON            NULL,
  PRIMARY KEY (error_id),
  KEY ix_error_load (load_id),
  CONSTRAINT fk_error_load FOREIGN KEY (load_id)
    REFERENCES cip_load_log (load_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Rows that failed validation, kept for review.';

CREATE TABLE IF NOT EXISTS cip_load_state (
  feed_name      VARCHAR(100) NOT NULL,
  survey_id      INT UNSIGNED NULL,
  last_record    INT UNSIGNED NULL,
  last_completed DATETIME     NULL                 COMMENT 'watermark for incremental pulls',
  last_ack_at    DATETIME     NULL,
  last_status    VARCHAR(50)  NULL,
  updated_at     TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (feed_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Watermarks so incremental pulls never re-read a whole survey.';


-- ───────────────────────────────────────────────────────────────────────────
-- HARMONISATION — the same question across waves and platforms
-- A grid is stored as one concept per grid row, sharing a concept_group.
-- ───────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS cip_concept (
  concept_id    INT UNSIGNED      NOT NULL AUTO_INCREMENT,
  concept_code  VARCHAR(80)       NOT NULL COMMENT 'BEAUTY_RETAILER_3M',
  concept_name  VARCHAR(255)      NOT NULL,
  concept_group VARCHAR(80)       NULL     COMMENT 'rows of one grid share a group',
  topic_id      SMALLINT UNSIGNED NULL,
  qtype         ENUM('single','multi','grid_single','grid_multi','numeric','text','datetime') NOT NULL,
  description   VARCHAR(1000)     NULL,
  match_text    VARCHAR(2000)     NULL     COMMENT 'normalised wording the harmoniser matches on',
  created_at    TIMESTAMP         NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (concept_id),
  UNIQUE KEY uq_concept (concept_code),
  KEY ix_concept_group (concept_group),
  CONSTRAINT fk_concept_topic FOREIGN KEY (topic_id)
    REFERENCES cip_topic (topic_id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Canonical questions, stable across waves and platforms.';

CREATE TABLE IF NOT EXISTS cip_concept_option (
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
    REFERENCES cip_concept (concept_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Canonical answers, with band midpoints.';

CREATE TABLE IF NOT EXISTS cip_concept_map (
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
    REFERENCES cip_survey (survey_id) ON DELETE CASCADE,
  CONSTRAINT fk_map_question FOREIGN KEY (question_id)
    REFERENCES cip_question (question_id) ON DELETE CASCADE,
  CONSTRAINT fk_map_item FOREIGN KEY (item_id)
    REFERENCES cip_item (item_id) ON DELETE CASCADE,
  CONSTRAINT fk_map_option FOREIGN KEY (option_id)
    REFERENCES cip_option (option_id) ON DELETE CASCADE,
  CONSTRAINT fk_map_concept FOREIGN KEY (concept_id)
    REFERENCES cip_concept (concept_id) ON DELETE CASCADE,
  CONSTRAINT fk_map_coption FOREIGN KEY (concept_option_id)
    REFERENCES cip_concept_option (concept_option_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Wave question/item/option -> canonical concept, proposed or confirmed.';

-- ───────────────────────────────────────────────────────────────────────────
-- WEIGHTS — supported, none applied yet
-- ───────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS cip_weight_scheme (
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
    REFERENCES cip_survey (survey_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Named weighting schemes, per wave.';

CREATE TABLE IF NOT EXISTS cip_weight (
  respondent_id BIGINT UNSIGNED NOT NULL,
  scheme_id     INT UNSIGNED    NOT NULL,
  weight        DECIMAL(12,6)   NOT NULL,
  PRIMARY KEY (respondent_id, scheme_id),
  KEY ix_weight_scheme (scheme_id),
  CONSTRAINT fk_weight_respondent FOREIGN KEY (respondent_id)
    REFERENCES cip_respondent (respondent_id) ON DELETE CASCADE,
  CONSTRAINT fk_weight_scheme FOREIGN KEY (scheme_id)
    REFERENCES cip_weight_scheme (scheme_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='One weight per respondent per scheme.';

-- ───────────────────────────────────────────────────────────────────────────
-- COHORTS — analyst rules made data ("Beauty shopper")
-- ───────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS cip_cohort_def (
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

CREATE TABLE IF NOT EXISTS cip_respondent_cohort (
  cohort_id     INT UNSIGNED    NOT NULL,
  respondent_id BIGINT UNSIGNED NOT NULL,
  survey_id     INT UNSIGNED    NOT NULL,
  PRIMARY KEY (cohort_id, respondent_id),
  KEY ix_rcohort_survey (cohort_id, survey_id),
  KEY ix_rcohort_respondent (respondent_id),
  CONSTRAINT fk_rcohort_cohort FOREIGN KEY (cohort_id)
    REFERENCES cip_cohort_def (cohort_id) ON DELETE CASCADE,
  CONSTRAINT fk_rcohort_respondent FOREIGN KEY (respondent_id)
    REFERENCES cip_respondent (respondent_id) ON DELETE CASCADE,
  CONSTRAINT fk_rcohort_survey FOREIGN KEY (survey_id)
    REFERENCES cip_survey (survey_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Materialised cohort membership.';

-- ───────────────────────────────────────────────────────────────────────────
-- AGGREGATES — pre-computed cells for the portal's standard views
-- ───────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS cip_agg_cell (
  cell_id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  survey_id         INT UNSIGNED    NOT NULL,
  cell_key          VARCHAR(200)    NOT NULL COMMENT 'question:item:option:cohort:scheme:dim:value',
  question_id       INT UNSIGNED    NOT NULL,
  item_id           INT UNSIGNED    NULL,
  option_id         INT UNSIGNED    NULL,
  concept_option_id INT UNSIGNED    NULL,
  map_key           VARCHAR(40)     NULL     COMMENT 'question:item:option — joins cip_concept_map at read time',
  cohort_id         INT UNSIGNED    NULL     COMMENT 'NULL = all qualified respondents',
  scheme_id         INT UNSIGNED    NULL     COMMENT 'NULL = unweighted',
  dim               VARCHAR(30)     NOT NULL COMMENT 'total, gender, age_band, …',
  dim_value         VARCHAR(120)    NOT NULL,
  n                 INT             NOT NULL,
  base_n            INT             NOT NULL,
  n_weighted        DECIMAL(14,4)   NULL,
  base_weighted     DECIMAL(14,4)   NULL,
  sum_age_mid       DECIMAL(14,4)   NULL,
  n_age_mid         INT             NULL     COMMENT 'respondents in n with an age midpoint',
  sum_income_mid_k  DECIMAL(16,4)   NULL,
  n_income_mid      INT             NULL,
  built_at          TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (cell_id),
  UNIQUE KEY uq_agg_cell (survey_id, cell_key),
  KEY ix_agg_concept (concept_option_id, cohort_id, dim, survey_id),
  KEY ix_agg_question (survey_id, question_id, dim),
  KEY ix_agg_map (survey_id, map_key, cohort_id, dim),
  CONSTRAINT fk_agg_survey FOREIGN KEY (survey_id)
    REFERENCES cip_survey (survey_id) ON DELETE CASCADE,
  CONSTRAINT fk_agg_question FOREIGN KEY (question_id)
    REFERENCES cip_question (question_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Pre-computed counts per wave x answer x cut x cohort.';

-- ───────────────────────────────────────────────────────────────────────────
-- PUBLICATIONS — frozen deliverables, with drift detection
-- ───────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS cip_publication (
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

CREATE TABLE IF NOT EXISTS cip_publication_cell (
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
    REFERENCES cip_publication (publication_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='The frozen numbers of a publication.';


-- ───────────────────────────────────────────────────────────────────────────
-- DYNAMIC SURVEY SUPPORT
--
-- These two tables are what let a new wave load without a code change. The
-- loader resolves which question supplies each demographic cut, records the
-- decision here, and an analyst can correct it without touching Python.
-- ───────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS cip_profile_map (
  survey_id   INT UNSIGNED NOT NULL,
  dimension   VARCHAR(40)  NOT NULL             COMMENT 'gender, age, income_band, ...',
  qcode       VARCHAR(50)  NOT NULL             COMMENT 'the question that supplies it',
  resolved_by ENUM('config','detected','manual') NOT NULL DEFAULT 'detected',
  updated_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (survey_id, dimension),
  CONSTRAINT fk_pmap_survey FOREIGN KEY (survey_id)
    REFERENCES cip_survey (survey_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Which question feeds each demographic cut, per wave. Auditable and editable.';


-- ───────────────────────────────────────────────────────────────────────────
-- ACCESS AND SAVED WORK
-- ───────────────────────────────────────────────────────────────────────────

-- One row per sign-in. Gives an auditable record of who opened the portal and
-- a way for an admin to revoke a session without waiting for it to expire.
CREATE TABLE IF NOT EXISTS cip_auth_session (
  session_id   VARCHAR(64)  NOT NULL,
  user_email   VARCHAR(200) NOT NULL,
  user_name    VARCHAR(200) NULL,
  provider     VARCHAR(20)  NOT NULL DEFAULT 'local',
  created_at   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  expires_at   DATETIME     NULL,
  revoked_at   DATETIME     NULL,
  request_meta VARCHAR(500) NULL COMMENT 'host and user agent at sign-in',
  PRIMARY KEY (session_id),
  KEY ix_auth_user (user_email, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Sign-in audit and revocation.';

-- A saved analysis: the filters, the questions and the break, as JSON.
-- Storing the definition rather than the numbers means a saved view re-runs
-- against the current data — which is the point of saving it.
CREATE TABLE IF NOT EXISTS cip_saved_view (
  view_id     INT UNSIGNED NOT NULL AUTO_INCREMENT,
  survey_id   INT UNSIGNED NOT NULL,
  view_name   VARCHAR(160) NOT NULL,
  owner_email VARCHAR(200) NOT NULL,
  is_shared   TINYINT(1)   NOT NULL DEFAULT 0 COMMENT '1 = visible to the whole team',
  definition  TEXT         NOT NULL COMMENT 'JSON: criteria, question ids, break',
  description VARCHAR(500) NULL,
  created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (view_id),
  UNIQUE KEY uq_saved_view (owner_email, view_name),
  KEY ix_saved_view_survey (survey_id, is_shared),
  CONSTRAINT fk_view_survey FOREIGN KEY (survey_id)
    REFERENCES cip_survey (survey_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Saved filter + question sets, re-run against current data.';


-- ─────────────────────────────────────────────────────────────────────────
-- Forsta register: every survey the API lists, and where the ETL is with it.
-- One Forsta survey = one wave (selfserve/58f/YYMMNN). The ETL's to-do list:
-- closed + readable + not loaded = due.
-- ─────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cip_forsta_survey (
  forsta_path  VARCHAR(255) NOT NULL              COMMENT 'selfserve/58f/260907',
  title        VARCHAR(500) NOT NULL,
  state        VARCHAR(30)  NOT NULL              COMMENT 'Forsta state: testing, live, closed',
  hibernated   TINYINT(1)   NOT NULL DEFAULT 0    COMMENT '1 = Forsta answers 428 until reactivated',
  tags         VARCHAR(500) NULL,
  study_type   ENUM('tracker','annual','adhoc') NOT NULL DEFAULT 'adhoc',
  created_on   DATETIME     NULL,
  launched_at  DATETIME     NULL,
  closed_at    DATETIME     NULL,
  qualified_n  INT          NULL,
  total_n      INT          NULL,
  last_seen    DATETIME     NOT NULL,
  load_state   ENUM('new','due','loaded','failed','hibernated','testing') NOT NULL DEFAULT 'new',
  survey_id    INT UNSIGNED NULL                  COMMENT 'cip_survey row once loaded',
  loaded_at    DATETIME     NULL,
  last_error   VARCHAR(1000) NULL,
  PRIMARY KEY (forsta_path),
  KEY ix_forsta_due (load_state, closed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ─────────────────────────────────────────────────────────────────────────
-- Search: one row per survey, question and concept, rebuilt after each load.
-- The portal's search box is one FULLTEXT read of this table.
-- ─────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cip_search (
  search_id    INT UNSIGNED NOT NULL AUTO_INCREMENT,
  kind         ENUM('survey','question','concept') NOT NULL,
  survey_id    INT UNSIGNED NULL,
  question_id  INT UNSIGNED NULL,
  concept_id   INT UNSIGNED NULL,
  wave_label   VARCHAR(50)  NULL,
  waves        INT          NULL                  COMMENT 'concept: waves it appears in',
  title        VARCHAR(500) NOT NULL,
  body         TEXT         NULL,
  PRIMARY KEY (search_id),
  KEY ix_search_kind (kind, wave_label),
  FULLTEXT KEY ft_search (title, body)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ─────────────────────────────────────────────────────────────────────────
-- The weekly tracker's line-by-line table (the data team's "Weekly Line-By-
-- Line Survey Data"): one row per qualified respondent of each tracker wave,
-- the core questions under the team's headers, as JSON in the team's order.
-- Rebuilt by the ETL after every load (etl/tracker_line.py).
-- ─────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cip_tracker_line (
  respondent_id BIGINT UNSIGNED NOT NULL,
  survey_id     INT UNSIGNED    NOT NULL,
  wave_date     DATE            NOT NULL,
  line          JSON            NOT NULL COMMENT 'header -> value, config/tracker_line.yml order',
  PRIMARY KEY (respondent_id),
  KEY ix_line_wave (wave_date, survey_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ─────────────────────────────────────────────────────────────────────────
-- The survey calendar: every Forsta survey × the modules it carries (lead
-- sector, topics, seasonal trackers, events; annual and ad hoc studies), with
-- seasonal waves numbered within their season. Rebuilt by the ETL after each
-- discovery and load (etl/survey_calendar.py, config/survey_calendar.yml).
-- ─────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cip_wave_module (
  forsta_path    VARCHAR(255) NOT NULL,
  module_code    VARCHAR(40)  NOT NULL,
  module_name    VARCHAR(120) NOT NULL,
  kind           ENUM('sector','topic','seasonal','event','annual','adhoc') NOT NULL,
  is_lead        TINYINT(1)   NOT NULL DEFAULT 0  COMMENT 'the tracker week''s lead sector',
  launched_on    DATE         NULL,
  season         SMALLINT     NULL               COMMENT 'seasonal / annual: Jul-Jun season year',
  series_wave_no SMALLINT     NULL               COMMENT 'nth wave of this module (in its season)',
  survey_id      INT UNSIGNED NULL               COMMENT 'set once loaded',
  detected_by    ENUM('title','questions') NOT NULL DEFAULT 'title',
  PRIMARY KEY (forsta_path, module_code),
  KEY ix_module_series (module_code, season, series_wave_no),
  KEY ix_module_day (launched_on)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
