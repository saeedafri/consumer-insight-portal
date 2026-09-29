"""Access control.

The portal serves respondent-level survey microdata, so the interesting tests
are the ones that prove it says no.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest


@pytest.fixture()
def auth(monkeypatch):
    import app.core.auth as _auth
    for key in ("AUTH_PROVIDER", "AUTH_ALLOWED_EMAILS", "AUTH_SHARED_PASSPHRASE",
                "OIDC_CLIENT_ID", "IDP_BASE_URL"):
        monkeypatch.delenv(key, raising=False)
    return _auth


# ── provider selection ─────────────────────────────────────────────────────
def test_provider_defaults_to_off_when_nothing_is_configured(auth):
    assert auth.provider() == "off"


def test_provider_infers_local_from_an_allowlist(auth, monkeypatch):
    monkeypatch.setenv("AUTH_ALLOWED_EMAILS", "@coresight.com")
    assert auth.provider() == "local"


def test_provider_infers_oidc_when_the_idp_is_configured(auth, monkeypatch):
    monkeypatch.setenv("OIDC_CLIENT_ID", "abc")
    monkeypatch.setenv("IDP_BASE_URL", "https://idp.example")
    assert auth.provider() == "oidc"


def test_explicit_provider_wins(auth, monkeypatch):
    monkeypatch.setenv("OIDC_CLIENT_ID", "abc")
    monkeypatch.setenv("IDP_BASE_URL", "https://idp.example")
    monkeypatch.setenv("AUTH_PROVIDER", "local")
    assert auth.provider() == "local"


# ── the allowlist ──────────────────────────────────────────────────────────
def test_domain_entry_admits_the_domain_and_nothing_else(auth, monkeypatch):
    monkeypatch.setenv("AUTH_ALLOWED_EMAILS", "@coresight.com")
    assert auth.email_is_allowed("john@coresight.com")
    assert auth.email_is_allowed("JOHN@Coresight.com")      # case-insensitive
    assert not auth.email_is_allowed("john@gmail.com")
    assert not auth.email_is_allowed("john@notcoresight.com")
    assert not auth.email_is_allowed("john@coresight.com.evil.com")


def test_named_addresses_are_admitted_individually(auth, monkeypatch):
    monkeypatch.setenv("AUTH_ALLOWED_EMAILS", "a@x.com, b@y.com")
    assert auth.email_is_allowed("b@y.com")
    assert not auth.email_is_allowed("c@y.com")


def test_an_empty_allowlist_admits_nobody(auth, monkeypatch):
    monkeypatch.setenv("AUTH_ALLOWED_EMAILS", "")
    assert not auth.email_is_allowed("anyone@coresight.com")


def test_garbage_is_rejected(auth, monkeypatch):
    monkeypatch.setenv("AUTH_ALLOWED_EMAILS", "@coresight.com")
    for bad in ("", "   ", "not-an-email", "@coresight.com", None):
        assert not auth.email_is_allowed(bad)  # type: ignore[arg-type]


# ── sessions ───────────────────────────────────────────────────────────────
def test_expiry_is_honoured(auth):
    past = auth.AuthUser(email="a@b.com",
                         expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
    future = auth.AuthUser(email="a@b.com",
                           expires_at=datetime.now(timezone.utc) + timedelta(hours=1))
    assert past.is_expired
    assert not future.is_expired


def test_timestamps_parse_from_both_engines(auth):
    """SQLite returns a string, MySQL a datetime. Both must compare."""
    assert auth._as_datetime("2026-09-29 12:00:00") is not None
    assert auth._as_datetime("2026-09-29 12:00:00.123456") is not None
    assert auth._as_datetime(datetime(2026, 9, 29, 12)) is not None
    assert auth._as_datetime(None) is None
    assert auth._as_datetime("not a date") is None


def test_oidc_sign_in_refuses_an_unentitled_account(auth, monkeypatch):
    monkeypatch.setenv("AUTH_ALLOWED_EMAILS", "@coresight.com")
    ok, message = auth.sign_in_oidc({"email": "someone@elsewhere.com"})
    assert not ok and "entitled" in message


def test_oidc_sign_in_refuses_claims_with_no_email(auth):
    ok, message = auth.sign_in_oidc({"name": "No Email"})
    assert not ok and "email" in message.lower()


def test_fingerprint_does_not_leak_the_identity(auth):
    tag = auth.fingerprint("john@coresight.com")
    assert "john" not in tag and "@" not in tag and len(tag) == 12
