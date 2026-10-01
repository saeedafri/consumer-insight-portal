"""Analysis Builder — the answer to "can it handle any question?".

The published cross-tab answers the questions Forsta was asked to tabulate.
This page answers the rest: build a cohort from any combination of
demographics and prior answers, then run one question — or a whole report of
them — over it, break it by anything, save it, and take it to Excel.
"""
from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from app.components import charts, export, grid
from app.components.footer import render_footer
from app.components.header import page_title, render_header
from app.core import auth
from app.core.config import config
from app.core.database import healthcheck
from app.data import repository as repo

ok, status = healthcheck("app")
render_header("analysis", status if ok else "database unavailable",
              config.environment.value.upper())
user = auth.require_auth("analysis")
page_title("Analysis Builder",
           "Any cohort, any question, any break — with the base attached.")

if not ok:
    st.error("The portal cannot reach the database.")
    st.stop()

surveys = repo.list_surveys()
if surveys.empty:
    st.info("No survey waves loaded yet.")
    st.stop()

wave_labels = repo.wave_names(surveys)
user_email = (user.email if user else "local-dev")

if "an_criteria" not in st.session_state:
    st.session_state.an_criteria = []


def _drop(idx: int) -> None:
    st.session_state.an_criteria.pop(idx)


def _apply_view(definition: dict) -> None:
    st.session_state.an_criteria = definition.get("criteria", [])
    st.session_state["an_targets"] = definition.get("questions", [])
    st.session_state["an_break"] = definition.get("break") or "(none)"


# ── 1. wave and saved views ────────────────────────────────────────────────
top = st.columns([4, 3, 1])
with top[0]:
    survey_id = st.selectbox("Wave", list(wave_labels), format_func=lambda k: wave_labels[k])

questions = repo.question_lookup(survey_id)
if questions.empty:
    st.warning("No reportable questions in this wave.")
    st.stop()

week = surveys.set_index("survey_id").wave_label[survey_id]
qlabel = {int(r.question_id): f"{r.qcode} — {r.qtext_short}" for r in questions.itertuples()}
wave_base = int(surveys[surveys.survey_id == survey_id].qualified_n.iloc[0] or 0)

views = repo.list_views(survey_id, user_email)
with top[1]:
    if not views.empty:
        options = {
            int(r.view_id): f"{'👥 ' if r.is_shared else ''}{r.view_name}"
            for r in views.itertuples()
        }
        chosen = st.selectbox("Saved view", ["(none)"] + list(options),
                              format_func=lambda k: "(none)" if k == "(none)" else options[k],
                              key="an_view")
        if chosen != "(none)" and st.button("Load view"):
            row = views[views.view_id == chosen].iloc[0]
            _apply_view(json.loads(row.definition))
            st.rerun()
    else:
        st.caption("No saved views yet — build one below and save it.")

# ── 2. filters ─────────────────────────────────────────────────────────────
st.markdown("#### Filters")
st.caption("Criteria are combined with AND. Values inside one criterion are OR.")

with st.expander("Add a criterion", expanded=not st.session_state.an_criteria):
    c1, c2, c3 = st.columns([1, 2, 2])
    with c1:
        source = st.radio("From", ["Demographic", "An answer", "Defined cohort"], key="an_src")
    if source == "Defined cohort":
        defined = repo.cohort_list()
        with c2:
            picked_cohort = st.selectbox(
                "Cohort", defined.cohort_id.tolist(), key="an_cohort",
                format_func=lambda k: defined.set_index("cohort_id").loc[k, "cohort_name"],
                help="A named rule over questions, applied the same way to every wave.")
        with c3:
            if not defined.empty and picked_cohort is not None:
                st.caption(defined.set_index("cohort_id").loc[picked_cohort, "base_note"] or "")
        if st.button("Add criterion", type="primary", disabled=defined.empty):
            name = defined.set_index("cohort_id").loc[picked_cohort, "cohort_name"]
            st.session_state.an_criteria.append(
                {"kind": "cohort", "label": f"Cohort: {name}",
                 "cohort_code": str(defined.set_index("cohort_id").loc[picked_cohort, "cohort_code"])})
            st.rerun()
    elif source == "Demographic":
        with c2:
            dim = st.selectbox("Cut", list(repo.PROFILE_DIMENSIONS),
                               format_func=lambda d: repo.PROFILE_DIMENSIONS[d], key="an_dim")
        with c3:
            vals = st.multiselect("Is one of", repo.dimension_values(survey_id, dim), key="an_vals")
        if st.button("Add criterion", type="primary", disabled=not vals):
            st.session_state.an_criteria.append(
                {"kind": "profile", "dimension": dim, "values": list(vals),
                 "label": f"{repo.PROFILE_DIMENSIONS[dim]}: {', '.join(vals)}"})
            st.rerun()
    else:
        with c2:
            fq = st.selectbox("Question", list(qlabel), format_func=lambda k: qlabel[k], key="an_fq")
        choices = repo.question_choices(survey_id, fq)
        with c3:
            picked = st.multiselect("Answered", choices["label"].tolist(), key="an_fa",
                                    help="Respondents who gave any of these answers.")
        if st.button("Add criterion", type="primary", disabled=not picked):
            rows = choices[choices["label"].isin(picked)]
            kind = str(rows["kind"].iloc[0]) if not rows.empty else "item"
            st.session_state.an_criteria.append(
                {"kind": kind, "ids": [int(x) for x in rows["id"].tolist()],
                 "question_id": int(fq),
                 "label": f"{questions.set_index('question_id').loc[fq, 'qcode']}: "
                          f"{', '.join(picked)}"})
            st.rerun()

