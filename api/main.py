"""CIP client API. Reads only the ETL's serving tables (sql/005_serving.sql) and its own caches.

  /api/v1/waves/{id}/results   finished rows for any (question, cut): one primary-key range read, then
                               cached per worker until the serving data changes (polled once a minute)
  /api/v1/waves                the survey picker: every built wave, newest first
  /api/v1/waves/{id}/book      the whole wave in the dashboard's shape (Overview, Question explorer,
                               Cross-tab matrix, Survey preview): every question × the 7 banner columns
  /api/v1/search               questions across every survey and wave, from an in-memory catalogue
  /api/v1/waves/{id}/crosstab  one question by two cuts combined (e.g. generation × gender), optionally
                               pooled over the last 2–4 weekly waves: one GROUP BY on srv_answer, same cache
  /api/v1/questions/<family>/<study>/<qcode>   one question, every wave and cut, compact (Compare, Trends)
  /api/v1/dashboards/...       the sample dashboard's stored payloads (api/dashboards.py), from memory
  /api/v1/me, /methodology     who is signed in and what they may use; how the numbers are made (config/methodology.yml)
  /auth/...                    sign-in, sign-out and the session check (api/signin.py)

Every /api route needs a signed-in session, sees only the waves the person's tier and client may see
(shared/core/access.py), and answers errors as {"detail": text, "status": code}.

    gunicorn api.main:app -k uvicorn.workers.UvicornWorker -w 2 -b 0.0.0.0:8000
"""
from __future__ import annotations

import asyncio
import base64
import gzip
import hashlib
import json
import logging
import os
import re
import threading
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional
from pathlib import Path

from collections import OrderedDict, defaultdict

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, text
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import Headers
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.staticfiles import NotModifiedResponse

from shared.core import access, api_keys, audit
from shared.core.database import apply_sql, get_engine
from shared.data import payloads
from api import assistant, exports, ingest, logs, mcp, metrics, signin, team
from api.search import SearchIndex
from api.signin import admin, user
from etl import launch_schedule
from etl.publish import ROOT as PUBLISH_ROOT
from etl.serving import CUTS

log = logging.getLogger("cip.api")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s | %(message)s")   # [PERF] lines show
WEB = Path(os.environ.get("CIP_WEB_DIR") or Path(__file__).resolve().parents[1] / "web" / "dist")
SECRET = os.environ.get("CIP_SESSION_SECRET", "").encode()
REFRESH_SECONDS = 60
METHODOLOGY = Path(__file__).resolve().parents[1] / "config" / "methodology.yml"


def build_id() -> str:
    """The code this process runs: CIP_BUILD from the image, else the checkout's commit (a dirty tree says so)."""
    if os.environ.get("CIP_BUILD"):
        return os.environ["CIP_BUILD"]
    import subprocess
    try:
        return subprocess.run(["git", "describe", "--always", "--dirty"], capture_output=True, text=True, timeout=5,
                              cwd=Path(__file__).parent).stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


BUILD = build_id()


@dataclass(frozen=True)
class Payload:
    etag: str
    body: bytes   # JSON
    gz: bytes     # the same JSON, gzipped by the build


STORE: dict[tuple[str, int], Payload] = {}
LATEST: dict[str, int] = {}
STAMP: tuple = ()
SCHEDULE: Payload | None = None          # the launch plan against the Forsta register, rebuilt every poll
SERVING: tuple = ()                      # (count, newest built_at) of srv_wave: the serving data's version
RESULTS: OrderedDict[tuple, Payload] = OrderedDict()   # (version, kind, args) → finished response, least recent first
CACHE_BYTES = int(os.environ.get("CIP_CACHE_MB", "256")) * 2**20   # per worker: the cache never grows past this
CACHED_BYTES = 0
CACHE_COUNTS = {"hits": 0, "misses": 0}   # RESULTS answered from memory vs built, since this process started (Logs page)
BUILD_SLOTS = asyncio.Semaphore(int(os.environ.get("CIP_BUILD_SLOTS", "8")))   # concurrent database builds per worker
BUILD_WAIT = float(os.environ.get("CIP_BUILD_WAIT", "3"))
ASK_SLOTS = asyncio.Semaphore(int(os.environ.get("CIP_ASK_SLOTS", "6")))   # Ask questions at once per worker: most of a new one
ASK_WAIT = 8.0                                                              # is ~2 s waiting on the model (no CPU); seconds a question queues   # seconds a request may queue for a slot before "busy, retry"
CATALOGUE: SearchIndex | None = None     # every reportable question of every built wave (api/search.py)
CATALOGUE_ROWS: tuple = ()               # what CATALOGUE was built from, to build a filtered one per scope
SCOPED: dict[str, SearchIndex] = {}      # scope (shared/core/access.scope) → the catalogue of the waves it may see
WAVES: tuple = ((), [])                  # (data version, every built wave described): the visibility rule's input
WAVES_LOCK = threading.Lock()            # one thread rebuilds the list; a burst after a deploy waits for it, not the pool
CACHE_RESULTS = os.environ.get("CIP_RESULT_CACHE", "1") != "0"   # 0 only to measure the database path
PUBLISHED = PUBLISH_ROOT / "current"     # the ETL's prebuilt responses (etl/publish.py): no database work on a view
PUBLISHED_VERSION = ""


def load_published() -> None:
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


def published_changed() -> bool:
    global SERVING, RESULTS, CACHED_BYTES, CATALOGUE, PUBLISHED_VERSION
    with get_engine("app").connect() as conn:
        serving = tuple(conn.execute(text("SELECT COUNT(*), MAX(built_at) FROM srv_wave")).one())
        dashboards = tuple(conn.execute(text("SELECT COUNT(*), MAX(published_at) FROM cip_dash_published")).one())
    if serving != SERVING:
        CATALOGUE = _load_catalogue()
        SCOPED.clear()
    version = os.path.realpath(PUBLISHED)
    if serving != SERVING or version != PUBLISHED_VERSION:   # new data or a new publish: old answers are never asked for again
        SERVING, PUBLISHED_VERSION, RESULTS, CACHED_BYTES = serving, version, OrderedDict(), 0
    return dashboards != STAMP


def published_file(*parts: str) -> Payload | None:
    """The prebuilt response for api/v1/<parts>, or None when it was not published (a new wave before the next
    publish, a single-wave family's trend): the caller then builds it from the database."""
    if any(not p or p.startswith(".") or ".." in p or "/" in p or "\\" in p for p in parts):
        return None
    path = PUBLISHED.joinpath("api", "v1", *parts)
    try:
        gz = path.with_name(path.name + ".json.gz").read_bytes()
    except OSError:
        return None
    body = gzip.decompress(gz)
    return Payload(f'"{hashlib.sha256(body).hexdigest()[:16]}"', body, gz)


