"""Signing in to the portal, and the session check every /api route depends on.

  /auth/login       to the identity provider (OIDC authorization code + PKCE, state and nonce), or, when no provider
                    is configured and CIP_DEMO_LOGIN=1, the demo sign-in; else a page that says sign-in is not set up
  /auth/callback    the provider's answer: the code exchanged for an ID token, the token's issuer, audience, expiry
                    and nonce checked, the email mapped to a role, client and tier (shared/core/access.py)
  /auth/logout      the session revoked (sql/008_access.sql), the cookie dropped, the provider's session ended
                    (CIP_OIDC_LOGOUT_URL, with the ID token as id_token_hint), then the home page
  /auth/dev-login   the demo sign-in as any email: only with CIP_DEMO_LOGIN=1 and no provider, never implied by APP_ENV
  /auth/check       nginx's auth_request (deploy/nginx.conf)

Provider settings: CIP_OIDC_ISSUER (e.g. https://login.microsoftonline.com/<tenant>/v2.0), CIP_OIDC_CLIENT_ID,
CIP_OIDC_CLIENT_SECRET, and optionally CIP_OIDC_REDIRECT_URI (default: this host's /auth/callback).
Coresight's own identity provider (coresight.com/csr-idp, the one SIP signs in with) publishes no discovery document:
for it also set CIP_OIDC_AUTHORIZE_URL, CIP_OIDC_TOKEN_URL, CIP_OIDC_LOGOUT_URL (<host>/csr-idp/logout/) and
CIP_OIDC_PKCE=plain (what it is proven with).
CIP_OIDC_TOKEN_ISSUER: the iss the ID token carries, only if it differs from CIP_OIDC_ISSUER.
CIP_OIDC_LOG_CLAIMS=1 (test instances only) logs every claim the provider sends, to map roles from them;
CIP_OIDC_USERINFO_URL adds the userinfo answer to that log.
"""
from __future__ import annotations

import base64
import hashlib
import html
import json
import logging
import os
import re
import secrets
import time
from functools import lru_cache
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import text
from starlette.concurrency import run_in_threadpool

from api.team import json_body
from shared.core import access, api_keys, audit
from shared.core.database import get_engine
from shared.core.session import REVOKED, SESSION_HOURS, digest, issue, read, same, sign

log = logging.getLogger("cip.signin")
router = APIRouter()
COOKIE = "cip_session"
LOGIN = "cip_login"          # the OIDC round trip's state, nonce, PKCE verifier and next page, signed, for 10 minutes
ID_TOKEN = "cip_id_token"    # the provider's ID token, kept for /auth/logout: csr-idp ends its own session only with id_token_hint


def demo() -> bool:
    """The demo sign-in (any email, no password): only with CIP_DEMO_LOGIN=1 and no identity provider configured. With
    one, anyone could type anyone's email on a public address (staging, 7 Nov 2026), so the provider always wins."""
    return os.environ.get("CIP_DEMO_LOGIN") == "1" and provider() is None


def provider() -> dict | None:
    issuer, client_id = os.environ.get("CIP_OIDC_ISSUER", "").rstrip("/"), os.environ.get("CIP_OIDC_CLIENT_ID", "")
    return {"issuer": issuer, "client_id": client_id, "secret": os.environ.get("CIP_OIDC_CLIENT_SECRET", "")} \
        if issuer and client_id else None


def endpoints(issuer: str) -> dict:
    """The provider's sign-in and token addresses: set by hand (CIP_OIDC_AUTHORIZE_URL, CIP_OIDC_TOKEN_URL) for a
    provider without a discovery document, else read from its discovery document. Called by /auth/login and /auth/callback."""
    if os.environ.get("CIP_OIDC_AUTHORIZE_URL"):
        return {"issuer": issuer, "authorization_endpoint": os.environ["CIP_OIDC_AUTHORIZE_URL"],
                "token_endpoint": os.environ.get("CIP_OIDC_TOKEN_URL", ""),
                "end_session_endpoint": os.environ.get("CIP_OIDC_LOGOUT_URL", "")}
    return discovery(issuer)


@lru_cache(maxsize=4)
def discovery(issuer: str) -> dict:
    import requests
    found = requests.get(f"{issuer}/.well-known/openid-configuration", timeout=10)
    found.raise_for_status()
    return found.json()


def https(request: Request) -> bool:
    """Behind cloudflared or nginx the socket is plain HTTP; the proxy says what the browser used."""
    return request.url.scheme == "https" or request.headers.get("x-forwarded-proto", "").split(",")[0].strip() == "https"


