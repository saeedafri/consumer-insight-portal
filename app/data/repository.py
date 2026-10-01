"""Read-only query layer. Every page goes through here — no SQL in pages."""
from __future__ import annotations

from typing import Optional, Sequence

import pandas as pd
import streamlit as st

from app.core.database import query_df

TTL = 900  # 15 minutes


@st.cache_data(ttl=TTL, show_spinner=False)
def list_surveys() -> pd.DataFrame:
    # A wave mid-load has definitions but no respondents yet: counts are 0, not NaN.
    return query_df(
        """
        SELECT s.survey_id, s.title, s.survey_family, s.wave_label, s.wave_date,
               h.total_records, h.qualified_n, h.avg_loi_minutes,
               h.first_complete, h.last_complete
          FROM csi_survey s
          LEFT JOIN v_csi_survey_health h ON h.survey_id = s.survey_id
         WHERE s.load_status = 'verified'          -- a wave mid-load or failed is not shown
         ORDER BY s.wave_date DESC, s.survey_id DESC
        """
    ).fillna({"total_records": 0, "qualified_n": 0})


@st.cache_data(ttl=60, show_spinner=False)
def mapping_queue() -> pd.DataFrame:
    """Harmoniser proposals waiting for an analyst (short TTL: decisions clear it)."""
    return query_df("SELECT * FROM v_csi_mapping_queue ORDER BY wave_label, qcode, item_id")


@st.cache_data(ttl=60, show_spinner=False)
def mapping_summary() -> pd.DataFrame:
    return query_df(
        """
        SELECT s.wave_label, m.status, COUNT(*) AS units
          FROM csi_concept_map m JOIN csi_survey s ON s.survey_id = m.survey_id
         WHERE m.concept_option_id IS NULL
         GROUP BY s.wave_label, m.status
         ORDER BY s.wave_label, m.status
        """
    )


@st.cache_data(ttl=60, show_spinner=False)
def concept_choice(concept_id: int) -> pd.DataFrame:
    return query_df(
        "SELECT option_label, sort_order FROM csi_concept_option"
        " WHERE concept_id = :cid ORDER BY sort_order", {"cid": concept_id})


@st.cache_data(ttl=60, show_spinner=False)
def concept_list(qtype: str, survey_id: Optional[int] = None) -> pd.DataFrame:
    """Concepts a unit of this type could map to — minus those another
    question of the same wave already uses (one wave, one question per concept)."""
    return query_df(
        """
        SELECT c.concept_id, c.concept_code, c.concept_name FROM csi_concept c
         WHERE c.qtype = :qtype
           AND NOT EXISTS (SELECT 1 FROM csi_concept_map m
                            WHERE m.concept_id = c.concept_id AND m.survey_id = :sid
                              AND m.concept_option_id IS NULL AND m.status <> 'rejected')
         ORDER BY c.concept_code
        """, {"qtype": qtype, "sid": -1 if survey_id is None else survey_id})


def wave_names(surveys: pd.DataFrame) -> dict[int, str]:
    """'2026-09-28 · Shopping and Spending - inc Beauty + Holiday + …' — the
    modules differ every week, so the week alone doesn't say what was asked."""
    return {int(r.survey_id): f"{r.wave_label} · {r.title}" for r in surveys.itertuples()}


@st.cache_data(ttl=TTL, show_spinner=False)
def question_catalog(survey_id: int) -> pd.DataFrame:
    return query_df(
        """
        SELECT q.question_id, q.qcode, q.qtext, q.qtext_short, q.qtype,
               q.is_multi, q.base_n, q.base_desc,
               g.topic_code, g.topic_name, g.sort_order AS group_order,
               q.sort_order
          FROM csi_question q
          LEFT JOIN csi_topic g ON g.topic_id = q.topic_id
         WHERE q.survey_id = :sid AND q.is_technical = 0
         ORDER BY g.sort_order, q.sort_order
        """,
        {"sid": survey_id},
    )


