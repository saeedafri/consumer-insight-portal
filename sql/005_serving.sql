-- ═══════════════════════════════════════════════════════════════════════════
-- Serving layer: the ETL's last step and the ONLY tables a user-facing screen reads.
--
-- Built by etl/serving.py for each wave right after the cube, inside the load. It is
-- screen-agnostic: every answer of every non-technical question, for Total and every
-- standard cut, already filtered (qualified respondents only — the cube is), labelled,
-- turned into a percentage, and compared with the prior week and the same week last year.
-- A screen asks for (wave, question, cut) and gets finished rows from one primary-key
-- range read: no joins, no GROUP BY, no arithmetic at request time.
--
--   srv_wave    one row per verified wave: its comparison waves and qualified base
--   srv_result  one row per wave × question × cut value × answer
--   srv_answer  one row per qualified respondent's answer, carrying all six cuts: combined
--               filters (generation × gender, pooled weeks) are one GROUP BY over a
--               primary-key range, ≈ 1 ms, instead of 4–34 ms over the raw answers
--
-- Rebuilding a wave is DELETE + INSERT in one transaction, so readers see the old rows
-- or the new ones, never a mix (InnoDB MVCC).
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS srv_wave (
    survey_id        INT UNSIGNED NOT NULL,
    survey_family    VARCHAR(80)  NOT NULL,
    study_type       VARCHAR(20)  NOT NULL,
    wave_date        DATE         NOT NULL,
    qualified_n      INT          NOT NULL,
    prior_survey_id  INT UNSIGNED NULL COMMENT 'Previous verified wave of the same tracker family (within 14 days)',
    ly_survey_id     INT UNSIGNED NULL COMMENT 'Same family, same calendar week last year (wave_date - 364 days, ±3)',
    ly_status        ENUM('loaded','not_loaded','none') NOT NULL DEFAULT 'none'
                     COMMENT 'not_loaded: that week exists in Forsta but was never loaded (e.g. hibernated)',
    rows_built       INT          NOT NULL DEFAULT 0,
    built_at         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (survey_id),
    KEY ix_srv_wave_family (survey_family, wave_date),
    CONSTRAINT fk_srv_wave_survey FOREIGN KEY (survey_id) REFERENCES cip_survey (survey_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Serving layer: one row per verified wave';

CREATE TABLE IF NOT EXISTS srv_result (
    survey_id         INT UNSIGNED  NOT NULL,
    qcode             VARCHAR(50)   NOT NULL,
    dim               VARCHAR(30)   NOT NULL COMMENT 'total, gender, age_band, generation, income_band, census_region, urbanicity',
    dim_value         VARCHAR(120)  NOT NULL,
    item_id           INT UNSIGNED  NOT NULL DEFAULT 0 COMMENT '0 for single-choice questions',
    option_id         INT UNSIGNED  NOT NULL DEFAULT 0 COMMENT '0 for multi-choice items',
    question_id       INT UNSIGNED  NOT NULL,
    qtype             VARCHAR(20)   NOT NULL,
    item_label        VARCHAR(255)  NOT NULL DEFAULT '',
    option_code       INT           NULL,
    option_label      VARCHAR(255)  NULL,
    sort_order        INT           NOT NULL DEFAULT 0,
    concept_option_id INT UNSIGNED  NULL COMMENT 'Harmonised answer: the same answer across waves, for trends',
    n                 INT           NOT NULL,
    base_n            INT           NOT NULL,
    pct               DECIMAL(6,3)  NOT NULL,
    prior_pct         DECIMAL(6,3)  NULL,
    prior_base_n      INT           NULL,
    ly_pct            DECIMAL(6,3)  NULL,
    ly_base_n         INT           NULL,
    flags             SET('small_base','base_changed_prior','base_changed_ly') NOT NULL DEFAULT '',
    PRIMARY KEY (survey_id, qcode, dim, dim_value, item_id, option_id),
    KEY ix_srv_concept (concept_option_id, dim, dim_value, survey_id),
    CONSTRAINT fk_srv_result_wave FOREIGN KEY (survey_id) REFERENCES srv_wave (survey_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Serving layer: finished percentages with comparisons, one PK range per screen widget';

CREATE TABLE IF NOT EXISTS srv_answer (
    survey_id      INT UNSIGNED NOT NULL,
    qcode          VARCHAR(50)  NOT NULL,
    item_id        INT UNSIGNED NOT NULL COMMENT 'As srv_result. 0 with option_id 0 = base row: this respondent answered the multi question',
    option_id      INT UNSIGNED NOT NULL COMMENT 'As srv_result: the answer for single choice, 0 for a multi item chosen',
    respondent_id  INT UNSIGNED NOT NULL,
    gender         VARCHAR(120) NOT NULL DEFAULT '',
    age_band       VARCHAR(120) NOT NULL DEFAULT '',
    generation     VARCHAR(120) NOT NULL DEFAULT '',
    income_band    VARCHAR(120) NOT NULL DEFAULT '',
    census_region  VARCHAR(120) NOT NULL DEFAULT '',
    urbanicity     VARCHAR(120) NOT NULL DEFAULT '',
    PRIMARY KEY (survey_id, qcode, item_id, option_id, respondent_id),
    CONSTRAINT fk_srv_answer_wave FOREIGN KEY (survey_id) REFERENCES srv_wave (survey_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Serving layer: qualified answers with every cut, for combined filters; multi items only when chosen';
