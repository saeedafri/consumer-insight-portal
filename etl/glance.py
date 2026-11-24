"""Home's "This week at a glance": six cards from the newest weekly tracker wave, picked by the ETL so Home only draws.

Who calls it: etl/publish.py write_views, after the wave books, the topic dashboards, the weekly report and the sector
tables are written. build() picks from those published files (no database); publish() writes api/v1/glance.json.gz,
which Home (frontend/src/screens/Home.tsx) shows as it is. The API route /api/v1/glance is the fallback when nginx is
absent.

The six cards, as the research team laid them out (call of 23 Nov 2026), in two rows of three:
  row one   the week's sector (etl/sectors.py): its leading retailer and its top product or category; then what is new
            this week: a one-off or event module (a retro, such as Singles Day), else a monthly or seasonal topic's
            dashboard (financial health, the holiday tracker), else the sector's median spend
  row two   the biggest significant three-month change of the weekly report in food, nonfood, in store or online
            (etl/weekly_report.py three_points), the category with the widest gap between buying in a store and online
            this week, and the personal-finances outlook (net better) against the week before, with the share whose
            utility bills went up
Every card names where it comes from in a badge (the sector, "New this week", "Monthly topic"…) and carries change
badges like the at-a-glance tiles the research team pointed to ("vs LY", "vs last week"), where the figure has an
earlier one. A card whose figures the week lacks is null, so the other cards keep their row. Which questions:
config/glance.yml.
Checked by tests/test_glance.py.
"""
from __future__ import annotations

import gzip
import json
import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

import yaml

from api.dashboards import load_config as dashboard_config
from etl import survey_calendar, weekly_report
from etl.weekly_report import read_waves

CONFIG = Path(__file__).resolve().parents[1] / "config" / "glance.yml"


@lru_cache(maxsize=1)
def settings() -> dict:
    """config/glance.yml: the in-store and online questions and the weekly report's outlook line."""
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


def sector_card(sector: dict, kind: str) -> dict | None:
    """One of the sector's own cards (etl/sectors.py newest_cards: "leader", "product", "spend"), named with the sector
    and opening its tab of the Sector databank.

    Every card of this file: badge, title, value, note, change badges ({d, label, flags}), the screen it opens, and the
    menu that screen needs (config/access.yml), so Home links only to screens this person may open."""
    found = next((c for c in sector["cards"] if c["kind"] == kind), None)
    tab = f"&tab={quote(found['tab'])}" if found and found["tab"] else ""
    return found and {"badge": sector["name"], "title": found["title"], "value": found["value"], "note": found["note"],
                      "changes": found["changes"], "link": f"/sectors?sector={quote(sector['name'])}{tab}", "feature": "sectors"}


def event_card(wave: dict, book: dict) -> dict | None:
    """A one-off or event module of this week (a retro, Singles Day), not a sector, topic or season: its first
    question's biggest answer other than a "No" (a highlight says what people did). Only modules the book names as a
    section of their own (some come as "HW block")."""
    calendar = survey_calendar.load_config()
    regular = {m["name"].lower() for kind in ("sectors", "topics", "seasonal") for m in calendar[kind]}
    skip = tuple(weekly_report.settings()["leave_out_answers"])
    for module in wave.get("modules") or []:
        asked = [q for q in book["questions"] if q["section"].lower() == module.lower() and "coded" not in q]
        if module.lower() in regular or not asked:
            continue
        rows = [r for r in asked[0]["groups"][0]["rows"] if r.get("Total") is not None
                and not r["label"].lower().startswith(skip) and not re.match(r"no\b", r["label"], re.I)]
        if rows:
            top = max(rows, key=lambda r: r["Total"])
            question = asked[0]["text"].split("?")[0] + "?"
            return dict(badge="New this week", title=module, value=f"{top['Total']:.1f}%", note=f"{top['label']}: {question}",
                        changes=[], link=f"/w/{wave['survey_id']}/questions/{asked[0]['id']}", feature="explorer")
    return None