def _load_catalogue() -> SearchIndex:
    """Every reportable question of every built wave, one search document per code + wording, with its answer
    labels and the surveys that asked it: ≈ 3,000 documents, a few MB, rebuilt when the serving data changes."""
    global CATALOGUE_ROWS
    with get_engine("app").connect() as conn:
        rows = conn.execute(text(
            "SELECT q.survey_id, q.qcode, q.qtext, q.qtype, w.wave_date, w.survey_family, w.study_type, s.title FROM cip_question q"
            " JOIN srv_wave w ON w.survey_id = q.survey_id JOIN cip_survey s ON s.survey_id = q.survey_id"
            " WHERE q.is_technical = 0 AND q.is_virtual = 0 AND q.qtype IN ('single', 'multi', 'grid_single', 'grid_multi')"
            " ORDER BY w.wave_date")).mappings().all()
        labels = defaultdict(set)
        for sid, qc, lbl in conn.execute(text(
                "SELECT q.survey_id, q.qcode, o.value_label FROM cip_option o"
                " JOIN cip_question q ON q.question_id = o.question_id")):
            if lbl:
                labels[(sid, qc)].add(lbl)
        for sid, qc, lbl in conn.execute(text(
                "SELECT q.survey_id, q.qcode, i.item_label FROM cip_item i"
                " JOIN cip_question q ON q.question_id = i.question_id")):
            if lbl:
                labels[(sid, qc)].add(lbl)
        measure = {(sid, qc): (cid, name) for sid, qc, cid, name in conn.execute(text(   # the harmonised concept: a measure
            "SELECT m.survey_id, q.qcode, MIN(c.concept_id), MIN(COALESCE(c.concept_group, c.concept_name)) FROM cip_concept_map m"
            " JOIN cip_concept c ON c.concept_id = m.concept_id JOIN cip_question q ON q.question_id = m.question_id"
            " WHERE m.status = 'confirmed' AND m.concept_option_id IS NULL GROUP BY m.survey_id, q.qcode"))}
    CATALOGUE_ROWS = (rows, labels, measure)
    return _catalogue(rows, labels, measure)


def _catalogue(rows, labels, measure) -> SearchIndex:
    groups: dict = {}
    for r in rows:
        key = (r["qcode"].upper(), " ".join(r["qtext"].lower().split()))
        g = groups.setdefault(key, {"qcode": r["qcode"], "text": r["qtext"], "type": r["qtype"], "family": r["survey_family"],
                                    "first": str(r["wave_date"]), "waves": 0, "_answers": set(), "_titles": set()})
        g.update(last=str(r["wave_date"]), survey_id=r["survey_id"], title=r["title"], waves=g["waves"] + 1)
        g["_answers"] |= labels.get((r["survey_id"], r["qcode"]), set())
        g["_titles"].add(r["title"])
        if (r["survey_id"], r["qcode"]) in measure:
            g["measure_id"], g["measure"] = measure[(r["survey_id"], r["qcode"])]
    docs = [{**{k: v for k, v in g.items() if not k.startswith("_")},
             "answers": " · ".join(sorted(g["_answers"]))[:4000], "titles": " · ".join(sorted(g["_titles"]))[:2000]}
            for g in groups.values()]
    return SearchIndex(docs)


def _load_schedule() -> None:
    global SCHEDULE
    SCHEDULE = to_payload(launch_schedule.weeks())


async def _refresh_forever() -> None:
    while True:
        await asyncio.sleep(REFRESH_SECONDS)
        try:
            if await run_in_threadpool(published_changed):
                await run_in_threadpool(load_published)
            await run_in_threadpool(_load_schedule)
            await run_in_threadpool(signin.load_revoked)
            await run_in_threadpool(metrics.read_traffic)   # every minute, so a busy log is counted before it rotates
            await run_in_threadpool(metrics.measure_storage)   # folder and database sizes, at most every 5 minutes
        except Exception:   # keep serving the last good payloads; the next poll retries
            log.exception("Dashboard refresh failed; still serving the previous payloads")


def report_caches() -> list[dict]:
    """The API's memory caches for the Logs page (api/metrics.py CACHE_REPORTERS): what each holds, its size, its hits."""
    asked = CACHE_COUNTS["hits"] + CACHE_COUNTS["misses"]
    search_mb = 0.0
    if CATALOGUE is not None:   # the search index is an in-memory SQLite database
        pages, size = (CATALOGUE.db.execute(f"PRAGMA {p}").fetchone()[0] for p in ("page_count", "page_size"))
        search_mb = round(pages * size / 2**20, 1)
    return [
        {"name": "API answer cache (Python)", "where": "API memory",
         "meaning": f"Answers the API built once (cross-tabs, results, search), kept until the data changes; at most {CACHE_BYTES // 2**20} MB.",
         "answered": CACHE_COUNTS["hits"], "share_pct": round(100 * CACHE_COUNTS["hits"] / max(1, asked), 1),
         "size_mb": round(CACHED_BYTES / 2**20, 1), "entries": len(RESULTS),
         "detail": {"answered from memory": CACHE_COUNTS["hits"], "built (first asker)": CACHE_COUNTS["misses"]}},
        {"name": "Dashboard and wave store (Python)", "where": "API memory",
         "meaning": "Every published dashboard and the wave list, loaded at start and refreshed when the data changes.",
         "size_mb": round(sum(len(x.body) + len(x.gz) for x in STORE.values()) / 2**20, 1), "entries": len(STORE)},
        {"name": "Search index", "where": "API memory",
         "meaning": "Every question of every wave, for Search and Ask.", "size_mb": search_mb},
    ]


metrics.CACHE_REPORTERS.append(report_caches)


def check_settings() -> None:
    """Refuse to start rather than run unsafely: no signing key, a guessable one on a server, or the demo sign-in
    (anyone as anyone) in production."""
    if not SECRET:
        raise RuntimeError("CIP_SESSION_SECRET is not set")
    env = os.environ.get("APP_ENV", "").lower()
    if env in ("production", "staging") and len(SECRET) < 32:
        raise RuntimeError("CIP_SESSION_SECRET must be at least 32 random characters on a server")
    if env == "production" and signin.demo():
        raise RuntimeError("CIP_DEMO_LOGIN=1 lets anyone sign in as any email: never in production")


