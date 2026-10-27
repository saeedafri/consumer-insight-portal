"""Owner-approved read-only parity canary for survey 238.

This is deliberately not a publisher entrypoint. It loads the base-HEAD and
working-tree payload builders, runs them sequentially through one guarded
staging connection, writes only to a TemporaryDirectory, compares exact
payloads and canonical hashes, then removes the temporary output.
"""
from __future__ import annotations

import gc
import gzip
import hashlib
import importlib.util
import json
import os
import resource
import subprocess
import sys
import tempfile
import time
import tracemalloc
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

BASE_HEAD = "6f978b0595b2c71c064991ae10b832514637a0da"
SURVEY_ID = 238
EXPECTED_DATABASE = "cip_stg"
EXPECTED_SERVER_HOST_HASH = "sha256:3c3485f00d05"
EXPECTED_ACCOUNT_HASH = "sha256:2837eb29d5ae"
MAX_THREADS_RUNNING = 8
OUTPUT_PATH = REPO_ROOT / (
    "docs/performance/cip_staging_verification/evidence/"
    "FINAL_SURVEY_238_CANARY_RESULTS.json"
)

IDENTITY_SQL = """SELECT VERSION() AS server_version,
       DATABASE() AS current_database,
       CURRENT_USER() AS authenticated_account,
       @@hostname AS server_hostname,
       @@port AS server_port,
       CONNECTION_ID() AS inspection_connection_id,
       @@session.autocommit AS session_autocommit,
       @@session.transaction_read_only AS transaction_read_only,
       @@session.max_execution_time AS max_execution_time_ms,
       @@session.lock_wait_timeout AS metadata_lock_wait_seconds,
       @@session.innodb_lock_wait_timeout AS row_lock_wait_seconds"""
GUARD_SQL = """SELECT @@session.autocommit AS session_autocommit,
       @@session.transaction_read_only AS transaction_read_only,
       @@session.max_execution_time AS max_execution_time_ms,
       @@session.lock_wait_timeout AS metadata_lock_wait_seconds,
       @@session.innodb_lock_wait_timeout AS row_lock_wait_seconds"""
LOCK_SQL = "SELECT IS_USED_LOCK('cip_etl') AS cip_etl_owner_connection_id"
PRESSURE_SQL = "SHOW GLOBAL STATUS WHERE Variable_name = 'Threads_running'"
STATE_SQL = """SELECT w.rows_built, w.built_at,
       (SELECT COUNT(*) FROM srv_answer a WHERE a.survey_id = :s) AS answer_rows,
       (SELECT COUNT(DISTINCT a.respondent_id) FROM srv_answer a WHERE a.survey_id = :s) AS respondents,
       (SELECT COUNT(*) FROM srv_result r WHERE r.survey_id = :s) AS result_rows
FROM srv_wave w WHERE w.survey_id = :s"""


def _sanitise_integration_environment() -> None:
    for name in (
        "EMAIL_HOST", "EMAIL_PORT", "EMAIL_USERNAME", "EMAIL_PASSWORD",
        "SMTP_HOST", "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD",
        "SENDGRID_API_KEY", "MAILGUN_API_KEY", "RESEND_API_KEY",
        "TEAMS_WEBHOOK_URL", "SLACK_WEBHOOK_URL", "WEBHOOK_URL",
        "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY", "FORSTA_API_KEY", "ANTHROPIC_API_KEY",
        "CIP_PUBLISH_BACKUP_URL", "CIP_NGINX_URL", "CIP_NGINX_CACHE",
    ):
        os.environ[name] = ""


def _hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(str(value).encode()).hexdigest()[:12]


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        default=_json_default,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _row_dict(result) -> dict[str, Any]:
    row = result.mappings().one()
    return dict(row)


def _validate_identity(row: dict[str, Any]) -> dict[str, Any]:
    if row["current_database"] != EXPECTED_DATABASE:
        raise RuntimeError("unexpected database")
    if "azure" not in str(row["server_version"]).lower():
        raise RuntimeError("unexpected server product")
    if _hash(row["server_hostname"]) != EXPECTED_SERVER_HOST_HASH:
        raise RuntimeError("server identity differs from prior approved stages")
    if _hash(row["authenticated_account"]) != EXPECTED_ACCOUNT_HASH:
        raise RuntimeError("account identity differs from prior approved stages")
    if int(row["server_port"]) != 3306 or int(row["session_autocommit"]) != 1:
        raise RuntimeError("unexpected port or autocommit state")
    return {
        "server_version": row["server_version"],
        "current_database": row["current_database"],
        "server_hostname": EXPECTED_SERVER_HOST_HASH,
        "authenticated_account": EXPECTED_ACCOUNT_HASH,
        "inspection_connection_id": _hash(row["inspection_connection_id"]),
        "session_autocommit": int(row["session_autocommit"]),
    }


