-- ═══════════════════════════════════════════════════════════════════════════
-- CSI reporting views. The portal reads these, never the base tables.
-- Every view that produces a percentage carries the base it was computed on.
-- ═══════════════════════════════════════════════════════════════════════════

-- Denormalised answer stream with demographics attached.
CREATE OR REPLACE VIEW v_csi_answers AS
SELECT
    r.survey_id, s.survey_family, s.wave_label, s.wave_date,
    r.respondent_id, r.is_qualified,
    p.gender, p.age_band, p.generation, p.ethnicity, p.income_band,
    p.urbanicity, p.census_region, p.political,
    t.topic_name,
    q.qcode, q.qtext, q.qtext_short, q.qtype, q.base_n AS question_base_n,
    i.item_code, i.item_label,
    f.field_name,
    a.value_code, a.value_label, a.value_number,
    p.weight
FROM csi_answer     a
JOIN csi_respondent r ON r.respondent_id = a.respondent_id
JOIN csi_survey     s ON s.survey_id     = r.survey_id
LEFT JOIN csi_profile p ON p.respondent_id = r.respondent_id
JOIN csi_field      f ON f.field_id      = a.field_id
LEFT JOIN csi_question q ON q.question_id = f.question_id
LEFT JOIN csi_topic    t ON t.topic_id    = q.topic_id
LEFT JOIN csi_item     i ON i.item_id     = f.item_id
WHERE COALESCE(q.is_technical, 0) = 0;

-- "% who selected each item", computed on the question's OWN answering base.
-- The base is every respondent with any non-null cell across the question's
-- fields — i.e. everyone routed into it — not everyone in the wave.
CREATE OR REPLACE VIEW v_csi_item_incidence AS
WITH reached AS (
    SELECT a.survey_id, f.question_id, a.respondent_id
      FROM csi_answer a
      JOIN csi_field  f ON f.field_id = a.field_id
      JOIN csi_respondent r ON r.respondent_id = a.respondent_id AND r.is_qualified = 1
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
    SUM(CASE WHEN a.value_code = 1 THEN 1 ELSE 0 END)
        / NULLIF((SELECT COUNT(*) FROM reached x
                   WHERE x.survey_id = a.survey_id AND x.question_id = q.question_id), 0) AS pct
FROM csi_answer     a
JOIN csi_respondent r ON r.respondent_id = a.respondent_id AND r.is_qualified = 1
JOIN csi_field      f ON f.field_id = a.field_id
JOIN csi_question   q ON q.question_id = f.question_id AND q.is_multi = 1
JOIN csi_item       i ON i.item_id = f.item_id
GROUP BY a.survey_id, q.question_id, q.qcode, q.qtext_short,
         i.item_id, i.item_label, i.is_exclusive;

-- Single-punch distributions. Denominator is everyone who answered THIS question.
CREATE OR REPLACE VIEW v_csi_single_distribution AS
SELECT
    r.survey_id, q.question_id, q.qcode, q.qtext_short,
    a.value_code,
    COALESCE(o.value_label, a.value_label) AS value_label,
    o.is_nonresponse, o.net_group,
    COUNT(*) AS n,
    COUNT(*) / NULLIF(SUM(COUNT(*)) OVER (PARTITION BY r.survey_id, q.question_id), 0) AS pct,
    SUM(COUNT(*)) OVER (PARTITION BY r.survey_id, q.question_id) AS base_n
FROM csi_answer     a
JOIN csi_respondent r ON r.respondent_id = a.respondent_id AND r.is_qualified = 1
JOIN csi_field      f ON f.field_id = a.field_id
JOIN csi_question   q ON q.question_id = f.question_id
                      AND q.qtype = 'single' AND q.is_technical = 0
LEFT JOIN csi_option o ON o.question_id = q.question_id AND o.value_code = a.value_code
WHERE a.value_code IS NOT NULL
GROUP BY r.survey_id, q.question_id, q.qcode, q.qtext_short,
         a.value_code, value_label, o.is_nonresponse, o.net_group;

-- Grid questions: item x scale point (DP7 retailers x sentiment, GP6 categories).
CREATE OR REPLACE VIEW v_csi_grid AS
SELECT
    r.survey_id, q.qcode, q.qtext_short,
    i.item_label,
    a.value_code,
    COALESCE(o.value_label, a.value_label) AS scale_label,
    o.sort_order AS scale_order,
    COUNT(*) AS n,
    COUNT(*) / NULLIF(SUM(COUNT(*)) OVER (PARTITION BY r.survey_id, q.qcode, i.item_id), 0) AS pct
FROM csi_answer     a
JOIN csi_respondent r ON r.respondent_id = a.respondent_id AND r.is_qualified = 1
JOIN csi_field      f ON f.field_id = a.field_id
JOIN csi_question   q ON q.question_id = f.question_id AND q.qtype IN ('grid_single','grid_multi')
JOIN csi_item       i ON i.item_id = f.item_id
LEFT JOIN csi_option o ON o.question_id = q.question_id AND o.value_code = a.value_code
WHERE a.value_code IS NOT NULL
GROUP BY r.survey_id, q.qcode, q.qtext_short, i.item_id, i.item_label,
         a.value_code, scale_label, o.sort_order;

-- The cross-tab grid as an analyst reads it, carrying BOTH bases.
CREATE OR REPLACE VIEW v_csi_crosstab AS
SELECT
    c.survey_id, s.wave_label,
    q.qcode, q.qtext,
    c.stub_label, c.stub_type,
    b.banner_name,
    g.seg_letter, g.seg_label,
    g.seg_base_n            AS segment_size_n,
    c.answer_base_n         AS denominator_n,
    g.low_base,
    c.pct, c.count_n, c.sig_letters,
    run.pct_base, run.respondent_base
FROM csi_crosstab      c
JOIN csi_crosstab_run  run ON run.run_id = c.run_id AND run.is_current = 1
JOIN csi_survey        s   ON s.survey_id = c.survey_id
JOIN csi_question      q   ON q.question_id = c.question_id
JOIN csi_segment       g   ON g.segment_id = c.segment_id
JOIN csi_banner        b   ON b.banner_id = g.banner_id;

-- Wave-over-wave trend within a survey family.
CREATE OR REPLACE VIEW v_csi_trend AS
SELECT
    s.survey_family, s.wave_label, s.wave_date,
    i.qcode, i.item_label, i.pct, i.base_n
FROM v_csi_item_incidence i
JOIN csi_survey s ON s.survey_id = i.survey_id;

-- Field health for the data team.
CREATE OR REPLACE VIEW v_csi_survey_health AS
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
FROM csi_survey s
LEFT JOIN csi_respondent r ON r.survey_id = s.survey_id
GROUP BY s.survey_id, s.title, s.wave_label;

-- Every question with its base, so a chart can never lose it.
CREATE OR REPLACE VIEW v_csi_question_base AS
SELECT
    q.survey_id, t.topic_name, q.qcode, q.qtext_short, q.qtype,
    q.is_multi, q.base_n, q.base_desc,
    ROUND(100 * q.base_n / NULLIF(h.qualified_n, 0), 1) AS pct_of_wave
FROM csi_question q
LEFT JOIN csi_topic t ON t.topic_id = q.topic_id
LEFT JOIN v_csi_survey_health h ON h.survey_id = q.survey_id
WHERE q.is_technical = 0;
