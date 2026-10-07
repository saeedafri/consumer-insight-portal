"""Link each wave's questions to canonical concepts (spec §5.2).

For every question a wave asked, decide which concept it is:

    exact    same normalised wording and type, and every answer it offers is
             already a concept option                     -> confirmed
    changed  same wording, but it offers answers the concept lacks -> proposed
    similar  wording at least SIMILAR_THRESHOLD alike      -> proposed
    new      nothing close: a new concept                  -> confirmed

A grid is harmonised row by row — each row is its own concept, rows of one
grid share concept_group. A proposal writes only its unit-level map row;
answers are mapped when an analyst confirms it on the Mappings page, so
nothing trends before someone has looked.
"""
from __future__ import annotations

import difflib
import hashlib
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import bindparam, text

from app.core.database import get_engine

# The highest-scoring unrelated pair between the 09/21 and 09/28 waves is 0.796.
SIMILAR_THRESHOLD = 0.85

# An instruction trailing the question — "…? Select all that apply", ". Please
# select one". Only after sentence punctuation, so wording that merely starts
# with "Please select your age" is kept, and it stops at " - " so an
# "- Other (please specify)" suffix survives.
_INSTRUCTIONS = re.compile(
    r"\s*[?.:]\s*\(?\s*(select\s+(all|up to|one|only)\b|please select)[^-]*?(?=\s+-\s|$)", re.I)
_QUOTES = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"'})


def normalise_text(value) -> str:
    """The wording two waves must share to be the same question or answer."""
    s = str(value or "").replace("\xa0", " ").replace("Â", "").translate(_QUOTES)
    s = " ".join(s.split()).lower()
    return _INSTRUCTIONS.sub("", s).strip(" .?:;") or s.strip(" .?:;")


def slug(value, limit: int = 60) -> str:
    return (re.sub(r"[^a-z0-9]+", "_", normalise_text(value)).strip("_")[:limit]) or "x"


@dataclass
class Unit:
    """One thing a concept can be: a question, or one row of a grid."""
    question_id: int
    item_id: Optional[int]                 # the grid row; None for a whole question
    qcode: str
    qtype: str
    topic_id: Optional[int]
    wording: str
    group: Optional[str] = None            # concept_group, grid rows only
    choices: list = field(default_factory=list)   # (item_id, option_id, label, is_nonresponse, order)

    @property
    def key(self) -> str:
        return f"{self.question_id}:{self.item_id or 0}:0"

    @property
    def match_text(self) -> str:
        return normalise_text(self.wording)


@dataclass
class Concept:
    concept_id: int
    code: str
    qtype: str
    match_text: str
    options: dict = field(default_factory=dict)      # normalised label -> concept_option_id
    option_codes: set = field(default_factory=set)


def _digest(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:6].upper()


def _units(conn, survey_id: int) -> list[Unit]:
    questions = conn.execute(text(
        "SELECT question_id, qcode, qtext, qtype, topic_id FROM cip_question"
        " WHERE survey_id = :sid AND is_technical = 0 AND is_virtual = 0 ORDER BY sort_order"),
        {"sid": survey_id}).all()
    items, options = defaultdict(list), defaultdict(list)
    for qid, iid, label, order in conn.execute(text(
            "SELECT i.question_id, i.item_id, i.item_label, i.sort_order FROM cip_item i"
            " JOIN cip_question q ON q.question_id = i.question_id"
            " WHERE q.survey_id = :sid ORDER BY i.sort_order"), {"sid": survey_id}):
        items[qid].append((iid, label, order))
    for qid, oid, label, nonresponse, order in conn.execute(text(
            "SELECT o.question_id, o.option_id, o.value_label, o.is_nonresponse, o.sort_order"
            " FROM cip_option o JOIN cip_question q ON q.question_id = o.question_id"
            " WHERE q.survey_id = :sid ORDER BY o.sort_order"), {"sid": survey_id}):
        options[qid].append((oid, label, nonresponse, order))

    units: list[Unit] = []
    for qid, qcode, qtext, qtype, topic_id in questions:
        if qtype.startswith("grid"):
            group = f"{slug(qcode, 20).upper()}_{_digest(normalise_text(qtext))}"
            for iid, row_label, _ in items[qid]:
                units.append(Unit(qid, iid, qcode, qtype, topic_id, f"{qtext} :: {row_label}", group,
                                  [(iid, oid, lab, nr, o) for oid, lab, nr, o in options[qid]]))
        elif qtype == "multi":
            units.append(Unit(qid, None, qcode, qtype, topic_id, qtext, None,
                              [(iid, None, lab, 0, o) for iid, lab, o in items[qid]]))
        else:
            units.append(Unit(qid, None, qcode, qtype, topic_id, qtext, None,
                              [(None, oid, lab, nr, o) for oid, lab, nr, o in options[qid]]))
    return units


