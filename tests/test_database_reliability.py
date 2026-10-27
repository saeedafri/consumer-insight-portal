"""Finite MySQL connection, session and pool budgets."""
from __future__ import annotations

import pytest
from sqlalchemy.exc import OperationalError

from app.core import database
from app.core.config import Config, DatabaseConfig
from etl import serving


def mysql_engine(monkeypatch, role: str):
    captured = {}
    marker = object()
    monkeypatch.setattr(
        database.config,
        "database",
        lambda requested: DatabaseConfig(
            host="staging.example",
            port=3306,
            database="cip_stg",
            user="inspection",
            password="not-a-real-secret",
            pool_size=10,
            max_overflow=20,
            pool_timeout=30,
        ),
    )
    monkeypatch.setattr(database, "_engines", {})

    def create(url, **kwargs):
        captured.update(kwargs)
        return marker

    monkeypatch.setattr(database, "create_engine", create)
    assert database.get_engine(role) is marker
    return captured


def test_mysql_app_reads_have_finite_query_and_lock_budgets(monkeypatch):
    configured = mysql_engine(monkeypatch, "app")
    args = configured["connect_args"]
    session = args["init_command"]

    assert args["connect_timeout"] == 10
    assert args["read_timeout"] == 185
    assert args["write_timeout"] == 185
    assert "max_execution_time=180000" in session
    assert "lock_wait_timeout=5" in session
    assert "innodb_lock_wait_timeout=10" in session
    assert configured["pool_size"] == 4
    assert configured["max_overflow"] == 0
    assert configured["pool_timeout"] == 10


def test_mysql_api_writes_use_a_small_transactional_pool(monkeypatch):
    configured = mysql_engine(monkeypatch, "api_write")
    args = configured["connect_args"]
    session = args["init_command"]

    assert args["connect_timeout"] == 10
    assert args["read_timeout"] == 185
    assert args["write_timeout"] == 185
    assert "max_execution_time=180000" in session
    assert "lock_wait_timeout=5" in session
    assert "innodb_lock_wait_timeout=10" in session
    assert configured["pool_size"] == 2
    assert configured["max_overflow"] == 2
    assert configured["pool_timeout"] == 10
    assert "isolation_level" not in configured


def test_mysql_etl_has_finite_select_and_lock_budgets(monkeypatch):
    configured = mysql_engine(monkeypatch, "etl")
    args = configured["connect_args"]
    session = args["init_command"]

    assert args["connect_timeout"] == 10
    assert args["read_timeout"] == 605
    assert args["write_timeout"] == 605
    assert "max_execution_time=600000" in session
    assert "lock_wait_timeout=10" in session
    assert "innodb_lock_wait_timeout=30" in session
    assert "tmp_table_size=536870912" in session
    assert configured["pool_size"] == 4
    assert configured["max_overflow"] == 0
    assert configured["pool_timeout"] == 10


@pytest.mark.parametrize(
    ("name", "value"),
    (("DB_POOL_SIZE", "11"), ("DB_MAX_OVERFLOW", "21"), ("DB_POOL_TIMEOUT", "31"), ("DB_POOL_SIZE", "zero")),
)
def test_database_pool_limits_fail_closed(monkeypatch, name, value):
    monkeypatch.setenv("APP_ENV", "STAGING")
    monkeypatch.setenv("STG_DB_HOST", "staging.example")
    monkeypatch.setenv("STG_DB_NAME", "cip_stg")
    monkeypatch.setenv(name, value)

    with pytest.raises(ValueError, match=name):
        Config().database("app")


def mysql_error(code: int) -> OperationalError:
    return OperationalError("statement redacted", {}, type("MySQLError", (Exception,), {"args": (code,)})())


def test_serving_retries_lock_timeout_with_bounded_backoff(monkeypatch):
    outcomes = [mysql_error(1205), mysql_error(1213), 17]
    delays = []

    def build(_survey_id):
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(serving, "_build_wave", build)
    monkeypatch.setattr(serving.random, "uniform", lambda _start, _end: 0.125)
    monkeypatch.setattr(serving.time, "sleep", delays.append)

    assert serving.build_wave(262) == 17
    assert delays == [1.125, 2.125]


def test_serving_does_not_retry_nontransient_mysql_errors(monkeypatch):
    calls = []

    def build(_survey_id):
        calls.append(1)
        raise mysql_error(1146)

    monkeypatch.setattr(serving, "_build_wave", build)
    monkeypatch.setattr(serving.time, "sleep", lambda _seconds: pytest.fail("nontransient error was retried"))

    with pytest.raises(OperationalError):
        serving.build_wave(262)
    assert len(calls) == 1
