"""Mappings — where an analyst settles what the harmoniser could not.

A question only trends across waves once it is confirmed against a concept.
Exact matches confirm themselves; this page holds the rest: the same wording
with new answers, or similar wording. Accept, point it at another concept,
keep it separate, or reject it.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st
from sqlalchemy.exc import DBAPIError

from app.components.footer import render_footer
from app.components.header import page_title, render_header
from app.core import auth
from app.core.config import config
from app.core.database import healthcheck
from app.data import cube, harmonise
from app.data import repository as repo

ok, status = healthcheck("app")
render_header("mappings", status if ok else "database unavailable",
              config.environment.value.upper())
user = auth.require_auth("mappings")
reviewer = user.email if user else "local-dev"
page_title("Mappings", "Confirm which questions are the same across waves — nothing trends until it is.")

if not ok:
    st.error("The portal cannot reach the database.")
    st.stop()


def decide(action, *args) -> None:
    try:
        action(*args)
    except (ValueError, DBAPIError) as exc:     # already settled, e.g. by a colleague
        st.warning(str(exc))
    else:
        try:                                   # args[0] is the decided row's survey_id
            cube.refresh_cohorts(args[0])
        except DBAPIError as exc:              # the decision stands; the cohort numbers wait
            st.warning(f"Saved. Cohort figures for this wave could not be refreshed yet: {exc.orig}")
    repo.mapping_queue.clear()
    repo.mapping_summary.clear()
    repo.concept_list.clear()           # a decision changes which concepts a wave has used
    for cached in (repo.concept_trend, repo.concept_pooled, repo.concept_catalog, repo.cohort_list, repo.analyse):
        cached.clear()                  # trends and cohort numbers read the mappings
    st.rerun()


summary = repo.mapping_summary()
if not summary.empty:
    st.dataframe(summary.pivot_table(index="wave_label", columns="status", values="units",
                                     aggfunc="sum", fill_value=0), width="stretch")

queue = repo.mapping_queue()
if queue.empty:
    st.success("Nothing waiting — every loaded question is settled.")
    render_footer()
    st.stop()

waves = ["All waves"] + sorted(queue.wave_label.unique())
pick_wave = st.selectbox("Wave", waves, key="map_wave")
if pick_wave != "All waves":
    queue = queue[queue.wave_label == pick_wave]
PAGE = 25
pages = max(1, -(-len(queue) // PAGE))
if st.session_state.get("map_page", 1) > pages:    # the wave filter shrank the queue
    st.session_state["map_page"] = pages
page = st.number_input(f"Page (of {pages})", min_value=1, max_value=pages, value=1, key="map_page")
st.markdown(f"#### {len(queue)} waiting for review")
queue = queue.iloc[(page - 1) * PAGE: page * PAGE]
for row in queue.itertuples():
    item = None if pd.isna(row.item_id) else int(row.item_id)
    label = f"{row.wave_label} · {row.qcode}" + (f" · {row.item_label}" if item else "")
    with st.expander(f"{label} — {row.evidence}", expanded=len(queue) <= 5):
        left, right = st.columns(2)
        with left:
            st.caption("This wave asked")
            st.markdown(f"**{row.qtext}**" + (f"  \nRow: *{row.item_label}*" if item else ""))
        with right:
            st.caption(f"Proposed concept · {row.concept_code} · {row.method}"
                       + (f" · {row.confidence:.0%}" if pd.notna(row.confidence) else ""))
            st.markdown(f"**{row.concept_name}**")
            answers = repo.concept_choice(int(row.concept_id))
            if not answers.empty:
                st.caption("Its answers so far: " + ", ".join(answers.option_label))

        key = f"{row.survey_id}_{row.question_id}_{item}"
        b1, b2, b3 = st.columns(3)
        if b1.button("Accept", key=f"acc_{key}", type="primary"):
            decide(harmonise.confirm, int(row.survey_id), int(row.question_id), item,
                   int(row.concept_id), reviewer)
        if b2.button("Keep separate", key=f"sep_{key}"):
            decide(harmonise.keep_separate, int(row.survey_id), int(row.question_id), item, reviewer)
        if b3.button("Reject", key=f"rej_{key}"):
            decide(harmonise.reject, int(row.survey_id), int(row.question_id), item, reviewer)

        others = repo.concept_list(row.qtype, int(row.survey_id))
        others = others[others.concept_id != row.concept_id]
        if not others.empty:
            names = dict(zip(others.concept_id, others.concept_code + " — " + others.concept_name.str[:80]))
            pick = st.selectbox("…or map it to another concept", list(names),
                                format_func=names.get, key=f"pick_{key}", index=None)
            if pick is not None and st.button("Map to this concept", key=f"map_{key}"):
                decide(harmonise.confirm, int(row.survey_id), int(row.question_id), item,
                       int(pick), reviewer)

render_footer()
