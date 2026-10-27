"""The portal as an MCP connector: Claude (or any MCP client) searches the question library and reads results,
trends and cross-tabs, as the person whose API key it uses (app/core/api_keys.py), with that person's access.

Streamable HTTP, stateless: each POST /mcp carries one JSON-RPC message and gets one JSON answer. No vector
database: the client's model does the reasoning and calls search_questions (api/search.py: words, synonyms,
typos and plain-English questions) to find what to read. Connect with, for example:

    claude mcp add --transport http cip https://<portal>/mcp --header "Authorization: Bearer cip_…"
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, Response

from api.signin import user
from app.data import payloads
from etl.serving import CUTS

router = APIRouter()
VERSION = "2025-06-18"
INSTRUCTIONS = ("Coresight Research's Consumer Insight Portal: weekly US consumer surveys since 2020 and annual and ad hoc "
                "studies since 2018 (about 400 adults a week). Find questions with search_questions, then read one wave "
                "with question_results, its history with question_trend, or two demographic cuts with crosstab. "
                "Figures are unweighted percentages unless weighted=true; cite the survey, wave date and base (n).")

TOOLS = [
    {"name": "search_questions", "description": "Find survey questions by topic, words, brand or question code. Plain English works.",
     "inputSchema": {"type": "object", "required": ["query"], "properties": {
         "query": {"type": "string", "description": "e.g. 'holiday shopping status', 'GLP-1', 'XM3'"},
         "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10}}}},
    {"name": "list_waves", "description": "Survey waves, newest first, optionally of one family (e.g. CSI-US).",
     "inputSchema": {"type": "object", "properties": {
         "family": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20}}}},
    {"name": "question_results", "description": "One question in one wave: each answer's % for Total, gender and "
     "generation, the prior week and last year, and whether the change is significant.",
     "inputSchema": {"type": "object", "required": ["survey_id", "qcode"], "properties": {
         "survey_id": {"type": "integer"}, "qcode": {"type": "string"},
         "weighted": {"type": "boolean", "default": False, "description": "Census-weighted (gender, age, region)"}}}},
    {"name": "question_trend", "description": "One question's Total % for each answer across every wave of its survey family.",
     "inputSchema": {"type": "object", "required": ["survey_id", "qcode"], "properties": {
         "survey_id": {"type": "integer", "description": "any wave of the family that asked it"}, "qcode": {"type": "string"},
         "last": {"type": "integer", "minimum": 2, "maximum": 300, "default": 12, "description": "how many recent waves"}}}},
    {"name": "crosstab", "description": f"One question in one wave by two demographic cuts at once. Cuts: {', '.join(CUTS)}.",
     "inputSchema": {"type": "object", "required": ["survey_id", "qcode", "by"], "properties": {
         "survey_id": {"type": "integer"}, "qcode": {"type": "string"},
         "by": {"type": "array", "items": {"type": "string", "enum": list(CUTS)}, "minItems": 2, "maxItems": 2}}}},
]


@router.post("/mcp")
async def mcp(request: Request, who: dict = Depends(user)) -> Response:
    try:
        message = json.loads(await request.body())
    except ValueError:
        return JSONResponse(error(None, -32700, "Parse error"))
    if not isinstance(message, dict):
        return JSONResponse(error(None, -32600, "Send one JSON-RPC message per request"))
    if "id" not in message:   # a notification (notifications/initialized): nothing to answer
        return Response(status_code=202)
    method, params, ask = message.get("method"), message.get("params") or {}, message["id"]
    if method == "initialize":
        return JSONResponse(result(ask, {"protocolVersion": params.get("protocolVersion") or VERSION,
                                         "capabilities": {"tools": {}}, "instructions": INSTRUCTIONS,
                                         "serverInfo": {"name": "coresight-consumer-insight-portal", "version": "1.0"}}))
    if method == "ping":
        return JSONResponse(result(ask, {}))
    if method == "tools/list":
        return JSONResponse(result(ask, {"tools": TOOLS}))
    if method == "tools/call":
        name, args = params.get("name"), params.get("arguments") or {}
        if name not in CALLS:
            return JSONResponse(error(ask, -32602, f"Unknown tool: {name}"))
        try:
            found = await CALLS[name](who, **args)
        except HTTPException as exc:      # not visible, not found, not entitled: the model reads why
            return JSONResponse(result(ask, {"content": [{"type": "text", "text": str(exc.detail)}], "isError": True}))
        except (TypeError, ValueError, LookupError) as exc:
            return JSONResponse(result(ask, {"content": [{"type": "text", "text": f"Bad arguments: {exc}"}], "isError": True}))
        return JSONResponse(result(ask, {"content": [{"type": "text", "text": json.dumps(found, default=str)}]}))
    return JSONResponse(error(ask, -32601, f"Method not found: {method}"))


@router.get("/mcp")
async def no_stream() -> Response:
    return Response(status_code=405, headers={"Allow": "POST"})   # stateless: no server-sent event stream


def result(ask, body: dict) -> dict:
    return {"jsonrpc": "2.0", "id": ask, "result": body}


def error(ask, code: int, text: str) -> dict:
    return {"jsonrpc": "2.0", "id": ask, "error": {"code": code, "message": text}}


async def search_questions(who: dict, query: str, limit: int = 10) -> dict:
    from api import main
    main.need(who, "search")
    index = main.catalogue(who)
    found = index.search(str(query)[:100], max(1, min(int(limit), 50))) if index else {"results": [], "total": 0}
    kind = {w["survey_id"]: w["study_type"] for w in await run_in_threadpool(main.all_waves)}
    return {"total": found["total"], "results": [
        {"qcode": h["qcode"], "question": h["text"], "family": h["family"], "study_type": kind.get(h["survey_id"]),
         "latest_survey_id": h["survey_id"], "latest_title": h["title"], "first_asked": h["first"], "last_asked": h["last"],
         "waves": h["waves"]} for h in found["results"]]}


async def list_waves(who: dict, family: str = "", limit: int = 20) -> list[dict]:
    from api import main
    from app.core import access
    waves = [w for w in await run_in_threadpool(main.all_waves) if access.sees(who, w) and (not family or w["survey_family"] == family)]
    waves.sort(key=lambda w: str(w["wave_date"]), reverse=True)
    return [{k: w.get(k) for k in ("survey_id", "title", "wave_date", "survey_family", "study_type", "qualified_n")}
            for w in waves[:max(1, min(int(limit), 100))]]


async def question_results(who: dict, survey_id: int, qcode: str, weighted: bool = False) -> dict:
    from api import main
    wave = await main.visible(who, int(survey_id))
    book = await run_in_threadpool(main._book_data, int(survey_id))
    question = next((q for q in (book or {}).get("questions", []) if q["id"].lower() == str(qcode).lower()), None)
    if question is None:
        raise LookupError(f"{qcode} is not a charted question in survey {survey_id}")
    weighted = bool(weighted) and bool(book["wave"].get("weighting_available"))
    groups = []
    for g in question["groups"]:
        rows = []
        for r in g["rows"]:
            figures = {**r, **(r.get("w") or {})} if weighted else r
            rows.append({"answer": r["label"], **{c: figures.get(c) for c in book["columns"] if c in figures},
                         "prior_week": figures.get("prior"), "last_year": figures.get("ly"),
                         "significant_vs_prior": "sig_prior" in r.get("flags", ""),
                         "significant_vs_last_year": "sig_ly" in r.get("flags", "")})
        groups.append({"group": g["label"], "base_n": g["base"], "bases": g["bases"], "rows": rows})
    return {"survey_id": wave["survey_id"], "title": wave["title"], "wave_date": wave["wave_date"], "qcode": question["id"],
            "question": question["text"], "weighting": book["wave"].get("weighting_available") if weighted else "unweighted",
            "coded_open_end": question.get("coded"), "groups": groups}


async def question_trend(who: dict, survey_id: int, qcode: str, last: int = 12) -> dict:
    from api import main
    main.need(who, "trends")
    wave = await main.visible(who, int(survey_id))
    def build() -> dict:
        found = main._published("questions", wave["survey_family"], wave["study_type"], qcode)
        return json.loads(found.body) if found else payloads.question(wave["survey_family"], wave["study_type"], qcode)
    doc = await run_in_threadpool(build)
    from app.core import access
    shown = {w["survey_id"] for w in await run_in_threadpool(main.all_waves) if access.sees(who, w)}
    total = doc["cuts"].index(["total", "Total"]) if ["total", "Total"] in doc["cuts"] else None
    mine = next((w[2] for w in doc["waves"] if w[0] == wave["survey_id"]), None)   # this wording only: a code can be reused
    recent = sorted((i for i, w in enumerate(doc["waves"]) if w[0] in shown and w[2] == mine), key=lambda i: str(doc["waves"][i][1]))
    recent = set(recent[-max(2, min(int(last), 300)):])
    series: dict = {}
    for k, w in enumerate(doc["w"]):
        if w in recent and doc["c"][k] == total and doc["n"][k] is not None and doc["b"][k]:
            item, _, label = doc["answers"][doc["a"][k]]
            answer = label if not item or item == label else f"{item} · {label}"
            series.setdefault(answer, []).append({"wave_date": doc["waves"][w][1], "survey_id": doc["waves"][w][0],
                                                  "pct": round(100 * doc["n"][k] / doc["b"][k], 1), "base_n": doc["b"][k]})
    return {"qcode": doc["qcode"], "family": wave["survey_family"],
            "question": doc["versions"][mine - 1] if mine and len(doc.get("versions") or []) >= mine else None,   # version 1 = first wording
            "answers": {a: sorted(points, key=lambda p: str(p["wave_date"])) for a, points in series.items()}}


async def crosstab(who: dict, survey_id: int, qcode: str, by: list) -> dict:
    from api import main
    main.need(who, "crosstab")
    await main.visible(who, int(survey_id))
    if len(by) != 2 or len(set(by)) != 2 or not set(by) <= set(CUTS):
        raise ValueError(f"by takes two different cuts from: {', '.join(CUTS)}")
    cuts = tuple(by)
    item = await main._cached(
        (main.SERVING, "crosstab", int(survey_id), str(qcode), cuts, 1),
        main._crosstab_payload,
        int(survey_id),
        str(qcode),
        cuts,
        1,
    )
    found = json.loads(item.body)
    return {"qcode": found["qcode"], "by": found["by"], "columns": found["columns"], "rows": found["rows"]}


CALLS = {"search_questions": search_questions, "list_waves": list_waves, "question_results": question_results,
         "question_trend": question_trend, "crosstab": crosstab}
