"""Consumer Insight Portal — Streamlit entry point.

    streamlit run app/main.py

Navigation lives in the header bar, not the sidebar (app/components/header.py),
matching the Market Data Portal. `position="hidden"` stops Streamlit drawing
its own sidebar nav alongside it.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

st.set_page_config(
    page_title="Consumer Insight Portal · Coresight Research",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

HERE = Path(__file__).parent

# title, file, url_path — url_path must match app/components/header.py NAV
PAGES = [
    ("Overview",         "pages/1_Overview.py",          "overview"),
    ("Questions",        "pages/2_Question_Explorer.py", "questions"),
    ("Analysis Builder", "pages/3_Analysis.py",          "analysis"),
    ("Cross-tabs",       "pages/4_Crosstabs.py",         "crosstabs"),
    ("Trends",           "pages/5_Trends.py",            "trends"),
    ("Data Health",      "pages/6_Data_Health.py",       "data-health"),
]


def main() -> None:
    pages = [
        st.Page(str(HERE / path), title=title, url_path=url, default=(url == "overview"))
        for title, path, url in PAGES
    ]
    st.navigation(pages, position="hidden").run()


if __name__ == "__main__":
    main()
