-- ═══════════════════════════════════════════════════════════════════════════
-- CIP least-privilege accounts on cip_stg. Run as a DBA.
-- Replace <ETL_PWD> / <APP_PWD> before running. Do not commit real values.
-- ═══════════════════════════════════════════════════════════════════════════

-- Writer: used only by the scheduled loader.
CREATE USER IF NOT EXISTS 'csi_etl'@'%' IDENTIFIED BY '<ETL_PWD>' REQUIRE SSL;
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, REFERENCES
  ON `cip_stg`.`cip_%` TO 'csi_etl'@'%';

-- Reader: used by the Streamlit portal. Cannot modify anything.
CREATE USER IF NOT EXISTS 'csi_app'@'%' IDENTIFIED BY '<APP_PWD>' REQUIRE SSL;
GRANT SELECT ON `cip_stg`.`cip_%`   TO 'csi_app'@'%';
GRANT SELECT ON `cip_stg`.`v_cip_%` TO 'csi_app'@'%';

FLUSH PRIVILEGES;
