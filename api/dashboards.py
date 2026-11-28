"""Backend (not ETL): shape the ETL's serving tables into one sample dashboard's screen payload.

The ETL ends at the serving tables (etl/serving.py, sql/005_serving.sql); it knows nothing about screens.
This backend job reads the few serving rows one screen needs, picks its comparison weeks from the
season calendar, writes the screen's key-takeaway sentences, and stores the finished JSON (gzipped) in
the backend's own cache tables (sql/006_dashboards.sql). The API holds those bytes in memory.
The dashboard definition is config/dashboards.yml. Its lists' headings reach builds stored before a heading was added
(add_list_heads): when etl/publish.py writes the files and after a restore (write_views → name_lists), and when
api/main.py load_published reads the builds for the API.

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
import sys
from collections import Counter
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml
from sqlalchemy import bindparam, text

from shared.core.database import get_engine
from shared.data.payloads import HIDDEN_BASE, TEST_BASE
from etl.loaders import etl_lock
from etl.serving import p_value

log = logging.getLogger("cip.api.dashboards")
CONFIG = Path(__file__).resolve().parents[1] / "config" / "dashboards.yml"
BASE_SHIFT = 10.0   # points: a question's base share of qualified respondents moving more than this is a routing change


@lru_cache(maxsize=1)
def load_config() -> dict:
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


def series(conn, module: str) -> list[dict]:
    """Every wave of the module, loaded or not (hibernated waves have no survey_id)."""
    rows = [dict(r) for r in conn.execute(text(
        "SELECT w.forsta_path, w.season, w.series_wave_no, w.launched_on, s.survey_id, s.wave_label, s.wave_date,"
        "       (SELECT SUM(r.is_qualified) FROM cip_respondent r WHERE r.survey_id = s.survey_id) AS qualified"
        "  FROM cip_wave_module w"
        "  LEFT JOIN cip_forsta_survey f ON f.forsta_path = w.forsta_path"
        "  LEFT JOIN cip_survey s ON s.survey_id = f.survey_id AND s.load_status = 'verified'"
        " WHERE w.module_code = :m AND w.launched_on IS NOT NULL ORDER BY w.launched_on"), {"m": module}).mappings()]
    for r in rows:   # MySQL returns a date, SQLite a string
        r["launched_on"] = date.fromisoformat(str(r["launched_on"])[:10])
        r["wave_date"] = r["wave_date"] and date.fromisoformat(str(r["wave_date"])[:10])
    return rows


def week_of(wave: Optional[dict]) -> Optional[str]:
    """The week a wave is shown under: its survey's date, as the week picker and every other screen show it (Forsta's
    launch can be days earlier: 4 Jul vs 7 Jul 2025); the launch for a wave not loaded."""
    return wave and (wave.get("wave_date") or wave["launched_on"]).isoformat()


LY_RULES = ("same_wave_number", "same_calendar_week", "nearest_year_ago")


def comparisons(waves: list[dict], wave: dict, ly_rule: str = "same_calendar_week") -> tuple[Optional[dict], Optional[dict]]:
    """Prior: the latest earlier wave of `waves` (same season for seasonal ones). Last year, by the module's rule:
      same_wave_number    wave N of last season (the business team's Databank: wave 3 2026 vs wave 3 2025)
      same_calendar_week  the wave launched in the same calendar week one year earlier (±3 days)
      nearest_year_ago    the wave launched closest to one year earlier, within a month (monthly topic modules)
    Loaded or not — so a missing one is reported, not skipped. compute() passes only the waves that asked the
    question (or are not loaded), so a week that skipped it is never the comparison."""
    if ly_rule not in LY_RULES:
        raise ValueError(f"ly_rule must be one of {LY_RULES}")
    prior = max((w for w in waves if w["season"] == wave["season"] and w["launched_on"] < wave["launched_on"]),
                key=lambda w: w["launched_on"], default=None)
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
    if min(n1 or 0, n2 or 0) < TEST_BASE:
        return False
    return p_value(p1 / 100 * n1, n1, p2 / 100 * n2, n2) < 0.05


def cells(conn, survey_ids: list[int], qcodes: list[str], dims: list[str], aliases: Optional[dict] = None) -> dict:
    """{(survey_id, qcode, dim, dim_value): {"base": n, "built_at": ts, "answers": {code-or-label: n}, "flags": {code-or-label: flags}}},
    read from the ETL's serving rows: one primary-key range per wave, no joins. `aliases` maps an older code
    of the same question to the configured one (Social commerce: SM1 in Feb 2026, SC1 otherwise)."""
    aliases = aliases or {}
    qcodes = list(qcodes) + [old for old, new in aliases.items() if new in qcodes]
    out: dict = {}
    if not survey_ids:
        return out
    rows = conn.execute(text(
        "SELECT r.survey_id, r.qcode, r.dim, r.dim_value, r.n, r.base_n, r.flags, w.built_at,"
        "       COALESCE(CAST(r.option_code AS CHAR), r.item_label) AS answer"
        "  FROM srv_result r JOIN srv_wave w ON w.survey_id = r.survey_id"
        " WHERE r.survey_id IN :s AND r.qcode IN :q AND r.dim IN :d")
        .bindparams(bindparam("s", expanding=True), bindparam("q", expanding=True), bindparam("d", expanding=True)),
        {"s": survey_ids, "q": qcodes, "d": dims})
    for r in rows.mappings():
        cell = out.setdefault((r["survey_id"], aliases.get(r["qcode"], r["qcode"]), r["dim"], r["dim_value"]),
                              {"base": r["base_n"], "built_at": r["built_at"], "answers": {}, "flags": {}})
        cell["answers"][r["answer"]] = cell["answers"].get(r["answer"], 0) + r["n"]
        cell["flags"][r["answer"]] = r["flags"] or ""
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


def tested(cube: dict, wave: Optional[dict], qcode: str, answers: list) -> Optional[set]:
    """Which comparisons ("prior", "ly") the ETL found significant for this one answer's Total row: srv_result's sig_prior
    and sig_ly flags (BH-FDR at 5 % over the wave's testable Total rows, etl/serving.py), the rule the Overview shows.
    A number summing several answers, or a segment, has no such test, so it is never called significant. None when the
    wave's serving rows carry no sig flag at all (built before the ETL wrote them): takeaways then fall back to one
    z-test and say "single comparison"."""
    if not wave or not any("sig_" in f for k, c in cube.items() if k[0] == wave["survey_id"] for f in c["flags"].values()):
        return None
    cell = cube.get((wave["survey_id"], qcode, "total", "Total"))
    if not cell or len(answers) != 1:
        return set()
    flags = cell["flags"].get(str(answers[0]), "")
    return {key for key in ("prior", "ly") if f"sig_{key}" in flags}


def metric(code, label, now, prior, ly, waves, cfg, segment="Total", rank=0) -> dict:
    """One number with its comparisons (and the week each compares with) and the flags that warn a reader before
    they compare. Percentages stay unrounded: payload() rounds each figure and change once (rounding to 3 decimals
    first put 13.4503% on screen as 13.4, and Tariffs' 6 Jul 2026 change of -3.9 as -3.8: 28 Nov 2026 check)."""
    (n, base), (wave, prior_wave, ly_wave) = now, waves
    row = {"metric_code": code, "segment": segment, "rank_no": rank, "label": label, "n": n, "base_n": base,
           "pct": 100 * n / base, "prior_pct": None, "prior_base_n": None, "ly_pct": None, "ly_base_n": None,
           "prior_week": None, "ly_week": None}
    flags = ["small_base"] if base < cfg["small_base"] else []
    if base < HIDDEN_BASE:
        flags.append("suppressed")
    for key, other, other_wave in (("prior", prior, prior_wave), ("ly", ly, ly_wave)):
        if other is None:
            flags.append(f"{key}_missing")
            continue
        row[f"{key}_pct"], row[f"{key}_base_n"], row[f"{key}_week"] = 100 * other[0] / other[1], other[1], week_of(other_wave)
        if abs(100 * base / wave["qualified"] - 100 * other[1] / other_wave["qualified"]) > BASE_SHIFT:
            flags.append(f"base_changed_{key}")
    row["flags"] = ",".join(flags)
    return row


def compute(conn, code: str, survey_id: int) -> tuple[dict, list[dict]]:
    """Every number of one dashboard for one wave → (build header, metric rows). Each tile, list and segment compares
    with the latest earlier wave and the last-year wave that asked its own question in its usual meaning (meanings()):
    a week that asked part of the tracker (GenAI's shopping question alone, May-Aug 2026) or none of it (GLP-1's
    10 Nov 2025 asked other questions under its codes) is never compared as if it had. The header's prior and last
    year are the dashboard's as a whole, and a figure compared with another week names it (payload)."""
    cfg = load_config()[code]
    rule = cfg.get("ly_rule", "same_calendar_week")
    specs = cfg["tiles"] + cfg["lists"]
    every = series(conn, cfg["module"])
    usual = meanings(conn, [w["survey_id"] for w in every if w["survey_id"]], specs, cfg.get("aliases"))
    def asked(spec, w):   # a wave whose code means something else counts as not asked
        return usual.get((spec["code"], w["survey_id"]), False)
    waves = [w for w in every if not w["survey_id"] or any(asked(s, w) for s in specs)]
    count: Counter = Counter()
    for w in waves:   # "Wave N": the Nth week (of the season) that asked its questions, as the tracker page counts them
        count[w["season"]] += 1
        w["series_wave_no"] = count[w["season"]]
    wave = next(w for w in every if w["survey_id"] == survey_id)
    prior, ly = comparisons(waves, wave, rule)
    trios = {s["code"]: (wave, *comparisons([w for w in waves if not w["survey_id"] or asked(s, w)], wave, rule)) for s in specs}
    qcodes = sorted({s["qcode"] for s in specs})
    dims = ["total"] + [s["dim"] for s in cfg.get("segments", [])]
    loaded = sorted({w["survey_id"] for trio in [*trios.values(), (wave, prior, ly)] for w in trio if w and w["survey_id"]})
    cube = cells(conn, loaded, qcodes, dims, cfg.get("aliases"))
    tiles = {t["code"]: t for t in cfg["tiles"]}
    rows = []
    for t in cfg["tiles"]:
        trio = trios[t["code"]]
        now = asked(t, wave) and share(cube, wave, t["qcode"], t["codes"])
        if now:
            rows.append(metric(t["code"], t["label"], now, *(share(cube, w, t["qcode"], t["codes"]) for w in trio[1:]), trio, cfg))
            rows[-1]["sig"] = tested(cube, wave, t["qcode"], t["codes"])
    for spec in cfg["lists"]:
        trio = trios[spec["code"]]
        def offered(w, label):   # an answer that week did not offer (GenAI's Claude, Nov 2025) has no comparison, not 0 %
            other = w and cube.get((w["survey_id"], spec["qcode"], "total", "Total"))
            return share(cube, w, spec["qcode"], [label]) if other and label in other["answers"] else None
        cell = asked(spec, wave) and cube.get((survey_id, spec["qcode"], "total", "Total"))
        ranked = sorted(((n, label) for label, n in (cell or {"answers": {}})["answers"].items()
                         if label not in spec.get("exclude", []) and not filler(label)), key=lambda x: (-x[0], x[1]))
        for rank, (n, label) in enumerate(ranked[:spec["top"]], 1):
            rows.append(metric(spec["code"], label, (n, cell["base"]), *(offered(w, label) for w in trio[1:]), trio, cfg, rank=rank))
            rows[-1]["sig"] = tested(cube, wave, spec["qcode"], [label])
    for seg in cfg.get("segments", []):
        tile = tiles[seg["of"]]
        trio = trios[tile["code"]]
        for value in seg["order"]:
            now = asked(tile, wave) and share(cube, wave, tile["qcode"], tile["codes"], seg["dim"], value)
            if now:
                rows.append(metric(seg["code"], value, now, *(share(cube, w, tile["qcode"], tile["codes"], seg["dim"], value)
                                                              for w in trio[1:]), trio, cfg, segment=value))
    built = [c["built_at"] for k, c in cube.items() if k[0] == survey_id]
    header = {"dashboard_code": code, "survey_id": survey_id, "wave": wave, "waves": waves,
              "prior": prior, "ly": ly, "cube_built_at": max(built) if built else None}
    return header, rows


def point_change(a, b):
    return None if a is None or b is None else round(a - b, 1)


def move(r: dict, key: str) -> Optional[float]:
    """The change in points vs prior or last year, only when comparable and flagged significant by the ETL (tested)."""
    if r[f"{key}_pct"] is None or f"base_changed_{key}" in r["flags"]:
        return None
    if r.get("sig") is None:   # no ETL flags for this wave: one uncorrected test, worded as such (single())
        if not significant(r["pct"], r["base_n"], r[f"{key}_pct"], r[f"{key}_base_n"]):
            return None
    elif key not in r["sig"]:
        return None
    return round(r["pct"] - r[f"{key}_pct"], 1)


def single(r: dict) -> str:
    return ", single comparison" if r.get("sig") is None else ""


def takeaways(rows: list[dict], cfg: dict) -> list[str]:
    """Key-takeaway sentences written from the numbers (so they can never disagree with them), from each
    tile's, list's and segment's `say` in config/dashboards.yml. A change is mentioned only when significant."""
    rows = [r for r in rows if "suppressed" not in r["flags"]]   # under HIDDEN_BASE people: never quoted
    by = {(r["metric_code"], r["segment"], r["rank_no"]): r for r in rows}
    prior = cfg.get("prior_label", "the previous wave")
    def changes(r):
        out = []
        if (d := move(r, "prior")) is not None:
            out.append(f"{'up' if d > 0 else 'down'} {abs(d)} pts vs {prior}{single(r)}")
        if r["ly_pct"] is not None and "base_changed_ly" not in r["flags"]:
            d = move(r, "ly")
            out.append(f"{round(r['ly_pct'])}% a year ago" + (f", {d:+} pts{single(r)}" if d is not None else ""))
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
        moved = [(d, r["label"], key, r) for r in top for key in ("prior", "ly") if (d := move(r, key)) is not None]
        d, label, key, r = max(moved, key=lambda m: abs(m[0]), default=(None, None, None, None))
        out.append(f"{spec['head']}: {lead} {spec['say']} (n={top[0]['base_n']})."
                   + (f" Biggest significant move vs {prior if key == 'prior' else 'last year'}: {label} ({d:+} pts{single(r)})." if d else ""))
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
    """The browser's whole dashboard in one small document: no further requests, no client maths. Every figure and
    change is rounded here, once, from the counts. prior_week / ly_week name the week a figure compares with when it
    is not the header's (the previous wave skipped its question: Tariffs' 26 Oct 2026 asked only IN1 and IN2)."""
    w, prior, ly = header["wave"], header["prior"], header["ly"]
    def number(r):
        if "suppressed" in r["flags"]:   # fewer than HIDDEN_BASE people: the base only, as on every other screen
            return {"label": r["label"], "segment": r["segment"], "pct": None, "n": None, "base": r["base_n"],
                    "vs_prior": None, "vs_ly": None, "ly_pct": None, "flags": [f for f in r["flags"].split(",") if f]}
        return {"label": r["label"], "segment": r["segment"], "pct": round(r["pct"], 1), "n": r["n"], "base": r["base_n"],
                "vs_prior": point_change(r["pct"], r["prior_pct"]), "vs_ly": point_change(r["pct"], r["ly_pct"]),
                "ly_pct": None if r["ly_pct"] is None else round(r["ly_pct"], 1),
                "prior_week": None if r.get("prior_week") == week_of(prior) else r.get("prior_week"),
                "ly_week": None if r.get("ly_week") == week_of(ly) else r.get("ly_week"),
                "flags": [f for f in r["flags"].split(",") if f]}
    group = lambda code: [number(r) for r in rows if r["metric_code"] == code]
    cfg = load_config()[header["dashboard_code"]]
    wave_info = lambda x: x and {"survey_id": x["survey_id"], "wave_no": x["series_wave_no"], "season": x["season"],
                                 "week_of": week_of(x), "loaded": bool(x["survey_id"])}
    return {
        "dashboard": header["dashboard_code"], "title": cfg["title"],
        "wave": wave_info(w), "prior": wave_info(prior), "last_year": wave_info(ly),
        "waves": [wave_info(x) for x in header["waves"] if x["survey_id"]],
        "tiles": {t["code"]: (group(t["code"]) or [None])[0] for t in cfg["tiles"]},
        "lists": {l["code"]: group(l["code"]) for l in cfg["lists"]},
        "segments": {s["code"]: group(s["code"]) for s in cfg.get("segments", [])},
        "takeaways": takeaways(rows, cfg),
        "tile_labels": {t["code"]: t["label"] for t in cfg["tiles"]},
        "list_heads": list_heads(cfg),
        "highlights": [{"list": l["code"], "title": l["tile"], "of": l.get("of", "")} for l in cfg["lists"] if l.get("tile")],
        "prior_label": cfg.get("prior_label", "the previous wave"),
        "small_base": cfg["small_base"],
        "ly_rule": cfg.get("ly_rule", "same_calendar_week"),
        "data_as_of": str(header["cube_built_at"])[:19].replace(" ", "T") if header["cube_built_at"] else None,
    }


def list_heads(cfg: dict) -> dict:
    """A dashboard's lists by their headings (top → Top platforms): each list's tab name in the tracker's Excel."""
    return {l["code"]: l["head"] for l in cfg["lists"] if l.get("head")}


def add_list_heads(body: str, code: str, config: dict) -> Optional[dict]:
    """A stored build (its JSON) with its lists' headings as config/dashboards.yml has them now, or None when it has
    them already. A build keeps the config of its day, so a heading added or renamed would otherwise wait for that
    tracker's next week to be built (27 Nov 2026)."""
    heads, doc = list_heads(config.get(code) or {"lists": []}), json.loads(body)
    return {**doc, "list_heads": heads} if heads and doc.get("list_heads") != heads else None


def name_lists(out: Path, write) -> int:
    """Give every published dashboard file its lists' headings (add_list_heads): nginx serves these files. Called by
    etl/publish.py write_views; after a restore (a deploy) the files are the backup's, as built; after a publish they
    have them already, so none is rewritten. Returns the bytes written."""
    size, config = 0, load_config()
    for path in (out / "api/v1/dashboards").glob("*/*.json.gz"):
        if doc := add_list_heads(gzip.decompress(path.read_bytes()).decode(), path.parent.name, config):
            size += write(path.with_name(path.name.removesuffix(".json.gz")), doc)
    return size


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
            [{"b": build_id, **r, **{k: r[k] and round(r[k], 3) for k in ("pct", "prior_pct", "ly_pct")}} for r in rows])   # DECIMAL(6,3)
        conn.execute(text("INSERT INTO cip_dash_payload (build_id, etag, payload_json, payload_gz) VALUES (:b, :e, :j, :g)"),
                     {"b": build_id, "e": hashlib.sha256(body.encode()).hexdigest()[:16], "j": body,
                      "g": gzip.compress(body.encode(), 9)})
        conn.execute(text(
            "INSERT INTO cip_dash_published (dashboard_code, survey_id, build_id) VALUES (:c, :s, :b)"
            " ON DUPLICATE KEY UPDATE build_id = VALUES(build_id), published_at = CURRENT_TIMESTAMP"),
            {"c": code, "s": survey_id, "b": build_id})
    log.info("Published %s for survey %s as build %s (%d numbers, %d bytes)", code, survey_id, build_id, len(rows), len(body))
    return build_id


def meanings(conn, ids: list[int], specs: list[dict], aliases: Optional[dict] = None) -> dict:
    """{(tile or list code, survey_id): True when its question means what it usually does in that wave}: the same
    question type and, for a tile, the same labels on its answer codes. "Usual" is the most common across the module's
    waves: a wave that reused the code for another question (GLP-1, 10 Nov 2025: GP2-GP5 asked about groceries and the
    drug's price, single-choice where GP4 and GP5 are lists) is left out of that tile or list, not misread."""
    found: dict = {}
    aliases = aliases or {}
    qcodes = {s["qcode"] for s in specs}
    if ids:
        for sid, qcode, qtype, value, label in conn.execute(text(
                "SELECT q.survey_id, q.qcode, q.qtype, o.value_code, o.value_label FROM cip_question q"
                " LEFT JOIN cip_option o ON o.question_id = q.question_id WHERE q.survey_id IN :s AND q.qcode IN :q")
                .bindparams(bindparam("s", expanding=True), bindparam("q", expanding=True)),
                {"s": ids, "q": sorted(qcodes | {o for o, n in aliases.items() if n in qcodes}) or ["-"]}):
            question = found.setdefault((sid, aliases.get(qcode, qcode)), {"type": qtype, "labels": {}})
            if value is not None:
                question["labels"][value] = " ".join(label.lower().replace("’", "'").split())
    out = {}
    for s in specs:
        seen = {sid: (q["type"], *(q["labels"].get(c) for c in s.get("codes", []))) for (sid, qcode), q in found.items() if qcode == s["qcode"]}
        usual = Counter(seen.values()).most_common(1)[0][0] if seen else None
        out.update({(s["code"], sid): key == usual for sid, key in seen.items()})
    return out


def check(conn) -> list[str]:
    """Waves whose tile or list codes mean something else (left out of it, listed here for the data team)."""
    problems = []
    for code, cfg in load_config().items():
        ids = [w["survey_id"] for w in series(conn, cfg["module"]) if w["survey_id"]]
        specs = {s["code"]: s for s in cfg["tiles"] + cfg["lists"]}
        usual = meanings(conn, ids, list(specs.values()), cfg.get("aliases"))
        problems += [f"{code}.{spec}: {specs[spec]['qcode']} means something else in survey {sid}"
                     for (spec, sid), ok in sorted(usual.items()) if not ok]
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
        with etl_lock():   # a writer like any other: never alongside a load
            ids = [build(a.build, a.survey)] if a.survey else build_all(a.build)
        print(f"published builds: {ids}")
        return 0
    p.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
