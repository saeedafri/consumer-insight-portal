"""Run the MySQL schema and loaders on SQLite, from the same source files.

Why this exists: the STG warehouse sits behind a firewall and a VPN, so a
developer (or CI, or a laptop on a train) often cannot reach it. Rather than
keep a second hand-written schema that drifts from the real one, this module
converts `sql/001_schema.sql` on the fly. MySQL stays the single source of
truth; SQLite is a derived, disposable copy.

Scope is deliberately narrow — the dialect differences this codebase actually
uses, nothing more:

    ENGINE=/CHARSET=/COLLATE= table options   dropped
    COMMENT '...'                             dropped
    ENUM(...)                                 TEXT
    INT UNSIGNED                              INTEGER
    AUTO_INCREMENT                            INTEGER PRIMARY KEY AUTOINCREMENT
    ON UPDATE CURRENT_TIMESTAMP               dropped
    inline KEY (...) lines                    separate CREATE INDEX
    CREATE OR REPLACE VIEW                    DROP VIEW + CREATE VIEW
    ON DUPLICATE KEY UPDATE x = VALUES(x)     ON CONFLICT DO UPDATE SET x = excluded.x
    LAST_INSERT_ID()                          last_insert_rowid()
    CREATE USER / GRANT / FLUSH               skipped
"""
from __future__ import annotations

import re
from typing import Optional

_COMMENT = re.compile(r"\s+COMMENT\s+('(?:[^']|'')*'|\"(?:[^\"]|\"\")*\")", re.I)
_TABLE_OPTS = re.compile(r"\)\s*ENGINE=\w+.*?$", re.I | re.S)
_ENUM = re.compile(r"\bENUM\s*\([^)]*\)", re.I)
_UNSIGNED = re.compile(r"\b(BIGINT|INT|SMALLINT|TINYINT|MEDIUMINT)\s+UNSIGNED\b", re.I)
_AUTOINC = re.compile(r"\bAUTO_INCREMENT\b", re.I)
_ON_UPDATE_TS = re.compile(r"\s+ON UPDATE CURRENT_TIMESTAMP\b", re.I)
_CHARSET = re.compile(r"\s+(DEFAULT\s+)?CHARSET=\S+|\s+COLLATE=\S+", re.I)
_KEY_LINE = re.compile(r"^\s*(UNIQUE\s+)?KEY\s+\w+\s*\([^)]*\),?\s*$", re.I | re.M)
_TINYINT_LEN = re.compile(r"\bTINYINT\(\d+\)", re.I)
_ADMIN = re.compile(r"^\s*(CREATE\s+USER|GRANT|FLUSH|SET\s+NAMES)\b", re.I)


def split_statements(sql: str) -> list[str]:
    """Split a .sql file into statements, dropping full-line comments."""
    cleaned = "\n".join(l for l in sql.splitlines() if not l.strip().startswith("--"))
    return [s.strip() for s in re.split(r";\s*(?:\n|$)", cleaned) if s.strip()]


_INSERT_TABLE = re.compile(r"\bINSERT\s+(?:OR\s+\w+\s+|IGNORE\s+)?INTO\s+`?(\w+)`?", re.I)


def conflict_targets(schema_sql: str) -> dict[str, str]:
    """Map table -> the column list SQLite needs as an ON CONFLICT target.

    MySQL infers the conflicting key; SQLite makes you name it. The targets are
    read straight out of the same DDL file, so adding a UNIQUE KEY in MySQL
    keeps the two in step with no second place to edit.
    """
    targets: dict[str, str] = {}
    for table_match in re.finditer(r"CREATE TABLE IF NOT EXISTS (\w+)\s*\((.*?)\n\)", schema_sql, re.S):
        table, body = table_match.group(1), table_match.group(2)
        uq = re.search(r"^\s*UNIQUE KEY\s+\w+\s*\(([^)]*)\)", body, re.I | re.M)
        if uq:
            targets[table] = ", ".join(c.strip().strip("`") for c in uq.group(1).split(","))
            continue
        pk = re.search(r"^\s*PRIMARY KEY\s*\(([^)]*)\)", body, re.I | re.M)
        if pk:
            targets[table] = ", ".join(c.strip().strip("`") for c in pk.group(1).split(","))
    return targets


