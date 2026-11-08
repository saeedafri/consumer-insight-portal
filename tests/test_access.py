"""Who gets in and what they see, over HTTP: sign-in, the cookie, revocation, roles, client scoping, limits, the error
shape, security headers and the audit log (api/signin.py, shared/core/access.py, shared/core/audit.py)."""
import asyncio
import gzip
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from urllib.parse import urlsplit

import pytest
import sqlalchemy as sa

import api.main as api
from api import signin, team
from shared.core import access, audit, session


def call(path, cookie="", method="GET", body=b"", headers=None):
    """One request straight into the ASGI app: (status, headers as a dict of lists, body)."""
    parts = urlsplit(path)
    head = {**({"cookie": f"{signin.COOKIE}={cookie}"} if cookie else {}), **(headers or {})}
    if body:
        head.setdefault("content-type", "application/json")
        head.setdefault("content-length", str(len(body)))
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": method, "scheme": "http",
             "path": parts.path, "raw_path": parts.path.encode(), "query_string": parts.query.encode(), "root_path": "",
             "headers": [(k.encode(), v.encode()) for k, v in head.items()], "client": ("1.2.3.4", 1), "server": ("test", 80)}
    sent = []

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        sent.append(message)
    asyncio.run(api.app(scope, receive, send))
    found: dict = {}
    for k, v in sent[0].get("headers", []):
        found.setdefault(k.decode().lower(), []).append(v.decode())
    return sent[0]["status"], found, b"".join(m.get("body", b"") for m in sent[1:])


def put(root, rel, data):
    path = root / "api" / "v1" / f"{rel}.json.gz"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(json.dumps(data).encode()))


RULES = {
    "features": ["dashboards", "explorer", "crosstab", "trends", "search", "ask", "export", "boards", "audiences", "alerts", "saved_views",
                 "report", "sectors", "expectations", "fieldwork"],
    "chosen_only": ["fieldwork"],
    "feature_labels": {"sectors": "Sector databank"},
    "tiers": {"core": {"features": ["dashboards", "explorer", "trends", "search", "export", "boards", "report", "sectors", "expectations"],
                       "study_types": ["tracker", "adhoc"]},
              "enterprise": {"features": "*", "study_types": "*"}},
    "roles": {"super_admin": {"permissions": "*"}, "analyst": {"permissions": []}, "client": {"permissions": []}},
    "people": {"super_admin": ["boss@coresight.com"]},
    "staff": {"domains": ["coresight.com"], "tier": "enterprise"},
    "clients": {"acme": {"name": "Acme", "domains": ["acme.com"], "tier": "core"},
                "zeta": {"name": "Zeta", "domains": ["zeta.com"], "tier": "core"}},
    "surveys": {"default_visibility": "all", "families": {"ACME_STUDY": {"client": "acme", "visibility": "client"}}, "ids": {}},
    "unknown": "refuse", "limits": {"ask": 2, "export": 30, "audience": 60}, "min_audience": 30, "max_body_kb": 1,
}


@pytest.fixture()
def portal(tmp_path, monkeypatch, csi_db):
    monkeypatch.setenv("CIP_SESSION_SECRET", "test-secret")
    monkeypatch.setenv("CIP_TEAM_STAMP", str(tmp_path / "team.stamp"))
    monkeypatch.setattr(team, "STAMP", tmp_path / "team.stamp")
    monkeypatch.delenv("CIP_DEMO_LOGIN", raising=False)
    for key in ("CIP_OIDC_ISSUER", "CIP_OIDC_CLIENT_ID"):
        monkeypatch.delenv(key, raising=False)
    access.rules.cache_clear()
    monkeypatch.setattr(access, "rules", lambda: RULES)
    monkeypatch.setattr(api, "MAX_BODY", 1024)
    monkeypatch.setattr(access, "BUCKETS", {})
    monkeypatch.setattr(session, "REVOKED", set())
    monkeypatch.setattr(signin, "REVOKED", session.REVOKED)
    tracker = {"survey_id": 415, "survey_family": "CSI-US", "study_type": "tracker", "prior_survey_id": None, "wave_date": "2026-10-19", "title": "Weekly"}
    client = {"survey_id": 300, "survey_family": "ACME_STUDY", "study_type": "adhoc", "prior_survey_id": None, "wave_date": "2026-01-05", "title": "Acme"}
    put(tmp_path, "waves", [tracker, client])
    put(tmp_path, "waves/415/book", {"wave": tracker, "questions": []})
    put(tmp_path, "waves/300/book", {"wave": client, "questions": []})
    put(tmp_path, "questions/CSI-US/tracker/Q1", {"qcode": "Q1", "waves": [[415, "2026-10-19", 1]], "versions": ["Q?"], "answers": [],
                                                  "cuts": [], "w": [], "c": [], "a": [], "n": [], "b": []})
    monkeypatch.setattr(api, "PUBLISHED", tmp_path)
    monkeypatch.setattr(api, "RESULTS", type(api.RESULTS)())
    monkeypatch.setattr(api, "WAVES", ((), []))
    while not audit.PENDING.empty():
        audit.PENDING.get_nowait()
    return tmp_path


def signed(email, scope=None):
    return session.issue(email, scope=scope or access.scope(access.profile(email)))


