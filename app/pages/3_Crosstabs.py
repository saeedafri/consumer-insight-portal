"""The cross-tab grid, straight from csi_crosstab."""
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

items = cells[cells.stub_type == "item"]
grid = items.pivot_table(index="stub_label", columns="seg_label", values="pct", aggfunc="mean")

st.subheader(f"{qcode} × {banner}")
st.dataframe(
    grid.style.format("{:.1%}", na_rep="—").background_gradient(cmap="Reds", axis=None),
    use_container_width=True,
)

# Forsta prints the SEGMENT size in the header but divides by the number who
# ANSWERED. On a routed question those differ a lot, so show the real one.
_denoms = sorted({int(d) for d in items.denominator_n.dropna().unique()})
if _denoms:
    _sizes = sorted({int(d) for d in items.segment_size_n.dropna().unique()})
    if _denoms != _sizes:
        st.info(
            f"Percentages here are based on **{min(_denoms)}–{max(_denoms)}** answering"
            f" respondents, not the {max(_sizes)} shown as the segment size — this"
            f" question is routed."
            if len(_denoms) > 1 else
            f"Percentages here are based on **n={_denoms[0]}** who answered, not the"
            f" {max(_sizes)} in the segment — this question is routed."
        )

low = cells[cells.low_base.isin(["*", "**"])].seg_label.unique()
if len(low):
    st.caption(
        "⚠︎ Low base — interpret with caution or suppress: " + ", ".join(sorted(low))
    )

st.divider()
st.subheader("Compare segments")
picked = st.multiselect(
    "Segments", sorted(items.seg_label.unique()),
    default=sorted(items.seg_label.unique())[: min(3, items.seg_label.nunique())],
)
if picked:
    sub = items[items.seg_label.isin(picked)]
    st.plotly_chart(
        charts.grouped_bar(sub, "stub_label", "pct", "seg_label",
                           title=f"{qcode} by segment", entity_order=sorted(picked)),
        use_container_width=True,
    )
charts.show_table(items[["stub_label", "seg_label", "pct", "count_n", "denominator_n", "segment_size_n"]])
