"""Forsta's own record of every survey and of the company, kept by CIP in its database and shown where it helps.

Why: the respondents of every loaded survey are in CIP's database, but how the fieldwork went, how the questionnaire
was built and when Forsta will delete a survey lived only in Forsta. Forsta deletes an archived survey a year after
archiving it (the 101 archived surveys of 7 Nov 2026 go between Feb and Nov 2027), and all of that with it.

What is kept (read-only GET calls only, etl/forsta_client.py; one row per survey and kind in cip_forsta_record,
sql/009_forsta_record.sql, Forsta's answer verbatim and gzip-compressed):
  per survey   SURVEY_READS: its record, hibernation, funnel, drop-outs by page, warnings, quota, splits, screen-out
               rules, cross-tab banners, launch checks, files, audit log, saved reports, archive check, data layouts,
               data sources, tasks, and survey.xml (the questionnaire's source)
  company      COMPANY_READS: the archive and deletion schedule, every survey's warnings, the full survey history,
               planned auto-closes and archives, deletion reports, retention, categories, cross-tab defaults, and
               Forsta's own list of its endpoints (meta: to spot new ones)
Not kept, on purpose (docs/FORSTA_API_REVIEW.md): API keys, translations, campaigns, MaxDiff/conjoint and video.

Who calls it:
  collect()  scripts/weekly_forsta.py run(), every run: the surveys it just loaded, the ones in the field, and a few
             older ones still missing a record (PER_RUN), plus the company records. About 18 GETs (6-8 s) a survey;
             a failure is logged and never stops the load.
  python -m etl.fieldwork   at each server start (deploy/etl-loop.sh, in the background): every survey still missing
             a record, then the published files refreshed, so a deploy never shows an empty Fieldwork screen.
  publish()  etl/publish.py write_views, from the table (no Forsta call):
             api/v1/admin/fieldwork.json.gz  the admins' Fieldwork screen (frontend/src/screens/Fieldwork.tsx)
             api/v1/waves/<id>/logic.json.gz each wave's question conditions and screen-out rules, from its
                                             survey.xml (the Survey preview, frontend/src/screens/Survey.tsx)
A hibernated survey is not woken (that changes Forsta and is a paid action): it is marked hibernated and skipped.
"""
from __future__ import annotations

import gzip
import json
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import inspect, text

from shared.core.database import apply_sql, get_engine

log = logging.getLogger("cip.fieldwork")
TABLE = Path(__file__).resolve().parents[1] / "sql" / "009_forsta_record.sql"
PER_RUN = 10   # older surveys backfilled per run: ~70 s of Forsta calls, so a daily run stays short

# kind: the read-only endpoint for one survey ({path} is its Forsta path)
SURVEY_READS = {
    "survey": "rh/surveys/{path}", "completions": "surveys/{path}/summary/completions",
    "dropouts": "surveys/{path}/summary/dropouts", "warnings": "surveys/{path}/warnings", "quota": "surveys/{path}/quota",
    "splits": "surveys/{path}/summary/splits", "terms": "surveys/{path}/terms", "banners": "surveys/{path}/crosstabs/configuration",
    "launch_warnings": "surveys/{path}/state/live/warnings", "files": "surveys/{path}/files", "audit_log": "rh/surveys/{path}/audit-log",
    "saved_reports": "surveys/{path}/crosstabs/saved", "can_archive": "surveys/{path}/can-archive", "layouts": "surveys/{path}/layouts",
    "datasources": "surveys/{path}/datasources", "tasks": "surveys/{path}/tasks",
}
# kind: the read-only endpoint for the company ({company} is its id; Coresight's is 86)
COMPANY_READS = {
    "archived": "rh/surveys/archived", "warnings_summary": "rh/warnings/summary", "historical": "rh/surveys/historical",
    "autoclose_planned": "autoclose/planned", "archives_planned": "archives/planned", "categories": "rh/surveys/categories",
    "meta": "meta", "retention": "rh/companies/{company}/retention", "archives_scheduled": "archives/{company}/scheduled",
    "archives_deleted": "archives/{company}/deleted", "archives_deletion": "archives/{company}/deletion",
    "archives_deletion_data": "archives/{company}/deletion/data", "crosstab_defaults": "rh/companies/{company}/crosstab-report-defaults",
}
QUESTION_TAGS = {"radio", "checkbox", "select", "text", "textarea", "number", "float", "autosum", "autofill"}