def test_no_session_is_401_in_the_one_error_shape(portal):
    status, _, body = call("/api/v1/waves")
    assert status == 401 and json.loads(body) == {"detail": "Sign in required", "status": 401}
    old = session.sign("ana@coresight.com|*|9999999999")   # the 3-field cookie before session ids: refused
    import base64
    assert call("/api/v1/waves", base64.urlsafe_b64encode(b"ana@coresight.com|*|9999999999").decode() + "." + old)[0] == 401
    good = signed("ana@coresight.com")
    assert call("/api/v1/waves", good[:-2] + "xx")[0] == 401                          # tampered


def test_demo_sign_in_needs_cip_demo_login_and_the_cookie_is_secure_behind_https(portal, monkeypatch):
    monkeypatch.setenv("APP_ENV", "LOCAL")                     # LOCAL alone no longer opens the demo sign-in
    assert call("/auth/dev-login")[0] == 404
    status, _, body = call("/auth/login")
    assert status == 503 and b"not set up" in body             # no provider, no demo: a page that says so
    monkeypatch.setenv("CIP_DEMO_LOGIN", "1")
    status, head, _ = call("/auth/login?next=/w/415")
    assert status == 303 and head["location"] == ["/auth/dev-login?next=%2Fw%2F415"]
    status, head, _ = call("/auth/dev-login?email=ana@coresight.com&next=/w/415", headers={"x-forwarded-proto": "https"})
    cookie = next(c for c in head["set-cookie"] if c.startswith("cip_session="))
    assert status == 303 and "HttpOnly" in cookie and "Secure" in cookie and head["location"] == ["/w/415"]
    assert "strict-transport-security" in head
    status, head, _ = call("/auth/dev-login?email=ana@coresight.com")
    assert "Secure" not in next(c for c in head["set-cookie"] if c.startswith("cip_session="))   # plain http: no Secure
    assert call("/auth/dev-login?email=someone@gmail.com")[0] == 403   # unknown emails are refused by this config
    assert call("/auth/dev-login?email=ana@coresight.com&next=//evil.example")[1]["location"] == ["/"]   # same site only


def test_sign_out_revokes_the_session_and_is_audited(portal):
    cookie = signed("ana@coresight.com")
    assert call("/api/v1/me", cookie)[0] == 200
    assert call("/auth/logout", cookie)[0] == 303
    assert call("/api/v1/me", cookie)[0] == 401
    assert audit.write_pending() == 1
    with api.get_engine("app").connect() as conn:
        assert conn.execute(sa.text("SELECT email, action, ip_hash IS NOT NULL FROM cip_access_log")).one() == ("ana@coresight.com", "sign_out", 1)


def test_me_and_methodology_have_the_agreed_shapes_and_openapi_needs_a_session(portal):
    status, _, body = call("/api/v1/me", signed("boss@coresight.com"))
    me = json.loads(body)
    assert status == 200 and set(me) == {"email", "name", "role", "tier", "client", "features", "permissions"} and me["role"] == "super_admin"
    assert json.loads(call("/api/v1/me", signed("pat@acme.com"))[2])["client"] == "acme"
    method = json.loads(call("/api/v1/methodology", signed("pat@acme.com"))[2])
    assert method["weighting"] == "none" and "small_cells" in method and "significance" in method
    assert call("/api/v1/openapi.json")[0] == 401 and call("/api/v1/openapi.json", signed("pat@acme.com"))[0] == 200
    assert json.loads(call("/healthz")[2]).keys() == {"ok", "build"}           # public: no internals
    assert call("/healthz", method="HEAD")[0] == 200   # uptime checks send HEAD; it was a 404 page (uvicorn drops the body)
    assert call("/api/v1/admin/health", signed("pat@acme.com"))[0] == 403


def test_a_client_sees_its_own_study_and_not_anothers_and_waves_say_where_they_came_from(portal):
    acme, zeta, staff = signed("pat@acme.com"), signed("max@zeta.com"), signed("ana@coresight.com")
    assert access.scope(access.profile("ana@coresight.com")) == "*" and access.scope(access.profile("pat@acme.com")) == "acme:core"
    ids = lambda cookie: [w["survey_id"] for w in json.loads(call("/api/v1/waves", cookie)[2])]   # noqa: E731
    assert ids(staff) == [415, 300] and ids(acme) == [415, 300] and ids(zeta) == [415]
    assert call("/api/v1/waves/300/book", zeta)[0] == 404 and call("/api/v1/waves/300/book", acme)[0] == 200
    wave = json.loads(call("/api/v1/waves/415/book", zeta)[2])["wave"]
    assert wave["population"] == "US adults 18+" and wave["weighting"] == "unweighted" and wave["verified"] is True
    assert {"in_field", "client", "visibility"} <= wave.keys()
    assert json.loads(call("/api/v1/waves/300/book", acme)[2])["wave"]["population"] == "Survey respondents"
    assert call("/api/v1/waves/415/crosstab?q=Q1&by=gender,generation", acme)[0] == 403   # core has no cross-tabs


def test_the_unmasked_trend_routes_are_gone(portal):
    cookie = signed("ana@coresight.com")
    assert call("/api/v1/trend?survey_id=415&q=Q1", cookie)[0] == 404
    assert call("/api/v1/trends/CSI-US/tracker/Q1/total/Total", cookie)[0] == 404


