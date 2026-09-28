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

# st.Page resolves paths relative to this file, not the working directory,
# so the portal starts the same way from the repo root or from app/.
PAGES = {
    "Overview": "pages/1_Overview.py",
    "Question explorer": "pages/2_Question_Explorer.py",
    "Cross-tabs": "pages/3_Crosstabs.py",
    "Trends": "pages/4_Trends.py",
    "Data health": "pages/5_Data_Health.py",
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

    pages = [
        st.Page(str(Path(__file__).parent / path), title=title, url_path=title.lower().replace(" ", "-"))
        for title, path in PAGES.items()
    ]
    st.navigation(pages, position="sidebar").run()


if __name__ == "__main__":
    main()
