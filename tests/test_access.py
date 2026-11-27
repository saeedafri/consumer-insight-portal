"""Who gets in and what they see, over HTTP: sign-in, the cookie, revocation, roles, client scoping, limits, the error
shape, security headers and the audit log (api/signin.py, shared/core/access.py, shared/core/audit.py)."""
import asyncio
import gzip
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from urllib.parse import urlsplit

import pytest
import sqlalchemy as sa
import yaml

import api.main as api
from api import signin, team
from shared.core import access, audit, session
from shared.core.config import REPO_ROOT


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
    sent, received = [], False

    async def receive():   # the body once, then nothing until the client leaves, as a server does (a file response waits on it)
        nonlocal received
        if received:
            await asyncio.Event().wait()
        received = True
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
                 "report", "sectors", "expectations", "weighted", "api", "fieldwork"],
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


def signed(email, scope=None, hours=session.SESSION_HOURS):
    """A signed-in cookie whose session is recorded as the demo sign-in records it (signin.remember)."""
    cookie = session.issue(email, hours=hours, scope=scope or access.scope(access.profile(email)))
    signin.remember(session.read(cookie)["sid"], access.profile(email), "demo")
    return cookie


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


def test_the_consumer_health_dataset_goes_only_to_those_given_it(portal, monkeypatch):
    """Respondent rows (etl/consumer_health.py): a chosen-only menu, so staff without it get 403 and the super admin the file."""
    monkeypatch.setattr(access, "rules", lambda: {**RULES, "features": RULES["features"] + ["datasets"],
                                                  "chosen_only": RULES["chosen_only"] + ["datasets"]})
    assert call("/api/v1/datasets/consumer-health", signed("boss@coresight.com"))[0] == 404            # not built yet
    # the left menu asks first (HEAD): a note, not a failed consumer-health.json download (27 Nov 2026)
    assert call("/api/v1/datasets/consumer-health", signed("boss@coresight.com"), "HEAD")[0] == 404
    folder = portal / "api/v1/datasets"
    folder.mkdir(parents=True)
    (folder / "Consumer_Health_Raw_Respondent_Data_Chronological_2023_2026.xlsx").write_bytes(b"PK workbook")
    assert call("/api/v1/datasets/consumer-health", signed("ana@coresight.com"))[0] == 403
    assert call("/api/v1/datasets/consumer-health", signed("ana@coresight.com"), "HEAD")[0] == 403
    assert call("/api/v1/datasets/consumer-health", signed("boss@coresight.com"), "HEAD")[::2] == (200, b"")   # there, not sent
    status, headers, body = call("/api/v1/datasets/consumer-health", signed("boss@coresight.com"))
    assert status == 200 and body == b"PK workbook" and "Chronological_2023_2026.xlsx" in headers["content-disposition"][0]


def test_the_tracker_views_are_served_as_published_and_say_so_before_the_first_publish(portal):
    for name in ("sectors", "expectations"):
        assert call(f"/api/v1/{name}", signed("ana@coresight.com"))[0] == 503              # being published: the screen retries
        put(portal, name, {"sectors": [], "events": []})
        status, _, body = call(f"/api/v1/{name}", signed("pat@acme.com"))                 # a client who sees every tracker wave
        assert status == 200 and "sectors" in json.loads(body)
        assert call(f"/api/v1/{name}")[0] == 401                                           # signed out: nothing



