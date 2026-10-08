"""The survey calendar — what each Forsta survey is and when it ran.

Built from the register (cip_forsta_survey) after every discovery and every
load, so it covers hibernated and unloaded surveys too: one row per survey ×
module in cip_wave_module. A module is found from the survey title; once the
wave is loaded, a seasonal tracker is found from its own questions instead
(titles miss it: the Sep 28 2026 wave says only "Holiday", yet carries the
holiday tracker). Seasonal waves are numbered within their season, which is
what "wave 2 vs last year's wave 2" compares. Rules: config/survey_calendar.yml.

    python -m etl.survey_calendar            # the calendar and the next 12 expected lead sectors
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Optional

import yaml
from sqlalchemy import text

from app.core.database import get_engine

CONFIG = Path(__file__).resolve().parents[1] / "config" / "survey_calendar.yml"


@lru_cache(maxsize=1)
def load_config() -> dict:
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


def season(day: Optional[date]) -> Optional[int]:
    if day is None:
        return None
    return day.year if day.month >= load_config()["season_starts_month"] else day.year - 1


def next_sector(code: str) -> str:
    order = [s["code"] for s in load_config()["sectors"]]
    return order[(order.index(code) + 1) % len(order)]


def _slug(text_: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", text_.upper()).strip("_")[:40] or "OTHER"


def classify(title: str, questions: Iterable[str] = (), tags: Iterable[str] = ()) -> list[dict]:
    """[{code, name, kind, is_lead}] for one survey. kind: sector, topic,
    seasonal, event (a one-off "+ X" in a tracker title), annual, adhoc."""
    cfg = load_config()
    title = " ".join(str(title or "").split())
    found: dict[str, dict] = {}

    def add(code, name, kind, lead=False):
        found.setdefault(code, {"code": code, "name": name, "kind": kind, "is_lead": lead})

    is_tracker = " - inc " in title or "weekly consumer tracker" in {str(t).lower() for t in tags}
    if not is_tracker:
        rule = next((a for a in cfg["annual"] if re.search(a["title"], title, re.I)), None)
        if rule:
            add(rule["code"], rule["name"], "annual")
        else:
            add(_slug(re.sub(r"\b(19|20)\d{2}\b", "", title)), title, "adhoc")
        return list(found.values())
    parts = [p.strip() for p in title.split(" - inc ", 1)[-1].split("+") if p.strip()]
    for i, part in enumerate(parts):
        hit = False
        for kind in ("sectors", "seasonal", "topics"):
            for rule in cfg[kind]:
                if re.search(rule["title"], part, re.I):
                    add(rule["code"], rule["name"], {"sectors": "sector", "seasonal": "seasonal", "topics": "topic"}[kind],
                        lead=i == 0 and kind == "sectors")
                    hit = True
        if not hit:
            add(_slug(re.sub(r"\bretro\b", "", part, flags=re.I)), part, "event")
    for rule in cfg["seasonal"]:
        if any(re.search(rule["question"], q, re.I) for q in questions):
            add(rule["code"], rule["name"], "seasonal")
    return list(found.values())


def _day(value: Any) -> Optional[date]:
    if not value:
        return None
    return value.date() if isinstance(value, datetime) else datetime.fromisoformat(str(value)[:19]).date()


def rebuild(conn=None) -> int:
    """Rewrite cip_wave_module from the register (and the loaded waves'
    questions), in the caller's transaction when given."""
    if conn is None:
        with get_engine("etl").begin() as own:
            return rebuild(own)
    patterns = [r["question"] for r in load_config()["seasonal"]]
    register = conn.execute(text(
        "SELECT forsta_path, title, tags, launched_at, created_on, survey_id FROM cip_forsta_survey")).all()
    asked: dict[int, list[str]] = defaultdict(list)
    for sid, qtext in conn.execute(text(
            "SELECT q.survey_id, q.qtext FROM cip_question q JOIN cip_forsta_survey r ON r.survey_id = q.survey_id")):
        if any(re.search(p, qtext or "", re.I) for p in patterns):
            asked[sid].append(qtext)
    rows = []
    for path, title, tags, launched, created, sid in register:
        day = _day(launched)
        for m in classify(title, asked.get(sid, ()), (tags or "").split(", ")):
            rows.append({"path": path, "code": m["code"], "name": m["name"][:120], "kind": m["kind"],
                         "lead": 1 if m["is_lead"] else 0, "day": day, "sid": sid,
                         "season": season(day) if m["kind"] in ("seasonal", "annual") else None,
                         "by": "questions" if sid in asked and m["kind"] == "seasonal" else "title"})
    counter: dict[tuple, int] = defaultdict(int)
    for r in sorted(rows, key=lambda r: (r["day"] is None, r["day"] or date.max, r["path"])):
        if r["day"] is not None:
            counter[(r["code"], r["season"])] += 1
            r["no"] = counter[(r["code"], r["season"])]
        else:
            r["no"] = None
    conn.execute(text("DELETE FROM cip_wave_module"))
    if rows:
        conn.execute(text(
            "INSERT INTO cip_wave_module (forsta_path, module_code, module_name, kind, is_lead, launched_on, season,"
            " series_wave_no, survey_id, detected_by)"
            " VALUES (:path, :code, :name, :kind, :lead, :day, :season, :no, :sid, :by)"), rows)
    return len(rows)


def main() -> int:
    with get_engine("etl").connect() as conn:
        rows = conn.execute(text(
            "SELECT w.launched_on, w.module_code, w.kind, w.is_lead, w.season, w.series_wave_no, r.load_state"
            " FROM cip_wave_module w JOIN cip_forsta_survey r ON r.forsta_path = w.forsta_path"
            " ORDER BY w.launched_on, w.is_lead DESC")).all()
    for r in rows:
        print(f"{r[0]}  {'*' if r[3] else ' '} {r[1]:<22} {r[2]:<9} {r[4] or '':<5} #{r[5] or '':<3} {r[6]}")
    leads = [r for r in rows if r[3] and r[0]]
    if leads:
        last_day, code = leads[-1][0], leads[-1][1]
        print("\nNext lead sectors:")
        for week in range(1, 13):
            code = next_sector(code)
            print(f"  {last_day + timedelta(weeks=week)}  {code}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
