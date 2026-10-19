"""Weekly backup of cip_stg: one consistent dump, proven complete, the last few kept.

    python scripts/backup_db.py

mysqldump --single-transaction (a snapshot, no locks) → backups/cip_stg-YYYYMMDD-HHMM.sql.gz. The file
counts only once it is proven: gzip intact, the "Dump completed" trailer, every table and view present,
and every table's row count equal to the live count just before or just after the dump. Keeps the newest
KEEP backups. With CIP_BACKUP_COPY_DIR set (e.g. a OneDrive folder), the proven file is also copied
there, so one copy lives off this Mac. Exit 0 = proven backup written; 1 = failed (and the failure list
is emailed). Restore: see docs/14-pipeline-validation-report.md §7.
"""
from __future__ import annotations

import gzip
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sqlalchemy import text  # noqa: E402

from app.core.config import config  # noqa: E402
from app.core.database import get_engine  # noqa: E402

log = logging.getLogger("cip.backup")
BACKUPS = ROOT / "backups"
KEEP = 4
MYSQLDUMP = shutil.which("mysqldump") or "/opt/homebrew/opt/mysql-client/bin/mysqldump"
INSERT = re.compile(rb"^INSERT INTO `([^`]+)` VALUES ")


def live() -> tuple[dict[str, int], int]:
    with get_engine("etl").connect() as conn:
        tables = [t for (t,) in conn.execute(text("SELECT table_name FROM information_schema.tables"
                                                  " WHERE table_schema = DATABASE() AND table_type = 'BASE TABLE'"))]
        views = conn.execute(text("SELECT COUNT(*) FROM information_schema.views WHERE table_schema = DATABASE()")).scalar()
        return {t: conn.execute(text(f"SELECT COUNT(*) FROM `{t}`")).scalar() for t in tables}, int(views)


def dump(target: Path) -> None:
    db = config.database("etl")
    fd, options = tempfile.mkstemp(suffix=".cnf")                 # 0600, deleted below: the password is never on a command line
    with os.fdopen(fd, "w") as f:
        f.write(f'[client]\nhost={db.host}\nport={db.port}\nuser={db.user}\npassword="{db.password}"\n'
                f"ssl-ca={ROOT / (db.ssl_ca or 'DigiCertGlobalRootG2.crt.pem')}\nssl-mode=VERIFY_CA\n")
    try:
        process = subprocess.Popen([MYSQLDUMP, f"--defaults-extra-file={options}", "--single-transaction", "--quick",
                                    "--no-tablespaces", "--set-gtid-purged=OFF", "--hex-blob",
                                    "--default-character-set=utf8mb4", db.database],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        with gzip.open(target, "wb", compresslevel=6) as out:
            shutil.copyfileobj(process.stdout, out, 1 << 20)
        error = process.stderr.read().decode(errors="replace")
        if process.wait() != 0:
            raise RuntimeError(f"mysqldump exit {process.returncode}: {error[:500]}")
    finally:
        os.remove(options)


def contents(path: Path) -> tuple[Counter, set, int, bool]:
    """(rows per table, tables, views, finished) — rows counted as top-level tuples, quotes honoured."""
    rows, tables, views, finished = Counter(), set(), 0, False
    with gzip.open(path, "rb") as f:
        for line in f:
            m = INSERT.match(line)
            if m:
                n = depth = 0
                quoted = escaped = False
                for b in line[m.end():]:
                    if quoted:
                        if escaped:
                            escaped = False
                        elif b == 92:
                            escaped = True
                        elif b == 39:
                            quoted = False
                    elif b == 39:
                        quoted = True
                    elif b == 40:
                        n += depth == 0
                        depth += 1
                    elif b == 41:
                        depth -= 1
                rows[m.group(1).decode()] += n
            elif line.startswith(b"CREATE TABLE `"):
                tables.add(line.split(b"`")[1].decode())
            elif line.startswith(b"/*!50001 VIEW `"):
                views += 1
            elif line.startswith(b"-- Dump completed"):
                finished = True
    return rows, tables, views, finished


def prove(path: Path, before: dict, after: dict, views: int) -> list[str]:
    rows, tables, dumped_views, finished = contents(path)
    problems = [] if finished else ["no 'Dump completed' trailer"]
    problems += [f"table {t} missing" for t in sorted(set(before) - tables)]
    problems += [f"{dumped_views} views dumped, {views} live"] if dumped_views != views else []
    problems += [f"{t}: dump {rows.get(t, 0):,}, live {before[t]:,} → {after.get(t, before[t]):,}"
                 for t in sorted(before) if rows.get(t, 0) not in (before[t], after.get(t, before[t]))]
    return problems


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s | %(message)s")
    BACKUPS.mkdir(exist_ok=True)
    final = BACKUPS / f"cip_stg-{datetime.now():%Y%m%d-%H%M}.sql.gz"
    part = final.with_name(final.name + ".part")
    try:
        before, views = live()
        dump(part)
        after, _ = live()
        problems = prove(part, before, after, views)
    except Exception as exc:
        problems = [f"{type(exc).__name__}: {exc}"]
    if problems:
        log.error("Backup not proven: %s", problems[:10])
        part.unlink(missing_ok=True)
        try:
            from etl import notify
            notify.failure("weekly backup", "\n".join(problems[:20]))
        except Exception:
            log.exception("Notification failed")
        return 1
    part.rename(final)
    log.info("Backup proven: %s (%.0f MB, %d tables, %s rows)", final.name, final.stat().st_size / 1e6, len(before),
             f"{sum(before.values()):,}")
    copy_dir = os.getenv("CIP_BACKUP_COPY_DIR", "").strip()
    if copy_dir:
        shutil.copy2(final, Path(copy_dir).expanduser() / final.name)
        log.info("Copied to %s", copy_dir)
    for old in sorted(BACKUPS.glob("cip_stg-*.sql.gz"))[:-KEEP]:
        old.unlink()
        log.info("Removed old backup %s", old.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