def test_bad_bodies_are_422_or_413_never_500_and_ask_is_rate_limited(portal):
    cookie = signed("ana@coresight.com")
    status, _, body = call("/api/v1/boards", cookie, "POST", b"{not json")
    assert status == 422 and json.loads(body)["status"] == 422
    assert call("/api/v1/boards", cookie, "POST", b"[1, 2]")[0] == 422
    assert call("/api/v1/boards", cookie, "POST", b'{"name": "' + b"x" * 2000 + b'"}')[0] == 413
    assert [call("/api/v1/ask", cookie, "POST", b'{"question": "holiday"}')[0] for _ in range(3)] == [200, 200, 429]


def test_every_answer_carries_the_security_headers(portal):
    _, head, _ = call("/api/v1/waves")
    assert head["x-frame-options"] == ["DENY"] and head["x-content-type-options"] == ["nosniff"]
    assert "frame-ancestors 'none'" in head["content-security-policy"][0] and "referrer-policy" in head


def test_team_boards_are_scoped_to_the_owners_organisation_and_admins_remove_anything(portal):
    acme, zeta, boss = signed("pat@acme.com"), signed("max@zeta.com"), signed("boss@coresight.com")
    board = json.loads(call("/api/v1/boards", acme, "POST", b'{"name": "Acme read-out"}')[2])["board_id"]
    assert [b["name"] for b in json.loads(call("/api/v1/boards", acme)[2])] == ["Acme read-out"]
    assert json.loads(call("/api/v1/boards", zeta)[2]) == [] and call(f"/api/v1/boards/{board}", zeta)[0] == 404
    spec = json.dumps({"url": "/w/415", "spec": {"name": "t", "header": ["a"], "rows": [[1]]}}).encode()
    assert call(f"/api/v1/boards/{board}/items", zeta, "POST", spec)[0] == 404       # no pinning onto another client's board
    assert json.loads(call("/api/v1/team/summary", acme)[2])["boards"][0]["board_id"] == board
    assert json.loads(call("/api/v1/team/summary", acme)[2])["alerts"] == []          # core has no alerts: empty, not an error
    assert call(f"/api/v1/boards/{board}", boss, "DELETE")[0] == 204
    assert json.loads(call("/api/v1/boards", acme)[2]) == []                          # the write cleared the cached list
    audit.write_pending()
    status, _, body = call("/api/v1/admin/audit", boss)
    assert status == 200 and [r["action"] for r in json.loads(body)["rows"]][:2] == ["board_remove", "board_new"]
    assert call("/api/v1/admin/audit", acme)[0] == 403


def test_a_question_file_for_a_filtered_person_keeps_only_their_waves():
    doc = {"waves": [[1, "a", 1], [2, "b", 1]], "w": [0, 1, 1], "c": [0, 0, 1], "a": [0, 0, 0], "n": [5, 6, 7], "b": [9, 9, 9]}
    assert api.only_waves(doc, {2}) == {"waves": [[2, "b", 1]], "w": [0, 0], "c": [0, 1], "a": [0, 0], "n": [6, 7], "b": [9, 9]}


def test_published_paths_never_climb_out():
    assert api.published_file("waves", "1", "cuts", "x/../../book") is None and api.published_file("..", "waves") is None


def test_every_feature_the_portal_checks_is_one_the_config_knows():
    """frontend/src hides a link whose feature a sign-in lacks: a name missing from config/access.yml hides it from everyone
    (the Launch schedule link, 23 Oct 2026)."""
    from pathlib import Path
    import re
    checked = {m for f in Path("frontend/src").rglob("*.tsx") for m in re.findall(r'allowed\(me, "([a-z_]+)"\)', f.read_text())}
    assert checked and checked <= set(access.rules()["features"])
    assert set(access.profile("analyst@coresight.com")["features"]) >= checked   # staff see every page


def test_the_weekly_report_is_served_as_published_and_a_wave_without_one_says_so(portal):
    put(portal, "waves/415/report", {"survey_id": 415, "wave_date": "2026-10-19", "three_points": []})
    status, _, body = call("/api/v1/waves/415/report", signed("ana@coresight.com"))
    assert status == 200 and json.loads(body)["wave_date"] == "2026-10-19"
    status, _, body = call("/api/v1/waves/300/report", signed("ana@coresight.com"))
    assert status == 404 and "no weekly report" in json.loads(body)["detail"]
    assert call("/api/v1/waves/415/report")[0] == 401                       # signed out: nothing


def test_the_tracker_views_are_served_as_published_and_say_so_before_the_first_publish(portal):
    for name in ("sectors", "expectations"):
        assert call(f"/api/v1/{name}", signed("ana@coresight.com"))[0] == 404              # not published yet
        put(portal, name, {"sectors": [], "events": []})
        status, _, body = call(f"/api/v1/{name}", signed("pat@acme.com"))                 # a client who sees every tracker wave
        assert status == 200 and "sectors" in json.loads(body)
        assert call(f"/api/v1/{name}")[0] == 401                                           # signed out: nothing



def test_the_tracker_views_refuse_someone_who_may_not_open_every_tracker_wave(portal, monkeypatch):
    put(portal, "sectors", {"sectors": []})
    monkeypatch.setitem(RULES["surveys"], "ids", {415: {"client": "acme", "visibility": "client"}})   # one tracker wave: Acme's
    assert call("/api/v1/sectors", signed("pat@acme.com"))[0] == 200
    status, _, body = call("/api/v1/sectors", signed("zed@zeta.com"))
    assert status == 403 and "subscription" in json.loads(body)["detail"]