def topic_card(wave: dict, dashboards: dict[str, dict]) -> dict | None:
    """A monthly topic's dashboard of this week (financial health, tariffs…), else a seasonal one (the holiday
    tracker): its first highlight (a list's #1), else its first tile. Sector dashboards are row one's already."""
    modules = {code: d["module"] for code, d in dashboard_config().items()}
    calendar = survey_calendar.load_config()
    topics, sectors = ({m["code"] for m in calendar[kind]} for kind in ("topics", "sectors"))
    others = [c for c in dashboards if modules.get(c) not in sectors]
    for code in sorted(others, key=lambda c: modules.get(c) not in topics):   # monthly topics first, then seasonal ones
        board, link = dashboards[code], f"/trackers/{code}?w={wave['survey_id']}"
        badge = "Monthly topic" if modules.get(code) in topics else "Seasonal"
        prior = f"vs {(board.get('prior_label') or 'prior week').removeprefix('the ')}"

        def moves(m: dict) -> list[dict]:   # the tile's own badges, as its tracker page shows them
            return [{"d": m["vs_ly"], "label": "vs LY", "flags": m["flags"]}, {"d": m["vs_prior"], "label": prior, "flags": m["flags"]}]
        for h in board.get("highlights") or []:
            top = (board["lists"].get(h["list"]) or [None])[0]
            if top and top["pct"] is not None:
                return dict(badge=badge, title=f"{board['title']}: {h['title']}", value=top["label"], note=f"{top['pct']:.1f}% {h['of']}",
                            changes=moves(top), link=link, feature=f"tracker_{code}")
        tiles = {t["code"]: t for t in dashboard_config()[code]["tiles"]}
        for key, m in board["tiles"].items():
            if m and m["pct"] is not None:
                return dict(badge=badge, title=f"{board['title']}: {board.get('tile_labels', {}).get(key, key)}", value=f"{m['pct']:.1f}%",
                            note=tiles[key]["say"] if key in tiles else "", changes=moves(m), link=link, feature=f"tracker_{code}")
    return None


def change_card(wave: dict, report: dict | None) -> dict | None:
    """The weekly report's biggest significant three-month change (four-week averages) in food, nonfood, in store or
    online (config/glance.yml change_sections)."""
    point = report and next((p for p in report.get("three_points") or [] if p["section"] in settings()["change_sections"]), None)
    return point and dict(badge="Weekly report", title=f"Biggest change: {point['section']}", value=f"{point['change']:+.1f} pts",
                          note=f"{point['label']}: {point['from']:.1f}% to {point['to']:.1f}% over three months (four-week averages), a significant change",
                          changes=[], link=f"/w/{wave['survey_id']}/report", feature="report")


def gap_card(wave: dict, book: dict) -> dict | None:
    """The category with the widest gap between buying in a store and online this week. The online list may add a note
    to an answer ("Books, movies, music or video games (incl. digital purchases)"): that is the same category."""
    questions = {q["id"]: q for q in book["questions"]}
    store, online = questions.get(settings()["in_store"]), questions.get(settings()["online"])
    if not store or not online:
        return None
    skip = tuple(weekly_report.settings()["leave_out_answers"])
    web = [r for r in online["groups"][0]["rows"] if r.get("Total") is not None]
    pairs = []
    for row in store["groups"][0]["rows"]:
        twin = next((r for r in web if r["label"] == row["label"] or r["label"].startswith(f"{row['label']} (")), None)
        if twin and row.get("Total") is not None and not row["label"].lower().startswith(skip):
            pairs.append((row, twin))
    if not pairs:
        return None
    row, twin = max(pairs, key=lambda p: abs(p[0]["Total"] - p[1]["Total"]))
    asked_before = row.get("prior") is not None and twin.get("prior") is not None and "wording_changed_prior" not in row["flags"] + twin["flags"]
    gap = row["Total"] - twin["Total"]
    moved = [{"d": round(gap - (row["prior"] - twin["prior"]), 1), "label": "vs last week"}] if asked_before else []
    return dict(badge="In store vs online", title="Widest gap: in store vs online", value=row["label"],
                note=f"{row['Total']:.1f}% bought in a store, {twin['Total']:.1f}% online, past two weeks: a gap of {abs(gap):.1f} pts",
                changes=moved, link=f"/channels?w={wave['survey_id']}&c={quote(row['label'])}", feature="channels")


