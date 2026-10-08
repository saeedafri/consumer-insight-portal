"""The weekly tracker's line-by-line table — what the data team built by hand.

Every week the team pasted each wave's raw export under one header row
("Weekly Line-By-Line Survey Data.xlsx", 36 waves, Feb–Sep 2026): qualified
respondents only, the core questions (q1–q5, CS1–CS2, D1–D8) as labelled
columns, plus Month, Age Range and Generation. The ETL builds the same rows
for every tracker wave it loads (cip_tracker_line), so the export and any page
reading it need no processing. The column list is config/tracker_line.yml.

    python -m etl.tracker_line --compare "Weekly Line-By-Line Survey Data.xlsx"
"""
from __future__ import annotations

import argparse
import html
import json
import logging
import sys
from collections import Counter
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional, Sequence

import pandas as pd
import yaml
from sqlalchemy import bindparam, text

from app.core.database import get_engine

log = logging.getLogger("cip.tracker_line")
CONFIG = Path(__file__).resolve().parents[1] / "config" / "tracker_line.yml"


@lru_cache(maxsize=1)
def load_config() -> dict:
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


def _stamp(value: Any) -> Optional[str]:
    if not value:
        return None
    if not isinstance(value, datetime):
        value = datetime.fromisoformat(str(value)[:19])
    return value.strftime("%m/%d/%Y %H:%M")


def _month(value: Any) -> Optional[str]:
    return str(value)[:7] + "-01" if value else None


def build(survey_id: int) -> int:
    """Rebuild one wave's lines (three reads, one batched insert). Waves
    outside the tracker family get none."""
    with get_engine("etl").begin() as conn:
        conn.execute(text("DELETE FROM cip_tracker_line WHERE survey_id = :s"), {"s": survey_id})
        rows = [{"rid": rid, "s": survey_id, "w": wave, "line": json.dumps(line, ensure_ascii=False)}
                for rid, wave, line in lines(conn, survey_id)]
        if rows:
            conn.execute(text("INSERT INTO cip_tracker_line (respondent_id, survey_id, wave_date, line)"
                              " VALUES (:rid, :s, :w, :line)"), rows)
    return len(rows)


def lines(conn, survey_id: int) -> list[tuple[int, Any, dict]]:
    """(respondent_id, wave_date, line) for each qualified respondent — reads only."""
    cfg = load_config()
    labels, columns = cfg.get("labels") or {}, cfg["columns"]
    codes = [c["qcode"] for c in columns if c.get("qcode")]
    family, wave_date = conn.execute(text(
        "SELECT survey_family, wave_date FROM cip_survey WHERE survey_id = :s"), {"s": survey_id}).one()
    if family != cfg["family"]:
        return []
    items: dict[str, list[str]] = {}
    for qcode, item in conn.execute(text(
            "SELECT q.qcode, i.item_label FROM cip_item i JOIN cip_question q ON q.question_id = i.question_id"
            " WHERE q.survey_id = :s AND q.is_multi = 1 AND q.qcode IN :codes ORDER BY q.qcode, i.sort_order")
            .bindparams(bindparam("codes", expanding=True)), {"s": survey_id, "codes": codes}):
        items.setdefault(qcode, []).append(item)
    answers: dict[int, dict] = {}
    for rid, qcode, multi, item, code, label, number, said in conn.execute(text("""
            SELECT a.respondent_id, q.qcode, q.is_multi, i.item_label, a.value_code, a.value_label,
                   a.value_number, a.value_text
              FROM cip_answer a
              JOIN cip_field f ON f.field_id = a.field_id
              JOIN cip_question q ON q.question_id = f.question_id AND q.qcode IN :codes
              LEFT JOIN cip_item i ON i.item_id = f.item_id
             WHERE a.survey_id = :s""").bindparams(bindparam("codes", expanding=True)),
            {"s": survey_id, "codes": codes}):
        mine = answers.setdefault(rid, {})
        if multi:
            mine[(qcode, item)] = item if code == 1 else None
        else:
            value = said if said is not None else label if label is not None else number
            mine[qcode] = int(value) if isinstance(value, str) and value.isdigit() else value
    rows = []
    for rid, done, band, generation in conn.execute(text(
            "SELECT r.respondent_id, r.completed_at, p.age_band, p.generation FROM cip_respondent r"
            " LEFT JOIN cip_profile p ON p.respondent_id = r.respondent_id"
            " WHERE r.survey_id = :s AND r.is_qualified = 1 ORDER BY r.completed_at, r.record_no"),
            {"s": survey_id}):
        derived = {"wave_month": _month(wave_date), "completed_at": _stamp(done),
                   "age_band": labels.get(band, band), "generation": labels.get(generation, generation)}
        mine, line = answers.get(rid, {}), {}
        for c in columns:
            if c.get("from"):
                line[c["header"]] = derived[c["from"]]
            elif c.get("prefix"):
                for item in items.get(c["qcode"], []):
                    line[c["prefix"] + item] = mine.get((c["qcode"], item))
            else:
                line[c["header"]] = mine.get(c["qcode"])
        rows.append((rid, wave_date, line))
    return rows