def test_sign_in_through_coresights_own_identity_provider(portal, monkeypatch):
    """csr-idp (coresight.com, SIP's sign-in) has no discovery document, proves PKCE "plain", may not echo the nonce
    and puts the email under data.wp_user: the whole round trip with a stand-in for its token endpoint."""
    import base64
    import time
    from urllib.parse import parse_qs
    import requests
    for key, value in {"CIP_OIDC_ISSUER": "https://coresight.com", "CIP_OIDC_CLIENT_ID": "sip-app",
                       "CIP_OIDC_AUTHORIZE_URL": "https://coresight.com/csr-idp/authorize",
                       "CIP_OIDC_TOKEN_URL": "https://coresight.com/csr-idp/token", "CIP_OIDC_PKCE": "plain"}.items():
        monkeypatch.setenv(key, value)
    status, head, _ = call("/auth/login?next=/app/sectors")
    sent = parse_qs(urlsplit(head["location"][0]).query)
    assert status == 303 and head["location"][0].startswith("https://coresight.com/csr-idp/authorize?")
    assert sent["code_challenge_method"] == ["plain"] and sent["client_id"] == ["sip-app"]
    login = head["set-cookie"][0].split(";")[0]                                  # cip_login=<signed state>
    token = {"iss": "https://coresight.com", "aud": "sip-app", "exp": time.time() + 60,
             "data": {"wp_user": {"user_email": "Ana@Coresight.com"}}}
    body = "x." + base64.urlsafe_b64encode(json.dumps(token).encode()).decode().rstrip("=") + ".x"

    class Answer:
        def raise_for_status(self): pass
        def json(self): return {"id_token": body, "access_token": "a"}
    monkeypatch.setattr(requests, "post", lambda url, **kw: Answer() if url.endswith("/csr-idp/token") else None)
    status, head, _ = call(f"/auth/callback?code=c&state={sent['state'][0]}", headers={"cookie": login})
    assert status in (302, 303) and any(c.startswith(signin.COOKIE + "=") for c in head["set-cookie"])


def test_sign_in_through_stage3_coresight_idp(portal, monkeypatch, caplog):
    """stage3.coresight.com with cip-staging client configuration; CIP_OIDC_LOG_CLAIMS=1 logs the claims, never the tokens."""
    import base64
    import time
    from urllib.parse import parse_qs
    import requests
    for key, value in {"CIP_OIDC_ISSUER": "https://stage3.coresight.com", "CIP_OIDC_CLIENT_ID": "cip-staging",
                       "CIP_OIDC_CLIENT_SECRET": "test-secret",
                       "CIP_OIDC_AUTHORIZE_URL": "https://stage3.coresight.com/csr-idp/authorize",
                       "CIP_OIDC_TOKEN_URL": "https://stage3.coresight.com/csr-idp/token", "CIP_OIDC_PKCE": "plain",
                       "CIP_OIDC_LOG_CLAIMS": "1"}.items():
        monkeypatch.setenv(key, value)
    caplog.set_level("INFO", logger="cip.signin")
    status, head, _ = call("/auth/login?next=/app/explore")
    sent = parse_qs(urlsplit(head["location"][0]).query)
    assert status == 303 and head["location"][0].startswith("https://stage3.coresight.com/csr-idp/authorize?")
    assert sent["code_challenge_method"] == ["plain"] and sent["client_id"] == ["cip-staging"]
    login = head["set-cookie"][0].split(";")[0]
    token = {"iss": "https://stage3.coresight.com", "aud": "cip-staging", "exp": time.time() + 60,
             "data": {"wp_user": {"user_email": "dataautomation@coresight.com", "roles": ["administrator"]}}}
    body = "x." + base64.urlsafe_b64encode(json.dumps(token).encode()).decode().rstrip("=") + ".x"

    class Answer:
        def raise_for_status(self): pass
        def json(self): return {"id_token": body, "access_token": "secret-access", "scope": "openid email"}
    monkeypatch.setattr(requests, "post", lambda url, **kw: Answer() if url.endswith("/csr-idp/token") else None)
    status, head, _ = call(f"/auth/callback?code=c&state={sent['state'][0]}", headers={"cookie": login})
    assert status in (302, 303) and any(c.startswith(signin.COOKIE + "=") for c in head["set-cookie"])
    assert "administrator" in caplog.text and '"scope": "openid email"' in caplog.text
    assert "secret-access" not in caplog.text and body not in caplog.text
    assert any(c.startswith(f"{signin.ID_TOKEN}={body}") for c in head["set-cookie"])   # kept for /auth/logout


def test_logout_never_500s_when_idp_has_no_discovery(portal, monkeypatch):
    """Logging out when the provider has no openid-configuration returns 200 and drops the cookie."""
    for key, value in {"CIP_OIDC_ISSUER": "https://stage3.coresight.com", "CIP_OIDC_CLIENT_ID": "cip-staging",
                       "CIP_OIDC_AUTHORIZE_URL": "https://stage3.coresight.com/csr-idp/authorize",
                       "CIP_OIDC_TOKEN_URL": "https://stage3.coresight.com/csr-idp/token"}.items():
        monkeypatch.setenv(key, value)
    status, head, body = call("/auth/logout", signed("dataautomation@coresight.com"))
    assert status == 303 and head["location"] == ["/"]                        # the home page
    assert any(c.startswith(signin.COOKIE + "=;") or "Max-Age=0" in c for c in head.get("set-cookie", []))


