"""Search every wave, question and concept; chart every question of a wave by
its shape. One FULLTEXT read for the search, three reads for the report."""
from __future__ import annotations

import re

import pandas as pd
import streamlit as st

from app.components import charts, export
from app.components.footer import render_footer
from app.components.header import page_title, render_header
from app.core import auth
from app.core.config import config
from app.core.database import healthcheck
from app.data import repository as repo

ok, status = healthcheck("app")
render_header("report", status if ok else "database unavailable", config.environment.value.upper())
auth.require_auth("report")
page_title("Survey report", "Search any wave or question; every question is charted on its own base.")

if not ok:
    st.error("The portal cannot reach the database.")
    st.stop()

surveys = repo.list_surveys()
if surveys.empty:
    st.info("No survey waves loaded yet.")
    st.stop()
labels = repo.wave_names(surveys)

# ── search ─────────────────────────────────────────────────────────────────
words = st.text_input("Search", placeholder="tariffs, holiday budget, D5, Beauty…", label_visibility="collapsed")
hits = repo.search(words) if words else pd.DataFrame()
if words and hits.empty:
    st.caption("Nothing matches every word.")
elif not hits.empty:
    openable = hits[hits.survey_id.notna() & hits.survey_id.isin(surveys.survey_id)]
    if not openable.empty:
        def open_hit() -> None:
            i = st.session_state["report_hit"]
            st.session_state["report_wave"] = int(openable.survey_id[i])
            st.session_state["report_module"] = "All"
            st.session_state["report_question"] = (int(openable.question_id[i])
                                                   if pd.notna(openable.question_id[i]) else 0)

        st.radio("Results", list(openable.index), index=None, key="report_hit", on_change=open_hit,
                 label_visibility="collapsed",
                 format_func=lambda i: (f"{openable.wave_label[i]} · "
                                        + ("Wave — " if openable.kind[i] == "survey" else f"{openable.body[i]} — ")
                                        + openable.title[i]))
    concepts = hits[hits.kind == "concept"]
    if not concepts.empty:
        with st.expander(f"{len(concepts)} concepts tracked across waves — open them in Trends"):
            st.dataframe(concepts.rename(columns={"title": "Concept", "waves": "Waves"})[["Concept", "Waves"]],
                         hide_index=True, width="stretch")

# ── the wave ───────────────────────────────────────────────────────────────
waves = list(labels)
if st.session_state.get("report_wave") not in waves:
    st.session_state["report_wave"] = waves[0]
survey_id = st.selectbox("Wave", waves, format_func=lambda k: labels[k], key="report_wave")
catalog = repo.question_catalog(survey_id)
if catalog.empty:
    st.warning("No questions loaded for this wave.")
    st.stop()
cells, numbers, texts = repo.wave_report(survey_id)

f1, f2 = st.columns([1, 3])
with f1:
    modules = ["All"] + sorted(catalog.topic_name.dropna().unique().tolist())
    if st.session_state.get("report_module") not in modules:
        st.session_state["report_module"] = "All"
    module = st.selectbox("Module", modules, key="report_module")
scoped = catalog if module == "All" else catalog[catalog.topic_name == module]
with f2:
    picks = {0: "All questions", **{int(r.question_id): f"{r.qcode} — {r.qtext_short}" for r in scoped.itertuples()}}
    if st.session_state.get("report_question") not in picks:
        st.session_state["report_question"] = 0
    focus = st.selectbox("Question", list(picks), format_func=picks.get, key="report_question")
if focus:
    scoped = scoped[scoped.question_id == focus]


def draw(q) -> pd.DataFrame:
    """Chart one question by its shape; return the table behind the chart."""
    qid = int(q.question_id)
    mine = cells[cells.question_id == qid].sort_values(["item_order", "option_order"])
    rows = mine.item_label.nunique() or 1
    kind = charts.chart_kind(q.qtype, bool(q.is_multi), mine.option_order.nunique(), rows,
                             bool(mine.left_label.notna().any() and mine.right_label.notna().any()))
    st.markdown(f"**{q.qcode}** · " + re.sub(r"([\\`*_{}\[\]<>()#+!|$~-])", r"\\\1", str(q.qtext)))
    if kind == "distribution":
        values = numbers[numbers.question_id == qid].value
        if values.empty:
            st.caption("No answers stored.")
            return pd.DataFrame()
        st.caption(f"Base: n={len(values)} · mean {values.mean():,.1f} · median {values.median():,.1f}")
        st.plotly_chart(charts.distribution(values), width="stretch", key=f"c{qid}")
        return values.describe().rename("value").reset_index()
    if kind == "verbatims":
        said = texts[texts.question_id == qid][["value"]].rename(columns={"value": "Answer"})
        st.caption(f"{len(said)} answers")
        if not said.empty:
            st.dataframe(said, hide_index=True, width="stretch", height=min(320, 36 * len(said) + 38), key=f"c{qid}")
        return said
    if mine.empty:
        st.caption("No answers stored.")
        return pd.DataFrame()
    base = int(mine.base_n.max())
    if kind == "ranked_bar":
        fig = charts.horizontal_bar(mine, "item_label", "pct", base_n=base, max_items=40)
    elif kind == "bar":
        fig = charts.horizontal_bar(mine.assign(label=mine.value_label), "label", "pct", base_n=base)
    elif kind == "donut":
        fig = charts.donut(mine, "value_label", "n", center_text=f"n={base}")
    elif kind == "butterfly":
        fig = charts.butterfly(mine)
    elif kind == "diverging_stack":
        order = mine.drop_duplicates("value_label").sort_values("option_order").value_label.tolist()
        fig = charts.diverging_stack(mine, "item_label", "pct", "value_label", order)
    else:
        fig = charts.heatmap(mine, "value_label", "item_label", "pct")
    st.caption(f"Base: n={base}" + (f" · {q.base_desc}" if q.base_desc else ""))
    st.plotly_chart(fig, width="stretch", key=f"c{qid}")
    table = mine[["item_label", "value_label", "n", "base_n", "pct"]].dropna(axis=1, how="all")
    return table.rename(columns={"item_label": "Item", "value_label": "Answer", "n": "n", "base_n": "Base", "pct": "%"})


tables = {}
for q in scoped.itertuples():
    with st.container(border=True):
        tables[str(q.qcode)[:31]] = draw(q)

wave = surveys.set_index("survey_id").wave_label[survey_id]
export.download_button(
    "Download to Excel", f"CIP_{wave}.xlsx",
    lambda: export.build_workbook({k: v for k, v in tables.items() if not v.empty}, labels[survey_id],
                                  [("Wave", labels[survey_id]), ("Base", "qualified respondents who answered")]),
    key_seed=f"report{survey_id}{module}{focus}")

render_footer()
