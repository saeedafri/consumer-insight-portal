"""The 'just show it' pattern: load the table once with st.cache_data, filter in pandas, show it."""
import sqlite3, sys
import pandas as pd
import streamlit as st

DB = sys.argv[-1]

@st.cache_data
def load_stores() -> pd.DataFrame:
    return pd.read_sql("select * from stores", sqlite3.connect(DB))

stores = load_stores()
sector = st.selectbox("Sector", sorted(stores.sector.unique()))
view = stores[stores.sector == sector]
st.metric("Stores open", f"{int((view.closed == 0).sum()):,}")
summary = view.groupby("state").agg(stores=("store_id", "count"), revenue=("revenue", "sum")).reset_index()
st.bar_chart(summary, x="state", y="stores")
st.dataframe(summary)
