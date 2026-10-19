"""Copy the Qualtrics / SurveyMonkey source (dwh_stg.dwh_sm*) into cip_stg, so CIP no longer reads dwh_stg.

Since 14 Oct 2026 cip_stg read these seven tables through pass-through views. This replaces each view
with a real table holding the same rows: copied inside MySQL (nothing crosses the VPN), read at READ
COMMITTED (no locks on the other team's tables), and proven equal by COUNT(*) and CHECKSUM TABLE before
the view is replaced. dwh_stg is only read. The source has been frozen since 29 Aug 2025.

    python scripts/move_legacy_source.py          # report only
    python scripts/move_legacy_source.py --yes    # copy, verify, swap
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import text  # noqa: E402

from app.core.database import get_engine  # noqa: E402

TABLES = ["dwh_smsurveydetail", "dwh_smquestion", "dwh_smanswer", "dwh_smresponse", "dwh_smdemography",
          "dwh_smsurveytrend", "dwh_smresponseqa"]
CHUNK = 500_000                                   # rows per INSERT … SELECT on an integer key


def kind(conn, name: str):
    return conn.execute(text("SELECT table_type FROM information_schema.tables WHERE table_schema = 'cip_stg'"
                             " AND table_name = :t"), {"t": name}).scalar()


def same(conn, source: str, target: str) -> tuple[bool, str]:
    counts = [conn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar() for t in (source, target)]
    sums = [conn.execute(text(f"CHECKSUM TABLE {t}")).first()[1] for t in (source, target)]
    return counts[0] == counts[1] and sums[0] == sums[1], f"rows {counts[0]:,} / {counts[1]:,}, checksum {sums[0]} / {sums[1]}"


def copy(conn, name: str) -> None:
    source, target = f"dwh_stg.{name}", f"cip_stg.{name}_copy"
    conn.execute(text(f"DROP TABLE IF EXISTS {target}"))
    conn.execute(text(f"CREATE TABLE {target} LIKE {source}"))
    integer = conn.execute(text("SELECT data_type FROM information_schema.columns WHERE table_schema = 'dwh_stg'"
                                " AND table_name = :t AND column_name = 'id'"), {"t": name}).scalar() == "int"
    if not integer:
        conn.execute(text(f"INSERT INTO {target} SELECT * FROM {source}"))
        conn.commit()
        return
    low, high = conn.execute(text(f"SELECT MIN(id), MAX(id) FROM {source}")).one()
    for start in range(low or 0, (high or 0) + 1, CHUNK):
        conn.execute(text(f"INSERT INTO {target} SELECT * FROM {source} WHERE id >= :a AND id < :b"),
                     {"a": start, "b": start + CHUNK})
        conn.commit()


def main() -> int:
    go = "--yes" in sys.argv
    with get_engine("etl").connect() as conn:
        conn.execute(text("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED"))
        for name in TABLES:
            state = kind(conn, name)
            if state == "BASE TABLE":
                ok, detail = same(conn, f"dwh_stg.{name}", f"cip_stg.{name}")
                print(f"{name}: already a table in cip_stg — {'equal' if ok else 'DIFFERS'} ({detail})")
                continue
            print(f"{name}: {'view' if state == 'VIEW' else 'missing'} in cip_stg", end="")
            if not go:
                print(" — would copy")
                continue
            copy(conn, name)
            ok, detail = same(conn, f"dwh_stg.{name}", f"cip_stg.{name}_copy")
            if not ok:
                print(f" — copy DIFFERS ({detail}); view left in place")
                return 1
            if state == "VIEW":
                conn.execute(text(f"DROP VIEW cip_stg.{name}"))
            conn.execute(text(f"RENAME TABLE cip_stg.{name}_copy TO cip_stg.{name}"))
            conn.commit()
            print(f" — copied and swapped ({detail})")
        left = conn.execute(text("SELECT GROUP_CONCAT(table_name) FROM information_schema.views"
                                 " WHERE table_schema = 'cip_stg' AND view_definition LIKE '%dwh_stg%'")).scalar()
        print("cip_stg views still reading dwh_stg:", left or "none")
    return 0


if __name__ == "__main__":
    sys.exit(main())