@asynccontextmanager
async def lifespan(app: FastAPI):
    check_settings()
    await run_in_threadpool(load_published)
    await run_in_threadpool(published_changed)
    await run_in_threadpool(_load_schedule)
    audit.start()
    task = asyncio.get_running_loop().create_task(_refresh_forever())
    asyncio.get_running_loop().run_in_executor(None, metrics.measure_storage)   # the Logs page's storage table, at start
    # the first read of the request log (up to 64 MB) at start, in the background: on 7 Nov 2026 the first Logs visit
    # after a deploy did it and waited 5.4 s
    asyncio.get_running_loop().run_in_executor(None, metrics.read_traffic)
    asyncio.get_running_loop().run_in_executor(None, warm_ask)   # Ask CIP's index (~1 s), so no question waits for it
    try:
        yield
    finally:
        task.cancel()


# OpenAPI: the typed contract a future chatbot's tools are generated from (api/mcp.py); signed-in only
app = FastAPI(title="Coresight Consumer Insight Portal API", version="1", docs_url=None, redoc_url=None,
              openapi_url=None, lifespan=lifespan)


def failed(status: int, detail: str, headers: dict | None = None) -> JSONResponse:
    """Every error, one shape: {"detail": what went wrong, in words, "status": the HTTP code}."""
    return JSONResponse({"detail": detail, "status": status}, status_code=status, headers=headers)


@app.exception_handler(LookupError)
async def not_found(request: Request, exc: LookupError) -> Response:
    return failed(404, str(exc).strip("'"))


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException) -> Response:
    return failed(exc.status_code, str(exc.detail), getattr(exc, "headers", None))


@app.exception_handler(RequestValidationError)
async def bad_request(request: Request, exc: RequestValidationError) -> Response:
    said = "; ".join(f"{'.'.join(str(p) for p in e.get('loc', ())[1:]) or 'body'}: {e.get('msg', '')}" for e in exc.errors())
    return failed(422, said or "The request is not valid")


@app.exception_handler(Exception)
async def server_error(request: Request, exc: Exception) -> Response:
    log.exception("Unhandled error on %s %s", request.method, request.url.path)
    return failed(500, "Something went wrong on our side; it has been logged")


@app.get("/api/v1/openapi.json", include_in_schema=False)
async def openapi(who: dict = Depends(user)) -> dict:
    return app.openapi()


def all_waves() -> list[dict]:
    """Every built wave, described (payloads.describe), from the published list or the database: once per data version."""
    global WAVES
    version = (SERVING, PUBLISHED_VERSION, os.path.realpath(PUBLISHED))
    if WAVES[0] == version:
        return WAVES[1]
    with WAVES_LOCK:
        if WAVES[0] != version:
            listed = published_file("waves")
            published = json.loads(listed.body) if listed else []
            # a wave built since the last publish (532 on a machine with no ETL loop) is listed from the database, its
            # screens built live, instead of answering "No such wave"; one read per data version, none when they agree
            waves = payloads.waves(_boards()) if not published or (SERVING and len(published) < SERVING[0]) else published
            WAVES = (version, [payloads.describe(w) for w in waves])
        return WAVES[1]


async def visible(who: dict, survey_id: int) -> dict:
    """The wave, if this person may open it; else 404, so a hidden study is indistinguishable from a missing one."""
    wave = next((w for w in await run_in_threadpool(all_waves) if w["survey_id"] == survey_id), None)
    if wave is None or not access.sees(who, wave):
        raise HTTPException(404, "No such wave")
    return wave


def require_feature(who: dict, *features: str) -> None:
    """403 unless the person's menus include one of `features`: the same rule as their left menu (components/Shell.tsx),
    their API keys and the MCP connector (api/mcp.py), so no way in shows more than the screens do."""
    if not any(access.allows(who, feature) for feature in features):
        raise HTTPException(403, "Not included in your subscription")


def send_payload(request: Request, item: Payload) -> Response:
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
    require_feature(who, "dashboards")
    if "*" not in who["products"] and code not in who["products"]:
        raise HTTPException(403, "Not included in your subscription")
    item = STORE.get((code, survey_id))
    if item is not None:
        await visible(who, survey_id)
    if item is None:
        raise HTTPException(404, "No published dashboard for that wave")
    return send_payload(request, item)


async def cached_payload(key: tuple, build, *args) -> Payload:
    """A finished response from this worker's cache, or built in a thread and kept until the serving data
    changes. Least recently used responses leave first once the cache reaches CACHE_BYTES."""
    global CACHED_BYTES, RESULTS, PUBLISHED_VERSION
    version = os.path.realpath(PUBLISHED)
    if version != PUBLISHED_VERSION:   # a publish swapped in new files: drop old answers now, not at the next poll, or
        RESULTS, CACHED_BYTES, PUBLISHED_VERSION = OrderedDict(), 0, version   # nginx files one under the new key
    item = RESULTS.get(key) if CACHE_RESULTS else None
    if item is not None:
        RESULTS.move_to_end(key)
        CACHE_COUNTS["hits"] += 1
        return item
    CACHE_COUNTS["misses"] += 1
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


def to_payload(data) -> Payload:
    """A finished response: compact JSON (shared/data/payloads.encode), its ETag and its gzip."""
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
    require_feature(who, "explorer")   # as the MCP connector's question_results
    await visible(who, survey_id)
    qcodes, dims = tuple(sorted(set(q.split(",")))[:20]), tuple(sorted(set(dim.split(",")))[:8])
    return send_payload(request, await cached_payload((SERVING, survey_id, qcodes, dims), lambda: to_payload(payloads.results(survey_id, qcodes, dims))))


@app.get("/api/v1/schedule")
async def schedule(request: Request, who: dict = Depends(user)) -> Response:
    """The data team's launch plan, week by week, against what Forsta fielded (etl/launch_schedule.py)."""
    require_feature(who, "schedule")
    if SCHEDULE is None:
        raise HTTPException(503, "The schedule is loading", headers={"Retry-After": "3"})
    return send_payload(request, SCHEDULE)


@app.get("/api/v1/waves")
async def waves(request: Request, who: dict = Depends(user)) -> Response:
    """Every wave this person may open, newest first, each with its provenance (payloads.describe)."""
    return send_payload(request, await cached_payload((SERVING, "waves", access.scope(who)),
                                        lambda: to_payload([w for w in all_waves() if access.sees(who, w)])))


@app.get("/api/v1/waves/{survey_id}/book")
async def book(survey_id: int, request: Request, who: dict = Depends(user)) -> Response:
    """The whole wave for the four dashboard screens in one cached response (≈ 30 KB gzipped)."""
    await visible(who, survey_id)
    def build() -> Payload:   # a book published before the provenance fields existed gets them here
        found = published_file("waves", str(survey_id), "book")
        data = json.loads(found.body) if found else payloads.book(survey_id)
        return to_payload({**data, "wave": payloads.describe(data["wave"])})
    return send_payload(request, await cached_payload((SERVING, "book", survey_id), build))


