"""Write the data dictionary of every cip_ table and view from the live
database: columns, types, keys, comments, indexes, foreign keys, row counts.

    python scripts/data_dictionary.py > docs/technical/06-data-dictionary.md
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.core.database import get_engine  # noqa: E402


def main() -> int:
    with get_engine("etl").connect() as conn:
        tables = conn.execute(text(
            "SELECT table_name, table_type, table_rows, table_comment FROM information_schema.tables"
            " WHERE table_schema = DATABASE() AND (table_name LIKE 'cip\\_%' OR table_name LIKE 'v\\_cip\\_%') ORDER BY table_type, table_name")).all()
        columns = conn.execute(text(
            "SELECT table_name, column_name, column_type, is_nullable, column_key, column_default, column_comment"
            " FROM information_schema.columns WHERE table_schema = DATABASE() AND (table_name LIKE 'cip\\_%' OR table_name LIKE 'v\\_cip\\_%')"
            " ORDER BY table_name, ordinal_position")).all()
        indexes = conn.execute(text(
            "SELECT table_name, index_name, non_unique, index_type,"
            " GROUP_CONCAT(column_name ORDER BY seq_in_index SEPARATOR ', ')"
            " FROM information_schema.statistics WHERE table_schema = DATABASE() AND (table_name LIKE 'cip\\_%' OR table_name LIKE 'v\\_cip\\_%')"
            " GROUP BY table_name, index_name, non_unique, index_type ORDER BY table_name, index_name")).all()
        fks = conn.execute(text(
            "SELECT k.table_name, k.column_name, k.referenced_table_name, k.referenced_column_name, r.delete_rule"
            " FROM information_schema.key_column_usage k JOIN information_schema.referential_constraints r"
            " ON r.constraint_schema = k.constraint_schema AND r.constraint_name = k.constraint_name"
            " WHERE k.table_schema = DATABASE() AND k.table_name LIKE 'cip\\_%'")).all()
    cols, idx, refs = {}, {}, {}
    for r in columns:
        cols.setdefault(r[0], []).append(r[1:])
    for r in indexes:
        idx.setdefault(r[0], []).append(r[1:])
    for r in fks:
        refs.setdefault((r[0], r[1]), f"→ {r[2]}.{r[3]} ({r[4].lower()})")
    out = ["# 6. Data dictionary — `cip_` tables and views in `cip_stg`", "",
           "Generated from the live database by `scripts/data_dictionary.py`; row counts are InnoDB estimates.", "",
           "| Object | Kind | Rows (approx.) | Purpose |", "|---|---|---:|---|"]
    for name, kind, rows, comment in tables:
        out.append(f"| [`{name}`](#{name.replace('_', '-')}) | {'view' if kind == 'VIEW' else 'table'} | "
                   f"{'' if rows is None else f'{rows:,}'} | {comment or ''} |")
    for name, kind, rows, comment in tables:
        out += ["", f"## {name}", "", f"*{'View' if kind == 'VIEW' else 'Table'}*" + (f" — {comment}" if comment else ""), "",
                "| Column | Type | Null | Key | Default | Meaning |", "|---|---|---|---|---|---|"]
        for col, ctype, null, key, default, ccomment in cols.get(name, []):
            meaning = " ".join(x for x in (ccomment or "", refs.get((name, col), "")) if x)
            out.append(f"| `{col}` | {ctype} | {null} | {key} | {'' if default is None else default} | {meaning} |")
        if idx.get(name):
            out += ["", "Indexes: " + "; ".join(
                f"`{i}` ({'unique ' if not nu and i != 'PRIMARY' else ''}{t.lower()}: {c})" for i, nu, t, c in idx[name])]
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
