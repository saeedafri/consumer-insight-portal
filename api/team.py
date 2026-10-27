"""What the team keeps in the portal (sql/007_team.sql), written through the portal's own account (sql/004_grants.sql: it
may write only these tables): saved views anyone can open, metric alerts the pipeline checks
after every load, and audiences — saved groups of respondents (any cuts and answers combined) shown against any
question. Alerts and audiences follow the portal's rules: the same question version only, every figure shown (no significance under 30),
significance by the two-proportion z-test at 95 %.

Each client organisation sees only its own team's things (whose they are follows the owner's email, config/access.yml);
Coresight staff see Coresight's, admins see everything. The lists are kept in memory and dropped on any write: a write
touches CIP_TEAM_STAMP, which every worker on the host compares before answering from its copy.
"""
from __future__ import annotations

import gzip
import json
import os
import tempfile
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import bindparam, text

from api.dashboards import significant
from app.core import access, audit
from app.core.database import get_engine
from app.data import payloads
from app.data.harmonise import normalise_text
from app.data.payloads import HIDDEN_BASE, TEST_BASE
from etl.publish import ROOT as PUBLISH_ROOT
from etl.serving import CUTS

router = APIRouter(prefix="/api/v1")
STAMP = Path(os.environ.get("CIP_TEAM_STAMP") or Path(tempfile.gettempdir()) / "cip-team.stamp")
CACHE: dict[tuple, tuple[int, object]] = {}


def _person(body: dict) -> str:
    name = " ".join(str(body.get("by") or "").split())[:120]
    if not name:
        raise HTTPException(422, "Say who you are (your name), so the team knows whose it is")
    return name


async def json_body(request: Request) -> dict:
    """The request's JSON object, or 422: a malformed body or a list is the caller's mistake, not a server error."""
    try:
        body = await request.json()
    except ValueError:
        raise HTTPException(422, "The request body is not valid JSON")
    if not isinstance(body, dict):
        raise HTTPException(422, "The request body must be a JSON object")
    return body


def email_of(request: Request) -> str:
    """The signed-in person (api/signin.user puts it on the request): who owns a board, an item, a comment, an alert."""
    return getattr(request.state, "email", "") or "unknown"


EVERYONE = {"email": "pipeline", "role": "admin", "client": None, "features": [], "study_types": "*"}


def person_of(request: Request | None) -> dict:
    """Who is asking. None is a call from Python (the pipeline, tests), never over HTTP: it sees everything."""
    if request is None:
        return {**EVERYONE, "features": access.rules()["features"]}
    found = getattr(request.state, "person", None) or access.profile(email_of(request))
    if not found:
        raise HTTPException(401, "Sign in required")
    return found


def need(request: Request | None, feature: str) -> dict:
    who = person_of(request)
    if not access.allows(who, feature):
        raise HTTPException(403, "Not included in your subscription")
    return who


def mine(who: dict, owner: str | None) -> bool:
    """Is a thing owned by `owner` (an email, or None for one saved before owners were recorded) in this person's team."""
    if who["role"] == "admin":
        return True
    found = access.profile(owner) if owner else None
    return (found["client"] if found else None) == who["client"]


def stamp() -> int:
    try:
        return STAMP.stat().st_mtime_ns
    except OSError:
        return 0


def changed() -> None:
    STAMP.touch()
    CACHE.clear()


def cached(key: tuple, load):
    """load() once per team change (any worker's write), per database: the team endpoints are polled on every page."""
    key = (id(get_engine("app")), *key)
    now = stamp()
    hit = CACHE.get(key)
    if hit and hit[0] == now:
        return hit[1]
    value = load()
    CACHE[key] = (now, value)
    return value


def remove(table: str, key_column: str, owner_column: str, key: int, request: Request) -> None:
    """Only whoever made a thing (or an admin) removes it; one saved with no owner, only an admin. One round trip when
    it is yours; a second only to say why not."""
    who = person_of(request)
    admin = who["role"] == "admin"
    with get_engine("api_write").begin() as conn:
        gone = conn.execute(text(f"DELETE FROM {table} WHERE {key_column} = :k" + ("" if admin else f" AND {owner_column} = :me")),
                            {"k": key, "me": who["email"]}).rowcount
        if not gone:
            row = conn.execute(text(f"SELECT {owner_column} FROM {table} WHERE {key_column} = :k"), {"k": key}).first()
            if row is None or not mine(who, row[0]):
                raise HTTPException(404, "Not found")
            raise HTTPException(403, f"Only {row[0]} can remove this" if row[0] else "Only an admin can remove this")
    changed()
    audit.record(request, f"{table.removeprefix('cip_')}_remove", target=key)


