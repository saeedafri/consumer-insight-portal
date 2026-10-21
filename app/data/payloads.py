"""The portal's payloads, built from the ETL's serving tables (sql/005_serving.sql). Pure: each returns plain data
for one screen request. The API serves them (api/main.py) and the ETL publishes the standard ones as static
files (etl/publish.py), so both always produce the same bytes. A wave or question that does not exist raises
LookupError."""
from __future__ import annotations

import json
from collections import defaultdict
from decimal import Decimal

from sqlalchemy import bindparam, text

from app.core.database import get_engine
from etl.serving import SMALL_BASE

COLUMNS = ("qcode", "dim", "dim_value", "item_label", "option_code", "option_label", "n", "base_n",
           "pct", "prior_pct", "prior_base_n", "ly_pct", "ly_base_n", "flags")
CROSSTAB_COLUMNS = ("v1", "v2", "item_label", "option_code", "option_label", "n", "base_n", "pct", "flags")
BANNER = (("Total", "total", "Total"), ("Male", "gender", "Male"), ("Female", "gender", "Female"),
          ("Gen Z", "generation", "GenZ"), ("Millennial", "generation", "Millennial"), ("Gen X", "generation", "GenX"),
          ("Boomer", "generation", "Boomer"))   # dashboard column, srv_result dim, dim_value
HIDDEN_BASE = 30   # respondents: below this a two-cut cell shows no number at all, only "suppressed"


def encode(data) -> bytes:
    """Compact JSON: decimals as numbers, dates as text."""
    return json.dumps(data, default=lambda v: float(v) if isinstance(v, Decimal) else str(v), separators=(",", ":")).encode()


def results(survey_id: int, qcodes: tuple, dims: tuple) -> dict:
    """One primary-key range read per question on srv_result; the rows are already finished."""
    with get_engine("app").connect() as conn:
        rows = conn.execute(text(
            f"SELECT {', '.join(COLUMNS)} FROM srv_result WHERE survey_id = :s AND qcode IN :q AND dim IN :d"
            " ORDER BY qcode, dim, dim_value, sort_order").bindparams(bindparam("q", expanding=True),
                                                                      bindparam("d", expanding=True)),
            {"s": survey_id, "q": list(qcodes), "d": list(dims)}).all()
    return {"survey_id": survey_id, "columns": COLUMNS, "rows": [list(r) for r in rows]}


def waves(dashboards: dict) -> list[dict]:
    with get_engine("app").connect() as conn:
        rows = conn.execute(text(
            "SELECT w.survey_id, s.title, s.wave_label, w.wave_date, w.survey_family, w.study_type, w.qualified_n,"
            " w.prior_survey_id, w.ly_survey_id, w.ly_status, w.rows_built FROM srv_wave w JOIN cip_survey s ON s.survey_id = w.survey_id"
            " ORDER BY w.wave_date DESC, w.survey_id DESC")).mappings().all()
        modules = defaultdict(list)
        for survey_id, name in conn.execute(text(
                "SELECT survey_id, module_name FROM cip_wave_module WHERE survey_id IS NOT NULL ORDER BY is_lead DESC, module_name")):
            modules[survey_id].append(name)
    return [{**r, "modules": modules.get(r["survey_id"], []), "dashboards": sorted(dashboards.get(r["survey_id"], []))} for r in rows]


