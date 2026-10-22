"""The portal's session cookie: "email|products|expires", HMAC-SHA256 signed with CIP_SESSION_SECRET. The API issues
and checks it (api/main.py), nginx checks it before every data file (deploy/cip_auth.js), and the publish step signs
one to warm nginx's answer cache (etl/publish.warm_nginx)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time

SESSION_HOURS = 12


def sign(value: str) -> str:
    key = os.environ.get("CIP_SESSION_SECRET", "").encode()
    return base64.urlsafe_b64encode(hmac.new(key, value.encode(), hashlib.sha256).digest()).decode().rstrip("=")


def issue(email: str, products: str = "*", hours: float = SESSION_HOURS) -> str:
    value = f"{email}|{products}|{int(time.time() + hours * 3600)}"
    return f"{base64.urlsafe_b64encode(value.encode()).decode()}.{sign(value)}"