@app.get("/api/v1/waves/{survey_id}/report")
async def weekly_report(survey_id: int, request: Request, who: dict = Depends(user)) -> Response:
    """The weekly US Consumer Survey Insights report of a recent tracker wave, as the ETL published it
    (etl/weekly_report.py). nginx sends the file itself to most people (deploy/cip_locations.conf); this route serves a
    filtered session and a laptop without nginx. Nothing is computed here."""
    require_feature(who, "report")
    await visible(who, survey_id)
    found = published_file("waves", str(survey_id), "report")
    if found is None:
        raise HTTPException(404, "This wave has no weekly report (only the recent weekly tracker waves have one)")
    return send_payload(request, found)


@app.get("/api/v1/waves/{survey_id}/logic")
async def wave_logic(survey_id: int, request: Request, who: dict = Depends(user)) -> Response:
    """When each question of the wave was shown and its screen-out rules, from its survey.xml in Forsta (etl/fieldwork.py
    logic), for the Survey preview. Forsta waves whose questionnaire is kept only; nothing is computed here."""
    require_feature(who, "survey")   # the Survey preview's own rule
    await visible(who, survey_id)
    found = published_file("waves", str(survey_id), "logic")
    if found is None:
        raise HTTPException(404, "No questionnaire logic for this wave (kept for Forsta surveys only)")
    return send_payload(request, found)


async def tracker_view(request: Request, who: dict, name: str) -> Response:
    """A view across the weekly tracker's waves, as the ETL published it (api/v1/<name>.json.gz). nginx sends the file
    itself to most people (deploy/cip_locations.conf); this serves a filtered session and a laptop without nginx.
    Someone who may not open every tracker wave gets 403: the file mixes all of them. Nothing is computed here."""
    tracker = [w for w in await run_in_threadpool(all_waves) if w["study_type"] == "tracker"]
    if not all(access.sees(who, w) for w in tracker):
        raise HTTPException(403, "Not included in your subscription: this view covers every weekly tracker survey")
    found = published_file(name)
    if found is None:
        raise HTTPException(404, "Not published yet")
    return send_payload(request, found)


@app.get("/api/v1/public/facts")
async def public_facts(request: Request) -> Response:
    """The public home page's live figures (etl/publish.py site_facts): counts and dates only, so no sign-in. nginx
    sends the file itself; this serves a laptop without nginx."""
    found = published_file("public", "facts")
    if found is None:
        raise HTTPException(404, "Not published yet")
    return send_payload(request, found)


@app.get("/api/v1/retailers")
async def retailers(request: Request, who: dict = Depends(user)) -> Response:
    """Retailer comparison (etl/retailers.py): each retailer's reach, its shoppers' profile and sentiment, pooled weeks."""
    require_feature(who, "retailers")
    return await tracker_view(request, who, "retailers")


@app.get("/api/v1/sectors")
async def sectors(request: Request, who: dict = Depends(user)) -> Response:
    """The Databank's sector tables (etl/sectors.py): purchase rate, retailers, brands and categories per sector wave."""
    require_feature(who, "sectors")
    return await tracker_view(request, who, "sectors")


@app.get("/api/v1/reports")
async def report_waves(request: Request, who: dict = Depends(user)) -> Response:
    """The survey ids of the waves with a weekly report (etl/weekly_report.py), for the left menu's link."""
    return await tracker_view(request, who, "reports")


@app.get("/api/v1/expectations")
async def expectations(request: Request, who: dict = Depends(user)) -> Response:
    """Retail events, expected vs actual (etl/expectations.py): answers before and after, median spend, market size."""
    require_feature(who, "expectations")
    return await tracker_view(request, who, "expectations")


@app.get("/api/v1/search")
async def search(request: Request, q: str = Query(..., min_length=2, max_length=100), limit: int = Query(40, ge=1, le=200),
                 offset: int = Query(0, ge=0, le=5000), who: dict = Depends(user)) -> Response:
    """Questions by words, code, answer label or survey title, typo- and synonym-tolerant (api/search.py).
    The response says what it understood: {"results": [...], "understood": {corrected, expanded, matched_by}}."""
    require_feature(who, "search")
    def run() -> Payload:
        index = catalogue(who)
        found = index.search(q, limit, offset) if index else {"results": [], "total": 0, "understood": {}}
        if not found["results"]:
            log.info("search with no results: %r", q[:100])   # reviewed monthly to grow config/search_synonyms.yml
        return to_payload(found)
    return send_payload(request, await cached_payload((SERVING, "search", access.scope(who), " ".join(q.lower().split()), limit, offset), run))


def catalogue(who: dict) -> SearchIndex | None:
    """The search catalogue of the waves this person may see: the whole one for "*", else built once per scope."""
    scope = access.scope(who)
    if scope == access.EVERYTHING or not CATALOGUE_ROWS:
        return CATALOGUE
    if scope not in SCOPED:
        rows, labels, measure = CATALOGUE_ROWS
        SCOPED[scope] = _catalogue([r for r in rows if access.sees(who, r)], labels, measure)
    return SCOPED[scope]


@app.get("/api/v1/waves/{survey_id}/crosstab")
async def crosstab(survey_id: int, request: Request, q: str, by: str, weeks: int = Query(1, ge=1, le=4),
                   who: dict = Depends(user)) -> Response:
    """One question by two cuts, e.g. ?q=XM3&by=generation,gender&weeks=4 (this wave and the 3 before)."""
    require_feature(who, "crosstab")
    await visible(who, survey_id)
    cuts = tuple(by.split(","))
    if len(cuts) != 2 or len(set(cuts)) != 2 or not set(cuts) <= set(CUTS):
        raise HTTPException(422, f"by takes two different cuts from: {', '.join(CUTS)}")
    return send_payload(request, await cached_payload((SERVING, "crosstab", survey_id, q, cuts, weeks),
                                        crosstab_payload, survey_id, q, cuts, weeks))


def crosstab_payload(survey_id: int, qcode: str, cuts: tuple, weeks: int) -> Payload:
    """Use versioned published cut files; query live only when they are absent or incomplete."""
    waves = all_waves()   # parsed once per version, not on every cross-tab (half of each one's time)
    me = next((w for w in waves if w["survey_id"] == survey_id), None)
    pool = payloads.chain(
        {w["survey_id"]: w for w in waves if me and w["survey_family"] == me["survey_family"]},
        survey_id,
        weeks,
    )
    parts = {
        w["survey_id"]: json.loads(found.body)
        for w in pool
        if (found := published_file("waves", str(w["survey_id"]), "cuts", qcode))
    }
    if parts.get(survey_id, {}).get("counts"):
        return to_payload(payloads.crosstab_from(survey_id, qcode, cuts, pool, parts))
    # a published wave's cuts folder lists every question it has (etl/publish.py): one missing from it (an "other,
    # please specify" text) is not in the wave, so say so now instead of a 1–5 s database round trip to the same 404
    folder = PUBLISHED / "api" / "v1" / "waves" / str(survey_id) / "cuts"
    if survey_id not in parts and folder.is_dir():
        # q1 or XM3 typed in another case (an API key, the MCP connector): the files are named as the wave spells the
        # code, and a case-sensitive disk would say 404 where /results answers; no two codes of a wave differ by case
        spelt = next((p.name.removesuffix(".json.gz") for p in folder.iterdir()
                      if p.name.lower() == f"{qcode.lower()}.json.gz" and p.name != f"{qcode}.json.gz"), None)
        if spelt:
            return crosstab_payload(survey_id, spelt, cuts, weeks)
        raise LookupError("That question is not in that wave")
    return to_payload(payloads.crosstab(survey_id, qcode, cuts, weeks))


