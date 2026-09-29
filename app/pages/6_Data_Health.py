"""Ingestion audit trail — what loaded, when, and what was rejected."""
from __future__ import annotations

import streamlit as st

from app.components import charts
from app.data import repository as repo

from app.components.header import page_title, render_header
from app.core.config import config
from app.components.footer import render_footer
from app.core import auth
from app.core.database import healthcheck

_ok, _status = healthcheck("app")
render_header("data-health", _status if _ok else "database unavailable",
              config.environment.value.upper())
_user = auth.require_auth("data-health")
page_title("Data health", "What loaded, when, and what was rejected.")

if not _ok:
    st.error("The portal cannot reach the database.")
    st.stop()



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

render_footer()
