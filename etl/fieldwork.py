"""Forsta's own record of every survey and of the company, kept by CIP in its database and shown where it helps.

Why: the respondents of every loaded survey are in CIP's database, but how the fieldwork went, how the questionnaire
was built and when Forsta will delete a survey lived only in Forsta. Forsta deletes an archived survey a year after
archiving it (the 101 archived surveys of 7 Nov 2026 go between Feb and Nov 2027), and all of that with it.

What is kept (read-only GET calls, and the three POSTs that only compute, etl/forsta_client.py READ_ONLY_POSTS;
one row per survey and kind in cip_forsta_record,
sql/009_forsta_record.sql, Forsta's answer verbatim and gzip-compressed):
  per survey   SURVEY_READS: its record, hibernation, funnel, drop-outs by page, warnings, quota, splits, screen-out
               rules, cross-tab banners, launch checks, files, audit log, saved reports, archive check, data layouts,
               data sources, tasks, survey.xml (the questionnaire's source), the funnel by each split (sample
               source, OS, browser, mobile device), and the team's saved reports: run by Forsta (saved_runs) and
               exported as Excel (saved_export:<id>), with the survey's last edit re-read to prove nothing changed
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
             api/v1/admin/fieldwork.json.gz  the admins' Fieldwork screens (frontend/src/screens/Fieldwork.tsx and
                                             FieldworkSurvey.tsx): everything
             api/v1/fieldwork.json.gz        the same surveys for the roles the super admin lets see Fieldwork (the
                                             "fieldwork" feature): no deletion schedule, no Forsta user emails
             api/v1/admin/forsta.json.gz     the Forsta admin screens (frontend/src/screens/Forsta.tsx): company
             api/v1/admin/forsta/<key>.json.gz   records, and per survey its reports, banners, splits, warnings, files
             api/v1/waves/<id>/logic.json.gz each wave's question conditions and screen-out rules, from its
                                             survey.xml (the Survey preview, frontend/src/screens/Survey.tsx)
A hibernated survey is not woken (that changes Forsta and is a paid action): it is marked hibernated and skipped.
"""
from __future__ import annotations

import gzip
import html
import json
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import bindparam, inspect, text

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


FUNNEL = ("clickthrough", "qualified", "terminates", "overquota", "partial", "inprogress")


def page_key(path: str) -> str:
    """A survey's name in the Forsta admin files' addresses: its Forsta path with dots (selfserve.58f.261003)."""
    return path.replace("/", ".")


def survey_part(path: str, kind: str):
    """One big kept answer of one survey (its saved reports' tables), read on its own to keep memory low."""
    with get_engine("app").connect() as conn:
        payload = conn.execute(text("SELECT payload FROM cip_forsta_record WHERE forsta_path = :p AND kind = :k"),
                               {"p": path, "k": kind}).scalar()
    return json.loads(gzip.decompress(payload)) if payload else None


def question_titles(xml: str | None) -> dict[str, str]:
    """Each question's label and wording from survey.xml, to title the saved reports' tables."""
    if not xml:
        return {}
    try:
        root = ET.fromstring(xml.encode("utf-8"))
    except ET.ParseError:
        return {}
    def plain(title) -> str:   # Forsta titles can hold HTML as text (<span style=…>, &nbsp;)
        return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", "".join(title.itertext()))).split())
    return {node.get("label"): plain(node.find("title"))
            for node in root.iter() if node.tag.split("}")[-1] in QUESTION_TAGS and node.get("label") and node.find("title") is not None}