@app.get("/api/v1/questions/{family}/{study_type}/{qcode}")
async def question(family: str, study_type: str, qcode: str, request: Request, who: dict = Depends(user)) -> Response:
    """One question across every wave of its family and every cut, in compact columns: Compare and Trends pick waves
    and cuts from it on screen. The ETL publishes one per question (a static read); others are built once and cached.
    Someone who may not see every wave of the family gets the file without those waves."""
    require_feature(who, "trends", "compare", "audiences")   # the three screens that read a question across waves
    scope = access.scope(who)
    def build() -> Payload:
        found = published_file("questions", family, study_type, qcode)
        if found is None and not family.startswith(".") and (PUBLISHED / "api" / "v1" / "questions" / family / study_type).is_dir():
            # publish writes every question of a published family that has figures; one missing (an "other, please
            # specify" text) has none: the same empty file the database gave after 1-5 s, now without the round trip
            found = to_payload(payloads.question_from(qcode, [], [], {}))
        found = found or to_payload(payloads.question(family, study_type, qcode))
        if scope == access.EVERYTHING:
            return found
        shown = {w["survey_id"] for w in all_waves() if access.sees(who, w)}
        return to_payload(only_waves(json.loads(found.body), shown))
    return send_payload(request, await cached_payload((SERVING, "question", scope, family, study_type, qcode), build))


def only_waves(doc: dict, shown: set) -> dict:
    """A question file (payloads.question_from) cut to some of its waves: their cells, re-indexed."""
    keep = [i for i, w in enumerate(doc["waves"]) if w[0] in shown]
    if not keep:
        raise HTTPException(404, "No such question")
    at = {old: new for new, old in enumerate(keep)}
    cells = [k for k, w in enumerate(doc["w"]) if w in at]
    return {**doc, "waves": [doc["waves"][i] for i in keep], "w": [at[doc["w"][k]] for k in cells],
            **{name: [doc[name][k] for k in cells] for name in ("c", "a", "n", "b")}}


app.include_router(team.router, dependencies=[Depends(user)])   # saved views, alerts, audiences (api/team.py)
app.include_router(signin.router)                                 # /auth/* and the admin's session revocation
app.include_router(mcp.router)                                    # /mcp: the MCP connector, by API key (api/mcp.py)
app.include_router(logs.router)                                   # /api/v1/admin/logs: operational logs (api/logs.py)
app.include_router(metrics.router)                                # /api/v1/admin/metrics: the Logs page's dashboard (api/metrics.py)
app.include_router(ingest.router)                                 # /api/v1/admin/survey: upload & ingest (api/ingest.py)

def book_data(survey_id: int) -> Optional[dict]:
    return _parsed_book(survey_id, PUBLISHED_VERSION)


@lru_cache(maxsize=128)   # parsed once per published version: Ask CIP reads up to 12 books per question
def _parsed_book(survey_id: int, version: str) -> Optional[dict]:
    found = published_file("waves", str(survey_id), "book")
    try:
        return json.loads(found.body) if found else payloads.book(survey_id)
    except LookupError:
        return None


def warm_ask() -> None:
    """Build Ask CIP's question index at start, in the background (api/assistant.py index_for)."""
    try:
        assistant.index_for(PUBLISHED / "api" / "v1" / "questions", os.path.realpath(PUBLISHED), all_waves())
    except Exception as exc:   # noqa: BLE001 — the first question builds it instead
        log.warning("Ask CIP index not built at start: %s", type(exc).__name__)


async def ask_index(who: dict):
    """Ask CIP's question index (built at start; again after a publish) and the surveys this person may see."""
    waves = await run_in_threadpool(all_waves)
    index = await run_in_threadpool(assistant.index_for, PUBLISHED / "api" / "v1" / "questions", os.path.realpath(PUBLISHED), waves)
    return index, {w["survey_id"] for w in waves if access.sees(who, w)}


async def ask_answer(who: dict, question: str) -> dict:
    """Ask CIP for the page (POST /api/v1/ask) and the MCP connector's ask tool alike: Ask on the person's menu, their
    per-minute limit (config/access.yml limits.ask), and at most ASK_SLOTS questions computed at once per worker, so a
    burst queues briefly, then "busy", never slows the site."""
    require_feature(who, "ask")
    if not access.spend(who["email"], "ask"):
        raise HTTPException(429, "Too many questions: wait a minute", headers={"Retry-After": "60"})
    try:
        await asyncio.wait_for(ASK_SLOTS.acquire(), ASK_WAIT)
    except asyncio.TimeoutError:
        raise HTTPException(503, "Ask Coresight is busy: try again in a few seconds", headers={"Retry-After": "5"})
    try:
        index, shown = await ask_index(who)
        return await run_in_threadpool(assistant.ask, question, index, shown, access.scope(who))
    finally:
        ASK_SLOTS.release()


@app.post("/api/v1/ask")
async def ask(request: Request, who: dict = Depends(user)) -> dict:
    """A question in plain words, answered from the published survey figures with a chart (api/assistant.py), no model
    and no database. Only from the waves this person may see."""
    question = str((await team.json_body(request)).get("question") or "")
    answer = await ask_answer(who, question)
    audit.record(request, "ask", target=question[:300], detail={"mode": answer["mode"], "sources": [s["link"] for s in answer["sources"]]})
    return answer


EXPORT_TYPES = {"xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation"}


