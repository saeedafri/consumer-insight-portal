"""The Logs page's raw logs (/app/logs, bottom), for admins: every file the server writes, readable without a shell.

  nginx-access   every request nginx answered (JSON lines: time, client, path, status, bytes, seconds, cache, user)
  nginx-error    nginx's warnings and errors
  api            the API's own log (startup, slow requests, errors)
  etl            the scheduled ETL runs (deploy/etl-loop.sh) and their errors
  publish        the publish at container start (restore from backup, or a full rebuild)
  container      the container's supervisor (deploy/start.sh): which process stopped and when
  platform       Azure App Service's own docker log (pulls, starts, restarts), when App Service logging is on
  machine        CPU, memory, bandwidth and memory per process every 15 s (deploy/machine-log.sh)
  security       sign-ins, sign-outs, denied and revoked access (cip_access_log), plus every 401/403/429 nginx answered

GET /api/v1/admin/logs?source=&q=&lines=&page= gives one page of a log, newest first; /api/v1/admin/logs/download?source=
the whole file. Only these fixed files are read, never a path from the request. Admins only (api/signin.admin).
The dashboard above the logs is api/metrics.py; it reads the same files through path_of() and tail() below.
"""
from __future__ import annotations

import json
import os
import re
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import text

from api.signin import admin
from shared.core.database import get_engine

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


@router.get("/logs/archives")
def archives(who: dict = Depends(admin)) -> list[dict]:
    """Every packed log (deploy/archive-log.py writes one .zip each time a log passes 20 MB; none is ever deleted),
    newest first: [{name, bytes, time}]."""
    folder = LOGS / "archive"
    found = sorted(folder.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True) if folder.is_dir() else []
    return [{"name": p.name, "bytes": p.stat().st_size,
             "time": datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")} for p in found]


@router.get("/logs/archive")
def archive(name: str = Query(..., max_length=120), who: dict = Depends(admin)) -> FileResponse:
    """One packed log, by its exact name from archives(): never a path from the request."""
    path = LOGS / "archive" / name
    if not re.fullmatch(r"[\w.-]+\.zip", name) or not path.is_file():
        raise HTTPException(404, "No such archive")
    return FileResponse(path, media_type="application/zip", filename=name)


@router.get("/logs/download")
def download(source: str, who: dict = Depends(admin)) -> FileResponse:
    path = None if source == "security" else path_of(source)
    if not path or not path.exists():
        raise HTTPException(404, "No such log file")
    return FileResponse(path, media_type="text/plain", filename=f"cip-{source}-{path.name}")


@router.get("/logs/context")
def context(source: str, line: str = Query(..., max_length=2000), who: dict = Depends(admin)) -> dict:
    """A logged line with the 10 before and 40 after it (an error's traceback, the request before it), from the newest
    4 MB of its log: what the Logs page's "Show" opens, so a problem is read where it happened."""
    path = path_of(source)
    if not path or not path.exists():
        raise HTTPException(404, "No such log")
    with path.open("rb") as f:
        f.seek(max(0, f.seek(0, os.SEEK_END) - TAIL_BYTES))
        lines = [raw.decode("utf-8", errors="replace").rstrip("\n") for raw in f]
    at = max((i for i, text in enumerate(lines) if text.startswith(line[:300])), default=None)
    if at is None:
        raise HTTPException(404, "That line is no longer in the newest part of the log: see Older logs")
    return {"source": source, "file": str(path), "line": at, "before": lines[max(0, at - 10):at], "found": lines[at],
            "after": lines[at + 1:at + 41]}
