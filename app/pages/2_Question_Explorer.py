"""Browse every question in a wave and chart it."""
from __future__ import annotations

import streamlit as st

from app.components import charts
from app.data import repository as repo

st.title("Question explorer")

surveys = repo.list_surveys()
if surveys.empty:
    st.info("No survey waves loaded yet.")
    st.stop()

labels = {int(r.survey_id): f"{r.survey_family or 'Survey'} · {r.wave_label or r.survey_id}"
          for r in surveys.itertuples()}
survey_id = st.selectbox("Wave", list(labels), format_func=lambda k: labels[k])

catalog = repo.question_catalog(survey_id)
if catalog.empty:
    st.warning("No questions loaded for this wave.")
    st.stop()

# Filters live in one row above the chart.
f1, f2 = st.columns([1, 3])
with f1:
    group = st.selectbox("Module", ["All"] + sorted(catalog.topic_name.dropna().unique().tolist()))
scoped = catalog if group == "All" else catalog[catalog.topic_name == group]
with f2:
    qmap = {int(r.question_id): f"{r.qcode} — {r.qtext_short}" for r in scoped.itertuples()}
    question_id = st.selectbox("Question", list(qmap), format_func=lambda k: qmap[k])

q = scoped[scoped.question_id == question_id].iloc[0]
st.caption(q.qtext)

# The base travels with the question. Most of this questionnaire is routed —
# DP2 is asked of department-store buyers only, BN2 of BNPL users, GP8 of
# GLP-1 users — so the wave base would overstate the denominator badly.
_wave_base = int(surveys[surveys.survey_id == survey_id].qualified_n.iloc[0] or 0)
if q.base_n and _wave_base and int(q.base_n) < _wave_base:
    st.info(
        f"**Routed question** — asked of {int(q.base_n)} of {_wave_base} respondents"
        f" ({100 * int(q.base_n) / _wave_base:.0f}%). All percentages below use"
        f" n={int(q.base_n)} as the base."
        + (f" Base: {q.base_desc}" if q.base_desc else "")
    )

if q.is_multi:
    data = repo.item_incidence(survey_id, question_id)
    if data.empty:
        st.warning("No responses stored for this question.")
    else:
        st.plotly_chart(
            charts.horizontal_bar(data, "item_label", "pct",
                                  title=f"{q.qcode} · % selected",
                                  base_n=int(data.base_n.max())),
            use_container_width=True,
        )
        charts.show_table(data.rename(columns={
            "item_label": "Item", "pct": "%", "selected_n": "n selected", "base_n": "Base"}))
else:
    data = repo.single_distribution(survey_id, question_id)
    if data.empty:
        st.warning("No responses stored for this question.")
    else:
        left, right = st.columns([3, 2])
        with left:
            st.plotly_chart(
                charts.horizontal_bar(data, "value_label", "pct", title=f"{q.qcode} · distribution"),
                use_container_width=True,
            )
        with right:
            st.plotly_chart(charts.donut(data, "value_label", "n", title="Share"),
                            use_container_width=True)
        charts.show_table(data.rename(columns={
            "value_label": "Answer", "n": "Respondents", "pct": "%"}))
