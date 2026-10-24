"""The MCP connector (api/mcp.py) and API keys (app/core/api_keys.py)."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import mcp
from api.signin import user
from app.core import api_keys


def client(monkeypatch):
    async def echo(who, query, limit=10):
        return {"who": who["email"], "query": query, "limit": limit}
    monkeypatch.setitem(mcp.CALLS, "search_questions", echo)
    app = FastAPI()
    app.include_router(mcp.router)
    app.dependency_overrides[user] = lambda: {"email": "ana@coresight.com"}
    return TestClient(app)


def test_the_connector_speaks_json_rpc(monkeypatch):
    c = client(monkeypatch)
    ask = lambda body: c.post("/mcp", json={"jsonrpc": "2.0", "id": 1, **body}).json()
    assert ask({"method": "initialize", "params": {"protocolVersion": "2025-06-18"}})["result"]["capabilities"] == {"tools": {}}
    assert {t["name"] for t in ask({"method": "tools/list"})["result"]["tools"]} == set(mcp.CALLS)
    called = ask({"method": "tools/call", "params": {"name": "search_questions", "arguments": {"query": "tariffs"}}})
    assert '"who": "ana@coresight.com"' in called["result"]["content"][0]["text"]
    assert ask({"method": "tools/call", "params": {"name": "search_questions", "arguments": {"nope": 1}}})["result"]["isError"]
    assert ask({"method": "nope"})["error"]["code"] == -32601
    assert c.post("/mcp", json={"jsonrpc": "2.0", "method": "notifications/initialized"}).status_code == 202


def test_an_api_key_is_kept_only_as_a_hash_and_can_be_revoked(tmp_path, monkeypatch):
    monkeypatch.setattr(api_keys, "FILE", tmp_path / "keys.yml")
    token = api_keys.new("Ana@Coresight.com", "Ana's Claude")
    assert api_keys.owner(token) == "ana@coresight.com" and token not in (tmp_path / "keys.yml").read_text()
    assert api_keys.owner("cip_wrong") is None and api_keys.owner("not-a-key") is None
    api_keys.save({})
    assert api_keys.owner(token) is None
