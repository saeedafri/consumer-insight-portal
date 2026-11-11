"""The retail databank: every retailer and sector, week by week, computed by the ETL so the portal only adds weeks up.

Who calls it: etl/publish.py write_views(), after every wave's respondent bitsets are written
(api/v1/waves/<id>/people.json.gz: for each answer, a bit per respondent who gave it; "0,0" is everyone asked). publish()
writes api/v1/retailers.json.gz, which the Retailers screen (frontend/src/screens/Retailers.tsx) reads: one retailer,
two or more side by side, one sector or two. nginx sends the file; the API route /api/v1/retailers is the fallback.

Counts, not percentages, one set per week: each week's respondents are different people, so any choice of weeks (one,
the last four, any twelve) is the sum of their counts, which the screen adds in the browser. Two markets:
  weekly   the weekly retailer questions (config/retailers.yml reach, asked of everyone): a retailer's shoppers bought
           from it in the past two weeks, food or nonfood; % of all respondents
  sectors  each sector's retailer question (config/sectors.yml tables: Retailers), asked of the sector's buyers in the
           weeks that ran the sector (its module tag): % of those buyers, and the sector's purchase rate
For each retailer and week: its shoppers and their split by gender, generation, household income, region and area
(config/retailers.yml profile); for each week, everyone's split for reference. Sentiment: the apparel grid (AP8), % positive
per week asked. Rules: config/retailers.yml and config/sectors.yml. Checked by tests/test_retailers.py.
"""
from __future__ import annotations

import gzip
import json
import re
from functools import lru_cache
from pathlib import Path

import yaml

from etl import weekly_report
from etl.weekly_report import read_waves

CONFIG = Path(__file__).resolve().parents[1] / "config"
CUTS = {"gender": "gender", "generation": "generation", "income": "income_band", "region": "census_region", "area": "urbanicity"}


@lru_cache(maxsize=1)
def settings() -> dict:
    """config/retailers.yml, and the sectors with a retailer table from config/sectors.yml."""
    rules = yaml.safe_load((CONFIG / "retailers.yml").read_text(encoding="utf-8"))
    sectors = yaml.safe_load((CONFIG / "sectors.yml").read_text(encoding="utf-8"))["sectors"]
    rules["sectors"] = [s for s in sectors if "Retailers" in s["tables"]]
    return rules


def key(label: str) -> str:
    """A retailer's name for matching across questions: letters and digits only ("T.J. Maxx" = "TJ Maxx")."""
    return re.sub(r"[^a-z0-9]", "", label.lower())


def read_people(path: Path) -> dict:
    """One week's respondent bitsets as ints: cuts {cut: {group: bits}}, questions {code: {rows, bits {(item, option): bits}}}."""
    doc = json.loads(gzip.decompress(path.read_bytes()))
    return {"cuts": {c: {g: int(h, 16) for g, h in groups.items()} for c, groups in doc["cuts"].items()},
            "questions": {q: {"rows": body["rows"], "bits": {tuple(map(int, k.split(","))): int(h, 16) for k, h in body["bits"].items()}}
                          for q, body in doc["questions"].items()}}


def profile(bits: int, cuts: dict) -> list[int]:
    """How many of `bits` fall in each group of config/retailers.yml profile, every dimension in order, one flat list."""
    out = []
    for dimension, groups in settings()["profile"].items():
        have = cuts.get(CUTS[dimension], {})
        out += [sum((bits & have.get(g, 0)).bit_count() for g in members) for members in groups.values()]
    return out


def answers(question: dict, skip: tuple) -> dict:
    """A multi-choice retailer question's answers: {retailer key: (name, bits)}, "None of these" and the like left out."""
    found = {}
    for item, option, label, *_ in question["rows"]:
        if label and not label.lower().startswith(skip):
            name, bits = found.get(key(label), (label, 0))
            found[key(label)] = (name, bits | question["bits"].get((item, option), 0))
    return found


def week_markets(wave: dict, people: dict) -> dict:
    """One week's markets: {market name: {asked, bought, shops {key: (name, {kind: bits})}}}; weekly first, then each
    sector the week ran (its module tag)."""
    rules, skip = settings(), tuple(weekly_report.settings()["leave_out_answers"])
    questions, out = people["questions"], {}
    asked, shops = 0, {}
    for kind, code in rules["reach"].items():   # food, nonfood
        if code in questions:
            asked |= questions[code]["bits"].get((0, 0), 0)
            for k, (name, bits) in answers(questions[code], skip).items():
                shops.setdefault(k, (name, {"food": 0, "nonfood": 0}))[1][kind] |= bits
    if asked:
        out["weekly"] = {"asked": asked, "bought": None, "shops": shops}
    for sector in rules["sectors"]:
        code = sector["tables"]["Retailers"]
        if sector["module"] not in (wave.get("modules") or []) or code not in questions:
            continue
        purchase = sector.get("purchase")
        bought = None
        if purchase and purchase["question"] in questions:
            q = questions[purchase["question"]]
            bought = sum((q["bits"].get((row[0], row[1]), 0) for row in q["rows"] if row[3] in purchase["codes"]), 0)
        out[sector["name"]] = {"asked": questions[code]["bits"].get((0, 0), 0), "bought": bought,
                               "everyone": (questions[purchase["question"]]["bits"].get((0, 0), 0) if bought is not None else None),
                               "shops": {k: (name, {"any": bits}) for k, (name, bits) in answers(questions[code], skip).items()}}
    return out