def _rows(sql: str, **params) -> list[dict]:
    with get_engine("app").connect() as conn:
        return [dict(r) for r in conn.execute(text(sql), params).mappings()]


@lru_cache(maxsize=2048)
def wave_of(survey_id: int) -> dict | None:
    """{survey_id, survey_family, study_type} of a built wave (they never change), for the visibility rule."""
    found = _rows("SELECT survey_id, survey_family, study_type FROM srv_wave WHERE survey_id = :s", s=survey_id)
    return found[0] if found else None


def open_wave(who: dict, survey_id: int) -> dict:
    wave = wave_of(survey_id)
    if not wave or not access.sees(who, wave):
        raise HTTPException(404, "No such wave")
    return wave


# ── saved views ────────────────────────────────────────────────────────────
def scoped(request: Request | None, feature: str, key: str, sql: str) -> list[dict]:
    """A team list as this person's team sees it (owner column dropped), from memory when nothing changed."""
    who = need(request, feature)
    return [{k: v for k, v in r.items() if k != "_owner"} for r in cached((key,), lambda: _rows(sql)) if mine(who, r["_owner"])]


VIEWS = "SELECT view_id, name, url, note, saved_by, created_at, owner_email AS _owner FROM cip_team_view ORDER BY created_at DESC LIMIT 500"
ALERTS = ("SELECT alert_id, name, survey_family, study_type, qcode, answer_label, dim, dim_value, against, created_by,"
          " created_at, last_fired, owner_email AS _owner FROM cip_metric_alert ORDER BY created_at DESC LIMIT 500")
AUDIENCES = "SELECT audience_id, name, definition, created_by, created_at, owner_email AS _owner FROM cip_audience ORDER BY name LIMIT 500"
BOARDS = ("SELECT b.board_id, b.name, b.created_by, b.created_at, COUNT(i.item_id) AS items, b.created_by AS _owner FROM cip_board b"
          " LEFT JOIN cip_board_item i ON i.board_id = b.board_id GROUP BY b.board_id, b.name, b.created_by, b.created_at"
          " ORDER BY b.created_at DESC LIMIT 500")


@router.get("/team/views")
def views(request: Request = None) -> list[dict]:
    return scoped(request, "saved_views", "views", VIEWS)


@router.post("/team/views", status_code=201)
async def save_view(request: Request) -> dict:
    need(request, "saved_views")
    body = await json_body(request)
    url, name = str(body.get("url") or ""), " ".join(str(body.get("name") or "").split())[:200]
    if not url.startswith("/w/") or len(url) > 1000 or not name:
        raise HTTPException(422, "A view needs a name and a portal screen (/w/…)")
    with get_engine("api_write").begin() as conn:
        view_id = conn.execute(text("INSERT INTO cip_team_view (name, url, note, saved_by, owner_email) VALUES (:n, :u, :note, :by, :o)"),
                               {"n": name, "u": url, "note": (str(body.get("note") or "")[:1000] or None), "by": _person(body),
                                "o": email_of(request)}).lastrowid
    changed()
    audit.record(request, "view_save", target=view_id, detail={"url": url})
    return {"view_id": view_id}


@router.delete("/team/views/{view_id}", status_code=204)
def drop_view(view_id: int, request: Request) -> None:
    remove("cip_team_view", "view_id", "owner_email", view_id, request)


# ── metric alerts ──────────────────────────────────────────────────────────
@router.get("/alerts")
def alerts(request: Request = None) -> list[dict]:
    return scoped(request, "alerts", "alerts", ALERTS)


