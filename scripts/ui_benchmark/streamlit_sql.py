"""Streamlit done well: the database aggregates; only the small summary is cached."""
import sqlite3, sys
import pandas as pd
import streamlit as st

DB = sys.argv[-1]

@st.cache_data
def sector_summary(sector: str) -> pd.DataFrame:
    sql = "select state, count(*) stores, sum(revenue) revenue, sum(closed = 0) open from stores where sector = ? group by state"
    return pd.read_sql(sql, sqlite3.connect(DB), params=(sector,))

sector = st.selectbox("Sector", ["Apparel", "Beauty", "Department", "Dollar", "Electronics", "Grocery", "Home", "Sporting"])
summary = sector_summary(sector)
st.metric("Stores open", f"{int(summary.open.sum()):,}")
st.bar_chart(summary, x="state", y="stores")
st.dataframe(summary)
