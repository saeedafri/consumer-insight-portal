-- The frozen part of a dataset a team built by hand before CIP kept it: their workbook's rows and sheets, gzip-compressed
-- JSON, one row per dataset, replaced when they hand over a new copy. Written by `python -m etl.consumer_health --history`,
-- read by etl/consumer_health.py publish, which adds every newer week from CIP's own respondents.
CREATE TABLE IF NOT EXISTS cip_dataset_history (
  dataset    VARCHAR(60)  NOT NULL              COMMENT 'which dataset: consumer_health',
  loaded_at  DATETIME     NOT NULL              COMMENT 'when the team''s workbook was loaded (UTC)',
  source     VARCHAR(255) NOT NULL              COMMENT 'the workbook''s file name, for the record',
  payload    MEDIUMBLOB   NOT NULL              COMMENT 'gzip JSON: header, rows, source_qa, dictionary, read_me',
  PRIMARY KEY (dataset)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Hand-built datasets CIP now keeps up to date';
