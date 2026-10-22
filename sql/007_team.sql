-- What the team keeps in the portal (api/team.py): saved views everyone can open, metric alerts the pipeline checks
-- after each load, and audiences (saved groups of respondents). Written only by the portal; nothing here is survey data.

CREATE TABLE IF NOT EXISTS cip_team_view (
  view_id     INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  name        VARCHAR(200)  NOT NULL,
  url         VARCHAR(1000) NOT NULL              COMMENT 'the screen with its full state: wave, question, cut, waves picked',
  note        VARCHAR(1000) NULL,
  saved_by    VARCHAR(120)  NOT NULL,
  owner_email VARCHAR(255)  NULL               COMMENT 'the signed-in person who saved it: only they remove it',
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
  notify_email   VARCHAR(255)  NULL               COMMENT 'who set it: they get the alert by email too',
  owner_email    VARCHAR(255)  NULL               COMMENT 'the signed-in person who set it: only they remove it',
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
  owner_email  VARCHAR(255)  NULL               COMMENT 'the signed-in person who saved it: only they remove it',
  created_at   TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (audience_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Saved groups of respondents: any cuts and answers combined';

CREATE TABLE IF NOT EXISTS cip_board (
  board_id    INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  name        VARCHAR(200)  NOT NULL,
  created_by  VARCHAR(255)  NOT NULL,
  created_at  TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (board_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Workspaces: tables pinned as they were, downloadable as one deck';

CREATE TABLE IF NOT EXISTS cip_board_item (
  item_id       INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  board_id      INT UNSIGNED  NOT NULL,
  title         VARCHAR(300)  NOT NULL,
  url           VARCHAR(1000) NOT NULL              COMMENT 'the live screen, to compare the pinned numbers with today',
  spec          MEDIUMTEXT    NOT NULL              COMMENT 'JSON {name, header, rows, notes}: the numbers as pinned, never recomputed',
  data_version  VARCHAR(64)   NOT NULL              COMMENT 'the published data version the numbers came from',
  added_by      VARCHAR(255)  NOT NULL,
  added_at      TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (item_id),
  KEY ix_board_item_board (board_id),
  CONSTRAINT fk_board_item_board FOREIGN KEY (board_id) REFERENCES cip_board (board_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS cip_board_comment (
  comment_id  INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  item_id     INT UNSIGNED  NOT NULL,
  author      VARCHAR(255)  NOT NULL,
  body        VARCHAR(2000) NOT NULL,
  created_at  TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (comment_id),
  KEY ix_board_comment_item (item_id),
  CONSTRAINT fk_board_comment_item FOREIGN KEY (item_id) REFERENCES cip_board_item (item_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='The team discussing a pinned table';