@st.cache_data(ttl=TTL, show_spinner=False)
def item_incidence(survey_id: int, question_id: int) -> pd.DataFrame:
    return query_df(
        """
        SELECT item_label, pct, selected_n, base_n, is_exclusive
          FROM v_csi_item_incidence
         WHERE survey_id = :sid AND question_id = :qid
         ORDER BY pct DESC
        """,
        {"sid": survey_id, "qid": question_id},
    )


@st.cache_data(ttl=TTL, show_spinner=False)
def single_distribution(survey_id: int, question_id: int) -> pd.DataFrame:
    return query_df(
        """
        SELECT value_code, answer_label AS value_label, n, pct, base_n, is_nonresponse
          FROM v_csi_single_distribution
         WHERE survey_id = :sid AND question_id = :qid
         ORDER BY value_code
        """,
        {"sid": survey_id, "qid": question_id},
    )


@st.cache_data(ttl=TTL, show_spinner=False)
def crosstab(survey_id: int, qcode: str, banner_name: Optional[str] = None) -> pd.DataFrame:
    sql = """
        SELECT item_label, stub_label, stub_type, banner_name, seg_letter, seg_label,
               segment_size_n, denominator_n, low_base, pct, count_n, sig_letters
          FROM v_csi_crosstab
         WHERE survey_id = :sid AND qcode = :qcode
    """
    params: dict = {"sid": survey_id, "qcode": qcode}
    if banner_name:
        sql += " AND banner_name = :banner"
        params["banner"] = banner_name
    return query_df(sql + " ORDER BY stub_label, seg_label", params)


@st.cache_data(ttl=TTL, show_spinner=False)
def banners(survey_id: int) -> pd.DataFrame:
    return query_df(
        """
        SELECT b.banner_id, b.banner_name, COUNT(s.segment_id) AS n_segments
          FROM csi_banner b
          LEFT JOIN csi_segment s ON s.banner_id = b.banner_id
         WHERE b.survey_id = :sid
         GROUP BY b.banner_id, b.banner_name
         ORDER BY b.sort_order
        """,
        {"sid": survey_id},
    )


@st.cache_data(ttl=TTL, show_spinner=False)
def trend(survey_family: str, qcode: str) -> pd.DataFrame:
    return query_df(
        """
        SELECT wave_label, wave_date, item_label, pct, base_n
          FROM v_csi_trend
         WHERE survey_family = :fam AND qcode = :qcode
         ORDER BY wave_date, item_label
        """,
        {"fam": survey_family, "qcode": qcode},
    )


@st.cache_data(ttl=TTL, show_spinner=False)
def profile_counts(survey_id: int, dimension: str) -> pd.DataFrame:
    allowed = {
        "gender", "age_band", "generation", "ethnicity", "income_band",
        "urbanicity", "census_region", "political",
    }
    if dimension not in allowed:
        raise ValueError(f"Unsupported dimension: {dimension}")
    return query_df(
        f"""
        SELECT {dimension} AS label, COUNT(*) AS n,
               COUNT(*) * 1.0 / SUM(COUNT(*)) OVER () AS pct
          FROM csi_profile p
          JOIN csi_respondent r ON r.respondent_id = p.respondent_id
         WHERE p.survey_id = :sid AND r.is_qualified = 1 AND {dimension} IS NOT NULL
         GROUP BY {dimension}
         ORDER BY n DESC
        """,
        {"sid": survey_id},
    )


@st.cache_data(ttl=TTL, show_spinner=False)
def ingest_history(limit: int = 25) -> pd.DataFrame:
    return query_df(
        """
        SELECT load_id, survey_id, source_type, object_type, source_ref,
               rows_read, rows_loaded, rows_bad, status,
               started_at, finished_at
          FROM csi_load_log
         ORDER BY started_at DESC
         LIMIT :lim
        """,
        {"lim": limit},
    )


# ═══════════════════════════════════════════════════════════════════════════
# Analysis engine — arbitrary cohort, arbitrary question, arbitrary break
#
# The portal has to answer questions nobody wrote a page for: "among GenZ BNPL
# users in the Midwest, which department stores did they buy from?" That is a
# cohort (three criteria) crossed with a question, and it cannot be served from
# the pre-computed cross-tab because Forsta never tabulated it.
#
# So the cohort is built as an intersection of EXISTS conditions over the long
# fact table and the flattened profile, and the target question is aggregated
# over whoever survives. Every result carries the base it was computed on.
# ═══════════════════════════════════════════════════════════════════════════