def same_site(target: str) -> str:
    return target if target.startswith("/") and not target.startswith("//") and "\\" not in target else "/"


def page(status: int, title: str, body: str) -> HTMLResponse:
    return HTMLResponse(f"<!doctype html><meta charset=utf-8><title>{html.escape(title)}</title>"
                        f"<body style='font:16px system-ui;max-width:36rem;margin:4rem auto;padding:0 1rem;color:#2D2A29'>"
                        f"<h1>{html.escape(title)}</h1><p>{body}</p>", status_code=status)


def user(request: Request) -> dict:
    """The signed-in person on every API route: {email, role, tier, client, features, study_types, products, sid}.
    A program signs in with an API key instead (Authorization: Bearer cip_…, shared/core/api_keys.py)."""
    bearer = request.headers.get("authorization", "")
    if bearer.lower().startswith("bearer "):
        email = api_keys.owner(bearer[7:].strip())
        who = email and access.profile(email)
        if not who:
            raise HTTPException(401, "Unknown or revoked API key")
        if not access.spend(who["email"], "api"):
            raise HTTPException(429, "Too many API requests: wait a minute", headers={"Retry-After": "60"})
        person = {**who, "products": ["*"], "sid": "api-key"}
        request.state.email, request.state.person = who["email"], person
        return person
    session = read(request.cookies.get(COOKIE, ""))
    who = session and access.profile(session["email"])
    if not who:
        raise HTTPException(401, "Sign in required")
    if session["scope"] != access.scope(who) or session["expires"] < stale_before():   # access changed since sign-in
        request.state.cookie = issue(who["email"], ",".join(session["products"]), sid=session["sid"], scope=access.scope(who))
    person = {**who, "products": session["products"], "sid": session["sid"]}
    request.state.email, request.state.person = who["email"], person   # the team routes record who did what
    return person


def admin(request: Request, who: dict = Depends(user)) -> dict:
    if not access.can(who, "admin_pages"):
        raise HTTPException(403, "Only an admin can do that")
    # the demo sign-in takes any email at its word, so anyone could type an admin's: a session that came through it
    # also needs CIP_ADMIN_TOKEN (32+ characters) in the X-CIP-Admin-Token header. A sign-in the identity provider
    # proved (csr-idp, Entra) needs nothing more: the email is the person's own
    token = os.environ.get("CIP_ADMIN_TOKEN", "")
    if demo() and not proven(who.get("sid", "")) \
            and not (len(token) >= 32 and same(token, request.headers.get("x-cip-admin-token", ""))):
        raise HTTPException(403, "While sign-in is the demo, admin pages also need the admin token")
    return who


PROVEN: set[str] = set()   # sessions known to have signed in through the identity provider (never changes for a session)


def proven(sid: str) -> bool:
    """Did this session sign in through the identity provider (cip_access_session.provider 'oidc'), not the demo sign-in.
    A yes is remembered; a no is asked again (the database may have been out of reach). An API key is never proven."""
    if sid in PROVEN:
        return True
    if not sid or sid == "api-key":
        return False
    try:
        with get_engine("app").connect() as conn:
            found = conn.execute(text("SELECT provider FROM cip_access_session WHERE session_hash = :h"), {"h": digest(sid)}).scalar()
    except Exception:   # noqa: BLE001   the database out of reach: ask for the token, as before
        return False
    if found == "oidc":
        PROVEN.add(sid)
    return found == "oidc"


def remember(sid: str, who: dict, how: str) -> None:
    try:
        with get_engine("api_write").begin() as conn:
            conn.execute(text("INSERT INTO cip_access_session (session_hash, email, client, role, provider, expires_at)"
                              " VALUES (:h, :e, :c, :r, :p, :x)"),
                         {"h": digest(sid), "e": who["email"], "c": who["client"], "r": who["role"], "p": how,
                          "x": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(time.time() + SESSION_HOURS * 3600))})
    except Exception as exc:   # noqa: BLE001 — before sql/008 is applied a sign-in still works, it just can't be revoked by an admin
        log.warning("Session not recorded: %s", type(exc).__name__)


