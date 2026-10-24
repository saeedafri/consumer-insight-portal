# 20 · MySQL `cip_stg`: verified inventory, indexes, security (corrected 23 Oct 2026, evening)

> **Correction notice.** The first version of this file contained an invented EXPLAIN plan, invented index names (`idx_survey`, `idx_question`, `idx_wave_q_dim`), a claim that `srv_answer` has no index and does a 10M-row scan, and a "12.4M multi-select zero rows / 2.6 GB" figure. None of those were measured. They were wrong and are removed. Everything below was queried live on 23 Oct 2026 (read-only). Label: **[O]** observed, **[I]** inferred, **[U]** not measured.

## 1. Table sizes [O] (`information_schema.tables`, row counts are InnoDB estimates)

| Table | Rows | Data MB | Index MB | Total MB |
|---|---|---|---|---|
| cip_answer | 27,796,732 | 2,641 | 3,348 | 5,989 |
| dwh_smresponseqa (legacy copy) | 5,206,395 | 1,424 | 946 | 2,370 |
| cip_agg_cell | 2,789,342 | 687 | 763 | 1,450 |
| srv_answer | 10,021,628 | 1,209 | 0 (PK only, clustered) | 1,209 |
| srv_result | 2,535,697 | 488 | 164 | 652 |
| cip_tracker_line | 15,311 | 239 | 2 | 241 |
| cip_respondent | 194,818 | 34 | 50 | 84 |
| cip_profile | 188,337 | 31 | 25 | 56 |
| cip_concept_map | 80,299 | 7 | 23 | 30 |

Server: MySQL 8.0.46-azure, `innodb_buffer_pool_size` = 2.00 GB (8 instances), `max_connections` 341, utf8mb4 / `utf8mb4_0900_ai_ci`. The instance holds 7 databases [O: SHOW DATABASES]; the ~560 GB total comes from the earlier Claude Opus audit and was **not** re-measured by me [U].

## 2. Real indexes [O] (`information_schema.statistics`)

| Table | Indexes |
|---|---|
| cip_answer | PRIMARY(answer_id); `uq_answer`(respondent_id, field_id); `ix_answer_cover`(survey_id, field_id, value_code, respondent_id); FK `fk_answer_field`(field_id) |
| srv_answer | PRIMARY(survey_id, qcode, item_id, option_id, respondent_id) only |
| srv_result | PRIMARY(survey_id, qcode, dim, dim_value, item_id, option_id); `ix_srv_concept`(concept_option_id, dim, dim_value, survey_id) |
| cip_agg_cell | PRIMARY(cell_id); `uq_agg_cell`(survey_id, cell_key); `ix_agg_map`; `ix_agg_question`; `ix_agg_concept`; FK on question_id |

Findings:
- **cip_answer: indexes (3.35 GB) are larger than data (2.64 GB) [O].** The big one is the covering index `ix_answer_cover` plus `uq_answer`. Whether `ix_answer_cover` can be narrowed or dropped depends on the queries that use it [U]. The earlier advice to "drop `idx_survey`/`idx_question`" was wrong, those indexes do not exist.
- **srv_answer is not an unindexed table scan.** The clustered PK starts with `(survey_id, qcode, item_id, option_id, …)`, so a single-question read is a primary-key range. The earlier "1.8–3.2 s scan" claim was invented. Real cold timing of the crosstab fallback path is [U].
- **Hot read path [O]:** `EXPLAIN SELECT * FROM srv_result WHERE survey_id=415 AND qcode='Q1' AND dim='total'` → `type=ref`, `key=PRIMARY`, `key_len=328`, `ref=const,const,const`, ~15 rows, no filesort.

## 3. Verified issues

| # | Finding | Evidence |
|---|---|---|
| D1 | App and ETL use personal account `mohdsaeedafri@%`: ALL PRIVILEGES on `chainxydata_stg`, `cip_stg`, `coresight_market_data_stg`, `dwh_directus_stg`; SELECT+SHOW VIEW on `dwh_stg` | `SHOW GRANTS` [O] |
| D2 | All 12 `v_cip_*` views: DEFINER `mohdsaeedafri@%`, SQL SECURITY DEFINER | `information_schema.views` [O] |
| D3 | 161,734 of 161,748 rows in `dwh_smresponse` hold a non-null `ip_address` | COUNT [O] |
| D4 | `CIP_RESPONDENT_SALT` is not set in `.env` | grep [O]. Whether it is set in `~/.config/cip/api.env` or the ETL's environment is [U] |
| D5 | 2 GB buffer pool vs 11.9 GB schema on a shared instance. Real pressure (hit ratio) not measured | [I] |
| D6 | `dwh_smresponseqa` (2.37 GB) is a legacy copy. Whether anything still reads it is [U] (check the code before dropping) | [O] size / [U] usage |
| D7 | 766 serving cells lost across 8 waves; Survey 97 Q7 serves Facebook, Instagram, Pinterest, TikTok, Twitter, YouTube at 0.000 % | Per-wave `rows_built` vs cube count and `srv_result` query [O] (see doc 10) |
| D8 | `concept_option_id` non-NULL in 0 of 12,425 (wave 415) and 0 of 14,639 (wave 412) `srv_result` rows | [O]. `cip_concept_map`: 87,086 confirmed, 3,771 proposed [O] |

(The earlier claim of "27,064 rows" was the sum 12,425 + 14,639; the Claude Opus doc's figure is consistent.)

## 4. Not measured here
Buffer-pool hit ratio, slow-query log, multi-select zero-row share of `cip_answer`, crosstab cold-path timing, the 560 GB figure, and whether `dwh_*` tables are still read. Run them before any index or table is dropped.
