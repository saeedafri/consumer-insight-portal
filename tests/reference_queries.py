"""Independent ways to read the test database, for checking what the ETL loaded and what the cube counts.

These are the queries of the portal's first version (its Streamlit pages). Production no longer uses them: the API
reads published files and the serving tables. The tests keep them because each one counts straight from the raw
tables, so it is a second, independent answer to compare the ETL's own results with (e.g. analyse vs analyse_cube:
raw responses vs the cube the ETL built).
"""
from __future__ import annotations

import re
from typing import Optional

import pandas as pd

from app.core.database import dialect, query_df

INNODB_STOPWORDS = set("a about an are as at be by com de en for from how i in is it la of on or that the this to"
                       " was what when where who will with und www".split())
_SEARCH_COLUMNS = """
    SELECT x.kind, x.survey_id, x.question_id, x.concept_id, x.wave_label, x.waves, x.title, x.body
      FROM cip_search x LEFT JOIN cip_survey s ON s.survey_id = x.survey_id
     WHERE (x.survey_id IS NULL OR s.load_status = 'verified')"""
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
GRID_KEY = 1000


def list_surveys() -> pd.DataFrame:
    # A wave mid-load has definitions but no respondents yet: counts are 0, not NaN.
    return query_df(
        """
        SELECT s.survey_id, s.title, s.survey_family, s.wave_label, s.wave_date,
               h.total_records, h.qualified_n, h.avg_loi_minutes,
               h.first_complete, h.last_complete
          FROM cip_survey s
          LEFT JOIN v_cip_survey_health h ON h.survey_id = s.survey_id
         WHERE s.load_status = 'verified'          -- a wave mid-load or failed is not shown
         ORDER BY s.wave_date DESC, s.survey_id DESC
        """
    ).fillna({"total_records": 0, "qualified_n": 0})


def mapping_queue() -> pd.DataFrame:
    """Harmoniser proposals waiting for an analyst (short TTL: decisions clear it)."""
    return query_df("SELECT * FROM v_cip_mapping_queue ORDER BY wave_label, qcode, item_id")


def concept_list(qtype: str, survey_id: Optional[int] = None) -> pd.DataFrame:
    """Concepts a unit of this type could map to — minus those another
    question of the same wave already uses (one wave, one question per concept)."""
    return query_df(
        """
        SELECT c.concept_id, c.concept_code, c.concept_name FROM cip_concept c
         WHERE c.qtype = :qtype
           AND NOT EXISTS (SELECT 1 FROM cip_concept_map m
                            WHERE m.concept_id = c.concept_id AND m.survey_id = :sid
                              AND m.concept_option_id IS NULL AND m.status <> 'rejected')
         ORDER BY c.concept_code
        """, {"qtype": qtype, "sid": -1 if survey_id is None else survey_id})


def question_catalog(survey_id: int) -> pd.DataFrame:
    return query_df(
        """
        SELECT q.question_id, q.qcode, q.qtext, q.qtext_short, q.qtype,
               q.is_multi, q.base_n, q.base_desc,
               g.topic_code, g.topic_name, g.sort_order AS group_order,
               q.sort_order
          FROM cip_question q
          LEFT JOIN cip_topic g ON g.topic_id = q.topic_id
         WHERE q.survey_id = :sid AND q.is_technical = 0 AND q.is_virtual = 0
         ORDER BY g.sort_order, q.sort_order
        """,
        {"sid": survey_id},
    )


def search(words: str, limit: int = 40) -> pd.DataFrame:
    """Waves, questions and concepts matching every word — one FULLTEXT read
    on MySQL; LIKE where FULLTEXT is missing (SQLite) or the words are shorter
    than InnoDB indexes (3 characters: a code such as "D5")."""
    terms = re.findall(r"\w+", words or "")
    if len("".join(terms)) < 2:
        return pd.DataFrame(columns=["kind", "survey_id", "question_id", "concept_id", "wave_label", "waves", "title", "body"])
    required = [t for t in terms if t.lower() not in INNODB_STOPWORDS]
    if dialect("app") == "mysql" and required and all(len(t) >= 3 for t in required):
        return query_df(_SEARCH_COLUMNS + " AND MATCH(x.title, x.body) AGAINST (:q IN BOOLEAN MODE)"
                        " ORDER BY MATCH(x.title, x.body) AGAINST (:q IN BOOLEAN MODE) DESC, x.wave_label DESC"
                        f" LIMIT {int(limit)}", {"q": " ".join(f"+{t}*" for t in required)})
    like = " AND ".join(f"CONCAT(x.title, ' ', COALESCE(x.body, '')) LIKE :t{i}" for i in range(len(terms)))
    return query_df(_SEARCH_COLUMNS + f" AND {like} ORDER BY x.wave_label DESC LIMIT {int(limit)}",
                    {f"t{i}": f"%{t}%" for i, t in enumerate(terms)})


