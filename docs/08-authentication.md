# Authentication

The portal serves respondent-level consumer survey data — 404 interviews per
wave with demographics and every answer given. It is client-confidential and
not anonymised beyond the panel's own identifiers, so it does not go on a
shared host without a login.

---

## Providers

Chosen by `AUTH_PROVIDER`, or inferred from what is configured.

| Provider | What it is | When |
|---|---|---|
| `oidc` | Coresight SSO — the same identity provider SIP-Prod uses | production |
| `local` | email allowlist + a shared passphrase | STG today, before SSO is wired |
| `off` | no login at all | a laptop, and nowhere else |

`off` is not a quiet default. On anything other than `APP_ENV=LOCAL` the portal
refuses to render and says why, because an open portal on a staging host is
how survey microdata leaks.

## Local testing bypass

Until OIDC/SSO is wired in (the same flow as MDP and SIP), local testing skips
sign-in: with `APP_ENV=LOCAL` **and** `DEBUG=true`, `auth.debug_user()` returns
`LOCAL_TEST_USER_EMAIL` (default `local@test.com`) and every page treats that as
the signed-in user — saved views and export provenance are attributed to it.
Neither condition alone is enough, and `tests/test_auth.py` proves it never
activates on STAGING or PRODUCTION.

## Configuration

```bash
# STG today — works without the IdP
AUTH_PROVIDER=local
AUTH_ALLOWED_EMAILS=@coresight.com        # a domain, or named addresses
AUTH_SHARED_PASSPHRASE=<set by IT>
AUTH_SESSION_HOURS=12

# Production, once IT has registered the client
AUTH_PROVIDER=oidc
IDP_BASE_URL=https://<coresight idp>
IDP_TOKEN_URL=https://<coresight idp>/oauth/token
IDP_USERINFO_URL=https://<coresight idp>/oauth/userinfo
OIDC_CLIENT_ID=<from IT>
OIDC_CLIENT_SECRET=<from IT>
```

The variable names deliberately match SIP-Prod's, so the same values work in
both and IT registers one client rather than two.

### What IT needs to register for SSO

1. A **redirect URI** for wherever this portal is hosted, e.g.
   `https://cip-stg.coresight.com/login`. A mismatch here is the single most
   common cause of a sign-in that starts and never completes.
2. The **scopes** `openid email profile`.
3. Whether entitlement is carried in a claim we should check, or whether
   `AUTH_ALLOWED_EMAILS` stays the gate.

## How a session works

The header nav uses plain anchors — the same pattern as the Market Data Portal
— so moving between pages is a **full page load and a brand-new Streamlit
session**. Anything kept only in `st.session_state` is gone by the time the
next page renders. That is why sessions here are cookie-backed:

- the cookie (`csi_session`) carries an opaque id and nothing else;
- `csi_auth_session` carries the email, provider, expiry and the host/user
  agent at sign-in;
- every page recovers the user from that row, so a sign-in survives navigation;
- an admin revokes a session by setting `revoked_at` — it stops working on the
  next page load, without waiting for expiry.

## The public API

Identical in shape to market-data-stg's `auth_manager`, so the Coresight OIDC
manager can be dropped in by swapping one provider without touching a page:

```python
from app.core import auth

user = auth.require_auth("analysis")   # returns the user, or redirects to login
auth.is_authenticated()
auth.get_current_user()                # email
auth.logout()
```

## What is tested

`tests/test_auth.py` covers the parts that matter — the refusals:

- a bare `@coresight.com` allowlist entry admits the domain and **not itself**,
  so typing the domain into the email box does not sign you in;
- `john@coresight.com.evil.com` is rejected;
- an empty allowlist admits nobody;
- OIDC claims without an email, or for an unentitled account, are refused;
- expiry is honoured, and timestamps parse from both MySQL (datetime) and
  SQLite (string).

## What is NOT tested here

**The OIDC flow itself.** Completing an authorization-code exchange needs the
real IdP, its client secret and a registered redirect URI — none of which
exist in this environment. `sign_in_oidc()` takes verified claims and does the
entitlement check and session creation; the token exchange in front of it is
the one piece that has to be wired and tested against the live IdP.

Until then, run `local`. It is real protection — allowlist plus passphrase,
compared with `hmac.compare_digest`, with every sign-in recorded — and it does
not pretend to be SSO.
