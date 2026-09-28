"""Read-only query layer. Every page goes through here — no SQL in pages."""
from __future__ import annotations

from typing import Optional

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
        SELECT value_code, value_label, n, pct, base_n, is_nonresponse
          FROM v_csi_single_distribution
         WHERE survey_id = :sid AND question_id = :qid
         ORDER BY value_code
        """,
        {"sid": survey_id, "qid": question_id},
    )


@st.cache_data(ttl=TTL, show_spinner=False)
def crosstab(survey_id: int, qcode: str, banner_name: Optional[str] = None) -> pd.DataFrame:
    sql = """
        SELECT stub_label, stub_type, banner_name, seg_letter, seg_label,
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
               COUNT(*) / SUM(COUNT(*)) OVER () AS pct
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
