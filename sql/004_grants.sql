-- ═══════════════════════════════════════════════════════════════════════════
-- CSI least-privilege accounts on dwh_stg. Run as a DBA.
-- Replace <ETL_PWD> / <APP_PWD> before running. Do not commit real values.
-- ═══════════════════════════════════════════════════════════════════════════

-- Writer: used only by the scheduled loader.
CREATE USER IF NOT EXISTS 'csi_etl'@'%' IDENTIFIED BY '<ETL_PWD>' REQUIRE SSL;
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, REFERENCES
  ON `dwh_stg`.`csi_%` TO 'csi_etl'@'%';

-- Reader: used by the Streamlit portal. Cannot modify anything.
CREATE USER IF NOT EXISTS 'csi_app'@'%' IDENTIFIED BY '<APP_PWD>' REQUIRE SSL;
GRANT SELECT ON `dwh_stg`.`csi_%`   TO 'csi_app'@'%';
GRANT SELECT ON `dwh_stg`.`v_csi_%` TO 'csi_app'@'%';

FLUSH PRIVILEGES;
