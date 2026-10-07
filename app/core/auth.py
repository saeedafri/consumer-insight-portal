"""Authentication for the Consumer Insight Portal.

The public API deliberately mirrors market-data-stg's `auth_manager` —
`require_auth`, `is_authenticated`, `get_current_user`, `logout` — so pages
here look like pages there, and so the Coresight OIDC manager can be dropped
in later by swapping one provider without touching a single page.

Three providers, chosen by AUTH_PROVIDER:

  oidc   the Coresight identity provider, same env vars as SIP-Prod
         (IDP_BASE_URL / IDP_TOKEN_URL / IDP_USERINFO_URL / OIDC_CLIENT_ID /
         OIDC_CLIENT_SECRET). Authorization-code flow with PKCE.
  local  an email allowlist plus a shared passphrase. Real protection for an
         internal STG deployment, and it works today with no IdP.
  off    no auth. Refuses to run outside APP_ENV=LOCAL — an open portal on a
         staging host is how survey microdata leaks.

Sessions are cookie-backed. That is not a style choice: the header nav uses
plain anchors (the same pattern as the Market Data Portal), so moving between
pages is a full page load and a brand-new Streamlit session — anything kept
only in `st.session_state` is gone by the time the next page renders. The
cookie carries an opaque session id; the row in `cip_auth_session` carries
everything else, so a sign-in survives navigation, every access is auditable,
and an admin can revoke a session by updating one row.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import streamlit as st
from sqlalchemy import text

from .config import config
from .database import get_engine

logger = logging.getLogger(__name__)

SESSION_KEY = "csi_auth"
COOKIE_NAME = "csi_session"
DEFAULT_TTL_HOURS = 12

try:
    from streamlit_cookies_controller import CookieController
    _HAS_COOKIES = True
except Exception:  # noqa: BLE001
    _HAS_COOKIES = False


def _cookies():
    """A controller for THIS browser session. Never cache it process-wide: the
    controller holds the cookies it read, so a shared one hands the first
    visitor's session id to everyone after them. The library keeps its own
    per-session state under the key, so building it each run is cheap."""
    return CookieController(key="csi_cookies") if _HAS_COOKIES else None


def _cookie_set(session_id: str, ttl_hours: int) -> None:
    ctl = _cookies()
    if ctl is None:
        return
    try:
        ctl.set(COOKIE_NAME, session_id,
                max_age=ttl_hours * 3600, path="/", same_site="lax")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not set the session cookie: %s", exc)


def _cookie_get() -> str:
    ctl = _cookies()
    if ctl is None:
        return ""
    try:
        return str(ctl.get(COOKIE_NAME) or "")
    except Exception:  # noqa: BLE001
        return ""


def _cookie_clear() -> None:
    ctl = _cookies()
    if ctl is None:
        return
    try:
        ctl.remove(COOKIE_NAME)
    except Exception:  # noqa: BLE001
        pass


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


@dataclass(frozen=True)
class AuthUser:
    email: str
    name: str = ""
    provider: str = "local"
    session_id: str = ""
    expires_at: Optional[datetime] = None

    @property
    def is_expired(self) -> bool:
        return bool(self.expires_at and datetime.now(timezone.utc) >= self.expires_at)


# ── provider selection ─────────────────────────────────────────────────────
def provider() -> str:
    explicit = _env("AUTH_PROVIDER").lower()
    if explicit in {"oidc", "local", "off"}:
        return explicit
    if _env("OIDC_CLIENT_ID") and _env("IDP_BASE_URL"):
        return "oidc"
    if _env("AUTH_ALLOWED_EMAILS"):
        return "local"
    return "off"


def allowed_emails() -> set[str]:
    raw = _env("AUTH_ALLOWED_EMAILS")
    out: set[str] = set()
    for part in raw.replace(";", ",").split(","):
        part = part.strip().lower()
        if part:
            out.add(part)
    return out


def email_is_allowed(email: str) -> bool:
    """An allowlist entry may be a full address or a bare @domain suffix.

    A bare "@coresight.com" is a RULE, never an identity: it must not admit
    itself as a login. Hence the explicit local-part check — without it,
    typing the domain into the email box signs you in.
    """
    email = (email or "").strip().lower()
    local, _, domain_part = email.partition("@")
    if not local or not domain_part or "@" in domain_part:
        return False
    allow = allowed_emails()
    if not allow:
        return False
    return email in allow or f"@{domain_part}" in allow


# ── session store ──────────────────────────────────────────────────────────
def _record_session(user: AuthUser, request_meta: str = "") -> None:
    try:
        with get_engine("etl").begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO cip_auth_session
                        (session_id, user_email, user_name, provider, expires_at, request_meta)
                    VALUES (:sid, :email, :name, :prov, :exp, :meta)
                    """
                ),
                {"sid": user.session_id, "email": user.email, "name": user.name,
                 "prov": user.provider,
                 "exp": user.expires_at.replace(tzinfo=None) if user.expires_at else None,
                 "meta": request_meta[:500]},
            )
    except Exception as exc:  # noqa: BLE001
        # Auditing must never be the reason someone cannot sign in.
        logger.warning("Could not record auth session: %s", exc)


