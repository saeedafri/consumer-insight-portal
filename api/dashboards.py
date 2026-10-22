"""Backend (not ETL): shape the ETL's serving tables into one sample dashboard's screen payload.

The ETL ends at the serving tables (etl/serving.py, sql/005_serving.sql); it knows nothing about screens.
This backend job reads the few serving rows one screen needs, picks its comparison weeks from the
season calendar, writes the screen's key-takeaway sentences, and stores the finished JSON (gzipped) in
the backend's own cache tables (sql/006_dashboards.sql). The API holds those bytes in memory.
The dashboard definition is config/dashboards.yml.

    python -m api.dashboards --build holiday_tracker            # every loaded wave of the series
    python -m api.dashboards --build holiday_tracker --survey 412
    python -m api.dashboards --show holiday_tracker --survey 412
    python -m api.dashboards --check                            # tile codes mean the same in every wave
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import logging
import math
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml
from sqlalchemy import bindparam, text

from app.core.database import get_engine
from app.data.payloads import HIDDEN_BASE, TEST_BASE

log = logging.getLogger("cip.api.dashboards")
CONFIG = Path(__file__).resolve().parents[1] / "config" / "dashboards.yml"
BASE_SHIFT = 10.0   # points: a question's base share of qualified respondents moving more than this is a routing change


@lru_cache(maxsize=1)
def load_config() -> dict:
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


def series(conn, module: str) -> list[dict]:
    """Every wave of the module, loaded or not (hibernated waves have no survey_id)."""
    rows = [dict(r) for r in conn.execute(text(
        "SELECT w.forsta_path, w.season, w.series_wave_no, w.launched_on, s.survey_id, s.wave_label,"
        "       (SELECT SUM(r.is_qualified) FROM cip_respondent r WHERE r.survey_id = s.survey_id) AS qualified"
        "  FROM cip_wave_module w"
        "  LEFT JOIN cip_forsta_survey f ON f.forsta_path = w.forsta_path"
        "  LEFT JOIN cip_survey s ON s.survey_id = f.survey_id AND s.load_status = 'verified'"
        " WHERE w.module_code = :m AND w.launched_on IS NOT NULL ORDER BY w.launched_on"), {"m": module}).mappings()]
    for r in rows:   # MySQL returns a date, SQLite a string
        r["launched_on"] = date.fromisoformat(str(r["launched_on"])[:10])
    return rows


LY_RULES = ("same_wave_number", "same_calendar_week", "nearest_year_ago")


def comparisons(waves: list[dict], wave: dict, ly_rule: str = "same_calendar_week") -> tuple[Optional[dict], Optional[dict]]:
    """Prior: the previous wave of the module (same season for seasonal ones). Last year, by the module's rule:
      same_wave_number    wave N of last season (the business team's Databank: wave 3 2026 vs wave 3 2025)
      same_calendar_week  the wave launched in the same calendar week one year earlier (±3 days)
      nearest_year_ago    the wave launched closest to one year earlier, within a month (monthly topic modules)
    Loaded or not — so a missing one is reported, not skipped."""
    if ly_rule not in LY_RULES:
        raise ValueError(f"ly_rule must be one of {LY_RULES}")
    prior = next((w for w in waves if w["season"] == wave["season"]
                  and w["series_wave_no"] == wave["series_wave_no"] - 1), None)
    target = wave["launched_on"] - timedelta(days=364)
    if ly_rule == "same_wave_number":
        ly = next((w for w in waves if w["season"] == wave["season"] - 1 and w["series_wave_no"] == wave["series_wave_no"]), None)
    elif ly_rule == "same_calendar_week":
        ly = next((w for w in waves if abs((w["launched_on"] - target).days) <= 3), None)
    else:
        near = [w for w in waves if abs((w["launched_on"] - target).days) <= 31]
        ly = min(near, key=lambda w: abs((w["launched_on"] - target).days), default=None)
    return prior, ly


def significant(p1: float, n1: int, p2: float, n2: int) -> bool:
    """Two-sided two-proportion z-test at 95% (percentages in, as web/src/stats.ts); never with under TEST_BASE a side."""
    if not n1 or not n2 or min(n1, n2) < TEST_BASE:
        return False
    a, b = p1 / 100, p2 / 100
    pooled = (a * n1 + b * n2) / (n1 + n2)
    se = math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2))
    return se > 0 and math.erfc(abs(a - b) / se / math.sqrt(2)) < 0.05


def cells(conn, survey_ids: list[int], qcodes: list[str], dims: list[str], aliases: Optional[dict] = None) -> dict:
    """{(survey_id, qcode, dim, dim_value): {"base": n, "built_at": ts, "answers": {code-or-label: n}}},
    read from the ETL's serving rows: one primary-key range per wave, no joins. `aliases` maps an older code
    of the same question to the configured one (Social commerce: SM1 in Feb 2026, SC1 otherwise)."""
    aliases = aliases or {}
    qcodes = list(qcodes) + [old for old, new in aliases.items() if new in qcodes]
    out: dict = {}
    if not survey_ids:
        return out
    rows = conn.execute(text(
        "SELECT r.survey_id, r.qcode, r.dim, r.dim_value, r.n, r.base_n, w.built_at,"
        "       COALESCE(CAST(r.option_code AS CHAR), r.item_label) AS answer"
        "  FROM srv_result r JOIN srv_wave w ON w.survey_id = r.survey_id"
        " WHERE r.survey_id IN :s AND r.qcode IN :q AND r.dim IN :d")
        .bindparams(bindparam("s", expanding=True), bindparam("q", expanding=True), bindparam("d", expanding=True)),
        {"s": survey_ids, "q": qcodes, "d": dims})
    for r in rows.mappings():
        cell = out.setdefault((r["survey_id"], aliases.get(r["qcode"], r["qcode"]), r["dim"], r["dim_value"]),
                              {"base": r["base_n"], "built_at": r["built_at"], "answers": {}})
        cell["answers"][r["answer"]] = cell["answers"].get(r["answer"], 0) + r["n"]
    return out


def filler(label: str) -> bool:
    """'None of these', 'Other (please specify)' and the like never lead a ranked list."""
    low = label.lower()
    return low.startswith(("none of", "other", "don't know", "don’t know", "not sure")) or "please specify" in low


def share(cube: dict, wave: Optional[dict], qcode: str, answers: list, dim="total", value="Total") -> Optional[tuple[int, int]]:
    """(n, base) of respondents giving any of `answers`, or None when the wave or question is absent."""
    cell = wave and wave["survey_id"] and cube.get((wave["survey_id"], qcode, dim, value))
    if not cell or not cell["base"]:
        return None
    return sum(cell["answers"].get(str(a), 0) for a in answers), cell["base"]


def metric(code, label, now, prior, ly, waves, cfg, segment="Total", rank=0) -> dict:
    """One number with its comparisons and the flags that warn a reader before they compare."""
    (n, base), (wave, prior_wave, ly_wave) = now, waves
    row = {"metric_code": code, "segment": segment, "rank_no": rank, "label": label, "n": n, "base_n": base,
           "pct": round(100 * n / base, 3), "prior_pct": None, "prior_base_n": None, "ly_pct": None, "ly_base_n": None}
    flags = ["small_base"] if base < cfg["small_base"] else []
    if base < HIDDEN_BASE:
        flags.append("suppressed")
    for key, other, other_wave in (("prior", prior, prior_wave), ("ly", ly, ly_wave)):
        if other is None:
            flags.append(f"{key}_missing")
            continue
        row[f"{key}_pct"], row[f"{key}_base_n"] = round(100 * other[0] / other[1], 3), other[1]
        if abs(100 * base / wave["qualified"] - 100 * other[1] / other_wave["qualified"]) > BASE_SHIFT:
            flags.append(f"base_changed_{key}")
    row["flags"] = ",".join(flags)
    return row


def compute(conn, code: str, survey_id: int) -> tuple[dict, list[dict]]:
    """Every number of one dashboard for one wave → (build header, metric rows)."""
    cfg = load_config()[code]
    waves = series(conn, cfg["module"])
    wave = next(w for w in waves if w["survey_id"] == survey_id)
    prior, ly = comparisons(waves, wave, cfg.get("ly_rule", "same_calendar_week"))
    trio = (wave, prior, ly)
    qcodes = sorted({t["qcode"] for t in cfg["tiles"]} | {l["qcode"] for l in cfg["lists"]})
    dims = ["total"] + [s["dim"] for s in cfg.get("segments", [])]
    loaded = [w["survey_id"] for w in trio if w and w["survey_id"]]
    cube = cells(conn, loaded, qcodes, dims, cfg.get("aliases"))
    usual = meanings(conn, [w["survey_id"] for w in waves if w["survey_id"]], cfg["tiles"], cfg.get("aliases"))
    tiles = {t["code"]: t for t in cfg["tiles"]}
    def same(t, w):   # a wave whose codes mean something else counts as not asked
        return w if w and usual.get((t["code"], w["survey_id"])) else None
    rows = []
    for t in cfg["tiles"]:
        now = share(cube, same(t, wave), t["qcode"], t["codes"])
        if now:
            rows.append(metric(t["code"], t["label"], now, share(cube, same(t, prior), t["qcode"], t["codes"]),
                               share(cube, same(t, ly), t["qcode"], t["codes"]), trio, cfg))
    for spec in cfg["lists"]:
        cell = cube.get((survey_id, spec["qcode"], "total", "Total"))
        ranked = sorted(((n, label) for label, n in (cell or {"answers": {}})["answers"].items()
                         if label not in spec.get("exclude", []) and not filler(label)), key=lambda x: (-x[0], x[1]))
        for rank, (n, label) in enumerate(ranked[:spec["top"]], 1):
            rows.append(metric(spec["code"], label, (n, cell["base"]), share(cube, prior, spec["qcode"], [label]),
                               share(cube, ly, spec["qcode"], [label]), trio, cfg, rank=rank))
    for seg in cfg.get("segments", []):
        tile = tiles[seg["of"]]
        for value in seg["order"]:
            now = share(cube, same(tile, wave), tile["qcode"], tile["codes"], seg["dim"], value)
            if now:
                rows.append(metric(seg["code"], value, now,
                                   share(cube, same(tile, prior), tile["qcode"], tile["codes"], seg["dim"], value),
                                   share(cube, same(tile, ly), tile["qcode"], tile["codes"], seg["dim"], value), trio, cfg, segment=value))
    built = [c["built_at"] for k, c in cube.items() if k[0] == survey_id]
    header = {"dashboard_code": code, "survey_id": survey_id, "wave": wave, "waves": waves,
              "prior": prior, "ly": ly, "cube_built_at": max(built) if built else None}
    return header, rows


def _pts(a, b):
    return None if a is None or b is None else round(a - b, 1)


def move(r: dict, key: str) -> Optional[float]:
    """The change in points vs prior or last year, only when comparable and significant."""
    if r[f"{key}_pct"] is None or f"base_changed_{key}" in r["flags"]:
        return None
    if not significant(r["pct"], r["base_n"], r[f"{key}_pct"], r[f"{key}_base_n"]):
        return None
    return round(r["pct"] - r[f"{key}_pct"], 1)


def takeaways(rows: list[dict], cfg: dict) -> list[str]:
    """Key-takeaway sentences written from the numbers (so they can never disagree with them), from each
    tile's, list's and segment's `say` in config/dashboards.yml. A change is mentioned only when significant."""
    rows = [r for r in rows if "suppressed" not in r["flags"]]   # under HIDDEN_BASE people: never quoted
    by = {(r["metric_code"], r["segment"], r["rank_no"]): r for r in rows}
    prior = cfg.get("prior_label", "the previous wave")
    def changes(r):
        out = []
        if (d := move(r, "prior")) is not None:
            out.append(f"{'up' if d > 0 else 'down'} {abs(d)} pts vs {prior}")
        if r["ly_pct"] is not None and "base_changed_ly" not in r["flags"]:
            d = move(r, "ly")
            out.append(f"{round(r['ly_pct'])}% a year ago" + (f", {d:+} pts" if d is not None else ""))
        return f" ({'; '.join(out)})" if out else ""
    bullets: dict[str, list[str]] = {}
    for t in cfg["tiles"]:
        r = by.get((t["code"], "Total", 0))
        if r:
            bullets.setdefault(t.get("head", t["label"].capitalize()), []).append(f"{round(r['pct'])}% {t['say']}{changes(r)}")
    out = [f"{head}: {'; '.join(parts)}." for head, parts in bullets.items()]
    for spec in cfg["lists"]:
        top = [by[k] for k in sorted(k for k in by if k[0] == spec["code"])]
        if not top:
            continue
        lead = ", ".join(f"{r['label']} ({round(r['pct'])}%)" for r in top[:3])
        moved = [(d, r["label"], key) for r in top for key in ("prior", "ly") if (d := move(r, key)) is not None]
        d, label, key = max(moved, key=lambda m: abs(m[0]), default=(None, None, None))
        out.append(f"{spec['head']}: {lead} {spec['say']} (n={top[0]['base_n']})."
                   + (f" Biggest significant move vs {prior if key == 'prior' else 'last year'}: {label} ({d:+} pts)." if d else ""))
    for seg in cfg.get("segments", []):
        group = [r for r in rows if r["metric_code"] == seg["code"]]
        total = by.get((seg["of"], "Total", 0))
        if len(group) < 2 or not total:
            continue
        hi, lo = max(group, key=lambda r: r["pct"]), min(group, key=lambda r: r["pct"])
        small = [r["segment"] for r in group if "small_base" in r["flags"]]
        gap = (f" {hi['segment']} leads and {lo['segment']} trails, a significant gap of {round(hi['pct'] - lo['pct'])} pts."
               if significant(hi["pct"], hi["base_n"], lo["pct"], lo["base_n"]) else " No significant gap between generations.")
        out.append(f"{seg['say']}: " + ", ".join(f"{r['segment']} {round(r['pct'])}%" for r in group)
                   + f" (all adults: {round(total['pct'])}%)." + gap + (f" Small base: {', '.join(small)}." if small else ""))
    return out


def payload(header: dict, rows: list[dict]) -> dict:
    """The browser's whole dashboard in one small document: no further requests, no client maths."""
    w, prior, ly = header["wave"], header["prior"], header["ly"]
    def number(r):
        if "suppressed" in r["flags"]:   # fewer than HIDDEN_BASE people: the base only, as on every other screen
            return {"label": r["label"], "segment": r["segment"], "pct": None, "n": None, "base": r["base_n"],
                    "vs_prior": None, "vs_ly": None, "ly_pct": None, "flags": [f for f in r["flags"].split(",") if f]}
        return {"label": r["label"], "segment": r["segment"], "pct": round(r["pct"], 1), "n": r["n"], "base": r["base_n"],
                "vs_prior": _pts(r["pct"], r["prior_pct"]), "vs_ly": _pts(r["pct"], r["ly_pct"]),
                "ly_pct": None if r["ly_pct"] is None else round(r["ly_pct"], 1),
                "flags": [f for f in r["flags"].split(",") if f]}
    group = lambda code: [number(r) for r in rows if r["metric_code"] == code]
    cfg = load_config()[header["dashboard_code"]]
    wave_info = lambda x: x and {"survey_id": x["survey_id"], "wave_no": x["series_wave_no"], "season": x["season"],
                                 "week_of": x["launched_on"].isoformat(), "loaded": bool(x["survey_id"])}
    return {
        "dashboard": header["dashboard_code"], "title": cfg["title"],
        "wave": wave_info(w), "prior": wave_info(prior), "last_year": wave_info(ly),
        "waves": [wave_info(x) for x in header["waves"] if x["survey_id"]],
        "tiles": {t["code"]: (group(t["code"]) or [None])[0] for t in cfg["tiles"]},
        "lists": {l["code"]: group(l["code"]) for l in cfg["lists"]},
        "segments": {s["code"]: group(s["code"]) for s in cfg.get("segments", [])},
        "takeaways": takeaways(rows, cfg),
        "tile_labels": {t["code"]: t["label"] for t in cfg["tiles"]},
        "highlights": [{"list": l["code"], "title": l["tile"], "of": l.get("of", "")} for l in cfg["lists"] if l.get("tile")],
        "prior_label": cfg.get("prior_label", "the previous wave"),
        "small_base": cfg["small_base"],
        "ly_rule": cfg.get("ly_rule", "same_calendar_week"),
        "data_as_of": str(header["cube_built_at"])[:19].replace(" ", "T") if header["cube_built_at"] else None,
    }


def build(code: str, survey_id: int) -> Optional[int]:
    """Compute, render and publish one dashboard wave in one transaction; returns the build id, or None when
    the wave asked none of the dashboard's questions (a module wave that skipped them): nothing is published."""
    with get_engine("etl").begin() as conn:
        header, rows = compute(conn, code, survey_id)
        if not rows:
            log.info("Skipped %s for survey %s: none of its questions were asked", code, survey_id)
            return None
        doc = payload(header, rows)
        body = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
        build_id = conn.execute(text(
            "INSERT INTO cip_dash_build (dashboard_code, survey_id, prior_survey_id, ly_survey_id, cube_built_at)"
            " VALUES (:c, :s, :p, :l, :t)"),
            {"c": code, "s": survey_id, "p": (header["prior"] or {}).get("survey_id"),
             "l": (header["ly"] or {}).get("survey_id"), "t": header["cube_built_at"]}).lastrowid
        conn.execute(text(
            "INSERT INTO cip_dash_metric (build_id, metric_code, segment, rank_no, label, n, base_n, pct,"
            " prior_pct, prior_base_n, ly_pct, ly_base_n, flags) VALUES (:b, :metric_code, :segment, :rank_no,"
            " :label, :n, :base_n, :pct, :prior_pct, :prior_base_n, :ly_pct, :ly_base_n, :flags)"),
            [{"b": build_id, **r} for r in rows])
        conn.execute(text("INSERT INTO cip_dash_payload (build_id, etag, payload_json, payload_gz) VALUES (:b, :e, :j, :g)"),
                     {"b": build_id, "e": hashlib.sha256(body.encode()).hexdigest()[:16], "j": body,
                      "g": gzip.compress(body.encode(), 9)})
        conn.execute(text(
            "INSERT INTO cip_dash_published (dashboard_code, survey_id, build_id) VALUES (:c, :s, :b)"
            " ON DUPLICATE KEY UPDATE build_id = VALUES(build_id), published_at = CURRENT_TIMESTAMP"),
            {"c": code, "s": survey_id, "b": build_id})
    log.info("Published %s for survey %s as build %s (%d numbers, %d bytes)", code, survey_id, build_id, len(rows), len(body))
    return build_id


def meanings(conn, ids: list[int], tiles: list[dict], aliases: Optional[dict] = None) -> dict:
    """{(tile code, survey_id): True when the tile's answer codes carry their usual labels in that wave}.
    "Usual" is the most common labelling across the module's waves: a wave that reused the question code
    for another question (GLP1 wave of 10 Nov 2025: GP2/GP3 asked about groceries) is left out, not misread."""
    labels: dict = defaultdict(dict)
    aliases = aliases or {}
    if ids:
        for sid, qcode, value, label in conn.execute(text(
                "SELECT q.survey_id, q.qcode, o.value_code, o.value_label FROM cip_question q"
                " JOIN cip_option o ON o.question_id = q.question_id WHERE q.survey_id IN :s AND q.qcode IN :q")
                .bindparams(bindparam("s", expanding=True), bindparam("q", expanding=True)),
                {"s": ids, "q": sorted({t["qcode"] for t in tiles} | {o for o, n in aliases.items() if n in {t["qcode"] for t in tiles}}) or ["-"]}):
            labels[(sid, aliases.get(qcode, qcode))][value] = " ".join(label.lower().replace("’", "'").split())
    out = {}
    for t in tiles:
        seen = {sid: tuple(labels[(sid, t["qcode"])].get(c) for c in t["codes"]) for sid in ids if (sid, t["qcode"]) in labels}
        usual = Counter(seen.values()).most_common(1)[0][0] if seen else None
        out.update({(t["code"], sid): key == usual for sid, key in seen.items()})
    return out


def check(conn) -> list[str]:
    """Waves whose tile codes mean something else (left out of that tile, listed here for the data team)."""
    problems = []
    for code, cfg in load_config().items():
        ids = [w["survey_id"] for w in series(conn, cfg["module"]) if w["survey_id"]]
        usual = meanings(conn, ids, cfg["tiles"], cfg.get("aliases"))
        problems += [f"{code}.{tile}: {next(t['qcode'] for t in cfg['tiles'] if t['code'] == tile)} means something else in survey {sid}"
                     for (tile, sid), ok in sorted(usual.items()) if not ok]
    return problems


def build_all(code: str) -> list[int]:
    with get_engine("app").connect() as conn:
        ids = [w["survey_id"] for w in series(conn, load_config()[code]["module"]) if w["survey_id"]]
    return [b for s in ids if (b := build(code, s))]


def build_for(survey_ids: list[int]) -> list[int]:
    """After a load: every configured dashboard of the module(s) the new waves carry. A new wave only looks
    back (prior, last year), so earlier waves' dashboards stay as they are."""
    with get_engine("app").connect() as conn:
        due = [(code, s) for code, cfg in load_config().items()
               for s in {w["survey_id"] for w in series(conn, cfg["module"])} & set(survey_ids)]
    return [b for code, s in due if (b := build(code, s))]


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s | %(message)s")
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--build", metavar="DASHBOARD")
    p.add_argument("--show", metavar="DASHBOARD")
    p.add_argument("--survey", type=int)
    p.add_argument("--check", action="store_true")
    a = p.parse_args()
    if a.check:
        with get_engine("app").connect() as conn:
            problems = check(conn)
        print("\n".join(problems) or "Every tile code means the same answer in every loaded wave.")
        return 1 if problems else 0
    if a.show:
        with get_engine("app").connect() as conn:
            header, rows = compute(conn, a.show, a.survey)
        print(json.dumps(payload(header, rows), indent=2, ensure_ascii=False))
        return 0
    if a.build:
        ids = [build(a.build, a.survey)] if a.survey else build_all(a.build)
        print(f"published builds: {ids}")
        return 0
    p.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
