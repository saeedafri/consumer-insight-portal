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
(app/core/access.py), and answers errors as {"detail": text, "status": code}.

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
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional
from pathlib import Path

from collections import OrderedDict, defaultdict

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core import access, audit
from app.core.database import get_engine
from app.core.session import issue   # noqa: F401 — tests and tools sign sessions through the API module
from app.data import payloads
from api import assistant, exports, mcp, signin, team
from api.search import SearchIndex
from api.signin import COOKIE, admin, user
from etl import launch_schedule
from etl.publish import ROOT as PUBLISH_ROOT
from etl.serving import CUTS

log = logging.getLogger("cip.api")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s | %(message)s")   # [PERF] lines show
WEB = Path(__file__).resolve().parents[1] / "web" / "dist"
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
BUILD_SLOTS = asyncio.Semaphore(int(os.environ.get("CIP_BUILD_SLOTS", "8")))   # concurrent database builds per worker
BUILD_WAIT = float(os.environ.get("CIP_BUILD_WAIT", "3"))   # seconds a request may queue for a slot before "busy, retry"
CATALOGUE: SearchIndex | None = None     # every reportable question of every built wave (api/search.py)
CATALOGUE_ROWS: tuple = ()               # what CATALOGUE was built from, to build a filtered one per scope
SCOPED: dict[str, SearchIndex] = {}      # scope (app/core/access.scope) → the catalogue of the waves it may see
WAVES: tuple = ((), [])                  # (data version, every built wave described): the visibility rule's input
CACHE_RESULTS = os.environ.get("CIP_RESULT_CACHE", "1") != "0"   # 0 only to measure the database path
PUBLISHED = PUBLISH_ROOT / "current"     # the ETL's prebuilt responses (etl/publish.py): no database work on a view
PUBLISHED_VERSION = ""


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


def _published(*parts: str) -> Payload | None:
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
    SCHEDULE = _json(launch_schedule.weeks())


async def _refresh_forever() -> None:
    while True:
        await asyncio.sleep(REFRESH_SECONDS)
        try:
            if await run_in_threadpool(_changed):
                await run_in_threadpool(_load)
            await run_in_threadpool(_load_schedule)
            await run_in_threadpool(signin.load_revoked)
        except Exception:   # keep serving the last good payloads; the next poll retries
            log.exception("Dashboard refresh failed; still serving the previous payloads")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not SECRET:
        raise RuntimeError("CIP_SESSION_SECRET is not set")
    await run_in_threadpool(_load)
    await run_in_threadpool(_changed)
    await run_in_threadpool(_load_schedule)
    audit.start()
    task = asyncio.get_running_loop().create_task(_refresh_forever())
    try:
        yield
    finally:
        task.cancel()


# OpenAPI: the typed contract a future chatbot's tools are generated from (docs/Ui-Design-Claude/20); signed-in only
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
    if WAVES[0] != version:
        listed = _published("waves")
        WAVES = (version, [payloads.describe(w) for w in (json.loads(listed.body) if listed else payloads.waves(_boards()))])
    return WAVES[1]


async def visible(who: dict, survey_id: int) -> dict:
    """The wave, if this person may open it; else 404, so a hidden study is indistinguishable from a missing one."""
    wave = next((w for w in await run_in_threadpool(all_waves) if w["survey_id"] == survey_id), None)
    if wave is None or not access.sees(who, wave):
        raise HTTPException(404, "No such wave")
    return wave


def need(who: dict, feature: str) -> None:
    if not access.allows(who, feature):
        raise HTTPException(403, "Not included in your subscription")


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
    need(who, "dashboards")
    if "*" not in who["products"] and code not in who["products"]:
        raise HTTPException(403, "Not included in your subscription")
    item = STORE.get((code, survey_id))
    if item is not None:
        await visible(who, survey_id)
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
    await visible(who, survey_id)
    qcodes, dims = tuple(sorted(set(q.split(",")))[:20]), tuple(sorted(set(dim.split(",")))[:8])
    return _send(request, await _cached((SERVING, survey_id, qcodes, dims), lambda: _json(payloads.results(survey_id, qcodes, dims))))


@app.get("/api/v1/schedule")
async def schedule(request: Request, who: dict = Depends(user)) -> Response:
    """The data team's launch plan, week by week, against what Forsta fielded (etl/launch_schedule.py)."""
    if SCHEDULE is None:
        raise HTTPException(503, "The schedule is loading", headers={"Retry-After": "3"})
    return _send(request, SCHEDULE)


@app.get("/api/v1/waves")
async def waves(request: Request, who: dict = Depends(user)) -> Response:
    """Every wave this person may open, newest first, each with its provenance (payloads.describe)."""
    return _send(request, await _cached((SERVING, "waves", access.scope(who)),
                                        lambda: _json([w for w in all_waves() if access.sees(who, w)])))


