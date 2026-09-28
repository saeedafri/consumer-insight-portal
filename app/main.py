"""Consumer Insight Portal — Streamlit entry point.

    streamlit run app/main.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

from app.core.config import config
from app.core.database import healthcheck

st.set_page_config(
    page_title="Consumer Insight Portal",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

PAGES = {
    "Overview": "app/pages/1_Overview.py",
    "Question explorer": "app/pages/2_Question_Explorer.py",
    "Cross-tabs": "app/pages/3_Crosstabs.py",
    "Trends": "app/pages/4_Trends.py",
    "Data health": "app/pages/5_Data_Health.py",
}


def main() -> None:
    st.sidebar.markdown("### Consumer Insight Portal")
    st.sidebar.caption(f"Environment: **{config.environment.value.upper()}**")

    ok, message = healthcheck("app")
    st.sidebar.markdown(
        f"<span style='color:{'#1b7f4f' if ok else '#a61f20'};font-size:12px;'>"
        f"{'● ' + message if ok else '● database unavailable'}</span>",
        unsafe_allow_html=True,
    )
    if not ok:
        st.error(
            "The portal cannot reach the STG (DWH) database.\n\n"
            "Check `STG_DB_HOST`, `APP_DB_USER` and the firewall rule for this host. "
            "Details are in `docs/04-it-requirements-checklist.md`."
        )
        with st.expander("Connection error"):
            st.code(message)
        return

    pages = [st.Page(path, title=title) for title, path in PAGES.items()]
    st.navigation(pages).run()


if __name__ == "__main__":
    main()