PROFILE_DIMENSIONS: dict[str, str] = {
    "generation": "Generation",
    "age_band": "Age band",
    "gender": "Gender",
    "ethnicity": "Ethnicity",
    "income_band": "Household income",
    "urbanicity": "Urbanicity",
    "census_region": "Census region",
    "state_name": "State",
    "political": "Political philosophy",
    "relationship": "Relationship status",
    "outlook_income": "Discretionary-income outlook",
    "outlook_economy": "Economy outlook",
}


@st.cache_data(ttl=TTL, show_spinner=False)
def dimension_values(survey_id: int, dimension: str) -> list[str]:
    """Distinct values of a demographic cut, most common first."""
    if dimension not in PROFILE_DIMENSIONS:
        raise ValueError(f"Unsupported dimension: {dimension}")
    df = query_df(
        f"""
        SELECT {dimension} AS v, COUNT(*) AS n
          FROM csi_profile p
          JOIN csi_respondent r ON r.respondent_id = p.respondent_id
         WHERE p.survey_id = :sid AND r.is_qualified = 1 AND {dimension} IS NOT NULL
         GROUP BY {dimension}
         ORDER BY n DESC
        """,
        {"sid": survey_id},
    )
    return df["v"].tolist()


@st.cache_data(ttl=TTL, show_spinner=False)
def question_choices(survey_id: int, question_id: int) -> pd.DataFrame:
    """The selectable answers for a question — items for a multi-punch,
    answer options for a single-punch, "item — rating" pairs for a grid.
    Used to build filter criteria."""
    meta = query_df("SELECT qtype, is_multi FROM csi_question WHERE question_id = :qid",
                    {"qid": question_id})
    if not meta.empty and str(meta.qtype.iloc[0]).startswith("grid") and not meta.is_multi.iloc[0]:
        rows = query_df(
            "SELECT item_id, item_label FROM csi_item WHERE question_id = :qid ORDER BY sort_order",
            {"qid": question_id})
        scale = query_df(
            "SELECT value_code, value_label FROM csi_option WHERE question_id = :qid ORDER BY sort_order",
            {"qid": question_id})
        pairs = rows.merge(scale, how="cross")
        # ponytail: item and code packed into one int; fine while scales stay under 1000 points
        return pd.DataFrame({"id": pairs.item_id * GRID_KEY + pairs.value_code,
                             "label": pairs.item_label + " — " + pairs.value_label,
                             "kind": "grid"})
    items = query_df(
        """
        SELECT i.item_id AS id, i.item_label AS label, 'item' AS kind
          FROM csi_item i
         WHERE i.question_id = :qid AND i.is_other = 0
         ORDER BY i.sort_order
        """,
        {"qid": question_id},
    )
    if not items.empty:
        return items
    return query_df(
        """
        SELECT o.value_code AS id, o.value_label AS label, 'code' AS kind
          FROM csi_option o
         WHERE o.question_id = :qid
         ORDER BY o.sort_order
        """,
        {"qid": question_id},
    )


GRID_KEY = 1000