def test_an_analyst_given_home_ask_library_channels_and_retailers_gets_both_weekly_surveys(portal, monkeypatch):
    """The analysts' menus of 24 Nov 2026, without either weekly tracker's: the US and China weekly waves stay open (those
    screens are built on them, config/access.yml family_menus), so the Library lists them, This week at a glance shows
    them and In store vs online reads its question files without Trends."""
    monkeypatch.setattr(access, "MANAGED", {"at": -1e9, "roles": {}})
    monkeypatch.setitem(RULES, "features", [*RULES["features"], "library", "us_tracker", "china_tracker", "channels", "retailers"])
    monkeypatch.setitem(RULES, "family_menus", yaml.safe_load((REPO_ROOT / "config/access.yml").read_text())["family_menus"])
    china = {"survey_id": 416, "survey_family": "CSI-CN", "study_type": "tracker", "prior_survey_id": None, "wave_date": "2026-10-19", "title": "China"}
    put(portal, "waves", [*json.loads(gzip.decompress((portal / "api/v1/waves.json.gz").read_bytes())), china])
    put(portal, "glance", {"surveys": [{"name": "US", "survey_id": 415, "cards": []}, {"name": "China", "survey_id": 416, "cards": []}]})
    boss = signed("boss@coresight.com")
    four = ["ask", "library", "channels", "retailers"]
    assert call("/api/v1/admin/roles/person:ana@coresight.com", boss, "PUT", json.dumps({"features": four}).encode())[0] == 200
    ana = signed("ana@coresight.com")
    assert [w["survey_id"] for w in json.loads(call("/api/v1/waves", ana)[2])] == [415, 300, 416]
    assert [s["name"] for s in json.loads(call("/api/v1/glance", ana)[2])["surveys"]] == ["US", "China"]
    assert call("/api/v1/questions/CSI-US/tracker/Q1", ana)[0] == 200                                 # In store vs online's files
    assert call("/api/v1/questions/ACME_STUDY/adhoc/Q1", ana)[0] == 403                               # not Trends for the rest


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
    login = head["set-cookie"][0].split(";")[0]                                  # cip_login_<state>=<signed handshake>
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
    token = {"iss": "https://stage3.coresight.com", "aud": "cip-staging", "exp": time.time() + 60, "auth_time": time.time() - 3600,
             "data": {"wp_user": {"user_email": "dataautomation@coresight.com", "roles": ["administrator"]}}}
    body = "x." + base64.urlsafe_b64encode(json.dumps(token).encode()).decode().rstrip("=") + ".x"

    class Answer:
        def raise_for_status(self): pass
        def json(self): return {"id_token": body, "access_token": "secret-access", "scope": "openid email"}
    monkeypatch.setattr(requests, "post", lambda url, **kw: Answer() if url.endswith("/csr-idp/token") else None)
    signed_out = f"{signin.SIGNED_OUT}={int(time.time()) - 60}"   # signed out a minute ago, provider sign-in an hour ago
    status, head, _ = call(f"/auth/callback?code=c&state={sent['state'][0]}", headers={"cookie": f"{login}; {signed_out}"})
    assert status in (302, 303) and any(c.startswith(signin.COOKIE + "=") for c in head["set-cookie"])
    assert "[SIGN-TRACE] 3. sent to the provider" in caplog.text and "no password typed" in caplog.text
    assert "reused a sign-in from BEFORE the last CIP sign-out" in caplog.text
    assert "administrator" in caplog.text and '"scope": "openid email"' in caplog.text
    assert "secret-access" not in caplog.text and body not in caplog.text
    assert any(c.startswith(f"{signin.ID_TOKEN}={body}") for c in head["set-cookie"])   # kept for /auth/logout


def test_logout_never_500s_when_idp_has_no_discovery(portal, monkeypatch, caplog):
    """Logging out when the provider has no openid-configuration returns 200 and drops the cookie, and the trace says
    the provider's session was not ended."""
    caplog.set_level("INFO", logger="cip.signin")
    for key, value in {"CIP_OIDC_ISSUER": "https://stage3.coresight.com", "CIP_OIDC_CLIENT_ID": "cip-staging",
                       "CIP_OIDC_AUTHORIZE_URL": "https://stage3.coresight.com/csr-idp/authorize",
                       "CIP_OIDC_TOKEN_URL": "https://stage3.coresight.com/csr-idp/token"}.items():
        monkeypatch.setenv(key, value)
    status, head, body = call("/auth/logout", signed("dataautomation@coresight.com"))
    assert status == 303 and head["location"] == ["/"]                        # the home page
    assert any(c.startswith(signin.COOKIE + "=;") or "Max-Age=0" in c for c in head.get("set-cookie", []))
    assert "ID token cookie: MISSING" in caplog.text and "the provider's session was NOT ended" in caplog.text
    # no CIP_OIDC_LOGOUT_URL (staging, 9 Nov 2026): csr-idp's logout beside its authorize address is used
    status, head, _ = call("/auth/logout", signed("dataautomation@coresight.com") + f"; {signin.ID_TOKEN}=h.p.s")
    assert head["location"][0].startswith("https://stage3.coresight.com/csr-idp/logout/?id_token_hint=h.p.s")


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