async def signed_in(request: Request, who: dict, how: str, target: str, id_token: str = "") -> Response:
    sid = secrets.token_urlsafe(18)
    await run_in_threadpool(remember, sid, who, how)
    audit.record(request, "sign_in", who=who, detail={"provider": how})
    # the database keeps only a hash of the address (shared/core/audit.py); the admins' Logs page lists sign-ins with the
    # real address from this line (api/metrics.py sign_ins), as nginx's request log already holds it
    where = re.sub(r"^(\d+\.\d+\.\d+\.\d+):\d+$", r"\1", audit.address(request))   # Azure adds ":port"
    log.info("sign-in: %s role=%s via %s from %s", who["email"], who["role"], how, where)
    response = RedirectResponse(same_site(target), status_code=303)
    response.set_cookie(COOKIE, issue(who["email"], sid=sid, scope=access.scope(who)), httponly=True, samesite="lax",
                        secure=https(request), max_age=SESSION_HOURS * 3600)
    response.delete_cookie(LOGIN, path="/auth")
    if id_token:
        response.set_cookie(ID_TOKEN, id_token, path="/auth", httponly=True, samesite="lax", secure=https(request),
                            max_age=SESSION_HOURS * 3600)
    return response


def attempt_failed(request: Request, reason: str, email: str = "") -> None:
    """A sign-in that did not get in, in the access log (cip_access_log, action sign_in_failed) beside the successful
    ones: who tried (when the token named them), when, why, the hashed address and the browser. The Logs page lists it."""
    audit.record(request, "sign_in_failed", who={"email": email or "unknown", "role": "", "client": None}, detail={"reason": reason})
    where = re.sub(r"^(\d+\.\d+\.\d+\.\d+):\d+$", r"\1", audit.address(request))
    log.info("sign-in: %s role=failed via %s from %s", email or "unknown", re.sub(r"\W+", "-", reason)[:40], where)   # the Logs page's sign-ins


def refused(request: Request, email: str) -> HTMLResponse:
    attempt_failed(request, "not entitled", email)
    return page(403, "No access to the portal", f"{html.escape(email)} is not entitled to the Consumer Insight Portal. "
                "Ask your Coresight contact to add your organisation.")


@router.get("/auth/login")
async def login(request: Request, next: str = "/") -> Response:
    found = provider()
    if not found:
        if demo():
            return RedirectResponse(f"/auth/dev-login?{urlencode({'next': same_site(next)})}", status_code=303)
        return page(503, "Sign-in is not set up", "This portal has no identity provider configured yet "
                    "(CIP_OIDC_ISSUER, CIP_OIDC_CLIENT_ID). Ask the Coresight data team for access.")
    meta = await run_in_threadpool(endpoints, found["issuer"])
    state, nonce, verifier = secrets.token_urlsafe(24), secrets.token_urlsafe(24), secrets.token_urlsafe(48)
    plain = os.environ.get("CIP_OIDC_PKCE") == "plain"   # csr-idp; every other provider: S256
    challenge = verifier if plain else base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    value = "|".join([state, nonce, verifier, same_site(next), str(int(time.time()) + 600)])
    response = RedirectResponse(meta["authorization_endpoint"] + "?" + urlencode({
        "response_type": "code", "client_id": found["client_id"], "redirect_uri": callback_url(request),
        "scope": "openid email profile", "state": state, "nonce": nonce,
        "code_challenge": challenge, "code_challenge_method": "plain" if plain else "S256"}), status_code=303)
    response.set_cookie(LOGIN, f"{base64.urlsafe_b64encode(value.encode()).decode()}.{sign(value)}", path="/auth",
                        httponly=True, samesite="lax", secure=https(request), max_age=600)
    return response


def callback_url(request: Request) -> str:
    return os.environ.get("CIP_OIDC_REDIRECT_URI") or f"{'https' if https(request) else 'http'}://{request.headers.get('host')}/auth/callback"


def claims(token: str) -> dict:
    part = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))


def log_claims(meta: dict, answer: dict, said: dict) -> None:
    """Everything the provider says about the person (ID token claims, the token answer minus its tokens, and the
    userinfo answer when there is one), so roles and permissions can be mapped to what it really sends.
    Only with CIP_OIDC_LOG_CLAIMS=1 (a test instance): the lines hold personal data. Called by /auth/callback."""
    import requests
    log.info("OIDC token answer (tokens removed): %s", json.dumps({k: v for k, v in answer.items() if not k.endswith("token")}))
    log.info("OIDC id_token claims: %s", json.dumps(said, default=str))
    url = os.environ.get("CIP_OIDC_USERINFO_URL") or meta.get("userinfo_endpoint")
    if url and answer.get("access_token"):
        try:
            found = requests.get(url, timeout=10, headers={"Authorization": f"Bearer {answer['access_token']}"})
            log.info("OIDC userinfo %s: %s", found.status_code, found.text[:4000])
        except Exception as exc:   # noqa: BLE001 — a missing userinfo must not stop the sign-in
            log.info("OIDC userinfo failed: %s", type(exc).__name__)


