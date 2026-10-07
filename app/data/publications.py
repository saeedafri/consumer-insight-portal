"""Publications: numbers that left Coresight, frozen with their definition.

A publication is a DEFINITION — which question (concept), which waves, which
cohort, which cut, pooled or wave by wave, minimum base — plus the cells it
gave on the day it was published. `compute` is the only function that turns a
definition into cells, so publishing and re-checking cannot disagree about
method. `drift` recomputes today and compares, cell by cell: the report that
replaces the analysts' manual Cross-Check tab.

    {"concept": "BT13_F00B90", "waves": ["2024-06-03", "2025-05-12"],
     "cohort": "BEAUTY_SHOPPER", "cut": "total", "pooled": true, "min_base": 30}

    python -m app.data.publications --drift     # exit 1 when a published number moved
"""
from __future__ import annotations

import argparse
import json
import logging
import unicodedata
from datetime import date
from typing import Optional

import pandas as pd
from sqlalchemy import bindparam, text

from app.core.database import get_engine, query_df
from app.data import repository

log = logging.getLogger("cip.publications")

TOLERANCE = 0.0005          # proportions and averages (spec §6); counts are exact


def _fresh(fn):
    return getattr(fn, "__wrapped__", fn)      # a drift check must not read a cached answer


def _resolve(definition: dict) -> tuple[int, dict[int, str], Optional[int], dict[int, date]]:
    """-> (concept_id, {survey_id: wave_label}, cohort_id, {survey_id: wave_date});
    refuses what does not exist."""
    concept = query_df("SELECT concept_id FROM cip_concept WHERE concept_code = :c",
                       {"c": definition.get("concept")})
    if concept.empty:
        raise ValueError(f"publication names concept {definition.get('concept')!r}, which does not exist")
    labels = list(definition.get("waves") or [])
    with get_engine("app").connect() as conn:
        rows = conn.execute(text("SELECT survey_id, wave_label, wave_date FROM cip_survey WHERE wave_label IN :w")
                            .bindparams(bindparam("w", expanding=True)), {"w": labels or ["-"]}).all()
    waves = {sid: label for sid, label, _ in rows}
    dates = {sid: day for sid, _, day in rows}
    missing = sorted(set(labels) - set(waves.values()))
    if missing or not labels:
        raise ValueError(f"publication names waves that are not loaded: {', '.join(missing) or '(none given)'}")
    cohort_id = None
    if definition.get("cohort"):
        from app.data.cohorts import current_id
        cohort_id = current_id(definition["cohort"])
        if cohort_id is None:
            raise ValueError(f"publication names cohort {definition['cohort']!r}, which does not exist")
    return int(concept.concept_id.iloc[0]), waves, cohort_id, dates


def _same_key(label: str) -> str:
    """How MySQL's accent- and case-insensitive collation compares two keys."""
    return "".join(ch for ch in unicodedata.normalize("NFKD", label) if not unicodedata.combining(ch)).casefold()


def compute(definition: dict) -> list[dict]:
    """The cells a definition gives on today's data.

    Keys are cut to the stored width here, so a frozen cell and its recompute
    always meet. Under the minimum base (D5) the value AND its count are
    withheld — n / base would give the hidden share away — and an average is
    withheld when too few people gave that answer, whatever the segment base."""
    concept_id, waves, cohort_id, _ = _resolve(definition)
    min_base = int(definition.get("min_base", 30))

    def cell(answer, column, n, base, value, people):
        hidden = value is None or pd.isna(value) or base < min_base or people < min_base
        return {"row_key": str(answer)[:250], "col_key": column[:250],
                "n": None if hidden or n is None else int(n), "base_n": int(base),
                "value": None if hidden else float(value)}

    cells = []
    if definition.get("pooled", True):
        frame = _fresh(repository.concept_pooled)(concept_id, sorted(waves), cohort_id,
                                                  definition.get("cut", "total"))
        for row in frame.itertuples():
            segment, base = row.segment if row.segment is not None else "(none)", int(row.base_n)
            cells.append(cell(row.answer, f"{segment}|pct", row.n, base, row.pct, base))
            for measure in ("avg_age", "avg_income_k"):
                cells.append({**cell(row.answer, f"{segment}|{measure}", None, base,
                                     getattr(row, measure), int(row.n)), "n": None})
    else:
        if definition.get("cut", "total") != "total":
            raise ValueError("a wave-by-wave publication is by total only")
        frame = _fresh(repository.concept_trend)(concept_id, cohort_id)
        frame = frame[frame.wave_label.isin(set(waves.values()))] if not frame.empty else frame
        for row in frame.itertuples():
            cells.append(cell(row.answer, f"{row.wave_label}|pct", row.n, int(row.base_n), row.pct, int(row.base_n)))
    seen = set()
    for c in cells:
        key = (_same_key(c["row_key"]), _same_key(c["col_key"]))
        if key in seen:
            raise ValueError(f"two answers of this question are both labelled {c['row_key']!r} — "
                             "rename one on the Mappings page before publishing")
        seen.add(key)
    return cells


