-- ═══════════════════════════════════════════════════════════════════════════
-- 23 Oct 2026 (docs/REA Claude Opus 2026-10-23/80-fixes-etl.md). Additive only; safe to re-run.
--
--   srv_result.flags  + sig_prior, sig_ly: the pipeline's significance verdict on a Total row
--                       (etl/serving.mark_significant: z-test, Benjamini-Hochberg 5 % over testable rows)
--   srv_wave.in_field   1 = loaded while Forsta still had the survey open; final once it closes
--   cip_forsta_survey.load_state + too_small: a closed annual or ad hoc study under 30 qualified, never loaded
--
-- Adding SET/ENUM members at the end is a metadata-only change in MySQL 8. The ETL checks for each one
-- (etl/serving.schema_has) and writes it only once this file is applied.
--
--   mysql … cip_stg < sql/009_serving_flags.sql
-- ═══════════════════════════════════════════════════════════════════════════

ALTER TABLE srv_result MODIFY COLUMN flags
    SET('small_base','base_changed_prior','base_changed_ly','wording_changed_prior','wording_changed_ly',
        'sig_prior','sig_ly') NOT NULL DEFAULT '';

-- MySQL has no ADD COLUMN IF NOT EXISTS: a second run fails here with 1060 (duplicate column), harmlessly
ALTER TABLE srv_wave ADD COLUMN in_field TINYINT(1) NOT NULL DEFAULT 0
    COMMENT '1 = loaded while the survey was still in field (Forsta live): numbers may still move'
    AFTER ly_status;

ALTER TABLE cip_forsta_survey MODIFY COLUMN load_state
    ENUM('new','due','loaded','failed','hibernated','testing','too_small') NOT NULL DEFAULT 'new';
