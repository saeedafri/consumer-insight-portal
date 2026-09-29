"""Analysis Builder — the answer to "can it handle any question?".

The pre-computed cross-tab answers the questions Forsta was asked to tabulate.
This page answers the rest: build a cohort from any combination of
demographics and prior answers, then run any question over it.

"Among GenZ BNPL users in the Midwest, which department stores did they buy
from?" is three criteria and a question, and nothing in the cross-tab covers
it. Here it is four clicks, and it comes with its base, a chart, a table and
an Excel file that carries the provenance.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app.components import charts, export
from app.components.header import page_title, render_header
from app.core.config import config
from app.core.database import healthcheck
from app.data import repository as repo

ok, status = healthcheck("app")
render_header("analysis", status if ok else "database unavailable",
              config.environment.value.upper())
page_title("Analysis Builder",
           "Any cohort, any question, any break — with the base attached.")

if not ok:
    st.error("The portal cannot reach the database.")
    st.stop()

surveys = repo.list_surveys()
if surveys.empty:
    st.info("No survey waves loaded yet.")
    st.stop()

wave_labels = {
    int(r.survey_id): f"{r.survey_family or 'Survey'} · {r.wave_label or r.survey_id}"
    for r in surveys.itertuples()
}

# ── state ──────────────────────────────────────────────────────────────────
if "an_criteria" not in st.session_state:
    st.session_state.an_criteria = []


def _drop(idx: int) -> None:
    st.session_state.an_criteria.pop(idx)


# ── 1. base ────────────────────────────────────────────────────────────────
top = st.columns([2, 3])
with top[0]:
    survey_id = st.selectbox("Wave", list(wave_labels), format_func=lambda k: wave_labels[k])

questions = repo.question_lookup(survey_id)
if questions.empty:
    st.warning("No reportable questions in this wave.")
    st.stop()

qlabel = {
    int(r.question_id): f"{r.qcode} — {r.qtext_short}"
    for r in questions.itertuples()
}
wave_base = int(surveys[surveys.survey_id == survey_id].qualified_n.iloc[0] or 0)

# ── 2. filters ─────────────────────────────────────────────────────────────
st.markdown("#### Filters")
st.caption("Criteria are combined with AND. Values inside one criterion are OR.")

with st.expander("Add a criterion", expanded=not st.session_state.an_criteria):
    c1, c2, c3 = st.columns([1, 2, 2])
    with c1:
        source = st.radio("From", ["Demographic", "An answer"], key="an_src")
    if source == "Demographic":
        with c2:
            dim = st.selectbox("Cut", list(repo.PROFILE_DIMENSIONS),
                               format_func=lambda d: repo.PROFILE_DIMENSIONS[d],
                               key="an_dim")
        with c3:
            vals = st.multiselect("Is one of", repo.dimension_values(survey_id, dim),
                                  key="an_vals")
        if st.button("Add criterion", type="primary", disabled=not vals):
            st.session_state.an_criteria.append(
                {"kind": "profile", "dimension": dim, "values": list(vals),
                 "label": f"{repo.PROFILE_DIMENSIONS[dim]}: {', '.join(vals)}"}
            )
            st.rerun()
    else:
        with c2:
            fq = st.selectbox("Question", list(qlabel), format_func=lambda k: qlabel[k],
                              key="an_fq")
        choices = repo.question_choices(survey_id, fq)
        with c3:
            picked = st.multiselect(
                "Answered", choices["label"].tolist(), key="an_fa",
                help="Respondents who gave any of these answers.")
        if st.button("Add criterion", type="primary", disabled=not picked):
            rows = choices[choices["label"].isin(picked)]
            kind = str(rows["kind"].iloc[0]) if not rows.empty else "item"
            st.session_state.an_criteria.append(
                {"kind": kind, "ids": [int(x) for x in rows["id"].tolist()],
                 "question_id": int(fq),
                 "label": f"{questions.set_index('question_id').loc[fq, 'qcode']}: "
                          f"{', '.join(picked)}"}
            )
            st.rerun()

if st.session_state.an_criteria:
    chips = st.columns(min(len(st.session_state.an_criteria), 4))
    for i, crit in enumerate(list(st.session_state.an_criteria)):
        with chips[i % len(chips)]:
            st.button(f"✕  {crit['label'][:58]}", key=f"an_rm{i}",
                      on_click=_drop, args=(i,), help="Remove this criterion")

criteria = tuple(
    tuple(sorted((k, tuple(v) if isinstance(v, list) else v) for k, v in c.items()
                 if k != "label"))
    for c in st.session_state.an_criteria
)
criteria_for_sql = tuple(
    {k: (list(v) if isinstance(v, tuple) else v) for k, v in dict(c).items()}
    for c in criteria
)

n_cohort = repo.cohort_size(survey_id, criteria_for_sql)
share = f"{100 * n_cohort / wave_base:.0f}%" if wave_base else "—"

m1, m2, m3 = st.columns(3)
with m1:
    charts.stat_tile("Cohort", f"{n_cohort:,}", f"{share} of the {wave_base:,} qualified")
with m2:
    charts.stat_tile("Criteria applied", str(len(st.session_state.an_criteria)))
with m3:
    charts.stat_tile("Wave", wave_labels[survey_id])

if n_cohort == 0:
    st.warning("No respondents match these criteria. Remove one and try again.")
    st.stop()
if n_cohort < 30:
    st.warning(
        f"**n={n_cohort} is below the reporting threshold.** Coresight's own "
        f"cross-tabs flag anything under ~50 and suppress under ~30. Read this "
        f"as directional only — do not put it in a client deck as a percentage."
    )

st.divider()

# ── 3. analyse ─────────────────────────────────────────────────────────────
st.markdown("#### Report")
a1, a2, a3 = st.columns([3, 2, 2])
with a1:
    target = st.selectbox("Question to report", list(qlabel),
                          format_func=lambda k: qlabel[k], key="an_target")
with a2:
    break_by = st.selectbox(
        "Break by", ["(none)"] + list(repo.PROFILE_DIMENSIONS),
        format_func=lambda d: "(none)" if d == "(none)" else repo.PROFILE_DIMENSIONS[d],
        key="an_break")
with a3:
    chart_kind = st.selectbox("Chart", ["Bar", "Grouped bar", "Donut", "Table only"],
                              key="an_chart")

qrow = questions[questions.question_id == target].iloc[0]
st.caption(qrow.qtext)

data = repo.analyse(
    survey_id, int(target), criteria_for_sql,
    None if break_by == "(none)" else break_by,
)
if data.empty:
    st.warning("Nobody in this cohort answered that question.")
    st.stop()

base_n = int(data["base_n"].max())
if base_n < n_cohort:
    st.info(
        f"**Routed question** — {base_n} of the {n_cohort} in this cohort reached "
        f"{qrow.qcode}. Percentages below use n={base_n}."
    )

# ── 4. render ──────────────────────────────────────────────────────────────
broken = break_by != "(none)"
if chart_kind != "Table only":
    if broken and chart_kind in ("Bar", "Grouped bar"):
        segments = sorted(data["segment"].dropna().unique())[:6]
        sub = data[data["segment"].isin(segments)]
        st.plotly_chart(
            charts.grouped_bar(sub, "answer", "pct", "segment",
                               title=f"{qrow.qcode} by {repo.PROFILE_DIMENSIONS[break_by]}",
                               entity_order=segments),
            width="stretch")
        if data["segment"].nunique() > 6:
            st.caption("Showing the six largest segments — past six, colours stop "
                       "being distinguishable. Narrow the break or filter instead.")
    elif chart_kind == "Donut":
        total = data.groupby("answer", as_index=False)["n"].sum()
        st.plotly_chart(charts.donut(total, "answer", "n", title=qrow.qtext_short),
                        width="stretch")
    else:
        total = data.groupby("answer", as_index=False).agg(
            pct=("pct", "mean"), n=("n", "sum"))
        st.plotly_chart(
            charts.horizontal_bar(total, "answer", "pct",
                                  title=f"{qrow.qcode} · % of cohort", base_n=base_n),
            width="stretch")

table = data.copy()
if not broken:
    table = table.drop(columns=["segment"])
table = table.rename(columns={
    "segment": repo.PROFILE_DIMENSIONS.get(break_by, "Segment"),
    "answer": "Answer", "n": "Respondents", "base_n": "Base", "pct": "%"})
st.dataframe(table, width="stretch", hide_index=True,
             column_config={"%": st.column_config.NumberColumn(format="%.1f%%")})

# ── 5. export ──────────────────────────────────────────────────────────────
notes = [
    ("Wave", wave_labels[survey_id]),
    ("Question", f"{qrow.qcode} — {qrow.qtext}"),
    ("Cohort", f"n={n_cohort} of {wave_base} qualified ({share})"),
    ("Base for these percentages", f"n={base_n}"),
    ("Break", "None" if not broken else repo.PROFILE_DIMENSIONS[break_by]),
]
notes += [(f"Filter {i + 1}", c["label"]) for i, c in enumerate(st.session_state.an_criteria)] \
    or [("Filters", "None — all qualified respondents")]

export.download_button(
    "Download to Excel",
    f"CSI_{qrow.qcode}_{wave_labels[survey_id].replace(' · ', '_').replace(' ', '')}.xlsx",
    lambda: export.build_workbook(
        {"Analysis": table}, f"{qrow.qcode} — {qrow.qtext_short}", notes),
    key_seed=f"{survey_id}{target}{break_by}{len(criteria)}",
)
