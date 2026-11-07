"""API keys for the public API and the MCP connector: `Authorization: Bearer cip_…` instead of a sign-in cookie.

A key acts as the person it was issued to, with their access as it is at each request (shared/core/access.py
profile: the same surveys, features, menus chosen on the Access page and rate limits as their sign-in): taking a
feature away from someone takes it from their keys at once. Each person makes and revokes their own keys on the
Account page (api/main.py /api/v1/keys); a key cannot make keys. Only a SHA-256 of each key is kept, in a file:
CIP_API_KEYS, else /home/cip/api_keys.yml on Azure (permanent storage: survives deploys), else
~/.config/cip/api_keys.yml. No database read per request: the file is re-read only when it changes.

    python -m shared.core.api_keys new ana@coresight.com "Ana's Claude"
    python -m shared.core.api_keys list
    python -m shared.core.api_keys revoke cip_AbC1        # by the first characters shown in list
"""
from __future__ import annotations

import argparse
import os
import secrets
import time
from pathlib import Path

import yaml

from shared.core.session import digest   # the same SHA-256 the session ids are kept as

FILE = Path(os.environ.get("CIP_API_KEYS") or ("/home/cip/api_keys.yml" if Path("/home/cip").is_dir() else Path.home() / ".config/cip/api_keys.yml"))
MOST = 10   # keys per person: enough for a few tools, few enough to keep track of
PREFIX = "cip_"
_cache: dict = {"mtime": None, "keys": {}, "checked": -1e9}
CHECK_EVERY = 5   # seconds between looks at the file: /home is network storage on Azure, a look per request costs


def keys() -> dict:
    """{sha256: {email, name, shown, created}}, re-read when the file changes (looked at every CHECK_EVERY seconds;
    this process's own saves apply at once)."""
    if time.monotonic() - _cache["checked"] < CHECK_EVERY:
        return _cache["keys"]
    _cache["checked"] = time.monotonic()
    try:
        mtime = FILE.stat().st_mtime
    except OSError:
        return {}
    if mtime != _cache["mtime"]:
        _cache.update(mtime=mtime, keys=yaml.safe_load(FILE.read_text()) or {})
    return _cache["keys"]


def owner(token: str) -> str | None:
    """The email a key was issued to, or None for an unknown or revoked key."""
    if not token.startswith(PREFIX):
        return None
    found = keys().get(digest(token))
    return found["email"] if found else None


def save(found: dict) -> None:
    FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = FILE.with_suffix(".tmp")
    tmp.write_text(yaml.safe_dump(found, sort_keys=False))
    os.chmod(tmp, 0o600)
    tmp.replace(FILE)
    _cache.update(mtime=FILE.stat().st_mtime, keys=found, checked=time.monotonic())   # a revoked key stops at once


def mine(email: str) -> list[dict]:
    """One person's keys, newest first, as the Account page lists them (never the key itself)."""
    email = email.strip().lower()
    return sorted(({"shown": k["shown"], "name": k["name"], "created": k["created"]} for k in keys().values() if k["email"] == email),
                  key=lambda k: k["created"], reverse=True)


def revoke(email: str, shown: str) -> bool:
    """Revoke one of this person's own keys, by the first characters the list shows. False: no such key of theirs."""
    email = email.strip().lower()
    found = {h: k for h, k in keys().items() if not (k["email"] == email and k["shown"] == shown)}
    if len(found) == len(keys()):
        return False
    save(found)
    return True


def new(email: str, name: str) -> str:
    token = PREFIX + secrets.token_urlsafe(32)
    found = dict(keys())
    found[digest(token)] = {"email": email.strip().lower(), "name": name, "shown": token[:8],
                            "created": time.strftime("%Y-%m-%d")}
    save(found)
    return token


def main() -> int:
    ap = argparse.ArgumentParser(description="API keys for the CIP public API and MCP connector")
    sub = ap.add_subparsers(dest="command", required=True)
    made = sub.add_parser("new")
    made.add_argument("email")
    made.add_argument("name")
    sub.add_parser("list")
    gone = sub.add_parser("revoke")
    gone.add_argument("shown", help="the key's first characters, as list shows them")
    args = ap.parse_args()
    if args.command == "new":
        print(new(args.email, args.name))
        print("Shown once: store it now. It acts as", args.email)
    elif args.command == "list":
        for k in keys().values():
            print(f"{k['shown']}…  {k['email']:<35} {k['name']}  ({k['created']})")
    else:
        found = {h: k for h, k in keys().items() if not k["shown"].startswith(args.shown[:8])}
        save(found)
        print("Revoked" if len(found) < len(keys()) else "No such key")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