def book(survey_id: int) -> dict:
    """Every reportable question of one wave with Total, gender and generation columns, in the shape the
    dashboard was designed on: {n: {column: base}, questions: [{id, text, groups: [{label, base, rows:
    [{label, column: pct}]}]}]}. A grid row is a group; a multi-select item or a single-choice answer is
    a row. Extra fields (type, section, per-column bases, prior week, flags) ride along."""
    columns = {(dim, value): name for name, dim, value in BANNER}
    with get_engine("app").connect() as conn:
        wave = conn.execute(text(
            "SELECT w.survey_id, s.title, s.wave_label, w.wave_date, w.survey_family, w.study_type, w.qualified_n,"
            " w.prior_survey_id, w.ly_survey_id, w.ly_status FROM srv_wave w JOIN cip_survey s ON s.survey_id = w.survey_id"
            " WHERE w.survey_id = :s"), {"s": survey_id}).mappings().first()
        if wave is None:
            raise LookupError("No such wave")
        questions = conn.execute(text(
            "SELECT q.qcode, q.qtext, q.qtext_short, q.qtype, q.base_desc, t.topic_name FROM cip_question q"
            " LEFT JOIN cip_topic t ON t.topic_id = q.topic_id WHERE q.survey_id = :s AND q.is_technical = 0"
            " AND q.is_virtual = 0 ORDER BY q.sort_order, q.question_id"), {"s": survey_id}).mappings().all()
        rows = conn.execute(text(
            "SELECT qcode, dim, dim_value, item_label, option_code, option_label, n, base_n, pct, prior_pct,"
            " prior_base_n, ly_pct, ly_base_n, flags FROM srv_result WHERE survey_id = :s AND dim IN ('total', 'gender', 'generation')"
            " ORDER BY qcode, sort_order"), {"s": survey_id}).mappings().all()
        modules = [r[0] for r in conn.execute(text("SELECT module_name FROM cip_wave_module WHERE survey_id = :s"), {"s": survey_id})]
        people = conn.execute(text(   # qualified respondents per banner column
            "SELECT p.gender, p.generation FROM cip_profile p JOIN cip_respondent r ON r.respondent_id = p.respondent_id"
            " AND r.is_qualified = 1 WHERE p.survey_id = :s"), {"s": survey_id}).all()
    n = {"Total": wave["qualified_n"]} | {name: 0 for name, _, _ in BANNER[1:]}
    for gender, generation in people:
        for dim, value in (("gender", gender), ("generation", generation)):
            if (dim, value) in columns:
                n[columns[(dim, value)]] += 1
    cells: dict = {}
    for r in rows:
        name = columns.get((r["dim"], r["dim_value"]))
        if name is None:
            continue
        cells.setdefault(r["qcode"], []).append((name, r))
    out = []
    for q in questions:
        if q["qcode"] not in cells:
            continue   # numeric and open text have no percentages
        multi = q["qtype"] in ("multi", "grid_multi")
        groups: dict = {}
        for name, r in cells[q["qcode"]]:
            group_label, row_label = ("", r["item_label"]) if multi else (r["item_label"], r["option_label"])
            group = groups.setdefault(group_label, {"label": group_label, "base": 0, "bases": {}, "rows": {}})
            group["bases"][name] = r["base_n"]
            row = group["rows"].setdefault(row_label, {"label": row_label, "code": r["option_code"]})
            row[name] = round(float(r["pct"]), 1)
            if name == "Total":
                group["base"] = r["base_n"]
                row["prior"] = None if r["prior_pct"] is None else round(float(r["prior_pct"]), 1)
                row["prior_base"] = r["prior_base_n"]
                row["ly"] = None if r["ly_pct"] is None else round(float(r["ly_pct"]), 1)
                row["ly_base"] = r["ly_base_n"]
                row["flags"] = r["flags"] or ""
        section = q["topic_name"] if q["topic_name"] not in (None, "Unclassified") else module_section(q["qcode"], modules)
        out.append({"id": q["qcode"], "text": q["qtext"], "short": q["qtext_short"], "type": q["qtype"],
                     "section": section, "base_desc": q["base_desc"],
                     "groups": [{**g, "rows": list(g["rows"].values())} for g in groups.values()]})
    return {"wave": dict(wave), "columns": [name for name, _, _ in BANNER], "n": n, "questions": out}


def _trend(qcode: str, dim: str, value: str, waves: list[dict], rows: list) -> dict:
    """One trend from a family's waves and the question's rows for one cut value: answers matched across waves by
    label and code (as srv_result's comparisons are), the latest wave's wording first."""
    asked = {r["survey_id"] for r in rows}
    waves = [dict(w) for w in waves if w["survey_id"] in asked]
    at = {w["survey_id"]: i for i, w in enumerate(waves)}
    series: dict = {}
    for r in sorted(rows, key=lambda r: -at[r["survey_id"]]):
        s = series.setdefault((r["item_label"], r["option_code"]), {
            "item_label": r["item_label"], "code": r["option_code"], "label": r["option_label"] or r["item_label"],
            "sort": r["sort_order"], "pct": [None] * len(waves), "base": [None] * len(waves)})
        s["pct"][at[r["survey_id"]]] = round(float(r["pct"]), 1)
        s["base"][at[r["survey_id"]]] = r["base_n"]
    return {"qcode": qcode, "dim": dim, "value": value, "waves": waves, "series": sorted(series.values(), key=lambda s: s["sort"])}