def coresight_idp(monkeypatch, **claims):
    """Sign-in through csr-idp (no discovery document, PKCE "plain"), its token endpoint answering an ID token with
    these claims; no network."""
    import base64
    import requests
    for key, value in {"CIP_OIDC_ISSUER": "https://coresight.com", "CIP_OIDC_CLIENT_ID": "sip-app",
                       "CIP_OIDC_AUTHORIZE_URL": "https://coresight.com/csr-idp/authorize",
                       "CIP_OIDC_TOKEN_URL": "https://coresight.com/csr-idp/token", "CIP_OIDC_PKCE": "plain"}.items():
        monkeypatch.setenv(key, value)
    token = {"iss": "https://coresight.com", "aud": "sip-app", "exp": time.time() + 60, **claims}
    body = "x." + base64.urlsafe_b64encode(json.dumps(token).encode()).decode().rstrip("=") + ".x"

    class Answer:
        def raise_for_status(self): pass
        def json(self): return {"id_token": body}
    monkeypatch.setattr(requests, "post", lambda url, **kw: Answer())


@pytest.mark.parametrize("verified, status", [(False, 403), ("false", 403), (True, 303), (None, 303)])
def test_an_email_the_provider_has_not_verified_never_signs_in(portal, monkeypatch, verified, status):
    """email_verified false: the provider has not proven the address is the person's, so it must not say who signs in.
    A provider that sends no such claim (csr-idp; None here) is trusted as before (15 Nov 2026)."""
    from urllib.parse import parse_qs
    coresight_idp(monkeypatch, email="ana@coresight.com", **({} if verified is None else {"email_verified": verified}))
    _, head, _ = call("/auth/login")
    state = parse_qs(urlsplit(head["location"][0]).query)["state"][0]
    assert call(f"/auth/callback?code=c&state={state}", headers={"cookie": head["set-cookie"][0].split(";")[0]})[0] == status


def test_two_tabs_signing_in_at_once_both_get_in(portal, monkeypatch):
    """Each sign-in attempt keeps its own handshake cookie, named by its state: a second tab's no longer replaces the
    first's (15 Nov 2026). The state is checked as strictly, each handshake works once, and at most four are kept."""
    from urllib.parse import parse_qs
    coresight_idp(monkeypatch, email="ana@coresight.com")
    jar: dict = {}   # the browser's cookies, oldest first, as it sends them

    def visit(path):
        status, head, _ = call(path, headers={"cookie": "; ".join(f"{k}={v}" for k, v in jar.items())})
        for line in head.get("set-cookie", []):
            name, value = line.split(";")[0].split("=", 1)
            if "Max-Age=0" in line:
                jar.pop(name, None)
            else:
                jar[name] = value
        return status, head
    states = [parse_qs(urlsplit(visit(f"/auth/login?next=/app/{tab}")[1]["location"][0]).query)["state"][0] for tab in "ab"]
    for tab, state in zip("ab", states):
        status, head = visit(f"/auth/callback?code=c&state={state}")
        assert status == 303 and head["location"] == [f"/app/{tab}"]
    assert visit(f"/auth/callback?code=c&state={states[0]}")[0] == 400   # a handshake works once
    assert visit("/auth/callback?code=c&state=forged")[0] == 400
    for _ in range(6):
        visit("/auth/login")
    assert sum(name.startswith(signin.LOGIN) for name in jar) == 4       # abandoned attempts never pile up


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
    boss, ana = signed("boss@coresight.com"), signed("ana@coresight.com", scope="*", hours=11)
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