def _validate_guards(row: dict[str, Any]) -> dict[str, int]:
    names = (
        "session_autocommit",
        "transaction_read_only",
        "max_execution_time_ms",
        "metadata_lock_wait_seconds",
        "row_lock_wait_seconds",
    )
    actual = {name: int(row[name]) for name in names}
    if tuple(actual.values()) != (1, 1, 5000, 3, 3):
        raise RuntimeError(f"session guard mismatch: {tuple(actual.values())}")
    return actual


class GuardedConnection:
    """Only SELECTs, with lock and pressure gates before each application read."""

    def __init__(self, connection) -> None:
        self.connection = connection
        self.phase = "preflight"
        self.query_log: list[dict[str, Any]] = []
        self.monitoring_checks = 0
        self.max_threads_running = 0

    def _monitor(self) -> None:
        lock = self.connection.exec_driver_sql(LOCK_SQL).scalar_one()
        self.monitoring_checks += 1
        if lock is not None:
            raise RuntimeError("cip_etl lock is held")
        pressure = self.connection.exec_driver_sql(PRESSURE_SQL).mappings().one()
        self.monitoring_checks += 1
        threads = int(pressure["Value"])
        self.max_threads_running = max(self.max_threads_running, threads)
        if threads > MAX_THREADS_RUNNING:
            raise RuntimeError("Threads_running exceeds approved limit")

    def execute(self, statement, parameters=None):
        sql = str(statement).lstrip()
        if not sql.upper().startswith("SELECT"):
            raise RuntimeError("canary rejected a non-SELECT application statement")
        self._monitor()
        fingerprint = sha256_bytes(" ".join(sql.split()).encode())[:16]
        started = time.perf_counter()
        try:
            result = self.connection.execute(statement, parameters or {})
        except Exception as exc:
            self.query_log.append({
                "phase": self.phase,
                "fingerprint": fingerprint,
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
                "status": type(exc).__name__,
            })
            raise
        self.query_log.append({
            "phase": self.phase,
            "fingerprint": fingerprint,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
            "status": "ok",
            "streamed": bool(statement.get_execution_options().get("stream_results")),
        })
        return result


class _BorrowedConnection:
    def __init__(self, connection: GuardedConnection) -> None:
        self.connection = connection

    def __enter__(self) -> GuardedConnection:
        return self.connection

    def __exit__(self, exc_type, exc, traceback) -> bool:
        return False


class SingleConnectionEngine:
    def __init__(self, connection: GuardedConnection) -> None:
        self.connection = connection

    def connect(self) -> _BorrowedConnection:
        return _BorrowedConnection(self.connection)