@app.post("/api/v1/export/{kind}")
async def export(kind: str, request: Request, who: dict = Depends(user)) -> Response:
    """The table a screen offers as CSV, as an Excel workbook or a PowerPoint slide (api/exports.py)."""
    if kind not in EXPORT_TYPES:
        raise HTTPException(404, "Exports are xlsx or pptx")
    require_feature(who, "export")
    if not access.spend(who["email"], "export"):
        raise HTTPException(429, "Too many exports: wait a minute", headers={"Retry-After": "60"})
    try:
        spec = exports.check(await team.json_body(request))
    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(422, str(exc))
    body = await run_in_threadpool(exports.build_xlsx if kind == "xlsx" else exports.build_pptx, spec)
    audit.record(request, "export", target=spec["name"], detail={"kind": kind, "rows": len(spec["rows"])})
    return Response(body, media_type=EXPORT_TYPES[kind], headers={"Content-Disposition": f'attachment; filename="{spec["name"]}.{kind}"'})


@app.get("/healthz")
@app.head("/healthz", include_in_schema=False)   # uptime checks send HEAD; a GET-only route sent it to the site's 404 page
async def healthz() -> dict:
    """Public: up or not, and which code. The detail is for admins (/api/v1/admin/health)."""
    return {"ok": True, "build": BUILD}


@app.get("/api/v1/admin/fieldwork")
async def fieldwork_record(request: Request, who: dict = Depends(admin)) -> Response:
    """Forsta's fieldwork record of every survey (etl/fieldwork.py): funnel, drop-outs by page, warnings and Forsta's
    archive and deletion schedule, as the ETL published it. Admins only; nothing is computed here."""
    found = published_file("admin", "fieldwork")
    if found is None:
        raise HTTPException(404, "No fieldwork record yet: the next Forsta run collects it")
    return send_payload(request, found)


@app.get("/api/v1/admin/forsta")
async def forsta_overview(request: Request, who: dict = Depends(admin)) -> Response:
    """The Forsta admin screens' company records and one line per survey (etl/fieldwork.py publish_forsta)."""
    found = published_file("admin", "forsta")
    if found is None:
        raise HTTPException(404, "No Forsta record yet: the next Forsta run collects it")
    return send_payload(request, found)


@app.get("/api/v1/admin/forsta/{key}")
async def forsta_survey(key: str, request: Request, who: dict = Depends(admin)) -> Response:
    """One survey on the Forsta admin screens: banners, saved reports' tables, funnel by split, warnings, files."""
    found = published_file("admin", "forsta", key)
    if found is None:
        raise HTTPException(404, "No Forsta record for this survey yet")
    return send_payload(request, found)


FORSTA_FILES = {"excel": ("saved_export", "xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
                "pdf": ("saved_pdf", "pdf", "application/pdf"),
                "pptx": ("saved_pptx", "pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation")}


@app.get("/api/v1/admin/forsta/{key}/export/{report}")
async def forsta_export(key: str, report: str, format: str = "excel", who: dict = Depends(admin)) -> Response:
    """A saved report as the file Forsta exported (Excel, PDF or PowerPoint: read-only POSTs, kept by the ETL in
    cip_forsta_record). Read from the database: an admin's rare download, not worth a file in every published version."""
    if not report.isalnum() or format not in FORSTA_FILES:
        raise HTTPException(404)
    kind, extension, media = FORSTA_FILES[format]
    def read() -> bytes | None:
        with get_engine("app").connect() as conn:
            return conn.execute(text("SELECT payload FROM cip_forsta_record WHERE forsta_path = :p AND kind = :k"),
                                {"p": key.replace(".", "/"), "k": f"{kind}:{report}"}).scalar()
    payload = await run_in_threadpool(read)
    if payload is None:
        raise HTTPException(404, f"Forsta has not exported this report as {format.upper()}")
    return Response(gzip.decompress(payload), media_type=media,
                    headers={"Content-Disposition": f'attachment; filename="{key}-{report}.{extension}"', "Cache-Control": "private, no-store"})


@app.get("/api/v1/fieldwork")
async def fieldwork_shared(request: Request, who: dict = Depends(user)) -> Response:
    """The Fieldwork screens for a role the super admin turned the "fieldwork" feature on for (the Access page): the
    same surveys without the deletion schedule or Forsta user emails (etl/fieldwork.py publish). Nothing computed here."""
    require_feature(who, "fieldwork")
    found = published_file("fieldwork")
    if found is None:
        raise HTTPException(404, "No fieldwork record yet: the next Forsta run collects it")
    return send_payload(request, found)


ROLE_SAVE_FAILED = "The menus were not saved: the database did not accept it. Nothing changed; try again in a minute."


@app.get("/api/v1/keys")
async def my_keys(who: dict = Depends(user)) -> dict:
    """The signed-in person's API keys (the Account page): name, first characters and date, never the key."""
    require_feature(who, "api")
    return {"keys": await run_in_threadpool(api_keys.mine, who["email"])}


@app.post("/api/v1/keys")
async def make_key(request: Request, who: dict = Depends(user)) -> dict:
    """Make an API key for the signed-in person (the Account page). It acts as them, with their access as it is at each
    request, for the API and the MCP connector. Shown once, here; only its SHA-256 is kept. A key cannot make keys."""
    require_feature(who, "api")
    if who["sid"] == "api-key":
        raise HTTPException(403, "Sign in to the portal to make API keys")
    name = " ".join(str((await team.json_body(request)).get("name") or "").split())[:60]
    if not name:
        raise HTTPException(422, "Give the key a name, such as the tool it is for")
    if len(await run_in_threadpool(api_keys.mine, who["email"])) >= api_keys.MOST:
        raise HTTPException(409, f"You have {api_keys.MOST} keys: revoke one first")
    token = await run_in_threadpool(api_keys.new, who["email"], name)
    audit.record(request, "api_key_made", who=who, detail={"name": name, "shown": token[:8]})
    return {"key": token, "name": name}


@app.delete("/api/v1/keys/{shown}")
async def revoke_key(shown: str, request: Request, who: dict = Depends(user)) -> dict:
    """Revoke one of the signed-in person's own keys: it stops working at once."""
    require_feature(who, "api")
    if who["sid"] == "api-key":
        raise HTTPException(403, "Sign in to the portal to revoke API keys")
    if not await run_in_threadpool(api_keys.revoke, who["email"], shown):
        raise HTTPException(404, "No such key of yours")
    audit.record(request, "api_key_revoked", who=who, detail={"shown": shown})
    return {"revoked": shown}


def super_admin(who: dict = Depends(admin)) -> dict:
    """The Access page's routes: an admin who may also manage roles (config/access.yml manage_roles)."""
    if not access.can(who, "manage_roles"):
        raise HTTPException(403, "Only the super admin manages roles")
    return who


@app.get("/api/v1/admin/roles")
async def roles(person: str = "", who: dict = Depends(super_admin)) -> dict:
    """The Access screen: every switchable feature (its name), and the menus of each role, each client in
    config/access.yml, and each person given menus of their own (the super admin's choice in cip_role_access, else
    what they inherit: shared/core/access.py inherited), plus `person` (an email typed on the screen) with what they
    inherit now. The super admin is not listed: they always have everything."""
    rules = access.rules()
    labels = rules.get("feature_labels") or {}
    chosen = await run_in_threadpool(access.managed_features)
    targets = [(role, "role", role) for role, said in (rules.get("roles") or {}).items() if said.get("permissions") != access.EVERYTHING]
    targets += [(f"client:{cid}", "client", c.get("name") or cid) for cid, c in (rules.get("clients") or {}).items()]
    people = {key for key in chosen if key.startswith("person:")} | ({f"person:{person.strip().lower()}"} if person else set())
    targets += [(key, "person", key.removeprefix("person:")) for key in sorted(people)]
    return {"features": [{"key": f, "label": labels.get(f, f)} for f in rules["features"]],
            "roles": [{"role": key, "kind": kind, "label": label, "features": got, "chosen": key in chosen} for key, kind, label in targets
                      if (got := chosen[key] if key in chosen else access.inherited(key)) is not None]}


@app.put("/api/v1/admin/roles/{role}")
async def save_role(role: str, request: Request, who: dict = Depends(super_admin)) -> dict:
    """Save the menus of a role ("analyst"), a client ("client:acme") or one person ("person:ana@acme.com") from the
    Access screen (cip_role_access, created on the first save). A person's choice beats their client's, which beats
    their role's (access.menus). Applies at once to the portal, the API and the MCP connector (signin.stale_before).
    Recorded in the access log."""
    role = role.strip().lower()
    if access.inherited(role) is None:
        raise HTTPException(404, "No such role, client or person to manage")
    body = await team.json_body(request)
    known = access.rules()["features"]
    features = [f for f in known if f in (body.get("features") or [])]   # only real features, in the catalogue's order

    def store() -> None:
        engine = get_engine("api_write")
        if "cip_role_access" not in inspect(engine).get_table_names():
            apply_sql(Path(__file__).resolve().parents[1] / "sql" / "010_role_access.sql", engine)
        with engine.begin() as conn:
            conn.execute(text("REPLACE INTO cip_role_access (role, features, updated_by, updated_at) VALUES (:r, :f, :b, :t)"),
                         {"r": role, "f": json.dumps(features), "b": who["email"], "t": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())})
    try:
        await run_in_threadpool(store)
    except Exception as exc:   # noqa: BLE001
        log.warning("Role %s not saved: %s", role, exc)
        raise HTTPException(503, ROLE_SAVE_FAILED)
    return applied(request, who, role, features)


