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
from app.data import payloads
from api.search import SearchIndex
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
BUILD_SLOTS = asyncio.Semaphore(int(os.environ.get("CIP_BUILD_SLOTS", "8")))   # concurrent database builds per worker
BUILD_WAIT = float(os.environ.get("CIP_BUILD_WAIT", "3"))   # seconds a request may queue for a slot before "busy, retry"
CATALOGUE: SearchIndex | None = None     # every reportable question of every built wave (api/search.py)
CACHE_RESULTS = os.environ.get("CIP_RESULT_CACHE", "1") != "0"   # 0 only to measure the database path


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


def _load_catalogue() -> SearchIndex:
    """Every reportable question of every built wave, one search document per code + wording, with its answer
    labels and the surveys that asked it: ≈ 3,000 documents, a few MB, rebuilt when the serving data changes."""
    with get_engine("app").connect() as conn:
        rows = conn.execute(text(
            "SELECT q.survey_id, q.qcode, q.qtext, q.qtype, w.wave_date, w.survey_family, s.title FROM cip_question q"
            " JOIN srv_wave w ON w.survey_id = q.survey_id JOIN cip_survey s ON s.survey_id = q.survey_id"
            " WHERE q.is_technical = 0 AND q.is_virtual = 0 AND q.qtype IN ('single', 'multi', 'grid_single', 'grid_multi')"
            " ORDER BY w.wave_date")).mappings().all()
        labels = defaultdict(set)
        for survey_id, qcode, item, option in conn.execute(text(
                "SELECT DISTINCT survey_id, qcode, item_label, option_label FROM srv_result WHERE dim = 'total'")):
            labels[(survey_id, qcode)].update(x for x in (item, option) if x)
    groups: dict = {}
    for r in rows:
        key = (r["qcode"].upper(), " ".join(r["qtext"].lower().split()))
        g = groups.setdefault(key, {"qcode": r["qcode"], "text": r["qtext"], "type": r["qtype"], "family": r["survey_family"],
                                    "first": str(r["wave_date"]), "waves": 0, "_answers": set(), "_titles": set()})
        g.update(last=str(r["wave_date"]), survey_id=r["survey_id"], title=r["title"], waves=g["waves"] + 1)
        g["_answers"] |= labels.get((r["survey_id"], r["qcode"]), set())
        g["_titles"].add(r["title"])
    docs = [{**{k: v for k, v in g.items() if not k.startswith("_")},
             "answers": " · ".join(sorted(g["_answers"]))[:4000], "titles": " · ".join(sorted(g["_titles"]))[:2000]}
            for g in groups.values()]
    return SearchIndex(docs)


async def _refresh_forever() -> None:
    while True:
        await asyncio.sleep(REFRESH_SECONDS)
        try:
            if await run_in_threadpool(_changed):
                await run_in_threadpool(_load)
        except Exception:   # keep serving the last good payloads; the next poll retries
            log.exception("Dashboard refresh failed; still serving the previous payloads")


# OpenAPI: the typed contract a future chatbot's tools are generated from (docs/Ui-Design-Claude/20)
app = FastAPI(title="Coresight Consumer Insight Portal API", version="1", docs_url=None, redoc_url=None,
              openapi_url="/api/v1/openapi.json")


@app.exception_handler(LookupError)
async def not_found(request: Request, exc: LookupError) -> Response:
    return Response(json.dumps({"detail": str(exc).strip("'")}), status_code=404, media_type="application/json")


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
    # admission control: a burst of cache misses queues briefly for a slot, then gets a fast 503 the screen
    # turns into "busy, retry" — never a pile-up that slows every request on the one core
    try:
        await asyncio.wait_for(BUILD_SLOTS.acquire(), BUILD_WAIT)
    except asyncio.TimeoutError:
        raise HTTPException(503, "Busy: please retry in a few seconds", headers={"Retry-After": "3"})
    try:
        item = await run_in_threadpool(build, *args)
    finally:
        BUILD_SLOTS.release()
    if CACHE_RESULTS and key not in RESULTS:
        RESULTS[key] = item
        CACHED_BYTES += len(item.body) + len(item.gz)
        while CACHED_BYTES > CACHE_BYTES and len(RESULTS) > 1:
            _, old = RESULTS.popitem(last=False)
            CACHED_BYTES -= len(old.body) + len(old.gz)
    return item


def _json(data) -> Payload:
    """A finished response: compact JSON (app/data/payloads.encode), its ETag and its gzip."""
    body = payloads.encode(data)
    return Payload(f'"{hashlib.sha256(body).hexdigest()[:16]}"', body, gzip.compress(body, 6))


def _boards() -> dict:
    """Module dashboards published per wave (api/dashboards.py, config/dashboards.yml)."""
    boards = defaultdict(list)
    for code, survey_id in STORE:
        boards[survey_id].append(code)
    return boards


