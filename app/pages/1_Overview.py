"""Wave overview: sample composition and headline sentiment."""
from __future__ import annotations

import streamlit as st

from app.components import charts, export
from app.data import repository as repo

from app.components.header import page_title, render_header
from app.core.config import config
from app.core.database import healthcheck

_ok, _status = healthcheck("app")
render_header("overview", _status if _ok else "database unavailable",
              config.environment.value.upper())
page_title("Wave overview", "Sample composition and headline sentiment for a single wave.")

if not _ok:
    st.error("The portal cannot reach the database.")
    st.stop()



surveys = repo.list_surveys()
if surveys.empty:
    st.info("No survey waves loaded yet. Run `python -m etl.run_pipeline --source excel ...`.")
    st.stop()

labels = {
    int(r.survey_id): f"{r.survey_family or 'Survey'} · {r.wave_label or r.survey_id}"
    for r in surveys.itertuples()
}
survey_id = st.selectbox("Wave", list(labels), format_func=lambda k: labels[k])
row = surveys[surveys.survey_id == survey_id].iloc[0]

c1, c2, c3, c4 = st.columns(4)
with c1:
    charts.stat_tile("Qualified respondents", f"{int(row.qualified_n or 0):,}")
with c2:
    charts.stat_tile("Records received", f"{int(row.total_records or 0):,}")
with c3:
    charts.stat_tile("Median interview", f"{row.avg_loi_minutes or 0:.0f} min")
with c4:
    charts.stat_tile("Field close", str(row.last_complete or "—")[:10])

st.divider()
st.subheader("Sample composition")

dimension = st.radio(
    "Break",
    ["generation", "gender", "income_band", "census_region", "urbanicity", "ethnicity"],
    horizontal=True,
    format_func=lambda d: d.replace("_", " ").title(),
)
comp = repo.profile_counts(survey_id, dimension)
if comp.empty:
    st.warning("No profile data for this break. Re-run the profile rebuild step.")
else:
    left, right = st.columns([3, 2])
    with left:
        st.plotly_chart(
            charts.horizontal_bar(comp, "label", "pct",
                                  title=dimension.replace("_", " ").title(),
                                  base_n=int(comp["n"].sum())),
            width="stretch",
        )
    with right:
        st.plotly_chart(charts.donut(comp, "label", "n", title="Share of sample"),
                        width="stretch")
    table = comp.rename(columns={"label": dimension.replace("_", " ").title(),
                                 "n": "Respondents", "pct": "Share"})
    charts.show_table(table)
    export.download_button(
        "Download to Excel",
        f"CSI_sample_{dimension}_{row.wave_label or survey_id}.xlsx",
        lambda: export.build_workbook(
            {"Sample composition": table},
            f"Sample composition by {dimension.replace('_', ' ')}",
            [("Wave", labels[survey_id]),
             ("Base", f"n={int(comp['n'].sum())} qualified respondents")]),
        key_seed=f"ov{survey_id}{dimension}")
