"""The Logs page's monitoring dashboard (/app/logs, top), for admins: GET /api/v1/admin/metrics answers everything it
draws in one call. The raw logs below the dashboard are api/logs.py; this file reads the same files through it.
"""
from __future__ import annotations

import io
import ipaddress
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
from fastapi.responses import Response
from sqlalchemy import text

from api import logs
from api.logs import FILES, path_of, tail
from api.signin import admin
from shared.core.database import get_engine

router = APIRouter(prefix="/api/v1/admin")


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
HOURS_FILE = "traffic-hours.jsonl"   # one line per finished hour, in logs/ (on /home on Azure: it survives deploys)
HOUR_TOP = 25   # pages and addresses kept per hour: ~3 KB a line, ~25 MB a year
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
    ("no such file or directory", "A browser or a bot asked for a website file that is not there: an open page's old script just "
     "after a deploy (a reload fixes it), or a probe for a common file. Harmless unless the same file repeats for real visitors."),
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
    "2026-11-06 04:55:58,312" (the API, the ETL), "2026/11/06 04:56:04" (nginx), "2026-11-06T04:49:00Z" (start.sh),
    "[2026-11-06 19:21:15 +0000]" (gunicorn). "" for a line with no time (a traceback's lines), so no time range
    takes it: as text "TracebackT(mostT" sorted after every date and showed a 6 Nov error in every range."""
    stamp = line.lstrip("[")[:16].replace("/", "-").replace(" ", "T")
    return stamp if re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d", stamp) else ""


class Traffic:
    """Per-minute request totals from nginx's request log, read incrementally (see the block comment above)."""

    def __init__(self):
        self.lock = threading.Lock()
        self.inode, self.offset, self.minutes = None, 0, {}
        self.whole, self.written = False, None   # read the log from its start; the newest hour in HOURS_FILE

    def read(self, path: Path) -> None:
        with self.lock:
            try:
                info = path.stat()
            except OSError:
                return
            if self.inode is None:
                self.inode, self.offset = info.st_ino, max(0, info.st_size - FIRST_READ)
                self.whole = self.offset == 0
            elif info.st_ino != self.inode or info.st_size < self.offset:   # rotated: from the new file's start
                copy = path.with_name(path.name + ".1")   # deploy/etl-loop.sh copies a full log to .1, then empties it
                if copy.exists() and copy.stat().st_size >= self.offset:
                    self.drain(copy)   # the lines written since the last read are only in the copy now
                self.inode, self.offset = info.st_ino, 0
            self.drain(path)
            self.save_hours(path.with_name(HOURS_FILE))
            for old in sorted(self.minutes)[:-KEEP_MINUTES]:
                del self.minutes[old]

    def save_hours(self, file: Path) -> None:
        """Append each finished hour not yet in `file` (its minutes merged, machine samples averaged), so ranges longer
        than the day kept in memory, and the time before a restart, can still be shown. Skips the oldest hour held when
        the log was read from the middle (a fresh process reads only its newest 64 MB): that hour is incomplete."""
        if self.written is None:
            last = logs.tail(file, 1, "") if file.exists() else []
            self.written = json.loads(last[0])["hour"] if last else ""
        finished = (datetime.now(timezone.utc) - timedelta(minutes=3)).strftime("%Y-%m-%dT%H")   # nginx flushes late
        hours = sorted({k[:13] for k in self.minutes if self.written < k[:13] < finished})
        if hours and not self.whole and hours[0] == min(self.minutes)[:13]:
            hours = hours[1:]
        try:
            with file.open("a") as out:
                for hour in hours:
                    out.write(json.dumps(hour_summary(hour, [v for k, v in self.minutes.items() if k.startswith(hour)])) + "\n")
                    self.written = hour
        except OSError:   # a read-only logs/ (a laptop checkout): ranges past a day then show only what memory holds
            pass

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
COUNTED = ("requests", "2xx", "3xx", "4xx", "5xx", "bytes", "hit", "file", "api", "browser")


def merge(buckets: list[dict]) -> dict:
    """Minutes (or hours) added into one: counts summed, slowest kept, pages and addresses counted together."""
    out = {f: sum(b[f] for b in buckets) for f in COUNTED}
    out["times"] = [sum(col) for col in zip(*(b["times"] for b in buckets))] or [0] * len(BOUNDS_MS)
    out["slowest"] = max((b["slowest"] for b in buckets), default=0.0)
    for name in ("cache", "pages", "page_ms", "page_hits", "clients"):
        out[name] = Counter()
        for b in buckets:
            out[name].update(b[name])
    out["page_slowest"] = Counter()
    for b in buckets:
        for page, ms in b["page_slowest"].items():
            out["page_slowest"][page] = max(out["page_slowest"][page], ms)
    out["users"] = {k: v for b in buckets for k, v in b["users"].items()}
    return out


def hour_summary(hour: str, minutes: list[dict]) -> dict:
    """One line of HOURS_FILE: the hour's requests (its busiest pages and addresses only) and its machine averages."""
    total = merge(minutes)
    pages = dict(total["pages"].most_common(HOUR_TOP))
    clients = dict(total["clients"].most_common(HOUR_TOP))
    samples = [s for s in machine_series(f"{hour}:00") if s["time"][:13] == hour]
    machine = None
    if samples:
        mean = lambda key: round(sum(s.get(key) or 0 for s in samples) / len(samples), 2)
        machine = {**samples[-1], "time": f"{hour}:30:00Z", **{k: mean(k) for k in (
            "cpu_pct", "cores_used", "working_set_mb", "anon_mb", "file_mb", "machine_used_mb", "net_in_kbs", "net_out_kbs", "load_1m")},
            "cpu_peak": max(s.get("cpu_pct") or 0 for s in samples), "memory_peak": max(s.get("working_set_mb") or 0 for s in samples)}
    return {"hour": hour, **{f: total[f] for f in COUNTED}, "times": total["times"], "slowest": total["slowest"],
            "cache": dict(total["cache"]), "pages": pages, "page_ms": {p: total["page_ms"][p] for p in pages},
            "page_hits": {p: total["page_hits"][p] for p in pages}, "page_slowest": {p: total["page_slowest"][p] for p in pages},
            "clients": clients, "users": {c: u for c, u in total["users"].items() if c in clients}, "machine": machine}


def saved_hours(since: str, until: str) -> list[dict]:
    """The hours of HOURS_FILE inside the range, oldest first (read only for ranges older than the day in memory)."""
    path = logs.LOGS / HOURS_FILE
    if not path.exists():
        return []
    with path.open() as f:
        return [h for h in map(json.loads, f) if since[:13] <= h["hour"] <= until[:13]]


def read_traffic() -> None:
    """Count the request-log lines written since the last call. Called by metrics() and every minute by the API."""
    TRAFFIC.read(logs.LOGS / FILES["nginx-access"])


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
    path = logs.LOGS / "machine.log"
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
STORAGE = {"measured": None, "disks": [], "folders": [], "database": None, "home": [], "home_measured": None}
HOME_EVERY = 3600   # /home is network storage (Azure Files): its folders are measured hourly, not every 5 minutes
STORAGE_LOCK = threading.Lock()
SRV = Path(os.environ.get("CIP_SRV_DIR", "/srv/cip"))
FOLDERS = (   # (what it is, where, why it exists)
    ("Published files", SRV / "published", "Every answer prepared ahead (books, results, cross-tabs): nginx sends them as they are."),
    ("nginx cache", Path(os.environ.get("CIP_NGINX_CACHE", "/var/cache/nginx/data")), "Answers the API computed, kept 60 s to 7 days so the next asker gets them without Python."),
    ("Published-files backup", Path(os.environ.get("CIP_PUBLISH_BACKUP_URL", "/home/cip/published-backup")), "A copy on Azure's permanent storage (/home): a restart restores it in about 1 s instead of rebuilding."),
    ("Logs", logs.LOGS, "These logs, kept for good: each file that reaches 20 MB is packed into logs/archive/ as a .zip (deploy/archive-log.py)."),
    ("Location file", GEO_FILE.parent, "DB-IP Lite: the city of a visitor's address, looked up here (Top visitors)."),
)


def folder_mb(path: Path) -> float | None:
    """A folder's size on disk in MB (du), or None when it is not there (e.g. on a laptop)."""
    if not path.exists():
        return None
    path = path.resolve()   # logs/ is a link to /home/cip/logs: du would measure the link, not the folder
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
    # Both disks are Azure's and shared: "used" counts everything on them, CIP's own part is measured on its own (ours_mb).
    # The container disk is the App Service worker's local disk (its size is Azure's for the plan, 73 GB on P0v3): the
    # operating system and every image a deploy pulled (Azure clears old images itself) take most of it. 7 Nov 2026:
    # 36 GB used, of which CIP's files 0.3 GB; it grew with the six deploys of that day, not with visitors.
    for label, path, ours, meaning in (
            ("Azure worker disk (container)", SRV, SRV, "The App Service worker's own disk: Azure sizes it for the plan and fills most of it "
             "with the operating system and the images each deploy pulls (Azure removes old ones). CIP's files on it are counted separately."),
            ("Azure permanent storage (/home)", Path("/home"), Path("/home/cip"), "Azure Files, shared by the plan: survives deploys and "
             "restarts. CIP keeps only the published-files backup here.")):
        usage = shutil.disk_usage(path) if path.exists() else None
        if usage and usage.total:   # an empty mount point (a laptop's /home) is not a disk worth showing
            disks.append({"name": label, "path": str(path), "meaning": meaning, "used_mb": round(usage.used / 2**20),
                          "total_mb": round(usage.total / 2**20), "used_pct": round(100 * usage.used / max(1, usage.total), 1),
                          "ours_mb": folder_mb(ours)})
    folders = [{"name": name, "path": str(path), "meaning": meaning, "mb": folder_mb(path)} for name, path, meaning in FOLDERS]
    home, home_measured = STORAGE["home"], STORAGE["home_measured"]
    now = datetime.now(timezone.utc)
    if Path("/home").is_dir() and (not home_measured or (now - home_measured).total_seconds() >= HOME_EVERY):
        # what /home holds, folder by folder: ours (cip), Azure's own (LogFiles, site, data…), so its use is explained
        home = sorted(({"path": str(p), "mb": folder_mb(p)} for p in Path("/home").iterdir() if p.is_dir()),
                      key=lambda f: -(f["mb"] or 0))
        home_measured = now
    with STORAGE_LOCK:
        STORAGE.update(measured=now, disks=disks, folders=folders, database=database_size(), home=home, home_measured=home_measured)


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
    for source, word in (("api", " error "), ("api", " critical "), ("api", "[error]"), ("nginx-error", "[error]"), ("nginx-error", "[crit]"),
                         ("nginx-error", "[alert]"), ("etl", " error "), ("etl", "warning")):
        path = path_of(source)
        if path and path.exists():
            found += [{"source": source, "minute": minute_of(line), "line": line[:400],
                       "meaning": next((m for k, m in PROBLEM_MEANINGS if k in line.lower()), "")}
                      for line in tail(path, 30, word) if minute_of(line) >= since and "[PERF-SLOW]" not in line]
    unique = {(p["source"], p["line"]): p for p in found}   # the same line can match two words
    return sorted(unique.values(), key=lambda p: p["minute"], reverse=True)[:30]


def sign_ins(since: str) -> list[dict]:
    """Who signed in, when, how and from where (api/signin.py writes one "sign-in:" line to the API log each time),
    newest first: [{time, email, role, method, address, place}]."""
    path = path_of("api")
    if not path or not path.exists():
        return []
    out = []
    for line in tail(path, 300, "sign-in:"):
        found = re.search(r"sign-in: (\S+) role=(\S+) via (\S+) from (\S*)", line)
        if found and minute_of(line) >= since:
            email, role, method, address = found.groups()
            out.append({"time": line[:19], "email": email, "role": role, "method": method, "address": address,
                        "place": place_of(address) if address else ""})
    return out[:50]


def time_range(minutes: int, start: str, end: str) -> tuple[str, str]:
    """(since, until) as UTC minutes "2026-11-07T14:20": `start`/`end` (ISO, UTC) when given, else the last `minutes`."""
    now = datetime.now(timezone.utc)
    try:
        until = datetime.fromisoformat(end.replace("Z", "+00:00")) if end else now
        since = datetime.fromisoformat(start.replace("Z", "+00:00")) if start else until - timedelta(minutes=minutes)
    except ValueError:
        raise HTTPException(422, "start and end are dates and times, e.g. 2026-11-01T00:00Z")
    utc = lambda t: (t if t.tzinfo else t.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M")
    if utc(since) >= utc(until):
        raise HTTPException(422, "The start must be before the end")
    return utc(since), utc(until)


def in_range(when: str, since: str, until: str) -> bool:
    """A log line's time ("2026-11-07 14:20:01", "2026-11-07T14:20…") inside [since, until]."""
    minute = when[:16].replace(" ", "T")
    return since <= minute <= until


@router.get("/metrics")
def metrics(minutes: int = Query(60, ge=5, le=400 * 24 * 60), who: dict = Depends(admin), start: str = "", end: str = "",
            top: int = 25) -> dict:
    """Everything the dashboard draws for a time range (see the block comment above for where each number comes from):
    per minute while the range is inside the day kept in memory, else per hour from HOURS_FILE."""
    since, until = time_range(minutes, start, end)
    read_traffic()
    with TRAFFIC.lock:
        held = sorted(TRAFFIC.minutes.items())
        if since >= (datetime.now(timezone.utc) - timedelta(minutes=KEEP_MINUTES)).strftime("%Y-%m-%dT%H:%M"):
            step, chosen = "minute", [(k, v) for k, v in held if since <= k <= until]
            machine = [x for x in machine_series(since) if x["time"][:16] <= until]
        else:   # older than the day in memory: the saved hours, then the hours not saved yet
            step, saved = "hour", saved_hours(since, until)
            recent: dict[str, list] = {}
            for k, v in held:
                if since <= k <= until and k[:13] > (saved[-1]["hour"] if saved else ""):
                    recent.setdefault(k[:13], []).append(v)
            chosen = [(h["hour"] + ":00", h) for h in saved + [hour_summary(hour, vs) for hour, vs in sorted(recent.items())]]
            machine = [h["machine"] for _, h in chosen if h.get("machine")]
        total = merge([v for _, v in chosen])
        traffic = [{"minute": k, **{f: v[f] for f in COUNTED}, "p50_ms": percentile(v["times"], .5, v["slowest"]),
                    "p95_ms": percentile(v["times"], .95, v["slowest"]), "p99_ms": percentile(v["times"], .99, v["slowest"])}
                   for k, v in chosen]
    times, slowest, cache = total["times"], total["slowest"], total["cache"]
    pages, page_ms, page_hits, page_slowest, clients, users = (total[k] for k in ("pages", "page_ms", "page_hits", "page_slowest", "clients", "users"))
    totals = {f: total[f] for f in COUNTED}
    totals.update(p50_ms=percentile(times, .5, slowest), p95_ms=percentile(times, .95, slowest),
                  p99_ms=percentile(times, .99, slowest), slowest_ms=round(slowest, 1),
                  under_1ms=round(100 * sum(times[:2]) / max(1, sum(times)), 1))
    asked = totals["requests"]
    caches = [   # every cache layer, what it holds and how often it answered
        {"name": "Browser cache", "where": "Each visitor's browser",
         "meaning": "The browser already had the answer and the server only said \"not modified\" (304). Website files are cached by browsers for a year and never re-asked.",
         "answered": totals["browser"], "share_pct": round(100 * totals["browser"] / max(1, asked), 1), "size": "on each visitor's computer"},
        {"name": "nginx cache", "where": "Azure worker disk (container)", "meaning": "Answers the API computed once, sent again by nginx without Python.",
         "answered": cache["HIT"], "share_pct": round(100 * cache["HIT"] / max(1, asked), 1),
         "detail": dict(cache.most_common())},
        {"name": "Published files", "where": "Azure worker disk (container)", "meaning": "Answers prepared ahead by the publish step, sent by nginx as files.",
         "answered": totals["file"], "share_pct": round(100 * totals["file"] / max(1, asked), 1)},
    ]
    caches.append({"name": "API (Python), computed", "where": "API process",
                   "meaning": "Neither a cache nor a published file had it: Python built the answer (or checked the sign-in). nginx cache + published files + this row = 100 % of requests. The browser-cache row is not a fourth share: those \"not modified\" answers are counted inside the other three.",
                   "answered": totals["api"], "share_pct": round(100 * totals["api"] / max(1, asked), 1)})
    for report in CACHE_REPORTERS:   # the API's memory caches (api/main.py)
        caches += report()
    with STORAGE_LOCK:
        storage = {"measured": STORAGE["measured"].isoformat(timespec="seconds") if STORAGE["measured"] else None,
                   "disks": STORAGE["disks"], "folders": STORAGE["folders"], "database": STORAGE["database"],
                   "home": STORAGE["home"]}
    return {
        "since": since, "until": until, "step": step, "now": datetime.now(timezone.utc).isoformat(timespec="seconds"), "machine": machine,
        "traffic": traffic, "totals": totals, "caches": caches, "storage": storage,
        "histogram": [{"up_to_ms": b if b != float("inf") else None, "requests": c} for b, c in zip(BOUNDS_MS, times)],
        "pages": [{"page": p, "name": PAGE_NAMES.get(p, ""), "requests": n, "share_pct": round(100 * n / max(1, asked), 1),
                   "average_ms": round(page_ms[p] / n, 1), "slowest_ms": round(page_slowest[p], 1),
                   "without_python_pct": round(100 * page_hits[p] / n, 1)} for p, n in pages.most_common(15)],
        "clients": [{"client": c, "user": users.get(c, ""), "place": place_of(c), "requests": n}
                    for c, n in clients.most_common(min(top, 500))],
        **{name: [x for x in found(since) if in_range(x.get("time") or x.get("minute", ""), since, until)]
           for name, found in (("problems", problems), ("restarts", restarts), ("etl", etl_runs), ("sign_ins", sign_ins))},
    }


# ---- One visitor: what they asked for, and who or what they are -----------------------------------------------------
AUTOMATED = ("bot", "crawl", "spider", "curl", "python", "httpx", "go-http", "wget", "java/", "headless", "check", "monitor",
             "scan", "lightspeed", "(compatible)")   # words in a user agent that mean a program, not a person's browser


def visitor_kind(address: str, users: set, agents: set) -> str:
    """Who or what an address is, in words, from its sessions and user agents."""
    if users:
        return f"Signed in as {', '.join(sorted(users))}."
    if address.startswith("169.254."):
        return "Azure's own health check of the container (an internal address), not a visitor."
    if agents and all(any(w in a.lower() for w in AUTOMATED) or a.strip() in ("", "-") for a in agents):
        return "An automated program (a bot, a checker or a script), not a person: it never signed in."
    return "A browser that did not sign in: only public pages, or a sign-in page it left."


@router.get("/visitor")
def visitor(address: str = Query(..., max_length=45), who: dict = Depends(admin)) -> dict:
    """The newest 300 requests from one address (the current request log), with its place, browser and where it came from."""
    try:
        address = str(ipaddress.ip_address(address))
    except ValueError:
        raise HTTPException(422, "Not an internet address")
    path, needle, found = path_of("nginx-access"), f'"{address}"'.encode(), deque(maxlen=300)
    if path and path.exists():
        with path.open("rb") as f:   # the whole current file (rotated at 20 MB): a click, not a poll, can afford it
            found.extend(raw for raw in f if needle in raw)
    requests = []
    for line in reversed(found):
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if entry.get("client") != address:   # the address can also appear in a path or a referer
            continue
        api = entry.get("api_seconds") not in ("", "-", None)
        requests.append({"time": entry["time"], "method": entry.get("method", ""), "path": entry.get("path", ""),
                         "status": entry.get("status"), "ms": round(float(entry.get("seconds") or 0) * 1000, 1),
                         "bytes": entry.get("bytes"), "user": entry.get("user") or "", "agent": entry.get("agent") or "",
                         "from": entry.get("referer") or "", "served": "nginx cache" if entry.get("cache") == "HIT" else "API" if api else "file"})
    users = {r["user"] for r in requests if r["user"] and r["status"] != 401}
    agents = {r["agent"] for r in requests}
    kind = visitor_kind(address, users, agents) if requests else "No request from this address in the current request log (see Older logs)."
    return {"address": address, "place": place_of(address), "kind": kind,
            "agents": sorted(agents), "came_from": sorted({r["from"] for r in requests if r["from"]}), "requests": requests}


# ---- Everything on the page, as one Excel file ----------------------------------------------------------------------
IST = timezone(timedelta(hours=5, minutes=30))


def ist(when: str) -> str:
    """A log time (UTC, any of the writers' styles) as India time on a 12-hour clock: "7 Nov 2026, 8:20 PM"."""
    text = (when or "").replace("/", "-").replace(" ", "T").rstrip("Z")
    try:
        at = datetime.fromisoformat(text[:19] if "+" not in text[10:] else text)
    except ValueError:
        return when or ""
    at = (at if at.tzinfo else at.replace(tzinfo=timezone.utc)).astimezone(IST)
    return f"{at.day} {at:%b %Y}, {at:%I:%M %p}".replace(", 0", ", ")


@router.get("/metrics/download")
def download(minutes: int = Query(60, ge=5, le=400 * 24 * 60), who: dict = Depends(admin), start: str = "", end: str = "") -> Response:
    """The Logs page for a time range as one workbook: a sheet per table, the per-minute (or per-hour) figures with their
    charts, every visitor, and the requests of the current request log in the range. Built on demand, never stored."""
    from openpyxl import Workbook   # imported on use, as in api/exports.py: it costs the API ~25 MB
    from openpyxl.chart import BarChart, LineChart, Reference
    from openpyxl.styles import Font
    m = metrics(minutes, who, start, end, top=500)
    book = Workbook()
    book.remove(book.active)

    def sheet(title: str, head: list[str], rows: list[list]):
        page = book.create_sheet(title[:31])
        page.append(head)
        for cell in page[1]:
            cell.font = Font(bold=True)
        for row in rows:
            page.append(row)
        for column, name in zip(page.columns, head):
            page.column_dimensions[column[0].column_letter].width = min(60, max(12, len(name) + 2))
        return page

    def chart(page, kind, title: str, columns: list[int], anchor: str, rows: int):
        drawn = kind()
        drawn.title, drawn.height, drawn.width = title, 8, 22
        for c in columns:
            drawn.add_data(Reference(page, min_col=c, min_row=1, max_row=rows + 1), titles_from_data=True)
        drawn.set_categories(Reference(page, min_col=1, min_row=2, max_row=rows + 1))
        page.add_chart(drawn, anchor)

    t, unit = m["totals"], "minute" if m["step"] == "minute" else "hour"
    sheet("Summary", ["What", "Value"], [
        ["From (IST)", ist(m["since"])], ["To (IST)", ist(m["until"])], ["Figures per", unit],
        ["Requests", t["requests"]], ["Server errors (5xx)", t["5xx"]], ["Refused or not found (4xx)", t["4xx"]],
        ["Server time, 95 % faster than (ms)", t["p95_ms"]], ["Server time, half faster than (ms)", t["p50_ms"]],
        ["Slowest (ms)", t["slowest_ms"]], ["Under 1 ms (%)", t["under_1ms"]], ["Data sent (MB)", round(t["bytes"] / 2**20, 2)],
        ["Answered by the nginx cache", t["hit"]], ["Answered by a published file", t["file"]], ["Answered by the API (Python)", t["api"]],
        ["Browser already had it (304)", t["browser"]], ["Problems", len(m["problems"])], ["Sign-ins", len(m["sign_ins"])]])
    traffic = sheet(f"Requests per {unit}", ["When (IST)", "Requests", "OK (2xx)", "3xx", "4xx", "5xx", "MB sent", "nginx cache",
                                             "Published file", "API (Python)", "p50 ms", "p95 ms", "p99 ms"],
                    [[ist(x["minute"]), x["requests"], x["2xx"], x["3xx"], x["4xx"], x["5xx"], round(x["bytes"] / 2**20, 3),
                      x["hit"], x["file"], x["api"], x["p50_ms"], x["p95_ms"], x["p99_ms"]] for x in m["traffic"]])
    if m["traffic"]:
        chart(traffic, BarChart, f"Requests per {unit}", [2], "O2", len(m["traffic"]))
        chart(traffic, LineChart, f"Server time per {unit} (ms)", [11, 12, 13], "O20", len(m["traffic"]))
    machine = sheet("CPU, memory, bandwidth", ["When (IST)", "CPU %", "CPU peak %", "CPUs in use", "Memory MB (container)",
                                                "Our processes MB", "File cache MB", "Machine used MB", "Received KB/s", "Sent KB/s", "Load (1 min)"],
                    [[ist(x["time"]), x.get("cpu_pct"), x.get("cpu_peak", x.get("cpu_pct")), x.get("cores_used"), x.get("working_set_mb"),
                      x.get("anon_mb"), x.get("file_mb"), x.get("machine_used_mb"), x.get("net_in_kbs"), x.get("net_out_kbs"), x.get("load_1m")]
                     for x in m["machine"]])
    if m["machine"]:
        chart(machine, LineChart, "CPU %", [2], "N2", len(m["machine"]))
        chart(machine, LineChart, "Memory MB", [5, 6], "N20", len(m["machine"]))
        chart(machine, LineChart, "Bandwidth KB/s", [9, 10], "N38", len(m["machine"]))
    last = m["machine"][-1] if m["machine"] else {}
    sheet("Memory per process", ["Process", "MB (latest sample)"], sorted((last.get("processes_mb") or {}).items(), key=lambda x: -x[1]))
    histogram = sheet("Response times", ["Server time up to", "Requests"],
                      [[f"{h['up_to_ms']} ms" if h["up_to_ms"] is not None else "over 5 s", h["requests"]] for h in m["histogram"]])
    chart(histogram, BarChart, "Requests by server time", [2], "D2", len(m["histogram"]))
    sheet("How requests were answered", ["Layer", "Where", "What it does", "Answered", "Share %", "Size"],
          [[c["name"], c["where"], c["meaning"], c.get("answered"), c.get("share_pct"), c.get("size") or c.get("size_mb")] for c in m["caches"]])
    storage = m["storage"]
    sheet("Storage", ["Disk or folder", "Path", "What it holds", "CIP's MB", "Used MB", "Size MB", "Full %"],
          [[d["name"], d["path"], d["meaning"], d.get("ours_mb"), d["used_mb"], d["total_mb"], d["used_pct"]] for d in storage["disks"]]
          + [[f["name"], f["path"], f["meaning"], f["mb"], None, None, None] for f in storage["folders"]]
          + ([["MySQL database", storage["database"]["name"], f"{storage['database']['tables']} tables", storage["database"]["mb"], None, None, None]]
             if storage["database"] else []))
    sheet("Busiest pages", ["Page", "Path", "Requests", "Share %", "Average ms", "Slowest ms", "Without Python %"],
          [[x["name"], x["page"], x["requests"], x["share_pct"], x["average_ms"], x["slowest_ms"], x["without_python_pct"]] for x in m["pages"]])
    sheet("Visitors", ["Who", "Where (approximate)", "Address", "Requests"],
          [[x["user"] or "not signed in", x["place"], x["client"], x["requests"]] for x in m["clients"]])
    sheet("Sign-ins", ["When (IST)", "Who", "Role", "How", "Where (approximate)", "Address"],
          [[ist(x["time"]), x["email"], x["role"], x["method"], x["place"], x["address"]] for x in m["sign_ins"]])
    sheet("Problems", ["When (IST)", "From", "What it means", "The line"],
          [[ist(x["minute"]), x["source"], x["meaning"], x["line"]] for x in m["problems"]])
    sheet("Restarts", ["When (IST)", "What happened", "Build"], [[ist(x["time"]), x["what"], x["build"]] for x in m["restarts"]])
    sheet("ETL", ["When (IST)", "Level", "What happened", "What it means"], [[ist(x["time"]), x["level"], x["message"], x["meaning"]] for x in m["etl"]])
    path, rows = path_of("nginx-access"), deque(maxlen=50000)
    with (path.open("rb") if path and path.exists() else io.BytesIO()) as f:   # the whole current file, as Visitor reads it
        for line in f:
            try:
                entry = json.loads(line)
                when = datetime.fromisoformat(entry["time"]).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M")
            except (ValueError, KeyError):
                continue
            if m["since"] <= when <= m["until"]:
                rows.append([ist(entry["time"]), entry.get("client"), entry.get("user") or "", entry.get("method"), entry.get("path"),
                         entry.get("status"), round(float(entry.get("seconds") or 0) * 1000, 1), entry.get("bytes"),
                             entry.get("cache") or "", entry.get("referer") or "", entry.get("agent") or ""])
    sheet("Requests (newest 50,000)", ["When (IST)", "Address", "Who", "Method", "Path", "Status", "Server ms", "Bytes",
                                       "nginx cache", "Came from", "Browser or program"], list(reversed(rows)))
    out = io.BytesIO()
    book.save(out)
    name = f"cip-logs-{m['since'][:10]}-to-{m['until'][:10]}.xlsx"
    return Response(out.getvalue(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})