@app.get("/api/v1/waves/{survey_id}/book")
async def book(survey_id: int, request: Request, who: dict = Depends(user)) -> Response:
    """The whole wave for the four dashboard screens in one cached response (≈ 30 KB gzipped)."""
    await visible(who, survey_id)
    def build() -> Payload:   # a book published before the provenance fields existed gets them here
        found = _published("waves", str(survey_id), "book")
        data = json.loads(found.body) if found else payloads.book(survey_id)
        return _json({**data, "wave": payloads.describe(data["wave"])})
    return _send(request, await _cached((SERVING, "book", survey_id), build))


@app.get("/api/v1/search")
async def search(request: Request, q: str = Query(..., min_length=2, max_length=100), limit: int = Query(40, ge=1, le=200),
                 offset: int = Query(0, ge=0, le=5000), who: dict = Depends(user)) -> Response:
    """Questions by words, code, answer label or survey title, typo- and synonym-tolerant (api/search.py).
    The response says what it understood: {"results": [...], "understood": {corrected, expanded, matched_by}}."""
    need(who, "search")
    def run() -> Payload:
        index = catalogue(who)
        found = index.search(q, limit, offset) if index else {"results": [], "total": 0, "understood": {}}
        if not found["results"]:
            log.info("search with no results: %r", q[:100])   # reviewed monthly to grow config/search_synonyms.yml
        return _json(found)
    return _send(request, await _cached((SERVING, "search", access.scope(who), " ".join(q.lower().split()), limit, offset), run))


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
    need(who, "crosstab")
    await visible(who, survey_id)
    cuts = tuple(by.split(","))
    if len(cuts) != 2 or len(set(cuts)) != 2 or not set(cuts) <= set(CUTS):
        raise HTTPException(422, f"by takes two different cuts from: {', '.join(CUTS)}")
    def build() -> Payload:   # from the published cut tables when the wave has them, else from the database
        listed = _published("waves")
        waves = json.loads(listed.body) if listed else []
        me = next((w for w in waves if w["survey_id"] == survey_id), None)
        pool = payloads.chain({w["survey_id"]: w for w in waves if me and w["survey_family"] == me["survey_family"]}, survey_id, weeks)
        parts = {w["survey_id"]: json.loads(found.body) for w in pool if (found := _published("waves", str(w["survey_id"]), "cuts", q))}
        if parts.get(survey_id, {}).get("counts"):   # a published file without counts is never trusted: read live
            return _json(payloads.crosstab_from(survey_id, q, cuts, pool, parts))
        return _json(payloads.crosstab(survey_id, q, cuts, weeks))
    return _send(request, await _cached((SERVING, "crosstab", survey_id, q, cuts, weeks), build))


@app.get("/api/v1/questions/{family}/{study_type}/{qcode}")
async def question(family: str, study_type: str, qcode: str, request: Request, who: dict = Depends(user)) -> Response:
    """One question across every wave of its family and every cut, in compact columns: Compare and Trends pick waves
    and cuts from it on screen. The ETL publishes one per question (a static read); others are built once and cached.
    Someone who may not see every wave of the family gets the file without those waves."""
    need(who, "trends")
    scope = access.scope(who)
    def build() -> Payload:
        found = _published("questions", family, study_type, qcode) or _json(payloads.question(family, study_type, qcode))
        if scope == access.EVERYTHING:
            return found
        shown = {w["survey_id"] for w in all_waves() if access.sees(who, w)}
        return _json(only_waves(json.loads(found.body), shown))
    return _send(request, await _cached((SERVING, "question", scope, family, study_type, qcode), build))


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

def _book_data(survey_id: int) -> Optional[dict]:
    return _parsed_book(survey_id, PUBLISHED_VERSION)


@lru_cache(maxsize=128)   # parsed once per published version: Ask CIP reads up to 12 books per question
def _parsed_book(survey_id: int, version: str) -> Optional[dict]:
    found = _published("waves", str(survey_id), "book")
    try:
        return json.loads(found.body) if found else payloads.book(survey_id)
    except LookupError:
        return None


@app.post("/api/v1/ask")
async def ask(request: Request, who: dict = Depends(user)) -> dict:
    """A question in plain words, answered only from published figures with every source cited (api/assistant.py).
    Only from the waves this person may see; at most limits.ask questions a minute (config/access.yml)."""
    need(who, "ask")
    if not access.spend(who["email"], "ask"):
        raise HTTPException(429, "Too many questions: wait a minute", headers={"Retry-After": "60"})
    body = await team.json_body(request)
    index = catalogue(who)
    search = index.search if index else (lambda q, n: {"results": []})
    shown = {w["survey_id"] for w in await run_in_threadpool(all_waves) if access.sees(who, w)}
    answer = await run_in_threadpool(assistant.ask, str(body.get("question") or ""), search,
                                     lambda sid: _book_data(sid) if sid in shown else None)
    audit.record(request, "ask", target=str(body.get("question") or "")[:300],
                 detail={"mode": answer["mode"], "sources": [s["link"] for s in answer["sources"]]})
    return answer


