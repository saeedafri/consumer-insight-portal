"""Retailer comparison, computed by the ETL so the portal only has to show it.

Who calls it: etl/publish.py write_views(), after every wave's respondent bitsets are written
(api/v1/waves/<id>/people.json.gz: for each answer, a bit per respondent who gave it; "0,0" is everyone asked). publish()
writes api/v1/retailers.json.gz, which the Retailers screen (frontend/src/screens/Retailers.tsx) shows as it is; nginx
sends the file, the API route /api/v1/retailers is the fallback. No database.

For each of the latest weeks that asked the weekly retailer questions, every retailer named in them, pooled over that
week and the ones before it (config/retailers.yml pool), so small retailers have enough buyers to profile:
  reach      % of respondents who bought from it in the past two weeks: any product, food, nonfood
  profile    its buyers' split by gender, generation and household income, next to everyone's (counts are added
             across the pooled weeks: each week's respondents are different people)
  sentiment  % positive about it in the newest apparel week that asked (only the 28 apparel retailers of that grid)
Rules (questions, weeks, bands, aliases): config/retailers.yml. Checked by tests/test_retailers.py.
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


@lru_cache(maxsize=1)
def settings() -> dict:
    """config/retailers.yml."""
    return yaml.safe_load((CONFIG / "retailers.yml").read_text(encoding="utf-8"))


def key(label: str) -> str:
    """A retailer's name for matching across questions: letters and digits only ("T.J. Maxx" = "TJ Maxx")."""
    return re.sub(r"[^a-z0-9]", "", label.lower())


def read_people(path: Path) -> dict:
    """One week's respondent bitsets as ints: cuts {cut: {group: bits}}, questions {code: {rows, bits {(item, option): bits}}}."""
    doc = json.loads(gzip.decompress(path.read_bytes()))
    return {"cuts": {c: {g: int(h, 16) for g, h in groups.items()} for c, groups in doc["cuts"].items()},
            "questions": {q: {"rows": body["rows"], "bits": {tuple(map(int, k.split(","))): int(h, 16) for k, h in body["bits"].items()}}
                          for q, body in doc["questions"].items()}}


def week_figures(people: dict) -> dict | None:
    """One week's counts: everyone asked, and for each retailer (by key) its name and the bits of its food, nonfood and
    any buyers. None when the week asked neither retailer question."""
    rules, skip = settings(), tuple(weekly_report.settings()["leave_out_answers"])
    asked, shops = 0, {}
    for kind, code in rules["reach"].items():
        question = people["questions"].get(code)
        if not question:
            continue
        asked |= question["bits"].get((0, 0), 0)
        for item, option, label, *_ in question["rows"]:
            if label.lower().startswith(skip):
                continue
            shop = shops.setdefault(key(label), {"name": label, "food": 0, "nonfood": 0})
            shop[kind] |= question["bits"].get((item, option), 0)
    if not asked:
        return None
    for shop in shops.values():
        shop["any"] = shop["food"] | shop["nonfood"]
    return {"asked": asked, "shops": shops, "cuts": people["cuts"]}


def profile(bits: int, cuts: dict) -> dict:
    """How many of `bits` fall in each group of config/retailers.yml profile, {dimension: [count per group]}."""
    source = {"gender": "gender", "generation": "generation", "income": "income_band"}
    out = {}
    for dimension, groups in settings()["profile"].items():
        have = cuts.get(source[dimension], {})
        out[dimension] = [sum((bits & have.get(g, 0)).bit_count() for g in members) for members in groups.values()]
    return out


def add(total: dict | None, more: dict) -> dict:
    """Two profiles' counts added group by group."""
    return more if total is None else {d: [a + b for a, b in zip(total[d], more[d])] for d in more}


def percent(counts: dict, n: int) -> dict:
    """A profile's counts as % of n, one decimal."""
    return {d: [round(100 * c / n, 1) if n else None for c in values] for d, values in counts.items()}