def test_logout_ends_the_providers_session_with_the_id_token_then_lands_home(portal, monkeypatch):
    """csr-idp ends its own session only with id_token_hint; without it "Sign in" lets the same person straight back in."""
    from urllib.parse import parse_qs
    for key, value in {"CIP_OIDC_ISSUER": "https://stage3.coresight.com", "CIP_OIDC_CLIENT_ID": "cip-staging",
                       "CIP_OIDC_AUTHORIZE_URL": "https://stage3.coresight.com/csr-idp/authorize",
                       "CIP_OIDC_LOGOUT_URL": "https://stage3.coresight.com/csr-idp/logout/",
                       "CIP_OIDC_REDIRECT_URI": "http://192.168.1.38:8001/auth/callback"}.items():
        monkeypatch.setenv(key, value)
    status, head, _ = call("/auth/logout", signed("dataautomation@coresight.com") + f"; {signin.ID_TOKEN}=h.p.s")
    sent = parse_qs(urlsplit(head["location"][0]).query)
    assert status == 303 and head["location"][0].startswith("https://stage3.coresight.com/csr-idp/logout/?")
    assert sent == {"id_token_hint": ["h.p.s"], "post_logout_redirect_uri": ["http://192.168.1.38:8001/"]}


def test_a_token_from_another_issuer_is_refused_unless_named(portal, monkeypatch):
    """Only the configured issuer's tokens sign in; CIP_OIDC_TOKEN_ISSUER names a different iss the provider really uses."""
    import base64
    import time
    from urllib.parse import parse_qs
    import requests
    for key, value in {"CIP_OIDC_ISSUER": "https://stage3.coresight.com", "CIP_OIDC_CLIENT_ID": "cip-staging",
                       "CIP_OIDC_AUTHORIZE_URL": "https://stage3.coresight.com/csr-idp/authorize",
                       "CIP_OIDC_TOKEN_URL": "https://stage3.coresight.com/csr-idp/token", "CIP_OIDC_PKCE": "plain"}.items():
        monkeypatch.setenv(key, value)
    token = {"iss": "https://coresight.com", "aud": "cip-staging", "exp": time.time() + 60,
             "data": {"wp_user": {"user_email": "dataautomation@coresight.com"}}}
    body = "x." + base64.urlsafe_b64encode(json.dumps(token).encode()).decode().rstrip("=") + ".x"

    class Answer:
        def raise_for_status(self): pass
        def json(self): return {"id_token": body}
    monkeypatch.setattr(requests, "post", lambda url, **kw: Answer())

    def sign_in() -> int:
        _, head, _ = call("/auth/login")
        state = parse_qs(urlsplit(head["location"][0]).query)["state"][0]
        return call(f"/auth/callback?code=c&state={state}", headers={"cookie": head["set-cookie"][0].split(";")[0]})[0]
    assert sign_in() == 400
    monkeypatch.setenv("CIP_OIDC_TOKEN_ISSUER", "https://coresight.com")
    assert sign_in() in (302, 303)


def test_the_fieldwork_record_is_for_admins_only(portal):
    assert call("/api/v1/admin/fieldwork", signed("boss@coresight.com"))[0] == 404     # not collected yet: says so
    put(portal, "admin/fieldwork", {"surveys": [], "archive": []})
    status, _, body = call("/api/v1/admin/fieldwork", signed("boss@coresight.com"))
    assert status == 200 and json.loads(body) == {"surveys": [], "archive": []}
    assert call("/api/v1/admin/fieldwork", signed("ana@coresight.com"))[0] == 403      # staff, not an admin
    assert call("/api/v1/admin/fieldwork", signed("pat@acme.com"))[0] == 403           # a client


def test_the_home_pages_figures_need_no_sign_in(portal):
    assert call("/api/v1/public/facts")[0] == 404                                        # not published yet
    put(portal, "public/facts", {"waves": 2, "latestDate": "2026-10-19"})
    status, _, body = call("/api/v1/public/facts")                                     # no cookie
    assert status == 200 and json.loads(body)["latestDate"] == "2026-10-19"


def test_the_super_admin_has_every_permission_and_feature_and_no_rate_limit(portal, monkeypatch):
    monkeypatch.setitem(RULES["people"], "super_admin", ["owner@coresight.com"])
    monkeypatch.setitem(RULES["tiers"], "staff", {"features": ["dashboards"], "study_types": ["tracker"]})
    monkeypatch.setitem(RULES["staff"], "tier", "staff")                      # even if staff get a small package
    me = access.profile("owner@coresight.com")
    assert me["role"] == "super_admin" and set(me["features"]) == set(RULES["features"]) and me["study_types"] == "*"
    assert all(access.can(me, p) for p in access.PERMISSIONS) and access.scope(me) == access.EVERYTHING
    assert all(access.spend("owner@coresight.com", "ask") for _ in range(100))   # limits: ask is 2 a minute here
    put(portal, "admin/fieldwork", {"surveys": [], "archive": []})
    assert call("/api/v1/admin/fieldwork", signed("owner@coresight.com"))[0] == 200
    said = json.loads(call("/api/v1/me", signed("owner@coresight.com"))[2])
    assert said["role"] == "super_admin" and "admin_pages" in said["permissions"]
    analyst = access.profile("ana@coresight.com")                            # staff: analysts, no admin pages
    assert analyst["role"] == "analyst" and not any(access.can(analyst, p) for p in access.PERMISSIONS)
    assert json.loads(call("/api/v1/me", signed("ana@coresight.com"))[2])["permissions"] == []
    assert call("/api/v1/admin/fieldwork", signed("ana@coresight.com"))[0] == 403