@router.post("/alerts", status_code=201)
async def save_alert(request: Request) -> dict:
    """{survey_id, qcode, item_label, option_code, answer_label, dim, dim_value, against, name, by}: the wave fixes the
    family and the question's wording, so a later wave that reuses the code for another question never fires it."""
    who = need(request, "alerts")
    body = await json_body(request)
    dim, against = str(body.get("dim") or "total"), str(body.get("against") or "prior")
    if dim not in ("total",) + CUTS or against not in ("prior", "ly"):
        raise HTTPException(422, "dim is total or a cut; against is prior or ly")
    try:
        survey_id = int(body.get("survey_id") or 0)
    except (TypeError, ValueError):
        raise HTTPException(422, "survey_id is a wave number")
    open_wave(who, survey_id)
    found = _rows("SELECT w.survey_family, w.study_type, q.qtext FROM srv_wave w JOIN cip_question q ON q.survey_id = w.survey_id"
                  " AND q.qcode = :q WHERE w.survey_id = :s", s=survey_id, q=str(body.get("qcode") or ""))
    if not found:
        raise HTTPException(404, "That question is not in that wave")
    with get_engine("api_write").begin() as conn:
        alert_id = conn.execute(text(
            "INSERT INTO cip_metric_alert (name, survey_family, study_type, qcode, qtext, item_label, option_code, answer_label,"
            " dim, dim_value, against, created_by, notify_email, owner_email, last_checked)"
            " VALUES (:name, :f, :t, :q, :qt, :il, :oc, :al, :d, :v, :ag, :by, :email, :o, :s)"),
            {"name": " ".join(str(body.get("name") or body.get("answer_label") or "")[:200].split()), "f": found[0]["survey_family"],
             "t": found[0]["study_type"], "q": body["qcode"], "qt": found[0]["qtext"], "il": str(body.get("item_label") or "")[:255],
             "oc": body.get("option_code"), "al": str(body.get("answer_label") or "")[:500], "d": dim,
             "v": str(body.get("dim_value") or "Total")[:120], "ag": against, "by": _person(body),
             "email": email_of(request) if body.get("email_me", True) else None, "o": email_of(request),
             "s": survey_id}).lastrowid
    changed()
    audit.record(request, "alert_save", survey_id=survey_id, target=alert_id, detail={"qcode": body["qcode"]})
    return {"alert_id": alert_id}


@router.delete("/alerts/{alert_id}", status_code=204)
def drop_alert(alert_id: int, request: Request) -> None:
    remove("cip_metric_alert", "alert_id", "owner_email", alert_id, request)


def due_alerts(survey_ids: list[int]) -> list[tuple[str, str | None]]:
    """Judge every alert once against each new wave of its family: a message when the answer moved significantly vs
    its baseline (previous wave or last year), on the same question version, with 30+ people on both sides (TEST_BASE). Returns
    (message, email of who set it); the pipeline posts each to Teams and emails that person (scripts/weekly_forsta.py)."""
    if not survey_ids:
        return []
    messages = []
    with get_engine("etl").begin() as conn:
        waves = {r["survey_id"]: r for r in conn.execute(text(
            "SELECT survey_id, survey_family, study_type, wave_date FROM srv_wave WHERE survey_id IN :ids")
            .bindparams(bindparam("ids", expanding=True)), {"ids": survey_ids}).mappings()}
        for a in [dict(r) for r in conn.execute(text("SELECT * FROM cip_metric_alert")).mappings()]:
            for sid in sorted(s for s, w in waves.items() if (w["survey_family"], w["study_type"]) == (a["survey_family"], a["study_type"])
                              and s > (a["last_checked"] or 0)):
                row = conn.execute(text(
                    "SELECT r.pct, r.base_n, r.prior_pct, r.prior_base_n, r.ly_pct, r.ly_base_n, r.flags, q.qtext FROM srv_result r"
                    " JOIN cip_question q ON q.question_id = r.question_id WHERE r.survey_id = :s AND r.qcode = :q AND r.dim = :d"
                    " AND r.dim_value = :v AND r.item_label = :il AND (r.option_code = :oc OR (r.option_code IS NULL AND :oc IS NULL))"),
                    {"s": sid, "q": a["qcode"], "d": a["dim"], "v": a["dim_value"], "il": a["item_label"], "oc": a["option_code"]}).mappings().first()
                conn.execute(text("UPDATE cip_metric_alert SET last_checked = :s WHERE alert_id = :a"), {"s": sid, "a": a["alert_id"]})
                key = a["against"]
                if not row or normalise_text(row["qtext"]) != normalise_text(a["qtext"]) or row[f"{key}_pct"] is None \
                        or f"base_changed_{key}" in (row["flags"] or "") or min(row["base_n"], row[f"{key}_base_n"] or 0) < TEST_BASE:
                    continue
                now, then = float(row["pct"]), float(row[f"{key}_pct"])
                if significant(now, row["base_n"], then, row[f"{key}_base_n"]):
                    conn.execute(text("UPDATE cip_metric_alert SET last_fired = :s WHERE alert_id = :a"), {"s": sid, "a": a["alert_id"]})
                    group = "" if a["dim"] == "total" else f" among {a['dim_value']}"
                    messages.append((
                        f"📈 CIP alert “{a['name']}”: {a['answer_label']}{group} is {now:.1f}% in the wave of {waves[sid]['wave_date']}, "
                        f"{'up' if now > then else 'down'} {abs(now - then):.1f} pts from {then:.1f}% "
                        f"{'the previous wave' if key == 'prior' else 'a year earlier'} (n={row['base_n']} vs {row[f'{key}_base_n']}), "
                        f"significant at 95 %. Open /w/{sid}/questions/{a['qcode']} · set by {a['created_by']}", a.get("notify_email")))
    return messages


