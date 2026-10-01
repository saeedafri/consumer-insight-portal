"""Trends — wave over wave within a survey family.

Two things this page refuses to do quietly, because both produce trend lines
that look real and are not:

  * plot a series whose base moves underneath it — a routed question asked of
    222 people one wave and 90 the next is not a trend in behaviour;
  * plot a single wave as if it were a trend.

Both are surfaced rather than hidden.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app.components import charts, export, grid
from app.components.footer import render_footer
from app.components.header import page_title, render_header
from app.core import auth
from app.core.config import config
from app.core.database import healthcheck
from app.data import repository as repo

_ok, _status = healthcheck("app")
render_header("trends", _status if _ok else "database unavailable",
              config.environment.value.upper())
_user = auth.require_auth("trends")
page_title("Trends", "One question across every wave and platform, or wave over wave within a survey family.")

if not _ok:
    st.error("The portal cannot reach the database.")
    st.stop()

mode = st.radio("Trend", ["By question — every wave and platform", "By survey family"], horizontal=True,
                help="By question follows one question through every wave it was asked in, Qualtrics "
                     "and Forsta alike, once the Mappings page has linked it.")

if mode.startswith("By question"):
    catalog = repo.concept_catalog()
    catalog = catalog[catalog.waves >= 2]
    if catalog.empty:
        st.info("No question is linked across two waves yet — confirm matches on the Mappings page.")
        render_footer()
        st.stop()
    names = catalog.set_index("concept_id")
    defined = repo.cohort_list()
    f1, f2, f3 = st.columns([4, 2, 2])
    with f1:
        concept = st.selectbox("Question", names.index.tolist(),
                               format_func=lambda k: f"{names.loc[k, 'concept_name'][:110]} · {names.loc[k, 'waves']} waves")
    with f2:
        cohort = st.selectbox("Within", [0] + defined.cohort_id.tolist(),
                              format_func=lambda k: "Everyone" if k == 0 else
                              defined.set_index("cohort_id").loc[k, "cohort_name"])
    with f3:
        show_base = st.checkbox("Show the base alongside", value=True,
                                help="A percentage that rises while its base collapses "
                                     "is usually the base moving, not the behaviour.")
    family, qcode = "All platforms", str(names.loc[concept, "concept_code"])
    data = repo.concept_trend(int(concept), int(cohort) or None).rename(columns={"answer": "item_label"})
    data = data.drop(columns=["platform", "answer_order", "n"], errors="ignore")
else:
    surveys = repo.list_surveys()
    families = sorted(surveys.survey_family.dropna().unique().tolist())
    if not families:
        st.info("No survey families loaded yet.")
        render_footer()
        st.stop()

    f1, f2, f3 = st.columns([2, 3, 2])
    with f1:
        family = st.selectbox("Survey family", families)

    scope = surveys[surveys.survey_family == family].sort_values("wave_date")
    n_waves = len(scope)

    if n_waves < 2:
        st.warning(
            f"**{family} has one wave loaded ({scope.wave_label.iloc[0]}).** A trend "
            f"needs at least two. Load the earlier waves with\n\n"
            f"`python -m etl.run_pipeline --source excel --raw \"<wave>.xlsx\" "
            f"--wave YYYY-MM --family {family}`\n\n"
            f"and this page fills in. Nothing below is a trend until then."
        )

    catalog = repo.question_catalog(int(scope.survey_id.iloc[-1]))
    multi = catalog[catalog.is_multi == 1]
    if multi.empty:
        st.info("No multi-punch questions to trend in this family.")
        render_footer()
        st.stop()

    with f2:
        qcode = st.selectbox("Question", multi.qcode.tolist())
    with f3:
        show_base = st.checkbox("Show the base alongside", value=True,
                                help="A percentage that rises while its base collapses "
                                     "is usually the base moving, not the behaviour.")

    data = repo.trend(family, qcode)
if data.empty:
    st.warning("No trend data for that question yet.")
    render_footer()
    st.stop()

waves = data.sort_values("wave_date").wave_label.unique().tolist()
ranked = data.groupby("item_label")["pct"].mean().sort_values(ascending=False)
items = ranked.index.tolist()

picked = st.multiselect(
    "Items", items, default=items[: min(4, len(items))],
    help="Six series maximum — past that, colours stop being distinguishable.")

if picked:
    series = data[data.item_label.isin(picked)]
    st.plotly_chart(
        charts.trend_line(series, "wave_label", "pct", "item_label",
                          title=f"{qcode} over time", entity_order=picked[:6]),
        width="stretch")

    if show_base:
        bases = (data.groupby(["wave_label", "wave_date"], as_index=False)["base_n"]
                 .max().sort_values("wave_date"))
        if len(bases) > 1 and bases.base_n.nunique() > 1:
            lo, hi = int(bases.base_n.min()), int(bases.base_n.max())
            if hi and lo / hi < 0.75:
                st.warning(
                    f"**The base moves across these waves — {lo} to {hi}.** "
                    f"A change of that size can produce the shape of the trend on "
                    f"its own. Check the routing before reading the line."
                )
        if len(bases) > 12:        # a tile per wave stops being readable; the table below has each base
            st.caption(f"Base per wave: {int(bases.base_n.min()):,} – {int(bases.base_n.max()):,} "
                       f"across {len(bases)} waves (each wave's base is in the table below).")
        else:
            cols = st.columns(min(len(bases), 6))
            for i, row in enumerate(bases.itertuples()):
                with cols[i % len(cols)]:
                    charts.stat_tile(str(row.wave_label), f"n={int(row.base_n):,}")

table = data.rename(columns={"wave_label": "Wave", "item_label": "Item",
                             "pct": "%", "base_n": "Base"})
table = table.drop(columns=["wave_date"], errors="ignore")
grid.show(table, key="trend_grid")

export.download_button(
    "Download to Excel",
    f"CSI_trend_{family}_{qcode}.xlsx",
    lambda: export.build_workbook(
        {"Trend": table}, f"{qcode} over time — {family}",
        [("Survey family", family),
         ("Waves", ", ".join(waves)),
         ("Question", qcode),
         ("Note", "Each wave carries its own base. A moving base is not a trend "
                  "in the underlying behaviour — compare the Base column before "
                  "reading the percentages as change.")]),
    key_seed=f"tr{family}{qcode}")

render_footer()