def test_a_refused_sign_in_is_recorded_with_who_tried(portal, monkeypatch):
    monkeypatch.setenv("CIP_DEMO_LOGIN", "1")
    recorded = []
    monkeypatch.setattr(audit, "record", lambda request, action, **kw: recorded.append((action, kw["who"]["email"], kw.get("detail"))))
    assert call("/auth/dev-login?email=stranger@unknown.org")[0] == 403                # RULES: unknown emails refused
    assert recorded == [("sign_in_failed", "stranger@unknown.org", {"reason": "not entitled"})]



def test_the_super_admin_chooses_each_roles_menus_and_they_apply_at_once(portal, monkeypatch):
    """The Access screen: the super admin moves Sector databank off the analysts' menu; analysts lose it (menu and data)
    within the same request cycle, and only the super admin may see or change the choice."""
    monkeypatch.setattr(access, "MANAGED", {"at": -1e9, "roles": {}})           # read this test's database
    boss, ana = signed("boss@coresight.com"), signed("ana@coresight.com")
    status, _, body = call("/api/v1/admin/roles", boss)
    roles = {r["role"]: r for r in json.loads(body)["roles"]}
    assert status == 200 and "super_admin" not in roles and "sectors" in roles["analyst"]["features"] and not roles["analyst"]["chosen"]
    assert {"key": "sectors", "label": "Sector databank"} in json.loads(body)["features"]
    keep = [f for f in roles["analyst"]["features"] if f != "sectors"]
    status, _, body = call("/api/v1/admin/roles/analyst", boss, "PUT", json.dumps({"features": keep + ["not-a-feature"]}).encode())
    assert status == 200 and json.loads(body)["features"] == keep                 # unknown names dropped
    assert "sectors" not in access.profile("ana@coresight.com")["features"]
    put(portal, "sectors", {"sectors": []})
    assert call("/api/v1/sectors", ana)[0] == 403 and call("/api/v1/sectors", boss)[0] == 200   # the super admin keeps all
    assert call("/api/v1/admin/roles", ana)[0] == 403                             # analysts never see the Access screen
    assert call("/api/v1/admin/roles/super_admin", boss, "PUT", b'{"features": []}')[0] == 404


def test_an_identity_provider_sign_in_opens_admin_pages_without_the_token(portal, monkeypatch):
    monkeypatch.setenv("CIP_DEMO_LOGIN", "1")
    monkeypatch.setenv("CIP_ADMIN_TOKEN", "t" * 40)
    put(portal, "admin/fieldwork", {"surveys": [], "archive": []})
    demo = signed("boss@coresight.com")                                            # a session the demo sign-in made
    assert call("/api/v1/admin/fieldwork", demo)[0] == 403
    assert call("/api/v1/admin/fieldwork", demo, headers={"x-cip-admin-token": "t" * 40})[0] == 200
    sid = "proven-session"
    signin.remember(sid, access.profile("boss@coresight.com"), "oidc")             # what /auth/callback records
    sso = session.issue("boss@coresight.com", sid=sid, scope="*")
    assert call("/api/v1/admin/fieldwork", sso)[0] == 200                          # no token: the provider proved the email



def test_fieldwork_stays_with_admins_until_the_super_admin_turns_it_on_for_a_role(portal, monkeypatch):
    monkeypatch.setattr(access, "MANAGED", {"at": -1e9, "roles": {}})
    boss, ana = signed("boss@coresight.com"), signed("ana@coresight.com")
    put(portal, "fieldwork", {"surveys": [{"path": "p/1", "timeline": [["2026-11-02T13:25", None, "Launched"]]}], "archive": []})
    assert "fieldwork" not in access.profile("ana@coresight.com")["features"]                 # no package includes it
    assert call("/api/v1/fieldwork", ana)[0] == 403
    roles = {r["role"]: r for r in json.loads(call("/api/v1/admin/roles", boss)[2])["roles"]}
    assert "fieldwork" not in roles["analyst"]["features"]
    status, _, _ = call("/api/v1/admin/roles/analyst", boss, "PUT", json.dumps({"features": roles["analyst"]["features"] + ["fieldwork"]}).encode())
    assert status == 200 and call("/api/v1/fieldwork", ana)[0] == 200                          # the shared file: no emails
    assert call("/api/v1/admin/fieldwork", ana)[0] == 403                                      # the deletion schedule stays with admins