def sentiment(wave: dict, people: dict) -> dict:
    """{retailer key: [positive, asked]} from the week's apparel grid (config/retailers.yml sentiment), {} if not asked."""
    rules = settings()["sentiment"]
    aliases = {key(grid): key(weekly) for weekly, grid in settings()["aliases"].items()}
    grid = people["questions"].get(rules["question"])
    found = {}
    for item in {row[0] for row in grid["rows"]} if grid else ():
        rows = [row for row in grid["rows"] if row[0] == item]
        asked = 0
        for row in rows:
            asked |= grid["bits"].get((row[0], row[1]), 0)
        liked = sum(grid["bits"].get((row[0], row[1]), 0).bit_count() for row in rows if row[4] in rules["positive"])
        if asked:
            found[aliases.get(key(rows[0][2]), key(rows[0][2]))] = [liked, asked.bit_count()]
    return found


def build(people_by_week: list[tuple[dict, dict]]) -> dict:
    """The databank from (wave, people) pairs, oldest first. Weeks oldest first; each market lists the weeks it ran
    (indexes into weeks) and, per retailer, {week index: counts}: weekly [shoppers, food, nonfood, *profile], a sector
    [shoppers, *profile]. Retailers biggest first by their newest week."""
    rules = settings()
    weeks, markets, liked = [], {}, {}
    for wave, people in people_by_week:
        found = week_markets(wave, people)
        if not found:
            continue
        at = len(weeks)
        everyone = 0   # everyone asked anything the week's markets ask: all respondents in a weekly week
        for market in found.values():
            everyone |= market["asked"] | (market.get("everyone") or 0)
        weeks.append({"survey_id": wave["survey_id"], "date": wave["wave_date"], "n": everyone.bit_count(),
                      "profile": profile(everyone, people["cuts"])})
        for name, market in found.items():
            m = markets.setdefault(name, {"weeks": [], "asked": [], "bought": [], "buyers": [], "retailers": {}})
            m["weeks"].append(at)
            m["asked"].append(market["asked"].bit_count())
            m["bought"].append(market["bought"].bit_count() if market["bought"] is not None else None)
            m["buyers"].append(profile(market["asked"], people["cuts"]))   # who the market's base is (a sector's buyers)
            for k, (label, bits) in market["shops"].items():
                shop = m["retailers"].setdefault(k, {"name": label, "weeks": {}})
                shop["name"] = label   # the newest spelling
                kinds = [bits["food"] | bits["nonfood"], bits["food"], bits["nonfood"]] if name == "weekly" else [bits["any"]]
                shop["weeks"][at] = [b.bit_count() for b in kinds] + profile(kinds[0], people["cuts"])
        for k, figure in sentiment(wave, people).items():
            liked.setdefault(k, []).append([wave["wave_date"], *figure])
    order = ["weekly"] + [s["name"] for s in rules["sectors"]]
    out_markets = []
    for name in (n for n in order if n in markets):
        m = markets[name]
        newest = m["weeks"][-1]
        sector = next((s for s in rules["sectors"] if s["name"] == name), None)
        out_markets.append({"name": "Weekly retailers" if name == "weekly" else name, "sector": name != "weekly",
                            "base": "all respondents" if name == "weekly" else f"{name.lower()} shoppers asked",
                            "purchase": (sector.get("purchase") or {}).get("label") if sector else None,
                            "weeks": m["weeks"], "asked": m["asked"], "bought": m["bought"], "buyers": m["buyers"],
                            "retailers": [{"name": r["name"], "weeks": {str(w): c for w, c in r["weeks"].items()},
                                           "sentiment": liked.get(k) if name == "weekly" else None}
                                          for k, r in sorted(m["retailers"].items(), key=lambda kv: -(kv[1]["weeks"].get(newest) or [0])[0])]})
    return {"weeks": weeks, "groups": {d: list(g) for d, g in rules["profile"].items()}, "min_buyers": rules["min_buyers"],
            "pool": rules["pool"], "markets": out_markets}


def publish(out: Path, write) -> int:
    """Called by etl/publish.py write_views() once every wave's people file is written: api/v1/retailers.json.gz.
    Reads every weekly tracker week that has a people file (since Jul 2025, ~25 KB each). Returns the bytes written."""
    family, study = weekly_report.settings()["family"], weekly_report.settings()["study_type"]
    people_by_week = []
    for wave in read_waves(out, family, study):
        path = out / "api/v1/waves" / str(wave["survey_id"]) / "people.json.gz"
        if path.exists():
            people_by_week.append((wave, read_people(path)))
    return write(out / "api/v1/retailers", build(people_by_week))
