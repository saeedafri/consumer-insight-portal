"""Operational logs for admins (/app/logs): everything the server writes, readable without a shell on the server.

  nginx-access   every request nginx answered (JSON lines: time, client, path, status, bytes, seconds, cache)
  nginx-error    nginx's warnings and errors
  api            the API's own log (startup, slow requests, errors)
  etl            the scheduled ETL runs (deploy/etl-loop.sh) and their errors
  publish        the publish at container start (restore from backup, or a full rebuild)
  container      the container's supervisor (deploy/start.sh): which process stopped and when
  platform       Azure App Service's own docker log (pulls, starts, restarts), when App Service logging is on
  machine        CPU, memory (as Azure counts it), bandwidth and disk every 15 s (deploy/machine-log.sh)

GET /api/v1/admin/metrics?minutes= is the dashboard above the logs: the machine series, traffic per minute (requests,
status classes, bytes, cache, server time percentiles), the busiest pages and visitors, recent errors and restarts.
  security       sign-ins, sign-outs, denied and revoked access (cip_access_log), plus every 401/403/429 nginx answered

GET /api/v1/admin/logs?source=&q=&lines= gives the newest lines first; /api/v1/admin/logs/download?source= the file.
Only fixed files are read, never a path from the request. Admins only (api/signin.admin).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
from collections import Counter, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import text

from api.signin import admin
from app.core.database import get_engine

LOGS = Path(os.environ.get("CIP_LOG_DIR") or Path(__file__).resolve().parents[1] / "logs")
PLATFORM = Path("/home/LogFiles")   # App Service writes its docker log here when "App Service logs: File System" is on
FILES = {"nginx-access": "nginx-access.log", "nginx-error": "nginx-error.log", "api": "api.log", "etl": "etl-loop.log",
         "etl-errors": "forsta-etl-errors.jsonl", "publish": "publish-start.log", "container": "container.log",
         "machine": "machine.log"}
LABELS = {"nginx-access": "nginx: every request", "nginx-error": "nginx: warnings and errors", "api": "API",
          "etl": "ETL runs", "etl-errors": "ETL errors", "publish": "Publish at start", "container": "Container supervisor", "machine": "Machine: CPU, memory, bandwidth, disk",
          "platform": "Azure App Service (docker)", "security": "Security events"}
TAIL_BYTES = 4 * 2**20   # the newest 4 MB of a file: thousands of lines, never the whole file in memory

router = APIRouter(prefix="/api/v1/admin")


def path_of(source: str) -> Path | None:
    if source == "platform":
        found = sorted(PLATFORM.glob("*docker*.log"), key=lambda p: p.stat().st_mtime) if PLATFORM.is_dir() else []
        return found[-1] if found else None
    name = FILES.get(source)
    return LOGS / name if name else None


def tail(path: Path, lines: int, needle: str) -> list[str]:
    """The newest `lines` lines containing `needle` (any case), newest first."""
    with path.open("rb") as f:
        f.seek(max(0, f.seek(0, os.SEEK_END) - TAIL_BYTES))
        found = deque(maxlen=lines)
        for raw in f:
            line = raw.decode("utf-8", errors="replace").rstrip("\n")
            if line and (not needle or needle in line.lower()):
                found.append(line)
    return list(reversed(found))


def security(lines: int, needle: str) -> list[str]:
    """Access decisions from the database and refusals nginx gave, newest first, as one list."""
    with get_engine("app").connect() as conn:
        rows = conn.execute(text("SELECT ts, email, role, action, target, detail FROM cip_access_log"
                                 " ORDER BY log_id DESC LIMIT :n"), {"n": lines}).all()
    events = [json.dumps({"time": ts.isoformat() if hasattr(ts, "isoformat") else str(ts), "source": "portal", "email": email, "role": role, "action": action,
                          "target": target, "detail": detail}) for ts, email, role, action, target, detail in rows]
    access = LOGS / FILES["nginx-access"]
    if access.exists():
        events += [line for line in tail(access, lines * 4, "") if '"status":40' in line and any(
            f'"status":{code}' in line for code in (401, 403, 429))]
    events = [e for e in events if not needle or needle in e.lower()]
    return sorted(events, key=lambda e: json.loads(e).get("time", ""), reverse=True)[:lines]


@router.get("/logs")
def logs(source: str = "api", q: str = Query("", max_length=200), lines: int = Query(200, ge=1, le=5000),
         page: int = Query(1, ge=1, le=200), who: dict = Depends(admin)) -> dict:
    """One page of a log, newest first: page 1 is the newest `lines` lines (containing `q`), page 2 the ones before."""
    sources = []
    for name, label in LABELS.items():
        path = None if name == "security" else path_of(name)
        sources.append({"id": name, "label": label, "bytes": path.stat().st_size if path and path.exists() else None})
    if source not in LABELS:
        raise HTTPException(404, "No such log")
    needle = q.strip().lower()
    wanted = page * lines + 1   # one more than this page needs: tells whether an older page exists
    if source == "security":
        found = security(wanted, needle)
    else:
        path = path_of(source)
        found = tail(path, wanted, needle) if path and path.exists() else []
    return {"sources": sources, "source": source, "page": page, "per_page": lines,
            "lines": found[(page - 1) * lines:page * lines], "more": len(found) > page * lines}


@router.get("/logs/download")
def download(source: str, who: dict = Depends(admin)) -> FileResponse:
    path = None if source == "security" else path_of(source)
    if not path or not path.exists():
        raise HTTPException(404, "No such log file")
    return FileResponse(path, media_type="text/plain", filename=f"cip-{source}-{path.name}")




# ======================================================================================================================
# The monitoring dashboard (top of /app/logs). GET /api/v1/admin/metrics answers everything it draws in one call.
#
# Where each number comes from:
#   machine   deploy/machine-log.sh writes one JSON line every 15 s to logs/machine.log: CPU, memory, bandwidth,
#             memory per process. machine_series() reads them back.
#   traffic   nginx writes one JSON line per request to logs/nginx-access.log (deploy/cip_logs.conf). Traffic reads
#             only the lines written since its last read and keeps per-minute totals for a day (a few KB per minute,
#             whatever the traffic). The API's minute loop (api/main.py _refresh_forever) also calls read_traffic(), so
#             a busy log is counted before deploy/etl-loop.sh rotates it.
#   storage   folder sizes, the two disks and the database's size, measured at most every 5 minutes (storage()).
#   caches    nginx's cache and the browser's from the request log; the API's own memory caches from api/main.py, which
#             registers a function in CACHE_REPORTERS (this file cannot import api/main.py: main imports this file).
#   visitors  the signed-in email nginx logs from the session cookie (deploy/cip_auth.js user()), and the city of the
#             address from the free DB-IP Lite file (GEO_FILE), looked up on this server: no address is sent anywhere.
# ======================================================================================================================
BOUNDS_MS = (0.5, 1, 2, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, float("inf"))   # server-time buckets
KEEP_MINUTES = 24 * 60
FIRST_READ = 64 * 2**20   # a fresh API process reads at most the newest 64 MB of the request log
ADMIN_PAGES = "/api/v1/admin/"   # this dashboard's own polling: counted in the totals, left out of "busiest pages"
CACHE_REPORTERS: list = []   # functions returning {name: {...}} about the API's memory caches (api/main.py adds one)
GEO_FILE = Path(os.environ.get("CIP_GEO_FILE", "/srv/cip/geo/dbip-city-lite.mmdb"))   # deploy/Dockerfile downloads it

# What each page is, in words, for the "busiest pages" table (page_of() turns numbers in a path into :id)
PAGE_NAMES = {
    "/api/v1/waves/:id/crosstab": "Cross-tab (one question by two groups)",
    "/api/v1/waves/:id/results": "Question results",
    "/api/v1/waves/:id/book": "A wave's full question book",
    "/api/v1/waves": "Survey library list",
    "/api/v1/search": "Search",
    "/api/v1/me": "Who is signed in",
    "/api/v1/methodology": "Methodology page",
    "/api/v1/schedule": "Launch schedule",
    "/api/v1/ask": "Ask CIP",
    "/": "Public home page",
    "/features/": "Public site: features",
    "/this-week/": "Public site: this week",
    "/data/": "Public site: the data",
    "/sign-in/": "Sign-in page",
    "/auth/dev-login": "Sign-in (demo)",
    "/auth/login": "Sign-in (SSO)",
    "/auth/callback": "Sign-in (SSO return)",
    "/app/": "Portal page (first load)",
    "/app": "Portal page (first load)",
    "/api/v1/alerts": "Alerts (list)",
    "/api/v1/team/views": "Saved team views",
    "/api/v1/team/summary": "Team summary",
    "/api/v1/boards": "Boards (list)",
    "/api/v1/audiences": "Audiences (list)",
    "/api/v1/dashboards/:id": "A dashboard",
    "/api/v1/export/xlsx": "Excel export",
    "/api/v1/export/pptx": "PowerPoint export",
    "(website files)": "Images, fonts and page data",
}

# Plain-English meaning of the error lines the servers write, for "Recent problems" (first match wins)
PROBLEM_MEANINGS = (
    ("client intended to send too large body", "A request was bigger than the 20 MB limit and was refused. Harmless."),
    ("prematurely closed connection", "The API stopped while answering (a deploy or a restart); that one request failed."),
    ("connection reset by peer", "The API stopped while answering (a deploy or a restart); that one request failed."),
    ("connect() failed", "The API was not running yet (the minute after a start); nginx could not reach it."),
    ("upstream timed out", "The API took longer than the time limit to answer; that request failed."),
    ("no live upstreams", "The API was down; requests failed until it came back."),
    ("integrity (watch)", "A data check found something to look at (not an outage). The line says what and how many."),
    ("traceback", "The API hit an unexpected error. The API log has the full details."),
)


def page_of(path: str) -> str:
    """/api/v1/waves/532/crosstab?q=... -> /api/v1/waves/:id/crosstab; website files collapse to one group."""
    path = path.split("?", 1)[0]
    if path.startswith("/_next/") or "__next." in path or path.endswith((".png", ".ico", ".svg", ".txt", ".xml", ".woff2")):
        return "(website files)"   # images, fonts and the pages' prefetched data: the browser asks for many per page
    if path.startswith("/app/"):
        return "/app/"   # every portal screen is the same page on a first load; its router then picks the screen
    return re.sub(r"/\d+(?=/|$)", "/:id", path)[:80]


def minute_of(line: str) -> str:
    """The UTC minute a log line starts with, as "2026-11-06T04:49", whatever the writer's style:
    "2026-11-06 04:55:58,312" (the API, the ETL), "2026/11/06 04:56:04" (nginx), "2026-11-06T04:49:00Z" (start.sh)."""
    return line[:16].replace("/", "-").replace(" ", "T")


class Traffic:
    """Per-minute request totals from nginx's request log, read incrementally (see the block comment above)."""

    def __init__(self):
        self.lock = threading.Lock()
        self.inode, self.offset, self.minutes = None, 0, {}

    def read(self, path: Path) -> None:
        with self.lock:
            try:
                info = path.stat()
            except OSError:
                return
            if self.inode is None:
                self.inode, self.offset = info.st_ino, max(0, info.st_size - FIRST_READ)
            elif info.st_ino != self.inode or info.st_size < self.offset:   # rotated: from the new file's start
                copy = path.with_name(path.name + ".1")   # deploy/etl-loop.sh copies a full log to .1, then empties it
                if copy.exists() and copy.stat().st_size >= self.offset:
                    self.drain(copy)   # the lines written since the last read are only in the copy now
                self.inode, self.offset = info.st_ino, 0
            self.drain(path)
            for old in sorted(self.minutes)[:-KEEP_MINUTES]:
                del self.minutes[old]

    def drain(self, path: Path) -> None:
        with path.open("rb") as f:
            f.seek(max(0, self.offset - 1))
            if self.offset and f.read(1) != b"\n":
                f.readline()   # landed mid-line (a fresh process's first read): skip to the next whole line
            for raw in f:
                if not raw.endswith(b"\n"):
                    break   # nginx is still writing this line: the next call reads it
                self.offset = f.tell()
                self.add(raw)

    def add(self, raw: bytes) -> None:
        try:
            entry = json.loads(raw)
            stamp = entry["time"]
            if not stamp.endswith(("+00:00", "Z")):   # nginx writes the server's local time: minutes are kept in UTC
                stamp = datetime.fromisoformat(stamp).astimezone(timezone.utc).isoformat()
            minute, status, ms = stamp[:16], int(entry["status"]), float(entry["seconds"]) * 1000
        except (ValueError, KeyError, TypeError):
            return
        if entry.get("client") == "127.0.0.1":   # the platform's own probes and our cache warming, not visitors
            return
        m = self.minutes.get(minute)
        if m is None:
            m = self.minutes[minute] = {
                "requests": 0, "2xx": 0, "3xx": 0, "4xx": 0, "5xx": 0, "bytes": 0, "hit": 0, "file": 0, "api": 0,
                "browser": 0, "times": [0] * len(BOUNDS_MS), "slowest": 0.0, "cache": Counter(),
                "pages": Counter(), "page_ms": Counter(), "page_slowest": Counter(), "page_hits": Counter(),
                "clients": Counter(), "users": {}}
        m["requests"] += 1
        m[f"{min(status // 100, 5)}xx" if status >= 200 else "2xx"] += 1
        m["bytes"] += int(entry.get("bytes") or 0)
        cache = entry.get("cache") or ""
        served = "hit" if cache == "HIT" else "file" if entry.get("api_seconds") in ("", "-", None) else "api"
        m[served] += 1
        m["browser"] += status == 304   # the browser already had it: "not modified", no body sent
        if cache:
            m["cache"][cache] += 1   # nginx's cache: HIT, MISS, EXPIRED, BYPASS…
        m["times"][next(i for i, bound in enumerate(BOUNDS_MS) if ms <= bound)] += 1
        m["slowest"] = max(m["slowest"], ms)
        page = page_of(entry.get("path", ""))
        if not page.startswith(ADMIN_PAGES) and (len(m["pages"]) < 300 or page in m["pages"]):
            m["pages"][page] += 1
            m["page_ms"][page] += ms
            m["page_slowest"][page] = max(m["page_slowest"][page], ms)
            m["page_hits"][page] += served != "api"   # answered without Python (nginx cache or a published file)
        client = entry.get("client", "")
        if len(m["clients"]) < 300 or client in m["clients"]:
            m["clients"][client] += 1
            user = entry.get("user") or ""
            if user and status != 401:   # a forged or expired cookie gets 401: never shown as that person
                m["users"][client] = user