@app.get("/api/v1/waves/{survey_id}/results")
async def results(survey_id: int, request: Request, q: str, dim: str = "total", who: dict = Depends(user)) -> Response:
    """Finished rows for any questions × cuts of one wave, e.g. ?q=XM3,XM1&dim=total,generation."""
    qcodes, dims = tuple(sorted(set(q.split(",")))[:20]), tuple(sorted(set(dim.split(",")))[:8])
    return _send(request, await _cached((SERVING, survey_id, qcodes, dims), lambda: _json(payloads.results(survey_id, qcodes, dims))))


@app.get("/api/v1/waves")
async def waves(request: Request, who: dict = Depends(user)) -> Response:
    return _send(request, await _cached((SERVING, "waves"), lambda: _json(payloads.waves(_boards()))))


@app.get("/api/v1/waves/{survey_id}/book")
async def book(survey_id: int, request: Request, who: dict = Depends(user)) -> Response:
    """The whole wave for the four dashboard screens in one cached response (≈ 30 KB gzipped)."""
    return _send(request, await _cached((SERVING, "book", survey_id), lambda: _json(payloads.book(survey_id))))


@app.get("/api/v1/trend")
async def trend(survey_id: int, q: str, request: Request, dim: str = "total", value: str = "Total",
                who: dict = Depends(user)) -> Response:
    """E.g. ?survey_id=412&q=XM3 (Total) or &dim=generation&value=GenZ: one line per answer over the waves."""
    if dim not in ("total",) + CUTS:
        raise HTTPException(422, f"dim takes total or one of: {', '.join(CUTS)}")
    return _send(request, await _cached((SERVING, "trend", survey_id, q, dim, value), lambda: _json(payloads.trend(survey_id, q, dim, value))))


@app.get("/api/v1/trends/{family}/{study_type}/{qcode}/{dim}/{value}")
async def family_trend(family: str, study_type: str, qcode: str, dim: str, value: str, request: Request,
                       who: dict = Depends(user)) -> Response:
    """A question across every wave of one tracker family, for Total or one banner column. The ETL publishes
    these for every multi-wave family (etl/publish.py) and nginx serves the files; this answers the rest."""
    if dim not in ("total",) + CUTS:
        raise HTTPException(422, f"dim takes total or one of: {', '.join(CUTS)}")
    return _send(request, await _cached((SERVING, "family_trend", family, study_type, qcode, dim, value),
                                        lambda: _json(payloads.family_trend(family, study_type, qcode, dim, value))))


@app.get("/api/v1/search")
async def search(request: Request, q: str = Query(..., min_length=2, max_length=100), limit: int = Query(40, ge=1, le=200),
                 who: dict = Depends(user)) -> Response:
    """Questions by words, code, answer label or survey title, typo- and synonym-tolerant (api/search.py).
    The response says what it understood: {"results": [...], "understood": {corrected, expanded, matched_by}}."""
    def run() -> Payload:
        found = CATALOGUE.search(q, limit) if CATALOGUE else {"results": [], "understood": {}}
        if not found["results"]:
            log.info("search with no results: %r", q[:100])   # reviewed monthly to grow config/search_synonyms.yml
        return _json(found)
    return _send(request, await _cached((SERVING, "search", " ".join(q.lower().split()), limit), run))


@app.get("/api/v1/waves/{survey_id}/crosstab")
async def crosstab(survey_id: int, request: Request, q: str, by: str, weeks: int = Query(1, ge=1, le=4),
                   who: dict = Depends(user)) -> Response:
    """One question by two cuts, e.g. ?q=XM3&by=generation,gender&weeks=4 (this wave and the 3 before)."""
    cuts = tuple(by.split(","))
    if len(cuts) != 2 or len(set(cuts)) != 2 or not set(cuts) <= set(CUTS):
        raise HTTPException(422, f"by takes two different cuts from: {', '.join(CUTS)}")
    return _send(request, await _cached((SERVING, "crosstab", survey_id, q, cuts, weeks),
                                        lambda: _json(payloads.crosstab(survey_id, q, cuts, weeks))))


@app.get("/healthz")
async def healthz() -> dict:
    return {"dashboards": len(STORE), "published": str(STAMP[1]) if STAMP else None,
            "serving_waves": SERVING[0] if SERVING else 0, "serving_built": str(SERVING[1]) if SERVING else None,
            "cached_results": len(RESULTS), "cached_mb": round(CACHED_BYTES / 2**20, 1), "catalogue": len(CATALOGUE.docs) if CATALOGUE else 0}


@app.get("/auth/check", status_code=204)
async def auth_check(who: dict = Depends(user)) -> Response:
    """nginx auth_request: 204 if the session cookie is valid (HMAC only, no database), else 401."""
    return Response(status_code=204)


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
    elif response.headers.get("content-type", "").startswith("text/html"):   # index.html names this release's
        response.headers["Cache-Control"] = "no-cache"                        # assets: always revalidate it
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
