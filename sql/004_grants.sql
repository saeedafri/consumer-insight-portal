-- ═══════════════════════════════════════════════════════════════════════════
-- CIP — least-privilege accounts. Run as a DBA on the STG (DWH) server.
-- Replace <DB>, <ETL_PWD>, <APP_PWD> before running. Do not commit real values.
-- ═══════════════════════════════════════════════════════════════════════════

-- Writer: used only by etl/ (the scheduled Forsta pull).
CREATE USER IF NOT EXISTS 'cip_etl'@'%' IDENTIFIED BY '<ETL_PWD>' REQUIRE SSL;
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, REFERENCES
  ON `<DB>`.`cip_%` TO 'cip_etl'@'%';

-- Reader: used by the Streamlit app. Cannot modify anything.
CREATE USER IF NOT EXISTS 'cip_app'@'%' IDENTIFIED BY '<APP_PWD>' REQUIRE SSL;
GRANT SELECT ON `<DB>`.`cip_%` TO 'cip_app'@'%';
GRANT SELECT ON `<DB>`.`v_cip_%` TO 'cip_app'@'%';

FLUSH PRIVILEGES;