TRAFFIC = Traffic()


def read_traffic() -> None:
    """Count the request-log lines written since the last call. Called by metrics() and every minute by the API."""
    TRAFFIC.read(LOGS / FILES["nginx-access"])


def percentile(times: list[int], share: float, slowest: float) -> float:
    """The server time under which `share` of the requests were answered: the bucket's upper bound (ms). For the
    open-ended top bucket (over 5 s), the slowest request seen, instead of a made-up number."""
    total, seen = sum(times), 0
    for bound, count in zip(BOUNDS_MS, times):
        seen += count
        if total and seen >= share * total:
            return bound if bound != float("inf") else round(slowest, 1)
    return 0.0


def machine_series(since: str) -> list[dict]:
    """The machine samples (deploy/machine-log.sh) from `since` on, oldest first."""
    path = LOGS / "machine.log"
    if not path.exists():
        return []
    out = []
    for line in reversed(tail(path, 6000, "")):
        try:
            sample = json.loads(line)
        except ValueError:
            continue
        if sample.get("time", "") >= since and sample.get("source"):   # samples before 5 Nov 2026 read the whole host
            out.append(sample)
    return out


# ---- Storage: which disk, which folders, how big --------------------------------------------------------------------
# Measured at most every 5 minutes, from the API's minute loop (api/main.py), so the dashboard never waits on `du`.
STORAGE_EVERY = 300
STORAGE = {"measured": None, "disks": [], "folders": [], "database": None}
STORAGE_LOCK = threading.Lock()
SRV = Path(os.environ.get("CIP_SRV_DIR", "/srv/cip"))
FOLDERS = (   # (what it is, where, why it exists)
    ("Published files", SRV / "published", "Every answer prepared ahead (books, results, cross-tabs): nginx sends them as they are."),
    ("nginx cache", Path(os.environ.get("CIP_NGINX_CACHE", "/var/cache/nginx/data")), "Answers the API computed, kept 60 s to 7 days so the next asker gets them without Python."),
    ("Published-files backup", Path(os.environ.get("CIP_PUBLISH_BACKUP_URL", "/home/cip/published-backup")), "A copy on Azure's permanent storage (/home): a restart restores it in about 1 s instead of rebuilding."),
    ("Logs", LOGS, "These logs. Each file is rotated at 20 MB, one old copy kept (deploy/etl-loop.sh)."),
    ("Location file", GEO_FILE.parent, "DB-IP Lite: the city of a visitor's address, looked up here (Top visitors)."),
)


