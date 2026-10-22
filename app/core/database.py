"""Pooled SQLAlchemy access to the STG (DWH) MySQL database."""
from __future__ import annotations

import logging
import re
import tempfile
from typing import TYPE_CHECKING, Any, Iterable, Optional, Sequence

if TYPE_CHECKING:
    import pandas as pd
from functools import lru_cache
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.engine import Engine
from sqlalchemy.pool import QueuePool

from . import sqlite_compat
from .config import config

logger = logging.getLogger(__name__)

# seconds a single statement may wait for MySQL before failing instead of hanging. The read role also serves the
# publish and dashboard builds (a family-wide query takes minutes under load); screens are capped by gunicorn's 30 s.
READ_TIMEOUT = {"app": 600, "etl": 1800}

_engines: dict[str, Engine] = {}


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
            logger.info("Created SQLite engine role=%s path=%s ", role, db.database)
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
        # The writer bulk-loads answers with LOAD DATA LOCAL INFILE (etl/forsta_etl.py).
        connect_args = db.connect_args if reads_only else {**db.connect_args, "local_infile": True}
        if db.url.startswith("mysql"):   # a hung query fails instead of blocking the run (and the launchd slots after it)
            connect_args = {**connect_args, "connect_timeout": 20, "read_timeout": READ_TIMEOUT.get(role, 1800), "write_timeout": READ_TIMEOUT.get(role, 1800)}
            if reads_only:   # the socket timeout only abandons a slow SELECT: this makes the server stop it (SELECTs only, in ms)
                connect_args["init_command"] = f"SET SESSION max_execution_time={READ_TIMEOUT[role] * 1000}"
        _engines[role] = create_engine(
            db.url,
            poolclass=QueuePool,
            pool_size=db.pool_size,
            max_overflow=db.max_overflow,
            pool_timeout=db.pool_timeout,
            pool_recycle=db.pool_recycle,
            pool_pre_ping=not reads_only,
            connect_args=connect_args,
            future=True,
            **({"isolation_level": "AUTOCOMMIT", "skip_autocommit_rollback": True} if reads_only else {}),
        )
        logger.info("Created engine role=%s host=%s db=%s", role, db.host, db.database)
    return _engines[role]


def query_df(sql: str, params: Optional[dict] = None, role: str = "app") -> pd.DataFrame:
    """Run a SELECT and return a DataFrame. The app's only read path."""
    import pandas as pd   # only the staff pages use DataFrames; the API never loads pandas (≈60 MB per worker)
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


_UNESCAPED = {"t": "\t", "n": "\n", "r": "\r", "0": "\0", "\\": "\\"}


def tsv(value: Any) -> str:
    """One LOAD DATA field: NULL as \\N, the escape characters escaped."""
    if value is None:
        return r"\N"
    return (str(value).replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n")
            .replace("\r", "\\r").replace("\0", "\\0"))


def untsv(value: str) -> Optional[str]:
    """tsv() reversed in one pass, so an escaped backslash next to a t or n is never misread."""
    return None if value == r"\N" else re.sub(r"\\(.)", lambda m: _UNESCAPED.get(m.group(1), m.group(1)), value)


def bulk_insert(conn, table: str, columns: Sequence[str], rows: Iterable[Sequence]) -> None:
    """Rows into a table in the caller's transaction. On MySQL one LOAD DATA LOCAL INFILE: a compact upload instead
    of thousands of INSERT values (from India the link, not the server, is the cost: 13 k serving rows took 18 s as
    INSERTs). A row the server warns about fails the load (the transaction rolls back), never a silently changed
    value. Batched INSERTs on SQLite, or when the server refuses LOCAL INFILE (re-read from the same file)."""
    marks = ", ".join(f":c{i}" for i in range(len(columns)))
    statement = text(f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({marks})")

    def batched(source):
        batch = []
        for row in source:
            batch.append({f"c{i}": v for i, v in enumerate(row)})
            if len(batch) == 5000:
                conn.execute(statement, batch)
                batch = []
        if batch:
            conn.execute(statement, batch)
    if conn.dialect.name != "mysql":
        return batched(rows)
    with tempfile.NamedTemporaryFile("w", suffix=".tsv", encoding="utf-8", newline="\n", delete=False) as f:
        path = Path(f.name)
        for row in rows:
            f.write("\t".join(tsv(v) for v in row) + "\n")
    try:
        try:
            conn.exec_driver_sql(
                f"LOAD DATA LOCAL INFILE '{path.as_posix()}' INTO TABLE {table} CHARACTER SET utf8mb4"
                f" FIELDS TERMINATED BY '\\t' ESCAPED BY '\\\\' LINES TERMINATED BY '\\n' ({', '.join(columns)})")
        except OperationalError as exc:
            if getattr(exc.orig, "args", [None])[0] not in (1148, 2068, 3948):   # anything but "LOCAL INFILE is off"
                raise
            logger.warning("LOAD DATA refused (%s); using batched INSERTs", exc.orig)
            with path.open(encoding="utf-8") as lines:
                return batched([untsv(v) for v in line.rstrip("\n").split("\t")] for line in lines)
        warned = conn.exec_driver_sql("SHOW WARNINGS LIMIT 5").all()
        if warned:
            raise RuntimeError(f"LOAD DATA into {table} warned {warned}: nothing is kept")
    finally:
        path.unlink(missing_ok=True)


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