EXPORT_TYPES = {"xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation"}


@app.post("/api/v1/export/{kind}")
async def export(kind: str, request: Request, who: dict = Depends(user)) -> Response:
    """The table a screen offers as CSV, as an Excel workbook or a PowerPoint slide (api/exports.py)."""
    if kind not in EXPORT_TYPES:
        raise HTTPException(404, "Exports are xlsx or pptx")
    need(who, "export")
    if not access.spend(who["email"], "export"):
        raise HTTPException(429, "Too many exports: wait a minute", headers={"Retry-After": "60"})
    try:
        spec = exports.check(await team.json_body(request))
    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(422, str(exc))
    body = await run_in_threadpool(exports.xlsx if kind == "xlsx" else exports.pptx, spec)
    audit.record(request, "export", target=spec["name"], detail={"kind": kind, "rows": len(spec["rows"])})
    return Response(body, media_type=EXPORT_TYPES[kind], headers={"Content-Disposition": f'attachment; filename="{spec["name"]}.{kind}"'})


@app.get("/healthz")
async def healthz() -> dict:
    """Public: up or not, and which code. The detail is for admins (/api/v1/admin/health)."""
    return {"ok": True, "build": BUILD}


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
    """{email, name, role, tier, client, features[]}: role is admin, analyst or client; client is the organisation's id
    in config/access.yml (null for Coresight staff); features are what the tier includes (config/access.yml)."""
    return {"email": who["email"], "name": who["email"].split("@")[0].replace(".", " ").title(), "role": who["role"],
            "tier": who["tier"], "client": who["client"], "features": who["features"]}


@lru_cache(maxsize=1)
def _methodology() -> Payload:
    import yaml
    return _json(yaml.safe_load(METHODOLOGY.read_text(encoding="utf-8")))


@app.get("/api/v1/methodology")
async def methodology(request: Request, who: dict = Depends(user)) -> Response:
    """config/methodology.yml as JSON: {population: {default, study_types, families, ids}, panel, qualification,
    fielding, weighting ("none"), weighting_text, data_quality: [text], small_cells, significance} (all text)."""
    return _send(request, _methodology())


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


@app.middleware("http")
async def performance_logging_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000.0
    response.headers["Server-Timing"] = f"total;dur={duration_ms:.2f}"
    path = request.url.path
    if path.startswith("/api/"):
        status = response.status_code
        if duration_ms > 200:
            log.warning("[PERF-SLOW] %s %s took %.1f ms (status %d)", request.method, path, duration_ms, status)
        else:
            log.info("[PERF] %s %s took %.1f ms (status %d)", request.method, path, duration_ms, status)
    return response


@lru_cache(maxsize=4)
def _script_hashes(stamp: int) -> str:
    """CSP hashes of index.html's inline scripts (the theme-before-paint one), for this build of web/dist."""
    try:
        page = (WEB / "index.html").read_text(encoding="utf-8")
    except OSError:
        return ""
    return " ".join("'sha256-" + base64.b64encode(hashlib.sha256(body.encode()).digest()).decode() + "'"
                    for body in re.findall(r"<script>(.*?)</script>", page, re.S))


def policy() -> str:
    try:
        stamp = (WEB / "index.html").stat().st_mtime_ns
    except OSError:
        stamp = 0
    return ("default-src 'self'; script-src 'self' " + _script_hashes(stamp) + "; style-src 'self' 'unsafe-inline';"
            " img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; object-src 'none';"
            " frame-ancestors 'none'; base-uri 'self'; form-action 'self'")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """The same headers nginx adds (deploy/cip_headers.conf), for when the API is the front door (the tunnel)."""
    response = await call_next(request)
    response.headers.setdefault("Content-Security-Policy", policy())
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    if signin.https(request):
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


MAX_BODY = int(access.rules().get("max_body_kb", 1024)) * 1024


@app.middleware("http")
async def body_limit(request: Request, call_next):
    """A request body over max_body_kb (config/access.yml) is refused before anything reads it."""
    if request.method in ("POST", "PUT", "PATCH"):
        size = request.headers.get("content-length")
        if size is None and request.headers.get("transfer-encoding"):
            return failed(411, "Send the body with a Content-Length")
        if size is not None and (not size.isdigit() or int(size) > MAX_BODY):
            return failed(413, f"The request body is larger than {MAX_BODY // 1024} KB")
    return await call_next(request)


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