# ── audiences ──────────────────────────────────────────────────────────────
@router.get("/audiences")
def audiences(request: Request = None) -> list[dict]:
    return [{**a, "definition": json.loads(a["definition"])} for a in scoped(request, "audiences", "audiences", AUDIENCES)]


def _definition(body) -> dict:
    """{"cuts": {dim: [values]}, "answers": [{qcode, qtext, item_label, option_code, label}]}, checked."""
    cuts = {d: [str(v)[:120] for v in vs][:20] for d, vs in (body.get("cuts") or {}).items() if d in CUTS and vs}
    answers = [{"qcode": str(a["qcode"])[:50], "qtext": str(a.get("qtext") or "")[:2000], "item_label": str(a.get("item_label") or "")[:255],
                "option_code": a.get("option_code"), "label": str(a.get("label") or "")[:500]} for a in (body.get("answers") or [])][:8]
    if not cuts and not answers:
        raise HTTPException(422, "An audience needs at least one cut or answer")
    return {"cuts": cuts, "answers": answers}


@router.post("/audiences", status_code=201)
async def save_audience(request: Request) -> dict:
    need(request, "audiences")
    body = await json_body(request)
    definition, name = _definition(body.get("definition") or {}), " ".join(str(body.get("name") or "").split())[:200]
    if not name:
        raise HTTPException(422, "Name the audience")
    with get_engine("api_write").begin() as conn:
        audience_id = conn.execute(text("INSERT INTO cip_audience (name, definition, created_by, owner_email) VALUES (:n, :d, :by, :o)"),
                                   {"n": name, "d": json.dumps(definition), "by": _person(body), "o": email_of(request)}).lastrowid
    changed()
    audit.record(request, "audience_save", target=audience_id, detail=definition)
    return {"audience_id": audience_id}


@router.delete("/audiences/{audience_id}", status_code=204)
def drop_audience(audience_id: int, request: Request) -> None:
    remove("cip_audience", "audience_id", "owner_email", audience_id, request)


@router.post("/waves/{survey_id}/audience")
async def audience_view(survey_id: int, request: Request) -> dict:
    who = need(request, "audiences")
    if not access.spend(who["email"], "audience"):
        raise HTTPException(429, "Too many audience requests: wait a minute", headers={"Retry-After": "60"})
    body = await json_body(request)
    open_wave(who, survey_id)
    return audience(survey_id, str(body.get("qcode") or ""), _definition(body.get("definition") or {}))


@router.post("/waves/{survey_id}/audience/profile")
async def audience_profile_view(survey_id: int, request: Request) -> dict:
    who = need(request, "audiences")
    if not access.spend(who["email"], "audience"):
        raise HTTPException(429, "Too many audience requests: wait a minute", headers={"Retry-After": "60"})
    body = await json_body(request)
    open_wave(who, survey_id)
    return audience_profile(survey_id, _definition(body.get("definition") or {}))


@lru_cache(maxsize=16)   # ~0.1–1 MB per wave; a new publish is a new version, so old waves are never asked for again
def _people(survey_id: int, version: str) -> dict:
    """The wave's respondent bitsets (payloads.people) with hex as ints and "item_id,option_id" keys as tuples: the
    published file, or built from srv_answer for a wave loaded since the last publish."""
    try:
        doc = json.loads(gzip.decompress((Path(version) / f"api/v1/waves/{survey_id}/people.json.gz").read_bytes()))
    except OSError:
        with get_engine("app").connect() as conn:
            doc = json.loads(payloads.encode(payloads.people(conn, survey_id)))
    return {"cuts": {d: {v: int(h, 16) for v, h in values.items()} for d, values in doc["cuts"].items()},
            "questions": {q: {**body, "bits": {tuple(map(int, k.split(","))): int(h, 16) for k, h in body["bits"].items()}}
                          for q, body in doc["questions"].items()}}


