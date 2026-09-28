"""Wave-over-wave trending within a survey family."""
from __future__ import annotations

import streamlit as st

from app.components import charts
from app.data import repository as repo

st.title("Trends")

surveys = repo.list_surveys()
families = sorted(surveys.survey_family.dropna().unique().tolist())
if not families:
    st.info("Load at least two waves of the same survey family to trend.")
    st.stop()

f1, f2 = st.columns(2)
with f1:
    family = st.selectbox("Survey family", families)
scope = surveys[surveys.survey_family == family]
catalog = repo.question_catalog(int(scope.survey_id.iloc[0]))
with f2:
    qcode = st.selectbox("Question", catalog[catalog.is_multi_punch == 1].qcode.tolist())

data = repo.trend(family, qcode)
if data.empty:
    st.warning("No trend data for that question yet.")
    st.stop()

items = sorted(data.groupby("row_label")["pct"].mean().sort_values(ascending=False).index.tolist())
picked = st.multiselect("Items", items, default=items[: min(4, len(items))],
                        help="Six series maximum — past that, fold the tail into 'Other'.")
if picked:
    st.plotly_chart(
        charts.trend_line(data[data.row_label.isin(picked)], "wave_label", "pct", "row_label",
                          title=f"{qcode} over time", entity_order=picked[:6]),
        use_container_width=True,
    )
charts.show_table(data.rename(columns={
    "wave_label": "Wave", "row_label": "Item", "pct": "%", "base_n": "Base"}))