def sentiment(people_by_week: list[tuple[dict, dict]]) -> dict:
    """{retailer key: {positive %, n, date}} from the newest week that asked the sentiment grid."""
    rules = settings()["sentiment"]
    aliases = {key(grid): key(weekly) for weekly, grid in settings()["aliases"].items()}
    for wave, people in reversed(people_by_week):
        grid = people["questions"].get(rules["question"])
        if not grid:
            continue
        found = {}
        for item in {row[0] for row in grid["rows"]}:
            rows = [row for row in grid["rows"] if row[0] == item]
            asked = 0
            for row in rows:
                asked |= grid["bits"].get((row[0], row[1]), 0)
            liked = sum(grid["bits"].get((row[0], row[1]), 0).bit_count() for row in rows if row[4] in rules["positive"])
            n = asked.bit_count()
            if n:
                name = key(rows[0][2])
                found[aliases.get(name, name)] = {"positive": round(100 * liked / n, 1), "n": n, "date": wave["wave_date"]}
        return found
    return {}


def build(people_by_week: list[tuple[dict, dict]]) -> dict:
    """The comparison from (wave, people) pairs, oldest first: the newest `weeks` weeks that asked the retailer
    questions, each pooled with the `pool` - 1 asking weeks before it. Weeks and figures are newest first."""
    rules = settings()
    weeks = [(wave, figures) for wave, people in people_by_week if (figures := week_figures(people))]
    shown = weeks[-rules["weeks"]:][::-1]
    names, out_weeks, everyone = {}, [], []
    reach, buyers, profiles = {}, {}, {}
    for wave, _ in shown:
        at = next(k for k, (w, _) in enumerate(weeks) if w["survey_id"] == wave["survey_id"])
        pooled = weeks[max(0, at - rules["pool"] + 1):at + 1]
        asked = sum(f["asked"].bit_count() for _, f in pooled)
        all_counts = None
        for _, f in pooled:
            all_counts = add(all_counts, profile(f["asked"], f["cuts"]))
        everyone.append(percent(all_counts, asked))
        out_weeks.append({"survey_id": wave["survey_id"], "date": wave["wave_date"], "from": pooled[0][0]["wave_date"],
                          "weeks": len(pooled), "respondents": asked})
        shops = {k for _, f in pooled for k in f["shops"]}
        for k in shops:
            names.setdefault(k, next(f["shops"][k]["name"] for _, f in reversed(pooled) if k in f["shops"]))
            counts = {kind: sum(f["shops"][k][kind].bit_count() for _, f in pooled if k in f["shops"]) for kind in ("any", "food", "nonfood")}
            reach.setdefault(k, {kind: [] for kind in counts})
            for kind, n in counts.items():
                reach[k][kind].append(round(100 * n / asked, 1) if asked else None)
            buyers.setdefault(k, []).append(counts["any"])
            mix = None
            for _, f in pooled:
                if k in f["shops"]:
                    mix = add(mix, profile(f["shops"][k]["any"], f["cuts"]))
            profiles.setdefault(k, []).append(percent(mix, counts["any"]) if counts["any"] >= rules["min_buyers"] else None)
        for k in reach:   # a retailer this pooled week did not name: no figures for it
            if k not in shops:
                for kind in reach[k]:
                    reach[k][kind].append(None)
                buyers[k].append(0)
                profiles[k].append(None)
    liked = sentiment(people_by_week)
    return {"weeks": out_weeks, "groups": {d: list(g) for d, g in rules["profile"].items()}, "everyone": everyone,
            "min_buyers": rules["min_buyers"],
            "retailers": [{"name": names[k], "reach": reach[k], "buyers": buyers[k], "profile": profiles[k], "sentiment": liked.get(k)}
                          for k in sorted(reach, key=lambda k: reach[k]["any"][0] or 0, reverse=True)]}


def publish(out: Path, write) -> int:
    """Called by etl/publish.py write_views() once every wave's people file is written: api/v1/retailers.json.gz.
    Reads only the weeks the comparison can use (the newest weeks + pool, and back to the newest apparel week for
    sentiment). Returns the bytes written."""
    family, study = weekly_report.settings()["family"], weekly_report.settings()["study_type"]
    waves = read_waves(out, family, study)
    people_by_week = []
    for wave in waves[-(settings()["weeks"] + settings()["pool"] + 26):]:   # 26 more: an apparel week within half a year
        path = out / "api/v1/waves" / str(wave["survey_id"]) / "people.json.gz"
        if path.exists():
            people_by_week.append((wave, read_people(path)))
    return write(out / "api/v1/retailers", build(people_by_week))