def applied(request: Request, who: dict, role: str, features: list[str] | None) -> dict:
    """After the Access screen saved or dropped menus: this worker re-reads them at once, nginx stops trusting older
    "sees everything" cookies now (signin.stale_before), and the change is recorded in the access log."""
    access.menus_changed()
    signin.share_revoked()
    audit.record(request, "role_change", who=who, target=role, detail={"features": features})
    return {"role": role, "features": features if features is not None else access.inherited(role)}


@app.delete("/api/v1/admin/roles/{role}")
async def forget_role(role: str, request: Request, who: dict = Depends(super_admin)) -> dict:
    """Drop a client's or a person's own menus (the Access screen's "Use the inherited menus"): they get their
    role's, or their client's, again at once."""
    role = role.strip().lower()
    def drop() -> None:   # kept as "null" with its time, not deleted: every worker then sees access changed (stale_before)
        with get_engine("api_write").begin() as conn:
            conn.execute(text("UPDATE cip_role_access SET features = 'null', updated_by = :b, updated_at = :t WHERE role = :r"),
                         {"r": role, "b": who["email"], "t": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())})
    try:
        await run_in_threadpool(drop)
    except Exception as exc:   # noqa: BLE001
        log.warning("Role %s not dropped: %s", role, exc)
        raise HTTPException(503, ROLE_SAVE_FAILED)
    return applied(request, who, role, None)


@app.get("/api/v1/admin/health")
async def health(who: dict = Depends(admin)) -> dict:
    pool_info = {}
    try:
        p = get_engine("app").pool
        pool_info = {"size": p.size(), "checkedin": p.checkedin(), "checkedout": p.checkedout(), "overflow": p.overflow(),
                     "status": p.status()}
    except Exception:   # noqa: BLE001 — SQLite has no pool sizes
        pass
    return {"build": BUILD, "dashboards": len(STORE), "published": str(STAMP[1]) if STAMP else None,
            "serving_waves": SERVING[0] if SERVING else 0, "serving_built": str(SERVING[1]) if SERVING else None,
            "cached_results": len(RESULTS), "cached_mb": round(CACHED_BYTES / 2**20, 1), "catalogue": len(CATALOGUE.docs) if CATALOGUE else 0,
            "pool": pool_info, "audit_queue": audit.PENDING.qsize(), "revoked_sessions": len(signin.REVOKED)}


@app.get("/api/v1/me")
async def me(who: dict = Depends(user)) -> dict:
    """{email, name, role, tier, client, features[], permissions[]}: role is super_admin, analyst or client; client is
    the organisation's id in config/access.yml (null for Coresight staff); features are what the tier includes;
    permissions what the role may do (shared/core/access.py can()), so the screens show the admin pages only to it."""
    return {"email": who["email"], "name": who["email"].split("@")[0].replace(".", " ").title(), "role": who["role"],
            "tier": who["tier"], "client": who["client"], "features": who["features"],
            "permissions": sorted(access.permissions_of(who["role"]))}


@lru_cache(maxsize=1)
def _methodology() -> Payload:
    import yaml
    return to_payload(yaml.safe_load(METHODOLOGY.read_text(encoding="utf-8")))


@app.get("/api/v1/methodology")
async def methodology(request: Request, who: dict = Depends(user)) -> Response:
    """config/methodology.yml as JSON: {population: {default, study_types, families, ids}, panel, qualification,
    fielding, weighting ("none"), weighting_text, data_quality: [text], small_cells, significance} (all text)."""
    return send_payload(request, _methodology())


@app.get("/api/v1/admin/audit")
def audit_log(email: str = "", action: str = "", limit: int = Query(200, ge=1, le=2000), before: int = Query(0, ge=0),
              who: dict = Depends(admin)) -> dict:
    """The access log, newest first: {rows: [{log_id, ts, email, client, role, action, survey_id, target, detail,
    user_agent}], next: the `before` for the next page, or null}. Filter by email and action. Admins only."""
    where = " AND ".join(c for c, on in (("email = :e", email), ("action = :a", action), ("log_id < :b", before)) if on) or "1 = 1"
    with get_engine("app").connect() as conn:
        rows = [dict(r) for r in conn.execute(text(
            "SELECT log_id, ts, email, client, role, action, survey_id, target, detail, user_agent FROM cip_access_log"
            f" WHERE {where} ORDER BY log_id DESC LIMIT :n"), {"e": email.lower(), "a": action, "b": before, "n": limit}).mappings()]
    for r in rows:
        r["detail"] = json.loads(r["detail"]) if r["detail"] else None
    return {"rows": rows, "next": rows[-1]["log_id"] if len(rows) == limit else None}