def ensure_table() -> None:
    """Create cip_forsta_record the first time (sql/009_forsta_record.sql), so a server needs no manual step."""
    engine = get_engine("etl")
    if "cip_forsta_record" not in inspect(engine).get_table_names():
        apply_sql(TABLE, engine)


def store(path: str, kinds: dict) -> None:
    """Keep one survey's (or, with path '', the company's) answers, replacing the last ones of the same kinds."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    rows = [{"p": path, "k": kind, "t": now, "b": gzip.compress(data if isinstance(data, bytes) else json.dumps(data).encode(), 6)}
            for kind, data in kinds.items()]
    with get_engine("etl").begin() as conn:
        conn.execute(text("REPLACE INTO cip_forsta_record (forsta_path, kind, fetched_at, payload) VALUES (:p, :k, :t, :b)"), rows)


def records() -> dict[str, dict]:
    """Every kept answer, as {forsta path ('' for the company): {kind: data, 'fetched_at': when}}."""
    found: dict[str, dict] = {}
    with get_engine("app").connect() as conn:
        for path, kind, fetched, payload in conn.execute(text("SELECT forsta_path, kind, fetched_at, payload FROM cip_forsta_record")):
            body = gzip.decompress(payload)
            found.setdefault(path, {"path": path})[kind] = body.decode("utf-8", "replace") if kind == "survey_xml" else json.loads(body)
            found[path]["fetched_at"] = max(str(fetched), found[path].get("fetched_at", ""))
    return found


def snapshot(client, path: str) -> dict:
    """Forsta's record of one survey: its survey record and hibernation state, and unless hibernated every
    SURVEY_READS answer and its survey.xml. An endpoint Forsta refuses for this survey is left out, the rest kept."""
    kinds = {"survey": client.read_json(SURVEY_READS["survey"].format(path=path)),
             "hibernation": client.read_json("hibernation/status", survey=path)}
    if kinds["hibernation"].get("status") == "hibernated":
        return kinds
    for kind, endpoint in SURVEY_READS.items():
        if kind not in kinds:
            try:
                kinds[kind] = client.read_json(endpoint.format(path=path))
            except Exception as exc:   # noqa: BLE001   e.g. 404 for an endpoint this survey does not use
                log.info("Fieldwork: %s of %s not read: %s", kind, path, str(exc)[:120])
    try:
        kinds["survey_xml"] = client.survey_file(path, "survey.xml")
    except Exception as exc:   # noqa: BLE001
        log.info("Fieldwork: survey.xml of %s not read: %s", path, str(exc)[:120])
    return kinds


def company_snapshot(client) -> dict:
    """The company-wide answers (COMPANY_READS), each company's under its id; one that fails is left out."""
    kinds = {}
    companies = [c["id"] for c in client.read_json("rh/companies")]
    for kind, endpoint in COMPANY_READS.items():
        try:
            kinds[kind] = ({c: client.read_json(endpoint.format(company=c)) for c in companies} if "{company}" in endpoint
                           else client.read_json(endpoint))
        except Exception as exc:   # noqa: BLE001   e.g. 403: our key may not read it
            log.info("Fieldwork: %s not read: %s", kind, str(exc)[:120])
    return kinds


def due(loaded: list[str], limit: int | None = PER_RUN) -> list[str]:
    """The surveys to read this run: those just loaded, those in the field (their funnel moves), and up to `limit`
    loaded ones with no record yet, newest first (None: all of them, the catch-up at start)."""
    with get_engine("etl").connect() as conn:
        rows = conn.execute(text(
            "SELECT f.forsta_path, f.state FROM cip_forsta_survey f JOIN cip_survey s ON s.source_ref = f.forsta_path"
            " WHERE s.platform = 'forsta' ORDER BY f.launched_at DESC")).all()
        kept = {p for (p,) in conn.execute(text("SELECT forsta_path FROM cip_forsta_record WHERE kind = 'survey'"))}
    live = [path for path, state in rows if state == "live"]
    missing = [path for path, _ in rows if path not in kept][:limit]
    return list(dict.fromkeys([*loaded, *live, *missing]))