@router.get("/auth/callback")
async def callback(request: Request, code: str = "", state: str = "", error: str = "") -> Response:
    found = provider()
    raw = request.cookies.get(LOGIN, "")
    try:
        encoded, signature = raw.rsplit(".", 1)
        value = base64.urlsafe_b64decode(encoded.encode()).decode()
        mine, nonce, verifier, target, expires = value.split("|")
    except ValueError:
        attempt_failed(request, "sign-in expired or no sign-in cookie")
        return page(400, "Sign-in expired", "Please <a href='/auth/login'>sign in again</a>.")
    if not found or error or not code or not same(signature, sign(value)) \
            or not same(state, mine) or int(expires) < time.time():
        attempt_failed(request, f"provider error {error}" if error else "state or code did not check out")
        return page(400, "Sign-in failed", f"{html.escape(error or 'The sign-in could not be checked.')} "
                    "Please <a href='/auth/login'>try again</a>.")
    meta = await run_in_threadpool(endpoints, found["issuer"])

    def exchange() -> dict:
        import requests
        answer = requests.post(meta["token_endpoint"], timeout=15, data={
            "grant_type": "authorization_code", "code": code, "redirect_uri": callback_url(request),
            "client_id": found["client_id"], "code_verifier": verifier, **({"client_secret": found["secret"]} if found["secret"] else {})})
        answer.raise_for_status()
        return answer.json()
    try:
        # ponytail: the ID token comes straight from the token endpoint over TLS, so its signature is not re-checked
        # (OIDC Core 3.1.3.7 allows this); check it against the provider's JWKS if tokens ever arrive another way
        answer = await run_in_threadpool(exchange)
        said = claims(answer["id_token"])
        if os.environ.get("CIP_OIDC_LOG_CLAIMS") == "1":
            await run_in_threadpool(log_claims, meta, answer, said)
    except Exception as exc:   # noqa: BLE001
        log.warning("OIDC token exchange failed: %s", type(exc).__name__)
        attempt_failed(request, f"token exchange failed ({type(exc).__name__})")
        return page(502, "Sign-in failed", "The identity provider did not answer. Please <a href='/auth/login'>try again</a>.")
    audience = said.get("aud") if isinstance(said.get("aud"), list) else [said.get("aud")]
    issuer = os.environ.get("CIP_OIDC_TOKEN_ISSUER") or meta.get("issuer")   # set it when the token's iss differs from CIP_OIDC_ISSUER
    # a provider that does not echo the nonce (csr-idp) is still held by the state and the PKCE verifier
    if said.get("iss") != issuer or found["client_id"] not in audience or float(said.get("exp", 0)) < time.time() \
            or ("nonce" in said and not same(str(said["nonce"]), nonce)):
        log.warning("OIDC token refused: iss %s, aud %s", said.get("iss"), said.get("aud"))   # names, never the token
        attempt_failed(request, "identity token did not check out")
        return page(400, "Sign-in failed", "The identity token did not check out. Please <a href='/auth/login'>try again</a>.")
    wordpress = (said.get("data") or {}).get("wp_user") if isinstance(said.get("data"), dict) else None   # csr-idp's
    wordpress = wordpress if isinstance(wordpress, dict) else {}
    email = str(said.get("email") or said.get("user_email") or wordpress.get("user_email") or wordpress.get("email")
                or said.get("preferred_username") or said.get("upn") or "").lower()
    who = access.profile(email) if "@" in email else None
    if not who:
        return refused(request, email or "This account")
    return await signed_in(request, {**who, "name": said.get("name") or wordpress.get("name") or ""}, "oidc", target,
                           answer["id_token"])


@router.get("/auth/dev-login")
async def dev_login(request: Request, email: str = "analyst@coresight.com", next: str = "/") -> Response:
    """The demo sign-in, as any email: only when CIP_DEMO_LOGIN=1."""
    if not demo():
        raise HTTPException(404)
    who = access.profile(email)
    return await signed_in(request, who, "demo", next) if who else refused(request, email)


STARTED = time.time()


