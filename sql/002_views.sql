-- ═══════════════════════════════════════════════════════════════════════════
-- CSI reporting views. The portal reads these, never the base tables.
-- Every view that produces a percentage carries the base it was computed on.
-- Every view shows verified waves only (load_status = 'verified'): a wave still
-- loading, or failed, never appears half-written.
-- ═══════════════════════════════════════════════════════════════════════════

-- Denormalised answer stream with demographics attached.
CREATE OR REPLACE VIEW v_cip_answers AS
SELECT
    r.survey_id, s.survey_family, s.wave_label, s.wave_date,
    r.respondent_id, r.is_qualified,
    p.gender, p.age_band, p.generation, p.ethnicity, p.income_band,
    p.urbanicity, p.census_region, p.political,
    t.topic_name,
    q.qcode, q.qtext, q.qtext_short, q.qtype, q.base_n AS question_base_n,
    i.item_code, i.item_label,
    f.field_name,
    a.value_code, COALESCE(a.value_label, o.value_label, i.item_label) AS value_label, a.value_number,
    p.weight
FROM cip_answer     a
JOIN cip_respondent r ON r.respondent_id = a.respondent_id
JOIN cip_survey     s ON s.survey_id     = r.survey_id AND s.load_status = 'verified'
LEFT JOIN cip_profile p ON p.respondent_id = r.respondent_id
JOIN cip_field      f ON f.field_id      = a.field_id
LEFT JOIN cip_question q ON q.question_id = f.question_id
LEFT JOIN cip_topic    t ON t.topic_id    = q.topic_id
LEFT JOIN cip_item     i ON i.item_id     = f.item_id
LEFT JOIN cip_option   o ON o.question_id = f.question_id AND o.value_code = a.value_code
WHERE COALESCE(q.is_technical, 0) = 0;

-- "% who selected each item", computed on the question's OWN answering base.
-- The base is every respondent with any non-null cell across the question's
-- fields — i.e. everyone routed into it — not everyone in the wave.
CREATE OR REPLACE VIEW v_cip_item_incidence AS
WITH reached AS (
    SELECT a.survey_id, f.question_id, a.respondent_id
      FROM cip_answer a
      JOIN cip_field  f ON f.field_id = a.field_id
      JOIN cip_respondent r ON r.respondent_id = a.respondent_id AND r.is_qualified = 1
      JOIN cip_survey s ON s.survey_id = a.survey_id AND s.load_status = 'verified'
     WHERE f.question_id IS NOT NULL
     GROUP BY a.survey_id, f.question_id, a.respondent_id
)
SELECT
    a.survey_id,
    q.question_id, q.qcode, q.qtext_short,
    i.item_id, i.item_label, i.is_exclusive,
    (SELECT COUNT(*) FROM reached x
      WHERE x.survey_id = a.survey_id AND x.question_id = q.question_id) AS base_n,
    SUM(CASE WHEN a.value_code = 1 THEN 1 ELSE 0 END) AS selected_n,
    SUM(CASE WHEN a.value_code = 1 THEN 1 ELSE 0 END) * 1.0
        / NULLIF((SELECT COUNT(*) FROM reached x
                   WHERE x.survey_id = a.survey_id AND x.question_id = q.question_id), 0) AS pct
FROM cip_answer     a
JOIN cip_respondent r ON r.respondent_id = a.respondent_id AND r.is_qualified = 1
JOIN cip_survey     s ON s.survey_id = a.survey_id AND s.load_status = 'verified'
JOIN cip_field      f ON f.field_id = a.field_id
JOIN cip_question   q ON q.question_id = f.question_id AND q.is_multi = 1
JOIN cip_item       i ON i.item_id = f.item_id
GROUP BY a.survey_id, q.question_id, q.qcode, q.qtext_short,
         i.item_id, i.item_label, i.is_exclusive;

-- Single-punch distributions. Denominator is everyone who answered THIS question.
CREATE OR REPLACE VIEW v_cip_single_distribution AS
SELECT
    r.survey_id, q.question_id, q.qcode, q.qtext_short,
    a.value_code,
    COALESCE(o.value_label, a.value_label) AS answer_label,
    o.is_nonresponse, o.net_group,
    COUNT(*) AS n,
    COUNT(*) * 1.0
        / NULLIF(SUM(COUNT(*)) OVER (PARTITION BY r.survey_id, q.question_id), 0) AS pct,
    SUM(COUNT(*)) OVER (PARTITION BY r.survey_id, q.question_id) AS base_n
FROM cip_answer     a
JOIN cip_respondent r ON r.respondent_id = a.respondent_id AND r.is_qualified = 1
JOIN cip_survey     s ON s.survey_id = r.survey_id AND s.load_status = 'verified'
JOIN cip_field      f ON f.field_id = a.field_id
JOIN cip_question   q ON q.question_id = f.question_id
                      AND q.qtype = 'single' AND q.is_technical = 0