def _cohort_sql(criteria: list[dict]) -> tuple[str, dict]:
    """Build the WHERE fragment and params for a list of filter criteria.

    Criteria are ANDed. Within one criterion the selected values are ORed,
    which is what an analyst means by "GenZ or Millennial".
    """
    clauses: list[str] = []
    params: dict[str, object] = {}
    for n, crit in enumerate(criteria):
        kind = crit.get("kind")
        if kind == "profile":
            dim = crit["dimension"]
            if dim not in PROFILE_DIMENSIONS or not crit.get("values"):
                continue
            key = f"pv{n}"
            placeholders = ", ".join(f":{key}_{i}" for i in range(len(crit["values"])))
            params.update({f"{key}_{i}": v for i, v in enumerate(crit["values"])})
            clauses.append(f"p.{dim} IN ({placeholders})")
        elif kind == "item":
            ids = crit.get("ids") or []
            if not ids:
                continue
            key = f"iv{n}"
            placeholders = ", ".join(f":{key}_{i}" for i in range(len(ids)))
            params.update({f"{key}_{i}": v for i, v in enumerate(ids)})
            clauses.append(
                f"""EXISTS (SELECT 1 FROM csi_answer a{n}
                              JOIN csi_field f{n} ON f{n}.field_id = a{n}.field_id
                             WHERE a{n}.respondent_id = r.respondent_id
                               AND f{n}.item_id IN ({placeholders})
                               AND a{n}.value_code = 1)"""
            )
        elif kind == "code":
            ids = crit.get("ids") or []
            qid = crit.get("question_id")
            if not ids or not qid:
                continue
            key = f"cv{n}"
            placeholders = ", ".join(f":{key}_{i}" for i in range(len(ids)))
            params.update({f"{key}_{i}": v for i, v in enumerate(ids)})
            params[f"cq{n}"] = qid
            clauses.append(
                f"""EXISTS (SELECT 1 FROM csi_answer a{n}
                              JOIN csi_field f{n} ON f{n}.field_id = a{n}.field_id
                             WHERE a{n}.respondent_id = r.respondent_id
                               AND f{n}.question_id = :cq{n}
                               AND a{n}.value_code IN ({placeholders}))"""
            )
        elif kind == "cohort":
            # by code, so a saved view follows the cohort to its current version
            if crit.get("cohort_code"):
                params[f"ck{n}"] = str(crit["cohort_code"])
                clauses.append(
                    f"""EXISTS (SELECT 1 FROM csi_respondent_cohort rc{n}
                                  JOIN csi_cohort_def d{n} ON d{n}.cohort_id = rc{n}.cohort_id
                                   AND d{n}.is_current = 1 AND d{n}.cohort_code = :ck{n}
                                 WHERE rc{n}.respondent_id = r.respondent_id)"""
                )
            elif crit.get("cohort_id"):
                params[f"ck{n}"] = int(crit["cohort_id"])
                clauses.append(
                    f"""EXISTS (SELECT 1 FROM csi_respondent_cohort rc{n}
                                 WHERE rc{n}.respondent_id = r.respondent_id AND rc{n}.cohort_id = :ck{n})"""
                )
        elif kind == "grid":
            ids = crit.get("ids") or []
            if not ids:
                continue
            ors = []
            for i, packed in enumerate(ids):
                item, code = divmod(int(packed), GRID_KEY)
                params.update({f"gi{n}_{i}": item, f"gc{n}_{i}": code})
                ors.append(f"(f{n}.item_id = :gi{n}_{i} AND a{n}.value_code = :gc{n}_{i})")
            clauses.append(
                f"""EXISTS (SELECT 1 FROM csi_answer a{n}
                              JOIN csi_field f{n} ON f{n}.field_id = a{n}.field_id
                             WHERE a{n}.respondent_id = r.respondent_id
                               AND ({" OR ".join(ors)}))"""
            )
    return (" AND ".join(clauses) if clauses else "1=1"), params


@st.cache_data(ttl=TTL, show_spinner=False)
def cohort_size(survey_id: int, criteria: tuple) -> int:
    where, params = _cohort_sql(list(criteria))
    params["sid"] = survey_id
    df = query_df(
        f"""
        SELECT COUNT(*) AS n
          FROM csi_respondent r
          LEFT JOIN csi_profile p ON p.respondent_id = r.respondent_id
         WHERE r.survey_id = :sid AND r.is_qualified = 1 AND {where}
        """,
        params,
    )
    return int(df["n"].iloc[0]) if not df.empty else 0