def audience(survey_id: int, qcode: str, definition: dict) -> dict:
    """One question for an audience in one wave, next to everyone else: rows [label, aud_n, aud_base, aud_pct,
    rest_pct, rest_base, sig (+1 higher, -1 lower, 0), index], counted from the wave's respondent bitsets
    (payloads.people). index = 100 × the audience's share ÷ everyone's (120 = 20 % more likely than all respondents).
    An answer condition counts only where this wave asked the same question. An audience under min_audience
    (config/access.yml) shows no figures."""
    wave = _people(survey_id, os.path.realpath(PUBLISH_ROOT / "current"))
    question = wave["questions"].get(qcode)
    if not question:
        raise HTTPException(404, "That question is not in that wave")
    group, skipped = _group(wave, definition)
    rows = [row[:-1] for row in _compare(question, group)]
    return {"survey_id": survey_id, "qcode": qcode, "multi": _multi(question), "skipped": skipped,
            "columns": ["answer", "n", "base", "pct", "rest_pct", "rest_base", "sig", "index"], "rows": rows}


def audience_profile(survey_id: int, definition: dict, top: int = 15) -> dict:
    """What sets an audience apart in one wave: across every question, the answers it gives most and least often
    compared with all respondents (index), kept only where the difference is significant, the audience has
    min_audience people and the answer is not rare (at least 5 % of everyone)."""
    wave = _people(survey_id, os.path.realpath(PUBLISH_ROOT / "current"))
    group, skipped = _group(wave, definition)
    picked = {a["qcode"] for a in definition["answers"]}   # answers the audience is defined by say nothing new
    found = []
    for qcode, question in wave["questions"].items():
        if qcode in picked:
            continue
        for label, n, b, pct, rest, rest_b, sig, index, everyone in _compare(question, group):
            if sig and index is not None and everyone >= 5:
                found.append({"qcode": qcode, "question": question["text"], "answer": label, "pct": pct,
                              "everyone": everyone, "index": index, "base": b})
    found.sort(key=lambda f: f["index"])
    over = [f for f in reversed(found) if f["index"] > 100][:top]
    under = [f for f in found if f["index"] < 100][:top]
    size = (group & _everyone(wave)).bit_count()
    return {"survey_id": survey_id, "size": size, "skipped": skipped, "over": over, "under": under}


def _everyone(wave: dict) -> int:
    """Every respondent of the wave: anyone with an answer."""
    every = 0
    for q in wave["questions"].values():
        for b in q["bits"].values():
            every |= b
    return every


def _group(wave: dict, definition: dict) -> tuple[int, list]:
    """The audience as a bitset (-1 = everyone) and the answer conditions this wave could not apply."""
    group, skipped = -1, []   # -1 has every bit set: no condition yet means everyone
    for dim, values in definition["cuts"].items():
        group &= sum(set(wave["cuts"].get(dim, {}).get(v, 0) for v in values))   # values of one cut never share a person
    for a in definition["answers"]:
        other = wave["questions"].get(a["qcode"])
        hit = next((r for r in other["rows"] if r[2] == a["item_label"] and r[3] == a["option_code"]), None) if other else None
        if not hit or (a["qtext"] and other["text"] != normalise_text(a["qtext"])):
            skipped.append(a["label"] or a["qcode"])   # not asked in this wave, or the code means another question
            continue
        group &= other["bits"].get((hit[0], hit[1]), 0)
    return group, skipped


def _multi(question: dict) -> bool:
    return all(r[1] == 0 for r in question["rows"])


