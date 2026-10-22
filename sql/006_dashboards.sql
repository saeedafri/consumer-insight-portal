-- ═══════════════════════════════════════════════════════════════════════════
-- Backend cache for SAMPLE screen payloads (not the ETL). The ETL ends at the serving
-- tables (005_serving.sql); api/dashboards.py reads them and stores one finished payload
-- per screen and wave here. The API holds the published payloads in memory.
--
--   cip_dash_build      one build of one dashboard for one wave (audit + version)
--   cip_dash_metric     every number on the dashboard, with its base, prior-week
--                       and last-year comparison and quality flags (queryable)
--   cip_dash_payload    the exact JSON the browser receives, plus a gzip copy
--   cip_dash_published  the pointer users see: one row per (dashboard, wave);
--                       switching it is one UPDATE inside the build transaction
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS cip_dash_build (
    build_id        INT UNSIGNED NOT NULL AUTO_INCREMENT,
    dashboard_code  VARCHAR(40)  NOT NULL,
    survey_id       INT UNSIGNED NOT NULL,
    prior_survey_id INT UNSIGNED NULL COMMENT 'Previous wave of the same series and season, if loaded',
    ly_survey_id    INT UNSIGNED NULL COMMENT 'Same calendar week last season, if loaded',
    cube_built_at   TIMESTAMP    NULL COMMENT 'Freshness of the cube cells this build read',
    built_at        TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (build_id),
    KEY ix_dash_build (dashboard_code, survey_id),
    CONSTRAINT fk_dash_build_survey FOREIGN KEY (survey_id) REFERENCES cip_survey (survey_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='One build of one dashboard for one wave';

CREATE TABLE IF NOT EXISTS cip_dash_metric (
    build_id      INT UNSIGNED  NOT NULL,
    metric_code   VARCHAR(40)   NOT NULL COMMENT 'e.g. not_started, retailers, started_by_generation',
    segment       VARCHAR(80)   NOT NULL DEFAULT 'Total' COMMENT 'Total, or a cut value such as GenZ',
    rank_no       SMALLINT      NOT NULL DEFAULT 0 COMMENT '0 for a single tile, 1..N for ranked lists',
    label         VARCHAR(255)  NOT NULL,
    n             INT           NOT NULL,
    base_n        INT           NOT NULL,
    pct           DECIMAL(6,3)  NOT NULL COMMENT '100 * n / base_n, unrounded to 3 dp',
    prior_pct     DECIMAL(6,3)  NULL,
    prior_base_n  INT           NULL,
    ly_pct        DECIMAL(6,3)  NULL,
    ly_base_n     INT           NULL,
    flags         SET('small_base','base_changed_prior','base_changed_ly','prior_missing','ly_missing','suppressed') NOT NULL DEFAULT '',
    PRIMARY KEY (build_id, metric_code, segment, rank_no),
    CONSTRAINT fk_dash_metric_build FOREIGN KEY (build_id) REFERENCES cip_dash_build (build_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Every number a dashboard shows, with its base and comparisons';

CREATE TABLE IF NOT EXISTS cip_dash_payload (
    build_id     INT UNSIGNED NOT NULL,
    etag         CHAR(16)     NOT NULL COMMENT 'First 16 hex of SHA-256 of payload_json',
    payload_json MEDIUMTEXT   NOT NULL,
    payload_gz   MEDIUMBLOB   NOT NULL COMMENT 'gzip of payload_json: sent as-is with Content-Encoding: gzip',
    PRIMARY KEY (build_id),
    CONSTRAINT fk_dash_payload_build FOREIGN KEY (build_id) REFERENCES cip_dash_build (build_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='The exact response the API sends for a build';

CREATE TABLE IF NOT EXISTS cip_dash_published (
    dashboard_code VARCHAR(40)  NOT NULL,
    survey_id      INT UNSIGNED NOT NULL,
    build_id       INT UNSIGNED NOT NULL,
    published_at   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (dashboard_code, survey_id),
    KEY ix_dash_published_at (published_at),
    CONSTRAINT fk_dash_published_build FOREIGN KEY (build_id) REFERENCES cip_dash_build (build_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='What users see: the live build of each dashboard wave';
