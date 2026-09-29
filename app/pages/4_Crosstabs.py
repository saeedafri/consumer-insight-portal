"""The cross-tab grid, straight from csi_crosstab."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app.components import charts, export
from app.data import repository as repo

from app.components.header import page_title, render_header
from app.core.config import config
from app.core.database import healthcheck

_ok, _status = healthcheck("app")
render_header("crosstabs", _status if _ok else "database unavailable",
              config.environment.value.upper())
page_title("Cross-tabs", "The published Forsta tables, with both bases carried through.")

if not _ok:
    st.error("The portal cannot reach the database.")
    st.stop()



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
    # "Total" is a single column and tells you nothing you can't get elsewhere,
    # so open on the first real break.
    options = banner_df.banner_name.tolist()
    default = next((i for i, b in enumerate(options) if b != "Total"), 0)
    banner = st.selectbox("Banner", options, index=default)

cells = repo.crosstab(survey_id, qcode, banner)
if cells.empty:
    st.warning("No cells stored for that question/banner combination.")
    st.stop()

items = cells[cells.stub_type == "item"]

# Grid questions (DP7 retailers, GP6 categories) print one sub-table per item,
# so the scale labels repeat. Pick the item before pivoting or the rows collide.
grid_items = sorted(items.item_label.dropna().unique())
if grid_items:
    chosen = st.selectbox("Grid item", grid_items,
                          help="This question rates each item on the same scale.")
    items = items[items.item_label == chosen]

grid = items.pivot_table(index="stub_label", columns="seg_label", values="pct", aggfunc="mean")

st.subheader(f"{qcode} × {banner}")
# Segments Forsta flagged ** are too small to report (Non-binary is n=4 here).
# Showing 75% off four people invites exactly the wrong reading, so those
# columns are suppressed rather than shaded alongside real ones.
suppressed = sorted(cells[cells.low_base == "**"].seg_label.unique())
grid = grid.drop(columns=[c for c in suppressed if c in grid.columns])

styled = grid.style.format("{:.1%}", na_rep="—")
if not grid.empty:
    # Shade by absolute magnitude across the whole table, on a fixed 0..max
    # scale. Shading per row turns a two-column table into pure black and
    # white and implies a ranking that two numbers cannot support.
    styled = styled.background_gradient(
        cmap="Reds", axis=None, vmin=0, vmax=float(grid.max(numeric_only=True).max() or 1)
    )
st.dataframe(styled, width="stretch")

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

if suppressed:
    st.caption("Suppressed (base too small to report): " + ", ".join(suppressed))
caution = sorted(cells[cells.low_base == "*"].seg_label.unique())
if caution:
    st.caption("⚠︎ Low base — interpret with caution: " + ", ".join(caution))

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
        width="stretch",
    )
flat = items[["stub_label", "seg_label", "pct", "count_n",
              "denominator_n", "segment_size_n"]].rename(columns={
    "stub_label": "Row", "seg_label": "Segment", "pct": "%",
    "count_n": "Respondents", "denominator_n": "Base (answered)",
    "segment_size_n": "Segment size"})
charts.show_table(flat)

export.download_button(
    "Download to Excel",
    f"CSI_crosstab_{qcode}.xlsx",
    lambda: export.build_workbook(
        {"Grid": grid.reset_index(), "Long form": flat},
        f"{qcode} × {banner}",
        [("Wave", labels[survey_id]),
         ("Banner", banner),
         ("Percentage base", str(cells.pct_base.iloc[0]) if "pct_base" in cells else "Total Answering"),
         ("Suppressed segments", ", ".join(suppressed) or "None"),
         ("Note", "Segment size is how many people are in the column; "
                  "Base (answered) is the denominator behind the percentage. "
                  "They differ on every routed question.")]),
    key_seed=f"ct{survey_id}{qcode}{banner}")