def _load_baseline(temp_root: Path):
    completed = subprocess.run(
        ["git", "show", f"{BASE_HEAD}:app/data/payloads.py"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    )
    source = completed.stdout
    path = temp_root / "baseline_payloads.py"
    path.write_bytes(source)
    spec = importlib.util.spec_from_file_location("cip_baseline_payloads", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load baseline payload module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, sha256_bytes(source)


def _write_payload(root: Path, relative: Path, data: Any, encoder) -> int:
    body = encoder(data)
    target = root / relative.with_name(relative.name + ".json.gz")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(gzip.compress(body, compresslevel=6, mtime=0))
    return len(body)


def _bitset_metrics(people: dict[str, Any]) -> dict[str, int]:
    question_masks = [
        int(bits, 16)
        for question in people["questions"].values()
        for bits in question["bits"].values()
        if bits
    ]
    cut_masks = [
        int(bits, 16)
        for values in people["cuts"].values()
        for bits in values.values()
        if bits
    ]
    union = 0
    for mask in question_masks:
        union |= mask
    return {
        "question_bitsets": len(question_masks),
        "cut_bitsets": len(cut_masks),
        "represented_respondents": union.bit_count(),
    }


def _book_metrics(book: dict[str, Any]) -> dict[str, int]:
    groups = [group for question in book["questions"] for group in question["groups"]]
    rows = [row for group in groups for row in group["rows"]]
    columns = set(book["columns"])
    return {
        "questions": len(book["questions"]),
        "groups": len(groups),
        "rows": len(rows),
        "base_values": sum(1 + len(group.get("bases", {})) for group in groups),
        "unweighted_values": sum(sum(key in columns for key in row) for row in rows),
        "weighted_values": sum(len(row.get("w", {})) for row in rows),
    }


def _payload_summary(cuts: dict, people: dict, book: dict) -> dict[str, Any]:
    cut_hashes = {
        qcode: sha256_bytes(canonical_bytes(part))
        for (_, qcode), part in sorted(cuts.items())
    }
    manifest = {
        "cuts": cut_hashes,
        "people": sha256_bytes(canonical_bytes(people)),
        "book": sha256_bytes(canonical_bytes(book)),
    }
    return {
        "canonical_bundle_sha256": sha256_bytes(canonical_bytes(manifest)),
        "book_sha256": manifest["book"],
        "people_sha256": manifest["people"],
        "cut_hashes": cut_hashes,
        "cut_questions": len(cuts),
        "cut_count_rows": sum(len(part["counts"]) for part in cuts.values()),
        "cut_answer_rows": sum(len(part["answers"]) for part in cuts.values()),
        "bitsets": _bitset_metrics(people),
        "book": _book_metrics(book),
    }


def _build_payloads(module, connection: GuardedConnection, root: Path, phase: str) -> tuple[dict, dict, dict, dict]:
    connection.phase = phase
    started = time.perf_counter()
    tracemalloc.start()
    cuts = module.question_cuts(connection, [SURVEY_ID])
    people = module.people(connection, SURVEY_ID)
    book = module.book(SURVEY_ID)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    bytes_written = 0
    for (_, qcode), part in cuts.items():
        bytes_written += _write_payload(root, Path("cuts") / qcode, part, module.encode)
    bytes_written += _write_payload(root, Path("people"), people, module.encode)
    bytes_written += _write_payload(root, Path("book"), book, module.encode)
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    rss_mib = rss / (1024 * 1024) if sys.platform == "darwin" else rss / 1024
    metrics = {
        "wall_seconds": round(time.perf_counter() - started, 6),
        "traced_peak_mib": round(peak / 1024 / 1024, 3),
        "json_bytes": bytes_written,
        "process_max_rss_mib": round(rss_mib, 3),
        **_payload_summary(cuts, people, book),
    }
    return cuts, people, book, metrics


def _state_marker(connection: GuardedConnection, phase: str) -> tuple[dict[str, int], str]:
    connection.phase = phase
    row = dict(connection.execute(text(STATE_SQL), {"s": SURVEY_ID}).mappings().one())
    public = {
        "rows_built": int(row["rows_built"]),
        "answer_rows": int(row["answer_rows"]),
        "respondents": int(row["respondents"]),
        "result_rows": int(row["result_rows"]),
    }
    return public, sha256_bytes(canonical_bytes(row))


def _install_outbound_socket_block() -> None:
    def audit(event: str, args: tuple[Any, ...]) -> None:
        if event in {"socket.connect", "socket.getaddrinfo", "socket.bind"}:
            raise PermissionError("canary process blocks new network sockets")

    sys.addaudithook(audit)


def main() -> int:
    _sanitise_integration_environment()
    output: dict[str, Any] = {
        "base_head": BASE_HEAD,
        "survey_id": SURVEY_ID,
        "workers": 1,
        "target": EXPECTED_DATABASE,
        "connection_opened": False,
        "connection_closed": False,
        "pool_checked_out_after_close": None,
        "temporary_output_removed": False,
        "outbound_socket_block_active": False,
        "completed": False,
        "parity": False,
        "stopped_reason": None,
    }
    engine = connection = raw_connection = None
    temporary_path: Path | None = None
    current_get_engine = None
    try:
        current_head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, check=True, capture_output=True, text=True
        ).stdout.strip()
        if current_head != BASE_HEAD:
            raise RuntimeError(f"unexpected base HEAD: {current_head}")

        from app.core.config import Config
        from app.data import payloads as current

        db = Config().database("etl")
        if db.database != EXPECTED_DATABASE or not db.host or not db.user or not db.password:
            raise RuntimeError("configured staging target or credentials unavailable")
        if "ssl" not in db.connect_args:
            raise RuntimeError("TLS configuration unavailable")
        connect_args = dict(db.connect_args)
        connect_args.update({
            "connect_timeout": 5,
            "read_timeout": 10,
            "write_timeout": 10,
            "local_infile": False,
        })
        engine = create_engine(
            db.url,
            poolclass=QueuePool,
            pool_size=1,
            max_overflow=0,
            pool_timeout=3,
            pool_pre_ping=False,
            connect_args=connect_args,
            isolation_level="AUTOCOMMIT",
            skip_autocommit_rollback=True,
            future=True,
        )
        connection = engine.connect()
        output["connection_opened"] = True
        raw_connection = connection.connection.driver_connection

        identity_before = _row_dict(connection.execute(text(IDENTITY_SQL)))
        output["identity"] = _validate_identity(identity_before)
        connection.execute(text("SET SESSION TRANSACTION READ ONLY"))
        connection.execute(text("SET SESSION max_execution_time = 5000"))
        connection.execute(text("SET SESSION lock_wait_timeout = 3"))
        connection.execute(text("SET SESSION innodb_lock_wait_timeout = 3"))
        output["session_guards"] = _validate_guards(_row_dict(connection.execute(text(GUARD_SQL))))

        guarded = GuardedConnection(connection)
        guarded._monitor()
        _install_outbound_socket_block()
        output["outbound_socket_block_active"] = True

        with tempfile.TemporaryDirectory(prefix="cip-survey-238-canary-") as tmp:
            temporary_path = Path(tmp)
            baseline, output["baseline_source_sha256"] = _load_baseline(temporary_path)
            output["patched_source_sha256"] = sha256_bytes((REPO_ROOT / "app/data/payloads.py").read_bytes())
            baseline.COUNTRIES = current.COUNTRIES
            baseline.METHODOLOGY = current.METHODOLOGY
            single_engine = SingleConnectionEngine(guarded)
            baseline.get_engine = lambda role="app": single_engine
            current_get_engine = current.get_engine
            current.get_engine = lambda role="app": single_engine

            state_before, state_hash_before = _state_marker(guarded, "state_before")
            baseline_data = _build_payloads(
                baseline, guarded, temporary_path / "baseline", "baseline"
            )
            gc.collect()
            patched_data = _build_payloads(
                current, guarded, temporary_path / "patched", "patched"
            )
            state_after, state_hash_after = _state_marker(guarded, "state_after")

            baseline_cuts, baseline_people, baseline_book, baseline_metrics = baseline_data
            patched_cuts, patched_people, patched_book, patched_metrics = patched_data
            exact = {
                "question_cuts": baseline_cuts == patched_cuts,
                "respondent_bitsets": baseline_people == patched_people,
                "book": baseline_book == patched_book,
                "database_state": state_hash_before == state_hash_after,
            }
            output.update({
                "state_before": state_before,
                "state_after": state_after,
                "state_hash_before": state_hash_before,
                "state_hash_after": state_hash_after,
                "exact_parity": exact,
                "baseline": baseline_metrics,
                "patched": patched_metrics,
                "per_question_hashes_equal": (
                    baseline_metrics["cut_hashes"] == patched_metrics["cut_hashes"]
                ),
                "canonical_bundle_hash_equal": (
                    baseline_metrics["canonical_bundle_sha256"]
                    == patched_metrics["canonical_bundle_sha256"]
                ),
                "publisher_contract_hashes_equal": (
                    all(
                        sha256_bytes(baseline.encode(part))
                        == sha256_bytes(current.encode(patched_cuts[key]))
                        for key, part in baseline_cuts.items()
                    )
                    and sha256_bytes(baseline.encode(baseline_people))
                    == sha256_bytes(current.encode(patched_people))
                    and sha256_bytes(baseline.encode(baseline_book))
                    == sha256_bytes(current.encode(patched_book))
                ),
            })
            output["parity"] = all(exact.values()) and output["per_question_hashes_equal"] \
                and output["canonical_bundle_hash_equal"] and output["publisher_contract_hashes_equal"]
            if not output["parity"]:
                raise RuntimeError("baseline and patched survey payloads differ")

        output["temporary_output_removed"] = temporary_path is not None and not temporary_path.exists()
        if not output["temporary_output_removed"]:
            raise RuntimeError("temporary canary output was not removed")
        output["monitoring_checks"] = guarded.monitoring_checks
        output["max_threads_running"] = guarded.max_threads_running
        output["application_queries"] = guarded.query_log
        output["completed"] = True
        return_code = 0
    except Exception as exc:
        output["stopped_reason"] = f"{type(exc).__name__}: {exc}"
        print(f"STOP: {output['stopped_reason']}", file=sys.stderr, flush=True)
        return_code = 1
    finally:
        try:
            if current_get_engine is not None:
                from app.data import payloads as current
                current.get_engine = current_get_engine
        finally:
            if connection is not None:
                try:
                    final_guards = _row_dict(connection.execute(text(GUARD_SQL)))
                    output["final_session_guards"] = _validate_guards(final_guards)
                except Exception as exc:
                    output["final_guard_error"] = f"{type(exc).__name__}: {exc}"
                    return_code = 1
                connection.close()
            if engine is not None:
                output["pool_checked_out_after_close"] = engine.pool.checkedout()
                engine.dispose()
            output["connection_closed"] = bool(raw_connection is None or not raw_connection.open)
            if temporary_path is not None:
                output["temporary_output_removed"] = not temporary_path.exists()
            OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
            OUTPUT_PATH.write_text(json.dumps(output, indent=2, sort_keys=True, default=_json_default), encoding="utf-8")
    print(
        f"survey={SURVEY_ID} completed={output['completed']} parity={output['parity']} "
        f"connection_closed={output['connection_closed']} temp_removed={output['temporary_output_removed']}",
        flush=True,
    )
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