def folder_mb(path: Path) -> float | None:
    """A folder's size on disk in MB (du), or None when it is not there (e.g. on a laptop)."""
    if not path.exists():
        return None
    try:
        done = subprocess.run(["du", "-sk", str(path)], capture_output=True, text=True, timeout=60)
        return round(int(done.stdout.split()[0]) / 1024, 1)
    except (OSError, ValueError, IndexError, subprocess.TimeoutExpired):
        return None


def database_size() -> dict | None:
    """The portal database's size (MySQL's own table statistics) and its number of tables."""
    try:
        with get_engine("app").connect() as conn:
            name, mb, tables = conn.execute(text(
                "SELECT DATABASE(), ROUND(SUM(data_length + index_length) / 1048576, 1), COUNT(*)"
                " FROM information_schema.tables WHERE table_schema = DATABASE()")).one()
        return {"name": name, "mb": float(mb or 0), "tables": int(tables)}
    except Exception:   # the dashboard shows "not measured" rather than failing
        return None


def measure_storage(force: bool = False) -> None:
    """Refresh STORAGE when it is older than 5 minutes. Slow (du over many files), so never called per request."""
    measured = STORAGE["measured"]
    if not force and measured and (datetime.now(timezone.utc) - measured).total_seconds() < STORAGE_EVERY:
        return
    disks = []
    for label, path, meaning in (("Container disk", SRV, "The app's own files, published answers, nginx cache and logs. Emptied on every deploy."),
                                 ("Azure permanent storage (/home)", Path("/home"), "Survives deploys and restarts: the published-files backup lives here.")):
        usage = shutil.disk_usage(path) if path.exists() else None
        if usage and usage.total:   # an empty mount point (a laptop's /home) is not a disk worth showing
            disks.append({"name": label, "path": str(path), "meaning": meaning, "used_mb": round(usage.used / 2**20),
                          "total_mb": round(usage.total / 2**20), "used_pct": round(100 * usage.used / max(1, usage.total), 1)})
    folders = [{"name": name, "path": str(path), "meaning": meaning, "mb": folder_mb(path)} for name, path, meaning in FOLDERS]
    with STORAGE_LOCK:
        STORAGE.update(measured=datetime.now(timezone.utc), disks=disks, folders=folders, database=database_size())


