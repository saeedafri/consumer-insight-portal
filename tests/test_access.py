"""Who gets in and what they see, over HTTP: sign-in, the cookie, revocation, roles, client scoping, limits, the error
shape, security headers and the audit log (api/signin.py, app/core/access.py, app/core/audit.py)."""
import asyncio
import gzip
import json
from urllib.parse import urlsplit

import pytest
import sqlalchemy as sa

import api.main as api
from api import signin, team
from app.core import access, audit, session


def call(path, cookie="", method="GET", body=b"", headers=None):
    """One request straight into the ASGI app: (status, headers as a dict of lists, body)."""
    parts = urlsplit(path)
    head = {**({"cookie": f"{api.COOKIE}={cookie}"} if cookie else {}), **(headers or {})}
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
    "features": ["dashboards", "explorer", "crosstab", "trends", "search", "ask", "export", "boards", "audiences", "alerts", "saved_views"],
    "tiers": {"core": {"features": ["dashboards", "explorer", "trends", "search", "export", "boards"], "study_types": ["tracker", "adhoc"]},
              "enterprise": {"features": "*", "study_types": "*"}},
    "staff": {"domains": ["coresight.com"], "admins": ["boss@coresight.com"], "tier": "enterprise"},
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
    assert call("/auth/logout", cookie)[0] == 200
    assert call("/api/v1/me", cookie)[0] == 401
    assert audit.write_pending() == 1
    with api.get_engine("app").connect() as conn:
        assert conn.execute(sa.text("SELECT email, action, ip_hash IS NOT NULL FROM cip_access_log")).one() == ("ana@coresight.com", "sign_out", 1)


def test_me_and_methodology_have_the_agreed_shapes_and_openapi_needs_a_session(portal):
    status, _, body = call("/api/v1/me", signed("boss@coresight.com"))
    me = json.loads(body)
    assert status == 200 and set(me) == {"email", "name", "role", "tier", "client", "features"} and me["role"] == "admin"
    assert json.loads(call("/api/v1/me", signed("pat@acme.com"))[2])["client"] == "acme"
    method = json.loads(call("/api/v1/methodology", signed("pat@acme.com"))[2])
    assert method["weighting"] == "none" and "small_cells" in method and "significance" in method
    assert call("/api/v1/openapi.json")[0] == 401 and call("/api/v1/openapi.json", signed("pat@acme.com"))[0] == 200
    assert json.loads(call("/healthz")[2]).keys() == {"ok", "build"}           # public: no internals
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
    assert api._published("waves", "1", "cuts", "x/../../book") is None and api._published("..", "waves") is None


def test_every_feature_the_portal_checks_is_one_the_config_knows():
    """web/src hides a link whose feature a sign-in lacks: a name missing from config/access.yml hides it from everyone
    (the Launch schedule link, 23 Oct 2026)."""
    from pathlib import Path
    import re
    checked = {m for f in Path("web/src").rglob("*.tsx") for m in re.findall(r'allowed\(me, "([a-z_]+)"\)', f.read_text())}
    assert checked and checked <= set(access.rules()["features"])
    assert set(access.profile("analyst@coresight.com")["features"]) >= checked   # staff see every page