def stale_before() -> int:
    """A sign-in cookie expiring before this was issued before access last changed (the Access page, or this server's
    start, which may follow a config change): its scope may say "sees everything" for someone who no longer does. nginx
    then stops serving files to it directly and the API, which checks access on every request, answers and re-issues
    the cookie (user()). This is how a trial that ends mid-session closes at once, without a database read per file."""
    return int(max(STARTED, access.MANAGED.get("changed", 0)) + SESSION_HOURS * 3600)


def share_revoked() -> None:
    """For nginx (CIP_REVOKED_FILE, read by deploy/cip_auth.js), when nginx serves files itself: the revoked session
    hashes, and the line "access-before <time>" (stale_before)."""
    path = os.environ.get("CIP_REVOKED_FILE")
    if path:
        part = f"{path}.{os.getpid()}"
        with open(part, "w") as f:
            f.write("\n".join([f"access-before {stale_before()}", *sorted(REVOKED)]))
        os.replace(part, path)


def revoke(hashes: list[str], email: str | None = None) -> None:
    REVOKED.update(hashes)
    share_revoked()
    try:
        with get_engine("api_write").begin() as conn:
            if email:
                conn.execute(text("UPDATE cip_access_session SET revoked_at = CURRENT_TIMESTAMP WHERE email = :e AND revoked_at IS NULL"), {"e": email})
            for h in hashes:
                conn.execute(text("UPDATE cip_access_session SET revoked_at = CURRENT_TIMESTAMP WHERE session_hash = :h"), {"h": h})
    except Exception as exc:   # noqa: BLE001 — this worker refuses it already; others learn at their next poll once the table exists
        log.warning("Revocation not stored: %s", type(exc).__name__)


def load_revoked() -> None:
    """Every revoked, unexpired session (called by the API's minute poll), so all workers refuse them."""
    try:
        with get_engine("app").connect() as conn:
            REVOKED.update(r[0] for r in conn.execute(text(
                "SELECT session_hash FROM cip_access_session WHERE revoked_at IS NOT NULL AND expires_at > CURRENT_TIMESTAMP")))
    except Exception as exc:   # noqa: BLE001 — sql/008 not applied yet: say so once, keep serving
        if not getattr(load_revoked, "warned", False):
            log.warning("Revoked sessions not loaded (is sql/008_access.sql applied?): %s", type(exc).__name__)
            load_revoked.warned = True
        return
    share_revoked()


@router.get("/auth/logout")
async def logout(request: Request) -> Response:
    session = read(request.cookies.get(COOKIE, ""))
    if session:
        await run_in_threadpool(revoke, [digest(session["sid"])])
        audit.record(request, "sign_out", who=access.profile(session["email"]) or {"email": session["email"]})
    found = provider()
    meta = None
    if found:
        try:
            meta = await run_in_threadpool(endpoints, found["issuer"])
        except Exception:
            meta = None
    # the provider's session ends too, or the next "Sign in" lets the same person straight back in without a password;
    # either way the browser lands on the home page
    home = callback_url(request).rsplit("/auth/", 1)[0] + "/"
    id_token = request.cookies.get(ID_TOKEN, "")
    if meta and meta.get("end_session_endpoint") and id_token:
        target = meta["end_session_endpoint"] + "?" + urlencode({"id_token_hint": id_token, "post_logout_redirect_uri": home})
    else:
        target = "/"
    response = RedirectResponse(target, status_code=303)
    response.delete_cookie(COOKIE)
    response.delete_cookie(ID_TOKEN, path="/auth")
    return response


@router.get("/auth/check", status_code=204)
async def auth_check(who: dict = Depends(user)) -> Response:
    """nginx auth_request: 204 if the session cookie is valid (HMAC only, no database), else 401."""
    return Response(status_code=204)


@router.post("/api/v1/admin/sessions/revoke")
async def revoke_person(request: Request, who: dict = Depends(admin)) -> dict:
    """{email}: sign that person out everywhere (offboarding). Admins only."""
    email = str((await json_body(request)).get("email") or "").strip().lower()
    if "@" not in email:
        raise HTTPException(422, "Name the email to sign out")
    def hashes() -> list[str]:
        with get_engine("app").connect() as conn:
            return [r[0] for r in conn.execute(text("SELECT session_hash FROM cip_access_session WHERE email = :e"), {"e": email})]
    found = await run_in_threadpool(hashes)
    await run_in_threadpool(revoke, found, email)
    audit.record(request, "revoke_sessions", target=email, detail={"sessions": len(found)})
    return {"email": email, "revoked": len(found)}