def survey_page(record: dict) -> dict:
    """Everything the Forsta admin screens show for one survey (api/v1/admin/forsta/<key>): the team's banners, its
    saved reports run by Forsta, the funnel by sample source and device, warnings, launch checks and files."""
    banners = [{"title": b.get("title"), "segments": [[g.get("title"), g.get("cond")] for g in b.get("segments") or []]}
               for b in (record.get("banners") or {}).get("banners") or []]
    titles = question_titles(record.get("survey_xml"))
    runs = survey_part(record["path"], "saved_runs") or {}
    reports = []
    for report in record.get("saved_reports") or []:
        tables = runs.get(report.get("id")) or {}
        width = max((len(row) for rows in tables.values() for row in rows[:1]), default=1) // 2   # columns: a % and a count each
        banner = next((b for b in banners if len(b["segments"]) == width), None)
        reports.append({"id": report.get("id"), "title": report.get("title"), "description": report.get("description"),
                        "access": report.get("access"), "updated": report.get("updated_on"), "ran": bool(tables),
                        "columns": [g[0] for g in banner["segments"]] if banner else [f"Column {i + 1}" for i in range(width)],
                        "banner": banner and banner["title"],
                        "tables": [{"label": key.rstrip("$"), "title": titles.get(key.rstrip("$")), "rows": rows} for key, rows in tables.items()]})
    splits = {}
    for name, answer in (record.get("split_completions") or {}).items():
        rows = {r.get("formula"): [c.get("raw") for c in r.get("cells") or []] for r in (answer or {}).get("rows", [])}
        splits[name] = {"segments": (answer or {}).get("segments") or [], "rows": {f: rows[f] for f in FUNNEL if f in rows}}
    warnings = record.get("warnings") or {}
    return {"path": record["path"], "title": (record.get("survey") or {}).get("title"), "banners": banners, "reports": reports,
            "splits": splits, "files": record.get("files") or [],
            "launch_warnings": {k: v for k, v in (record.get("launch_warnings") or {}).items() if v},
            "warnings": {"counts": warnings.get("counts") or {},
                         "events": [[e.get("timestamp"), e.get("type"), (e.get("details") or {}).get("reason"), (e.get("details") or {}).get("message")]
                                    for e in warnings.get("events") or []]},
            "hibernated": (record.get("hibernation") or {}).get("status") == "hibernated"}


def ours(company: dict, kind: str):
    """A company record Forsta keys by company id ({"86": …}): Coresight's part."""
    found = company.get(kind)
    return next(iter(found.values()), None) if isinstance(found, dict) else found


def publish_forsta(out: Path, write, kept: dict, company: dict, waves: dict, not_loaded: list) -> int:
    """The Forsta admin screens (frontend/src/screens/Forsta.tsx): api/v1/admin/forsta (the company's records and one
    line per survey) and api/v1/admin/forsta/<key> per survey (survey_page). Everything Forsta gave, grouped."""
    size, lines = 0, []
    for path, record in kept.items():
        page = survey_page(record)
        size += write(out / "api/v1/admin/forsta" / page_key(path), page)
        info = record.get("survey") or {}
        lines.append({"key": page_key(path), "path": path, "title": page["title"], "launched": info.get("dateLaunched"),
                      "state": info.get("state"), "hibernated": page["hibernated"], "survey_id": (waves.get(path) or {}).get("survey_id"),
                      "reports": len(page["reports"]), "banners": len(page["banners"]), "files": len(page["files"]),
                      "splits": list(page["splits"]), "launch_warnings": sum(len(v) for v in page["launch_warnings"].values()),
                      "warnings": page["warnings"]["counts"]})
    lines.sort(key=lambda line: line["launched"] or "", reverse=True)
    return size + write(out / "api/v1/admin/forsta", {
        "surveys": lines, "warnings_summary": company.get("warnings_summary") or [],
        "deletion": ours(company, "archives_deletion") or [], "deletion_data": ours(company, "archives_deletion_data") or [],
        "deleted": ours(company, "archives_deleted") or [], "scheduled": ours(company, "archives_scheduled") or [],
        "planned": {"autoclose": company.get("autoclose_planned") or [], "archives": company.get("archives_planned") or []},
        "retention": ours(company, "retention"), "crosstab_defaults": ours(company, "crosstab_defaults"), "categories": company.get("categories") or [],
        "endpoints": sorted([m.get("method"), m.get("endpoint"), m.get("title")] for m in company.get("meta") or [] if m.get("endpoint")),
        "not_loaded": not_loaded, "collected": company.get("fetched_at")})


