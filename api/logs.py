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
def logs(source: str = "api", q: str = Query("", max_length=200), lines: int = Query(500, ge=1, le=5000),
         who: dict = Depends(admin)) -> dict:
    sources = []
    for name, label in LABELS.items():
        path = None if name == "security" else path_of(name)
        sources.append({"id": name, "label": label, "bytes": path.stat().st_size if path and path.exists() else None})
    if source not in LABELS:
        raise HTTPException(404, "No such log")
    needle = q.strip().lower()
    if source == "security":
        found = security(lines, needle)
    else:
        path = path_of(source)
        found = tail(path, lines, needle) if path and path.exists() else []
    return {"sources": sources, "source": source, "lines": found}


@router.get("/logs/download")
def download(source: str, who: dict = Depends(admin)) -> FileResponse:
    path = None if source == "security" else path_of(source)
    if not path or not path.exists():
        raise HTTPException(404, "No such log file")
    return FileResponse(path, media_type="text/plain", filename=f"cip-{source}-{path.name}")


# ---- The monitoring dashboard (/app/logs, top): machine, traffic and health in one answer ----------------------------
# nginx's request log is read incrementally (only the lines written since the last call) into per-minute totals kept
# for a day, with server times in a 14-bucket histogram: a few KB per minute, whatever the traffic.
BOUNDS_MS = (0.5, 1, 2, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, float("inf"))
KEEP_MINUTES = 24 * 60
FIRST_READ = 64 * 2**20   # a fresh worker reads at most the newest 64 MB of the log


def page_of(path: str) -> str:
    """/api/v1/waves/532/crosstab?q=... -> /api/v1/waves/:id/crosstab; website files collapse to a few groups."""
    path = path.split("?", 1)[0]
    if path.startswith("/_next/"):
        return "/_next (website files)"
    return re.sub(r"/\d+(?=/|$)", "/:id", path)[:80]


class Traffic:
    def __init__(self):
        self.lock = threading.Lock()
        self.inode, self.offset, self.minutes = None, 0, {}

    def read(self, path: Path) -> None:
        with self.lock:
            try:
                info = path.stat()
            except OSError:
                return
            if info.st_ino != self.inode or info.st_size < self.offset:   # a new or rotated file: from its start
                self.inode, self.offset = info.st_ino, max(0, info.st_size - FIRST_READ) if self.inode is None else 0
            with path.open("rb") as f:
                f.seek(max(0, self.offset - 1))
                if self.offset and f.read(1) != b"\n":
                    f.readline()   # landed mid-line (a fresh worker's first read): skip to the next whole line
                for raw in f:
                    if not raw.endswith(b"\n"):
                        break   # nginx is still writing this line: the next call reads it
                    self.offset = f.tell()
                    self.add(raw)
            for old in sorted(self.minutes)[:-KEEP_MINUTES]:
                del self.minutes[old]

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
            m = self.minutes[minute] = {"requests": 0, "2xx": 0, "3xx": 0, "4xx": 0, "5xx": 0, "bytes": 0,
                                        "hit": 0, "file": 0, "api": 0, "times": [0] * len(BOUNDS_MS), "pages": Counter(),
                                        "slow": Counter(), "clients": Counter()}
        m["requests"] += 1
        m[f"{min(status // 100, 5)}xx" if status >= 200 else "2xx"] += 1
        m["bytes"] += int(entry.get("bytes") or 0)
        served = "hit" if entry.get("cache") == "HIT" else "file" if entry.get("api_seconds") in ("", "-", None) else "api"
        m[served] += 1
        m["times"][next(i for i, bound in enumerate(BOUNDS_MS) if ms <= bound)] += 1
        page = page_of(entry.get("path", ""))
        if len(m["pages"]) < 300 or page in m["pages"]:
            m["pages"][page] += 1
            m["slow"][page] = max(m["slow"][page], ms)
        if len(m["clients"]) < 300 or entry["client"] in m["clients"]:
            m["clients"][entry["client"]] += 1


TRAFFIC = Traffic()


def percentile(times: list[int], share: float) -> float:
    """The histogram bucket's upper bound under which `share` of the requests were answered (ms)."""
    total, seen = sum(times), 0
    for bound, count in zip(BOUNDS_MS, times):
        seen += count
        if total and seen >= share * total:
            return bound if bound != float("inf") else 10000.0
    return 0.0


def machine_series(since: str) -> list[dict]:
    path = LOGS / "machine.log"
    if not path.exists():
        return []
    out = []
    for line in reversed(tail(path, 6000, "")):
        try:
            sample = json.loads(line)
        except ValueError:
            continue
        if sample.get("time", "") >= since:
            out.append(sample)
    return out


@router.get("/metrics")
def metrics(minutes: int = Query(60, ge=5, le=KEEP_MINUTES), who: dict = Depends(admin)) -> dict:
    """Everything the dashboard draws, for the last `minutes`: the machine every 15 s, traffic per minute, the busiest
    pages and visitors, and the latest errors, restarts and ETL runs."""
    now = datetime.now(timezone.utc)
    since = (now - timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M")
    TRAFFIC.read(LOGS / FILES["nginx-access"])
    with TRAFFIC.lock:
        chosen = [(k, v) for k, v in sorted(TRAFFIC.minutes.items()) if k >= since]
        times = [sum(col) for col in zip(*(v["times"] for _, v in chosen))] or [0] * len(BOUNDS_MS)
        pages, slow, clients = Counter(), Counter(), Counter()
        for _, v in chosen:
            pages.update(v["pages"]); clients.update(v["clients"])
            for page, ms in v["slow"].items():
                slow[page] = max(slow[page], ms)
        traffic = [{"minute": k, **{f: v[f] for f in ("requests", "2xx", "3xx", "4xx", "5xx", "bytes", "hit", "file", "api")},
                    "p50_ms": percentile(v["times"], .5), "p95_ms": percentile(v["times"], .95),
                    "p99_ms": percentile(v["times"], .99)} for k, v in chosen]
    totals = {f: sum(t[f] for t in traffic) for f in ("requests", "2xx", "3xx", "4xx", "5xx", "bytes", "hit", "file", "api")}
    totals.update(p50_ms=percentile(times, .5), p95_ms=percentile(times, .95), p99_ms=percentile(times, .99),
                  under_1ms=round(100 * sum(times[:2]) / max(1, sum(times)), 1))
    problems = []
    for source, word in (("api", "error"), ("nginx-error", "[error]"), ("nginx-error", "[crit]"), ("etl", "error")):
        path = path_of(source)
        if path and path.exists():
            problems += [{"source": source, "line": line[:400]} for line in tail(path, 15, word)]
    return {"since": since, "now": now.isoformat(timespec="seconds"), "machine": machine_series(since),
            "traffic": traffic, "totals": totals,
            "histogram": [{"up_to_ms": b if b != float("inf") else None, "requests": c} for b, c in zip(BOUNDS_MS, times)],
            "pages": [{"page": p, "requests": n, "slowest_ms": round(slow[p], 1)} for p, n in pages.most_common(12)],
            "clients": [{"client": c, "requests": n} for c, n in clients.most_common(8)],
            "problems": sorted(problems, key=lambda e: e["line"][:24], reverse=True)[:20],
            "restarts": tail(path_of("container"), 10, "") if path_of("container").exists() else [],
            "etl": tail(path_of("etl"), 5, "") if path_of("etl").exists() else []}