@lru_cache(maxsize=4)
def _script_hashes(stamp: int) -> str:
    """CSP hashes of every page's inline scripts (the theme-before-paint one; Next.js's own), for this build of WEB."""
    pages = "".join(page.read_text(encoding="utf-8") for page in WEB.rglob("*.html"))
    return " ".join(sorted({"'sha256-" + base64.b64encode(hashlib.sha256(body.encode()).digest()).decode() + "'"
                            for body in re.findall(r'<script(?: id="\w+")?>(.*?)</script>', pages, re.S)}))


@lru_cache(maxsize=4)
def _policy(stamp: int) -> str:
    return ("default-src 'self'; script-src 'self' " + _script_hashes(stamp) + "; style-src 'self' 'unsafe-inline';"
            " img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; object-src 'none';"
            " frame-ancestors 'none'; base-uri 'self'; form-action 'self'")


POLICY_CHECKED = [0.0, ""]   # when the build was last looked at, and its policy


def policy() -> str:
    """The CSP for the current build of WEB; the build is looked at once a second, not on every request."""
    now = time.monotonic()
    if now - POLICY_CHECKED[0] > 1:
        try:
            stamp = (WEB / "index.html").stat().st_mtime_ns
        except OSError:
            stamp = 0
        POLICY_CHECKED[:] = [now, _policy(stamp)]
    return POLICY_CHECKED[1]


MAX_BODY = int(access.rules().get("max_body_kb", 1024)) * 1024


@app.middleware("http")
async def every_request(request: Request, call_next):
    """One middleware, not four (each BaseHTTPMiddleware layer costs ~10 % of a small request): refuse oversized
    bodies, time and log API calls, add the headers nginx adds (deploy/cip_headers.conf) for when the API is the
    front door (the tunnel), and set browser caching."""
    if request.method in ("POST", "PUT", "PATCH"):   # a body over max_body_kb (config/access.yml) is refused unread
        size = request.headers.get("content-length")
        if size is None and request.headers.get("transfer-encoding"):
            return failed(411, "Send the body with a Content-Length")
        limit = ingest.MAX_BYTES * 2 if request.url.path.startswith(ingest.router.prefix) else MAX_BODY   # two files
        if size is not None and (not size.isdigit() or int(size) > limit):
            return failed(413, f"The request body is larger than {limit // 1024} KB")
    start = time.perf_counter()
    response = await call_next(request)
    if fresh := getattr(request.state, "cookie", None):   # signin.user(): access changed since sign-in, same session
        response.set_cookie(signin.COOKIE, fresh, httponly=True, samesite="lax", secure=signin.https(request),
                            max_age=signin.SESSION_HOURS * 3600)
    duration_ms = (time.perf_counter() - start) * 1000.0
    headers = response.headers
    headers["Server-Timing"] = f"total;dur={duration_ms:.2f}"
    path = request.url.path
    if path.startswith("/api/") and duration_ms > 200:   # every request's time is in nginx's log (the dashboard reads it):
        # a line per fast request too cost 2.5 % of the API's CPU and an unbuffered write each to /home (5 Nov 2026)
        log.warning("[PERF-SLOW] %s %s took %.1f ms (status %d)", request.method, path, duration_ms, response.status_code)
    # a 304 ("you already have it") carries no content type, yet the browser applies its policy to the page it kept:
    # a page's 304 must get the page policy, or a reload is blocked (seen with the local server; nginx serves pages on Azure)
    html = headers.get("content-type", "").startswith("text/html") or (
        response.status_code == 304 and not path.startswith(("/api/", "/auth/", "/_next/")))
    # only a page runs scripts: everything else gets the short API policy, not the pages' ~4 KB list of script hashes
    headers.setdefault("Content-Security-Policy", policy() if html else "default-src 'none'; frame-ancestors 'none'")
    headers["X-Frame-Options"] = "DENY"
    headers["X-Content-Type-Options"] = "nosniff"
    headers["Referrer-Policy"] = "same-origin"
    if signin.https(request):
        headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    if path.startswith(("/assets/", "/_next/static/")) and response.status_code in (200, 206, 304):   # content-hashed files never change
        headers["Cache-Control"] = "public, max-age=31536000, immutable"
    elif html:   # index.html names this release's assets: always revalidate it
        headers["Cache-Control"] = "no-cache"
    return response


class SinglePageApp(StaticFiles):
    """WEB as files. A deep link into the app (/app/w/412/crosstab; /w/412/crosstab in the Vite build) gets the app's
    page and its router picks the screen; anything else unknown gets the 404 page when the build has one.
    A file the build also gzipped (frontend/package.json postbuild) goes out gzipped, as nginx's gzip_static does on
    Azure: a wave's first visit was 1,539 KB without it, 3x the bytes (8 Nov 2026), on this server's own links."""
    async def get_response(self, path: str, scope):
        """The file or page for a path (file_or_page), swapped for its gzipped copy when the browser accepts gzip."""
        response = await self.file_or_page(path, scope)
        packed = Path(f"{getattr(response, 'path', '')}.gz")
        request_headers = Headers(scope=scope)
        if response.status_code != 200 or not packed.is_file():
            return response
        if "gzip" not in request_headers.get("accept-encoding", ""):
            response.headers["Vary"] = "Accept-Encoding"   # a shared cache keeps the plain and gzipped copies apart
            return response
        response = FileResponse(packed, media_type=response.media_type, stat_result=os.stat(packed),
                                headers={"Content-Encoding": "gzip", "Vary": "Accept-Encoding"})
        return NotModifiedResponse(response.headers) if self.is_not_modified(response.headers, request_headers) else response

    async def file_or_page(self, path: str, scope):
        """The file at a path; else the app's page for an /app/ deep link, the site's page, or its 404 page."""
        try:
            response = await super().get_response(path, scope)   # a build with 404.html gets it here, as a 404
        except StarletteHTTPException as exc:   # StaticFiles raises Starlette's 404, not FastAPI's
            if exc.status_code != 404 or path.startswith(("api/", "auth/", "assets/")):
                raise
            return await super().get_response("index.html", scope)
        if response.status_code == 404 and path.startswith("app/") and not Path(path).suffix and (WEB / "app").is_dir():   # a missing script stays a 404
            return await super().get_response("app/index.html", scope)
        return response


if WEB.exists():
    app.mount("/", SinglePageApp(directory=WEB, html=True), name="web")
