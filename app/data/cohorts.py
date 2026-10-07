"""Cohorts: an analyst's respondent rule, stored once, applied to every wave.

A rule is JSON over *concepts* (not question codes), so "beauty shoppers" means
the same thing in a 2023 Qualtrics wave and a 2026 Forsta one:

    {"any": [
      {"concept": "B1_7A4C2E", "option": "yes"},
      {"all": [{"concept": "B1_7A4C2E", "asked": false},
               {"concept": "B12_91D0AA", "answered": true}]}]}

Leaves:
    option   — the respondent gave that answer (single, grid) or ticked that item (multi)
    answered — the respondent answered any question mapped to the concept
    asked    — the respondent's WAVE has (true) / has not (false) the question

Only confirmed mappings count. The rule compiles to one SQL condition, and a
wave's membership is written with one INSERT … SELECT inside MySQL.

    python -m app.data.cohorts --sync      # define config/cohorts.yml, derive every wave
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Optional

import yaml
from sqlalchemy import bindparam, text

from app.core.database import get_engine

log = logging.getLogger("cip.cohorts")

CONFIG = Path(__file__).resolve().parents[2] / "config" / "cohorts.yml"


def _named(rule: dict) -> set[str]:
    if "all" in rule or "any" in rule:
        return set().union(*(_named(child) for child in rule.get("all") or rule.get("any") or []))
    if "not" in rule:
        return _named(rule["not"])
    return {rule.get("concept")}


def _codes(conn, rule: dict) -> tuple[dict[str, int], dict[tuple[int, str], int]]:
    """Only the concepts the rule names — every row costs a round trip's worth."""
    names = sorted(str(n) for n in _named(rule))
    concepts = dict(conn.execute(text("SELECT concept_code, concept_id FROM cip_concept WHERE concept_code IN :n")
                                 .bindparams(bindparam("n", expanding=True)), {"n": names}).all())
    options = {(cid, code): coid for cid, code, coid in conn.execute(text(
        "SELECT concept_id, option_code, concept_option_id FROM cip_concept_option WHERE concept_id IN :c")
        .bindparams(bindparam("c", expanding=True)), {"c": list(concepts.values()) or [-1]})}
    return concepts, options


def compile_rule(rule: dict, concepts: dict[str, int], options: dict[tuple[int, str], int]) -> tuple[str, dict]:
    """-> (SQL condition over `r`, a cip_respondent row; params)."""
    params: dict = {}

    def walk(node: dict) -> str:
        n = len(params)
        if "all" in node or "any" in node:
            parts = [walk(child) for child in node.get("all") or node.get("any")]
            joiner = " AND " if "all" in node else " OR "
            return "(" + joiner.join(parts) + ")" if parts else ("1=1" if "all" in node else "1=0")
        if "not" in node:
            return f"NOT {walk(node['not'])}"
        code = node.get("concept")
        if code not in concepts:
            raise ValueError(f"cohort rule names concept {code!r}, which does not exist")
        cid = concepts[code]
        if "option" in node:
            coid = options.get((cid, node["option"]))
            if coid is None:
                raise ValueError(f"concept {code} has no option {node['option']!r}")
            params[f"co{n}"] = coid
            return f"""EXISTS (SELECT 1 FROM cip_answer a{n}
                  JOIN cip_field f{n} ON f{n}.field_id = a{n}.field_id
                  JOIN cip_concept_map m{n} ON m{n}.survey_id = a{n}.survey_id
                       AND m{n}.question_id = f{n}.question_id
                       AND COALESCE(m{n}.item_id, 0) = COALESCE(f{n}.item_id, 0)
                       AND m{n}.status = 'confirmed' AND m{n}.concept_option_id = :co{n}
                  LEFT JOIN cip_option o{n} ON o{n}.option_id = m{n}.option_id
                 WHERE a{n}.respondent_id = r.respondent_id
                   AND a{n}.value_code = COALESCE(o{n}.value_code, 1))"""
        params[f"c{n}"] = cid
        if "answered" in node:
            found = f"""EXISTS (SELECT 1 FROM cip_answer a{n}
                  JOIN cip_field f{n} ON f{n}.field_id = a{n}.field_id
                  JOIN cip_concept_map m{n} ON m{n}.survey_id = a{n}.survey_id
                       AND m{n}.question_id = f{n}.question_id AND m{n}.concept_id = :c{n}
                       AND (m{n}.item_id IS NULL OR m{n}.item_id = f{n}.item_id)
                       AND m{n}.status = 'confirmed' AND m{n}.concept_option_id IS NULL
                 WHERE a{n}.respondent_id = r.respondent_id AND a{n}.value_code IS NOT NULL)"""
            return found if node["answered"] else f"NOT {found}"
        if "asked" in node:
            found = f"""EXISTS (SELECT 1 FROM cip_concept_map m{n}
                 WHERE m{n}.survey_id = r.survey_id AND m{n}.concept_id = :c{n}
                   AND m{n}.status = 'confirmed' AND m{n}.concept_option_id IS NULL)"""
            return found if node["asked"] else f"NOT {found}"
        raise ValueError(f"cohort rule leaf needs option, answered or asked: {node}")

    return walk(rule), params