def test_a_revoked_session_stays_out_after_a_restart(portal, monkeypatch):
    """Re-issuing a cookie after a restart moves its recorded expiry with it, so the minute poll (load_revoked) keeps a
    revocation for as long as the cookie lives; a revoked session a restart forgot is refused, not re-issued. A
    database out of reach re-issues as before (15 Nov 2026)."""
    def restart():   # a deploy: the API forgets its revoked sessions, then its minute poll reloads the live ones
        monkeypatch.setattr(signin, "STARTED", time.time())
        session.REVOKED.clear()
        signin.load_revoked()

    kept, gone = signed("ana@coresight.com", hours=1), signed("ben@coresight.com", hours=1)   # signed in 11 h ago
    with api.get_engine("api_write").begin() as conn:   # re-issued before 15 Nov: the cookies outlived their recorded expiry
        conn.execute(sa.text("UPDATE cip_access_session SET expires_at = '2000-01-01 00:00:00'"))
    signin.revoke([session.digest(session.read(gone)["sid"])])   # Ben signed out
    restart()
    assert call("/api/v1/me", gone)[0] == 401                     # forgotten by the restart, refused all the same
    status, head, _ = call("/api/v1/me", kept)
    fresh = next(c for c in head["set-cookie"] if c.startswith(signin.COOKIE)).split("=", 1)[1].split(";")[0]
    assert status == 200 and session.read(fresh)["sid"] == session.read(kept)["sid"]
    signin.revoke([session.digest(session.read(fresh)["sid"])], "ana@coresight.com")        # Ana is offboarded
    restart()
    assert call("/api/v1/me", fresh)[0] == 401                    # still loaded: the recorded expiry moved with the cookie

    def unreachable(role):
        raise OSError("the database is out of reach")
    monkeypatch.setattr(signin, "get_engine", unreachable)
    assert call("/api/v1/me", signed("cat@coresight.com", hours=1))[0] == 200


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
    assert call(f"/api/v1/keys/{listed[0]['shown']}", pat, "DELETE")[0] == 403           # Acme's package has no API keys
    assert call(f"/api/v1/keys/{listed[0]['shown']}", signed("bob@coresight.com"), "DELETE")[0] == 404   # not Bob's key
    assert call(f"/api/v1/keys/{listed[0]['shown']}", ana, "DELETE")[0] == 200
    assert call("/api/v1/waves", headers=bearer)[0] == 401                                # revoked: stops at once


def test_an_api_key_never_opens_admin_pages(portal, monkeypatch, tmp_path):
    """A key acts as its owner on the data routes, but an admin page needs the admin signed in: a leaked admin's key
    must not reach the logs, the Access screen or offboarding (15 Nov 2026)."""
    from shared.core import api_keys
    monkeypatch.setattr(api_keys, "FILE", tmp_path / "keys.yml")
    monkeypatch.setitem(api_keys._cache, "checked", -1e9)
    boss = signed("boss@coresight.com")
    bearer = {"authorization": "Bearer " + json.loads(call("/api/v1/keys", boss, "POST", b'{"name": "Boss"}')[2])["key"]}
    put(portal, "admin/fieldwork", {"surveys": [], "archive": []})
    assert call("/api/v1/waves", headers=bearer)[0] == 200 and call("/api/v1/admin/fieldwork", boss)[0] == 200
    status, _, body = call("/api/v1/admin/fieldwork", headers=bearer)
    assert status == 403 and "signed-in admin" in json.loads(body)["detail"]
    assert call("/api/v1/admin/sessions/revoke", method="POST", body=b'{"email": "ana@coresight.com"}', headers=bearer)[0] == 403


def test_offboarding_also_revokes_the_persons_api_keys(portal, monkeypatch, tmp_path, capsys):
    """Signing a person out everywhere also revokes their API keys: a key never passes the identity provider, so it
    outlived their sessions. The command line's revoke says what it revoked: it always said "No such key" (15 Nov 2026)."""
    from shared.core import api_keys
    monkeypatch.setattr(api_keys, "FILE", tmp_path / "keys.yml")
    monkeypatch.setitem(api_keys._cache, "checked", -1e9)
    boss, ana = signed("boss@coresight.com"), signed("ana@coresight.com")
    bearer = {"authorization": "Bearer " + json.loads(call("/api/v1/keys", ana, "POST", b'{"name": "Ana"}')[2])["key"]}
    team.set_subscribed("ana@coresight.com", True)   # her new-survey emails (My account) end with it (27 Nov 2026)
    status, _, body = call("/api/v1/admin/sessions/revoke", boss, "POST", b'{"email": "ana@coresight.com"}')
    assert status == 200 and call("/api/v1/waves", headers=bearer)[0] == 401 and json.loads(body)["keys"] == 1
    assert team._rows("SELECT email FROM cip_survey_subscriber") == []
    shown = api_keys.new("ben@coresight.com", "Ben's script")[:8]
    monkeypatch.setattr("sys.argv", ["api_keys", "revoke", shown])
    api_keys.main()
    assert capsys.readouterr().out.strip() == "Revoked 1" and api_keys.mine("ben@coresight.com") == []


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