def _concepts(conn) -> dict[int, Concept]:
    concepts = {cid: Concept(cid, code, qtype, match or normalise_text(name))
                for cid, code, qtype, match, name in conn.execute(text(
                    "SELECT concept_id, concept_code, qtype, match_text, concept_name"
                    " FROM cip_concept ORDER BY concept_id"))}
    # The wording a concept was confirmed on is the truth. Re-normalising it
    # here means a change to normalise_text() applies to every existing
    # concept — stored match_text is only the fallback. Newest first, so the
    # earliest wording is the one left standing.
    for cid, qtext, row in conn.execute(text(
            "SELECT m.concept_id, q.qtext, i.item_label FROM cip_concept_map m"
            " JOIN cip_question q ON q.question_id = m.question_id"
            " LEFT JOIN cip_item i ON i.item_id = m.item_id"
            " WHERE m.status = 'confirmed' AND m.concept_option_id IS NULL"
            " ORDER BY m.map_id DESC")):
        concepts[cid].match_text = normalise_text(f"{qtext} :: {row}" if row else qtext)
    for cid, coid, code, label in conn.execute(text(
            "SELECT concept_id, concept_option_id, option_code, option_label FROM cip_concept_option")):
        concepts[cid].options[normalise_text(label)] = coid
        concepts[cid].option_codes.add(code)
    return concepts


def _decide(unit: Unit, concepts: dict[int, Concept], used: set[int]):
    """-> (kind, concept or None, confidence, evidence)"""
    pool = [c for c in concepts.values() if c.qtype == unit.qtype and c.concept_id not in used]
    labels = {normalise_text(ch[2]) for ch in unit.choices}
    same = [(sorted(labels - set(c.options)), c) for c in pool if c.match_text == unit.match_text]
    if same:
        # A concept that already has every answer wins; otherwise the one this
        # wave adds least to. Newest first on a tie — it is the latest decision
        # (e.g. an analyst's "keep separate").
        added, concept = min(same, key=lambda s: (len(s[0]), -s[1].concept_id))
        if not added:
            return "exact", concept, 1.0, "same wording and answers"
        return "changed", concept, 1.0, f"same wording; adds: {', '.join(added)}"[:1000]
    scored = [(difflib.SequenceMatcher(None, unit.match_text, c.match_text).ratio(), c) for c in pool]
    ratio, best = max(scored, key=lambda s: s[0], default=(0.0, None))
    if best is not None and ratio >= SIMILAR_THRESHOLD:
        return "similar", best, round(ratio, 4), f"{ratio:.0%} similar wording to {best.code}"
    return "new", None, 1.0, "new concept"


def _create_concepts(conn, units: list[Unit], concepts: dict[int, Concept]) -> list[Concept]:
    """A new concept per unit: one INSERT and one SELECT, whatever the count —
    each round trip is ~250 ms from the India office to the database."""
    if not units:
        return []
    taken = {c.code for c in concepts.values()}
    rows = []
    for unit in units:
        base = f"{slug(unit.qcode, 20).upper()}_{_digest(unit.qtype + unit.match_text)}"
        code, n = base, 1
        while code in taken:
            n += 1
            code = f"{base}_{n}"
        taken.add(code)
        rows.append({"code": code, "name": unit.wording[:255], "grp": unit.group,
                     "topic": unit.topic_id, "qtype": unit.qtype, "match": unit.match_text[:2000]})
    conn.execute(text(
        "INSERT INTO cip_concept (concept_code, concept_name, concept_group, topic_id, qtype, match_text)"
        " VALUES (:code, :name, :grp, :topic, :qtype, :match)"), rows)
    ids = dict(conn.execute(text(
        "SELECT concept_code, concept_id FROM cip_concept WHERE concept_code IN :codes")
        .bindparams(bindparam("codes", expanding=True)), {"codes": [r["code"] for r in rows]}).all())
    created = []
    for unit, row in zip(units, rows):
        cid = ids[row["code"]]
        concepts[cid] = Concept(cid, row["code"], unit.qtype, unit.match_text)
        created.append(concepts[cid])
    return created


