"""Publications — numbers that left Coresight, and whether they still hold.

Each publication is frozen on the day it went out, with its definition. This
page recomputes every one from today's data and says, cell by cell, whether it
still gives the same number — the analysts' Cross-Check tab, done by the portal.
"""
from __future__ import annotations

import json
import re

import pandas as pd
import streamlit as st

from app.components import export, grid
from app.components.footer import render_footer
from app.components.header import page_title, render_header
from app.core import auth
from app.core.config import config
from app.core.database import healthcheck
from app.data import cube, publications
from app.data import repository as repo

ok, status = healthcheck("app")
render_header("publications", status if ok else "database unavailable",
              config.environment.value.upper())
user = auth.require_auth("publications")
page_title("Publications", "Delivered numbers, frozen — and checked against today's data.")

if not ok:
    st.error("The portal cannot reach the database.")
    st.stop()


@st.cache_data(ttl=60, show_spinner="Re-checking every publication…")
def summary() -> pd.DataFrame:
    return publications.drift_summary()


done = summary()
if done.empty:
    st.info("Nothing published yet — publish a table below and it is checked here from then on.")
else:
    done = done.assign(check=[
        "error — definition no longer resolves" if r.error else
        "unchanged" if r.moved + r.missing + r.new == 0 else
        f"{r.moved} moved · {r.missing} missing · {r.new} new" for r in done.itertuples()])
    moved = done[done.check != "unchanged"]
    if moved.empty:
        st.success("The publication still reproduces from today's data." if len(done) == 1 else
                   f"All {len(done)} publications still reproduce from today's data.")
    else:
        st.warning(f"**{len(moved)} of {len(done)} publications no longer reproduce exactly.** "
                   "Open one below to see which numbers moved.")
    grid.show(done[["pub_code", "version", "pub_name", "published_at", "cells", "check"]]
              .rename(columns={"pub_code": "Code", "version": "Version", "pub_name": "Name",
                               "published_at": "Published", "cells": "Cells", "check": "Today"}),
              key="pub_list")

    names = {int(r.publication_id): f"{r.pub_name} (v{r.version})" for r in done.itertuples()}
    pick = st.selectbox("Publication", list(names), format_func=names.get)
    meta = publications.list_publications().set_index("publication_id").loc[pick]
    report = publications.drift(int(pick))
    st.caption(meta.footnote or "")
    if (report.status == "error").any():
        st.error(report.detail.iloc[0])
    else:
        changed = report[report.status != "same"]
        if not changed.empty:
            st.warning(f"{len(changed)} of {len(report)} cells differ from what was published.")
        table = report.rename(columns={"row_key": "Answer", "col_key": "Measure", "published": "Published",
                                       "now": "Today", "delta": "Change", "published_n": "n then",
                                       "now_n": "n today", "status": "Status"}).drop(columns=["detail"])
        grid.show(table, percent_columns=(), key="pub_drift")
    with st.expander("Definition"):
        stored = meta.definition
        st.json(json.loads(stored) if isinstance(stored, str) else stored)
    export.download_button(
        "Download frozen numbers to Excel", f"CSI_publication_{meta.pub_code}_v{meta.version}.xlsx",
        lambda: export.build_workbook(
            {"Published": publications.cells(int(pick)), "Check today": report},
            f"{meta.pub_name} (v{meta.version})",
            [("Code", str(meta.pub_code)), ("Published", str(meta.published_at)),
             ("Footnote", str(meta.footnote or "")), ("Definition", json.dumps(
                 json.loads(meta.definition) if isinstance(meta.definition, str) else meta.definition))],
            percent_columns=()),
        key_seed=f"pub{pick}")

st.divider()
with st.expander("Publish a table", expanded=done.empty):
    catalog = repo.concept_catalog()
    concepts = catalog.set_index("concept_id")
    c1, c2 = st.columns([3, 2])
    with c1:
        concept = st.selectbox("Question", concepts.index.tolist(),
                               format_func=lambda k: f"{concepts.loc[k, 'concept_name'][:100]} · "
                                                     f"{concepts.loc[k, 'waves']} waves")
    trend = repo.concept_trend(int(concept)) if concept is not None else pd.DataFrame()
    waves = sorted(trend.wave_label.unique().tolist()) if not trend.empty else []
    with c2:
        picked_waves = st.multiselect("Waves", waves, default=waves[-5:])
    defined = repo.cohort_list()
    c3, c4, c5, c6 = st.columns(4)
    with c3:
        cohort = st.selectbox("Within", [""] + defined.cohort_code.tolist(),
                              format_func=lambda k: "Everyone" if not k else
                              defined.set_index("cohort_code").loc[k, "cohort_name"])
    with c4:
        pooled = st.checkbox("Pool the waves", value=True, help="One combined table, or one column per wave.")
    with c5:
        cut = st.selectbox("Cut", list(cube.CUBE_DIMS), disabled=not pooled)
    with c6:
        min_base = st.number_input("Suppress below n =", min_value=0, value=30, step=10)
    name = st.text_input("Name", placeholder="Beauty retailers — beauty shoppers, Jun 2024 – May 2025")
    destination = st.text_input("Delivered to (optional)", placeholder="SharePoint link or report name")
    if st.button("Publish", type="primary", disabled=not (name and picked_waves)):
        definition = {"concept": str(concepts.loc[concept, "concept_code"]), "waves": picked_waves,
                      "cohort": cohort or None, "cut": cut if pooled else "total", "pooled": pooled,
                      "min_base": int(min_base)}
        code = re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_")[:80]
        try:
            pid = publications.publish(code, name, definition, owner=user.email if user else None,
                                       destination=destination or None)
        except ValueError as exc:
            st.error(str(exc))
        else:
            summary.clear()
            st.success(f"Published {code} with {len(publications.cells(pid))} cells.")
            st.rerun()

render_footer()