def _compare(question: dict, group: int) -> list[list]:
    """The question's rows for the audience against everyone else: [label, n, base, pct, rest_pct, rest_base, sig,
    index, everyone's pct]."""
    mine = {key: (b & group).bit_count() for key, b in question["bits"].items()}
    everyone = {key: b.bit_count() for key, b in question["bits"].items()}
    labels = [dict(zip(("item_id", "option_id", "item_label", "option_code", "option_label"), r)) for r in question["rows"]]
    multi = _multi(question)
    smallest = max(HIDDEN_BASE, int(access.rules().get("min_audience", HIDDEN_BASE)))

    def base(counts, item):   # multi: answered the question (its base rows); single: answered this row
        return counts.get((0, 0), 0) if multi else sum(n for (i, o), n in counts.items() if i == item and o)
    rows = []
    for r in labels:
        key = (r["item_id"], r["option_id"])
        b, b_all = base(mine, r["item_id"]), base(everyone, r["item_id"])
        n, n_all = mine.get(key, 0), everyone.get(key, 0)
        rest_b, rest_n = b_all - b, n_all - n
        label = r["item_label"] if multi else (f"{r['item_label']} · {r['option_label']}" if r["item_label"] else r["option_label"])
        if b < smallest or 0 < rest_b < HIDDEN_BASE:
            rows.append([label, None, None if b < smallest else b, None, None, None if rest_b < HIDDEN_BASE else rest_b, 0, None, None])
            continue
        pct, rest = 100 * n / b, (100 * rest_n / rest_b if rest_b else None)
        whole = 100 * n_all / b_all if b_all else None
        sig = 0
        if rest is not None and significant(pct, b, rest, rest_b):
            sig = 1 if pct > rest else -1
        index = round(100 * pct / whole) if whole else None
        rows.append([label, n, b, round(pct, 1), None if rest is None else round(rest, 1), rest_b, sig, index,
                     None if whole is None else round(whole, 1)])
    return rows


# ── boards: tables pinned as they were, comments, one deck ────────────────
def data_version() -> str:
    return Path(os.path.realpath(PUBLISH_ROOT / "current")).name


@router.get("/boards")
def boards(request: Request = None) -> list[dict]:
    return scoped(request, "boards", "boards", BOARDS)


@router.post("/boards", status_code=201)
async def new_board(request: Request) -> dict:
    need(request, "boards")
    name = " ".join(str((await json_body(request)).get("name") or "").split())[:200]
    if not name:
        raise HTTPException(422, "A board needs a name")
    with get_engine("api_write").begin() as conn:
        board_id = conn.execute(text("INSERT INTO cip_board (name, created_by) VALUES (:n, :by)"),
                                {"n": name, "by": email_of(request)}).lastrowid
    changed()
    audit.record(request, "board_new", target=board_id)
    return {"board_id": board_id}


BOARD = ("SELECT b.board_id, b.name, b.created_by, b.created_at, i.item_id, i.title, i.url, i.spec, i.data_version, i.added_by,"
         " i.added_at, c.comment_id, c.author, c.body, c.created_at AS commented_at FROM cip_board b"
         " LEFT JOIN cip_board_item i ON i.board_id = b.board_id LEFT JOIN cip_board_comment c ON c.item_id = i.item_id"
         " WHERE b.board_id = :b ORDER BY i.item_id, c.comment_id")


def board(board_id: int, request: Request = None) -> dict:
    """The board, its items and their comments in one round trip (one row per comment), kept until the team changes.
    ponytail: an item's spec repeats on each of its comment rows; fine for tens of comments, split the read if boards grow."""
    def load() -> dict | None:
        rows = _rows(BOARD, b=board_id)
        if not rows:
            return None
        items: dict = {}
        for r in rows:
            if r["item_id"] is not None and r["item_id"] not in items:
                items[r["item_id"]] = {k: r[k] for k in ("item_id", "title", "url", "data_version", "added_by", "added_at")} \
                    | {"spec": json.loads(r["spec"]), "comments": []}
            if r["comment_id"] is not None:
                items[r["item_id"]]["comments"].append({"comment_id": r["comment_id"], "item_id": r["item_id"], "author": r["author"],
                                                        "body": r["body"], "created_at": r["commented_at"]})
        return {**{k: rows[0][k] for k in ("board_id", "name", "created_by", "created_at")}, "items": list(items.values())}
    found = cached(("board", board_id), load)
    if found is None or not mine(need(request, "boards"), found["created_by"]):
        raise HTTPException(404, "No such board")
    return {**found, "current_version": data_version()}


@router.get("/boards/{board_id}")
def open_board(board_id: int, request: Request = None) -> dict:
    return board(board_id, request)


@router.delete("/boards/{board_id}", status_code=204)
def drop_board(board_id: int, request: Request) -> None:
    remove("cip_board", "board_id", "created_by", board_id, request)