def test_without_api_keys_and_mcp_on_the_menu_no_key_works_and_none_can_be_made(portal, monkeypatch, tmp_path):
    """The super admin takes "API keys and MCP" off Ana's menu: her existing key is refused (API and MCP alike), and
    she can neither list nor make keys; turned back on, the same key works again (10 Nov 2026)."""
    from shared.core import api_keys
    monkeypatch.setattr(access, "MANAGED", {"at": -1e9, "roles": {}})
    monkeypatch.setattr(api_keys, "FILE", tmp_path / "keys.yml")
    monkeypatch.setitem(api_keys._cache, "checked", -1e9)
    boss, ana = signed("boss@coresight.com"), signed("ana@coresight.com")
    key = json.loads(call("/api/v1/keys", ana, "POST", b'{"name": "Ana"}')[2])["key"]
    bearer = {"authorization": f"Bearer {key}"}
    assert call("/api/v1/waves", headers=bearer)[0] == 200
    without = [f for f in RULES["features"] if f not in ("api", "fieldwork")]
    assert call("/api/v1/admin/roles/person:ana@coresight.com", boss, "PUT", json.dumps({"features": without}).encode())[0] == 200
    assert call("/api/v1/waves", headers=bearer)[0] == 403
    assert call("/mcp", method="POST", body=b'{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}', headers=bearer)[0] == 403
    assert call("/api/v1/keys", ana)[0] == 403 and call("/api/v1/keys", ana, "POST", b'{"name": "x"}')[0] == 403
    assert call("/api/v1/waves", ana)[0] == 200                                        # her screens are unaffected
    assert call("/api/v1/admin/roles/person:ana@coresight.com", boss, "DELETE")[0] == 200
    assert call("/api/v1/waves", headers=bearer)[0] == 200


def test_the_mcp_connector_asks_like_the_page_and_under_the_same_menu(portal, monkeypatch, tmp_path):
    """The connector's ask tool is the Ask CIP page's answer (api/main.py ask_answer): listed, answered, and
    refused once Ask CIP is off the person's menu."""
    from shared.core import api_keys
    monkeypatch.setattr(access, "MANAGED", {"at": -1e9, "roles": {}})
    monkeypatch.setattr(api_keys, "FILE", tmp_path / "keys.yml")
    monkeypatch.setitem(api_keys._cache, "checked", -1e9)
    boss, ana = signed("boss@coresight.com"), signed("ana@coresight.com")
    bearer = {"authorization": "Bearer " + json.loads(call("/api/v1/keys", ana, "POST", b'{"name": "Ana"}')[2])["key"]}
    tools = json.loads(call("/mcp", method="POST", body=b'{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}', headers=bearer)[2])
    assert "ask" in [t["name"] for t in tools["result"]["tools"]]
    asked = json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "ask", "arguments": {"question": "holiday shopping"}}})
    answer = json.loads(call("/mcp", method="POST", body=asked.encode(), headers=bearer)[2])["result"]
    assert not answer.get("isError") and json.loads(answer["content"][0]["text"])["mode"] in ("figures", "none")
    without = [f for f in RULES["features"] if f not in ("ask", "fieldwork")]
    assert call("/api/v1/admin/roles/person:ana@coresight.com", boss, "PUT", json.dumps({"features": without}).encode())[0] == 200
    answer = json.loads(call("/mcp", method="POST", body=asked.encode(), headers=bearer)[2])["result"]
    assert answer["isError"] and "subscription" in answer["content"][0]["text"]


def test_the_ai_check_and_search_have_their_own_limits(portal, monkeypatch):
    """A check skipped the per-minute limit, so a loop of checks could spend the month's AI cap for everyone, and Search
    had none, ~40 ms of the one CPU a misspelt query (security review, 15 Nov 2026)."""
    monkeypatch.setitem(RULES["limits"], "ask_check", 2)
    monkeypatch.setitem(RULES["limits"], "search", 2)
    cookie = signed("ana@coresight.com")
    checks = [call("/api/v1/ask", cookie, "POST", b'{"question": "holiday", "check": true}')[0] for _ in range(3)]
    searches = [call("/api/v1/search?q=holiday", cookie)[0] for _ in range(3)]
    assert checks == [200, 200, 429] and searches == [200, 200, 429]