def records() -> dict[str, dict]:
    """Every kept answer, as {forsta path ('' for the company): {kind: data, 'fetched_at': when}}, without the saved
    reports' tables and files (megabytes: survey_part() reads them one survey at a time)."""
    found: dict[str, dict] = {}
    with get_engine("app").connect() as conn:
        for path, kind, fetched, payload in conn.execute(text(
                "SELECT forsta_path, kind, fetched_at, payload FROM cip_forsta_record"
                " WHERE kind <> 'saved_runs' AND kind NOT LIKE 'saved_export:%'")):
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
        kinds["split_completions"] = None   # marks it read: nothing more can be read until Forsta wakes it
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
    kinds["split_completions"] = {}   # the funnel by sample source, operating system, browser and mobile device
    for name in [s.get("name") for s in kinds.get("splits") or [] if s.get("name") not in (None, "none")]:
        try:
            kinds["split_completions"][name] = client.read_json(f"surveys/{path}/summary/completions", split=name)
        except Exception as exc:   # noqa: BLE001
            log.info("Fieldwork: the %s split of %s not read: %s", name, path, str(exc)[:120])
    kinds.update(saved_reports(client, path, kinds))
    return kinds


def saved_reports(client, path: str, kinds: dict) -> dict:
    """The research team's saved Forsta reports, run by Forsta (their tables) and exported (the Excel file), through
    the read-only POSTs only (etl/forsta_client.py read_post). Then the proof that nothing changed: the survey's last
    edit is read again and must be the one read before; if it moved, it is logged as an error for the admins."""
    runs, found = {}, {}
    for report in kinds.get("saved_reports") or []:
        rid = report.get("id")
        try:
            runs[rid] = client.read_post(f"surveys/{path}/crosstabs/saved/{rid}/execute", {"simplified": True}).json()
            found[f"saved_export:{rid}"] = client.read_post(f"surveys/{path}/crosstabs/saved/{rid}/export/excel", {}).content
        except Exception as exc:   # noqa: BLE001
            log.info("Fieldwork: saved report %s of %s not run: %s", rid, path, str(exc)[:120])
    found["saved_runs"] = runs
    if runs:
        before, after = kinds["survey"], client.read_json(SURVEY_READS["survey"].format(path=path))
        if (after.get("lastEdit"), after.get("state")) != (before.get("lastEdit"), before.get("state")):
            log.error("Fieldwork: %s changed in Forsta while its saved reports were run (last edit %s → %s)",
                      path, before.get("lastEdit"), after.get("lastEdit"))
    return found


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
        kept = {p for (p,) in conn.execute(text("SELECT forsta_path FROM cip_forsta_record WHERE kind = 'split_completions'"))}   # the newest kind
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


def cause_label(cause: str, record: dict) -> tuple[str, str]:
    """A respondent's cause as people read it, and where in the survey it happened: a screen-out rule from the
    questionnaire's terms ("Speeder (te4): timeSpent() < 120"), or the full quota cell ("Regions: Northeast")."""
    if cause.startswith("term:"):
        term = next((t for t in record.get("terms") or [] if t.get("marker") == cause), {})
        rule = term.get("cond") or cause[5:]
        return (f"{term.get('description') or 'Screen-out rule'} ({term['label']}): {rule}" if term.get("label") else rule,
                "the whole interview (time taken)" if "timeSpent" in rule else "the screen-out rule's question")
    sheet, _, cell = cause.removeprefix("OQ ").strip("/").partition("/")
    defined = ((record.get("quota") or {}).get("defines") or {}).get(cell) or {}
    return f"{sheet}: {defined.get('description') or cell} was already full", f"the {sheet} question"