def test_a_trial_that_ends_closes_at_once_without_a_page_refresh(portal, monkeypatch, tmp_path):
    """An analyst signed in an hour ago with a "sees everything" cookie; the super admin takes the Sector databank away.
    The API refuses at once (it checks access on every request), hands back a cookie that no longer says "sees
    everything", and tells nginx that older such cookies are stale, so nginx stops serving files to it directly."""
    monkeypatch.setattr(access, "MANAGED", {"at": -1e9, "roles": {}})
    monkeypatch.setenv("CIP_REVOKED_FILE", str(tmp_path / "revoked"))
    boss, ana = signed("boss@coresight.com"), session.issue("ana@coresight.com", hours=11, scope="*")
    put(portal, "sectors", {"sectors": []})
    assert call("/api/v1/sectors", ana)[0] == 200
    roles = {r["role"]: r for r in json.loads(call("/api/v1/admin/roles", boss)[2])["roles"]}
    keep = [f for f in roles["analyst"]["features"] if f != "sectors"]
    assert call("/api/v1/admin/roles/analyst", boss, "PUT", json.dumps({"features": keep}).encode())[0] == 200
    status, headers, _ = call("/api/v1/sectors", ana)
    fresh = next(c for c in headers["set-cookie"] if c.startswith(signin.COOKIE)).split("=", 1)[1].split(";")[0]
    assert status == 403 and session.read(fresh)["scope"] != "*" and session.read(fresh)["sid"] == session.read(ana)["sid"]
    cutoff = int((tmp_path / "revoked").read_text().splitlines()[0].split()[1])
    assert session.read(ana)["expires"] < cutoff <= session.read(fresh)["expires"]   # nginx: the old cookie goes to the API


@pytest.mark.skipif(not shutil.which("node"), reason="node is not installed")
def test_nginx_trusts_a_sees_everything_cookie_only_if_it_was_issued_after_access_last_changed(tmp_path, monkeypatch):
    """deploy/cip_auth.js itself, run by node with nginx's two objects stubbed: 204 serve the file, 403 ask the API."""
    secret, now = "test-secret", int(time.time())
    (tmp_path / "revoked").write_text(f"access-before {now + 12 * 3600}\n")
    monkeypatch.setenv("CIP_SESSION_SECRET", secret)
    cookies = {"old_everything": session.issue("ana@coresight.com", hours=11, scope="*"),
               "new_everything": session.issue("ana@coresight.com", hours=13, scope="*"),
               "new_filtered": session.issue("pat@acme.com", hours=13, scope="acme:core"), "forged": "abc.def"}
    script = tmp_path / "run.mjs"
    script.write_text("globalThis.ngx = { shared: { sessions: { get() {}, set() {} } } };\n"
                      f"const auth = (await import({json.dumps((Path(__file__).resolve().parents[1] / 'deploy/cip_auth.js').as_uri())})).default;\n"
                      f"const cookies = {json.dumps(cookies)};\n"
                      "const out = {};\n"
                      "for (const [name, c] of Object.entries(cookies)) auth.check({ variables: { cookie_cip_session: c }, headersIn: {}, return: s => { out[name] = s; } });\n"
                      "console.log(JSON.stringify(out));\n")
    run = subprocess.run(["node", str(script)], capture_output=True, text=True, timeout=30,
                         env={**os.environ, "CIP_SESSION_SECRET": secret, "CIP_REVOKED_FILE": str(tmp_path / "revoked")})
    assert json.loads(run.stdout) == {"old_everything": 403, "new_everything": 204, "new_filtered": 403, "forged": 401}, run.stderr



def test_menus_for_one_client_or_one_employee_beat_their_role_everywhere(portal, monkeypatch):
    """The super admin gives Acme (a client) and then one Acme person their own menus: a person's choice beats their
    client's, which beats their role's; dropping a person's choice gives them their client's again. The API refuses
    what the menu hides, so the portal, the API keys and the MCP connector all follow the one rule (access.menus)."""
    monkeypatch.setattr(access, "MANAGED", {"at": -1e9, "roles": {}})
    boss, pat = signed("boss@coresight.com"), signed("pat@acme.com")
    put(portal, "sectors", {"sectors": []})
    targets = {r["role"]: r for r in json.loads(call("/api/v1/admin/roles", boss)[2])["roles"]}
    assert targets["client:acme"]["kind"] == "client" and "sectors" in targets["client:acme"]["features"]
    assert call("/api/v1/sectors", pat)[0] == 200
    acme = [f for f in targets["client:acme"]["features"] if f != "sectors"]
    assert call("/api/v1/admin/roles/client:acme", boss, "PUT", json.dumps({"features": acme}).encode())[0] == 200
    assert call("/api/v1/sectors", pat)[0] == 403 and "sectors" not in access.profile("pat@acme.com")["features"]
    assert call("/api/v1/admin/roles/person:pat@acme.com", boss, "PUT", json.dumps({"features": acme + ["sectors"]}).encode())[0] == 200
    assert call("/api/v1/sectors", pat)[0] == 200                                     # Pat's own trial
    assert "sectors" not in access.profile("other@acme.com")["features"]              # the rest of Acme still without
    people = [r for r in json.loads(call("/api/v1/admin/roles", boss)[2])["roles"] if r["kind"] == "person"]
    assert [p["role"] for p in people] == ["person:pat@acme.com"] and people[0]["chosen"]
    assert call("/api/v1/admin/roles/person:pat@acme.com", boss, "DELETE")[0] == 200   # the trial ends
    assert call("/api/v1/sectors", pat)[0] == 403
    assert call("/api/v1/admin/roles/person:nobody@unknown.org", boss, "PUT", b'{"features": []}')[0] == 404
    assert call("/api/v1/admin/roles/person:boss@coresight.com", boss, "PUT", b'{"features": []}')[0] == 404   # the super admin
    assert call("/api/v1/admin/roles/client:acme", pat, "PUT", b'{"features": []}')[0] == 403



