"""What the team keeps in the portal (sql/007_team.sql), written through the portal's own account (sql/004_grants.sql: it
may write only these tables): saved views anyone can open, metric alerts the pipeline checks
after every load, and audiences — saved groups of respondents (any cuts and answers combined) shown against any
question. Alerts and audiences follow the portal's rules: the same question version only, nothing under 5 people (no significance under 30),
significance by the two-proportion z-test at 95 %.
"""
from __future__ import annotations

import gzip
import json
import os
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import bindparam, text

from api.dashboards import significant
from app.core.database import get_engine
from app.data import payloads
from app.data.harmonise import normalise_text
from app.data.payloads import HIDDEN_BASE, TEST_BASE
from etl.publish import ROOT as PUBLISH_ROOT
from etl.serving import CUTS

router = APIRouter(prefix="/api/v1")


def _person(body: dict) -> str:
    name = " ".join(str(body.get("by") or "").split())[:120]
    if not name:
        raise HTTPException(422, "Say who you are (your name), so the team knows whose it is")
    return name


def email_of(request: Request) -> str:
    """The signed-in person (api/main.user puts it on the request): who owns a board, an item, a comment, an alert."""
    return getattr(request.state, "email", "") or "unknown"


def owned(conn, sql: str, key: int, request: Request) -> None:
    """Only whoever made a thing removes it (anyone may remove one saved before owners were recorded)."""
    row = conn.execute(text(sql), {"k": key}).first()
    if row is None:
        raise HTTPException(404, "Not found")
    owner = row[0]
    if owner and owner != email_of(request):
        raise HTTPException(403, f"Only {owner} can remove this")


def _rows(sql: str, **params) -> list[dict]:
    with get_engine("app").connect() as conn:
        return [dict(r) for r in conn.execute(text(sql), params).mappings()]


# ── saved views ────────────────────────────────────────────────────────────
@router.get("/team/views")
def views() -> list[dict]:
    return _rows("SELECT view_id, name, url, note, saved_by, created_at FROM cip_team_view ORDER BY created_at DESC LIMIT 500")


@router.post("/team/views", status_code=201)
async def save_view(request: Request) -> dict:
    body = await request.json()
    url, name = str(body.get("url") or ""), " ".join(str(body.get("name") or "").split())[:200]
    if not url.startswith("/w/") or len(url) > 1000 or not name:
        raise HTTPException(422, "A view needs a name and a portal screen (/w/…)")
    with get_engine("app").begin() as conn:
        view_id = conn.execute(text("INSERT INTO cip_team_view (name, url, note, saved_by, owner_email) VALUES (:n, :u, :note, :by, :o)"),
                               {"n": name, "u": url, "note": (str(body.get("note") or "")[:1000] or None), "by": _person(body),
                                "o": email_of(request)}).lastrowid
    return {"view_id": view_id}


@router.delete("/team/views/{view_id}", status_code=204)
def drop_view(view_id: int, request: Request) -> None:
    with get_engine("app").begin() as conn:
        owned(conn, "SELECT owner_email FROM cip_team_view WHERE view_id = :k", view_id, request)
        conn.execute(text("DELETE FROM cip_team_view WHERE view_id = :v"), {"v": view_id})


# ── metric alerts ──────────────────────────────────────────────────────────
@router.get("/alerts")
def alerts() -> list[dict]:
    return _rows("SELECT alert_id, name, survey_family, study_type, qcode, answer_label, dim, dim_value, against, created_by,"
                 " created_at, last_fired FROM cip_metric_alert ORDER BY created_at DESC")