def _family(conn, family: str, study_type: str) -> list[dict]:
    return [dict(w) for w in conn.execute(text(
        "SELECT survey_id, wave_date FROM srv_wave WHERE survey_family = :f AND study_type = :t ORDER BY wave_date, survey_id"),
        {"f": family, "t": study_type}).mappings()]


TREND_COLUMNS = [(dim, value) for _, dim, value in BANNER]   # the trends the ETL publishes (etl/publish.py)
_TREND_ROWS = ("SELECT survey_id, dim, dim_value, item_label, option_code, option_label, sort_order, base_n, pct"
               " FROM srv_result WHERE survey_id IN :ids AND qcode = :q AND dim IN :d")


def family_trend(family: str, study_type: str, qcode: str, dim: str, value: str) -> dict:
    """The question's answers (Total, or one cut value) in every built wave of one family and study type, oldest
    first. Empty when nobody in that group answered."""
    with get_engine("app").connect() as conn:
        waves = _family(conn, family, study_type)
        rows = conn.execute(text(_TREND_ROWS + " AND dim_value = :v").bindparams(bindparam("ids", expanding=True), bindparam("d", expanding=True)),
                            {"ids": [w["survey_id"] for w in waves] or [-1], "q": qcode, "d": [dim], "v": value}).mappings().all()
    return _trend(qcode, dim, value, waves, rows)


def family_trends(family: str, study_type: str, qcode: str) -> dict:
    """Every banner column's trend for one question in one query: {(dim, value): trend} (for publishing)."""
    with get_engine("app").connect() as conn:
        waves = _family(conn, family, study_type)
        rows = conn.execute(text(_TREND_ROWS).bindparams(bindparam("ids", expanding=True), bindparam("d", expanding=True)),
                            {"ids": [w["survey_id"] for w in waves] or [-1], "q": qcode, "d": sorted({d for d, _ in TREND_COLUMNS})}).mappings().all()
    by: dict = {}
    for r in rows:
        by.setdefault((r["dim"], r["dim_value"]), []).append(r)
    return {(d, v): _trend(qcode, d, v, waves, by[(d, v)]) for d, v in TREND_COLUMNS if (d, v) in by}


def trend(survey_id: int, qcode: str, dim: str, value: str) -> dict:
    """family_trend for the wave's family; LookupError if the wave did not ask the question."""
    with get_engine("app").connect() as conn:
        wave = conn.execute(text("SELECT survey_family, study_type FROM srv_wave WHERE survey_id = :s"), {"s": survey_id}).first()
        asked = wave and conn.execute(text("SELECT 1 FROM srv_result WHERE survey_id = :s AND qcode = :q LIMIT 1"),
                                      {"s": survey_id, "q": qcode}).first()
    if not asked:
        raise LookupError("That question is not in that wave")
    return family_trend(wave[0], wave[1], qcode, dim, value)


def module_section(qcode: str, modules: list[str]) -> str:
    """A section for a question the topic map has not classified: the wave module whose initials begin with
    the code's letters (HI → "Home improvement / DIY", BD → "Big Deal Days Retro"), else "<letters> block"."""
    letters = "".join(ch for ch in qcode.split("_")[0] if ch.isalpha()).upper()
    for name in modules:
        initials = "".join(w[0] for w in name.replace("/", " ").split() if w[0].isalpha()).upper()
        if letters and initials.startswith(letters):
            return name
    return f"{letters} block"