def wave_report(survey_id: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Everything the survey report charts, in three reads: the cube's total
    cells (single, grid, multi), the numeric answers and the verbatims —
    qualified respondents only, technical and virtual questions left out."""
    cells = query_df(
        """
        SELECT c.question_id, c.n, c.base_n, i.item_label, i.left_label, i.right_label,
               COALESCE(i.sort_order, 0) AS item_order, o.value_label, COALESCE(o.sort_order, 0) AS option_order
          FROM cip_agg_cell c
          JOIN cip_question q ON q.question_id = c.question_id AND q.is_virtual = 0
          LEFT JOIN cip_item i ON i.item_id = c.item_id
          LEFT JOIN cip_option o ON o.option_id = c.option_id
         WHERE c.survey_id = :sid AND c.dim = 'total' AND c.cohort_id IS NULL
        """, {"sid": survey_id})
    cells["pct"] = cells["n"] / cells["base_n"].where(cells["base_n"] > 0)
    answers = """
        SELECT f.question_id, a.{column} AS value
          FROM cip_answer a
          JOIN cip_field f ON f.field_id = a.field_id
          JOIN cip_question q ON q.question_id = f.question_id AND q.qtype = :qtype
               AND q.is_technical = 0 AND q.is_virtual = 0
          JOIN cip_respondent r ON r.respondent_id = a.respondent_id AND r.is_qualified = 1
         WHERE a.survey_id = :sid AND a.{column} IS NOT NULL"""
    numbers = query_df(answers.format(column="value_number"), {"sid": survey_id, "qtype": "numeric"})
    texts = query_df(answers.format(column="value_text"), {"sid": survey_id, "qtype": "text"})
    return cells, numbers, texts


def trend(survey_family: str, qcode: str) -> pd.DataFrame:
    return query_df(
        """
        SELECT wave_label, wave_date, item_label, pct, base_n
          FROM v_cip_trend
         WHERE survey_family = :fam AND qcode = :qcode
         ORDER BY wave_date, item_label
        """,
        {"fam": survey_family, "qcode": qcode},
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
                f"""EXISTS (SELECT 1 FROM cip_answer a{n}
                              JOIN cip_field f{n} ON f{n}.field_id = a{n}.field_id
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
                f"""EXISTS (SELECT 1 FROM cip_answer a{n}
                              JOIN cip_field f{n} ON f{n}.field_id = a{n}.field_id
                             WHERE a{n}.respondent_id = r.respondent_id
                               AND f{n}.question_id = :cq{n}
                               AND a{n}.value_code IN ({placeholders}))"""
            )
        elif kind == "cohort":
            # by code, so a saved view follows the cohort to its current version
            if crit.get("cohort_code"):
                params[f"ck{n}"] = str(crit["cohort_code"])
                clauses.append(
                    f"""EXISTS (SELECT 1 FROM cip_respondent_cohort rc{n}
                                  JOIN cip_cohort_def d{n} ON d{n}.cohort_id = rc{n}.cohort_id
                                   AND d{n}.is_current = 1 AND d{n}.cohort_code = :ck{n}
                                 WHERE rc{n}.respondent_id = r.respondent_id)"""
                )
            elif crit.get("cohort_id"):
                params[f"ck{n}"] = int(crit["cohort_id"])
                clauses.append(
                    f"""EXISTS (SELECT 1 FROM cip_respondent_cohort rc{n}
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
                f"""EXISTS (SELECT 1 FROM cip_answer a{n}
                              JOIN cip_field f{n} ON f{n}.field_id = a{n}.field_id
                             WHERE a{n}.respondent_id = r.respondent_id
                               AND ({" OR ".join(ors)}))"""
            )
    return (" AND ".join(clauses) if clauses else "1=1"), params


def cohort_size(survey_id: int, criteria: tuple) -> int:
    where, params = _cohort_sql(list(criteria))
    params["sid"] = survey_id
    df = query_df(
        f"""
        SELECT COUNT(*) AS n
          FROM cip_respondent r
          LEFT JOIN cip_profile p ON p.respondent_id = r.respondent_id
         WHERE r.survey_id = :sid AND r.is_qualified = 1 AND {where}
        """,
        params,
    )
    return int(df["n"].iloc[0]) if not df.empty else 0


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
    from etl.cube import CUBE_DIMS
    kinds = [c.get("kind") for c in criteria]
    if kinds in ([], ["cohort"]) and (break_dimension or "total") in CUBE_DIMS:
        cohort_id = None
        if criteria:
            from etl.cohorts import current_id
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
        "SELECT qtype, is_multi FROM cip_question WHERE question_id = :qid",
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
              FROM cip_respondent r
              LEFT JOIN cip_profile p ON p.respondent_id = r.respondent_id
              JOIN cip_answer a ON a.respondent_id = r.respondent_id
              JOIN cip_field  f ON f.field_id = a.field_id AND f.question_id = :qid
              JOIN cip_item   i ON i.item_id = f.item_id
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
              FROM cip_respondent r
              LEFT JOIN cip_profile p ON p.respondent_id = r.respondent_id
              JOIN cip_answer a ON a.respondent_id = r.respondent_id
              JOIN cip_field  f ON f.field_id = a.field_id AND f.question_id = :qid
              LEFT JOIN cip_item i ON i.item_id = f.item_id
              LEFT JOIN cip_option o ON o.question_id = :qid AND o.value_code = a.value_code
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
              FROM cip_respondent r
              LEFT JOIN cip_profile p ON p.respondent_id = r.respondent_id
              JOIN cip_answer a ON a.respondent_id = r.respondent_id
              JOIN cip_field  f ON f.field_id = a.field_id AND f.question_id = :qid
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
          FROM cip_agg_cell c
          JOIN cip_question q ON q.question_id = c.question_id
          LEFT JOIN cip_item i ON i.item_id = c.item_id
          LEFT JOIN cip_option o ON o.option_id = c.option_id
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


def question_lookup(survey_id: int) -> pd.DataFrame:
    """Every reportable question with the label the pickers show."""
    return query_df(
        """
        SELECT q.question_id, q.qcode, q.qtext, q.qtext_short, q.qtype,
               q.is_multi, q.base_n, t.topic_name
          FROM cip_question q
          LEFT JOIN cip_topic t ON t.topic_id = q.topic_id
         WHERE q.survey_id = :sid AND q.is_technical = 0
           AND q.qtype IN ('single', 'multi', 'grid_single', 'grid_multi')
         ORDER BY t.sort_order, q.sort_order
        """,
        {"sid": survey_id},
    )
