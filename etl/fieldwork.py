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
    return {node.get("label"): plain_text("".join(node.find("title").itertext()))
            for node in root.iter() if node.tag.split("}")[-1] in QUESTION_TAGS and node.get("label") and node.find("title") is not None}


def plain_text(label) -> str:
    """Text as people read it: Forsta's titles and answers can hold HTML as text (<span style=…>, &nbsp;)."""
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", str(label or ""))).split())


def check(forsta: dict | None, survey_id: int | None) -> dict | None:
    """Forsta's own cross-tab against CIP's figures, everyone qualified, cell by cell: for each question (each row of
    a grid) its base and how many gave each answer. Why: CIP recounts every answer from Forsta's raw data export, so an
    independent count by Forsta itself proves the load lost or doubled nobody. Forsta's internal tables (quota and
    routing variables CIP does not show) are listed as not compared, never hidden."""
    if not forsta or not survey_id:
        return None
    with get_engine("app").connect() as conn:
        rows = conn.execute(text(
            "SELECT r.qcode, r.qtype, i.item_code, r.item_label, r.option_code, r.option_label, r.n, r.base_n FROM srv_result r"
            " LEFT JOIN cip_item i ON i.item_id = r.item_id WHERE r.survey_id = :s AND r.dim = 'total'"), {"s": survey_id}).all()
        codes: dict[str, list] = {}   # each question's answer codes in the questionnaire's order, answers nobody gave too
        for qcode, code in conn.execute(text("SELECT q.qcode, o.value_code FROM cip_option o JOIN cip_question q ON q.question_id = o.question_id"
                                             " WHERE q.survey_id = :s ORDER BY q.qcode, o.sort_order"), {"s": survey_id}):
            codes.setdefault(qcode, []).append(code)
    cip: dict[str, dict] = {}   # Forsta's table name (q1$, AP8$r1) → {answer: people, "(base)": base}
    for qcode, qtype, item_code, item, code, option, people, base in rows:
        grid = qtype.startswith("grid")
        table = f"{qcode}${item_code[len(qcode):]}" if grid and item_code else f"{qcode}$"
        counts = cip.setdefault(table, {"(base)": base})
        counts[plain_text(option if grid or qtype == "single" else item).casefold()] = people
        if code is not None:
            counts[f"#{code}"] = people   # by answer code, for answers whose wording is blank or repeated (see below)
    tables, differs, cells, equal, skipped = 0, [], 0, 0, []
    for table, answers in forsta.items():
        if table not in cip:
            skipped.append(table.rstrip("$"))
            continue
        tables += 1
        mine = cip[table]
        labels = [plain_text(row[0]).casefold() for row in answers]
        for i, row in enumerate(answers):
            label = "(base)" if i == 0 or labels[i] == "count" else labels[i]   # Count: Forsta's "answering", the base again
            ours = mine.get(label)
            if label != "(base)" and (not label or labels.count(label) > 1):   # blank middle points of a scale, "This one" twice:
                order = codes.get(table.split("$")[0], [])                     # the i-th answer in the questionnaire's order
                ours = mine.get(f"#{order[i - 1]}", 0) if i - 1 < len(order) else None   # no CIP row: nobody gave it
            theirs = row[2]
            cells += 1
            if theirs == ours and ours is not None:
                equal += 1
            elif not (i and theirs == 0 and ours is None):   # an answer nobody gave: CIP keeps no row for it
                differs.append([table.rstrip("$"), "Base" if label == "(base)" else row[0], theirs, ours])
            else:
                equal += 1
    return {"tables": tables, "cells": cells, "equal": equal, "differs": differs, "not_compared": sorted(skipped),
            "cip_only": sorted(t.rstrip("$") for t in cip if t not in forsta)}


def exported() -> dict[str, dict[str, list[str]]]:
    """Which files Forsta exported for each saved report: {survey path: {report id: ["excel", "pdf", "pptx"]}}."""
    formats = {kind: file_format for file_format, kind in EXPORTS.items()}
    found: dict[str, dict[str, list[str]]] = {}
    with get_engine("app").connect() as conn:
        for path, kind in conn.execute(text("SELECT forsta_path, kind FROM cip_forsta_record WHERE kind LIKE 'saved_%:%'")):
            prefix, _, report_id = kind.partition(":")
            if prefix in formats:
                found.setdefault(path, {}).setdefault(report_id, []).append(formats[prefix])
    return found


