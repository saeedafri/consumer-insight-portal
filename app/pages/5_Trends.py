"""Wave-over-wave trending within a survey family."""
from __future__ import annotations

import streamlit as st

from app.components import charts, export
from app.data import repository as repo

from app.components.header import page_title, render_header
from app.core.config import config
from app.core.database import healthcheck

_ok, _status = healthcheck("app")
render_header("trends", _status if _ok else "database unavailable",
              config.environment.value.upper())
page_title("Trends", "Wave over wave, within a survey family.")

if not _ok:
    st.error("The portal cannot reach the database.")
    st.stop()



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
    qcode = st.selectbox("Question", catalog[catalog.is_multi == 1].qcode.tolist())

data = repo.trend(family, qcode)
if data.empty:
    st.warning("No trend data for that question yet.")
    st.stop()

items = sorted(data.groupby("item_label")["pct"].mean().sort_values(ascending=False).index.tolist())
picked = st.multiselect("Items", items, default=items[: min(4, len(items))],
                        help="Six series maximum — past that, fold the tail into 'Other'.")
if picked:
    st.plotly_chart(
        charts.trend_line(data[data.item_label.isin(picked)], "wave_label", "pct", "item_label",
                          title=f"{qcode} over time", entity_order=picked[:6]),
        width="stretch",
    )
trend_table = data.rename(columns={
    "wave_label": "Wave", "item_label": "Item", "pct": "%", "base_n": "Base"})
charts.show_table(trend_table)
export.download_button(
    "Download to Excel",
    f"CSI_trend_{qcode}.xlsx",
    lambda: export.build_workbook(
        {"Trend": trend_table}, f"{qcode} over time",
        [("Survey family", family), ("Question", qcode),
         ("Note", "Each wave carries its own base; a moving base is not a trend "
                  "in the underlying behaviour.")]),
    key_seed=f"tr{family}{qcode}")