@st.cache_data(ttl=TTL, show_spinner=False)
def analyse(
    survey_id: int,
    question_id: int,
    criteria: tuple = (),
    break_dimension: Optional[str] = None,
) -> pd.DataFrame:
    """Answer distribution for one question over a filtered cohort.

    Returns tidy rows: answer, [segment], n, base_n, pct. The base is the
    number in the cohort who ANSWERED this question — routed questions keep
    their own denominator even after filtering.
    """
    # Cube first: everyone or one defined cohort, by a standard cut (or none).
    from app.data.cube import CUBE_DIMS
    kinds = [c.get("kind") for c in criteria]
    if kinds in ([], ["cohort"]) and (break_dimension or "total") in CUBE_DIMS:
        cohort_id = None
        if criteria:
            from app.data.cohorts import current_id
            code = criteria[0].get("cohort_code")
            cohort_id = current_id(code) if code else criteria[0].get("cohort_id")
        if not criteria or cohort_id:
            frame = analyse_cube(survey_id, question_id, cohort_id, break_dimension)
            if not frame.empty:
                return frame

    where, params = _cohort_sql(list(criteria))
    params.update({"sid": survey_id, "qid": question_id})

    if break_dimension and break_dimension not in PROFILE_DIMENSIONS:
        raise ValueError(f"Unsupported break: {break_dimension}")
    seg_select = f"p.{break_dimension} AS segment," if break_dimension else "'Total' AS segment,"
    seg_group = f"p.{break_dimension}" if break_dimension else "'Total'"

    meta = query_df(
        "SELECT qtype, is_multi FROM csi_question WHERE question_id = :qid",
        {"qid": question_id},
    )
    if meta.empty:
        return pd.DataFrame()
    is_multi = bool(meta["is_multi"].iloc[0])
    # A grid rates several items on one scale; each item is its own distribution.
    is_grid = str(meta["qtype"].iloc[0]).startswith("grid") and not is_multi

    if is_multi:
        sql = f"""
            SELECT {seg_select}
                   i.item_label AS answer,
                   i.sort_order AS answer_order,
                   SUM(CASE WHEN a.value_code = 1 THEN 1 ELSE 0 END) AS n,
                   COUNT(*) AS base_n
              FROM csi_respondent r
              LEFT JOIN csi_profile p ON p.respondent_id = r.respondent_id
              JOIN csi_answer a ON a.respondent_id = r.respondent_id
              JOIN csi_field  f ON f.field_id = a.field_id AND f.question_id = :qid
              JOIN csi_item   i ON i.item_id = f.item_id
             WHERE r.survey_id = :sid AND r.is_qualified = 1 AND {where}
             GROUP BY {seg_group}, i.item_label, i.sort_order
        """
    else:
        sql = f"""
            SELECT {seg_select}
                   COALESCE(i.item_label, '') AS item,
                   COALESCE(i.sort_order, 0) AS item_order,
                   COALESCE(o.value_label, a.value_label) AS answer,
                   COALESCE(o.sort_order, a.value_code) AS answer_order,
                   COUNT(*) AS n,
                   0 AS base_n
              FROM csi_respondent r
              LEFT JOIN csi_profile p ON p.respondent_id = r.respondent_id
              JOIN csi_answer a ON a.respondent_id = r.respondent_id
              JOIN csi_field  f ON f.field_id = a.field_id AND f.question_id = :qid
              LEFT JOIN csi_item i ON i.item_id = f.item_id
              LEFT JOIN csi_option o ON o.question_id = :qid AND o.value_code = a.value_code
             WHERE r.survey_id = :sid AND r.is_qualified = 1 AND {where}
               AND a.value_code IS NOT NULL
             GROUP BY {seg_group}, COALESCE(i.item_label, ''), COALESCE(i.sort_order, 0),
                      COALESCE(o.value_label, a.value_label),
                      COALESCE(o.sort_order, a.value_code)
        """

    df = query_df(sql, params)
    if df.empty:
        return df
    # A respondent with no value for the cut is a segment too; pandas drops
    # None keys from groupby and map, which left that row with no base.
    df["segment"] = df["segment"].fillna("")

    if is_multi:
        # Forsta's "Total Answering": everyone who answered the question, not
        # only those shown a given item. Items routed away from someone count
        # as not chosen — BT8 shows cosmetics only to cosmetics buyers.
        answered = query_df(
            f"""
            SELECT {seg_select} COUNT(DISTINCT r.respondent_id) AS answered_n
              FROM csi_respondent r
              LEFT JOIN csi_profile p ON p.respondent_id = r.respondent_id
              JOIN csi_answer a ON a.respondent_id = r.respondent_id
              JOIN csi_field  f ON f.field_id = a.field_id AND f.question_id = :qid
             WHERE r.survey_id = :sid AND r.is_qualified = 1 AND {where}
               AND a.value_code IS NOT NULL
             GROUP BY {seg_group}
            """,
            params,
        )
        df["base_n"] = df["segment"].map(dict(zip(answered["segment"].fillna(""), answered["answered_n"])))
    else:
        # base for a single-punch is everyone in the segment who answered —
        # per grid row, since only a retailer's own shoppers rate it
        df["base_n"] = df.groupby(["segment", "item"])["n"].transform("sum")
        if is_grid:
            df["answer"] = df["item"] + " — " + df["answer"]
        df["answer_order"] = df["item_order"] * 1000 + df["answer_order"]

    df["segment"] = df["segment"].replace("", None)
    df["pct"] = df["n"] / df["base_n"].replace(0, pd.NA)
    df = df.sort_values(["segment", "answer_order"]).reset_index(drop=True)
    return df[["segment", "answer", "n", "base_n", "pct"]]