def test_each_person_makes_their_own_keys_and_a_key_has_exactly_their_access_now(portal, monkeypatch, tmp_path):
    """Ana makes a key on the Account page; it works for the API and the MCP connector as Ana. When the super admin
    hides a menu from Ana, her key loses it at the same moment as her screens. A key cannot make keys, nobody can
    revoke someone else's, and a revoked key stops at once."""
    from shared.core import api_keys
    monkeypatch.setattr(access, "MANAGED", {"at": -1e9, "roles": {}})
    monkeypatch.setattr(api_keys, "FILE", tmp_path / "keys.yml")
    monkeypatch.setitem(api_keys._cache, "checked", -1e9)
    boss, ana, pat = signed("boss@coresight.com"), signed("ana@coresight.com"), signed("pat@acme.com")
    status, _, body = call("/api/v1/keys", ana, "POST", b'{"name": "Ana\'s Claude"}')
    key = json.loads(body)["key"]
    assert status == 200 and key.startswith("cip_") and key not in (tmp_path / "keys.yml").read_text()
    listed = json.loads(call("/api/v1/keys", ana)[2])["keys"]
    assert [k["name"] for k in listed] == ["Ana's Claude"] and "key" not in listed[0]
    bearer = {"authorization": f"Bearer {key}"}
    put(portal, "sectors", {"sectors": []})
    assert call("/api/v1/sectors", headers=bearer)[0] == 200
    assert call("/api/v1/keys", method="POST", body=b'{"name": "more"}', headers=bearer)[0] == 403   # a key makes no keys
    hidden = [f for f in access.profile("ana@coresight.com")["features"] if f not in ("sectors", "explorer")]
    assert call("/api/v1/admin/roles/person:ana@coresight.com", boss, "PUT", json.dumps({"features": hidden}).encode())[0] == 200
    assert call("/api/v1/sectors", headers=bearer)[0] == 403 and call("/api/v1/sectors", ana)[0] == 403   # key and screen alike
    ask = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "question_results", "arguments": {"survey_id": 1, "qcode": "q1"}}})
    answer = json.loads(call("/mcp", method="POST", body=ask.encode(), headers=bearer)[2])["result"]
    assert answer["isError"] and "subscription" in answer["content"][0]["text"]         # the MCP connector alike
    assert call(f"/api/v1/keys/{listed[0]['shown']}", pat, "DELETE")[0] == 404           # not Pat's key
    assert call(f"/api/v1/keys/{listed[0]['shown']}", ana, "DELETE")[0] == 200
    assert call("/api/v1/waves", headers=bearer)[0] == 401                                # revoked: stops at once


def test_the_api_refuses_exactly_what_the_menus_hide(portal, monkeypatch):
    """Launch schedule, a wave's results (the Question explorer's, also read by the MCP connector) and a question across
    waves (Trends, Compare waves and Audiences all read it): each answers only when one of its screens is on the menu."""
    monkeypatch.setattr(access, "MANAGED", {"at": -1e9, "roles": {}})
    boss, ana = signed("boss@coresight.com"), signed("ana@coresight.com")
    everything = access.profile("ana@coresight.com")["features"]
    def menus(*hidden):
        keep = [f for f in everything if f not in hidden]
        assert call("/api/v1/admin/roles/person:ana@coresight.com", boss, "PUT", json.dumps({"features": keep}).encode())[0] == 200
    menus("schedule", "explorer", "trends")
    assert call("/api/v1/schedule", ana)[0] == 403 and call("/api/v1/waves/1/results?q=q1", ana)[0] == 403
    assert call("/api/v1/questions/CSI-US/tracker/q1", ana)[0] != 403          # Compare waves still reads it
    menus("trends", "compare", "audiences")
    assert call("/api/v1/questions/CSI-US/tracker/q1", ana)[0] == 403


def test_the_demo_sign_in_is_off_wherever_company_sign_in_is_set_up(monkeypatch):
    """On a public address with the identity provider configured, the demo sign-in would let anyone type anyone's
    email (staging, 7 Nov 2026): the provider always wins, whatever CIP_DEMO_LOGIN says."""
    monkeypatch.setenv("CIP_DEMO_LOGIN", "1")
    monkeypatch.delenv("CIP_OIDC_ISSUER", raising=False)
    assert signin.demo()
    monkeypatch.setenv("CIP_OIDC_ISSUER", "https://idp.example.com")
    monkeypatch.setenv("CIP_OIDC_CLIENT_ID", "cip")
    assert not signin.demo()


def test_the_cache_warmer_sees_every_feature_whatever_the_analysts_menus():
    """nginx shares one cached answer among everyone who sees everything, so the session that fills it (publish@cip)
    must see every feature even when the analysts' menus are trimmed; it gets no admin page."""
    warmer = access.profile("publish@cip")
    assert set(warmer["features"]) == set(access.rules()["features"])
    assert not access.can(warmer, "admin_pages")


def test_non_ascii_text_in_a_cookie_is_a_refusal_not_a_crash():
    assert session.same("abc", "abc") and session.same("é", "é") and not session.same("abc", "é")
    assert session.read("eA==.é") is None
    assert call("/api/v1/me", "e30=.é")[0] == 401   # a cookie of valid shape with a non-ASCII signature