def outlook_card(wave: dict, report: dict | None, book: dict) -> dict | None:
    """The personal-finances outlook this week: % better minus % worse over the next 12 months, the week before, and
    the share who say a bill went up in the past year (config/glance.yml bills: utilities, from q6)."""
    line = report and report.get("sentiment", {}).get(settings()["outlook"])
    if not line or wave["wave_date"] not in line["dates"]:
        return None
    at = line["dates"].index(wave["wave_date"])
    weekly = line["lines"]["Total"]["weekly"]
    if weekly[at] is None:
        return None
    before = [{"d": round(weekly[at] - weekly[at - 1], 1), "label": "vs last week"}] if at and weekly[at - 1] is not None else []
    bills = settings()["bills"]
    asked = next((q for q in book["questions"] if q["id"] == bills["question"]), None)
    group = asked and next((g for g in asked["groups"] if g["label"] == bills["group"]), None)
    rose = group and sum(r["Total"] or 0 for r in group["rows"] if "increase" in r["label"].lower())
    went_up = f". {rose:.1f}% say {bills['group'].lower()} went up in the past year" if rose else ""
    return dict(badge="Consumer sentiment", title=f"{settings()['outlook']} outlook", value=f"{weekly[at]:+.1f}",
                note=f"net better: % expecting better minus % worse, next 12 months{went_up}", changes=before,
                link=f"/w/{wave['survey_id']}/report", feature="report")


def build(wave: dict, book: dict, sectors: list[dict], report: dict | None, dashboards: dict[str, dict]) -> dict:
    """The six cards of `wave` (the newest weekly tracker wave) from its book, the sector tables, its weekly report and
    its dashboards (code → published dashboard). The week's sector: the one whose newest survey is this wave; when two
    share it, the one the title names first (Off-price leads "inc Off Price + Dollar Stores")."""
    title = re.sub(r"[^a-z]", "", wave.get("title", "").lower())

    def named_at(sector: dict) -> int:   # where the title names the sector, letters only; not named: after everything
        at = title.find(re.sub(r"[^a-z]", "", sector["name"].lower()))
        return at if at >= 0 else len(title)
    sector = min((s for s in sectors if s["waves"] and s["waves"][-1]["survey_id"] == wave["survey_id"]), key=named_at, default=None)
    found = [sector and sector_card(sector, "leader"), sector and sector_card(sector, "product"),
             event_card(wave, book) or topic_card(wave, dashboards) or (sector and sector_card(sector, "spend")),
             change_card(wave, report), gap_card(wave, book), outlook_card(wave, report, book)]
    return {"survey_id": wave["survey_id"], "wave_date": wave["wave_date"], "respondents": wave["qualified_n"],
            "sector": sector and sector["name"], "cards": [c or None for c in found]}


def publish(out: Path, write) -> int:
    """Called by etl/publish.py write_views once the books, dashboards, weekly reports and sector tables are written:
    api/v1/glance.json.gz for the newest weekly tracker wave with results. Returns the bytes written (0: none yet)."""
    family, study = weekly_report.settings()["family"], weekly_report.settings()["study_type"]
    waves = [w for w in read_waves(out, family, study) if w.get("rows_built") != 0]
    files = out / "api/v1"

    def read(path: Path) -> dict | None:   # a published file, or None when this version has none
        return json.loads(gzip.decompress(path.read_bytes())) if path.exists() else None
    wave = waves[-1] if waves else None
    book = wave and read(files / "waves" / str(wave["survey_id"]) / "book.json.gz")
    if not (book and book.get("questions")):   # no wave yet, or a broken book: the publish's gates judge it, not this
        return 0
    dashboards = {code: board for code in wave.get("dashboards") or []
                  if (board := read(files / "dashboards" / code / f"{wave['survey_id']}.json.gz"))}
    sectors = (read(files / "sectors.json.gz") or {}).get("sectors", [])
    report = read(files / "waves" / str(wave["survey_id"]) / "report.json.gz")
    return write(files / "glance", build(wave, book, sectors, report, dashboards))
