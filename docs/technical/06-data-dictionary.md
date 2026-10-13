# 6. Data dictionary — `cip_` tables and views in `dwh_stg`

Generated from the live database by `scripts/data_dictionary.py`; row counts are InnoDB estimates.

| Object | Kind | Rows (approx.) | Purpose |
|---|---|---:|---|
| [`cip_agg_cell`](#cip-agg-cell) | table | 1,796,799 | Pre-computed counts per wave x answer x cut x cohort. |
| [`cip_answer`](#cip-answer) | table | 22,959,662 | Every answer, long format. ~151k rows per wave. |
| [`cip_auth_session`](#cip-auth-session) | table | 2 | Sign-in audit and revocation. |
| [`cip_banner`](#cip-banner) | table | 0 | Cross-tab column groups. |
| [`cip_cohort_def`](#cip-cohort-def) | table | 2 | Named, versioned respondent rules. |
| [`cip_concept`](#cip-concept) | table | 1,558 | Canonical questions, stable across waves and platforms. |
| [`cip_concept_map`](#cip-concept-map) | table | 63,375 | Wave question/item/option -> canonical concept, proposed or confirmed. |
| [`cip_concept_option`](#cip-concept-option) | table | 12,708 | Canonical answers, with band midpoints. |
| [`cip_crosstab`](#cip-crosstab) | table | 0 | Cross-tab cells: percentage, count, true base, significance. |
| [`cip_crosstab_run`](#cip-crosstab-run) | table | 0 | One row per cross-tab export, with its base and filter settings. |
| [`cip_field`](#cip-field) | table | 51,932 | Export column -> question/item map. |
| [`cip_forsta_survey`](#cip-forsta-survey) | table | 90 | Register of every Forsta survey the key can see, and what the ETL did with it. |
| [`cip_item`](#cip-item) | table | 45,281 | List items and grid rows. |
| [`cip_load_error`](#cip-load-error) | table | 0 | Rows that failed validation, kept for review. |
| [`cip_load_log`](#cip-load-log) | table | 393 | Audit trail. Nothing enters CSI without a row here. |
| [`cip_load_state`](#cip-load-state) | table | 0 | Watermarks so incremental pulls never re-read a whole survey. |
| [`cip_option`](#cip-option) | table | 28,832 | Answer codes and their labels. |
| [`cip_profile`](#cip-profile) | table | 166,393 | Demographic cuts, one row per respondent. |
| [`cip_profile_map`](#cip-profile-map) | table | 1,184 | Which question feeds each demographic cut, per wave. Auditable and editable. |
| [`cip_publication`](#cip-publication) | table | 2 | A delivered chart or table, frozen at a version. |
| [`cip_publication_cell`](#cip-publication-cell) | table | 196 | The frozen numbers of a publication. |
| [`cip_question`](#cip-question) | table | 8,218 | Questions, with their own answering base. |
| [`cip_respondent`](#cip-respondent) | table | 165,948 | One row per interview. |
| [`cip_respondent_cohort`](#cip-respondent-cohort) | table | 6,215 | Materialised cohort membership. |
| [`cip_saved_view`](#cip-saved-view) | table | 0 | Saved filter + question sets, re-run against current data. |
| [`cip_search`](#cip-search) | table | 10,034 | Search index: one row per wave, question and concept (FULLTEXT). |
| [`cip_segment`](#cip-segment) | table | 0 | Cross-tab columns with their Forsta definitions. |
| [`cip_survey`](#cip-survey) | table | 301 | Survey waves. |
| [`cip_topic`](#cip-topic) | table | 15 | Editorial grouping of questions. |
| [`cip_tracker_line`](#cip-tracker-line) | table | 4,223 | The data team's line-by-line rows: one per qualified tracker respondent, JSON in their column order. |
| [`cip_wave_module`](#cip-wave-module) | table | 242 | Survey calendar: every Forsta survey x module (lead sector, topic, seasonal, event, annual, ad hoc). |
| [`cip_weight`](#cip-weight) | table | 0 | One weight per respondent per scheme. |
| [`cip_weight_scheme`](#cip-weight-scheme) | table | 0 | Named weighting schemes, per wave. |
| [`v_cip_answers`](#v-cip-answers) | view |  | VIEW |
| [`v_cip_crosstab`](#v-cip-crosstab) | view |  | VIEW |
| [`v_cip_grid`](#v-cip-grid) | view |  | VIEW |
| [`v_cip_item_incidence`](#v-cip-item-incidence) | view |  | VIEW |
| [`v_cip_mapping_queue`](#v-cip-mapping-queue) | view |  | VIEW |
| [`v_cip_question_base`](#v-cip-question-base) | view |  | VIEW |
| [`v_cip_single_distribution`](#v-cip-single-distribution) | view |  | VIEW |
| [`v_cip_survey_health`](#v-cip-survey-health) | view |  | VIEW |
| [`v_cip_trend`](#v-cip-trend) | view |  | VIEW |

## cip_agg_cell

*Table* — Pre-computed counts per wave x answer x cut x cohort.

| Column | Type | Null | Key | Default | Meaning |
|---|---|---|---|---|---|
| `cell_id` | bigint unsigned | NO | PRI |  |  |
| `survey_id` | int unsigned | NO | MUL |  | → cip_survey.survey_id (cascade) |
| `cell_key` | varchar(200) | NO |  |  | question:item:option:cohort:scheme:dim:value |
| `question_id` | int unsigned | NO | MUL |  | → cip_question.question_id (cascade) |
| `item_id` | int unsigned | YES |  |  |  |
| `option_id` | int unsigned | YES |  |  |  |
| `concept_option_id` | int unsigned | YES | MUL |  |  |
| `cohort_id` | int unsigned | YES |  |  | NULL = all qualified respondents |
| `scheme_id` | int unsigned | YES |  |  | NULL = unweighted |
| `dim` | varchar(30) | NO |  |  | total, gender, age_band, … |
| `dim_value` | varchar(120) | NO |  |  |  |
| `n` | int | NO |  |  |  |
| `base_n` | int | NO |  |  |  |
| `n_weighted` | decimal(14,4) | YES |  |  |  |
| `base_weighted` | decimal(14,4) | YES |  |  |  |
| `sum_age_mid` | decimal(14,4) | YES |  |  |  |
| `sum_income_mid_k` | decimal(16,4) | YES |  |  |  |
| `built_at` | timestamp | NO |  | CURRENT_TIMESTAMP |  |
| `map_key` | varchar(40) | YES |  |  |  |
| `n_age_mid` | int | YES |  |  |  |
| `n_income_mid` | int | YES |  |  |  |

Indexes: `fk_agg_question` (btree: question_id); `ix_agg_concept` (btree: concept_option_id, cohort_id, dim, survey_id); `ix_agg_map` (btree: survey_id, map_key, cohort_id, dim); `ix_agg_question` (btree: survey_id, question_id, dim); `PRIMARY` (btree: cell_id); `uq_agg_cell` (unique btree: survey_id, cell_key)

## cip_answer

*Table* — Every answer, long format. ~151k rows per wave.

| Column | Type | Null | Key | Default | Meaning |
|---|---|---|---|---|---|
| `answer_id` | bigint unsigned | NO | PRI |  |  |
| `respondent_id` | bigint unsigned | NO | MUL |  | → cip_respondent.respondent_id (cascade) |
| `survey_id` | int unsigned | NO | MUL |  | denormalised for filter speed |
| `field_id` | int unsigned | NO | MUL |  | → cip_field.field_id (cascade) |
| `value_code` | int | YES |  |  | 0/1, 1-5, 1-54 |
| `value_label` | varchar(500) | YES |  |  | resolved label, denormalised for display |
| `value_number` | decimal(18,4) | YES |  |  | open numeric |
| `value_text` | text | YES | MUL |  | open-ended verbatim |

Indexes: `fk_answer_field` (btree: field_id); `ft_answer_text` (fulltext: value_text); `ix_answer_cover` (btree: survey_id, field_id, value_code, respondent_id); `ix_answer_respondent` (btree: respondent_id); `PRIMARY` (btree: answer_id); `uq_answer` (unique btree: respondent_id, field_id)

## cip_auth_session

*Table* — Sign-in audit and revocation.

| Column | Type | Null | Key | Default | Meaning |
|---|---|---|---|---|---|
| `session_id` | varchar(64) | NO | PRI |  |  |
| `user_email` | varchar(200) | NO | MUL |  |  |
| `user_name` | varchar(200) | YES |  |  |  |
| `provider` | varchar(20) | NO |  | local |  |
| `created_at` | timestamp | NO |  | CURRENT_TIMESTAMP |  |
| `expires_at` | datetime | YES |  |  |  |
| `revoked_at` | datetime | YES |  |  |  |
| `request_meta` | varchar(500) | YES |  |  | host and user agent at sign-in |

Indexes: `ix_auth_user` (btree: user_email, created_at); `PRIMARY` (btree: session_id)

## cip_banner

*Table* — Cross-tab column groups.

| Column | Type | Null | Key | Default | Meaning |
|---|---|---|---|---|---|
| `banner_id` | int unsigned | NO | PRI |  |  |
| `survey_id` | int unsigned | NO | MUL |  | → cip_survey.survey_id (cascade) |
| `banner_code` | varchar(50) | NO |  |  | AGE, GENDER, INCOME |
| `banner_name` | varchar(500) | NO |  |  | header text as printed |
| `source_q` | varchar(50) | YES |  |  | question the banner is built from |
| `sort_order` | smallint | NO |  | 0 |  |

Indexes: `PRIMARY` (btree: banner_id); `uq_banner` (unique btree: survey_id, banner_code)

## cip_cohort_def

*Table* — Named, versioned respondent rules.

| Column | Type | Null | Key | Default | Meaning |
|---|---|---|---|---|---|
| `cohort_id` | int unsigned | NO | PRI |  |  |
| `cohort_code` | varchar(60) | NO | MUL |  | BEAUTY_SHOPPER |
| `version` | smallint unsigned | NO |  | 1 |  |
| `cohort_name` | varchar(200) | NO |  |  |  |
| `rule_json` | json | NO |  |  | any/all over concepts; see the spec §5.4 |
| `base_note` | varchar(500) | YES |  |  |  |
| `owner_email` | varchar(200) | YES |  |  |  |
| `is_current` | tinyint(1) | NO |  | 1 |  |
| `created_at` | timestamp | NO |  | CURRENT_TIMESTAMP |  |

Indexes: `PRIMARY` (btree: cohort_id); `uq_cohort_def` (unique btree: cohort_code, version)

## cip_concept

*Table* — Canonical questions, stable across waves and platforms.

| Column | Type | Null | Key | Default | Meaning |
|---|---|---|---|---|---|
| `concept_id` | int unsigned | NO | PRI |  |  |
| `concept_code` | varchar(80) | NO | UNI |  | BEAUTY_RETAILER_3M |
| `concept_name` | varchar(255) | NO |  |  |  |
| `concept_group` | varchar(80) | YES | MUL |  | rows of one grid share a group |
| `topic_id` | smallint unsigned | YES | MUL |  | → cip_topic.topic_id (set null) |
| `qtype` | enum('single','multi','grid_single','grid_multi','numeric','text','datetime') | NO |  |  |  |
| `description` | varchar(1000) | YES |  |  |  |
| `created_at` | timestamp | NO |  | CURRENT_TIMESTAMP |  |
| `match_text` | varchar(2000) | YES |  |  |  |

Indexes: `fk_concept_topic` (btree: topic_id); `ix_concept_group` (btree: concept_group); `PRIMARY` (btree: concept_id); `uq_concept` (unique btree: concept_code)

## cip_concept_map

*Table* — Wave question/item/option -> canonical concept, proposed or confirmed.

| Column | Type | Null | Key | Default | Meaning |
|---|---|---|---|---|---|
| `map_id` | bigint unsigned | NO | PRI |  |  |
| `survey_id` | int unsigned | NO | MUL |  | → cip_survey.survey_id (cascade) |
| `map_key` | varchar(80) | NO |  |  | question_id:item_id:option_id, 0 when absent |
| `question_id` | int unsigned | NO | MUL |  | → cip_question.question_id (cascade) |
| `item_id` | int unsigned | YES | MUL |  | → cip_item.item_id (cascade) |
| `option_id` | int unsigned | YES | MUL |  | → cip_option.option_id (cascade) |
| `concept_id` | int unsigned | NO | MUL |  | → cip_concept.concept_id (cascade) |
| `concept_option_id` | int unsigned | YES | MUL |  | → cip_concept_option.concept_option_id (cascade) |
| `status` | enum('proposed','confirmed','rejected') | NO | MUL | proposed |  |
| `method` | enum('exact_text','similar_text','manual') | NO |  |  |  |
| `confidence` | decimal(5,4) | YES |  |  |  |
| `evidence` | varchar(1000) | YES |  |  | why the harmoniser proposed it |
| `reviewed_by` | varchar(200) | YES |  |  |  |
| `reviewed_at` | datetime | YES |  |  |  |
| `created_at` | timestamp | NO |  | CURRENT_TIMESTAMP |  |

Indexes: `fk_map_concept` (btree: concept_id); `fk_map_item` (btree: item_id); `fk_map_option` (btree: option_id); `fk_map_question` (btree: question_id); `ix_map_concept_option` (btree: concept_option_id); `ix_map_question` (btree: survey_id, question_id); `ix_map_status` (btree: status); `PRIMARY` (btree: map_id); `uq_concept_map` (unique btree: survey_id, map_key)

## cip_concept_option

*Table* — Canonical answers, with band midpoints.

| Column | Type | Null | Key | Default | Meaning |
|---|---|---|---|---|---|
| `concept_option_id` | int unsigned | NO | PRI |  |  |
| `concept_id` | int unsigned | NO | MUL |  | → cip_concept.concept_id (cascade) |
| `option_code` | varchar(80) | NO |  |  | amazon |
| `option_label` | varchar(500) | NO |  |  | Amazon.com |
| `sort_order` | smallint | NO |  | 0 |  |
| `midpoint` | decimal(12,4) | YES |  |  | numeric midpoint of a band: 23.5, 74.9995 |
| `net_group` | varchar(50) | YES |  |  | TOP2, ANY_DRUGSTORE |
| `is_nonresponse` | tinyint(1) | NO |  | 0 |  |

Indexes: `PRIMARY` (btree: concept_option_id); `uq_concept_option` (unique btree: concept_id, option_code)

## cip_crosstab

*Table* — Cross-tab cells: percentage, count, true base, significance.

| Column | Type | Null | Key | Default | Meaning |
|---|---|---|---|---|---|
| `crosstab_id` | bigint unsigned | NO | PRI |  |  |
| `run_id` | int unsigned | NO | MUL |  | → cip_crosstab_run.run_id (cascade) |
| `survey_id` | int unsigned | NO | MUL |  |  |
| `question_id` | int unsigned | NO | MUL |  | → cip_question.question_id (cascade) |
| `item_id` | int unsigned | YES | MUL |  |  |
| `option_id` | int unsigned | YES |  |  |  |
| `segment_id` | int unsigned | NO | MUL |  | → cip_segment.segment_id (cascade) |
| `item_label` | varchar(500) | YES |  |  | grid sub-item, e.g. the retailer being rated in DP7 |
| `stub_label` | varchar(1000) | NO |  |  | row label as printed |
| `stub_key` | varchar(600) | NO |  |  | item_label|stub_label — unique within a table |
| `stub_type` | enum('item','net','mean','count','base') | NO |  | item |  |
| `pct` | decimal(9,6) | YES |  |  | 0.527228 = 52.7% |
| `count_n` | int | YES |  |  |  |
| `answer_base_n` | int | YES |  |  | the true denominator: count_n / pct |
| `sig_letters` | varchar(40) | YES |  |  | segments this cell significantly beats |

Indexes: `fk_crosstab_question` (btree: question_id); `fk_crosstab_segment` (btree: segment_id); `ix_crosstab_item` (btree: item_id); `ix_crosstab_lookup` (btree: survey_id, question_id, segment_id); `PRIMARY` (btree: crosstab_id); `uq_crosstab` (unique btree: run_id, question_id, stub_key, segment_id)

## cip_crosstab_run

*Table* — One row per cross-tab export, with its base and filter settings.

| Column | Type | Null | Key | Default | Meaning |
|---|---|---|---|---|---|
| `run_id` | int unsigned | NO | PRI |  |  |
| `survey_id` | int unsigned | NO | MUL |  | → cip_survey.survey_id (cascade) |
| `run_label` | varchar(255) | NO |  |  |  |
| `respondent_base` | varchar(100) | YES |  |  | "Qualified Only" |
| `extra_filter` | varchar(500) | YES |  |  |  |
| `table_set` | varchar(100) | YES |  |  |  |
| `pct_base` | varchar(100) | YES |  |  | "Total Answering" — see csi_crosstab.answer_base_n |
| `stat_test` | varchar(100) | YES |  |  |  |
| `date_from` | date | YES |  |  |  |
| `date_to` | date | YES |  |  |  |
| `source_type` | enum('api','excel') | NO |  | excel |  |
| `source_file` | varchar(255) | YES |  |  |  |
| `is_current` | tinyint(1) | NO |  | 1 |  |
| `created_at` | timestamp | NO |  | CURRENT_TIMESTAMP |  |

Indexes: `ix_run_survey` (btree: survey_id, is_current); `PRIMARY` (btree: run_id)

## cip_field

*Table* — Export column -> question/item map.

| Column | Type | Null | Key | Default | Meaning |
|---|---|---|---|---|---|
| `field_id` | int unsigned | NO | PRI |  |  |
| `survey_id` | int unsigned | NO | MUL |  | → cip_survey.survey_id (cascade) |
| `question_id` | int unsigned | YES | MUL |  | → cip_question.question_id (cascade) |
| `item_id` | int unsigned | YES | MUL |  | set when the column is one row of a list/grid → cip_item.item_id (cascade) |
| `field_name` | varchar(100) | NO |  |  | exact export header: q1r1, D2, uuid |
| `value_type` | enum('code','numeric','text','datetime') | NO |  |  |  |
| `col_position` | smallint | YES |  |  |  |

Indexes: `ix_field_item` (btree: item_id); `ix_field_question` (btree: question_id); `PRIMARY` (btree: field_id); `uq_field` (unique btree: survey_id, field_name)

## cip_forsta_survey

*Table* — Register of every Forsta survey the key can see, and what the ETL did with it.

| Column | Type | Null | Key | Default | Meaning |
|---|---|---|---|---|---|
| `forsta_path` | varchar(255) | NO | PRI |  | selfserve/58f/260907 |
| `title` | varchar(500) | NO |  |  |  |
| `state` | varchar(30) | NO |  |  | Forsta state: testing, live, closed |
| `hibernated` | tinyint(1) | NO |  | 0 | 1 = Forsta answers 428 until reactivated |
| `tags` | varchar(500) | YES |  |  |  |
| `study_type` | enum('tracker','annual','adhoc') | NO |  | adhoc |  |
| `created_on` | datetime | YES |  |  |  |
| `launched_at` | datetime | YES |  |  |  |
| `closed_at` | datetime | YES |  |  |  |
| `qualified_n` | int | YES |  |  |  |
| `total_n` | int | YES |  |  |  |
| `last_seen` | datetime | NO |  |  |  |
| `load_state` | enum('new','due','loaded','failed','hibernated','testing') | NO | MUL | new |  |
| `survey_id` | int unsigned | YES |  |  | cip_survey row once loaded |
| `loaded_at` | datetime | YES |  |  |  |
| `last_error` | varchar(1000) | YES |  |  |  |

Indexes: `ix_forsta_due` (btree: load_state, closed_at); `PRIMARY` (btree: forsta_path)

## cip_item

*Table* — List items and grid rows.

| Column | Type | Null | Key | Default | Meaning |
|---|---|---|---|---|---|
| `item_id` | int unsigned | NO | PRI |  |  |
| `question_id` | int unsigned | NO | MUL |  | → cip_question.question_id (cascade) |
| `item_code` | varchar(50) | NO |  |  | q1r1, DP7r3 |
| `item_label` | varchar(1000) | NO |  |  |  |
| `item_short` | varchar(255) | YES |  |  | trimmed for axis ticks |
| `is_exclusive` | tinyint(1) | NO |  | 0 | 1 = "None of these" — drop from rankings |
| `is_other` | tinyint(1) | NO |  | 0 | 1 = Other (please specify) |
| `sort_order` | smallint | NO |  | 0 |  |
| `left_label` | varchar(500) | YES |  |  |  |
| `right_label` | varchar(500) | YES |  |  |  |

Indexes: `PRIMARY` (btree: item_id); `uq_item` (unique btree: question_id, item_code)

## cip_load_error

*Table* — Rows that failed validation, kept for review.

| Column | Type | Null | Key | Default | Meaning |
|---|---|---|---|---|---|
| `error_id` | bigint unsigned | NO | PRI |  |  |
| `load_id` | bigint unsigned | NO | MUL |  | → cip_load_log.load_id (cascade) |
| `record_ref` | varchar(200) | YES |  |  | record number or sheet!cell |
| `reason` | varchar(500) | NO |  |  |  |
| `payload` | json | YES |  |  |  |

Indexes: `ix_error_load` (btree: load_id); `PRIMARY` (btree: error_id)

## cip_load_log

*Table* — Audit trail. Nothing enters CSI without a row here.

| Column | Type | Null | Key | Default | Meaning |
|---|---|---|---|---|---|
| `load_id` | bigint unsigned | NO | PRI |  |  |
| `survey_id` | int unsigned | YES | MUL |  |  |
| `source_type` | enum('api','excel','manual') | NO |  |  |  |
| `object_type` | enum('datamap','data','crosstab','profile') | NO |  |  |  |
| `source_ref` | varchar(500) | YES |  |  | endpoint URL or file name |
| `rows_read` | int | NO |  | 0 |  |
| `rows_loaded` | int | NO |  | 0 |  |
| `rows_bad` | int | NO |  | 0 |  |
| `status` | enum('running','success','partial','failed') | NO |  | running |  |
| `error_text` | text | YES |  |  |  |
| `started_at` | datetime | NO |  | CURRENT_TIMESTAMP |  |
| `finished_at` | datetime | YES |  |  |  |
| `archive_uri` | varchar(1000) | YES |  |  |  |
| `archive_sha256` | char(64) | YES |  |  |  |

Indexes: `ix_load_survey` (btree: survey_id, object_type, started_at); `PRIMARY` (btree: load_id)

## cip_load_state

*Table* — Watermarks so incremental pulls never re-read a whole survey.

| Column | Type | Null | Key | Default | Meaning |
|---|---|---|---|---|---|
| `feed_name` | varchar(100) | NO | PRI |  |  |
| `survey_id` | int unsigned | YES |  |  |  |
| `last_record` | int unsigned | YES |  |  |  |
| `last_completed` | datetime | YES |  |  | watermark for incremental pulls |
| `last_ack_at` | datetime | YES |  |  |  |
| `last_status` | varchar(50) | YES |  |  |  |
| `updated_at` | timestamp | NO |  | CURRENT_TIMESTAMP |  |

Indexes: `PRIMARY` (btree: feed_name)

## cip_option

*Table* — Answer codes and their labels.

| Column | Type | Null | Key | Default | Meaning |
|---|---|---|---|---|---|
| `option_id` | int unsigned | NO | PRI |  |  |
| `question_id` | int unsigned | NO | MUL |  | → cip_question.question_id (cascade) |
| `value_code` | int | NO |  |  |  |
| `value_label` | varchar(500) | NO |  |  |  |
| `is_nonresponse` | tinyint(1) | NO |  | 0 | Don't know / Prefer not to say — excluded from Top-2-Box |
| `net_group` | varchar(50) | YES |  |  | TOP2 / BOT2 for net calculations |
| `sort_order` | smallint | NO |  | 0 |  |

Indexes: `PRIMARY` (btree: option_id); `uq_option` (unique btree: question_id, value_code)

## cip_profile

*Table* — Demographic cuts, one row per respondent.

| Column | Type | Null | Key | Default | Meaning |
|---|---|---|---|---|---|
| `respondent_id` | bigint unsigned | NO | PRI |  | → cip_respondent.respondent_id (cascade) |
| `survey_id` | int unsigned | NO | MUL |  | → cip_survey.survey_id (cascade) |
| `gender` | varchar(40) | YES |  |  | D1 |
| `age_years` | smallint | YES |  |  | D2 resolved to a number |
| `age_band` | varchar(20) | YES |  |  | 18-29 / 30-44 / 45-60 / Over 60 |
| `generation` | varchar(20) | YES |  |  | GenZ / Millennial / GenX / Boomer |
| `relationship` | varchar(60) | YES |  |  | D3 |
| `ethnicity` | varchar(60) | YES |  |  | D4 |
| `income_band` | varchar(40) | YES |  |  | D5 |
| `urbanicity` | varchar(20) | YES |  |  | D6 |
| `political` | varchar(120) | YES |  |  | D7 |
| `state_name` | varchar(60) | YES |  |  | D8 |
| `census_region` | varchar(20) | YES |  |  | derived from D8 |
| `outlook_income` | varchar(40) | YES |  |  | CS1 |
| `outlook_economy` | varchar(40) | YES |  |  | CS2 |
| `weight` | decimal(10,6) | NO |  | 1.000000 | reserved; these waves are unweighted |
| `age_mid` | decimal(6,2) | YES |  |  |  |
| `income_mid_k` | decimal(10,4) | YES |  |  |  |

Indexes: `ix_profile_cuts` (btree: survey_id, generation, gender, income_band); `ix_profile_region` (btree: survey_id, census_region); `PRIMARY` (btree: respondent_id)

## cip_profile_map

*Table* — Which question feeds each demographic cut, per wave. Auditable and editable.

| Column | Type | Null | Key | Default | Meaning |
|---|---|---|---|---|---|
| `survey_id` | int unsigned | NO | PRI |  | → cip_survey.survey_id (cascade) |
| `dimension` | varchar(40) | NO | PRI |  | gender, age, income_band, ... |
| `qcode` | varchar(50) | NO |  |  | the question that supplies it |
| `resolved_by` | enum('config','detected','manual') | NO |  | detected |  |
| `updated_at` | timestamp | NO |  | CURRENT_TIMESTAMP |  |

Indexes: `PRIMARY` (btree: survey_id, dimension)

## cip_publication

*Table* — A delivered chart or table, frozen at a version.

| Column | Type | Null | Key | Default | Meaning |
|---|---|---|---|---|---|
| `publication_id` | int unsigned | NO | PRI |  |  |
| `pub_code` | varchar(80) | NO | MUL |  | BEAUTY_RETAILER_PROFILE |
| `version` | smallint unsigned | NO |  | 1 |  |
| `pub_name` | varchar(255) | NO |  |  |  |
| `owner_email` | varchar(200) | YES |  |  |  |
| `definition` | json | NO |  |  | waves, concepts, cohort, break, scheme, min base |
| `footnote` | varchar(2000) | YES |  |  |  |
| `destination` | varchar(1000) | YES |  |  | where it was delivered, e.g. SharePoint URL |
| `status` | enum('draft','published','withdrawn') | NO |  | draft |  |
| `published_at` | datetime | YES |  |  |  |
| `created_at` | timestamp | NO |  | CURRENT_TIMESTAMP |  |

Indexes: `PRIMARY` (btree: publication_id); `uq_publication` (unique btree: pub_code, version)

## cip_publication_cell

*Table* — The frozen numbers of a publication.

| Column | Type | Null | Key | Default | Meaning |
|---|---|---|---|---|---|
| `cell_id` | bigint unsigned | NO | PRI |  |  |
| `publication_id` | int unsigned | NO | MUL |  | → cip_publication.publication_id (cascade) |
| `row_key` | varchar(250) | NO |  |  |  |
| `col_key` | varchar(250) | NO |  |  |  |
| `n` | int | YES |  |  |  |
| `base_n` | int | YES |  |  |  |
| `value` | decimal(18,6) | YES |  |  |  |

Indexes: `PRIMARY` (btree: cell_id); `uq_publication_cell` (unique btree: publication_id, row_key, col_key)

## cip_question

*Table* — Questions, with their own answering base.

| Column | Type | Null | Key | Default | Meaning |
|---|---|---|---|---|---|
| `question_id` | int unsigned | NO | PRI |  |  |
| `survey_id` | int unsigned | NO | MUL |  | → cip_survey.survey_id (cascade) |
| `topic_id` | smallint unsigned | YES | MUL |  | → cip_topic.topic_id (set null) |
| `qcode` | varchar(50) | NO |  |  | q1, DP7, BN3 |
| `qtext` | text | NO |  |  |  |
| `qtext_short` | varchar(255) | YES |  |  | chart title |
| `qtype` | enum('single','multi','grid_single','grid_multi','numeric','text','datetime') | NO |  |  |  |
| `value_min` | int | YES |  |  |  |
| `value_max` | int | YES |  |  |  |
| `is_technical` | tinyint(1) | NO |  | 0 |  |
| `is_multi` | tinyint(1) | NO |  | 0 | 1 = respondent may pick several |
| `base_n` | int | YES |  |  | respondents who reached this question |
| `base_desc` | varchar(255) | YES |  |  | e.g. "Bought from a department store in past 3 months" |
| `asked_if` | varchar(500) | YES |  |  | routing condition, when known |
| `sort_order` | smallint | NO |  | 0 |  |
| `is_virtual` | tinyint(1) | NO |  | 0 |  |

Indexes: `ix_question_topic` (btree: topic_id); `PRIMARY` (btree: question_id); `uq_question` (unique btree: survey_id, qcode)

## cip_respondent

*Table* — One row per interview.

| Column | Type | Null | Key | Default | Meaning |
|---|---|---|---|---|---|
| `respondent_id` | bigint unsigned | NO | PRI |  |  |
| `survey_id` | int unsigned | NO | MUL |  | → cip_survey.survey_id (cascade) |
| `record_no` | int unsigned | NO |  |  | Forsta [record] |
| `forsta_uuid` | varchar(64) | YES |  |  |  |
| `status_code` | tinyint | YES |  |  | 1 Terminated 2 Overquota 3 Qualified 4 Partial |
| `status_label` | varchar(30) | YES |  |  |  |
| `is_qualified` | tinyint(1) | NO |  | 0 | default analysis base |
| `started_at` | datetime | YES |  |  |  |
| `completed_at` | datetime | YES |  |  |  |
| `interview_secs` | int | YES |  |  |  |
| `panel_source` | varchar(100) | YES |  |  |  |
| `sample_rid` | varchar(100) | YES |  |  |  |
| `markers` | varchar(1000) | YES |  |  | quota buckets as Forsta records them |
| `device` | varchar(50) | YES |  |  |  |
| `os` | varchar(100) | YES |  |  |  |
| `browser` | varchar(100) | YES |  |  |  |
| `dropout_qcode` | varchar(50) | YES |  |  |  |
| `load_id` | bigint unsigned | YES |  |  |  |
| `loaded_at` | timestamp | NO |  | CURRENT_TIMESTAMP |  |
| `respondent_key` | char(64) | YES |  |  |  |
| `quality_flag` | varchar(40) | YES |  |  |  |

Indexes: `ix_respondent_completed` (btree: survey_id, completed_at); `ix_respondent_key` (btree: survey_id, respondent_key); `ix_respondent_qualified` (btree: survey_id, is_qualified); `PRIMARY` (btree: respondent_id); `uq_respondent` (unique btree: survey_id, record_no)

## cip_respondent_cohort

*Table* — Materialised cohort membership.

| Column | Type | Null | Key | Default | Meaning |
|---|---|---|---|---|---|
| `cohort_id` | int unsigned | NO | PRI |  | → cip_cohort_def.cohort_id (cascade) |
| `respondent_id` | bigint unsigned | NO | PRI |  | → cip_respondent.respondent_id (cascade) |
| `survey_id` | int unsigned | NO | MUL |  | → cip_survey.survey_id (cascade) |

Indexes: `fk_rcohort_survey` (btree: survey_id); `ix_rcohort_respondent` (btree: respondent_id); `ix_rcohort_survey` (btree: cohort_id, survey_id); `PRIMARY` (btree: cohort_id, respondent_id)

## cip_saved_view

*Table* — Saved filter + question sets, re-run against current data.

| Column | Type | Null | Key | Default | Meaning |
|---|---|---|---|---|---|
| `view_id` | int unsigned | NO | PRI |  |  |
| `survey_id` | int unsigned | NO | MUL |  | → cip_survey.survey_id (cascade) |
| `view_name` | varchar(160) | NO |  |  |  |
| `owner_email` | varchar(200) | NO | MUL |  |  |
| `is_shared` | tinyint(1) | NO |  | 0 | 1 = visible to the whole team |
| `definition` | text | NO |  |  | JSON: criteria, question ids, break |
| `description` | varchar(500) | YES |  |  |  |
| `created_at` | timestamp | NO |  | CURRENT_TIMESTAMP |  |
| `updated_at` | timestamp | NO |  | CURRENT_TIMESTAMP |  |

Indexes: `ix_saved_view_survey` (btree: survey_id, is_shared); `PRIMARY` (btree: view_id); `uq_saved_view` (unique btree: owner_email, view_name)

## cip_search

*Table* — Search index: one row per wave, question and concept (FULLTEXT).

| Column | Type | Null | Key | Default | Meaning |
|---|---|---|---|---|---|
| `search_id` | int unsigned | NO | PRI |  |  |
| `kind` | enum('survey','question','concept') | NO | MUL |  |  |
| `survey_id` | int unsigned | YES |  |  |  |
| `question_id` | int unsigned | YES |  |  |  |
| `concept_id` | int unsigned | YES |  |  |  |
| `wave_label` | varchar(50) | YES |  |  |  |
| `waves` | int | YES |  |  | concept: waves it appears in |
| `title` | varchar(500) | NO | MUL |  |  |
| `body` | text | YES |  |  |  |

Indexes: `ft_search` (fulltext: title, body); `ix_search_kind` (btree: kind, wave_label); `PRIMARY` (btree: search_id)

## cip_segment

*Table* — Cross-tab columns with their Forsta definitions.

| Column | Type | Null | Key | Default | Meaning |
|---|---|---|---|---|---|
| `segment_id` | int unsigned | NO | PRI |  |  |
| `banner_id` | int unsigned | NO | MUL |  | → cip_banner.banner_id (cascade) |
| `survey_id` | int unsigned | NO | MUL |  | → cip_survey.survey_id (cascade) |
| `seg_letter` | varchar(4) | YES |  |  | stat-test letter A..N1 |
| `seg_label` | varchar(255) | NO |  |  | Male, GenZ, $50,000 - $99,999 |
| `seg_definition` | varchar(2000) | YES |  |  | Forsta expression, kept verbatim so a wave is auditable |
| `seg_base_n` | int | YES |  |  | segment size — NOT the denominator of a routed question |
| `is_total` | tinyint(1) | NO |  | 0 |  |
| `low_base` | enum('','*','**') | NO |  |  | * caution, ** too small to report |
| `sort_order` | smallint | NO |  | 0 |  |

Indexes: `ix_segment_survey` (btree: survey_id); `PRIMARY` (btree: segment_id); `uq_segment` (unique btree: banner_id, seg_label)

## cip_survey

*Table* — Survey waves.

| Column | Type | Null | Key | Default | Meaning |
|---|---|---|---|---|---|
| `survey_id` | int unsigned | NO | PRI |  |  |
| `forsta_host` | varchar(100) | NO | MUL |  | se1.decipherinc.com |
| `forsta_path` | varchar(255) | NO |  |  | selfserve/58f/260908 |
| `title` | varchar(500) | NO |  |  |  |
| `survey_family` | varchar(100) | YES | MUL |  | CSI-US — groups waves for trending |
| `wave_label` | varchar(50) | NO |  |  | fielding week, 2026-09-28 |
| `wave_date` | date | YES |  |  |  |
| `field_start` | datetime | YES |  |  |  |
| `field_end` | datetime | YES |  |  |  |
| `country` | char(2) | YES |  | US |  |
| `status` | enum('draft','fielding','closed','archived') | NO |  | closed |  |
| `datamap_hash` | char(64) | YES |  |  | sha256 of the datamap; detects questionnaire change |
| `created_at` | timestamp | NO |  | CURRENT_TIMESTAMP |  |
| `updated_at` | timestamp | NO |  | CURRENT_TIMESTAMP |  |
| `platform` | enum('forsta','qualtrics','surveymonkey') | NO | MUL | forsta |  |
| `source_ref` | varchar(255) | NO |  |  |  |
| `study_type` | enum('tracker','annual','adhoc') | NO |  | tracker |  |
| `load_status` | enum('loading','verified','failed','superseded') | NO | MUL | verified |  |
| `language` | varchar(10) | NO |  | en |  |
| `sample_source` | varchar(50) | YES |  |  |  |
| `total_n` | int | YES |  |  |  |
| `tags` | varchar(500) | YES |  |  |  |

Indexes: `ix_survey_family` (btree: survey_family, wave_date); `ix_survey_pick` (btree: load_status, study_type, wave_date); `PRIMARY` (btree: survey_id); `uq_survey` (unique btree: forsta_host, forsta_path, wave_label); `uq_survey_source` (unique btree: platform, source_ref, wave_label)

## cip_topic

*Table* — Editorial grouping of questions.

| Column | Type | Null | Key | Default | Meaning |
|---|---|---|---|---|---|
| `topic_id` | smallint unsigned | NO | PRI |  |  |
| `topic_code` | varchar(40) | NO | UNI |  | DEPT_STORES |
| `topic_name` | varchar(150) | NO |  |  | Department Stores |
| `is_technical` | tinyint(1) | NO |  | 0 | 1 = paradata/quota, hidden by default |
| `sort_order` | smallint | NO |  | 0 |  |

Indexes: `PRIMARY` (btree: topic_id); `uq_topic` (unique btree: topic_code)

## cip_tracker_line

*Table* — The data team's line-by-line rows: one per qualified tracker respondent, JSON in their column order.

| Column | Type | Null | Key | Default | Meaning |
|---|---|---|---|---|---|
| `respondent_id` | bigint unsigned | NO | PRI |  |  |
| `survey_id` | int unsigned | NO |  |  |  |
| `wave_date` | date | NO | MUL |  |  |
| `line` | json | NO |  |  | header -> value, config/tracker_line.yml order |

Indexes: `ix_line_wave` (btree: wave_date, survey_id); `PRIMARY` (btree: respondent_id)

## cip_wave_module

*Table* — Survey calendar: every Forsta survey x module (lead sector, topic, seasonal, event, annual, ad hoc).

| Column | Type | Null | Key | Default | Meaning |
|---|---|---|---|---|---|
| `forsta_path` | varchar(255) | NO | PRI |  |  |
| `module_code` | varchar(40) | NO | PRI |  |  |
| `module_name` | varchar(120) | NO |  |  |  |
| `kind` | enum('sector','topic','seasonal','event','annual','adhoc') | NO |  |  |  |
| `is_lead` | tinyint(1) | NO |  | 0 | the tracker week's lead sector |
| `launched_on` | date | YES | MUL |  |  |
| `season` | smallint | YES |  |  | seasonal / annual: Jul-Jun season year |
| `series_wave_no` | smallint | YES |  |  | nth wave of this module (in its season) |
| `survey_id` | int unsigned | YES |  |  | set once loaded |
| `detected_by` | enum('title','questions') | NO |  | title |  |

Indexes: `ix_module_day` (btree: launched_on); `ix_module_series` (btree: module_code, season, series_wave_no); `PRIMARY` (btree: forsta_path, module_code)

## cip_weight

*Table* — One weight per respondent per scheme.

| Column | Type | Null | Key | Default | Meaning |
|---|---|---|---|---|---|
| `respondent_id` | bigint unsigned | NO | PRI |  | → cip_respondent.respondent_id (cascade) |
| `scheme_id` | int unsigned | NO | PRI |  | → cip_weight_scheme.scheme_id (cascade) |
| `weight` | decimal(12,6) | NO |  |  |  |

Indexes: `ix_weight_scheme` (btree: scheme_id); `PRIMARY` (btree: respondent_id, scheme_id)

## cip_weight_scheme

*Table* — Named weighting schemes, per wave.

| Column | Type | Null | Key | Default | Meaning |
|---|---|---|---|---|---|
| `scheme_id` | int unsigned | NO | PRI |  |  |
| `survey_id` | int unsigned | NO | MUL |  | → cip_survey.survey_id (cascade) |
| `scheme_code` | varchar(60) | NO |  |  | CENSUS_AGE_GENDER_REGION |
| `method` | varchar(100) | YES |  |  | raking, cell, … |
| `targets` | json | YES |  |  |  |
| `description` | varchar(500) | YES |  |  |  |
| `created_at` | timestamp | NO |  | CURRENT_TIMESTAMP |  |

Indexes: `PRIMARY` (btree: scheme_id); `uq_weight_scheme` (unique btree: survey_id, scheme_code)

## v_cip_answers

*View* — VIEW

| Column | Type | Null | Key | Default | Meaning |
|---|---|---|---|---|---|
| `survey_id` | int unsigned | NO |  |  |  |
| `survey_family` | varchar(100) | YES |  |  | CSI-US — groups waves for trending |
| `wave_label` | varchar(50) | NO |  |  | fielding week, 2026-09-28 |
| `wave_date` | date | YES |  |  |  |
| `respondent_id` | bigint unsigned | NO |  | 0 |  |
| `is_qualified` | tinyint(1) | NO |  | 0 | default analysis base |
| `gender` | varchar(40) | YES |  |  | D1 |
| `age_band` | varchar(20) | YES |  |  | 18-29 / 30-44 / 45-60 / Over 60 |
| `generation` | varchar(20) | YES |  |  | GenZ / Millennial / GenX / Boomer |
| `ethnicity` | varchar(60) | YES |  |  | D4 |
| `income_band` | varchar(40) | YES |  |  | D5 |
| `urbanicity` | varchar(20) | YES |  |  | D6 |
| `census_region` | varchar(20) | YES |  |  | derived from D8 |
| `political` | varchar(120) | YES |  |  | D7 |
| `topic_name` | varchar(150) | YES |  |  | Department Stores |
| `qcode` | varchar(50) | YES |  |  | q1, DP7, BN3 |
| `qtext` | text | YES |  |  |  |
| `qtext_short` | varchar(255) | YES |  |  | chart title |
| `qtype` | enum('single','multi','grid_single','grid_multi','numeric','text','datetime') | YES |  |  |  |
| `question_base_n` | int | YES |  |  | respondents who reached this question |
| `item_code` | varchar(50) | YES |  |  | q1r1, DP7r3 |
| `item_label` | varchar(1000) | YES |  |  |  |
| `field_name` | varchar(100) | NO |  |  | exact export header: q1r1, D2, uuid |
| `value_code` | int | YES |  |  | 0/1, 1-5, 1-54 |
| `value_label` | varchar(500) | YES |  |  | resolved label, denormalised for display |
| `value_number` | decimal(18,4) | YES |  |  | open numeric |
| `weight` | decimal(10,6) | YES |  | 1.000000 | reserved; these waves are unweighted |

## v_cip_crosstab

*View* — VIEW

| Column | Type | Null | Key | Default | Meaning |
|---|---|---|---|---|---|
| `survey_id` | int unsigned | NO |  |  |  |
| `wave_label` | varchar(50) | NO |  |  | fielding week, 2026-09-28 |
| `qcode` | varchar(50) | NO |  |  | q1, DP7, BN3 |
| `qtext` | text | NO |  |  |  |
| `item_label` | varchar(500) | YES |  |  | grid sub-item, e.g. the retailer being rated in DP7 |
| `stub_label` | varchar(1000) | NO |  |  | row label as printed |
| `stub_type` | enum('item','net','mean','count','base') | NO |  | item |  |
| `banner_name` | varchar(500) | NO |  |  | header text as printed |
| `seg_letter` | varchar(4) | YES |  |  | stat-test letter A..N1 |
| `seg_label` | varchar(255) | NO |  |  | Male, GenZ, $50,000 - $99,999 |
| `segment_size_n` | int | YES |  |  | segment size — NOT the denominator of a routed question |
| `denominator_n` | int | YES |  |  | the true denominator: count_n / pct |
| `low_base` | enum('','*','**') | NO |  |  | * caution, ** too small to report |
| `pct` | decimal(9,6) | YES |  |  | 0.527228 = 52.7% |
| `count_n` | int | YES |  |  |  |
| `sig_letters` | varchar(40) | YES |  |  | segments this cell significantly beats |
| `pct_base` | varchar(100) | YES |  |  | "Total Answering" — see csi_crosstab.answer_base_n |
| `respondent_base` | varchar(100) | YES |  |  | "Qualified Only" |

## v_cip_grid

*View* — VIEW

| Column | Type | Null | Key | Default | Meaning |
|---|---|---|---|---|---|
| `survey_id` | int unsigned | NO |  |  |  |
| `qcode` | varchar(50) | NO |  |  | q1, DP7, BN3 |
| `qtext_short` | varchar(255) | YES |  |  | chart title |
| `item_label` | varchar(1000) | NO |  |  |  |
| `value_code` | int | YES |  |  | 0/1, 1-5, 1-54 |
| `scale_label` | varchar(500) | YES |  |  |  |
| `scale_order` | smallint | YES |  | 0 |  |
| `n` | bigint | NO |  | 0 |  |
| `pct` | decimal(26,5) | YES |  |  |  |

## v_cip_item_incidence

*View* — VIEW

| Column | Type | Null | Key | Default | Meaning |
|---|---|---|---|---|---|
| `survey_id` | int unsigned | NO |  |  | denormalised for filter speed |
| `question_id` | int unsigned | NO |  | 0 |  |
| `qcode` | varchar(50) | NO |  |  | q1, DP7, BN3 |
| `qtext_short` | varchar(255) | YES |  |  | chart title |
| `item_id` | int unsigned | NO |  | 0 |  |
| `item_label` | varchar(1000) | NO |  |  |  |
| `is_exclusive` | tinyint(1) | NO |  | 0 | 1 = "None of these" — drop from rankings |
| `base_n` | bigint | YES |  |  |  |
| `selected_n` | decimal(23,0) | YES |  |  |  |
| `pct` | decimal(29,5) | YES |  |  |  |

## v_cip_mapping_queue

*View* — VIEW

| Column | Type | Null | Key | Default | Meaning |
|---|---|---|---|---|---|
| `survey_id` | int unsigned | NO |  |  |  |
| `wave_label` | varchar(50) | NO |  |  | fielding week, 2026-09-28 |
| `survey_title` | varchar(500) | NO |  |  |  |
| `question_id` | int unsigned | NO |  |  |  |
| `item_id` | int unsigned | YES |  |  |  |
| `qcode` | varchar(50) | NO |  |  | q1, DP7, BN3 |
| `qtext` | text | NO |  |  |  |
| `qtype` | enum('single','multi','grid_single','grid_multi','numeric','text','datetime') | NO |  |  |  |
| `item_label` | varchar(1000) | YES |  |  |  |
| `concept_id` | int unsigned | NO |  |  |  |
| `concept_code` | varchar(80) | NO |  |  | BEAUTY_RETAILER_3M |
| `concept_name` | varchar(255) | NO |  |  |  |
| `method` | enum('exact_text','similar_text','manual') | NO |  |  |  |
| `confidence` | decimal(5,4) | YES |  |  |  |
| `evidence` | varchar(1000) | YES |  |  | why the harmoniser proposed it |
| `created_at` | timestamp | NO |  | CURRENT_TIMESTAMP |  |

## v_cip_question_base

*View* — VIEW

| Column | Type | Null | Key | Default | Meaning |
|---|---|---|---|---|---|
| `survey_id` | int unsigned | NO |  |  |  |
| `topic_name` | varchar(150) | YES |  |  | Department Stores |
| `qcode` | varchar(50) | NO |  |  | q1, DP7, BN3 |
| `qtext_short` | varchar(255) | YES |  |  | chart title |
| `qtype` | enum('single','multi','grid_single','grid_multi','numeric','text','datetime') | NO |  |  |  |
| `is_multi` | tinyint(1) | NO |  | 0 | 1 = respondent may pick several |
| `base_n` | int | YES |  |  | respondents who reached this question |
| `base_desc` | varchar(255) | YES |  |  | e.g. "Bought from a department store in past 3 months" |
| `pct_of_wave` | decimal(15,1) | YES |  |  |  |

## v_cip_single_distribution

*View* — VIEW

| Column | Type | Null | Key | Default | Meaning |
|---|---|---|---|---|---|
| `survey_id` | int unsigned | NO |  |  |  |
| `question_id` | int unsigned | NO |  | 0 |  |
| `qcode` | varchar(50) | NO |  |  | q1, DP7, BN3 |
| `qtext_short` | varchar(255) | YES |  |  | chart title |
| `value_code` | int | YES |  |  | 0/1, 1-5, 1-54 |
| `answer_label` | varchar(500) | YES |  |  |  |
| `is_nonresponse` | tinyint(1) | YES |  | 0 | Don't know / Prefer not to say — excluded from Top-2-Box |
| `net_group` | varchar(50) | YES |  |  | TOP2 / BOT2 for net calculations |
| `n` | bigint | NO |  | 0 |  |
| `pct` | decimal(26,5) | YES |  |  |  |
| `base_n` | decimal(42,0) | YES |  |  |  |

## v_cip_survey_health

*View* — VIEW

| Column | Type | Null | Key | Default | Meaning |
|---|---|---|---|---|---|
| `survey_id` | int unsigned | NO |  | 0 |  |
| `title` | varchar(500) | NO |  |  |  |
| `wave_label` | varchar(50) | NO |  |  | fielding week, 2026-09-28 |
| `total_records` | bigint | NO |  | 0 |  |
| `qualified_n` | decimal(25,0) | YES |  |  |  |
| `terminated_n` | decimal(23,0) | YES |  |  |  |
| `overquota_n` | decimal(23,0) | YES |  |  |  |
| `partial_n` | decimal(23,0) | YES |  |  |  |
| `avg_loi_minutes` | decimal(12,1) | YES |  |  |  |
| `first_complete` | datetime | YES |  |  |  |
| `last_complete` | datetime | YES |  |  |  |

## v_cip_trend

*View* — VIEW

| Column | Type | Null | Key | Default | Meaning |
|---|---|---|---|---|---|
| `survey_family` | varchar(100) | YES |  |  | CSI-US — groups waves for trending |
| `wave_label` | varchar(50) | NO |  |  | fielding week, 2026-09-28 |
| `wave_date` | date | YES |  |  |  |
| `qcode` | varchar(50) | NO |  |  | q1, DP7, BN3 |
| `item_label` | varchar(1000) | NO |  |  |  |
| `pct` | decimal(29,5) | YES |  |  |  |
| `base_n` | bigint | YES |  |  |  |
