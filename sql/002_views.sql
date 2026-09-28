-- ═══════════════════════════════════════════════════════════════════════════
-- CIP — reporting views. The Streamlit app reads these, never the raw tables.
-- ═══════════════════════════════════════════════════════════════════════════

-- Wide, human-readable answer stream: what the analyst actually wants to chart.
CREATE OR REPLACE VIEW v_cip_answers AS
SELECT
    r.survey_id,
    s.survey_family,
    s.wave_label,
    s.wave_date,
    r.respondent_id,
    r.is_qualified,
    p.gender, p.age_band, p.generation, p.ethnicity, p.income_band,
    p.urbanicity, p.census_region, p.political,
    g.group_name,
    q.qcode, q.qtext, q.qtext_short, q.qtype,
    qr.row_code, qr.row_label,
    v.variable_name,
    resp.value_code,
    resp.value_label,
    resp.value_numeric,
    p.weight
FROM cip_response      resp
JOIN cip_respondent    r  ON r.respondent_id = resp.respondent_id
JOIN cip_survey        s  ON s.survey_id     = r.survey_id
LEFT JOIN cip_respondent_profile p ON p.respondent_id = r.respondent_id
JOIN cip_variable      v  ON v.variable_id   = resp.variable_id
LEFT JOIN cip_question q  ON q.question_id   = v.question_id
LEFT JOIN cip_question_group g ON g.group_id = q.group_id
LEFT JOIN cip_question_row qr  ON qr.row_id  = v.row_id
WHERE COALESCE(q.is_system, 0) = 0;

-- Incidence of every multi-punch item, computed live off the raw fact table.
-- This is the "% selected" number behind most bar charts.
CREATE OR REPLACE VIEW v_cip_item_incidence AS
SELECT
    r.survey_id,
    q.question_id,
    q.qcode,
    q.qtext_short,
    qr.row_id,
    qr.row_label,
    COUNT(*)                                             AS base_n,
    SUM(CASE WHEN resp.value_code = 1 THEN 1 ELSE 0 END) AS selected_n,
    SUM(CASE WHEN resp.value_code = 1 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0) AS pct
FROM cip_response   resp
JOIN cip_respondent r  ON r.respondent_id = resp.respondent_id AND r.is_qualified = 1
JOIN cip_variable   v  ON v.variable_id   = resp.variable_id
JOIN cip_question   q  ON q.question_id   = v.question_id AND q.is_multi_punch = 1
JOIN cip_question_row qr ON qr.row_id     = v.row_id
GROUP BY r.survey_id, q.question_id, q.qcode, q.qtext_short, qr.row_id, qr.row_label;

-- Single-punch distributions (pie / donut / stacked bar source).
CREATE OR REPLACE VIEW v_cip_single_distribution AS
SELECT
    r.survey_id,
    q.question_id,
    q.qcode,
    q.qtext_short,
    resp.value_code,
    COALESCE(o.value_label, resp.value_label) AS value_label,
    o.is_nonresponse,
    o.net_group,
    COUNT(*) AS n,
    COUNT(*) / NULLIF(SUM(COUNT(*)) OVER (PARTITION BY r.survey_id, q.question_id), 0) AS pct
FROM cip_response   resp
JOIN cip_respondent r ON r.respondent_id = resp.respondent_id AND r.is_qualified = 1
JOIN cip_variable   v ON v.variable_id   = resp.variable_id
JOIN cip_question   q ON q.question_id   = v.question_id
                      AND q.qtype = 'single' AND q.is_system = 0
LEFT JOIN cip_answer_option o
       ON o.question_id = q.question_id AND o.value_code = resp.value_code
WHERE resp.value_code IS NOT NULL
GROUP BY r.survey_id, q.question_id, q.qcode, q.qtext_short,
         resp.value_code, value_label, o.is_nonresponse, o.net_group;

-- Flattened cross-tab: the grid an analyst expects to see on screen.
CREATE OR REPLACE VIEW v_cip_crosstab AS
SELECT
    c.survey_id,
    s.wave_label,
    q.qcode,
    q.qtext,
    c.stub_label,
    c.stub_kind,
    b.banner_name,
    seg.segment_letter,
    seg.segment_label,
    seg.base_n      AS segment_base_n,
    seg.low_base_flag,
    c.pct,
    c.count_n,
    c.sig_against,
    run.percentage_base,
    run.respondent_base
FROM cip_crosstab_cell c
JOIN cip_crosstab_run  run ON run.run_id   = c.run_id AND run.is_current = 1
JOIN cip_survey        s   ON s.survey_id  = c.survey_id
JOIN cip_question      q   ON q.question_id = c.question_id
JOIN cip_segment       seg ON seg.segment_id = c.segment_id
JOIN cip_banner        b   ON b.banner_id  = seg.banner_id;

-- Wave-over-wave trend for any item, keyed on survey_family.
CREATE OR REPLACE VIEW v_cip_trend AS
SELECT
    s.survey_family,
    s.wave_label,
    s.wave_date,
    q.qcode,
    i.row_label,
    i.pct,
    i.base_n
FROM v_cip_item_incidence i
JOIN cip_survey  s ON s.survey_id  = i.survey_id
JOIN cip_question q ON q.question_id = i.question_id;

-- Field-health dashboard for the data team.
CREATE OR REPLACE VIEW v_cip_survey_health AS
SELECT
    s.survey_id,
    s.survey_title,
    s.wave_label,
    COUNT(r.respondent_id)                                          AS total_records,
    SUM(r.is_qualified)                                             AS qualified_n,
    SUM(CASE WHEN r.status_code = 1 THEN 1 ELSE 0 END)              AS terminated_n,
    SUM(CASE WHEN r.status_code = 2 THEN 1 ELSE 0 END)              AS overquota_n,
    SUM(CASE WHEN r.status_code = 4 THEN 1 ELSE 0 END)              AS partial_n,
    ROUND(AVG(NULLIF(r.interview_secs, 0)) / 60, 1)                 AS avg_loi_minutes,
    MIN(r.completed_at)                                             AS first_complete,
    MAX(r.completed_at)                                             AS last_complete
FROM cip_survey s
LEFT JOIN cip_respondent r ON r.survey_id = s.survey_id
GROUP BY s.survey_id, s.survey_title, s.wave_label;
