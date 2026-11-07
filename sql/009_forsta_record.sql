-- Forsta's read-only answers about each survey and the company, kept verbatim (etl/fieldwork.py collects them with GET
-- calls only; Forsta deletes an archived survey a year on, and these records with it). One row per survey and kind,
-- replaced when read again: the funnel, drop-outs, warnings, quota, audit log, survey.xml, saved reports, archive
-- schedule... (the kinds are etl/fieldwork.py SURVEY_READS and COMPANY_READS). Company-wide rows have forsta_path ''.
-- Read by etl/fieldwork.py publish (the admins' Fieldwork screen, the Survey preview's conditions).
CREATE TABLE IF NOT EXISTS cip_forsta_record (
  forsta_path  VARCHAR(255) NOT NULL              COMMENT 'the survey (selfserve/58f/261003), or empty for company-wide records',
  kind         VARCHAR(40)  NOT NULL              COMMENT 'which answer: completions, dropouts, audit_log, survey_xml, archived, ...',
  fetched_at   DATETIME     NOT NULL              COMMENT 'when Forsta was read (UTC)',
  payload      MEDIUMBLOB   NOT NULL              COMMENT 'Forsta''s answer as it came, gzip-compressed (JSON, or the file for survey_xml)',
  PRIMARY KEY (forsta_path, kind)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Read-only Forsta answers, kept verbatim';