LEFT JOIN cip_option o ON o.question_id = q.question_id AND o.value_code = a.value_code
WHERE a.value_code IS NOT NULL
GROUP BY r.survey_id, q.question_id, q.qcode, q.qtext_short,
         a.value_code, COALESCE(o.value_label, a.value_label),
         o.is_nonresponse, o.net_group;

-- Grid questions: item x scale point (DP7 retailers x sentiment, GP6 categories).
CREATE OR REPLACE VIEW v_cip_grid AS
SELECT
    r.survey_id, q.qcode, q.qtext_short,
    i.item_label,
    a.value_code,
    COALESCE(o.value_label, a.value_label) AS scale_label,
    o.sort_order AS scale_order,
    COUNT(*) AS n,
    COUNT(*) * 1.0
        / NULLIF(SUM(COUNT(*)) OVER (PARTITION BY r.survey_id, q.qcode, i.item_id), 0) AS pct
FROM cip_answer     a
JOIN cip_respondent r ON r.respondent_id = a.respondent_id AND r.is_qualified = 1
JOIN cip_survey     s ON s.survey_id = r.survey_id AND s.load_status = 'verified'
JOIN cip_field      f ON f.field_id = a.field_id
JOIN cip_question   q ON q.question_id = f.question_id AND q.qtype IN ('grid_single','grid_multi')
JOIN cip_item       i ON i.item_id = f.item_id
LEFT JOIN cip_option o ON o.question_id = q.question_id AND o.value_code = a.value_code
WHERE a.value_code IS NOT NULL
GROUP BY r.survey_id, q.qcode, q.qtext_short, i.item_id, i.item_label,
         a.value_code, COALESCE(o.value_label, a.value_label), o.sort_order;

-- The cross-tab grid as an analyst reads it, carrying BOTH bases.
CREATE OR REPLACE VIEW v_cip_crosstab AS
SELECT
    c.survey_id, s.wave_label,
    q.qcode, q.qtext,
    c.item_label, c.stub_label, c.stub_type,
    b.banner_name,
    g.seg_letter, g.seg_label,
    g.seg_base_n            AS segment_size_n,
    c.answer_base_n         AS denominator_n,
    g.low_base,
    c.pct, c.count_n, c.sig_letters,
    run.pct_base, run.respondent_base
FROM cip_crosstab      c
JOIN cip_crosstab_run  run ON run.run_id = c.run_id AND run.is_current = 1
JOIN cip_survey        s   ON s.survey_id = c.survey_id AND s.load_status = 'verified'
JOIN cip_question      q   ON q.question_id = c.question_id
JOIN cip_segment       g   ON g.segment_id = c.segment_id
JOIN cip_banner        b   ON b.banner_id = g.banner_id;

-- Wave-over-wave trend within a survey family.
CREATE OR REPLACE VIEW v_cip_trend AS
SELECT
    s.survey_family, s.wave_label, s.wave_date,
    i.qcode, i.item_label, i.pct, i.base_n
FROM v_cip_item_incidence i
JOIN cip_survey s ON s.survey_id = i.survey_id AND s.load_status = 'verified';

-- Field health for the data team.
CREATE OR REPLACE VIEW v_cip_survey_health AS
SELECT
    s.survey_id, s.title, s.wave_label,
    COUNT(r.respondent_id)                             AS total_records,
    SUM(r.is_qualified)                                AS qualified_n,
    SUM(CASE WHEN r.status_code = 1 THEN 1 ELSE 0 END) AS terminated_n,
    SUM(CASE WHEN r.status_code = 2 THEN 1 ELSE 0 END) AS overquota_n,
    SUM(CASE WHEN r.status_code = 4 THEN 1 ELSE 0 END) AS partial_n,
    ROUND(AVG(NULLIF(r.interview_secs, 0)) / 60, 1)    AS avg_loi_minutes,
    MIN(r.completed_at)                                AS first_complete,
    MAX(r.completed_at)                                AS last_complete
FROM cip_survey s
LEFT JOIN cip_respondent r ON r.survey_id = s.survey_id
WHERE s.load_status = 'verified'
GROUP BY s.survey_id, s.title, s.wave_label;

-- Every question with its base, so a chart can never lose it.
CREATE OR REPLACE VIEW v_cip_question_base AS
SELECT
    q.survey_id, t.topic_name, q.qcode, q.qtext_short, q.qtype,
    q.is_multi, q.base_n, q.base_desc,
    ROUND(100.0 * q.base_n / NULLIF(h.qualified_n, 0), 1) AS pct_of_wave
FROM cip_question q
JOIN cip_survey s ON s.survey_id = q.survey_id AND s.load_status = 'verified'
LEFT JOIN cip_topic t ON t.topic_id = q.topic_id
LEFT JOIN v_cip_survey_health h ON h.survey_id = q.survey_id
WHERE q.is_technical = 0;


