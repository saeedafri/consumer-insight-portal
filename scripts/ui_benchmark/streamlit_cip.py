"""Benchmark only: CIP's cut view as a simple Streamlit app done well, on the same optimised serving table the API
uses (srv_result: every percentage already computed). The database does the work, results are cached with
st.cache_data, and the page shows a metric, a chart and a table. scripts/ui_benchmark/journey.py drives it.

    streamlit run scripts/ui_benchmark/streamlit_cip.py
"""
import pandas as pd
import streamlit as st
from sqlalchemy import text

from app.core.database import get_engine

WAVE = 415
CUTS = {"Gender": "gender", "Generation": "generation", "Age": "age_band", "Income": "income_band",
        "Region": "census_region", "Urbanicity": "urbanicity"}


@st.cache_data
def questions() -> list[str]:
    with get_engine("app").connect() as conn:
        return [q for (q,) in conn.execute(text(
            "SELECT DISTINCT qcode FROM srv_result WHERE survey_id = :s AND dim = 'total' ORDER BY qcode"), {"s": WAVE})]


@st.cache_data
def results(qcode: str, dim: str) -> pd.DataFrame:
    with get_engine("app").connect() as conn:
        return pd.read_sql(text(
            "SELECT dim_value, COALESCE(NULLIF(option_label, ''), item_label) AS answer, pct, base_n FROM srv_result"
            " WHERE survey_id = :s AND qcode = :q AND dim IN ('total', :d) ORDER BY sort_order"),
            conn, params={"s": WAVE, "q": qcode, "d": dim})


st.title("Consumer Insight Portal")
cut = st.selectbox("Cut", list(CUTS))
qs = questions()
qcode = st.selectbox("Question", qs, index=qs.index("q1") if "q1" in qs else 0)
data = results(qcode, CUTS[cut])
st.metric("Cut", cut)
table = data.pivot_table(index="answer", columns="dim_value", values="pct", sort=False)
st.bar_chart(table)
st.dataframe(table)
