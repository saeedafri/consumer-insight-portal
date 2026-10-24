"""API keys for the public API and the MCP connector: `Authorization: Bearer cip_…` instead of a sign-in cookie.

A key acts as the person it was issued to, with their access (config/access.yml): the same surveys, features and
rate limits. Only a SHA-256 of each key is kept, in CIP_API_KEYS (default ~/.config/cip/api_keys.yml, outside the
repository); the key itself is shown once, when it is made.

    python -m app.core.api_keys new ana@coresight.com "Ana's Claude"
    python -m app.core.api_keys list
    python -m app.core.api_keys revoke cip_AbC1        # by the first characters shown in list
"""
from __future__ import annotations

import argparse
import hashlib
import os
import secrets
import time
from pathlib import Path

import yaml

FILE = Path(os.environ.get("CIP_API_KEYS") or Path.home() / ".config/cip/api_keys.yml")
PREFIX = "cip_"
_cache: dict = {"mtime": None, "keys": {}}


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def keys() -> dict:
    """{sha256: {email, name, shown, created}}, re-read when the file changes."""
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
