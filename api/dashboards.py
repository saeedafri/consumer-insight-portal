"""Backend (not ETL): shape the ETL's serving tables into one sample dashboard's screen payload.

The ETL ends at the serving tables (etl/serving.py, sql/005_serving.sql); it knows nothing about screens.
This backend job reads the few serving rows one screen needs, picks its comparison weeks from the
season calendar, writes the screen's key-takeaway sentences, and stores the finished JSON (gzipped) in
the backend's own cache tables (sql/006_dashboards.sql). The API holds those bytes in memory.
The dashboard definition is config/dashboards.yml.

    python -m api.dashboards --build holiday_tracker            # every loaded wave of the series
    python -m api.dashboards --build holiday_tracker --survey 412
    python -m api.dashboards --show holiday_tracker --survey 412
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import logging
import sys
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml
from sqlalchemy import bindparam, text

from app.core.database import get_engine

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
        " WHERE w.module_code = :m ORDER BY w.launched_on"), {"m": module}).mappings()]
    for r in rows:   # MySQL returns a date, SQLite a string
        r["launched_on"] = date.fromisoformat(str(r["launched_on"])[:10])
    return rows


def comparisons(waves: list[dict], wave: dict) -> tuple[Optional[dict], Optional[dict]]:
    """Prior week: the previous wave of the same season. Last year: the wave launched in the same
    calendar week one year earlier (±3 days), loaded or not — so a missing one is reported, not skipped."""
    prior = next((w for w in waves if w["season"] == wave["season"]
                  and w["series_wave_no"] == wave["series_wave_no"] - 1), None)
    target = wave["launched_on"] - timedelta(days=364)
    ly = next((w for w in waves if abs((w["launched_on"] - target).days) <= 3), None)
    return prior, ly


def cells(conn, survey_ids: list[int], qcodes: list[str], dims: list[str]) -> dict:
    """{(survey_id, qcode, dim, dim_value): {"base": n, "built_at": ts, "answers": {code-or-label: n}}},
    read from the ETL's serving rows: one primary-key range per wave, no joins."""
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
        cell = out.setdefault((r["survey_id"], r["qcode"], r["dim"], r["dim_value"]),
                              {"base": r["base_n"], "built_at": r["built_at"], "answers": {}})
        cell["answers"][r["answer"]] = cell["answers"].get(r["answer"], 0) + r["n"]
    return out


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
    prior, ly = comparisons(waves, wave)
    trio = (wave, prior, ly)
    qcodes = sorted({t["qcode"] for t in cfg["tiles"]} | {l["qcode"] for l in cfg["lists"]})
    dims = ["total"] + [s["dim"] for s in cfg.get("segments", [])]
    loaded = [w["survey_id"] for w in trio if w and w["survey_id"]]
    cube = cells(conn, loaded, qcodes, dims)
    tiles = {t["code"]: t for t in cfg["tiles"]}
    rows = []
    for t in cfg["tiles"]:
        now = share(cube, wave, t["qcode"], t["codes"])
        if now:
            rows.append(metric(t["code"], t["label"], now, share(cube, prior, t["qcode"], t["codes"]),
                               share(cube, ly, t["qcode"], t["codes"]), trio, cfg))
    for spec in cfg["lists"]:
        cell = cube.get((survey_id, spec["qcode"], "total", "Total"))
        ranked = sorted(((n, label) for label, n in (cell or {"answers": {}})["answers"].items()
                         if label not in spec.get("exclude", [])), key=lambda x: (-x[0], x[1]))
        for rank, (n, label) in enumerate(ranked[:spec["top"]], 1):
            rows.append(metric(spec["code"], label, (n, cell["base"]), share(cube, prior, spec["qcode"], [label]),
                               share(cube, ly, spec["qcode"], [label]), trio, cfg, rank=rank))
    for seg in cfg.get("segments", []):
        tile = tiles[seg["of"]]
        for value in seg["order"]:
            now = share(cube, wave, tile["qcode"], tile["codes"], seg["dim"], value)
            if now:
                rows.append(metric(seg["code"], value, now,
                                   share(cube, prior, tile["qcode"], tile["codes"], seg["dim"], value),
                                   share(cube, ly, tile["qcode"], tile["codes"], seg["dim"], value), trio, cfg, segment=value))
    built = [c["built_at"] for k, c in cube.items() if k[0] == survey_id]
    header = {"dashboard_code": code, "survey_id": survey_id, "wave": wave, "waves": waves,
              "prior": prior, "ly": ly, "cube_built_at": max(built) if built else None}
    return header, rows