def footnote(definition: dict, cells: Optional[list] = None) -> str:
    """"Base: 2,020 US respondents aged 18+, surveyed June 2024–May 2025; 1,130
    beauty shoppers answered. …" — the sample AND the table's own base (spec §7)."""
    _, waves, cohort_id, dates = _resolve(definition)
    cells = compute(definition) if cells is None else cells
    with get_engine("app").connect() as conn:
        n = conn.execute(text("SELECT COUNT(*) FROM cip_respondent WHERE is_qualified = 1 AND survey_id IN :s")
                         .bindparams(bindparam("s", expanding=True)), {"s": sorted(waves)}).scalar()
    months = sorted({date.fromisoformat(str(d)[:10]).strftime("%Y-%m") for d in dates.values() if d})
    name = lambda ym: date.fromisoformat(ym + "-01").strftime("%B %Y")
    period = name(months[0]) if len(months) == 1 else f"{name(months[0])}–{name(months[-1])}"
    bases = {}
    for c in cells:
        if c["col_key"].endswith("|pct"):
            column = c["col_key"].rsplit("|", 1)[0]
            bases[column] = max(bases.get(column, 0), c["base_n"])
    who = ""
    if cohort_id:
        who = query_df("SELECT cohort_name FROM cip_cohort_def WHERE cohort_id = :c",
                       {"c": cohort_id}).cohort_name.iloc[0].lower() + " "
    note = f"Base: {n:,} US respondents aged 18+, surveyed {period}; {sum(bases.values()):,} {who}answered."
    if definition.get("pooled", True):
        note += " Averages use range midpoints."
    return note + " Source: Coresight Research."


def publish(code: str, name: str, definition: dict, owner: Optional[str] = None,
            destination: Optional[str] = None, note: Optional[str] = None) -> int:
    """Freeze today's cells as the next version of `code`. Returns publication_id."""
    code = (code or "").strip()
    if not code:
        raise ValueError("a publication needs a code (letters or digits in its name)")
    taken = query_df("SELECT DISTINCT pub_name FROM cip_publication WHERE pub_code = :c", {"c": code})
    if not taken.empty and name[:255] not in set(taken.pub_name):
        raise ValueError(f"code {code} is already used by {taken.pub_name.iloc[0]!r} — choose another name")
    cells = compute(definition)
    note = note or footnote(definition, cells)
    with get_engine("etl").begin() as conn:
        version = (conn.execute(text("SELECT MAX(version) FROM cip_publication WHERE pub_code = :c"),
                                {"c": code}).scalar() or 0) + 1
        conn.execute(text(
            "INSERT INTO cip_publication (pub_code, version, pub_name, owner_email, definition, footnote,"
            " destination, status, published_at)"
            " VALUES (:code, :v, :name, :owner, :definition, :note, :dest, :status, CURRENT_TIMESTAMP)"),
            {"code": code, "v": version, "name": name[:255], "owner": owner,
             "definition": json.dumps(definition, sort_keys=True), "note": note[:2000],
             "dest": (destination or None) and destination[:1000], "status": "published"})
        pid = int(conn.execute(text("SELECT publication_id FROM cip_publication WHERE pub_code = :c AND version = :v"),
                               {"c": code, "v": version}).scalar())
        if cells:
            conn.execute(text(
                "INSERT INTO cip_publication_cell (publication_id, row_key, col_key, n, base_n, value)"
                " VALUES (:pid, :row_key, :col_key, :n, :base_n, :value)"),
                [{"pid": pid, **c} for c in cells])
    log.info("Published %s v%d: %d cells", code, version, len(cells))
    return pid