def analyse_cube(survey_id: int, question_id: int, cohort_id: Optional[int] = None,
                 break_dimension: Optional[str] = None) -> pd.DataFrame:
    """analyse() read from the cube: the same frame, one indexed read."""
    df = query_df(
        """
        SELECT c.dim_value AS segment, c.n, c.base_n, i.item_label,
               COALESCE(i.sort_order, 0) AS item_order, o.value_label, o.sort_order AS option_order,
               q.qtype, q.is_multi
          FROM csi_agg_cell c
          JOIN csi_question q ON q.question_id = c.question_id
          LEFT JOIN csi_item i ON i.item_id = c.item_id
          LEFT JOIN csi_option o ON o.option_id = c.option_id
         WHERE c.survey_id = :sid AND c.question_id = :qid AND c.dim = :dim
           AND COALESCE(c.cohort_id, 0) = :coh
        """,
        {"sid": survey_id, "qid": question_id, "dim": break_dimension or "total", "coh": cohort_id or 0},
    )
    if df.empty:
        return df
    meta = df.iloc[:1]
    if bool(meta["is_multi"].iloc[0]):
        df["answer"], df["answer_order"] = df["item_label"], df["item_order"]
    else:
        is_grid = str(meta["qtype"].iloc[0]).startswith("grid")
        df["answer"] = (df["item_label"] + " — " + df["value_label"]) if is_grid else df["value_label"]
        df["answer_order"] = df["item_order"] * 1000 + df["option_order"]
    df["segment"] = df["segment"].replace("", None)
    df["pct"] = df["n"] / df["base_n"].replace(0, pd.NA)
    df = df.sort_values(["segment", "answer_order"]).reset_index(drop=True)
    return df[["segment", "answer", "n", "base_n", "pct"]]


_CONCEPT_CELLS = """
    FROM csi_concept_option co
    JOIN csi_concept_map m ON m.concept_option_id = co.concept_option_id AND m.status = 'confirmed'
    JOIN csi_agg_cell c ON c.survey_id = m.survey_id AND c.map_key = m.map_key
         AND c.dim = :dim AND COALESCE(c.cohort_id, 0) = :coh
    JOIN csi_survey s ON s.survey_id = m.survey_id AND s.load_status = 'verified'
   WHERE co.concept_id = :cid
"""