def _session_is_live(session_id: str) -> bool:
    if not session_id:
        return False
    try:
        with get_engine("app").connect() as conn:
            row = conn.execute(
                text("SELECT revoked_at, expires_at FROM cip_auth_session "
                     "WHERE session_id = :sid"),
                {"sid": session_id},
            ).first()
    except Exception:  # noqa: BLE001
        return True  # store unavailable — fall back to the in-memory session
    if row is None:
        return True
    revoked, expires = row
    if revoked is not None:
        return False
    expires = _as_datetime(expires)
    if expires is not None and datetime.now(timezone.utc) >= expires:
        return False
    return True


def _as_datetime(value: Any) -> Optional[datetime]:
    """SQLite hands back DATETIME columns as strings; MySQL as datetimes.

    Both paths land here so the session check does not depend on which engine
    is underneath — a naive value is read as UTC, which is how it was written.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(str(value).strip(), fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    logger.warning("Unparseable session timestamp: %r", value)
    return None


def _revoke(session_id: str) -> None:
    if not session_id:
        return
    try:
        with get_engine("etl").begin() as conn:
            conn.execute(
                text("UPDATE cip_auth_session SET revoked_at = CURRENT_TIMESTAMP "
                     "WHERE session_id = :sid"),
                {"sid": session_id},
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not revoke session: %s", exc)


# ── public API ─────────────────────────────────────────────────────────────
def _load_session(session_id: str) -> Optional[AuthUser]:
    """Rebuild a user from the audit row — the path taken after every header
    navigation, because that is a fresh Streamlit session."""
    if not session_id:
        return None
    try:
        with get_engine("app").connect() as conn:
            row = conn.execute(
                text("SELECT user_email, user_name, provider, expires_at, revoked_at "
                     "FROM cip_auth_session WHERE session_id = :sid"),
                {"sid": session_id},
            ).first()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not read the session store: %s", exc)
        return None
    if row is None or row[4] is not None:
        return None
    expires = _as_datetime(row[3])
    if expires is not None and datetime.now(timezone.utc) >= expires:
        return None
    return AuthUser(email=row[0], name=row[1] or "", provider=row[2] or "local",
                    session_id=session_id, expires_at=expires)


def debug_user() -> Optional[AuthUser]:
    """Local-testing bypass, the same gate as the Market Data Portal:
    APP_ENV=LOCAL and DEBUG=true, impersonating LOCAL_TEST_USER_EMAIL.
    Never active on STG/PROD — APP_ENV is not LOCAL there."""
    if not (config.is_local and config.debug):
        return None
    email = _env("LOCAL_TEST_USER_EMAIL") or "local@test.com"
    return AuthUser(email=email.lower(), name="Local Test User", provider="debug",
                    session_id="local-debug-session")


def current_user() -> Optional[AuthUser]:
    bypass = debug_user()
    if bypass:
        return bypass
    user = st.session_state.get(SESSION_KEY)

    if not isinstance(user, AuthUser):
        # New page load — recover the session from the cookie.
        user = _load_session(_cookie_get())
        if user is None:
            return None
        st.session_state[SESSION_KEY] = user
        return user

    if user.is_expired or not _session_is_live(user.session_id):
        st.session_state.pop(SESSION_KEY, None)
        _cookie_clear()
        return None
    return user


def is_authenticated() -> bool:
    if provider() == "off":
        return True
    return current_user() is not None


def get_current_user() -> Optional[str]:
    bypass = debug_user()
    if bypass:
        return bypass.email
    if provider() == "off":
        return "local-dev"
    user = current_user()
    return user.email if user else None


def sign_in_local(email: str, passphrase: str) -> tuple[bool, str]:
    """Allowlist + shared passphrase. Compared with `compare_digest` so the
    check does not leak length or prefix through timing."""
    email = (email or "").strip().lower()
    if not email_is_allowed(email):
        return False, "That address is not on the portal's allowlist."
    expected = _env("AUTH_SHARED_PASSPHRASE")
    if not expected:
        return False, "AUTH_SHARED_PASSPHRASE is not configured. Ask IT to set it."
    if not hmac.compare_digest(passphrase or "", expected):
        return False, "Incorrect passphrase."

    ttl = int(_env("AUTH_SESSION_HOURS", str(DEFAULT_TTL_HOURS)) or DEFAULT_TTL_HOURS)
    user = AuthUser(
        email=email,
        name=email.split("@")[0].replace(".", " ").title(),
        provider="local",
        session_id=secrets.token_urlsafe(24),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=ttl),
    )
    st.session_state[SESSION_KEY] = user
    _record_session(user, _request_meta())
    _cookie_set(user.session_id, ttl)
    logger.info("Signed in %s (local)", email)
    return True, ""


def sign_in_oidc(claims: dict[str, Any]) -> tuple[bool, str]:
    """Complete a sign-in from verified OIDC claims.

    The token exchange itself belongs in the Coresight auth manager; this takes
    the claims it produces so the rest of the portal is provider-agnostic.
    """
    email = str(claims.get("email", "")).strip().lower()
    if not email:
        return False, "The identity provider returned no email claim."
    if allowed_emails() and not email_is_allowed(email):
        return False, "That account is not entitled to this portal."
    ttl = int(_env("AUTH_SESSION_HOURS", str(DEFAULT_TTL_HOURS)) or DEFAULT_TTL_HOURS)
    user = AuthUser(
        email=email,
        name=str(claims.get("name") or claims.get("nickname") or ""),
        provider="oidc",
        session_id=str(claims.get("sid") or secrets.token_urlsafe(24)),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=ttl),
    )
    st.session_state[SESSION_KEY] = user
    _record_session(user, _request_meta())
    _cookie_set(user.session_id, ttl)
    return True, ""


def logout() -> None:
    user = st.session_state.get(SESSION_KEY)
    if isinstance(user, AuthUser):
        _revoke(user.session_id)
        logger.info("Signed out %s", user.email)
    st.session_state.pop(SESSION_KEY, None)
    _cookie_clear()


def require_auth(page: str = "") -> Optional[AuthUser]:
    """Guard a page. Returns the user, or stops the script and sends the
    visitor to the login page."""
    bypass = debug_user()
    if bypass:
        return bypass
    mode = provider()

    if mode == "off":
        if not config.is_local:
            st.error(
                "**Authentication is not configured.** The portal refuses to serve "
                f"survey microdata on `{config.environment.value}` without it. "
                "Set `AUTH_PROVIDER` — see `docs/08-authentication.md`."
            )
            st.stop()
        return None

    user = current_user()
    if user is None:
        st.session_state["csi_auth_next"] = page or ""
        st.switch_page("pages/0_Login.py")
    return user


def _request_meta() -> str:
    try:
        headers = st.context.headers or {}
        return f"host={headers.get('host', '?')} ua={str(headers.get('user-agent', ''))[:180]}"
    except Exception:  # noqa: BLE001
        return ""


def fingerprint(value: str) -> str:
    """Short non-reversible tag for logging an identity without storing it."""
    return hashlib.sha256(value.encode()).hexdigest()[:12]