@router.post("/alerts", status_code=201)
async def save_alert(request: Request) -> dict:
    """{survey_id, qcode, item_label, option_code, answer_label, dim, dim_value, against, name, by}: the wave fixes the
    family and the question's wording, so a later wave that reuses the code for another question never fires it."""
    body = await request.json()
    dim, against = str(body.get("dim") or "total"), str(body.get("against") or "prior")
    if dim not in ("total",) + CUTS or against not in ("prior", "ly"):
        raise HTTPException(422, "dim is total or a cut; against is prior or ly")
    found = _rows("SELECT w.survey_family, w.study_type, q.qtext FROM srv_wave w JOIN cip_question q ON q.survey_id = w.survey_id"
                  " AND q.qcode = :q WHERE w.survey_id = :s", s=int(body.get("survey_id") or 0), q=str(body.get("qcode") or ""))
    if not found:
        raise HTTPException(404, "That question is not in that wave")
    with get_engine("app").begin() as conn:
        alert_id = conn.execute(text(
            "INSERT INTO cip_metric_alert (name, survey_family, study_type, qcode, qtext, item_label, option_code, answer_label,"
            " dim, dim_value, against, created_by, notify_email, owner_email, last_checked)"
            " VALUES (:name, :f, :t, :q, :qt, :il, :oc, :al, :d, :v, :ag, :by, :email, :o, :s)"),
            {"name": " ".join(str(body.get("name") or body.get("answer_label") or "")[:200].split()), "f": found[0]["survey_family"],
             "t": found[0]["study_type"], "q": body["qcode"], "qt": found[0]["qtext"], "il": str(body.get("item_label") or "")[:255],
             "oc": body.get("option_code"), "al": str(body.get("answer_label") or "")[:500], "d": dim,
             "v": str(body.get("dim_value") or "Total")[:120], "ag": against, "by": _person(body),
             "email": email_of(request) if body.get("email_me", True) else None, "o": email_of(request),
             "s": int(body["survey_id"])}).lastrowid
    return {"alert_id": alert_id}


@router.delete("/alerts/{alert_id}", status_code=204)
def drop_alert(alert_id: int, request: Request) -> None:
    with get_engine("app").begin() as conn:
        owned(conn, "SELECT owner_email FROM cip_metric_alert WHERE alert_id = :k", alert_id, request)
        conn.execute(text("DELETE FROM cip_metric_alert WHERE alert_id = :a"), {"a": alert_id})


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
def audiences() -> list[dict]:
    out = _rows("SELECT audience_id, name, definition, created_by, created_at FROM cip_audience ORDER BY name")
    return [{**a, "definition": json.loads(a["definition"])} for a in out]


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
    body = await request.json()
    definition, name = _definition(body.get("definition") or {}), " ".join(str(body.get("name") or "").split())[:200]
    if not name:
        raise HTTPException(422, "Name the audience")
    with get_engine("app").begin() as conn:
        audience_id = conn.execute(text("INSERT INTO cip_audience (name, definition, created_by, owner_email) VALUES (:n, :d, :by, :o)"),
                                   {"n": name, "d": json.dumps(definition), "by": _person(body), "o": email_of(request)}).lastrowid
    return {"audience_id": audience_id}


@router.delete("/audiences/{audience_id}", status_code=204)
def drop_audience(audience_id: int, request: Request) -> None:
    with get_engine("app").begin() as conn:
        owned(conn, "SELECT owner_email FROM cip_audience WHERE audience_id = :k", audience_id, request)
        conn.execute(text("DELETE FROM cip_audience WHERE audience_id = :a"), {"a": audience_id})