def survey_page(record: dict, survey_id: int | None = None, files: dict | None = None) -> dict:
    """Everything the Forsta admin screens show for one survey (api/v1/admin/forsta/<key>): the team's banners, its
    saved reports run by Forsta (with the files Forsta exported, or Forsta's reason it could not), the funnel by
    sample source and device, warnings, launch checks, files, and Forsta's cross-tab checked against CIP."""
    banners = [{"title": b.get("title"), "segments": [[g.get("title"), g.get("cond")] for g in b.get("segments") or []]}
               for b in (record.get("banners") or {}).get("banners") or []]
    titles = question_titles(record.get("survey_xml"))
    runs = survey_part(record["path"], "saved_runs") or {}
    reports = []
    for report in record.get("saved_reports") or []:
        tables = runs.get(report.get("id")) or {}
        width = max((len(row) for rows in tables.values() for row in rows[:1]), default=1) // 2   # columns: a % and a count each
        banner = next((b for b in banners if len(b["segments"]) == width), None)
        errors = record.get("saved_errors") or {}
        reports.append({"id": report.get("id"), "title": report.get("title"), "description": report.get("description"),
                        "exports": sorted((files or {}).get(report.get("id"), [])), "error": errors.get(report.get("id")),
                        "export_errors": {file_format: errors[f"{report.get('id')}:{file_format}"] for file_format in EXPORTS if f"{report.get('id')}:{file_format}" in errors},
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
            "hibernated": (record.get("hibernation") or {}).get("status") == "hibernated",
            "check": check(survey_part(record["path"], "crosstab_check"), survey_id),
            "check_error": (record.get("saved_errors") or {}).get("crosstab")}


def company_part(company: dict, kind: str):
    """A company record Forsta keys by company id ({"86": …}): Coresight's part."""
    found = company.get(kind)
    return next(iter(found.values()), None) if isinstance(found, dict) else found


def publish_forsta(out: Path, write, kept: dict, company: dict, waves: dict, not_loaded: list) -> int:
    """The Forsta admin screens (frontend/src/screens/Forsta.tsx): api/v1/admin/forsta (the company's records and one
    line per survey) and api/v1/admin/forsta/<key> per survey (survey_page). Everything Forsta gave, grouped."""
    size, lines, files = 0, [], exported()
    for path, record in kept.items():
        page = survey_page(record, (waves.get(path) or {}).get("survey_id"), files.get(path))
        size += write(out / "api/v1/admin/forsta" / page_key(path), page)
        info = record.get("survey") or {}
        lines.append({"key": page_key(path), "path": path, "title": page["title"], "launched": info.get("dateLaunched"),
                      "state": info.get("state"), "hibernated": page["hibernated"], "survey_id": (waves.get(path) or {}).get("survey_id"),
                      "reports": len(page["reports"]), "banners": len(page["banners"]), "files": len(page["files"]),
                      "splits": list(page["splits"]), "launch_warnings": sum(len(v) for v in page["launch_warnings"].values()),
                      "warnings": page["warnings"]["counts"],
                      "check": page["check"] and {k: page["check"][k] for k in ("tables", "cells", "equal")} | {"differs": len(page["check"]["differs"])}})
    lines.sort(key=lambda line: line["launched"] or "", reverse=True)
    return size + write(out / "api/v1/admin/forsta", {
        "surveys": lines, "warnings_summary": company.get("warnings_summary") or [],
        "deletion": company_part(company, "archives_deletion") or [], "deletion_data": company_part(company, "archives_deletion_data") or [],
        "deleted": company_part(company, "archives_deleted") or [], "scheduled": company_part(company, "archives_scheduled") or [],
        "planned": {"autoclose": company.get("autoclose_planned") or [], "archives": company.get("archives_planned") or []},
        "retention": company_part(company, "retention"), "crosstab_defaults": company_part(company, "crosstab_defaults"), "categories": company.get("categories") or [],
        "endpoints": sorted([m.get("method"), m.get("endpoint"), m.get("title")] for m in company.get("meta") or [] if m.get("endpoint")),
        "not_loaded": not_loaded, "collected": company.get("fetched_at")})


def records() -> dict[str, dict]:
    """Every kept answer, as {forsta path ('' for the company): {kind: data, 'fetched_at': when}}, without the saved
    reports' tables and files (megabytes: survey_part() reads them one survey at a time)."""
    found: dict[str, dict] = {}
    with get_engine("app").connect() as conn:
        for path, kind, fetched, payload in conn.execute(text(
                "SELECT forsta_path, kind, fetched_at, payload FROM cip_forsta_record"
                " WHERE kind NOT IN ('saved_runs', 'crosstab_check') AND kind NOT LIKE 'saved_%:%'")):   # only the files have a colon
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
        kinds["crosstab_check"] = None   # marks it read: nothing more can be read until Forsta wakes it
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
    kinds.update(computations(client, path, kinds))
    return kinds


EXPORTS = {"excel": "saved_export", "pdf": "saved_pdf", "pptx": "saved_pptx"}   # format: kind prefix (saved_export:<id> is the Excel)


def computations(client, path: str, kinds: dict) -> dict:
    """What Forsta computes for CIP, through the read-only POSTs only (etl/forsta_client.py read_post): its own
    cross-tab of every question for everyone qualified (crosstab_check, compared with CIP's figures in check()), and
    each of the team's saved reports run (saved_runs) and exported as Excel, PDF and PowerPoint (saved_export:<id>,
    saved_pdf:<id>, saved_pptx:<id>). A report Forsta cannot run keeps Forsta's reason (saved_errors), e.g. a report
    copied from another survey that asks about a question this one does not have. Then the proof that nothing
    changed: the survey's last edit and state are read again and must match; if not, an error for the admins."""
    found, runs, errors = {}, {}, {}
    try:
        found["crosstab_check"] = client.read_post(f"surveys/{path}/crosstabs/execute",
                                                   {"segments": [{"cond": "(ALL)", "title": "Total"}], "simplified": True}).json()
    except Exception as exc:   # noqa: BLE001
        errors["crosstab"] = str(exc)[-300:]
    for report in kinds.get("saved_reports") or []:
        report_id = report.get("id")
        try:
            runs[report_id] = client.read_post(f"surveys/{path}/crosstabs/saved/{report_id}/execute", {"simplified": True}).json()
        except Exception as exc:   # noqa: BLE001
            errors[report_id] = str(exc)[-300:]
            log.info("Fieldwork: saved report %s of %s not run: %s", report_id, path, errors[report_id])
            continue
        for file_format, kind in EXPORTS.items():
            try:
                found[f"{kind}:{report_id}"] = client.read_post(f"surveys/{path}/crosstabs/saved/{report_id}/export/{file_format}", {}).content
            except Exception as exc:   # noqa: BLE001   e.g. a report too wide for a PDF page (Forsta's layout error)
                errors[f"{report_id}:{file_format}"] = str(exc)[-300:]
    found["saved_runs"], found["saved_errors"] = runs, errors
    before, after = kinds["survey"], client.read_json(SURVEY_READS["survey"].format(path=path))
    if (after.get("lastEdit"), after.get("state")) != (before.get("lastEdit"), before.get("state")):
        log.error("Fieldwork: %s changed in Forsta while Forsta computed for CIP (last edit %s → %s)",
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
        kept = {p for (p,) in conn.execute(text("SELECT forsta_path FROM cip_forsta_record WHERE kind = 'crosstab_check'"))}   # the newest kind
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
        rule = term.get("cond") or cause.removeprefix("term:")
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
    for marker, counts in (quota.get("markers") or {}).items():
        sheet, _, cell = marker.strip("/").partition("/")
        cells.append([sheet, (defines.get(cell) or {}).get("description") or cell, counts.get("limit"), counts.get("complete"), counts.get("oq")])
    cells.sort(key=lambda row: (-(row[4] or 0), row[0]))
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
