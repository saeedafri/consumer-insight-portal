"""Ingestion audit trail — what loaded, when, and what was rejected."""
from __future__ import annotations

import streamlit as st

from app.components import charts
from app.data import repository as repo

st.title("Data health")

surveys = repo.list_surveys()
if not surveys.empty:
    st.subheader("Waves in the portal")
    st.dataframe(surveys, width="stretch", hide_index=True)

st.subheader("Recent ingest runs")
runs = repo.ingest_history()
if runs.empty:
    st.info("No ingest runs recorded yet.")
else:
    failed = runs[runs.status.isin(["failed", "partial"])]
    c1, c2, c3 = st.columns(3)
    with c1:
        charts.stat_tile("Runs (last 25)", f"{len(runs)}")
    with c2:
        charts.stat_tile("Failed or partial", f"{len(failed)}")
    with c3:
        charts.stat_tile("Rows loaded", f"{int(runs.rows_loaded.sum()):,}")
    st.dataframe(runs, width="stretch", hide_index=True)
