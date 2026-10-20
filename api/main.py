"""CIP client API. Reads only the ETL's serving tables (sql/005_serving.sql) and its own caches.

  /api/v1/waves/{id}/results   finished rows for any (question, cut): one primary-key range read, then
                               cached per worker until the serving data changes (polled once a minute)
  /api/v1/waves                the survey picker: every built wave, newest first
  /api/v1/waves/{id}/book      the whole wave in the dashboard's shape (Overview, Question explorer,
                               Cross-tab matrix, Survey preview): every question × the 7 banner columns
  /api/v1/trend                one question's answers across every wave of its family (Total or one cut)
  /api/v1/search               questions across every survey and wave, from an in-memory catalogue
  /api/v1/waves/{id}/crosstab  one question by two cuts combined (e.g. generation × gender), optionally
                               pooled over the last 2–4 weekly waves: one GROUP BY on srv_answer, same cache
  /api/v1/dashboards/...       the sample dashboard's stored payloads (api/dashboards.py), from memory

    gunicorn api.main:app -k uvicorn.workers.UvicornWorker -w 2 -b 0.0.0.0:8000
"""
from __future__ import annotations

import asyncio
import base64
import gzip
import hashlib
import hmac
import json
import logging
import os
import time
from decimal import Decimal
from dataclasses import dataclass
from pathlib import Path

from collections import OrderedDict, defaultdict

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import bindparam, text
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.database import get_engine
from etl.serving import CUTS, SMALL_BASE

log = logging.getLogger("cip.api")
WEB = Path(__file__).resolve().parents[1] / "web" / "dist"
COOKIE = "cip_session"
SESSION_HOURS = 12
SECRET = os.environ.get("CIP_SESSION_SECRET", "").encode()
LOCAL = os.environ.get("APP_ENV", "").lower() == "local"   # dev sign-in only when explicitly local
REFRESH_SECONDS = 60


@dataclass(frozen=True)
class Payload:
    etag: str
    body: bytes   # JSON
    gz: bytes     # the same JSON, gzipped by the build


STORE: dict[tuple[str, int], Payload] = {}
LATEST: dict[str, int] = {}
STAMP: tuple = ()
SERVING: tuple = ()                      # (count, newest built_at) of srv_wave: the serving data's version
RESULTS: OrderedDict[tuple, Payload] = OrderedDict()   # (version, kind, args) → finished response, least recent first
CACHE_BYTES = int(os.environ.get("CIP_CACHE_MB", "256")) * 2**20   # per worker: the cache never grows past this
CACHED_BYTES = 0
CATALOGUE: list[dict] = []               # every reportable question of every built wave, grouped by wording
CACHE_RESULTS = os.environ.get("CIP_RESULT_CACHE", "1") != "0"   # 0 only to measure the database path
COLUMNS = ("qcode", "dim", "dim_value", "item_label", "option_code", "option_label", "n", "base_n",
           "pct", "prior_pct", "prior_base_n", "ly_pct", "ly_base_n", "flags")
CROSSTAB_COLUMNS = ("v1", "v2", "item_label", "option_code", "option_label", "n", "base_n", "pct", "flags")
BANNER = (("Total", "total", "Total"), ("Male", "gender", "Male"), ("Female", "gender", "Female"),
          ("Gen Z", "generation", "GenZ"), ("Millennial", "generation", "Millennial"), ("Gen X", "generation", "GenX"),
          ("Boomer", "generation", "Boomer"))   # dashboard column, srv_result dim, dim_value
HIDDEN_BASE = 30   # respondents: below this a two-cut cell shows no number at all, only "suppressed"