@st.cache_data(ttl=TTL, show_spinner=False)
def concept_trend(concept_id: int, cohort_id: Optional[int] = None) -> pd.DataFrame:
    """One concept across every wave and platform that has it confirmed —
    joined through csi_concept_map, so a mapping confirmed today shows today."""
    df = query_df(
        f"""
        SELECT s.survey_id, s.wave_label, s.wave_date, s.platform, co.option_label AS answer,
               co.sort_order AS answer_order, c.n, c.base_n
        {_CONCEPT_CELLS}
        """,
        {"cid": concept_id, "coh": cohort_id or 0, "dim": "total"},
    )
    if df.empty:
        return df
    df[["n", "base_n"]] = df[["n", "base_n"]].apply(pd.to_numeric)
    # One point per wave label: two panels fielded the same week (Dec 2023
    # Last Mile + RIWI) add up, and each survey's base counts once.
    base = (df.groupby(["survey_id", "wave_label"])["base_n"].max()
              .groupby("wave_label").sum())
    out = (df.groupby(["wave_label", "wave_date", "answer", "answer_order"], as_index=False)
             .agg(n=("n", "sum"), platform=("platform", lambda p: ", ".join(sorted(set(p))))))
    out["base_n"] = out["wave_label"].map(base)
    out["pct"] = out["n"] / out["base_n"].replace(0, pd.NA)
    return out.sort_values(["wave_date", "answer_order"]).reset_index(drop=True)


@st.cache_data(ttl=TTL, show_spinner=False)
def concept_pooled(concept_id: int, survey_ids: Sequence[int], cohort_id: Optional[int] = None,
                   dim: str = "total") -> pd.DataFrame:
    """Waves stacked (the workbook's "Five Waves Combined"): counts add, each
    wave's base adds once, averages use range midpoints over those who gave one."""
    ids = [int(x) for x in survey_ids]
    if not ids:
        return pd.DataFrame()
    marks = ", ".join(f":w{i}" for i in range(len(ids)))
    df = query_df(
        f"""
        SELECT c.survey_id, c.dim_value AS segment, co.option_label AS answer, co.sort_order AS answer_order,
               c.n, c.base_n, c.sum_age_mid, c.n_age_mid, c.sum_income_mid_k, c.n_income_mid
        {_CONCEPT_CELLS} AND c.survey_id IN ({marks})
        """,
        {"cid": concept_id, "coh": cohort_id or 0, "dim": dim, **{f"w{i}": v for i, v in enumerate(ids)}},
    )
    if df.empty:
        return df
    for col in ("n", "base_n", "sum_age_mid", "n_age_mid", "sum_income_mid_k", "n_income_mid"):
        df[col] = pd.to_numeric(df[col])
    base = df.groupby(["survey_id", "segment"])["base_n"].max().groupby("segment").sum()
    out = (df.groupby(["segment", "answer", "answer_order"], as_index=False)
             [["n", "sum_age_mid", "n_age_mid", "sum_income_mid_k", "n_income_mid"]].sum())
    out["base_n"] = out["segment"].map(base)
    out["pct"] = out["n"] / out["base_n"].replace(0, pd.NA)
    out["avg_age"] = out["sum_age_mid"] / out["n_age_mid"].replace(0, pd.NA)
    out["avg_income_k"] = out["sum_income_mid_k"] / out["n_income_mid"].replace(0, pd.NA)
    out["segment"] = out["segment"].replace("", None)
    out = out.sort_values(["segment", "answer_order"]).reset_index(drop=True)
    return out[["segment", "answer", "n", "base_n", "pct", "avg_age", "avg_income_k"]]


@st.cache_data(ttl=TTL, show_spinner=False)
def concept_catalog() -> pd.DataFrame:
    """Concepts confirmed in at least one wave, the most-asked first."""
    return query_df(
        """
        SELECT c.concept_id, c.concept_code, c.concept_name, c.qtype,
               COUNT(DISTINCT m.survey_id) AS waves
          FROM csi_concept c
          JOIN csi_concept_map m ON m.concept_id = c.concept_id AND m.status = 'confirmed'
               AND m.concept_option_id IS NULL
         GROUP BY c.concept_id, c.concept_code, c.concept_name, c.qtype
         ORDER BY waves DESC, c.concept_name
        """
    )


@st.cache_data(ttl=60, show_spinner=False)
def cohort_list() -> pd.DataFrame:
    return query_df(
        """
        SELECT d.cohort_id, d.cohort_code, d.cohort_name, d.version, d.base_note,
               COUNT(rc.respondent_id) AS members
          FROM csi_cohort_def d
          LEFT JOIN csi_respondent_cohort rc ON rc.cohort_id = d.cohort_id
         WHERE d.is_current = 1
         GROUP BY d.cohort_id, d.cohort_code, d.cohort_name, d.version, d.base_note
         ORDER BY d.cohort_name
        """
    )