def rewrite_dml(sql: str, targets: Optional[dict[str, str]] = None) -> str:
    """Make a loader's INSERT ... ON DUPLICATE KEY UPDATE work on SQLite."""
    out = sql
    m = re.search(r"\bON DUPLICATE KEY UPDATE\b(.*)$", out, re.I | re.S)
    if m:
        assignments = m.group(1)
        assignments = re.sub(r"VALUES\s*\(\s*(\w+)\s*\)", r"excluded.\1", assignments, flags=re.I)
        # a self-assignment used only to make LAST_INSERT_ID() return the id
        assignments = re.sub(r",?\s*\w+\s*=\s*LAST_INSERT_ID\(\s*\w+\s*\)", "", assignments, flags=re.I)
        assignments = assignments.strip().rstrip(",")
        head = out[: m.start()]
        table = _INSERT_TABLE.search(head)
        target = (targets or {}).get(table.group(1)) if table else None
        clause = f"ON CONFLICT ({target})" if target else "ON CONFLICT"
        out = f"{head} {clause} DO UPDATE SET {assignments}" if assignments \
              else f"{head} {clause} DO NOTHING"
    out = re.sub(r"\bINSERT\s+IGNORE\s+INTO\b", "INSERT OR IGNORE INTO", out, flags=re.I)
    out = re.sub(r"\bLAST_INSERT_ID\(\s*\)", "last_insert_rowid()", out, flags=re.I)
    out = re.sub(r"\bREGEXP_SUBSTR\s*\(([^,]+),\s*'\[0-9\]\+'\)", r"\1", out, flags=re.I)
    out = re.sub(r"\bNOW\(\s*\)", "CURRENT_TIMESTAMP", out, flags=re.I)
    out = re.sub(r"\bUTC_TIMESTAMP\(\s*\)", "CURRENT_TIMESTAMP", out, flags=re.I)
    out = re.sub(r"\bIFNULL\b", "COALESCE", out, flags=re.I)
    return out


def convert_ddl(stmt: str) -> list[str]:
    """Convert one MySQL statement into zero or more SQLite statements."""
    s = stmt
    if _ADMIN.match(s):
        return []

    view = re.match(r"^\s*CREATE\s+OR\s+REPLACE\s+VIEW\s+(\w+)\s+AS\s+(.*)$", s, re.I | re.S)
    if view:
        return [f"DROP VIEW IF EXISTS {view.group(1)}",
                f"CREATE VIEW {view.group(1)} AS {view.group(2)}"]

    if re.search(r"ON DUPLICATE KEY UPDATE", s, re.I):
        s = re.split(r"\s+ON DUPLICATE KEY UPDATE", s, flags=re.I)[0]
        s = re.sub(r"^\s*INSERT\s+INTO", "INSERT OR REPLACE INTO", s, flags=re.I)

    s = _COMMENT.sub("", s)
    s = _TABLE_OPTS.sub(")", s)
    s = _CHARSET.sub("", s)
    s = _ENUM.sub("TEXT", s)
    s = _UNSIGNED.sub(r"\1", s)
    s = _TINYINT_LEN.sub("TINYINT", s)
    s = _ON_UPDATE_TS.sub("", s)
    s = _KEY_LINE.sub("", s)

    if _AUTOINC.search(s):
        pk = re.search(r"PRIMARY KEY \((\w+)\)", s)
        s = _AUTOINC.sub("", s)
        if pk:
            col = pk.group(1)
            s = re.sub(rf"^(\s*){col}\s+\w+(\(\d+\))?\s+NOT NULL\s*,",
                       rf"\1{col} INTEGER PRIMARY KEY AUTOINCREMENT,", s, count=1, flags=re.M)
            s = re.sub(r",?\s*PRIMARY KEY \(" + col + r"\)", "", s, count=1)

    s = re.sub(r",(\s*,)+", ",", s)
    s = re.sub(r",\s*\)", ")", s)
    s = re.sub(r"\n\s*\n", "\n", s)
    return [s.strip()]


def index_statements(sql: str) -> list[str]:
    """MySQL declares plain indexes inline; SQLite needs CREATE INDEX."""
    out: list[str] = []
    for table_match in re.finditer(r"CREATE TABLE IF NOT EXISTS (\w+)\s*\((.*?)\n\)", sql, re.S):
        table, body = table_match.group(1), table_match.group(2)
        for key in re.finditer(r"^\s*(UNIQUE\s+)?KEY\s+(\w+)\s*\(([^)]*)\)", body, re.I | re.M):
            unique = "UNIQUE " if key.group(1) else ""
            out.append(
                f"CREATE {unique}INDEX IF NOT EXISTS {key.group(2)} "
                f"ON {table} ({key.group(3)})"
            )
    return out
