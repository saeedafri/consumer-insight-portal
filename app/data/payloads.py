"""The portal's payloads, built from the ETL's serving tables (sql/005_serving.sql). Pure: each returns plain data
for one screen request. The API serves them (api/main.py) and the ETL publishes the standard ones as static
files (etl/publish.py), so both always produce the same bytes. A wave or question that does not exist raises
LookupError."""
from __future__ import annotations

import json
from collections import defaultdict
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

import yaml

from sqlalchemy import bindparam, text

from app.core import access
from app.core.database import get_engine
from app.data.harmonise import normalise_text
from etl import open_ends, survey_calendar, weighting
from etl.serving import CUTS, SMALL_BASE, TEST_BASE   # TEST_BASE: one significance rule (etl/serving.py)

COLUMNS = ("qcode", "dim", "dim_value", "item_label", "option_code", "option_label", "n", "base_n",
           "pct", "prior_pct", "prior_base_n", "ly_pct", "ly_base_n", "flags")
CROSSTAB_COLUMNS = ("v1", "v2", "item_label", "option_code", "option_label", "n", "base_n", "pct", "flags")
BANNER = (("Total", "total", "Total"), ("Male", "gender", "Male"), ("Female", "gender", "Female"),
          ("Gen Z", "generation", "GenZ"), ("Millennial", "generation", "Millennial"), ("Gen X", "generation", "GenX"),
          ("Boomer", "generation", "Boomer"))   # dashboard column, srv_result dim, dim_value
HIDDEN_BASE = 1    # respondents: every figure is shown, however few answered (the user's rule, 23 Oct 2026); only a group of 0 has none
COUNTRIES = Path(__file__).resolve().parents[2] / "config" / "countries.yml"
METHODOLOGY = Path(__file__).resolve().parents[2] / "config" / "methodology.yml"
# Where a wave came from, for every screen's source line and export: platform, fielding window, source reference
SOURCE = "s.country, s.platform, s.source_ref, s.field_start, s.field_end, s.load_status"