def list_publications() -> pd.DataFrame:
    return query_df(
        """
        SELECT p.publication_id, p.pub_code, p.version, p.pub_name, p.owner_email, p.definition,
               p.footnote, p.destination, p.status, p.published_at,
               (SELECT COUNT(*) FROM cip_publication_cell c WHERE c.publication_id = p.publication_id) AS cells
          FROM cip_publication p
         ORDER BY p.pub_code, p.version
        """
    )


def cells(publication_id: int) -> pd.DataFrame:
    return query_df(
        "SELECT row_key, col_key, n, base_n, value FROM cip_publication_cell"
        " WHERE publication_id = :p ORDER BY cell_id", {"p": publication_id})


def drift(publication_id: int) -> pd.DataFrame:
    """Frozen cells vs today, cell by cell: same, moved, missing or new.
    A definition that no longer resolves is reported, not raised."""
    columns = ["row_key", "col_key", "published", "now", "delta", "published_n", "now_n", "status", "detail"]
    raw = query_df("SELECT definition FROM cip_publication WHERE publication_id = :p", {"p": publication_id})
    stored = raw.definition.iloc[0]
    definition = json.loads(stored) if isinstance(stored, str) else stored
    try:
        now = {(c["row_key"], c["col_key"]): c for c in compute(definition)}
    except ValueError as exc:
        return pd.DataFrame([{**{c: None for c in columns}, "status": "error", "detail": str(exc)}], columns=columns)
    frozen = {(r.row_key, r.col_key): r for r in cells(publication_id).itertuples()}
    rows = []
    for key in list(frozen) + [k for k in now if k not in frozen]:
        was, cur = frozen.get(key), now.get(key)
        published = None if was is None or pd.isna(was.value) else float(was.value)
        current = None if cur is None else cur["value"]
        was_n = None if was is None or pd.isna(was.n) else int(was.n)
        if was is None:
            state = "new"
        elif cur is None:
            state = "missing"
        elif (published is None) != (current is None):
            state = "moved"                  # crossed the minimum base either way
        elif published is not None and abs(current - published) > TOLERANCE:
            state = "moved"
        elif was_n is not None and cur["n"] is not None and was_n != cur["n"]:
            state = "moved"                  # counts are exact
        else:
            state = "same"
        delta = None if published is None or current is None else round(current - published, 6) + 0.0
        rows.append({"row_key": key[0], "col_key": key[1], "published": published, "now": current,
                     "delta": delta, "published_n": was_n, "now_n": None if cur is None else cur["n"],
                     "status": state, "detail": ""})
    return pd.DataFrame(rows, columns=columns)


def drift_summary() -> pd.DataFrame:
    """One row per published publication: how many of its cells moved."""
    out = []
    for p in list_publications().itertuples():
        if p.status != "published":
            continue
        report = drift(int(p.publication_id))
        count = report.status.value_counts()
        out.append({"publication_id": p.publication_id, "pub_code": p.pub_code, "version": p.version,
                    "pub_name": p.pub_name, "published_at": p.published_at, "cells": int(p.cells),
                    **{s: int(count.get(s, 0)) for s in ("moved", "missing", "new", "error")}})
    return pd.DataFrame(out, columns=["publication_id", "pub_code", "version", "pub_name", "published_at",
                                      "cells", "moved", "missing", "new", "error"])


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s | %(message)s")
    ap = argparse.ArgumentParser(description="Publications: drift report")
    ap.add_argument("--drift", action="store_true", required=True, help="recompute every publication and compare")
    ap.parse_args()
    summary = drift_summary()
    for row in summary.itertuples():
        flag = "OK   " if row.moved + row.missing + row.new + row.error == 0 else "DRIFT"
        print(f"{flag} {row.pub_code} v{row.version}: {row.cells} cells — moved {row.moved}, "
              f"missing {row.missing}, new {row.new}, errors {row.error}")
    return 1 if (summary[["moved", "missing", "new", "error"]].to_numpy().sum() if not summary.empty else 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
