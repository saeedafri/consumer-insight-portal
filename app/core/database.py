"""Pooled SQLAlchemy access to the STG (DWH) MySQL database."""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Generator, Iterable, Optional, Sequence

import pandas as pd
from functools import lru_cache
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from . import sqlite_compat
from .config import config

logger = logging.getLogger(__name__)

_engines: dict[str, Engine] = {}
_sessions: dict[str, sessionmaker] = {}


def dialect(role: str = "app") -> str:
    """'mysql' for STG, 'sqlite' for a local file database."""
    return get_engine(role).dialect.name


_SCHEMA_SQL = Path(__file__).resolve().parents[2] / "sql" / "001_schema.sql"


@lru_cache(maxsize=1)
def _conflict_targets() -> dict:
    try:
        return sqlite_compat.conflict_targets(_SCHEMA_SQL.read_text(encoding="utf-8"))
    except OSError:
        return {}


def _install_sqlite_translation(engine: Engine) -> None:
    """Translate MySQL DML to SQLite at the driver boundary.

    Every query in this codebase is written once, in MySQL, against the STG
    warehouse. Rather than fork the loaders for local development, the
    translation happens here — one place, applied to whatever SQL reaches the
    cursor, including raw text() the loaders build themselves.
    """
    targets = _conflict_targets()

    @event.listens_for(engine, "before_cursor_execute", retval=True)
    def _translate(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        return sqlite_compat.rewrite_dml(statement, targets), parameters


def _portable(sql: str, role: str) -> str:
    """Kept for callers that want the translated text up front."""
    return sqlite_compat.rewrite_dml(sql, _conflict_targets()) \
        if dialect(role) == "sqlite" else sql


def get_engine(role: str = "app") -> Engine:
    """One pooled engine per role. 'app' is read-only, 'etl' can write."""
    if role not in _engines:
        db = config.database(role)
        if db.url.startswith("sqlite"):
            engine = create_engine(db.url, future=True)
            _engines[role] = engine
            _install_sqlite_translation(engine)
            with engine.connect() as conn:
                conn.execute(text("PRAGMA foreign_keys=ON"))
            logger.info("Created SQLite engine role=%s path=%s", role, db.database)
            return engine
        if not db.host or not db.database:
            raise RuntimeError(
                "Database is not configured. Set STG_DB_HOST / STG_DB_NAME "
                "(or APP_ENV=LOCAL) in your .env — see .env.example."
            )
        # The read role runs in AUTOCOMMIT with no pre-ping: each query is then
        # ONE round trip instead of three (SELECT 1 + query + rollback) — about
        # 500 ms saved per read from the India office. pool_recycle retires
        # connections before Azure drops them. Writers keep transactions.
        reads_only = role == "app"
        _engines[role] = create_engine(
            db.url,
            poolclass=QueuePool,
            pool_size=db.pool_size,
            max_overflow=db.max_overflow,
            pool_timeout=db.pool_timeout,
            pool_recycle=db.pool_recycle,
            pool_pre_ping=not reads_only,
            connect_args=db.connect_args,
            future=True,
            **({"isolation_level": "AUTOCOMMIT", "skip_autocommit_rollback": True} if reads_only else {}),
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
        return conn.execute(text(_portable(sql, role)), params or {}).rowcount


def execute_many(sql: str, rows: Sequence[dict], role: str = "etl", chunk: int = 1000) -> int:
    """Batched executemany — the workhorse for loading cip_answer."""
    total = 0
    rows = list(rows)
    statement = text(_portable(sql, role))
    with get_engine(role).begin() as conn:
        for i in range(0, len(rows), chunk):
            batch = rows[i : i + chunk]
            conn.execute(statement, batch)
            total += len(batch)
    return total


def apply_sql(path, engine: Engine) -> int:
    """Apply one .sql file to `engine`. On SQLite the MySQL DDL is converted on
    the fly (see sqlite_compat) so there is only one schema file to maintain."""
    raw = Path(path).read_text(encoding="utf-8")
    statements = sqlite_compat.split_statements(raw)
    is_sqlite = engine.dialect.name == "sqlite"

    applied = 0
    with engine.begin() as conn:
        for stmt in statements:
            for out in (sqlite_compat.convert_ddl(stmt) if is_sqlite else [stmt]):
                if not out:
                    continue
                conn.execute(text(out))
                applied += 1
        if is_sqlite:
            for idx in sqlite_compat.index_statements(raw):
                conn.execute(text(idx))
                applied += 1
    logger.info("Applied %s (%d statements, dialect=%s)",
                path, applied, "sqlite" if is_sqlite else "mysql")
    return applied


def run_sql_file(path: str, role: str = "etl") -> None:
    """Apply a .sql migration with the engine for `role`."""
    apply_sql(path, get_engine(role))


def healthcheck(role: str = "app") -> tuple[bool, str]:
    try:
        engine = get_engine(role)
        if engine.dialect.name == "sqlite":
            import sqlite3

            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True, f"connected (local SQLite {sqlite3.sqlite_version})"
        with engine.connect() as conn:
            ver = conn.execute(text("SELECT VERSION()")).scalar()
        return True, f"connected (MySQL {ver})"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)
