"""Who did what in the portal (sql/008_access.sql, cip_access_log): sign-in, sign-out, exports, Ask CIP questions and
team writes. record() only queues the row; one background thread writes the queue in batches, so a request never
waits on the database for its audit line. A failed write is logged and dropped, never retried into a backlog."""
from __future__ import annotations

import json
import logging
import queue
import threading
import time

from sqlalchemy import text

from app.core.database import get_engine
from app.core.session import sign

log = logging.getLogger("cip.audit")
PENDING: queue.Queue = queue.Queue(maxsize=10_000)
COLUMNS = ("email", "client", "role", "action", "survey_id", "target", "detail", "ip_hash", "user_agent")


def address(request) -> str:
    """The caller's address behind Cloudflare or nginx: the first forwarded hop, else the socket's."""
    headers, client = getattr(request, "headers", {}), getattr(request, "client", None)
    forwarded = headers.get("cf-connecting-ip") or headers.get("x-forwarded-for", "").split(",")[0].strip()
    return forwarded or (client.host if client else "")


def record(request, action: str, who: dict | None = None, survey_id: int | None = None, target: str | None = None,
           detail: dict | None = None) -> None:
    who = who or getattr(request.state, "person", None) or {"email": getattr(request.state, "email", "unknown")}
    ip = address(request)
    row = {"email": who.get("email", "unknown")[:255], "client": who.get("client"), "role": who.get("role", "")[:20],
           "action": action[:40], "survey_id": survey_id, "target": None if target is None else str(target)[:300],
           "detail": json.dumps(detail, default=str)[:20_000] if detail else None,
           "ip_hash": sign(ip)[:22] if ip else None, "user_agent": getattr(request, "headers", {}).get("user-agent", "")[:120] or None}
    try:
        PENDING.put_nowait(row)
    except queue.Full:
        log.warning("Audit queue full: dropped %s by %s", action, row["email"])


def write_pending(rows: list | None = None) -> int:
    rows = rows or []
    while True:
        try:
            rows.append(PENDING.get_nowait())
        except queue.Empty:
            break
    if not rows:
        return 0
    try:
        with get_engine("app").begin() as conn:
            conn.execute(text(f"INSERT INTO cip_access_log ({', '.join(COLUMNS)}) VALUES ({', '.join(':' + c for c in COLUMNS)})"), rows)
    except Exception as exc:   # noqa: BLE001 — the audit never takes the portal down
        log.warning("Audit write failed, %d rows dropped: %s", len(rows), type(exc).__name__)
        return 0
    return len(rows)


def start() -> None:
    """The writer: wakes on the first queued row, waits a second for more, then writes them all in one INSERT."""
    def run():
        while True:
            first = PENDING.get()
            time.sleep(1)
            write_pending([first])
    threading.Thread(target=run, name="cip-audit", daemon=True).start()