def _add_options(conn, pairs: list[tuple[Concept, Unit]]) -> None:
    """Every answer each unit offers becomes (or already is) an option of its
    concept. One batched INSERT and one SELECT for the whole list."""
    new, key_of = [], {}                       # (concept_id, option_code) -> normalised label
    for concept, unit in pairs:
        pending = set()
        for _, _, label, nonresponse, order in unit.choices:
            key = normalise_text(label)
            if key in concept.options or key in pending:
                continue
            pending.add(key)
            code, n = slug(label), 1
            while code in concept.option_codes:
                n += 1
                code = f"{slug(label, 55)}_{n}"
            concept.option_codes.add(code)
            key_of[(concept.concept_id, code)] = key
            new.append({"cid": concept.concept_id, "code": code, "label": str(label)[:500],
                        "ord": order or 0, "nr": nonresponse or 0})
    if not new:
        return
    conn.execute(text(
        "INSERT INTO cip_concept_option (concept_id, option_code, option_label, sort_order, is_nonresponse)"
        " VALUES (:cid, :code, :label, :ord, :nr)"), new)
    by_id = {c.concept_id: c for c, _ in pairs}
    for cid, coid, code in conn.execute(text(
            "SELECT concept_id, concept_option_id, option_code FROM cip_concept_option"
            " WHERE concept_id IN :ids").bindparams(bindparam("ids", expanding=True)),
            {"ids": sorted(by_id)}):
        if (cid, code) in key_of:
            by_id[cid].options[key_of[(cid, code)]] = coid


def _map_units(conn, survey_id: int, rows: list[tuple]) -> None:
    """rows: (unit, concept, status, method, confidence, evidence)."""
    if rows:
        conn.execute(text(
            "INSERT INTO cip_concept_map (survey_id, map_key, question_id, item_id, concept_id,"
            " status, method, confidence, evidence)"
            " VALUES (:sid, :key, :qid, :item, :cid, :status, :method, :conf, :evidence)"),
            [{"sid": survey_id, "key": u.key, "qid": u.question_id, "item": u.item_id,
              "cid": c.concept_id, "status": status, "method": method,
              "conf": confidence, "evidence": evidence}
             for u, c, status, method, confidence, evidence in rows])


def _map_choices(conn, survey_id: int, pairs: list[tuple[Concept, Unit]],
                 reviewer: Optional[str] = None) -> None:
    """Answer-level rows, written only once the unit is confirmed."""
    rows = [{"sid": survey_id, "key": f"{unit.question_id}:{item or 0}:{option or 0}",
             "qid": unit.question_id, "item": item, "option": option,
             "cid": concept.concept_id, "coid": concept.options[normalise_text(label)],
             "who": reviewer, "status": "confirmed", "method": "exact_text", "conf": 1}
            for concept, unit in pairs for item, option, label, _, _ in unit.choices]
    if rows:
        conn.execute(text(
            "INSERT INTO cip_concept_map (survey_id, map_key, question_id, item_id, option_id,"
            " concept_id, concept_option_id, status, method, confidence, reviewed_by)"
            # every value a placeholder, or PyMySQL sends one round trip per row
            " VALUES (:sid, :key, :qid, :item, :option, :cid, :coid, :status, :method, :conf, :who)"),
            rows)


def harmonise_survey(survey_id: int) -> dict[str, int]:
    """Map every non-technical unit of one wave. Safe to re-run: a unit that
    already has a map row — confirmed, proposed or rejected — is left alone.

    Two passes: decide every unit against the concepts that existed before the
    wave (a concept made for this wave is already used by it, so it could never
    match a sibling), then write concepts, options and map rows in batches."""
    counts = {"exact": 0, "changed": 0, "similar": 0, "new": 0, "skipped": 0}
    with get_engine("etl").begin() as conn:
        concepts = _concepts(conn)
        mapped = conn.execute(text(
            "SELECT map_key, concept_id FROM cip_concept_map WHERE survey_id = :sid"),
            {"sid": survey_id}).all()
        done, used = {k for k, _ in mapped}, {c for _, c in mapped}
        decisions = []                              # [unit, kind, concept, confidence, evidence]
        for unit in _units(conn, survey_id):
            if unit.key in done:
                counts["skipped"] += 1
                continue
            kind, concept, confidence, evidence = _decide(unit, concepts, used)
            if concept is not None:
                used.add(concept.concept_id)
            decisions.append([unit, kind, concept, confidence, evidence])
            counts[kind] += 1

        fresh = [d for d in decisions if d[1] == "new"]
        for d, concept in zip(fresh, _create_concepts(conn, [d[0] for d in fresh], concepts)):
            d[2] = concept
        settled = [(concept, unit) for unit, kind, concept, _, _ in decisions if kind in ("exact", "new")]
        _add_options(conn, settled)
        _map_units(conn, survey_id, [
            (unit, concept,
             "confirmed" if kind in ("exact", "new") else "proposed",
             "similar_text" if kind == "similar" else "exact_text",
             confidence, evidence)
            for unit, kind, concept, confidence, evidence in decisions])
        _map_choices(conn, survey_id, settled)
    return counts


