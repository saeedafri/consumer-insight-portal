"""Fail-closed checks for the local test process."""
from __future__ import annotations

import os
import socket

import pytest

from app.core.config import config


def test_tests_use_only_local_sqlite_and_blank_live_integrations():
    assert config.database("app").sqlite_path
    assert config.database("etl").sqlite_path
    assert config.database("app").host == config.database("etl").host == ""
    for name in (
        "ANTHROPIC_API_KEY",
        "APP_DB_PASSWORD",
        "APP_DB_USER",
        "CIP_NGINX_URL",
        "CIP_OIDC_CLIENT_ID",
        "CIP_OIDC_CLIENT_SECRET",
        "CIP_OIDC_ISSUER",
        "CIP_PUBLISH_BACKUP_URL",
        "EMAIL_PASSWORD",
        "FORSTA_API_KEY",
        "STG_DB_HOST",
        "STG_DB_NAME",
        "STG_DB_PASSWORD",
        "STG_DB_USER",
        "TEAMS_WEBHOOK_URL",
    ):
        assert os.environ[name] == ""


def test_tests_cannot_open_a_network_socket():
    with socket.socket() as candidate, pytest.raises(AssertionError, match="real network connection"):
        candidate.connect(("example.invalid", 443))
    with socket.socket() as candidate, pytest.raises(AssertionError, match="real network connection"):
        candidate.connect_ex(("example.invalid", 443))
    with socket.socket(type=socket.SOCK_DGRAM) as candidate, pytest.raises(AssertionError, match="real network connection"):
        candidate.sendto(b"blocked", ("example.invalid", 53))
    with pytest.raises(AssertionError, match="real network connection"):
        socket.create_connection(("example.invalid", 443))