def test_weighted_figures_reach_only_who_has_them_and_never_carry_the_unweighted_verdict(portal):
    """The book carried weighted figures to accounts without them, and the MCP connector gave weighted figures the
    pipeline's significance verdict, which tests the unweighted ones (security review, 15 Nov 2026)."""
    from api import mcp
    wave = {"survey_id": 415, "survey_family": "CSI-US", "study_type": "tracker", "prior_survey_id": None,
            "wave_date": "2026-10-19", "title": "Weekly", "weighting_available": "Census"}
    row = {"label": "Yes", "code": 1, "Total": 47.0, "prior": 55.0, "prior_base": 400, "ly": None, "ly_base": None,
           "flags": "sig_prior", "w": {"Total": 50.0, "prior": 52.0, "ly": None}}
    put(portal, "waves/415/book", {"wave": wave, "columns": ["Total"], "questions": [{"id": "Q1", "text": "Bought?", "type": "single",
        "groups": [{"label": "", "base": 400, "bases": {"Total": 400}, "rows": [row]}]}]})
    api._parsed_book.cache_clear()
    shown = lambda cookie: json.loads(call("/api/v1/waves/415/book", cookie)[2])["questions"][0]["groups"][0]["rows"][0]   # noqa: E731
    assert "w" in shown(signed("ana@coresight.com")) and "w" not in shown(signed("pat@acme.com"))   # Acme has no weighted figures
    ana = access.profile("ana@coresight.com")
    weighted = asyncio.run(mcp.question_results(ana, 415, "Q1", weighted=True))["groups"][0]["rows"][0]
    assert (weighted["Total"], weighted["prior_week"], weighted["prior_base"], weighted["significant_vs_prior"]) == (50.0, 52.0, 400, None)
    plain = asyncio.run(mcp.question_results(ana, 415, "Q1"))["groups"][0]["rows"][0]
    assert (plain["Total"], plain["significant_vs_prior"]) == (47.0, True)


def test_a_key_carries_none_of_its_owners_admin_powers_and_is_always_rate_limited(portal, monkeypatch):
    """admin() refused keys, but a super admin's key still managed every team's items, unthrottled (second review,
    15 Nov 2026)."""
    boss = access.profile("boss@coresight.com")
    assert access.can(boss, "manage_team_items") and not access.can({**boss, "sid": "api-key"}, "manage_team_items")
    monkeypatch.setitem(RULES["limits"], "api", 2)
    assert [access.spend("boss@coresight.com", "api") for _ in range(3)] == [True, True, False]
    assert all(access.spend("boss@coresight.com", "ask") for _ in range(5))   # signed in, still never throttled


def menu_keys(items):
    """Every feature key in a branch of config/access.yml `menu`, in order."""
    for item in items:
        if isinstance(item, str):
            yield item
        else:
            yield from menu_keys(item.get("children", []))


def test_the_access_menu_tree_holds_every_feature_once_as_the_left_menu_does():
    """The Access screen offers the left menu's every group, menu and page (config/access.yml menu): each feature once,
    labelled, and the trackers and Forsta pages the same as the screens list (15 Nov 2026)."""
    access.rules.cache_clear()
    rules = access.rules()
    keys = [k for group in rules["menu"] for k in menu_keys(group["items"])]
    assert sorted(keys) == sorted(rules["features"]) and len(keys) == len(set(keys))
    assert all(f in rules["feature_labels"] for f in rules["features"])
    web = Path(__file__).resolve().parents[1] / "frontend" / "src"
    trackers = re.findall(r'\["(\w+)", "[^"]+"\]', web.joinpath("trackers.ts").read_text().split("SECTOR_DASHBOARDS")[0])
    sections = re.findall(r'^\s*\["(\w+)", "[^"]+", "', web.joinpath("forstaSections.ts").read_text(), re.M)
    assert [f"tracker_{c}" for c in trackers] == [k for k in rules["features"] if k.startswith("tracker_")]
    assert [f"forsta_{s}" for s in sections] == [k for k in rules["features"] if k.startswith("forsta_")]
    shell = web.joinpath("components", "Shell.tsx").read_text()
    named = set(re.findall(r'(?:allowed\(me, |given\(me, |features\?\.includes\()"(\w+)"', shell))
    assert named and named <= set(rules["features"])   # every menu the left menu checks is one the Access screen offers
    assert {"datasets", "ingest", "logs"} <= named     # given(): the menus only the super admin hands out (27 Nov 2026)
    assert {g["group"] for g in access.tree()} >= {"Explore", "Core research", "Trackers", "Reference", "Research operations", "Administration"}