def collect(client, loaded: list[str], limit: int | None = PER_RUN) -> list[str]:
    """Keep the company's records and those of the surveys due this run; returns the survey paths kept. Anything
    that fails is logged and left for the next run: this never stops the load."""
    try:
        ensure_table()
        store("", company_snapshot(client))
        paths = due(loaded, limit)
    except Exception as exc:   # noqa: BLE001   the database or Forsta out of reach: the surveys just loaded still count
        log.warning("Fieldwork: the company records or the register were not read: %s", exc)
        paths = loaded
    kept = []
    for path in paths:
        try:
            store(path, snapshot(client, path))
            kept.append(path)
        except Exception as exc:   # noqa: BLE001
            log.warning("Fieldwork record of %s not read: %s", path, exc)
    return kept


def logic(xml: str) -> dict:
    """The questionnaire's conditions from survey.xml: when each question is shown (its own condition and those of the
    blocks around it, joined with "and"), and the screen-out rules (terms) with their conditions."""
    questions, terms = {}, []

    def walk(node, around: list[str]) -> None:
        tag, own = node.tag.split("}")[-1], node.get("cond")
        conditions = around + ([own] if own and own != "1" else [])
        if tag in QUESTION_TAGS and node.get("label"):
            if conditions:
                questions[node.get("label")] = " and ".join(f"({c})" if len(conditions) > 1 else c for c in conditions)
            return                                     # a question's rows and columns carry their own conditions
        if tag == "term":
            terms.append([node.get("label"), " and ".join(conditions), (node.text or "").strip()])
            return
        for child in node:
            walk(child, conditions)
    walk(ET.fromstring(xml.encode("utf-8")), [])
    return {"questions": questions, "terms": terms}


def number(completions: dict, formula: str):
    """One funnel line of Forsta's completions summary (its rows are named by formula), or None."""
    row = next((r for r in completions.get("rows", []) if r.get("formula") == formula), None)
    return row["cells"][0].get("raw") if row and row.get("cells") else None


def summary(record: dict, wave: dict | None) -> dict:
    """One survey's line on the Fieldwork screen, its drop-out pages, its timeline and its Forsta details."""
    info, completions = record.get("survey") or {}, record.get("completions") or {}
    opened, qualified = number(completions, "clickthrough"), number(completions, "qualified")
    median = number(completions, "completionTimeMedian")
    # what happened to the survey, not who read it: Forsta also logs every API call and data view
    timeline = [[e.get("created_on"), e.get("user_email"), e.get("event")] for e in (record.get("audit_log") or {}).get("data", [])
                if e.get("event") and not e["event"].startswith(("API:", "View Responses", "Crosstabs: viewed", "Response summary:"))]
    terms = [[t.get("label"), t.get("description")] for t in record.get("terms") or []]
    pages = [[row.get("qlabel") or "", row.get("title") or "", split.get("started"), split.get("submitted"),
              split.get("dropped"), split.get("average_seconds")]
             for row in (record.get("dropouts") or {}).get("rows", []) for split in row.get("splits", [])[:1]
             if split.get("started")]
    saved = [[r.get("title"), datetime.fromtimestamp(r["updated_on"] / 1000, timezone.utc).date().isoformat() if r.get("updated_on") else None,
              r.get("access")] for r in record.get("saved_reports") or []]
    return {"path": record["path"], "survey_id": wave and wave["survey_id"], "title": info.get("title") or (wave or {}).get("title"),
            "wave_date": (wave or {}).get("wave_date"), "state": info.get("state"),
            "hibernated": (record.get("hibernation") or {}).get("status") == "hibernated",
            "launched": info.get("dateLaunched"), "closed": info.get("closedDate"), "questions": info.get("questions"),
            "opened": opened, "partial": number(completions, "partial"), "terminated": number(completions, "terminates"),
            "overquota": number(completions, "overquota"), "qualified": qualified,
            "incidence": round(100 * qualified / opened, 1) if opened and qualified is not None else None,
            "median_minutes": round(median / 60, 1) if median else None,
            "warnings": (record.get("warnings") or {}).get("counts") or {}, "pages": pages, "fetched_at": record.get("fetched_at"),
            "timeline": sorted(timeline), "terms": terms, "saved_reports": saved, "category": info.get("category"),
            "can_archive": (record.get("can_archive") or {}).get("message"), "tasks": len(record.get("tasks") or []),
            "layouts": len(record.get("layouts") or []), "datasources": len(record.get("datasources") or []),
            "conditions": len(logic(record["survey_xml"])["questions"]) if record.get("survey_xml") else None}


