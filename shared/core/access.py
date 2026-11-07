"""Who a signed-in person is to the portal and what they may do and see, from config/access.yml (role-based access):

  role         who they are: super_admin (the portal's owner), analyst (Coresight staff), client (an external
               organisation). Each role has a list of permissions (`roles:` in the file); can() is the one check
  permissions  admin_pages (Logs, Fieldwork, the audit log, revoking sessions), manage_team_items (remove anyone's
               boards and views), all_features (every feature and survey whatever the tier), unlimited (no rate limit)
  tier         the package of features and study types the role's people get (staff: `staff.tier`, clients: their own)

Who holds which role: `people:` in the file (the super admin), else staff by their email domain, else a client by
theirs. Adding a role is a few lines of config: its permissions, then its people. Every sign-in is recorded with the
role it had (cip_access_session, cip_access_log). Also: a client organisation (None for Coresight staff), a tier (a package of features and study types), and each
survey's owner and visibility. The API asks here on every request (dictionary lookups, no database), and the session
cookie carries the person's scope so nginx can tell a person who sees everything from one who must be filtered."""
from __future__ import annotations

import time
from functools import lru_cache

import yaml

from shared.core.config import REPO_ROOT

CONFIG = REPO_ROOT / "config" / "access.yml"
EVERYTHING = "*"     # the scope of a person who sees every survey and every feature


@lru_cache(maxsize=1)
def rules() -> dict:
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}


def profile(email: str) -> dict | None:
    """{email, role, tier, client, features, study_types} for an email, or None when config says to refuse it."""
    email = email.strip().lower()
    domain = email.rpartition("@")[2]
    r = rules()
    staff = r.get("staff") or {}
    client = next((cid for cid, c in (r.get("clients") or {}).items() if domain in (c.get("domains") or [])), None)
    named = next((role for role, emails in (r.get("people") or {}).items() if email in (emails or [])), None)
    if named:                                          # a role given by name (config `people:`): the super admin
        role, tier, client = named, staff.get("tier", "core"), None
    elif domain in (staff.get("domains") or []):
        role, tier, client = "analyst", staff.get("tier", "core"), None
    elif client:
        role, tier = "client", r["clients"][client].get("tier", "core")
    elif r.get("unknown", "refuse") == "refuse":
        return None
    else:
        role, tier = r["unknown"].get("role", "client"), r["unknown"].get("tier", "demo")
    if "all_features" in permissions_of(role):        # every feature and study type, whatever the tier
        tier = "enterprise"
    package = r["tiers"][tier]
    features = r["features"] if package["features"] == EVERYTHING else list(package["features"])
    return {"email": email, "role": role, "tier": tier, "client": client, "features": features,
            "study_types": package["study_types"]}


def permissions_of(role: str) -> set[str]:
    """A role's permissions from config/access.yml `roles:` ("*" = all of them)."""
    granted = ((rules().get("roles") or {}).get(role) or {}).get("permissions") or []
    return set(PERMISSIONS) if granted == EVERYTHING else set(granted)


PERMISSIONS = ("admin_pages", "manage_team_items", "all_features", "unlimited")


def can(person: dict, permission: str) -> bool:
    """The one role check: may this person do `permission` (one of PERMISSIONS)."""
    return permission in permissions_of(person["role"])


def internal(person: dict) -> bool:
    return person["client"] is None and person["role"] != "client"


def scope(person: dict) -> str:
    """"*" for someone who sees every survey and feature, else "client:tier": the key their filtered answers are cached
    under, and the part of the cookie nginx reads (deploy/cip_auth.js)."""
    if internal(person) and person["study_types"] == EVERYTHING and set(person["features"]) >= set(rules()["features"]):
        return EVERYTHING
    return f"{person['client'] or ''}:{person['tier']}"


def owner(wave: dict) -> dict:
    """{client, visibility} of one wave (needs survey_id and survey_family): a survey_id entry, else its family's."""
    surveys = rules().get("surveys") or {}
    found = (surveys.get("ids") or {}).get(wave["survey_id"]) or (surveys.get("families") or {}).get(wave.get("survey_family")) or {}
    return {"client": found.get("client"), "visibility": found.get("visibility", surveys.get("default_visibility", "all"))}


def sees(person: dict, wave: dict) -> bool:
    """May this person open this wave: their tier opens its study type, and its visibility admits them."""
    if person["study_types"] != EVERYTHING and wave.get("study_type") not in person["study_types"]:
        return False
    rule = owner(wave)
    if rule["visibility"] == "all" or internal(person):
        return True
    return rule["visibility"] == "client" and rule["client"] is not None and rule["client"] == person["client"]


def allows(person: dict, feature: str) -> bool:
    return feature in person["features"]


BUCKETS: dict[tuple[str, str], tuple[float, float]] = {}   # (email, kind) → (tokens left, when counted)


def spend(email: str, kind: str) -> bool:
    """One request from a per-person token bucket of `limits[kind]` a minute; False when it is empty.
    ponytail: per worker (2 workers allow twice the rate); a shared store if the limit must be exact."""
    person = profile(email) if "@" in email else None
    if person and can(person, "unlimited"):           # the super admin is never throttled
        return True
    rate = float((rules().get("limits") or {}).get(kind, 60))
    now = time.monotonic()
    tokens, at = BUCKETS.get((email, kind), (rate, now))
    tokens = min(rate, tokens + (now - at) * rate / 60)
    if tokens < 1:
        BUCKETS[(email, kind)] = (tokens, now)
        return False
    BUCKETS[(email, kind)] = (tokens - 1, now)
    return True
