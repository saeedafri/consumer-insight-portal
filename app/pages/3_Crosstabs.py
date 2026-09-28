"""The cross-tab grid, straight from cip_crosstab_cell."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app.components import charts
from app.data import repository as repo

st.title("Cross-tabs")

surveys = repo.list_surveys()
if surveys.empty:
    st.info("No survey waves loaded yet.")
    st.stop()

labels = {int(r.survey_id): f"{r.survey_family or 'Survey'} · {r.wave_label or r.survey_id}"
          for r in surveys.itertuples()}

f1, f2, f3 = st.columns(3)
with f1:
    survey_id = st.selectbox("Wave", list(labels), format_func=lambda k: labels[k])
catalog = repo.question_catalog(survey_id)
banner_df = repo.banners(survey_id)
if catalog.empty or banner_df.empty:
    st.warning("No cross-tab run loaded for this wave.")
    st.stop()
with f2:
    qcode = st.selectbox("Question", catalog.qcode.tolist())
with f3:
    banner = st.selectbox("Banner", banner_df.banner_name.tolist())

cells = repo.crosstab(survey_id, qcode, banner)
if cells.empty:
    st.warning("No cells stored for that question/banner combination.")
    st.stop()

items = cells[cells.stub_kind == "item"]
grid = items.pivot_table(index="stub_label", columns="segment_label", values="pct", aggfunc="mean")

st.subheader(f"{qcode} × {banner}")
st.dataframe(
    grid.style.format("{:.1%}", na_rep="—").background_gradient(cmap="Reds", axis=None),
    use_container_width=True,
)

low = cells[cells.low_base_flag.isin(["*", "**"])].segment_label.unique()
if len(low):
    st.caption(
        "⚠︎ Low base — interpret with caution or suppress: " + ", ".join(sorted(low))
    )

st.divider()
st.subheader("Compare segments")
picked = st.multiselect(
    "Segments", sorted(items.segment_label.unique()),
    default=sorted(items.segment_label.unique())[: min(3, items.segment_label.nunique())],
)
if picked:
    sub = items[items.segment_label.isin(picked)]
    st.plotly_chart(
        charts.grouped_bar(sub, "stub_label", "pct", "segment_label",
                           title=f"{qcode} by segment", entity_order=sorted(picked)),
        use_container_width=True,
    )
charts.show_table(items[["stub_label", "segment_label", "pct", "count_n", "segment_base_n"]])
