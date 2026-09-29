"""Read-only query layer. Every page goes through here — no SQL in pages."""
from __future__ import annotations

from typing import Optional, Sequence

import pandas as pd
import streamlit as st

from app.core.database import query_df

TTL = 900  # 15 minutes


@st.cache_data(ttl=TTL, show_spinner=False)
def list_surveys() -> pd.DataFrame:
    return query_df(
        """
        SELECT s.survey_id, s.title, s.survey_family, s.wave_label, s.wave_date,
               h.total_records, h.qualified_n, h.avg_loi_minutes,
               h.first_complete, h.last_complete
          FROM csi_survey s
          LEFT JOIN v_csi_survey_health h ON h.survey_id = s.survey_id
         ORDER BY s.wave_date DESC, s.survey_id DESC
        """
    )


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
    answer options for a single-punch. Used to build filter criteria."""
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
                   COALESCE(o.value_label, a.value_label) AS answer,
                   COALESCE(o.sort_order, a.value_code) AS answer_order,
                   COUNT(*) AS n,
                   0 AS base_n
              FROM csi_respondent r
              LEFT JOIN csi_profile p ON p.respondent_id = r.respondent_id
              JOIN csi_answer a ON a.respondent_id = r.respondent_id
              JOIN csi_field  f ON f.field_id = a.field_id AND f.question_id = :qid
              LEFT JOIN csi_option o ON o.question_id = :qid AND o.value_code = a.value_code
             WHERE r.survey_id = :sid AND r.is_qualified = 1 AND {where}
               AND a.value_code IS NOT NULL
             GROUP BY {seg_group}, COALESCE(o.value_label, a.value_label),
                      COALESCE(o.sort_order, a.value_code)
        """

    df = query_df(sql, params)
    if df.empty:
        return df

    if not is_multi:
        # base for a single-punch is everyone in the segment who answered
        df["base_n"] = df.groupby("segment")["n"].transform("sum")

    df["pct"] = df["n"] / df["base_n"].replace(0, pd.NA)
    df = df.sort_values(["segment", "answer_order"]).reset_index(drop=True)
    return df[["segment", "answer", "n", "base_n", "pct"]]


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