def define_cohort(code: str, name: str, rule: dict, base_note: Optional[str] = None,
                  owner: Optional[str] = None) -> int:
    """The current version's cohort_id; a changed rule becomes version + 1."""
    stored = json.dumps(rule, sort_keys=True)
    with get_engine("etl").begin() as conn:
        compile_rule(rule, *_codes(conn, rule))                       # refuse a broken rule before storing it
        current = conn.execute(text(
            "SELECT cohort_id, version, rule_json FROM cip_cohort_def"
            " WHERE cohort_code = :code AND is_current = 1"), {"code": code}).first()
        if current is not None:
            old = current.rule_json if isinstance(current.rule_json, str) else json.dumps(current.rule_json)
            if json.dumps(json.loads(old), sort_keys=True) == stored:
                return int(current.cohort_id)
            conn.execute(text("UPDATE cip_cohort_def SET is_current = 0 WHERE cohort_id = :c"),
                         {"c": current.cohort_id})
            # a retired version keeps no members and no cells: nothing can read it by mistake
            for table in ("cip_respondent_cohort", "cip_agg_cell"):
                conn.execute(text(f"DELETE FROM {table} WHERE cohort_id = :c"), {"c": current.cohort_id})
        version = (current.version + 1) if current is not None else 1
        conn.execute(text(
            "INSERT INTO cip_cohort_def (cohort_code, version, cohort_name, rule_json, base_note, owner_email, is_current)"
            " VALUES (:code, :version, :name, :rule, :note, :owner, 1)"),
            {"code": code, "version": version, "name": name[:200], "rule": stored,
             "note": base_note, "owner": owner})
        return int(conn.execute(text(
            "SELECT cohort_id FROM cip_cohort_def WHERE cohort_code = :code AND version = :v"),
            {"code": code, "v": version}).scalar())


def current_cohorts() -> list[dict]:
    with get_engine("etl").connect() as conn:
        return [dict(r._mapping) for r in conn.execute(text(
            "SELECT cohort_id, cohort_code, cohort_name, version FROM cip_cohort_def"
            " WHERE is_current = 1 ORDER BY cohort_code"))]


def current_id(code: str) -> Optional[int]:
    with get_engine("etl").connect() as conn:
        return conn.execute(text("SELECT cohort_id FROM cip_cohort_def WHERE cohort_code = :c AND is_current = 1"),
                            {"c": code}).scalar()


def derive(cohort_id: int, survey_ids: Optional[list[int]] = None, conn=None) -> int:
    """Replace the cohort's memberships (every wave, or those listed) — in the
    caller's transaction when one is given."""
    if conn is None:
        with get_engine("etl").begin() as own:
            return derive(cohort_id, survey_ids, own)
    rule = conn.execute(text("SELECT rule_json FROM cip_cohort_def WHERE cohort_id = :c"),
                        {"c": cohort_id}).scalar()
    rule = json.loads(rule) if isinstance(rule, str) else rule
    condition, params = compile_rule(rule, *_codes(conn, rule))
    params["cid"] = cohort_id
    scope = ""
    if survey_ids is not None:
        scope = " AND survey_id IN :ids"
        params["ids"] = list(survey_ids) or [-1]
    delete = text("DELETE FROM cip_respondent_cohort WHERE cohort_id = :cid" + scope)
    insert = text(
        "INSERT INTO cip_respondent_cohort (cohort_id, respondent_id, survey_id)"
        " SELECT :cid, r.respondent_id, r.survey_id FROM cip_respondent r"
        f" WHERE r.is_qualified = 1{scope.replace('survey_id', 'r.survey_id')} AND {condition}")
    if survey_ids is not None:
        delete, insert = (s.bindparams(bindparam("ids", expanding=True)) for s in (delete, insert))
    conn.execute(delete, params)
    return conn.execute(insert, params).rowcount


def sync(path: Path = CONFIG) -> list[int]:
    """Define every cohort in config/cohorts.yml and derive it on every wave."""
    ids = []
    for c in (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("cohorts", []):
        from app.data import cube                      # cube imports this module
        cid = define_cohort(c["code"], c["name"], c["rule"], c.get("base_note"), c.get("owner"))
        log.info("%s (cohort_id %s): %d members", c["code"], cid, derive(cid))
        with get_engine("etl").connect() as conn:
            waves = [r[0] for r in conn.execute(text(
                "SELECT DISTINCT survey_id FROM cip_respondent_cohort WHERE cohort_id = :c"), {"c": cid})]
        for sid in waves:
            cube.build_cube(sid, [cid])
        log.info("%s: cube cells built on %d waves", c["code"], len(waves))
        ids.append(cid)
    return ids


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s | %(message)s")
    ap = argparse.ArgumentParser(description="Define and derive cohorts")
    ap.add_argument("--sync", action="store_true", required=True, help="apply config/cohorts.yml to every wave")
    ap.parse_args()
    sync()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
