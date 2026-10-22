-- ═══════════════════════════════════════════════════════════════════════════
-- CIP least-privilege accounts on cip_stg. Run as a DBA. Not applied by scripts/init_db.py.
-- Replace <ETL_PWD> / <APP_PWD> before running. Do not commit real values.
-- MySQL matches wildcards only in database names, never table names, so grants name the database or each table.
-- cip_stg holds only CIP tables (the warehouse is dwh_stg, which neither account can touch).
-- ═══════════════════════════════════════════════════════════════════════════

-- Writer: the scheduled loader only (scripts/weekly_forsta.py). Builds temporary tables for the cube.
CREATE USER IF NOT EXISTS 'cip_etl'@'%' IDENTIFIED BY '<ETL_PWD>' REQUIRE SSL;
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, REFERENCES, DROP, CREATE TEMPORARY TABLES, CREATE VIEW
  ON `cip_stg`.* TO 'cip_etl'@'%';

-- Portal (API): reads everything, writes only what the team keeps in the portal (api/team.py).
-- Set APP_DB_USER / APP_DB_PASSWORD to this account; without them the API falls back to the STG owner account.
CREATE USER IF NOT EXISTS 'cip_app'@'%' IDENTIFIED BY '<APP_PWD>' REQUIRE SSL;
GRANT SELECT ON `cip_stg`.* TO 'cip_app'@'%';
GRANT INSERT, UPDATE, DELETE ON `cip_stg`.`cip_team_view`     TO 'cip_app'@'%';
GRANT INSERT, UPDATE, DELETE ON `cip_stg`.`cip_metric_alert`  TO 'cip_app'@'%';
GRANT INSERT, UPDATE, DELETE ON `cip_stg`.`cip_audience`      TO 'cip_app'@'%';
GRANT INSERT, UPDATE, DELETE ON `cip_stg`.`cip_board`         TO 'cip_app'@'%';
GRANT INSERT, UPDATE, DELETE ON `cip_stg`.`cip_board_item`    TO 'cip_app'@'%';
GRANT INSERT, UPDATE, DELETE ON `cip_stg`.`cip_board_comment` TO 'cip_app'@'%';
