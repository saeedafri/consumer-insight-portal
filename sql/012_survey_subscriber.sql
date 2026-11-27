-- Who is emailed each new survey, as they ticked it on My account (frontend/src/screens/Account.tsx →
-- PUT /api/v1/alerts/new-surveys, api/team.py). Read by etl/notify.py tell_subscribers after the team's own email: each
-- person is checked as the API checks them (their Alerts menu, the survey's visibility) and gets the summary without
-- the team's workbooks. Created by the API on the first tick, or by scripts/init_db.py (shared/core/schema_upgrade.py).
CREATE TABLE IF NOT EXISTS cip_survey_subscriber (
  email       VARCHAR(255)  NOT NULL              COMMENT 'the signed-in person who ticked it',
  created_at  TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Who is emailed each new survey (My account)';