if st.session_state.an_criteria:
    chips = st.columns(min(len(st.session_state.an_criteria), 4))
    for i, crit in enumerate(list(st.session_state.an_criteria)):
        with chips[i % len(chips)]:
            st.button(f"✕  {crit['label'][:58]}", key=f"an_rm{i}",
                      on_click=_drop, args=(i,), help="Remove this criterion")

criteria_for_sql = tuple(
    {k: v for k, v in c.items() if k != "label"} for c in st.session_state.an_criteria
)
n_cohort = repo.cohort_size(survey_id, criteria_for_sql)
share = f"{100 * n_cohort / wave_base:.0f}%" if wave_base else "—"

m1, m2, m3 = st.columns(3)
with m1:
    charts.stat_tile("Cohort", f"{n_cohort:,}", f"{share} of the {wave_base:,} qualified")
with m2:
    charts.stat_tile("Criteria applied", str(len(st.session_state.an_criteria)))
with m3:
    charts.stat_tile("Wave", week)

if n_cohort == 0:
    st.warning("No respondents match these criteria. Remove one and try again.")
    render_footer()
    st.stop()
if n_cohort < 30:
    st.warning(
        f"**n={n_cohort} is below the reporting threshold.** Coresight's own "
        f"cross-tabs flag anything under ~50 and suppress under ~30. Read this as "
        f"directional only — do not put it in a client deck as a percentage."
    )

st.divider()

# ── 3. what to report ──────────────────────────────────────────────────────
st.markdown("#### Report")
a1, a2, a3 = st.columns([3, 2, 2])
with a1:
    targets = st.multiselect(
        "Questions to report", list(qlabel), format_func=lambda k: qlabel[k],
        default=st.session_state.get("an_targets") or [list(qlabel)[0]],
        key="an_targets",
        help="Pick several to build a multi-question report — one section each, "
             "one Excel workbook with a sheet per question.")
with a2:
    break_by = st.selectbox(
        "Break by", ["(none)"] + list(repo.PROFILE_DIMENSIONS),
        format_func=lambda d: "(none)" if d == "(none)" else repo.PROFILE_DIMENSIONS[d],
        key="an_break")
with a3:
    chart_kind = st.selectbox("Chart", ["Bar", "Grouped bar", "Donut", "Table only"],
                              key="an_chart")

if not targets:
    st.info("Pick at least one question to report.")
    render_footer()
    st.stop()

broken = break_by != "(none)"
frames = repo.report(survey_id, [int(t) for t in targets], criteria_for_sql,
                     None if not broken else break_by)
if not frames:
    st.warning("Nobody in this cohort answered the questions you picked.")
    render_footer()
    st.stop()