def _load() -> None:
    """Read every published payload (one query) and swap the in-memory store in one assignment."""
    global STORE, LATEST, STAMP
    with get_engine("app").connect() as conn:
        rows = conn.execute(text(
            "SELECT p.dashboard_code, p.survey_id, d.etag, d.payload_json, d.payload_gz, s.wave_date"
            "  FROM cip_dash_published p JOIN cip_dash_payload d ON d.build_id = p.build_id"
            "  JOIN cip_survey s ON s.survey_id = p.survey_id")).all()
        stamp = tuple(conn.execute(text("SELECT COUNT(*), MAX(published_at) FROM cip_dash_published")).one())
    store, newest = {}, {}
    for code, survey_id, etag, body, gz, wave_date in rows:
        store[(code, survey_id)] = Payload(f'"{etag}"', body.encode(), bytes(gz))
        if code not in newest or wave_date > newest[code][0]:
            newest[code] = (wave_date, survey_id)
    STORE, LATEST, STAMP = store, {c: s for c, (_, s) in newest.items()}, stamp
    log.info("Loaded %d dashboard payloads (%d KB gzipped)", len(store), sum(len(p.gz) for p in store.values()) // 1024)


def _changed() -> bool:
    global SERVING, RESULTS, CACHED_BYTES, CATALOGUE
    with get_engine("app").connect() as conn:
        serving = tuple(conn.execute(text("SELECT COUNT(*), MAX(built_at) FROM srv_wave")).one())
        dashboards = tuple(conn.execute(text("SELECT COUNT(*), MAX(published_at) FROM cip_dash_published")).one())
    if serving != SERVING:   # new serving data: old answers are never asked for again
        CATALOGUE = _load_catalogue()
        SERVING, RESULTS, CACHED_BYTES = serving, OrderedDict(), 0
    return dashboards != STAMP


def _load_catalogue() -> list[dict]:
    """Questions grouped by code and wording across all built waves: ≈ 9,000 rows → a few MB."""
    with get_engine("app").connect() as conn:
        rows = conn.execute(text(
            "SELECT q.survey_id, q.qcode, q.qtext, q.qtype, w.wave_date, w.survey_family, s.title FROM cip_question q"
            " JOIN srv_wave w ON w.survey_id = q.survey_id JOIN cip_survey s ON s.survey_id = q.survey_id"
            " WHERE q.is_technical = 0 AND q.is_virtual = 0 AND q.qtype IN ('single', 'multi', 'grid_single', 'grid_multi')"
            " ORDER BY w.wave_date")).mappings().all()
    groups: dict = {}
    for r in rows:
        key = (r["qcode"].upper(), " ".join(r["qtext"].lower().split()))
        g = groups.setdefault(key, {"qcode": r["qcode"], "text": r["qtext"], "type": r["qtype"], "family": r["survey_family"],
                                    "first": str(r["wave_date"]), "waves": 0})
        g.update(last=str(r["wave_date"]), survey_id=r["survey_id"], title=r["title"], waves=g["waves"] + 1)
        g["haystack"] = f'{r["qcode"]} {r["qtext"]} {r["title"]}'.lower()
    return list(groups.values())


async def _refresh_forever() -> None:
    while True:
        await asyncio.sleep(REFRESH_SECONDS)
        try:
            if await run_in_threadpool(_changed):
                await run_in_threadpool(_load)
        except Exception:   # keep serving the last good payloads; the next poll retries
            log.exception("Dashboard refresh failed; still serving the previous payloads")


app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


@app.on_event("startup")
async def startup() -> None:
    if not SECRET:
        raise RuntimeError("CIP_SESSION_SECRET is not set")
    await run_in_threadpool(_load)
    await run_in_threadpool(_changed)
    asyncio.get_running_loop().create_task(_refresh_forever())


# ── Sessions: an HMAC-signed cookie, checked in microseconds with no database call ────────────────
def _sign(value: str) -> str:
    return base64.urlsafe_b64encode(hmac.new(SECRET, value.encode(), hashlib.sha256).digest()).decode().rstrip("=")


def issue(email: str, products: str = "*") -> str:
    value = f"{email}|{products}|{int(time.time()) + SESSION_HOURS * 3600}"
    return f"{base64.urlsafe_b64encode(value.encode()).decode()}.{_sign(value)}"


def user(request: Request) -> dict:
    raw = request.cookies.get(COOKIE, "")
    try:
        encoded, signature = raw.rsplit(".", 1)
        value = base64.urlsafe_b64decode(encoded.encode()).decode()
        email, products, expires = value.split("|")
    except ValueError:
        raise HTTPException(401, "Sign in required")
    if not hmac.compare_digest(signature, _sign(value)) or int(expires) < time.time():
        raise HTTPException(401, "Sign in required")
    return {"email": email, "products": products.split(",")}


def _send(request: Request, item: Payload) -> Response:
    headers = {"ETag": item.etag, "Cache-Control": "private, max-age=60", "Vary": "Accept-Encoding, Cookie"}
    if request.headers.get("if-none-match") == item.etag:
        return Response(status_code=304, headers=headers)
    if "gzip" in request.headers.get("accept-encoding", ""):
        return Response(item.gz, media_type="application/json", headers={**headers, "Content-Encoding": "gzip"})
    return Response(item.body, media_type="application/json", headers=headers)


@app.get("/api/v1/dashboards/{code}")
async def latest(code: str, request: Request, who: dict = Depends(user)) -> Response:
    return await wave(code, LATEST.get(code, -1), request, who)


@app.get("/api/v1/dashboards/{code}/{survey_id}")
async def wave(code: str, survey_id: int, request: Request, who: dict = Depends(user)) -> Response:
    if "*" not in who["products"] and code not in who["products"]:
        raise HTTPException(403, "Not included in your subscription")
    item = STORE.get((code, survey_id))
    if item is None:
        raise HTTPException(404, "No published dashboard for that wave")
    return _send(request, item)


async def _cached(key: tuple, build, *args) -> Payload:
    """A finished response from this worker's cache, or built in a thread and kept until the serving data
    changes. Least recently used responses leave first once the cache reaches CACHE_BYTES."""
    global CACHED_BYTES
    item = RESULTS.get(key) if CACHE_RESULTS else None
    if item is not None:
        RESULTS.move_to_end(key)
        return item
    item = await run_in_threadpool(build, *args)
    if CACHE_RESULTS and key not in RESULTS:
        RESULTS[key] = item
        CACHED_BYTES += len(item.body) + len(item.gz)
        while CACHED_BYTES > CACHE_BYTES and len(RESULTS) > 1:
            _, old = RESULTS.popitem(last=False)
            CACHED_BYTES -= len(old.body) + len(old.gz)
    return item


def _json(data) -> Payload:
    """A finished response: compact JSON (decimals as numbers, dates as text), its ETag and its gzip."""
    body = json.dumps(data, default=lambda v: float(v) if isinstance(v, Decimal) else str(v), separators=(",", ":")).encode()
    return Payload(f'"{hashlib.sha256(body).hexdigest()[:16]}"', body, gzip.compress(body, 6))


def _query_results(survey_id: int, qcodes: tuple, dims: tuple) -> Payload:
    """One primary-key range read per question on srv_result; the rows are already finished."""
    with get_engine("app").connect() as conn:
        rows = conn.execute(text(
            f"SELECT {', '.join(COLUMNS)} FROM srv_result WHERE survey_id = :s AND qcode IN :q AND dim IN :d"
            " ORDER BY qcode, dim, dim_value, sort_order").bindparams(bindparam("q", expanding=True),
                                                                      bindparam("d", expanding=True)),
            {"s": survey_id, "q": list(qcodes), "d": list(dims)}).all()
    return _json({"survey_id": survey_id, "columns": COLUMNS, "rows": [list(r) for r in rows]})


@app.get("/api/v1/waves/{survey_id}/results")
async def results(survey_id: int, request: Request, q: str, dim: str = "total", who: dict = Depends(user)) -> Response:
    """Finished rows for any questions × cuts of one wave, e.g. ?q=XM3,XM1&dim=total,generation."""
    qcodes, dims = tuple(sorted(set(q.split(",")))[:20]), tuple(sorted(set(dim.split(",")))[:8])
    return _send(request, await _cached((SERVING, survey_id, qcodes, dims), _query_results, survey_id, qcodes, dims))


def _query_waves() -> Payload:
    with get_engine("app").connect() as conn:
        rows = conn.execute(text(
            "SELECT w.survey_id, s.title, s.wave_label, w.wave_date, w.survey_family, w.study_type, w.qualified_n,"
            " w.prior_survey_id, w.ly_survey_id, w.ly_status FROM srv_wave w JOIN cip_survey s ON s.survey_id = w.survey_id"
            " ORDER BY w.wave_date DESC, w.survey_id DESC")).mappings().all()
        modules = defaultdict(list)
        for survey_id, name in conn.execute(text(
                "SELECT survey_id, module_name FROM cip_wave_module WHERE survey_id IS NOT NULL ORDER BY is_lead DESC, module_name")):
            modules[survey_id].append(name)
    return _json([{**r, "modules": modules.get(r["survey_id"], [])} for r in rows])


def _query_book(survey_id: int) -> Payload:
    """Every reportable question of one wave with Total, gender and generation columns, in the shape the
    dashboard was designed on: {n: {column: base}, questions: [{id, text, groups: [{label, base, rows:
    [{label, column: pct}]}]}]}. A grid row is a group; a multi-select item or a single-choice answer is
    a row. Extra fields (type, section, per-column bases, prior week, flags) ride along."""
    columns = {(dim, value): name for name, dim, value in BANNER}
    with get_engine("app").connect() as conn:
        wave = conn.execute(text(
            "SELECT w.survey_id, s.title, s.wave_label, w.wave_date, w.survey_family, w.qualified_n, w.prior_survey_id,"
            " w.ly_survey_id, w.ly_status FROM srv_wave w JOIN cip_survey s ON s.survey_id = w.survey_id"
            " WHERE w.survey_id = :s"), {"s": survey_id}).mappings().first()
        if wave is None:
            raise HTTPException(404, "No such wave")
        questions = conn.execute(text(
            "SELECT q.qcode, q.qtext, q.qtext_short, q.qtype, q.base_desc, t.topic_name FROM cip_question q"
            " LEFT JOIN cip_topic t ON t.topic_id = q.topic_id WHERE q.survey_id = :s AND q.is_technical = 0"
            " AND q.is_virtual = 0 ORDER BY q.sort_order, q.question_id"), {"s": survey_id}).mappings().all()
        rows = conn.execute(text(
            "SELECT qcode, dim, dim_value, item_label, option_code, option_label, n, base_n, pct, prior_pct,"
            " prior_base_n, ly_pct, ly_base_n, flags FROM srv_result WHERE survey_id = :s AND dim IN ('total', 'gender', 'generation')"
            " ORDER BY qcode, sort_order"), {"s": survey_id}).mappings().all()
        modules = [r[0] for r in conn.execute(text("SELECT module_name FROM cip_wave_module WHERE survey_id = :s"), {"s": survey_id})]
        people = conn.execute(text(   # qualified respondents per banner column
            "SELECT p.gender, p.generation FROM cip_profile p JOIN cip_respondent r ON r.respondent_id = p.respondent_id"
            " AND r.is_qualified = 1 WHERE p.survey_id = :s"), {"s": survey_id}).all()
    n = {"Total": wave["qualified_n"]} | {name: 0 for name, _, _ in BANNER[1:]}
    for gender, generation in people:
        for dim, value in (("gender", gender), ("generation", generation)):
            if (dim, value) in columns:
                n[columns[(dim, value)]] += 1
    cells: dict = {}
    for r in rows:
        name = columns.get((r["dim"], r["dim_value"]))
        if name is None:
            continue
        cells.setdefault(r["qcode"], []).append((name, r))
    book = []
    for q in questions:
        if q["qcode"] not in cells:
            continue   # numeric and open text have no percentages
        multi = q["qtype"] in ("multi", "grid_multi")
        groups: dict = {}
        for name, r in cells[q["qcode"]]:
            group_label, row_label = ("", r["item_label"]) if multi else (r["item_label"], r["option_label"])
            group = groups.setdefault(group_label, {"label": group_label, "base": 0, "bases": {}, "rows": {}})
            group["bases"][name] = r["base_n"]
            row = group["rows"].setdefault(row_label, {"label": row_label, "code": r["option_code"]})
            row[name] = round(float(r["pct"]), 1)
            if name == "Total":
                group["base"] = r["base_n"]
                row["prior"] = None if r["prior_pct"] is None else round(float(r["prior_pct"]), 1)
                row["prior_base"] = r["prior_base_n"]
                row["ly"] = None if r["ly_pct"] is None else round(float(r["ly_pct"]), 1)
                row["ly_base"] = r["ly_base_n"]
                row["flags"] = r["flags"] or ""
        section = q["topic_name"] if q["topic_name"] not in (None, "Unclassified") else _module_section(q["qcode"], modules)
        book.append({"id": q["qcode"], "text": q["qtext"], "short": q["qtext_short"], "type": q["qtype"],
                     "section": section, "base_desc": q["base_desc"],
                     "groups": [{**g, "rows": list(g["rows"].values())} for g in groups.values()]})
    return _json({"wave": dict(wave), "columns": [name for name, _, _ in BANNER], "n": n, "questions": book})


def _query_trend(survey_id: int, qcode: str, dim: str, value: str) -> Payload:
    """The question's answers (Total, or one cut value) in every built wave of the wave's family and study
    type, oldest first. Answers are matched across waves by label and code, as srv_result's comparisons are."""
    with get_engine("app").connect() as conn:
        waves = conn.execute(text(
            "SELECT w.survey_id, w.wave_date FROM srv_wave w JOIN srv_wave me ON me.survey_id = :s"
            " AND w.survey_family = me.survey_family AND w.study_type = me.study_type ORDER BY w.wave_date"),
            {"s": survey_id}).mappings().all()
        rows = conn.execute(text(
            "SELECT survey_id, item_label, option_code, option_label, sort_order, n, base_n, pct FROM srv_result"
            " WHERE survey_id IN :ids AND qcode = :q AND dim = :d AND dim_value = :v")
            .bindparams(bindparam("ids", expanding=True)),
            {"ids": [w["survey_id"] for w in waves] or [-1], "q": qcode, "d": dim, "v": value}).mappings().all()
    if not any(r["survey_id"] == survey_id for r in rows):
        raise HTTPException(404, "That question is not in that wave")
    asked = {r["survey_id"] for r in rows}
    waves = [dict(w) for w in waves if w["survey_id"] in asked]
    at = {w["survey_id"]: i for i, w in enumerate(waves)}
    series: dict = {}
    for r in sorted(rows, key=lambda r: r["survey_id"] != survey_id):   # the requested wave's wording first
        s = series.setdefault((r["item_label"], r["option_code"]), {
            "item_label": r["item_label"], "code": r["option_code"], "label": r["option_label"] or r["item_label"],
            "sort": r["sort_order"], "pct": [None] * len(waves), "base": [None] * len(waves)})
        s["pct"][at[r["survey_id"]]] = round(float(r["pct"]), 1)
        s["base"][at[r["survey_id"]]] = r["base_n"]
    return _json({"qcode": qcode, "dim": dim, "value": value, "waves": waves,
                  "series": sorted(series.values(), key=lambda s: s["sort"])})


def _search(words: list[str], limit: int) -> list[dict]:
    hits = [g for g in CATALOGUE if all(w in g["haystack"] for w in words)]
    hits.sort(key=lambda g: (g["last"], g["waves"]), reverse=True)
    return [{k: v for k, v in g.items() if k != "haystack"} for g in hits[:limit]]


def _module_section(qcode: str, modules: list[str]) -> str:
    """A section for a question the topic map has not classified: the wave module whose initials begin with
    the code's letters (HI → "Home improvement / DIY", BD → "Big Deal Days Retro"), else "<letters> block"."""
    letters = "".join(ch for ch in qcode.split("_")[0] if ch.isalpha()).upper()
    for name in modules:
        initials = "".join(w[0] for w in name.replace("/", " ").split() if w[0].isalpha()).upper()
        if letters and initials.startswith(letters):
            return name
    return f"{letters} block"


def _pool(conn, survey_id: int, weeks: int) -> list[dict]:
    """The wave and up to weeks - 1 earlier ones, following the same prior-week chain as srv_result."""
    family = {r["survey_id"]: r for r in conn.execute(text(   # one round trip: the family's latest waves up to this one
        "SELECT w.survey_id, w.wave_date, w.prior_survey_id FROM srv_wave w JOIN srv_wave me ON me.survey_id = :s"
        " AND w.survey_family = me.survey_family AND w.wave_date <= me.wave_date ORDER BY w.wave_date DESC LIMIT 20"),
        {"s": survey_id}).mappings()}
    waves = []
    while survey_id in family and len(waves) < weeks:
        waves.append(family[survey_id])
        survey_id = family[survey_id]["prior_survey_id"]
    return waves


def _query_crosstab(survey_id: int, qcode: str, by: tuple, weeks: int) -> Payload:
    """Counts by two cuts from srv_answer, pooled across waves on the answer's label and code (ids differ
    per wave, as in srv_result's comparisons), then bases, percentages and flags. Respondents with no
    value for a cut are left out, as in srv_result. Cells nobody chose come back as n = 0."""
    first, second = by
    with get_engine("app").connect() as conn:
        waves = _pool(conn, survey_id, weeks)
        ids = [w["survey_id"] for w in waves] or [-1]
        counts = conn.execute(text(
            f"SELECT survey_id, item_id, option_id, {first}, {second}, COUNT(*) FROM srv_answer"
            f" WHERE survey_id IN :ids AND qcode = :q GROUP BY survey_id, item_id, option_id, {first}, {second}")
            .bindparams(bindparam("ids", expanding=True)), {"ids": ids, "q": qcode}).all()
        answers = conn.execute(text(
            "SELECT survey_id, item_id, option_id, item_label, option_code, option_label, sort_order, flags"
            " FROM srv_result WHERE survey_id IN :ids AND qcode = :q AND dim = 'total'")
            .bindparams(bindparam("ids", expanding=True)), {"ids": ids, "q": qcode}).mappings().all()
    if not any(a["survey_id"] == survey_id for a in answers):
        raise HTTPException(404, "That question is not in that wave")
    label = {(a["survey_id"], a["item_id"], a["option_id"]): a for a in answers}
    order = {}   # answer → (sort order, label), the requested wave's wording first
    for a in sorted(answers, key=lambda a: a["survey_id"] != survey_id):
        order.setdefault((a["item_label"], a["option_code"]), (a["sort_order"], a["option_label"]))
    n, base = defaultdict(int), defaultdict(int)
    for sid, item, option, v1, v2, count in counts:
        if "" in (v1, v2):
            continue
        if item == 0 and option == 0:            # multi base row: answered the question
            base[(v1, v2, None)] += count
            continue
        a = label.get((sid, item, option))
        if a is None:
            continue
        n[(v1, v2, a["item_label"], a["option_code"])] += count
        if option:                               # single choice: base = answered this row
            base[(v1, v2, a["item_label"])] += count
    multi = all(a["option_id"] == 0 for a in answers)
    cells = sorted({(v1, v2) for v1, v2, _ in base})
    rows = []
    for v1, v2 in cells:
        for (item_label, code), (_, option_label) in sorted(order.items(), key=lambda kv: kv[1][0]):
            b = base.get((v1, v2, None if multi else item_label), 0)
            if not b:
                continue
            count = n.get((v1, v2, item_label, code), 0)
            if b < HIDDEN_BASE:
                rows.append([v1, v2, item_label, code, option_label, None, b, None, "suppressed"])
            else:
                rows.append([v1, v2, item_label, code, option_label, count, b, round(100 * count / b, 3),
                             "small_base" if b < SMALL_BASE else ""])
    asked = {a["survey_id"] for a in answers}
    waves = [w for w in waves if w["survey_id"] in asked]
    # a wave whose question base moved against its prior week, when both are in the pool, mixes populations
    inside = {w["survey_id"] for w in waves if w["prior_survey_id"] in asked}
    warnings = ["base_changed_within_pool"] if any(
        "base_changed_prior" in (a["flags"] or "") and a["survey_id"] in inside for a in answers) else []
    return _json({"survey_id": survey_id, "qcode": qcode, "by": list(by), "weeks": len(waves),
                  "waves": [{"survey_id": w["survey_id"], "wave_date": w["wave_date"]} for w in waves],
                  "warnings": warnings, "columns": CROSSTAB_COLUMNS, "rows": rows})


@app.get("/api/v1/waves")
async def waves(request: Request, who: dict = Depends(user)) -> Response:
    return _send(request, await _cached((SERVING, "waves"), _query_waves))


@app.get("/api/v1/waves/{survey_id}/book")
async def book(survey_id: int, request: Request, who: dict = Depends(user)) -> Response:
    """The whole wave for the four dashboard screens in one cached response (≈ 30 KB gzipped)."""
    return _send(request, await _cached((SERVING, "book", survey_id), _query_book, survey_id))


@app.get("/api/v1/trend")
async def trend(survey_id: int, q: str, request: Request, dim: str = "total", value: str = "Total",
                who: dict = Depends(user)) -> Response:
    """E.g. ?survey_id=412&q=XM3 (Total) or &dim=generation&value=GenZ: one line per answer over the waves."""
    if dim not in ("total",) + CUTS:
        raise HTTPException(422, f"dim takes total or one of: {', '.join(CUTS)}")
    return _send(request, await _cached((SERVING, "trend", survey_id, q, dim, value), _query_trend, survey_id, q, dim, value))


@app.get("/api/v1/search")
async def search(request: Request, q: str = Query(..., min_length=2, max_length=100), limit: int = Query(40, ge=1, le=200),
                 who: dict = Depends(user)) -> Response:
    """Questions whose code, wording or survey title contain every word, latest first."""
    words = tuple(sorted(set(q.lower().split())))
    return _send(request, await _cached((SERVING, "search", words, limit), lambda: _json({"results": _search(list(words), limit)})))


@app.get("/api/v1/waves/{survey_id}/crosstab")
async def crosstab(survey_id: int, request: Request, q: str, by: str, weeks: int = Query(1, ge=1, le=4),
                   who: dict = Depends(user)) -> Response:
    """One question by two cuts, e.g. ?q=XM3&by=generation,gender&weeks=4 (this wave and the 3 before)."""
    cuts = tuple(by.split(","))
    if len(cuts) != 2 or len(set(cuts)) != 2 or not set(cuts) <= set(CUTS):
        raise HTTPException(422, f"by takes two different cuts from: {', '.join(CUTS)}")
    return _send(request, await _cached((SERVING, "crosstab", survey_id, q, cuts, weeks),
                                        _query_crosstab, survey_id, q, cuts, weeks))


@app.get("/healthz")
async def healthz() -> dict:
    return {"dashboards": len(STORE), "published": str(STAMP[1]) if STAMP else None,
            "serving_waves": SERVING[0] if SERVING else 0, "serving_built": str(SERVING[1]) if SERVING else None,
            "cached_results": len(RESULTS), "cached_mb": round(CACHED_BYTES / 2**20, 1), "catalogue": len(CATALOGUE)}


@app.get("/auth/dev-login")
async def dev_login(email: str = "analyst@coresight.com", next: str = "/") -> Response:
    """Local development and load tests only; production signs in through the identity provider (OIDC)."""
    if not LOCAL:
        raise HTTPException(404)
    target = next if next.startswith("/") and not next.startswith("//") else "/"   # same-site paths only
    response = RedirectResponse(target, status_code=303)
    response.set_cookie(COOKIE, issue(email), httponly=True, samesite="lax", secure=False, max_age=SESSION_HOURS * 3600)
    return response


@app.middleware("http")
async def cache_static(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/assets/"):   # Vite's content-hashed files never change
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return response


class SinglePageApp(StaticFiles):
    """dist/ as files, and index.html for any other path, so a deep link like /w/412/crosstab opens the app."""
    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:   # StaticFiles raises Starlette's 404, not FastAPI's
            if exc.status_code != 404 or path.startswith(("api/", "auth/", "assets/")):
                raise
            return await super().get_response("index.html", scope)


if WEB.exists():
    app.mount("/", SinglePageApp(directory=WEB, html=True), name="web")