def pool(conn, survey_id: int, weeks: int) -> list[dict]:
    """The wave and up to weeks - 1 earlier ones, following the same prior-week chain as srv_result."""
    family = {r["survey_id"]: r for r in conn.execute(text(   # one round trip: the family's latest waves up to this one
        "SELECT w.survey_id, w.wave_date, w.prior_survey_id FROM srv_wave w JOIN srv_wave me ON me.survey_id = :s"
        " AND w.survey_family = me.survey_family AND w.wave_date <= me.wave_date ORDER BY w.wave_date DESC LIMIT 20"),
        {"s": survey_id}).mappings()}
    waves = []
    while survey_id in family and len(waves) < weeks:
        waves.append(family[survey_id])
        survey_id = family[survey_id]["prior_survey_id"]
    return waves


def crosstab(survey_id: int, qcode: str, by: tuple, weeks: int) -> dict:
    """Counts by two cuts from srv_answer, pooled across waves on the answer's label and code (ids differ
    per wave, as in srv_result's comparisons), then bases, percentages and flags. Respondents with no
    value for a cut are left out, as in srv_result. Cells nobody chose come back as n = 0."""
    first, second = by
    with get_engine("app").connect() as conn:
        waves = pool(conn, survey_id, weeks)
        ids = [w["survey_id"] for w in waves] or [-1]
        counts = conn.execute(text(
            f"SELECT survey_id, item_id, option_id, {first}, {second}, COUNT(*) FROM srv_answer"
            f" WHERE survey_id IN :ids AND qcode = :q GROUP BY survey_id, item_id, option_id, {first}, {second}")
            .bindparams(bindparam("ids", expanding=True)), {"ids": ids, "q": qcode}).all()
        answers = conn.execute(text(
            "SELECT survey_id, item_id, option_id, item_label, option_code, option_label, sort_order, flags"
            " FROM srv_result WHERE survey_id IN :ids AND qcode = :q AND dim = 'total'")
            .bindparams(bindparam("ids", expanding=True)), {"ids": ids, "q": qcode}).mappings().all()
    if not any(a["survey_id"] == survey_id for a in answers):
        raise LookupError("That question is not in that wave")
    label = {(a["survey_id"], a["item_id"], a["option_id"]): a for a in answers}
    order = {}   # answer → (sort order, label), the requested wave's wording first
    for a in sorted(answers, key=lambda a: a["survey_id"] != survey_id):
        order.setdefault((a["item_label"], a["option_code"]), (a["sort_order"], a["option_label"]))
    n, base = defaultdict(int), defaultdict(int)
    for sid, item, option, v1, v2, count in counts:
        if "" in (v1, v2):
            continue
        if item == 0 and option == 0:            # multi base row: answered the question
            base[(v1, v2, None)] += count
            continue
        a = label.get((sid, item, option))
        if a is None:
            continue
        n[(v1, v2, a["item_label"], a["option_code"])] += count
        if option:                               # single choice: base = answered this row
            base[(v1, v2, a["item_label"])] += count
    multi = all(a["option_id"] == 0 for a in answers)
    cells = sorted({(v1, v2) for v1, v2, _ in base})
    rows = []
    for v1, v2 in cells:
        for (item_label, code), (_, option_label) in sorted(order.items(), key=lambda kv: kv[1][0]):
            b = base.get((v1, v2, None if multi else item_label), 0)
            if not b:
                continue
            count = n.get((v1, v2, item_label, code), 0)
            if b < HIDDEN_BASE:
                rows.append([v1, v2, item_label, code, option_label, None, b, None, "suppressed"])
            else:
                rows.append([v1, v2, item_label, code, option_label, count, b, round(100 * count / b, 3),
                             "small_base" if b < SMALL_BASE else ""])
    asked = {a["survey_id"] for a in answers}
    waves = [w for w in waves if w["survey_id"] in asked]
    # a wave whose question base moved against its prior week, when both are in the pool, mixes populations
    inside = {w["survey_id"] for w in waves if w["prior_survey_id"] in asked}
    warnings = ["base_changed_within_pool"] if any(
        "base_changed_prior" in (a["flags"] or "") and a["survey_id"] in inside for a in answers) else []
    return {"survey_id": survey_id, "qcode": qcode, "by": list(by), "weeks": len(waves),
                  "waves": [{"survey_id": w["survey_id"], "wave_date": w["wave_date"]} for w in waves],
                  "warnings": warnings, "columns": CROSSTAB_COLUMNS, "rows": rows}