@st.cache_data(ttl=TTL, show_spinner=False)
def question_lookup(survey_id: int) -> pd.DataFrame:
    """Every reportable question with the label the pickers show."""
    return query_df(
        """
        SELECT q.question_id, q.qcode, q.qtext, q.qtext_short, q.qtype,
               q.is_multi, q.base_n, t.topic_name
          FROM csi_question q
          LEFT JOIN csi_topic t ON t.topic_id = q.topic_id
         WHERE q.survey_id = :sid AND q.is_technical = 0
           AND q.qtype IN ('single', 'multi', 'grid_single', 'grid_multi')
         ORDER BY t.sort_order, q.sort_order
        """,
        {"sid": survey_id},
    )


# ═══════════════════════════════════════════════════════════════════════════
# Saved views
#
# What is stored is the DEFINITION — filters, questions, break — not the
# numbers. A saved view therefore re-runs against whatever is in the warehouse
# today, which is the whole reason for saving it: "my GLP-1 cut" should follow
# the data forward, not freeze last month's figures.
# ═══════════════════════════════════════════════════════════════════════════
import json as _json  # noqa: E402


def list_views(survey_id: int, user_email: str) -> pd.DataFrame:
    """A user's own views plus anything the team has shared.

    Deliberately NOT cached: a view saved in one click must be in the list on
    the next rerun, and the query is a handful of rows.
    """
    return query_df(
        """
        SELECT view_id, view_name, owner_email, is_shared, description,
               definition, updated_at
          FROM csi_saved_view
         WHERE survey_id = :sid AND (owner_email = :email OR is_shared = 1)
         ORDER BY is_shared, view_name
        """,
        {"sid": survey_id, "email": (user_email or "").lower()},
    )


def save_view(survey_id: int, name: str, owner_email: str, definition: dict,
              description: str = "", shared: bool = False) -> None:
    from app.core.database import execute

    execute(
        """
        INSERT INTO csi_saved_view
            (survey_id, view_name, owner_email, is_shared, definition, description)
        VALUES (:sid, :name, :email, :shared, :definition, :description)
        ON DUPLICATE KEY UPDATE
            survey_id = VALUES(survey_id),
            is_shared = VALUES(is_shared),
            definition = VALUES(definition),
            description = VALUES(description)
        """,
        {"sid": survey_id, "name": name.strip()[:160],
         "email": (owner_email or "").lower(), "shared": 1 if shared else 0,
         "definition": _json.dumps(definition), "description": description[:500]},
    )


def delete_view(view_id: int, owner_email: str) -> None:
    from app.core.database import execute

    execute(
        "DELETE FROM csi_saved_view WHERE view_id = :vid AND owner_email = :email",
        {"vid": view_id, "email": (owner_email or "").lower()},
    )


# ═══════════════════════════════════════════════════════════════════════════
# Multi-question report
# ═══════════════════════════════════════════════════════════════════════════
def report(
    survey_id: int,
    question_ids: Sequence[int],
    criteria: tuple = (),
    break_dimension: Optional[str] = None,
) -> dict[str, pd.DataFrame]:
    """Run several questions over one cohort.

    Returns {qcode: tidy frame}. Each question keeps its own base — the whole
    point of reporting them together is comparing findings, not denominators.
    """
    lookup = question_lookup(survey_id).set_index("question_id")
    out: dict[str, pd.DataFrame] = {}
    for qid in question_ids:
        qid = int(qid)
        if qid not in lookup.index:
            continue
        frame = analyse(survey_id, qid, criteria, break_dimension)
        if frame.empty:
            continue
        row = lookup.loc[qid]
        frame = frame.copy()
        frame.insert(0, "qcode", row.qcode)
        frame.insert(1, "question", row.qtext_short)
        out[str(row.qcode)] = frame
    return out