-- Units the harmoniser could not settle alone, with its evidence.
-- Unit rows are the ones without a concept option; answers are mapped only
-- after confirmation, so every row here is one decision.
CREATE OR REPLACE VIEW v_cip_mapping_queue AS
SELECT m.survey_id, s.wave_label, s.title AS survey_title,
       m.question_id, m.item_id, q.qcode, q.qtext, q.qtype, i.item_label,
       m.concept_id, c.concept_code, c.concept_name,
       m.method, m.confidence, m.evidence, m.created_at
  FROM cip_concept_map m
  JOIN cip_survey   s ON s.survey_id   = m.survey_id AND s.load_status = 'verified'
  JOIN cip_question q ON q.question_id = m.question_id
  LEFT JOIN cip_item i ON i.item_id    = m.item_id
  JOIN cip_concept  c ON c.concept_id  = m.concept_id
 WHERE m.status = 'proposed' AND m.concept_option_id IS NULL;


-- ═══════════════════════════════════════════════════════════════════════════
-- ANALYST VIEWS (19 Oct 2026) — the starting point for any analysis outside
-- the portal. Verified waves and qualified respondents only, every platform
-- (Forsta, Qualtrics, SurveyMonkey) in one shape, plain column names.
--   v_cip_wave        one row per wave: what it was, when, how many
--   v_cip_respondent  one row per qualified respondent: wave + demographics
--   v_cip_answer_long one row per answer, with the harmonised concept so the
--                     same question can be followed across waves
-- Always filter v_cip_answer_long by survey_id, wave_date or concept_code.
-- ═══════════════════════════════════════════════════════════════════════════
CREATE OR REPLACE VIEW v_cip_wave AS
SELECT s.survey_id, s.platform, s.study_type, s.survey_family, s.title,
       s.wave_date, s.field_start, s.field_end, s.source_ref,
       (SELECT m.module_name FROM cip_wave_module m
         WHERE m.survey_id = s.survey_id AND m.is_lead = 1 LIMIT 1)          AS lead_module,
       (SELECT COUNT(*) FROM cip_respondent r
         WHERE r.survey_id = s.survey_id AND r.is_qualified = 1)              AS qualified_n,
       (SELECT COUNT(*) FROM cip_question q
         WHERE q.survey_id = s.survey_id AND q.is_technical = 0 AND q.is_virtual = 0) AS questions_n
  FROM cip_survey s
 WHERE s.load_status = 'verified';

CREATE OR REPLACE VIEW v_cip_respondent AS
SELECT r.respondent_id, r.survey_id, s.platform, s.study_type, s.survey_family, s.wave_date,
       r.respondent_key, r.completed_at, r.interview_secs, r.device,
       p.gender, p.age_years, p.age_band, p.generation, p.relationship, p.ethnicity,
       p.income_band, p.urbanicity, p.political, p.state_name, p.census_region,
       p.outlook_income, p.outlook_economy, p.weight
  FROM cip_respondent r
  JOIN cip_survey s ON s.survey_id = r.survey_id AND s.load_status = 'verified'
  LEFT JOIN cip_profile p ON p.respondent_id = r.respondent_id
 WHERE r.is_qualified = 1;

CREATE OR REPLACE VIEW v_cip_answer_long AS
SELECT a.survey_id, s.platform, s.study_type, s.survey_family, s.wave_date,
       a.respondent_id, p.gender, p.age_band, p.generation, p.income_band, p.census_region, p.urbanicity,
       q.qcode, q.qtext AS question, q.qtype AS question_type, t.topic_name AS topic,
       c.concept_code, c.concept_name, m.status AS mapping_status,
       i.item_label AS row_label,
       a.value_code AS answer_code, COALESCE(a.value_label, o.value_label, i.item_label) AS answer_label,
       a.value_number AS answer_number, a.value_text AS answer_text
  FROM cip_answer a
  JOIN cip_survey     s ON s.survey_id = a.survey_id AND s.load_status = 'verified'
  JOIN cip_respondent r ON r.respondent_id = a.respondent_id AND r.is_qualified = 1
  JOIN cip_field      f ON f.field_id = a.field_id
  JOIN cip_question   q ON q.question_id = f.question_id AND q.is_technical = 0 AND q.is_virtual = 0
  LEFT JOIN cip_item  i ON i.item_id = f.item_id
  LEFT JOIN cip_option o ON o.question_id = f.question_id AND o.value_code = a.value_code
  LEFT JOIN cip_topic t ON t.topic_id = q.topic_id
  LEFT JOIN cip_profile p ON p.respondent_id = a.respondent_id
  LEFT JOIN cip_concept_map m ON m.survey_id = a.survey_id AND m.status <> 'rejected'   -- the unit's row, by its unique key
       AND m.map_key = CONCAT(q.question_id, ':', CASE WHEN q.is_multi = 1 THEN 0 ELSE COALESCE(f.item_id, 0) END, ':', 0)
  LEFT JOIN cip_concept c ON c.concept_id = m.concept_id;
