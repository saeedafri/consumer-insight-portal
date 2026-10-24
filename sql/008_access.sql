-- Who used the portal and how (app/core/audit.py, app/core/session.py). Written only by the portal (the API's account);
-- nothing here is survey data. Applied by scripts/init_db.py (app/core/schema_upgrade.py), safely re-runnable.
-- The DBA grants the portal's account its writes here (sql/004_grants.sql style):
--   GRANT INSERT ON `cip_stg`.`cip_access_log` TO 'cip_app'@'%';
--   GRANT INSERT, UPDATE ON `cip_stg`.`cip_access_session` TO 'cip_app'@'%';

CREATE TABLE IF NOT EXISTS cip_access_log (
  log_id      BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  ts          TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  email       VARCHAR(255)  NOT NULL,
  client      VARCHAR(64)   NULL                COMMENT 'the client organisation (config/access.yml); NULL for Coresight staff',
  role        VARCHAR(20)   NOT NULL,
  action      VARCHAR(40)   NOT NULL            COMMENT 'sign_in, sign_out, export, ask, board_new, audience_save, alert_save, ...',
  survey_id   INT UNSIGNED  NULL,
  target      VARCHAR(300)  NULL                COMMENT 'what was acted on: a board id, an export name, a question',
  detail      TEXT          NULL                COMMENT 'JSON',
  ip_hash     CHAR(22)      NULL                COMMENT 'keyed hash of the address, never the address',
  user_agent  VARCHAR(120)  NULL,
  PRIMARY KEY (log_id),
  KEY ix_access_log_ts (ts),
  KEY ix_access_log_email (email, ts)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Append-only: who signed in, exported, asked or changed what';

CREATE TABLE IF NOT EXISTS cip_access_session (
  session_hash  CHAR(64)     NOT NULL           COMMENT 'SHA-256 of the session id in the cookie: the id itself is never stored',
  email         VARCHAR(255) NOT NULL,
  client        VARCHAR(64)  NULL,
  role          VARCHAR(20)  NOT NULL,
  provider      VARCHAR(20)  NOT NULL           COMMENT 'oidc or demo',
  created_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  expires_at    DATETIME     NOT NULL,
  revoked_at    DATETIME     NULL               COMMENT 'set by sign-out or an admin: the API refuses the cookie within a minute',
  PRIMARY KEY (session_hash),
  KEY ix_access_session_email (email),
  KEY ix_access_session_revoked (revoked_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Portal sign-ins, so one can be revoked';