def test_a_choice_saved_before_the_menus_grew_loses_nothing_and_a_new_one_is_kept_as_saved():
    """Menus split off an older one (grown_from) follow it in a package or in a choice saved before the split; a choice
    saved since keeps exactly what was ticked (15 Nov 2026)."""
    access.rules.cache_clear()
    old = access.choice(["dashboards", "explorer", "search"])   # a list as the Access screen saved it before
    assert {"library", "methodology", "whats_new", "us_tracker", "china_tracker", "channels", "tracker_glp1"} <= set(old)
    assert not {"logs", "ingest", "forsta_reports", "crosstab"} & set(old)   # the admin pages stay the super admin's
    offered = access.rules()["features"]
    new = access.choice({"on": ["dashboards", "tracker_genai"], "offered": offered})
    assert set(new) == {"dashboards", "tracker_genai"}   # GLP-1 and the rest off, as ticked
    core = access.menus([], "core")   # a package lists the old menus: it gets the new ones grown from them
    assert {"library", "tracker_glp1", "channels"} <= set(core) and "logs" not in core


def test_a_weekly_tracker_hidden_on_the_access_screen_closes_its_waves(portal, monkeypatch):
    """A weekly tracker in family_menus (none in config since 24 Nov 2026; the US one here, the fixture's wave)
    off for one person: its waves leave the list and do not open, and that person's cached answers are kept apart from
    their client's (access.scope, 15 Nov 2026)."""
    monkeypatch.setattr(access, "MANAGED", {"at": -1e9, "roles": {}})
    monkeypatch.setitem(RULES, "features", RULES["features"] + ["us_tracker"])
    monkeypatch.setitem(RULES, "family_menus", {"CSI-US": "us_tracker"})
    boss, ana = signed("boss@coresight.com"), signed("ana@coresight.com")
    assert 415 in [w["survey_id"] for w in json.loads(call("/api/v1/waves", ana)[2])]
    without = [f for f in access.profile("ana@coresight.com")["features"] if f != "us_tracker"]
    assert call("/api/v1/admin/roles/person:ana@coresight.com", boss, "PUT", json.dumps({"features": without}).encode())[0] == 200
    ana = signed("ana@coresight.com")
    assert 415 not in [w["survey_id"] for w in json.loads(call("/api/v1/waves", ana)[2])]
    assert call("/api/v1/waves/415/book", ana)[0] in (403, 404)
    assert access.scope(access.profile("ana@coresight.com")).endswith(":without:us_tracker")


def test_an_admin_page_given_on_the_access_screen_opens_for_that_person_only(portal, monkeypatch):
    """The Logs page and a Forsta page given to one analyst: their routes answer them, still never an API key, and
    nobody else (15 Nov 2026). Each tracker's dashboard needs its own menu."""
    monkeypatch.setattr(access, "MANAGED", {"at": -1e9, "roles": {}})
    monkeypatch.setitem(RULES, "features", RULES["features"] + ["logs", "forsta_reports", "tracker_glp1"])
    monkeypatch.setitem(RULES, "chosen_only", ["fieldwork", "logs", "forsta_reports"])
    boss, ana, bob = signed("boss@coresight.com"), signed("ana@coresight.com"), signed("bob@coresight.com")
    assert call("/api/v1/admin/health", ana)[0] == 403 and call("/api/v1/admin/forsta", ana)[0] == 403
    given = access.profile("ana@coresight.com")["features"] + ["logs", "forsta_reports"]
    assert call("/api/v1/admin/roles/person:ana@coresight.com", boss, "PUT", json.dumps({"features": given}).encode())[0] == 200
    ana = signed("ana@coresight.com")
    assert call("/api/v1/admin/health", ana)[0] == 200
    assert call("/api/v1/admin/forsta", ana)[0] == 404            # allowed in: there is just no Forsta record in a test
    assert call("/api/v1/admin/audit", ana)[0] == 403             # an admin page nobody is given
    assert call("/api/v1/admin/health", bob)[0] == 403            # only the person it was given to
    assert call("/api/v1/dashboards/glp1/415", ana)[0] == 404     # GLP-1 is on Ana's menu (no such dashboard here)
    no_glp1 = [f for f in given if f != "tracker_glp1"]
    assert call("/api/v1/admin/roles/person:ana@coresight.com", boss, "PUT", json.dumps({"features": no_glp1}).encode())[0] == 200
    assert call("/api/v1/dashboards/glp1/415", signed("ana@coresight.com"))[0] == 403