def _pts(a, b):
    return None if a is None or b is None else round(a - b, 1)


def takeaways(rows: list[dict], header: dict) -> list[str]:
    """The data team's key-takeaway sentences, written from the numbers so they can never disagree."""
    by = {(r["metric_code"], r["segment"], r["rank_no"]): r for r in rows}
    pct = lambda code, seg="Total", rank=0: round(by[(code, seg, rank)]["pct"]) if (code, seg, rank) in by else None
    out = []
    if pct("started") is not None:
        line = (f"Progress: {pct('started')}% of US consumers have started holiday shopping "
                f"({pct('finished')}% finished) and {pct('not_started')}% have not started")
        ly = by[("started", "Total", 0)]["ly_pct"]
        out.append(line + (f"; {round(ly)}% had started at the same point last year." if ly is not None
                           else " — last year's same week is not loaded, so no year-on-year comparison."))
    b = by.get(("bought_7d", "Total", 0))
    if b:
        line = f"Activity: {round(b['pct'])}% bought for the holidays in the past 7 days (n={b['base_n']})."
        if "base_changed_prior" in b["flags"]:
            line += (f" Last week the question went to {b['prior_base_n']} respondents only, so the change"
                     " vs prior week is a change of base, not of behaviour.")
        out.append(line)
    top = [by[k] for k in sorted(k for k in by if k[0] == "retailers")]
    if top:
        lead = ", ".join(f"{r['label']} ({round(r['pct'])}%)" for r in top[:3])
        moves = sorted((r for r in top if r["ly_pct"] is not None), key=lambda r: -abs(r["pct"] - r["ly_pct"]))
        out.append(f"Retailers: {lead} lead among holiday purchasers (n={top[0]['base_n']})."
                   + (f" Biggest move vs last year: {moves[0]['label']} ({_pts(moves[0]['pct'], moves[0]['ly_pct']):+} pts)."
                      if moves else ""))
    cats = [by[k] for k in sorted(k for k in by if k[0] == "categories")]
    if len(cats) >= 2:
        out.append(f"Categories: {cats[0]['label']} ({round(cats[0]['pct'])}%) and {cats[1]['label']} "
                   f"({round(cats[1]['pct'])}%) lead the basket.")
    gen = [r for r in rows if r["metric_code"] == "started_by_generation"]
    if gen:
        hi, lo = max(gen, key=lambda r: r["pct"]), min(gen, key=lambda r: r["pct"])
        small = [r["segment"] for r in gen if "small_base" in r["flags"]]
        out.append("By generation, started holiday shopping: "
                   + ", ".join(f"{r['segment']} {round(r['pct'])}%" for r in gen)
                   + f" (all adults: {pct('started')}%). {hi['segment']} leads and {lo['segment']} trails,"
                   f" a gap of {round(hi['pct'] - lo['pct'])} pts."
                   + (f" Small base: {', '.join(small)}." if small else ""))
    return out


def payload(header: dict, rows: list[dict]) -> dict:
    """The browser's whole dashboard in one small document: no further requests, no client maths."""
    w, prior, ly = header["wave"], header["prior"], header["ly"]
    def number(r):
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
        "takeaways": takeaways(rows, header),
        "small_base": cfg["small_base"],
        "data_as_of": str(header["cube_built_at"])[:19].replace(" ", "T") if header["cube_built_at"] else None,
    }


def build(code: str, survey_id: int) -> int:
    """Compute, render and publish one dashboard wave in one transaction; returns the build id."""
    with get_engine("etl").begin() as conn:
        header, rows = compute(conn, code, survey_id)
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


def build_all(code: str) -> list[int]:
    with get_engine("app").connect() as conn:
        ids = [w["survey_id"] for w in series(conn, load_config()[code]["module"]) if w["survey_id"]]
    return [build(code, s) for s in ids]


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s | %(message)s")
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--build", metavar="DASHBOARD")
    p.add_argument("--show", metavar="DASHBOARD")
    p.add_argument("--survey", type=int)
    a = p.parse_args()
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