# ---- Visitors: who and where ----------------------------------------------------------------------------------------
GEO_READER = None
GEO_CACHE: dict[str, str] = {}


def place_of(address: str) -> str:
    """"Mumbai, Maharashtra, India" for an IP address, from the local DB-IP Lite file; "" when unknown."""
    global GEO_READER
    if address in GEO_CACHE:
        return GEO_CACHE[address]
    place = ""
    try:
        if GEO_READER is None and GEO_FILE.exists():
            import maxminddb   # only where the file exists (the server image)
            GEO_READER = maxminddb.open_database(str(GEO_FILE))   # memory-mapped: the OS reads only the pages used
        found = GEO_READER.get(address) if GEO_READER else None
        if found:
            names = [found.get("city", {}).get("names", {}).get("en"),
                     (found.get("subdivisions") or [{}])[0].get("names", {}).get("en"),
                     found.get("country", {}).get("names", {}).get("en")]
            place = ", ".join(n for n in names if n)
    except (ValueError, OSError, ImportError):
        place = ""
    GEO_CACHE[address] = place
    return place


# ---- Restarts, ETL runs and problems, in words ----------------------------------------------------------------------
def restarts(since: str) -> list[dict]:
    """Container starts and stops (deploy/start.sh writes them to logs/container.log), newest first."""
    path = path_of("container")
    if not path or not path.exists():
        return []
    out = []
    for line in tail(path, 200, "start.sh"):
        if minute_of(line) < since:
            continue
        build = re.search(r"\(build ([^)]+)\)", line)
        stopped = re.search(r"a process stopped \(exit (\d+)\)", line)
        out.append({"time": line[:20], "build": build.group(1) if build else "",
                    "what": f"A process stopped (exit code {stopped.group(1)}): the container was restarted" if stopped
                    else "Started nginx, the API and the ETL scheduler" if "started" in line else line[21:200]})
    return out[:20]