# ── 4. render each question ────────────────────────────────────────────────
sheets: dict[str, pd.DataFrame] = {}
for qcode, data in frames.items():
    qrow = questions[questions.qcode == qcode].iloc[0]
    # segments partition the cohort, so the answering base is summed across them
    base_n = int(data.groupby("segment")["base_n"].max().sum())

    st.markdown(f"##### {qcode} · {qrow.qtext_short}")
    st.caption(qrow.qtext)
    is_grid = str(qrow.qtype).startswith("grid") and not qrow.is_multi
    if is_grid:
        st.info(f"**Grid** — each row is rated only by the people it applies to, so every "
                f"row has its own base (largest here: n={base_n} of {n_cohort}). "
                f"See the Base column.")
    elif base_n < n_cohort:
        st.info(f"**Routed question** — {base_n} of the {n_cohort} in this cohort "
                f"reached {qcode}. Percentages use n={base_n}.")

    if chart_kind != "Table only" and is_grid:
        # one 100% bar per rated row, across the whole cohort
        parts = data.assign(item=data.answer.str.split(" — ").str[0],
                            scale=data.answer.str.split(" — ").str[-1])
        stack = parts.groupby(["item", "scale"], as_index=False, sort=False)["n"].sum()
        stack["pct"] = stack.n / stack.groupby("item").n.transform("sum")
        choices = repo.question_choices(survey_id, int(qrow.question_id))
        scale_order = list(dict.fromkeys(choices.label.str.split(" — ").str[-1]))
        st.plotly_chart(charts.diverging_stack(stack, "item", "pct", "scale", scale_order,
                                               title=f"{qcode} · share of each row's raters"),
                        width="stretch", key=f"ch_{qcode}")
    elif chart_kind != "Table only":
        if broken and chart_kind in ("Bar", "Grouped bar"):
            segments = sorted(data["segment"].dropna().unique())[:6]
            st.plotly_chart(
                charts.grouped_bar(data[data["segment"].isin(segments)], "answer", "pct",
                                   "segment", title=f"{qcode} by "
                                   f"{repo.PROFILE_DIMENSIONS[break_by]}",
                                   entity_order=segments),
                width="stretch", key=f"ch_{qcode}")
            if data["segment"].nunique() > 6:
                st.caption("Showing the six largest segments — past six, colours stop "
                           "being distinguishable. Narrow the break instead.")
        elif chart_kind == "Donut":
            total = data.groupby("answer", as_index=False)["n"].sum()
            st.plotly_chart(charts.donut(total, "answer", "n", title=qrow.qtext_short),
                            width="stretch", key=f"ch_{qcode}")
        else:
            total = data.groupby("answer", as_index=False).agg(pct=("pct", "mean"),
                                                               n=("n", "sum"))
            st.plotly_chart(
                charts.horizontal_bar(total, "answer", "pct",
                                      title=f"{qcode} · % of cohort", base_n=base_n),
                width="stretch", key=f"ch_{qcode}")

    table = data.drop(columns=["qcode", "question"])
    if not broken:
        table = table.drop(columns=["segment"])
    table = table.rename(columns={
        "segment": repo.PROFILE_DIMENSIONS.get(break_by, "Segment"),
        "answer": "Answer", "n": "Respondents", "base_n": "Base", "pct": "%"})
    grid.show(table, key=f"grid_{qcode}")
    sheets[qcode] = table
    st.markdown("---")

# ── 5. save and export ─────────────────────────────────────────────────────
s1, s2 = st.columns([3, 2])

with s1:
    with st.expander("Save this view"):
        name = st.text_input("Name", placeholder="GLP-1 users — apparel spend")
        desc = st.text_input("Description (optional)")
        shared = st.checkbox("Share with the team", value=False)
        if st.button("Save", type="primary", disabled=not name.strip()):
            repo.save_view(
                survey_id, name, user_email,
                {"criteria": st.session_state.an_criteria,
                 "questions": [int(t) for t in targets],
                 "break": None if not broken else break_by},
                desc, shared)
            st.success(f"Saved “{name}”. It re-runs against the current data each "
                       f"time you load it.")
            st.rerun()

    if not views.empty:
        mine = views[views.owner_email == user_email.lower()]
        if not mine.empty:
            with st.expander("Manage saved views"):
                to_delete = st.selectbox(
                    "Delete", ["(none)"] + mine.view_name.tolist(), key="an_del")
                if to_delete != "(none)" and st.button("Delete view"):
                    repo.delete_view(
                        int(mine[mine.view_name == to_delete].view_id.iloc[0]), user_email)
                    st.rerun()

notes = [
    ("Wave", wave_labels[survey_id]),
    ("Cohort", f"n={n_cohort} of {wave_base} qualified ({share})"),
    ("Break", "None" if not broken else repo.PROFILE_DIMENSIONS[break_by]),
    ("Questions", ", ".join(frames)),
    ("Exported by", user_email),
]
notes += ([(f"Filter {i + 1}", c["label"]) for i, c in enumerate(st.session_state.an_criteria)]
          or [("Filters", "None — all qualified respondents")])

with s2:
    export.download_button(
        "Download report to Excel",
        f"CSI_report_{week}.xlsx",
        lambda: export.build_workbook(sheets, "Consumer Insight Portal — analysis", notes),
        key_seed=f"{survey_id}{'-'.join(frames)}{break_by}{len(criteria_for_sql)}",
    )
    st.caption(f"{len(sheets)} sheet{'s' if len(sheets) != 1 else ''} plus provenance.")

render_footer()
