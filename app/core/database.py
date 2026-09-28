"""Pooled SQLAlchemy access to the STG (DWH) MySQL database."""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Generator, Iterable, Optional, Sequence

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from .config import config

logger = logging.getLogger(__name__)

_engines: dict[str, Engine] = {}
_sessions: dict[str, sessionmaker] = {}


def get_engine(role: str = "app") -> Engine:
    """One pooled engine per role. 'app' is read-only, 'etl' can write."""
    if role not in _engines:
        db = config.database(role)
        if not db.host or not db.database:
            raise RuntimeError(
                "Database is not configured. Set STG_DB_HOST / STG_DB_NAME "
                "(or APP_ENV=LOCAL) in your .env — see .env.example."
            )
        _engines[role] = create_engine(
            db.url,
            poolclass=QueuePool,
            pool_size=db.pool_size,
            max_overflow=db.max_overflow,
            pool_timeout=db.pool_timeout,
            pool_recycle=db.pool_recycle,
            pool_pre_ping=True,
            connect_args=db.connect_args,
            future=True,
        )
        logger.info("Created engine role=%s host=%s db=%s", role, db.host, db.database)
    return _engines[role]


def get_sessionmaker(role: str = "app") -> sessionmaker:
    if role not in _sessions:
        _sessions[role] = sessionmaker(bind=get_engine(role), expire_on_commit=False, future=True)
    return _sessions[role]


@contextmanager
def session_scope(role: str = "etl") -> Generator[Session, None, None]:
    session = get_sessionmaker(role)()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def query_df(sql: str, params: Optional[dict] = None, role: str = "app") -> pd.DataFrame:
    """Run a SELECT and return a DataFrame. The app's only read path."""
    with get_engine(role).connect() as conn:
        return pd.read_sql(text(sql), conn, params=params or {})


def execute(sql: str, params: Optional[dict] = None, role: str = "etl") -> int:
    with get_engine(role).begin() as conn:
        return conn.execute(text(sql), params or {}).rowcount


def execute_many(sql: str, rows: Sequence[dict], role: str = "etl", chunk: int = 1000) -> int:
    """Batched executemany — the workhorse for loading cip_response."""
    total = 0
    rows = list(rows)
    with get_engine(role).begin() as conn:
        for i in range(0, len(rows), chunk):
            batch = rows[i : i + chunk]
            conn.execute(text(sql), batch)
            total += len(batch)
    return total


def run_sql_file(path: str, role: str = "etl") -> None:
    """Execute a .sql migration file statement by statement."""
    import re

    raw = open(path, "r", encoding="utf-8").read()
    # strip full-line comments, then split on ';' at end of statement
    cleaned = "\n".join(l for l in raw.splitlines() if not l.strip().startswith("--"))
    statements = [s.strip() for s in re.split(r";\s*\n", cleaned) if s.strip()]
    with get_engine(role).begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))
    logger.info("Applied %s (%d statements)", path, len(statements))


def healthcheck(role: str = "app") -> tuple[bool, str]:
    try:
        with get_engine(role).connect() as conn:
            ver = conn.execute(text("SELECT VERSION()")).scalar()
        return True, f"connected (MySQL {ver})"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)