@lru_cache(maxsize=1)
def countries() -> dict:
    return yaml.safe_load(COUNTRIES.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def populations() -> dict:
    return yaml.safe_load(METHODOLOGY.read_text(encoding="utf-8"))["population"]


def describe(wave: dict) -> dict:
    """The wave with its provenance, for every screen's source line and export: population (config/methodology.yml),
    weighting, in_field (still collecting answers), verified (its load was checked against Forsta; srv_wave holds
    only verified waves, so a file without load_status is verified), client (who commissioned it, or None) and
    visibility (config/access.yml). Needs survey_id, survey_family and study_type."""
    found = populations()
    population = (found.get("ids") or {}).get(wave["survey_id"]) or (found.get("families") or {}).get(wave.get("survey_family")) \
        or (found.get("study_types") or {}).get(wave.get("study_type")) or found["default"]
    return {**wave, "population": population, "weighting": "unweighted", "in_field": bool(wave.get("in_field")),
            "verified": wave.get("load_status", "verified") == "verified", **access.owner(wave)}


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
    def masked(r):   # under HIDDEN_BASE only the base goes out, like every other screen and file
        r = dict(zip(COLUMNS, r))
        if (r["base_n"] or 0) < HIDDEN_BASE:
            r["n"] = r["pct"] = None
        for pct, base in (("prior_pct", "prior_base_n"), ("ly_pct", "ly_base_n")):
            if (r[base] or 0) < HIDDEN_BASE:
                r[pct] = None
        return list(r.values())
    return {"survey_id": survey_id, "columns": COLUMNS, "rows": [masked(r) for r in rows]}


WAVE = ("survey_id", "title", "wave_label", "wave_date", "survey_family", "study_type", "qualified_n", "prior_survey_id",
        "ly_survey_id", "ly_status")


def waves(dashboards: dict) -> list[dict]:
    with get_engine("app").connect() as conn:   # w.*: in_field once the ETL has added it (sql/005_serving.sql)
        rows = [{k: r[k] for k in (*WAVE, "rows_built", "country", "platform", "source_ref", "field_start", "field_end", "load_status")}
                | {"in_field": r.get("in_field")} for r in conn.execute(text(
            f"SELECT w.*, s.title, s.wave_label, {SOURCE} FROM srv_wave w"
            " JOIN cip_survey s ON s.survey_id = w.survey_id ORDER BY w.wave_date DESC, w.survey_id DESC")).mappings()]
        modules = defaultdict(list)
        for survey_id, name in conn.execute(text(
                "SELECT survey_id, module_name FROM cip_wave_module WHERE survey_id IS NOT NULL ORDER BY is_lead DESC, module_name")):
            modules[survey_id].append(name)
    return [describe({**r, "modules": modules.get(r["survey_id"], []), "events": survey_calendar.events(r["title"]),
                      "dashboards": sorted(dashboards.get(r["survey_id"], []))}) for r in rows]


def book(survey_id: int) -> dict:
    """Every reportable question of one wave with Total, gender and generation columns, in the shape the
    dashboard was designed on: {n: {column: base}, questions: [{id, text, groups: [{label, base, rows:
    [{label, column: pct}]}]}]}. A grid row is a group; a multi-select item or a single-choice answer is
    a row. Extra fields (type, section, per-column bases, prior week, flags) ride along."""
    columns = {(dim, value): name for name, dim, value in BANNER}
    with get_engine("app").connect() as conn:
        wave = conn.execute(text(
            f"SELECT w.*, s.title, s.wave_label, {SOURCE} FROM srv_wave w JOIN cip_survey s ON s.survey_id = w.survey_id"
            " WHERE w.survey_id = :s"), {"s": survey_id}).mappings().first()
        if wave is None:
            raise LookupError("No such wave")
        wave = describe({k: wave[k] for k in (*WAVE, "country", "platform", "source_ref", "field_start", "field_end", "load_status")}
                        | {"in_field": wave.get("in_field")})
        questions = conn.execute(text(
            "SELECT q.qcode, q.qtext, q.qtext_short, q.qtype, q.base_desc, t.topic_name FROM cip_question q"
            " LEFT JOIN cip_topic t ON t.topic_id = q.topic_id WHERE q.survey_id = :s AND q.is_technical = 0"
            " AND q.is_virtual = 0 ORDER BY q.sort_order, q.question_id"), {"s": survey_id}).mappings().all()
        rows = conn.execute(text(
            "SELECT qcode, dim, dim_value, item_id, option_id, item_label, option_code, option_label, n, base_n, pct, prior_pct,"
            " prior_base_n, ly_pct, ly_base_n, flags FROM srv_result WHERE survey_id = :s AND dim IN ('total', 'gender', 'generation')"
            " ORDER BY qcode, sort_order"), {"s": survey_id}).mappings().all()
        modules = [r[0] for r in conn.execute(text("SELECT module_name FROM cip_wave_module WHERE survey_id = :s"), {"s": survey_id})]
        people = conn.execute(text(   # qualified respondents per banner column
            "SELECT p.gender, p.generation, p.respondent_id FROM cip_profile p JOIN cip_respondent r ON r.respondent_id = p.respondent_id"
            " AND r.is_qualified = 1 WHERE p.survey_id = :s"), {"s": survey_id}).all()
        mine = weighted(conn, survey_id, columns)
        then = {key: weighted(conn, wave[key], {("total", "Total"): "Total"}, by_label=True)
                for key in ("prior_survey_id", "ly_survey_id") if mine and wave.get(key)}
    n = {"Total": wave["qualified_n"]} | {name: 0 for name, _, _ in BANNER[1:]}
    for gender, generation, _ in people:
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
    themes = open_ends.coded(survey_id)
    groups_of = {rid: [columns[k] for k in (("gender", g), ("generation", gen)) if k in columns] for g, gen, rid in people}
    for q in questions:
        if q["qcode"] in themes:   # open-ended: the share of those who wrote something, by theme (etl/open_ends.py)
            section = q["topic_name"] if q["topic_name"] not in (None, "Unclassified") else module_section(q["qcode"], modules)
            out.append({"id": q["qcode"], "text": q["qtext"], "short": q["qtext_short"], "type": "single", "section": section,
                        "base_desc": "Open-ended answers, coded into themes", "coded": themes[q["qcode"]]["method"],
                        "groups": [open_group(themes[q["qcode"]], groups_of)]})
            continue
        if q["qcode"] not in cells:
            continue   # numeric answers have no percentages
        multi = q["qtype"] in ("multi", "grid_multi")
        groups: dict = {}
        for name, r in cells[q["qcode"]]:
            group_label, row_label = ("", r["item_label"]) if multi else (r["item_label"], r["option_label"])
            group = groups.setdefault(group_label, {"label": group_label, "base": 0, "bases": {}, "rows": {}})
            group["bases"][name] = r["base_n"]
            row = group["rows"].setdefault(row_label, {"label": row_label, "code": r["option_code"]})
            shown = lambda pct, base: None if pct is None or (base or 0) < HIDDEN_BASE else round(float(pct), 1)   # noqa: E731
            row[name] = shown(r["pct"], r["base_n"])
            if mine:   # Census-weighted: the same answer, each person counted by their weight (etl/weighting.py)
                row.setdefault("w", {})[name] = mine.get((r["qcode"], r["item_id"], r["option_id"]), {}).get(name, 0.0)
            if mine and name == "Total":
                label = (r["qcode"], normalise_text(r["item_label"]), r["option_code"])
                for key, field in (("prior_survey_id", "prior"), ("ly_survey_id", "ly")):
                    found = then.get(key, {}).get(label, {}).get("Total")
                    row["w"][field] = round(found, 1) if found is not None and r[f"{field}_pct"] is not None else None
            if name == "Total":
                group["base"] = r["base_n"]
                row["prior"] = shown(r["prior_pct"], r["prior_base_n"])
                row["prior_base"] = r["prior_base_n"]
                row["ly"] = shown(r["ly_pct"], r["ly_base_n"])
                row["ly_base"] = r["ly_base_n"]
                row["flags"] = r["flags"] or ""
        for g in groups.values():   # the cube keeps no cell for an answer nobody gave: a group that was asked shows 0 %
            for row in g["rows"].values():
                for name, base in g["bases"].items():
                    if base and name not in row:
                        row[name] = 0.0
                    if base and "w" in row:
                        row["w"].setdefault(name, 0.0)
                row.setdefault("flags", "")
        section = q["topic_name"] if q["topic_name"] not in (None, "Unclassified") else module_section(q["qcode"], modules)
        out.append({"id": q["qcode"], "text": q["qtext"], "short": q["qtext_short"], "type": q["qtype"],
                     "section": section, "base_desc": q["base_desc"],
                     "groups": [{**g, "rows": list(g["rows"].values())} for g in groups.values()]})
    if mine:
        wave = {**wave, "weighting_available": "Census (gender, age, region)"}
    return {"wave": wave, "columns": [name for name, _, _ in BANNER], "n": n, "questions": out}


def open_group(coded: dict, groups_of: dict) -> dict:
    """One chart group from an open-ended question's coding: each theme's share of those who wrote an answer."""
    bases, counts = defaultdict(int), defaultdict(int)
    for rid, theme in coded["codes"].items():
        for name in ["Total", *groups_of.get(int(rid), [])]:
            bases[name] += 1
            counts[(theme, name)] += 1
    rows = [{"label": label, "code": i + 1, "prior": None, "prior_base": None, "ly": None, "ly_base": None, "flags": "",
             **{name: round(100 * counts[(i, name)] / b, 1) for name, b in bases.items()}}
            for i, label in enumerate(coded["themes"])]
    rows.sort(key=lambda r: -r["Total"] if r["label"] not in (open_ends.NOTHING, open_ends.OTHER) else 1)
    return {"label": "", "base": bases["Total"], "bases": dict(bases), "rows": rows}


def weighted(conn, survey_id: int, columns: dict, by_label: bool = False) -> dict:
    """The wave's Census-weighted percentages from its respondent answers (srv_answer): {(qcode, item_id, option_id):
    {column: pct}}, or keyed (qcode, item label, option code) to match another wave's rows. Empty when the wave has
    no profile to weight on (every weight 1)."""
    weights = weighting.wave_weights(conn, survey_id)
    if all(abs(w - 1) < 1e-9 for w in weights.values()):
        return {}
    dims = sorted({dim for dim, _ in columns if dim != "total"})
    rows = conn.execute(text(f"SELECT qcode, item_id, option_id, respondent_id{''.join(', ' + d for d in dims)}"
                             " FROM srv_answer WHERE survey_id = :s"), {"s": survey_id}).all()
    n, base = defaultdict(float), defaultdict(float)
    for qcode, item, option, rid, *values in rows:
        w = weights.get(rid, 0.0)
        names = ["Total"] + [columns[(d, v)] for d, v in zip(dims, values) if (d, v) in columns]
        for name in names:
            if item == 0 and option == 0:   # multi base row: answered the question
                base[(qcode, None, name)] += w
            elif option:                    # single choice: base = answered this row
                base[(qcode, item, name)] += w
                n[(qcode, item, option, name)] += w
            else:                           # a multi item chosen
                n[(qcode, item, 0, name)] += w
    out: dict = defaultdict(dict)
    for (qcode, item, option, name), count in n.items():
        b = base.get((qcode, None if option == 0 else item, name))
        if b:
            out[(qcode, item, option)][name] = round(100 * count / b, 1)
    if not by_label:
        return dict(out)
    labels = conn.execute(text("SELECT qcode, item_id, option_id, item_label, option_code FROM srv_result"
                               " WHERE survey_id = :s AND dim = 'total'"), {"s": survey_id}).all()
    return {(q, normalise_text(label), code): out[(q, i, o)] for q, i, o, label, code in labels if (q, i, o) in out}


def versions(rows) -> dict[int, int]:
    """Which waves asked the same question under one code: {survey_id: group}. Waves join
    a group on the same wording or a shared harmonised answer (etl/serving.same_question). A code reused for a new topic starts a new version, so a trend or comparison never joins the two."""
    texts, concepts = {}, defaultdict(set)
    for r in rows:
        texts[r["survey_id"]] = r["qtext"] or ""
        if r["concept_option_id"]:
            concepts[r["concept_option_id"]].add(r["survey_id"])
    parent = {sid: sid for sid in texts}
    def root(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    def join(group):
        group = [root(g) for g in group]
        for g in group[1:]:
            parent[g] = group[0]
    by_text = defaultdict(list)
    for sid, t in texts.items():
        by_text[normalise_text(t)].append(sid)
    for group in [*by_text.values(), *map(list, concepts.values())]:
        join(group)
    return {sid: root(sid) for sid in texts}


def _trend(qcode: str, dim: str, value: str, waves: list[dict], rows: list, version: dict | None = None) -> dict:
    """One trend from a family's waves and the question's rows for one cut value: answers matched across waves by
    label and code, the latest wave's wording first. Each wave carries its question version (versions()); screens
    draw one version at a time."""
    asked = {r["survey_id"] for r in rows}
    waves = [dict(w) for w in waves if w["survey_id"] in asked]
    version = version if version is not None else versions(rows)
    number: dict = {}
    wording = {r["survey_id"]: r["qtext"] for r in rows}
    texts: dict = {}
    for w in waves:                  # oldest first: version 1 is the first wording
        w["version"] = number.setdefault(version.get(w["survey_id"]), len(number) + 1)
        texts[w["version"]] = wording.get(w["survey_id"]) or texts.get(w["version"])   # the version's latest wording
    at = {w["survey_id"]: i for i, w in enumerate(waves)}
    series: dict = {}
    for r in sorted(rows, key=lambda r: -at[r["survey_id"]]):
        s = series.setdefault((r["item_label"], r["option_code"]), {
            "item_label": r["item_label"], "code": r["option_code"], "label": r["option_label"] or r["item_label"],
            "sort": r["sort_order"], "pct": [None] * len(waves), "base": [None] * len(waves)})
        s["pct"][at[r["survey_id"]]] = None if (r["base_n"] or 0) < HIDDEN_BASE else round(float(r["pct"]), 1)
        s["base"][at[r["survey_id"]]] = r["base_n"]
    return {"qcode": qcode, "dim": dim, "value": value, "waves": waves, "versions": [texts[v] for v in sorted(texts)],
            "series": sorted(series.values(), key=lambda s: s["sort"])}


def _family(conn, family: str, study_type: str) -> list[dict]:
    return [dict(w) for w in conn.execute(text(
        "SELECT survey_id, wave_date FROM srv_wave WHERE survey_family = :f AND study_type = :t ORDER BY wave_date, survey_id"),
        {"f": family, "t": study_type}).mappings()]


TREND_COLUMNS = [(dim, value) for _, dim, value in BANNER]   # the trends the ETL publishes (etl/publish.py)
_TREND_ROWS = ("SELECT survey_id, dim, dim_value, item_label, option_code, option_label, sort_order, base_n, pct, concept_option_id"
               " FROM srv_result WHERE survey_id IN :ids AND qcode = :q AND dim IN :d")


def worded(conn, rows, qcode: str) -> list[dict]:
    """rows with each wave's question wording added (read once per wave, not once per row)."""
    ids = sorted({r["survey_id"] for r in rows})
    texts = dict(conn.execute(text("SELECT survey_id, qtext FROM cip_question WHERE survey_id IN :ids AND qcode = :q")
                              .bindparams(bindparam("ids", expanding=True)), {"ids": ids or [-1], "q": qcode}).all())
    return [{**r, "qtext": texts.get(r["survey_id"], "")} for r in rows]


def family_trend(family: str, study_type: str, qcode: str, dim: str, value: str) -> dict:
    """The question's answers (Total, or one cut value) in every built wave of one family and study type, oldest
    first. Empty when nobody in that group answered."""
    with get_engine("app").connect() as conn:
        waves = _family(conn, family, study_type)
        rows = conn.execute(text(_TREND_ROWS + " AND dim_value = :v").bindparams(bindparam("ids", expanding=True), bindparam("d", expanding=True)),
                            {"ids": [w["survey_id"] for w in waves] or [-1], "q": qcode, "d": [dim], "v": value}).mappings().all()
        rows = worded(conn, rows, qcode)
        if dim != "total":   # versions come from Total, so every column of a question numbers them alike
            total = conn.execute(text(_TREND_ROWS + " AND dim_value = 'Total'").bindparams(
                bindparam("ids", expanding=True), bindparam("d", expanding=True)),
                {"ids": [w["survey_id"] for w in waves] or [-1], "q": qcode, "d": ["total"]}).mappings().all()
            return _trend(qcode, dim, value, waves, rows, versions(worded(conn, total, qcode)))
    return _trend(qcode, dim, value, waves, rows)


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


def chain(family: dict, survey_id: int, weeks: int) -> list[dict]:
    """The wave and up to weeks - 1 earlier ones of {survey_id: wave}, following the prior-week chain as srv_result does."""
    waves = []
    while survey_id in family and len(waves) < weeks:
        waves.append(family[survey_id])
        survey_id = family[survey_id]["prior_survey_id"]
    return waves


def pool(conn, survey_id: int, weeks: int) -> list[dict]:
    family = {r["survey_id"]: dict(r) for r in conn.execute(text(   # one round trip: the family's latest waves up to this one
        "SELECT w.survey_id, w.wave_date, w.prior_survey_id FROM srv_wave w JOIN srv_wave me ON me.survey_id = :s"
        " AND w.survey_family = me.survey_family AND w.wave_date <= me.wave_date ORDER BY w.wave_date DESC LIMIT 20"),
        {"s": survey_id}).mappings()}
    return chain(family, survey_id, weeks)


def people(conn, survey_id: int) -> dict:
    """Who gave which answer in one wave, for Audiences (api/team.py): each respondent is one bit, so every cut value
    and every answer row is a bitset (hex) and an audience is ANDs plus bit counts, no database. A 2,300-person wave
    is ~250 KB raw. Respondent-level: published next to the book but never served (nginx and the API expose no route).
    {"cuts": {dim: {value: hex}}, "questions": {qcode: {"text": normalised wording, "rows": [[item_id, option_id,
    item_label, option_code, option_label], ...] in sort order, "bits": {"item_id,option_id": hex}}}}"""
    rows = conn.execute(text(
        f"SELECT respondent_id, qcode, item_id, option_id, {', '.join(CUTS)} FROM srv_answer"
        " WHERE survey_id = :s").execution_options(stream_results=True, max_row_buffer=1000), {"s": survey_id})
    respondents = set()
    members: dict = defaultdict(set)
    cuts: dict = {dim: defaultdict(set) for dim in CUTS}
    seen = set()
    try:
        for r in rows:
            respondents.add(r[0])
            members[(r[1], r[2], r[3])].add(r[0])
            if r[0] not in seen:   # a respondent's cuts are the same on every row
                seen.add(r[0])
                for dim, value in zip(CUTS, r[4:]):
                    if value not in (None, ""):   # no value for the cut: not a group, as in srv_result
                        cuts[dim][value].add(r[0])
    finally:
        rows.close()
    seat = {rid: i for i, rid in enumerate(sorted(respondents))}

    def mask(found: set[int]) -> int:
        out = 0
        for rid in found:
            out |= 1 << seat[rid]
        return out

    bits = {key: mask(found) for key, found in members.items()}
    cuts = {dim: {value: mask(found) for value, found in values.items()} for dim, values in cuts.items()}
    questions: dict = {}
    for a in conn.execute(text(
            "SELECT r.qcode, r.item_id, r.option_id, r.item_label, r.option_code, r.option_label, q.qtext FROM srv_result r"
            " JOIN cip_question q ON q.question_id = r.question_id WHERE r.survey_id = :s AND r.dim = 'total'"
            " ORDER BY r.qcode, r.sort_order"), {"s": survey_id}):
        q = questions.setdefault(a[0], {"text": normalise_text(a[6]), "rows": [], "bits": {}})
        q["rows"].append(list(a[1:6]))
    for (qcode, item, option), b in bits.items():
        if qcode in questions:
            questions[qcode]["bits"][f"{item},{option}"] = format(b, "x")
    return {"cuts": {dim: {v: format(b, "x") for v, b in values.items()} for dim, values in cuts.items()}, "questions": questions}


def question_cuts(conn, ids: list[int], qcode: str | None = None) -> dict:
    """{(survey_id, qcode): {"answers": [...], "counts": [[item_id, option_id, *CUTS, n], ...]}}: srv_answer counted
    by every cut at once and the question's answer labels, enough for any two-cut crosstab. The ETL publishes one
    per wave and question (etl/publish.py); crosstab() builds it live for the rest."""
    where = "survey_id IN :ids" + (" AND qcode = :q" if qcode else "")
    params = {"ids": ids, **({"q": qcode} if qcode else {})}
    cuts = ", ".join(CUTS)
    out: dict = defaultdict(lambda: {"answers": [], "counts": []})
    for r in conn.execute(text(
            f"SELECT survey_id, qcode, item_id, option_id, {cuts}, COUNT(*) FROM srv_answer WHERE {where}"
            f" GROUP BY survey_id, qcode, item_id, option_id, {cuts}").bindparams(bindparam("ids", expanding=True)), params):
        out[(r[0], r[1])]["counts"].append(list(r[2:]))
    for a in conn.execute(text(
            "SELECT r.survey_id, r.qcode, r.item_id, r.option_id, r.item_label, r.option_code, r.option_label, r.sort_order,"
            " r.flags, r.concept_option_id, q.qtext FROM srv_result r JOIN cip_question q ON q.question_id = r.question_id"
            f" WHERE r.{where.replace(' AND qcode', ' AND r.qcode')} AND r.dim = 'total'").bindparams(bindparam("ids", expanding=True)), params).mappings():
        out[(a["survey_id"], a["qcode"])]["answers"].append({k: a[k] for k in list(a.keys())[2:]})
    return dict(out)


def crosstab(survey_id: int, qcode: str, by: tuple, weeks: int) -> dict:
    with get_engine("app").connect() as conn:
        waves = pool(conn, survey_id, weeks)
        found = question_cuts(conn, [w["survey_id"] for w in waves] or [-1], qcode)
    return crosstab_from(survey_id, qcode, by, waves, {sid: part for (sid, _), part in found.items()})


def crosstab_from(survey_id: int, qcode: str, by: tuple, waves: list[dict], parts: dict) -> dict:
    """One question by two cuts, pooled across waves on the answer's label and code (ids differ per wave, as in
    srv_result's comparisons), then bases, percentages and flags. parts is question_cuts' {survey_id: part}.
    Respondents with no value for a cut are left out, as in srv_result. Cells nobody chose come back as n = 0."""
    first, second = (2 + CUTS.index(cut) for cut in by)
    answers = [{**a, "survey_id": sid} for sid, part in parts.items() for a in part["answers"]]
    if answers and "qtext" in answers[0]:   # pool only waves that asked this wave's question, not a reused code
        version = versions(answers)
        mine = version.get(survey_id)
        parts = {sid: part for sid, part in parts.items() if version.get(sid) == mine}
        answers = [a for a in answers if version.get(a["survey_id"]) == mine]
    counts = [(sid, c[0], c[1], c[first], c[second], c[-1]) for sid, part in parts.items() for c in part["counts"]]
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



_QUESTION_ROWS = ("SELECT survey_id, dim, dim_value, item_label, option_code, option_label, sort_order, n, base_n, concept_option_id"
                  " FROM srv_result WHERE survey_id IN :ids AND qcode = :q")


def question(family: str, study_type: str, qcode: str) -> dict:
    """One question across every wave of its family, for every cut at once: what Compare and Trends draw from, so
    picking waves or a cut on screen needs no further request. The ETL publishes one per question (etl/publish.py)."""
    with get_engine("app").connect() as conn:
        waves = _family(conn, family, study_type)
        rows = conn.execute(text(_QUESTION_ROWS).bindparams(bindparam("ids", expanding=True)),
                            {"ids": [w["survey_id"] for w in waves] or [-1], "q": qcode}).mappings().all()
        rows = worded(conn, rows, qcode)
    country = next((code for code, c in countries().items() if c.get("family") == family), "US")
    return question_from(qcode, waves, rows, countries().get(country, {}).get("cuts", {}))


def question_from(qcode: str, waves: list[dict], rows: list[dict], order: dict) -> dict:
    """Compact columns, small after gzip: waves [[survey_id, date, version]], each version's wording, answers
    [[item_label, code, label]], cuts [[dim, value]] in display order, then one entry per cell in w, c, a (indexes
    into those lists), n (people who chose it) and b (its base). A percentage is 100 * n / b."""
    rows = [r for r in rows if r["dim_value"] != ""]          # no value for the cut: not a group
    version = versions([r for r in rows if r["dim"] == "total"])
    asked = {r["survey_id"] for r in rows}
    wording = {r["survey_id"]: r["qtext"] for r in rows}
    number: dict = {}
    texts: dict = {}
    out_waves = []
    for w in waves:                                          # oldest first: version 1 is the first wording
        if w["survey_id"] in asked:
            v = number.setdefault(version.get(w["survey_id"], -w["survey_id"]), len(number) + 1)
            texts[v] = wording[w["survey_id"]]
            out_waves.append([w["survey_id"], str(w["wave_date"])[:10], v])
    at = {w[0]: i for i, w in enumerate(out_waves)}
    answers: dict = {}
    for r in sorted(rows, key=lambda r: -at[r["survey_id"]]):   # the latest wording of each answer
        answers.setdefault((r["item_label"], r["option_code"]), (r["sort_order"], r["option_label"] or r["item_label"]))
    keys = sorted(answers, key=lambda k: answers[k][0])
    answer = {k: i for i, k in enumerate(keys)}
    present = {(r["dim"], r["dim_value"]) for r in rows}
    rank = lambda d, v: (order.get(d, []).index(v) if v in order.get(d, []) else len(order.get(d, [])), v)   # noqa: E731
    cuts = [("total", "Total")] + sorted((c for c in present if c[0] != "total"),
                                         key=lambda c: (CUTS.index(c[0]) if c[0] in CUTS else 99, *rank(*c)))
    cut = {c: i for i, c in enumerate(cuts)}
    cells = sorted((at[r["survey_id"]], cut[(r["dim"], r["dim_value"])], answer[(r["item_label"], r["option_code"])],
                    int(r["n"]), int(r["base_n"])) for r in rows)
    return {"qcode": qcode, "waves": out_waves, "versions": [texts[v] for v in sorted(texts)],
            "answers": [[k[0], k[1], answers[k][1]] for k in keys], "cuts": [list(c) for c in cuts],
            **{name: [c[i] for c in cells] for i, name in enumerate(("w", "c", "a", "n", "b"))},
            "n": [c[3] if c[4] >= HIDDEN_BASE else None for c in cells]}   # under HIDDEN_BASE only the base is published