def _open_unit(conn, survey_id: int, question_id: int, item_id: Optional[int]) -> Unit:
    unit = next((u for u in _units(conn, survey_id)
                 if u.question_id == question_id and u.item_id == item_id), None)
    status = conn.execute(text(
        "SELECT status FROM cip_concept_map WHERE survey_id = :sid AND map_key = :key"),
        {"sid": survey_id, "key": f"{question_id}:{item_id or 0}:0"}).scalar()
    if unit is None or status != "proposed":
        raise ValueError(f"question {question_id} row {item_id} is not awaiting review")
    return unit


def _claim(conn, survey_id: int, unit: Unit, status: str, reviewer: str,
           concept_id: Optional[int] = None, method: Optional[str] = None) -> None:
    """Settle the unit only if it is still proposed — the conditional UPDATE is
    the guard. A colleague's page loaded before our decision passes its own
    status check but finds nothing to update here (and on MySQL waits on our
    row lock first), so a decision can never be made twice."""
    claimed = conn.execute(text(
        "UPDATE cip_concept_map SET status = :status, concept_id = COALESCE(:cid, concept_id),"
        " method = COALESCE(:method, method), reviewed_by = :who, reviewed_at = CURRENT_TIMESTAMP"
        " WHERE survey_id = :sid AND map_key = :key AND status = 'proposed'"),
        {"status": status, "cid": concept_id, "method": method, "who": reviewer,
         "sid": survey_id, "key": unit.key}).rowcount
    if claimed != 1:
        raise ValueError(f"question {unit.question_id} row {unit.item_id} is not awaiting review")


def confirm(survey_id: int, question_id: int, item_id: Optional[int],
            concept_id: int, reviewer: str) -> None:
    """Accept the proposal, or map the unit to another concept instead."""
    with get_engine("etl").begin() as conn:
        unit = _open_unit(conn, survey_id, question_id, item_id)
        concept = _concepts(conn).get(concept_id)
        if concept is None:
            raise ValueError(f"concept {concept_id} does not exist")
        clash = conn.execute(text(
            "SELECT COUNT(*) FROM cip_concept_map WHERE survey_id = :sid AND concept_id = :cid"
            " AND map_key <> :key AND concept_option_id IS NULL AND status <> 'rejected'"),
            {"sid": survey_id, "cid": concept_id, "key": unit.key}).scalar()
        if clash:          # one wave, one question per concept — or its answers count twice
            raise ValueError(f"concept {concept.code} is already used by another question in this wave")
        _claim(conn, survey_id, unit, "confirmed", reviewer, concept_id=concept_id)
        _add_options(conn, [(concept, unit)])
        _map_choices(conn, survey_id, [(concept, unit)], reviewer)


def keep_separate(survey_id: int, question_id: int, item_id: Optional[int], reviewer: str) -> int:
    """Not the same question after all: give it its own concept."""
    with get_engine("etl").begin() as conn:
        unit = _open_unit(conn, survey_id, question_id, item_id)
        _claim(conn, survey_id, unit, "confirmed", reviewer, method="manual")
        concept = _create_concepts(conn, [unit], _concepts(conn))[0]
        conn.execute(text(
            "UPDATE cip_concept_map SET concept_id = :cid WHERE survey_id = :sid AND map_key = :key"),
            {"cid": concept.concept_id, "sid": survey_id, "key": unit.key})
        _add_options(conn, [(concept, unit)])
        _map_choices(conn, survey_id, [(concept, unit)], reviewer)
        return concept.concept_id


def reject(survey_id: int, question_id: int, item_id: Optional[int], reviewer: str) -> None:
    """Never trend this unit."""
    with get_engine("etl").begin() as conn:
        unit = _open_unit(conn, survey_id, question_id, item_id)
        _claim(conn, survey_id, unit, "rejected", reviewer)


def harmonise_all() -> dict[str, dict[str, int]]:
    """Every wave, oldest first — the earliest wording seeds each concept."""
    with get_engine("etl").connect() as conn:
        waves = conn.execute(text(
            "SELECT survey_id, wave_label FROM cip_survey"
            " ORDER BY wave_date, wave_label, survey_id")).all()
    return {label: harmonise_survey(sid) for sid, label in waves}


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Link waves' questions to concepts")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--wave", help="one wave label, e.g. 2026-09-28")
    group.add_argument("--all", action="store_true", help="every wave, oldest first")
    args = ap.parse_args()
    if args.all:
        results = harmonise_all()
    else:
        with get_engine("etl").connect() as conn:
            sid = conn.execute(text("SELECT survey_id FROM cip_survey WHERE wave_label = :w"),
                               {"w": args.wave}).scalar()
        if sid is None:
            print(f"No wave labelled {args.wave}")
            return 1
        results = {args.wave: harmonise_survey(sid)}
    for label, counts in results.items():
        print(label, counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