def reasons(survey_ids: list[int]) -> dict[int, dict]:
    """Per survey, from the respondents CIP loaded: how many were terminated or over quota for each cause Forsta wrote
    on their record (the screen-out rule, or the full quota cell), with their average minutes, and every finished
    interview hour by hour. Drop-outs are not loaded (Forsta's export leaves them out): their pages come from Forsta."""
    found: dict[int, dict] = {}
    if not survey_ids:
        return found
    with get_engine("app").connect() as conn:
        rows = conn.execute(text("SELECT survey_id, status_label, markers, interview_secs, completed_at FROM cip_respondent"
                                 " WHERE survey_id IN :ids").bindparams(bindparam("ids", expanding=True)), {"ids": survey_ids})
        for survey_id, status, markers, secs, done in rows:
            why = found.setdefault(survey_id, {"causes": {}, "hours": {}})
            if done:
                hour = why["hours"].setdefault(str(done)[:13], {"Qualified": 0, "Terminated": 0, "Overquota": 0})
                hour[status] = hour.get(status, 0) + 1
            if status in ("Terminated", "Overquota"):
                prefix = "term:" if status == "Terminated" else "OQ /"
                cause = next((m.strip() for m in (markers or "").split(",") if m.strip().startswith(prefix)), "")
                line = why["causes"].setdefault((status, cause), [0, 0, 0])   # people, seconds summed, people timed
                line[0] += 1
                if secs is not None:
                    line[1] += secs
                    line[2] += 1
    return found


def explain(why: dict | None, record: dict) -> tuple[list, list]:
    """The reasons table and the hour-by-hour timeline of one survey, from reasons()."""
    if not why:
        return [], []
    causes = sorted(([status, *(cause_label(cause, record) if cause else ("Not recorded by Forsta", "–")), people,
                      round(seconds / timed / 60, 1) if timed else None]
                     for (status, cause), (people, seconds, timed) in why["causes"].items()), key=lambda c: -c[3])
    hours = [[hour.replace(" ", "T") + ":00", n["Qualified"], n["Terminated"], n["Overquota"]] for hour, n in sorted(why["hours"].items())]
    return causes, hours


def summary(record: dict, wave: dict | None, why: dict | None = None) -> dict:
    """One survey's line on the Fieldwork screen, and its own page: drop-out pages, why people left, quota cells,
    timelines and Forsta details."""
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
    quota = record.get("quota") or {}
    defines = quota.get("defines") or {}
    cells = []   # [sheet, cell, limit, completes, turned away over quota], the busiest cells first
    for marker, c in (quota.get("markers") or {}).items():
        sheet, _, cell = marker.strip("/").partition("/")
        cells.append([sheet, (defines.get(cell) or {}).get("description") or cell, c.get("limit"), c.get("complete"), c.get("oq")])
    cells.sort(key=lambda c: (-(c[4] or 0), c[0]))
    causes, hours = explain(why, record)
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
            "conditions": len(logic(record["survey_xml"])["questions"]) if record.get("survey_xml") else None,
            "causes": causes, "hours": hours, "quota_cells": cells}


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
    why = reasons([waves[p]["survey_id"] for p in kept if p in waves])
    surveys = sorted((summary(r, waves.get(p), why.get((waves.get(p) or {}).get("survey_id"))) for p, r in kept.items()),
                     key=lambda s: s.get("launched") or "", reverse=True)
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
    size += write(out / "api/v1/admin/fieldwork", {
        "surveys": surveys, "archive": archive, "retention": list((company.get("retention") or {}).values()),
        "not_loaded": not_loaded, "planned": planned, "collected": company.get("fetched_at")})
    size += publish_forsta(out, write, kept, company, waves, not_loaded)
    shared = [{**s, "timeline": [[when, None, what] for when, _, what in s["timeline"]]} for s in surveys]   # no Forsta user emails
    return size + write(out / "api/v1/fieldwork", {"surveys": shared, "archive": [], "not_loaded": [], "planned": [],
                                                    "collected": company.get("fetched_at")})


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