def etl_runs(since: str) -> list[dict]:
    """The ETL's own report lines (deploy/etl-loop.sh → logs/etl-loop.log): what it loaded and any warning or error."""
    path = path_of("etl")
    if not path or not path.exists():
        return []
    out = []
    for line in tail(path, 400, ""):
        level = next((w for w in ("ERROR", "CRITICAL", "WARNING") if f" {w} " in line), "INFO")
        if minute_of(line) < since or ("Created engine" in line):   # the database connection line is noise here
            continue
        if level == "INFO" and not any(w in line for w in ("Loaded", "Register", "finished", "started", "skipped")):
            continue
        out.append({"time": line[:19], "level": level, "message": re.sub(r"^\S+ \S+ +\w+ +\S+ \| ", "", line)[:400],
                    "meaning": next((m for k, m in PROBLEM_MEANINGS if k in line.lower()), "")})
    return out[:30]


def problems(since: str) -> list[dict]:
    """Error lines from the API, nginx and the ETL in the chosen time range, newest first, each with what it means."""
    found = []
    for source, word in (("api", " error "), ("api", " critical "), ("api", "traceback"), ("nginx-error", "[error]"), ("nginx-error", "[crit]"),
                         ("nginx-error", "[alert]"), ("etl", " error "), ("etl", "warning")):
        path = path_of(source)
        if path and path.exists():
            found += [{"source": source, "minute": minute_of(line), "line": line[:400],
                       "meaning": next((m for k, m in PROBLEM_MEANINGS if k in line.lower()), "")}
                      for line in tail(path, 30, word) if minute_of(line) >= since and "[PERF-SLOW]" not in line]
    unique = {(p["source"], p["line"]): p for p in found}   # the same line can match two words
    return sorted(unique.values(), key=lambda p: p["minute"], reverse=True)[:30]