def test_suggestions_while_typing_and_readiness_answer_over_the_api(portal, monkeypatch, tmp_path):
    """GET /api/v1/ask/suggest (Ask's box while typing; its own per-minute limit) and /readyz, which answers 503 until the
    published wave list is in, unlike /healthz, even while the database answers (15 Nov 2026)."""
    monkeypatch.setitem(RULES["limits"], "ask_suggest", 2)
    ana = signed("ana@coresight.com")
    status, _, body = call("/api/v1/ask/suggest?q=holiday", ana)
    assert status == 200 and set(json.loads(body)) == {"corrected", "suggestions"}
    assert [call("/api/v1/ask/suggest?q=holiday", ana)[0] for _ in range(2)] == [200, 429]
    restoring = tmp_path / "restoring"   # a new container still restoring its files
    monkeypatch.setattr(api, "PUBLISHED", restoring)
    monkeypatch.setattr(api, "all_waves", lambda: [{"id": 1}])   # the database's list: not the files
    assert call("/readyz")[0] == 503 and call("/healthz")[0] == 200
    (restoring / "api" / "v1").mkdir(parents=True)
    (restoring / "api" / "v1" / "waves.json.gz").write_bytes(gzip.compress(b"[]"))
    assert call("/readyz")[0] == 200 and json.loads(call("/readyz")[2])["ready"] is True


def test_the_minute_loop_builds_asks_index_for_a_new_published_version(monkeypatch):
    """The first question after a publish rebuilt the index while every other question waited (review of 15 Nov 2026):
    the minute loop builds it."""
    built, sleeps = [], []

    async def tick(seconds):
        sleeps.append(seconds)
        if len(sleeps) > 1:
            raise asyncio.CancelledError
    monkeypatch.setattr(api.asyncio, "sleep", tick)
    for name in ("published_changed", "_load_schedule"):
        monkeypatch.setattr(api, name, lambda: False)
    monkeypatch.setattr(api.signin, "load_revoked", lambda: None)
    for name in ("read_log_lists", "read_traffic", "measure_storage"):
        monkeypatch.setattr(api.metrics, name, lambda: None)
    monkeypatch.setattr(api, "warm_ask", lambda: built.append(1))
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(api._refresh_forever())
    assert built == [1]


def test_staff_and_a_client_less_outsider_never_share_a_cache_scope():
    # staff see commissioned studies an outsider does not; both had ":enterprise" (review of 20 Nov 2026)
    features = [f for f in access.rules()["features"] if f != "export"]
    staff = {"email": "a@coresight.com", "role": "analyst", "client": None, "tier": "enterprise", "study_types": "*", "features": features}
    outsider = {**staff, "email": "b@elsewhere.com", "role": "client"}
    assert access.scope(staff) != access.scope(outsider)


def test_ask_history_is_the_persons_own_questions_newest_first_each_once(portal):
    with api.get_engine("app").begin() as conn:
        for email, target, detail in [("boss@coresight.com", "How many shop at Amazon?", '{"mode": "figures"}'),
                                      ("boss@coresight.com", "What about Gen Z?", '{"mode": "figures", "asked_as": "how many shop at amazon among gen z"}'),
                                      ("pat@acme.com", "A client's question", None),
                                      ("boss@coresight.com", "how many shop at amazon?", None)]:   # asked again: listed once, newest
            conn.execute(sa.text("INSERT INTO cip_access_log (email, role, action, target, detail) VALUES (:e, 'x', 'ask', :t, :d)"),
                         {"e": email, "t": target, "d": detail})
    status, _, body = call("/api/v1/ask/history", signed("boss@coresight.com"))
    assert status == 200 and [q["question"] for q in json.loads(body)["questions"]] == \
        ["how many shop at amazon?", "how many shop at amazon among gen z"]
