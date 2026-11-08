"""The portal's session cookie: "email|products|expires|session id|scope", HMAC-SHA256 signed with CIP_SESSION_SECRET.
The API issues and checks it (api/signin.py), nginx checks it before every data file (deploy/cip_auth.js), and the
publish step signs one to warm nginx's answer cache (etl/publish.warm_nginx). The session id lets one sign-in be
revoked (sql/008_access.sql stores only its hash); scope is "*" for someone who sees everything (shared/core/access.py)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import time

SESSION_HOURS = 12
REVOKED: set[str] = set()   # hashes of revoked session ids: filled by sign-out and every API poll (api/main.py)


def sign(value: str) -> str:
    key = os.environ.get("CIP_SESSION_SECRET", "").encode()
    return base64.urlsafe_b64encode(hmac.new(key, value.encode(), hashlib.sha256).digest()).decode().rstrip("=")


def same(first: str, second: str) -> bool:
    """Constant-time text comparison that also accepts non-ASCII text (hmac.compare_digest raises on it: a 500, not a 401)."""
    return hmac.compare_digest(first.encode(), second.encode())


def digest(sid: str) -> str:
    return hashlib.sha256(sid.encode()).hexdigest()


def issue(email: str, products: str = "*", hours: float = SESSION_HOURS, sid: str = "", scope: str = "*") -> str:
    value = f"{email}|{products}|{int(time.time() + hours * 3600)}|{sid or secrets.token_urlsafe(18)}|{scope}"
    return f"{base64.urlsafe_b64encode(value.encode()).decode()}.{sign(value)}"


def read(raw: str) -> dict | None:
    """The signed-in session in a cookie value, or None: unsigned, tampered, expired, revoked or an old format."""
    try:
        encoded, signature = raw.strip('"').rsplit(".", 1)
        value = base64.urlsafe_b64decode(encoded.encode()).decode()
        email, products, expires, sid, scope = value.split("|")
        live = int(expires) >= time.time()
    except ValueError:
        return None
    if not same(signature, sign(value)) or not live or digest(sid) in REVOKED:
        return None
    return {"email": email, "products": products.split(","), "expires": int(expires), "sid": sid, "scope": scope}
