"""Operational logs for admins (/app/logs): everything the server writes, readable without a shell on the server.

  nginx-access   every request nginx answered (JSON lines: time, client, path, status, bytes, seconds, cache)
  nginx-error    nginx's warnings and errors
  api            the API's own log (startup, slow requests, errors)
  etl            the scheduled ETL runs (deploy/etl-loop.sh) and their errors
  publish        the publish at container start (restore from backup, or a full rebuild)
  container      the container's supervisor (deploy/start.sh): which process stopped and when
  platform       Azure App Service's own docker log (pulls, starts, restarts), when App Service logging is on
  security       sign-ins, sign-outs, denied and revoked access (cip_access_log), plus every 401/403/429 nginx answered

GET /api/v1/admin/logs?source=&q=&lines= gives the newest lines first; /api/v1/admin/logs/download?source= the file.
Only fixed files are read, never a path from the request. Admins only (api/signin.admin).
"""
from __future__ import annotations

import json
import os
from collections import deque
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import text

from api.signin import admin
from app.core.database import get_engine

LOGS = Path(os.environ.get("CIP_LOG_DIR") or Path(__file__).resolve().parents[1] / "logs")
PLATFORM = Path("/home/LogFiles")   # App Service writes its docker log here when "App Service logs: File System" is on
FILES = {"nginx-access": "nginx-access.log", "nginx-error": "nginx-error.log", "api": "api.log", "etl": "etl-loop.log",
         "etl-errors": "forsta-etl-errors.jsonl", "publish": "publish-start.log", "container": "container.log"}
LABELS = {"nginx-access": "nginx: every request", "nginx-error": "nginx: warnings and errors", "api": "API",
          "etl": "ETL runs", "etl-errors": "ETL errors", "publish": "Publish at start", "container": "Container supervisor",
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