@router.post("/boards/{board_id}/items", status_code=201)
async def pin(board_id: int, request: Request) -> dict:
    """{title, url, spec}: spec is the table the screen exports (api/exports.check), kept as it is now. Only onto a
    board of this person's own team."""
    from api.exports import check
    who = need(request, "boards")
    body = await json_body(request)
    url = str(body.get("url") or "")
    try:
        spec = check(body.get("spec") or {})
    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(422, str(exc))
    if not url.startswith("/w/") or len(url) > 1000:
        raise HTTPException(422, "An item needs its portal screen (/w/…)")
    with get_engine("api_write").begin() as conn:
        owner = conn.execute(text("SELECT created_by FROM cip_board WHERE board_id = :b"), {"b": board_id}).first()
        if owner is None or not mine(who, owner[0]):
            raise HTTPException(404, "No such board")
        item_id = conn.execute(text(
            "INSERT INTO cip_board_item (board_id, title, url, spec, data_version, added_by) VALUES (:b, :t, :u, :s, :v, :by)"),
            {"b": board_id, "t": " ".join(str(body.get("title") or spec["name"]).split())[:300], "u": url,
             "s": json.dumps(spec, separators=(",", ":")), "v": data_version(), "by": email_of(request)}).lastrowid
    changed()
    audit.record(request, "board_pin", target=board_id, detail={"item_id": item_id, "url": url})
    return {"item_id": item_id}


@router.delete("/boards/items/{item_id}", status_code=204)
def unpin(item_id: int, request: Request) -> None:
    remove("cip_board_item", "item_id", "added_by", item_id, request)


@router.post("/boards/items/{item_id}/comments", status_code=201)
async def comment(item_id: int, request: Request) -> dict:
    who = need(request, "boards")
    body = str((await json_body(request)).get("body") or "").strip()[:2000]
    if not body:
        raise HTTPException(422, "Write something")
    with get_engine("api_write").begin() as conn:
        owner = conn.execute(text("SELECT b.created_by FROM cip_board_item i JOIN cip_board b ON b.board_id = i.board_id"
                                  " WHERE i.item_id = :i"), {"i": item_id}).first()
        if owner is None or not mine(who, owner[0]):
            raise HTTPException(404, "No such item")
        comment_id = conn.execute(text("INSERT INTO cip_board_comment (item_id, author, body) VALUES (:i, :a, :b)"),
                                  {"i": item_id, "a": email_of(request), "b": body}).lastrowid
    changed()
    audit.record(request, "board_comment", target=item_id)
    return {"comment_id": comment_id}


@router.delete("/boards/comments/{comment_id}", status_code=204)
def drop_comment(comment_id: int, request: Request) -> None:
    remove("cip_board_comment", "comment_id", "author", comment_id, request)


@router.get("/team/summary")
def summary(request: Request = None) -> dict:
    """Boards, saved views, alerts and audiences in one answer (each list as its own route gives it; an empty list for a
    feature the person's tier lacks), so a page needs one request instead of four."""
    who = person_of(request) if request is not None else None
    def part(feature, load):
        return load(request) if who is None or access.allows(who, feature) else []
    return {"boards": part("boards", boards), "views": part("saved_views", views), "alerts": part("alerts", alerts),
            "audiences": part("audiences", audiences)}


@router.get("/boards/{board_id}/deck")
def deck(board_id: int, request: Request = None):
    """The whole board as one branded PowerPoint: a cover, then each pinned table as it was pinned."""
    from fastapi import Response
    from api.exports import deck_pptx
    b = board(board_id, request)
    if request is not None:
        if not access.allows(person_of(request), "export"):
            raise HTTPException(403, "Not included in your subscription")
        audit.record(request, "export", target=f"board {board_id}", detail={"kind": "deck"})
    if not b["items"]:
        raise HTTPException(422, "Pin something to the board first")
    when = b["created_at"].strftime("%d %b %Y") if hasattr(b["created_at"], "strftime") else str(b["created_at"])[:10]
    body = deck_pptx(b["name"], f"By {b['created_by']} · {when}", [{**i["spec"], "notes": [*i["spec"]["notes"],
                     f"Pinned {str(i['added_at'])[:10]} by {i['added_by']} · data version {i['data_version']}"]} for i in b["items"]])
    name = "".join(c if c.isalnum() or c in "-_" else "-" for c in b["name"])[:60] or "board"
    return Response(body, media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    headers={"Content-Disposition": f'attachment; filename="{name}.pptx"'})
