-- What the team keeps in the portal (api/team.py): saved views everyone can open, metric alerts the pipeline checks
-- after each load, and audiences (saved groups of respondents). Written only by the portal; nothing here is survey data.

CREATE TABLE IF NOT EXISTS cip_team_view (
  view_id     INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  name        VARCHAR(200)  NOT NULL,
  url         VARCHAR(1000) NOT NULL              COMMENT 'the screen with its full state: wave, question, cut, waves picked',
  note        VARCHAR(1000) NULL,
  saved_by    VARCHAR(120)  NOT NULL,
  created_at  TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (view_id),
  KEY ix_team_view_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Saved analyses the whole team sees';

CREATE TABLE IF NOT EXISTS cip_metric_alert (
  alert_id       INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  name           VARCHAR(200)  NOT NULL,
  survey_family  VARCHAR(100)  NOT NULL,
  study_type     VARCHAR(20)   NOT NULL,
  qcode          VARCHAR(50)   NOT NULL,
  qtext          TEXT          NOT NULL           COMMENT 'the wording when set: a reused code (another question) never fires it',
  item_label     VARCHAR(255)  NOT NULL DEFAULT '',
  option_code    INT           NULL,
  answer_label   VARCHAR(500)  NOT NULL,
  dim            VARCHAR(30)   NOT NULL DEFAULT 'total',
  dim_value      VARCHAR(120)  NOT NULL DEFAULT 'Total',
  against        ENUM('prior','ly') NOT NULL DEFAULT 'prior' COMMENT 'baseline: the previous wave or the same week last year',
  created_by     VARCHAR(120)  NOT NULL,
  created_at     TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_checked   INT UNSIGNED  NULL               COMMENT 'newest survey_id already checked: each wave is judged once',
  last_fired     INT UNSIGNED  NULL,
  PRIMARY KEY (alert_id),
  KEY ix_alert_family (survey_family, study_type, qcode)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Tell the team when an answer moves significantly';

CREATE TABLE IF NOT EXISTS cip_audience (
  audience_id  INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  name         VARCHAR(200)  NOT NULL,
  definition   TEXT          NOT NULL             COMMENT 'JSON: {"cuts": {dim: [values]}, "answers": [{qcode, qtext, item_label, option_code, label}]}',
  created_by   VARCHAR(120)  NOT NULL,
  created_at   TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (audience_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Saved groups of respondents: any cuts and answers combined';