def read(survey_ids: Sequence[int], role: str = "app") -> pd.DataFrame:
    """The lines of these waves, in the team's column order (one indexed read)."""
    with get_engine(role).connect() as conn:
        lines = [json.loads(x) for (x,) in conn.execute(text(
            "SELECT line FROM cip_tracker_line WHERE survey_id IN :ids ORDER BY wave_date, respondent_id")
            .bindparams(bindparam("ids", expanding=True)), {"ids": list(survey_ids) or [-1]})]
    order: list[str] = []
    for c in load_config()["columns"]:
        if c.get("prefix"):
            seen = dict.fromkeys(k for line in lines for k in line if k.startswith(c["prefix"]))
            order += [k for k in seen if k not in order]
        else:
            order.append(c["header"])
    return pd.DataFrame(lines, columns=order) if lines else pd.DataFrame()


def _wave(stamp: Any) -> date:
    day = pd.to_datetime(stamp, format="%m/%d/%Y %H:%M").date()
    return date.fromordinal(day.toordinal() - day.weekday())


def _counts(values: pd.Series) -> Counter:
    """Value counts, HTML entities decoded (the team's sheet keeps "Stop &amp; Shop")."""
    return Counter(html.unescape(str(v)).strip() for v in values if pd.notna(v) and str(v).strip() != "")


def compare(team: pd.DataFrame, ours: pd.DataFrame) -> list[str]:
    """Every wave both hold: same respondents, and every column the same count
    of every value. (Rows cannot be paired one to one — the team file keys them
    on the panel session id, which the warehouse never stores.)"""
    team, ours = team.copy(), ours.copy()
    by_case = {c.lower(): c for c in ours.columns}          # the team's "baby Toiletries" header
    team = team.rename(columns=lambda c: by_case.get(str(c).lower(), c))
    if "Month" in team:
        team["Month"] = pd.to_datetime(team["Month"]).dt.strftime("%Y-%m-%d")
    team["_wave"], ours["_wave"] = team["date"].map(_wave), ours["date"].map(_wave)
    problems = []
    for wave in sorted(set(team["_wave"]) & set(ours["_wave"])):
        a, b = team[team["_wave"] == wave], ours[ours["_wave"] == wave]
        if len(a) != len(b):
            problems.append(f"{wave}: respondents — team {len(a)}, ETL {len(b)}")
        for col in [c for c in b.columns if c != "_wave"]:
            if col not in a.columns:
                if _counts(b[col]):
                    problems.append(f"{wave}: column '{col}' only in the ETL")
                continue
            ta, tb = _counts(a[col]), _counts(b[col])
            if ta != tb:
                diff = {k: (ta.get(k, 0), tb.get(k, 0)) for k in set(ta) | set(tb) if ta.get(k, 0) != tb.get(k, 0)}
                problems.append(f"{wave}: {col} — team vs ETL {dict(list(diff.items())[:4])}")
        problems += [f"{wave}: column '{c}' only in the team file" for c in a.columns
                     if c not in b.columns and c not in ("_wave", "session") and _counts(a[c])]
    return problems


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s | %(message)s")
    ap = argparse.ArgumentParser(description="The tracker's line-by-line table")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--compare", metavar="XLSX", help="the team's workbook (read only)")
    group.add_argument("--rebuild", action="store_true", help="rebuild every verified tracker wave")
    args = ap.parse_args()
    with get_engine("etl").connect() as conn:
        waves = dict(conn.execute(text(
            "SELECT s.survey_id, s.wave_date FROM cip_survey s"
            " JOIN cip_forsta_survey r ON r.survey_id = s.survey_id AND r.load_state = 'loaded'"   # API loads only
            " WHERE s.load_status = 'verified' AND s.survey_family = :f"), {"f": load_config()["family"]}).all())
    if args.rebuild:
        log.info("Built %d lines over %d waves", sum(build(s) for s in waves), len(waves))
        return 0
    team = pd.read_excel(args.compare, sheet_name="Raw Data")
    wanted = set(team["date"].map(_wave))
    with get_engine("etl").connect() as conn:          # computed fresh from the answers: reads only
        fresh = [line for sid, day in waves.items() if day in wanted for _, _, line in lines(conn, sid)]
    ours = pd.DataFrame(fresh)
    shared = sorted(set(team["date"].map(_wave)) & set(ours["date"].map(_wave)))
    problems = compare(team, ours)
    print(f"{len(shared)} waves in both: {', '.join(map(str, shared))}")
    print("\n".join(problems) or "every wave matches the team's file")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