@router.post("/waves/{survey_id}/audience")
async def audience_view(survey_id: int, request: Request) -> dict:
    body = await request.json()
    return audience(survey_id, str(body.get("qcode") or ""), _definition(body.get("definition") or {}))


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
    rest_pct, rest_base, sig (+1 higher, -1 lower, 0)], counted from the wave's respondent bitsets (payloads.people).
    An answer condition counts only where this wave asked the same question; a group under HIDDEN_BASE (5) shows no figures."""
    wave = _people(survey_id, os.path.realpath(PUBLISH_ROOT / "current"))
    question = wave["questions"].get(qcode)
    if not question:
        raise HTTPException(404, "That question is not in that wave")
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
    mine = {key: (b & group).bit_count() for key, b in question["bits"].items()}
    everyone = {key: b.bit_count() for key, b in question["bits"].items()}
    labels = [dict(zip(("item_id", "option_id", "item_label", "option_code", "option_label"), r)) for r in question["rows"]]
    multi = all(r["option_id"] == 0 for r in labels)

    def base(counts, item):   # multi: answered the question (its base rows); single: answered this row
        return counts.get((0, 0), 0) if multi else sum(n for (i, o), n in counts.items() if i == item and o)
    rows = []
    for r in labels:
        key = (r["item_id"], r["option_id"])
        b, b_all = base(mine, r["item_id"]), base(everyone, r["item_id"])
        n, n_all = mine.get(key, 0), everyone.get(key, 0)
        rest_b, rest_n = b_all - b, n_all - n
        label = r["item_label"] if multi else (f"{r['item_label']} · {r['option_label']}" if r["item_label"] else r["option_label"])
        # ponytail: complementary suppression only. Two audiences that differ by under 5 people can still be
        # subtracted; the fix is rounding the counts, if this is ever shown outside the team.
        if b < HIDDEN_BASE or 0 < rest_b < HIDDEN_BASE:   # the total is public, so a small rest gives the audience away
            rows.append([label, None, None if b < HIDDEN_BASE else b, None, None, None if rest_b < HIDDEN_BASE else rest_b, 0])
            continue
        pct, rest = 100 * n / b, (100 * rest_n / rest_b if rest_b else None)
        sig = 0
        if rest is not None and significant(pct, b, rest, rest_b):
            sig = 1 if pct > rest else -1
        rows.append([label, n, b, round(pct, 1), None if rest is None else round(rest, 1), rest_b, sig])
    return {"survey_id": survey_id, "qcode": qcode, "multi": multi, "skipped": skipped,
            "columns": ["answer", "n", "base", "pct", "rest_pct", "rest_base", "sig"], "rows": rows}


# ── boards: tables pinned as they were, comments, one deck ────────────────
def data_version() -> str:
    return Path(os.path.realpath(PUBLISH_ROOT / "current")).name


@router.get("/boards")
def boards() -> list[dict]:
    return _rows("SELECT b.board_id, b.name, b.created_by, b.created_at, COUNT(i.item_id) AS items FROM cip_board b"
                 " LEFT JOIN cip_board_item i ON i.board_id = b.board_id GROUP BY b.board_id, b.name, b.created_by, b.created_at"
                 " ORDER BY b.created_at DESC LIMIT 500")


@router.post("/boards", status_code=201)
async def new_board(request: Request) -> dict:
    name = " ".join(str((await request.json()).get("name") or "").split())[:200]
    if not name:
        raise HTTPException(422, "A board needs a name")
    with get_engine("app").begin() as conn:
        return {"board_id": conn.execute(text("INSERT INTO cip_board (name, created_by) VALUES (:n, :by)"),
                                         {"n": name, "by": email_of(request)}).lastrowid}


def board(board_id: int) -> dict:
    found = _rows("SELECT board_id, name, created_by, created_at FROM cip_board WHERE board_id = :b", b=board_id)
    if not found:
        raise HTTPException(404, "No such board")
    items = _rows("SELECT item_id, title, url, spec, data_version, added_by, added_at FROM cip_board_item WHERE board_id = :b"
                  " ORDER BY item_id", b=board_id)
    comments: dict = {}
    for c in _rows("SELECT c.comment_id, c.item_id, c.author, c.body, c.created_at FROM cip_board_comment c"
                   " JOIN cip_board_item i ON i.item_id = c.item_id WHERE i.board_id = :b ORDER BY c.comment_id", b=board_id):
        comments.setdefault(c["item_id"], []).append(c)
    return {**found[0], "current_version": data_version(),
            "items": [{**i, "spec": json.loads(i["spec"]), "comments": comments.get(i["item_id"], [])} for i in items]}


@router.get("/boards/{board_id}")
def open_board(board_id: int) -> dict:
    return board(board_id)


@router.delete("/boards/{board_id}", status_code=204)
def drop_board(board_id: int, request: Request) -> None:
    with get_engine("app").begin() as conn:
        owned(conn, "SELECT created_by FROM cip_board WHERE board_id = :k", board_id, request)
        conn.execute(text("DELETE FROM cip_board WHERE board_id = :b"), {"b": board_id})


@router.post("/boards/{board_id}/items", status_code=201)
async def pin(board_id: int, request: Request) -> dict:
    """{title, url, spec}: spec is the table the screen exports (api/exports.check), kept as it is now."""
    from api.exports import check
    body = await request.json()
    url = str(body.get("url") or "")
    try:
        spec = check(body.get("spec") or {})
    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(422, str(exc))
    if not url.startswith("/w/") or len(url) > 1000:
        raise HTTPException(422, "An item needs its portal screen (/w/…)")
    with get_engine("app").begin() as conn:
        if not conn.execute(text("SELECT 1 FROM cip_board WHERE board_id = :b"), {"b": board_id}).scalar():
            raise HTTPException(404, "No such board")
        item_id = conn.execute(text(
            "INSERT INTO cip_board_item (board_id, title, url, spec, data_version, added_by) VALUES (:b, :t, :u, :s, :v, :by)"),
            {"b": board_id, "t": " ".join(str(body.get("title") or spec["name"]).split())[:300], "u": url,
             "s": json.dumps(spec, separators=(",", ":")), "v": data_version(), "by": email_of(request)}).lastrowid
    return {"item_id": item_id}


@router.delete("/boards/items/{item_id}", status_code=204)
def unpin(item_id: int, request: Request) -> None:
    with get_engine("app").begin() as conn:
        owned(conn, "SELECT added_by FROM cip_board_item WHERE item_id = :k", item_id, request)
        conn.execute(text("DELETE FROM cip_board_item WHERE item_id = :i"), {"i": item_id})


@router.post("/boards/items/{item_id}/comments", status_code=201)
async def comment(item_id: int, request: Request) -> dict:
    body = str((await request.json()).get("body") or "").strip()[:2000]
    if not body:
        raise HTTPException(422, "Write something")
    with get_engine("app").begin() as conn:
        if not conn.execute(text("SELECT 1 FROM cip_board_item WHERE item_id = :i"), {"i": item_id}).scalar():
            raise HTTPException(404, "No such item")
        return {"comment_id": conn.execute(text("INSERT INTO cip_board_comment (item_id, author, body) VALUES (:i, :a, :b)"),
                                           {"i": item_id, "a": email_of(request), "b": body}).lastrowid}


@router.delete("/boards/comments/{comment_id}", status_code=204)
def drop_comment(comment_id: int, request: Request) -> None:
    with get_engine("app").begin() as conn:
        owned(conn, "SELECT author FROM cip_board_comment WHERE comment_id = :k", comment_id, request)
        conn.execute(text("DELETE FROM cip_board_comment WHERE comment_id = :c"), {"c": comment_id})


@router.get("/boards/{board_id}/deck")
def deck(board_id: int):
    """The whole board as one branded PowerPoint: a cover, then each pinned table as it was pinned."""
    from fastapi import Response
    from api.exports import deck_pptx
    b = board(board_id)
    if not b["items"]:
        raise HTTPException(422, "Pin something to the board first")
    when = b["created_at"].strftime("%d %b %Y") if hasattr(b["created_at"], "strftime") else str(b["created_at"])[:10]
    body = deck_pptx(b["name"], f"By {b['created_by']} · {when}", [{**i["spec"], "notes": [*i["spec"]["notes"],
                     f"Pinned {str(i['added_at'])[:10]} by {i['added_by']} · data version {i['data_version']}"]} for i in b["items"]])
    name = "".join(c if c.isalnum() or c in "-_" else "-" for c in b["name"])[:60] or "board"
    return Response(body, media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    headers={"Content-Disposition": f'attachment; filename="{name}.pptx"'})