def publish(out: Path, write) -> int:
    """Called by etl/publish.py write_views: the admins' Fieldwork file and each wave's logic file, from the kept
    records and the published waves (to name each survey's wave). Returns the bytes written; nothing before the
    first collection (no table yet)."""
    engine = get_engine("app")
    if "cip_forsta_record" not in inspect(engine).get_table_names():
        return 0
    kept = records()
    company = kept.pop("", {})
    waves = {w.get("source_ref"): w for w in json.loads(gzip.decompress((out / "api/v1/waves.json.gz").read_bytes()))}
    size = 0
    for path, record in kept.items():   # the Survey preview's conditions, for every wave whose survey.xml is kept
        wave = waves.get(path)
        if wave and record.get("survey_xml"):
            try:
                size += write(out / "api/v1/waves" / str(wave["survey_id"]) / "logic", logic(record["survey_xml"]))
            except ET.ParseError as exc:
                log.warning("survey.xml of %s does not parse: %s", path, exc)
    surveys = sorted((summary(r, waves.get(p)) for p, r in kept.items()), key=lambda s: s.get("launched") or "", reverse=True)
    latest = {}   # Forsta lists a survey once per archiving: its latest one decides when it goes
    for a in sorted(company.get("archived") or [], key=lambda a: a.get("archived_at") or ""):
        latest[a.get("survey_path")] = a
    archive = sorted(({"path": path, "name": a.get("name"), "archived_at": a.get("archived_at"), "delete_at": a.get("delete_at"),
                       "held": path in waves} for path, a in latest.items()), key=lambda a: a["delete_at"] or "")
    with engine.connect() as conn:   # the register's titles and states, for the surveys Forsta has and CIP does not
        register = {p: (t, s) for p, t, s in conn.execute(text("SELECT forsta_path, title, state FROM cip_forsta_survey"))}
    not_loaded = [{"path": p, "title": register.get(p, (None, None))[0], "state": register.get(p, (None, None))[1]}
                  for p in company.get("historical") or [] if p not in waves]
    planned = [{"kind": kind, "items": items} for kind in ("autoclose_planned", "archives_planned")
               if (items := company.get(kind))]
    planned += [{"kind": kind, "items": items} for kind in ("archives_scheduled", "archives_deleted")
                for items in (company.get(kind) or {}).values() if items]
    return size + write(out / "api/v1/admin/fieldwork", {
        "surveys": surveys, "archive": archive, "retention": list((company.get("retention") or {}).values()),
        "not_loaded": not_loaded, "planned": planned, "collected": company.get("fetched_at")})


def catch_up() -> int:
    """Every survey still missing a record, and the company's, then the Fieldwork and logic files refreshed in the live
    version. Run at each server start (deploy/etl-loop.sh); returns the surveys kept."""
    from etl import publish as publishing   # here, not on top: etl/publish.py imports this module
    from etl.forsta_etl import open_forsta
    kept = collect(open_forsta(), [], limit=None)
    if (publishing.ROOT / "current").exists():
        size = publish(publishing.ROOT / "current", publishing.write)
        log.info("Fieldwork: %d surveys kept, %d bytes published", len(kept), size)
    return len(kept)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")
    catch_up()