@router.get("/metrics")
def metrics(minutes: int = Query(60, ge=5, le=KEEP_MINUTES), who: dict = Depends(admin)) -> dict:
    """Everything the dashboard draws for the last `minutes` (see the block comment above for where each comes from)."""
    now = datetime.now(timezone.utc)
    since = (now - timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M")
    read_traffic()
    fields = ("requests", "2xx", "3xx", "4xx", "5xx", "bytes", "hit", "file", "api", "browser")
    with TRAFFIC.lock:
        chosen = [(k, v) for k, v in sorted(TRAFFIC.minutes.items()) if k >= since]
        times = [sum(col) for col in zip(*(v["times"] for _, v in chosen))] or [0] * len(BOUNDS_MS)
        slowest = max((v["slowest"] for _, v in chosen), default=0.0)
        pages, page_ms, page_hits, page_slowest, clients, cache = Counter(), Counter(), Counter(), Counter(), Counter(), Counter()
        users: dict[str, str] = {}
        for _, v in chosen:
            pages.update(v["pages"]); page_ms.update(v["page_ms"]); page_hits.update(v["page_hits"])
            clients.update(v["clients"]); cache.update(v["cache"]); users.update(v["users"])
            for page, ms in v["page_slowest"].items():
                page_slowest[page] = max(page_slowest[page], ms)
        traffic = [{"minute": k, **{f: v[f] for f in fields}, "p50_ms": percentile(v["times"], .5, v["slowest"]),
                    "p95_ms": percentile(v["times"], .95, v["slowest"]), "p99_ms": percentile(v["times"], .99, v["slowest"])}
                   for k, v in chosen]
    totals = {f: sum(t[f] for t in traffic) for f in fields}
    totals.update(p50_ms=percentile(times, .5, slowest), p95_ms=percentile(times, .95, slowest),
                  p99_ms=percentile(times, .99, slowest), slowest_ms=round(slowest, 1),
                  under_1ms=round(100 * sum(times[:2]) / max(1, sum(times)), 1))
    asked = totals["requests"]
    caches = [   # every cache layer, what it holds and how often it answered
        {"name": "Browser cache", "where": "Each visitor's browser",
         "meaning": "The browser already had the answer and the server only said \"not modified\" (304). Website files are cached by browsers for a year and never re-asked.",
         "answered": totals["browser"], "share_pct": round(100 * totals["browser"] / max(1, asked), 1), "size": "on each visitor's computer"},
        {"name": "nginx cache", "where": "Container disk", "meaning": "Answers the API computed once, sent again by nginx without Python.",
         "answered": cache["HIT"], "share_pct": round(100 * cache["HIT"] / max(1, asked), 1),
         "detail": dict(cache.most_common())},
        {"name": "Published files", "where": "Container disk", "meaning": "Answers prepared ahead by the publish step, sent by nginx as files.",
         "answered": totals["file"], "share_pct": round(100 * totals["file"] / max(1, asked), 1)},
    ]
    for report in CACHE_REPORTERS:   # the API's memory caches (api/main.py)
        caches += report()
    with STORAGE_LOCK:
        storage = {"measured": STORAGE["measured"].isoformat(timespec="seconds") if STORAGE["measured"] else None,
                   "disks": STORAGE["disks"], "folders": STORAGE["folders"], "database": STORAGE["database"]}
    return {
        "since": since, "now": now.isoformat(timespec="seconds"), "machine": machine_series(since),
        "traffic": traffic, "totals": totals, "caches": caches, "storage": storage,
        "histogram": [{"up_to_ms": b if b != float("inf") else None, "requests": c} for b, c in zip(BOUNDS_MS, times)],
        "pages": [{"page": p, "name": PAGE_NAMES.get(p, ""), "requests": n, "share_pct": round(100 * n / max(1, asked), 1),
                   "average_ms": round(page_ms[p] / n, 1), "slowest_ms": round(page_slowest[p], 1),
                   "without_python_pct": round(100 * page_hits[p] / n, 1)} for p, n in pages.most_common(15)],
        "clients": [{"client": c, "user": users.get(c, ""), "place": place_of(c), "requests": n}
                    for c, n in clients.most_common(10)],
        "problems": problems(since), "restarts": restarts(since), "etl": etl_runs(since),
    }
