"""Forsta's fieldwork record of every survey, kept by CIP and published for the admins' Fieldwork screen.

Why: the respondents of every loaded survey are in CIP's database, but how the fieldwork went lived only in Forsta:
how many opened the survey, terminated, went over quota or dropped out (and on which page), how long the interview
took, and the warnings Forsta logged. Forsta deletes an archived survey a year after archiving it (the 101 archived
surveys of 7 Nov 2026 go between Feb and Nov 2027), and that record with it.

Who calls it:
  collect()  scripts/weekly_forsta.py run(), every run: the surveys it just loaded, the ones in the field, and a few
             older ones still missing a record (PER_RUN, so the backfill spreads over runs), plus Forsta's archive
             schedule. Read-only GETs (etl/forsta_client.py), about 2 s a survey. Forsta's answers are kept verbatim,
             one gzip file per survey under CIP_FIELDWORK_DIR (/home on the server: it survives deploys).
  publish()  etl/publish.py write_views: api/v1/admin/fieldwork.json.gz from those files (no Forsta, no database),
             served to admins only by /api/v1/admin/fieldwork (api/main.py). The screen: frontend/src/screens/Fieldwork.tsx.
A hibernated survey is not woken (that is a paid action in Forsta): it is marked hibernated and skipped.
"""
from __future__ import annotations

import gzip
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text

from shared.core.database import get_engine

log = logging.getLogger("cip.fieldwork")
ROOT = Path(os.environ.get("CIP_FIELDWORK_DIR") or Path(__file__).resolve().parents[1] / "data/fieldwork")
PER_RUN = 15   # older surveys backfilled per run: ~30 s of Forsta calls, so a daily run stays short


def file_of(path: str) -> Path:
    """Where one survey's record is kept: its Forsta path with the slashes as double underscores."""
    return ROOT / (path.strip("/").replace("/", "__") + ".json.gz")


def save(target: Path, data) -> None:
    """Write gzip JSON in one step (a reader never sees half a file)."""
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".part")
    partial.write_bytes(gzip.compress(json.dumps(data).encode(), 6))
    partial.replace(target)


def read(target: Path):
    """A kept file, or None when it is missing or unreadable."""
    try:
        return json.loads(gzip.decompress(target.read_bytes()))
    except (OSError, ValueError):
        return None


def snapshot(client, path: str) -> dict:
    """Forsta's fieldwork record of one survey, verbatim: its survey record, and unless hibernated the funnel, the
    page-by-page drop-outs and the warnings."""
    record = {"path": path, "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "survey": client.survey_info(path), "hibernated": client.hibernation(path) == "hibernated"}
    if not record["hibernated"]:
        record.update(completions=client.survey_completions(path), dropouts=client.survey_dropouts(path),
                      warnings=client.survey_warnings(path), quota=client.survey_quota(path), splits=client.survey_splits(path),
                      terms=client.survey_terms(path), banners=client.survey_banners(path),
                      launch_warnings=client.survey_launch_warnings(path), files=client.survey_files(path),
                      audit_log=client.survey_audit_log(path))
    return record


def due(loaded: list[str]) -> list[str]:
    """The surveys to fetch this run: those just loaded, those in the field (their funnel moves), and up to PER_RUN
    loaded ones with no record yet, newest first."""
    with get_engine("etl").connect() as conn:
        rows = conn.execute(text(
            "SELECT f.forsta_path, f.state FROM cip_forsta_survey f JOIN cip_survey s ON s.source_ref = f.forsta_path"
            " WHERE s.platform = 'forsta' ORDER BY f.launched_at DESC")).all()
    live = [path for path, state in rows if state == "live"]
    missing = [path for path, _ in rows if not file_of(path).exists()][:PER_RUN]
    return list(dict.fromkeys([*loaded, *live, *missing]))


def collect(client, loaded: list[str]) -> list[str]:
    """Keep the fieldwork record of the surveys due this run and Forsta's archive schedule; returns the paths kept.
    A survey that fails is logged and left for the next run: this never stops the load."""
    kept = []
    for name, read_it in (("archived", lambda: client.archived_surveys()), ("warnings", lambda: client.warnings_summary()),
                          ("retention", lambda: [client.retention(c["id"]) | {"company": c["id"]} for c in client.companies()])):
        try:   # the company-wide records: the archive schedule, every survey's warnings, the retention rules
            save(ROOT / f"{name}.json.gz", read_it())
        except Exception as exc:   # noqa: BLE001
            log.warning("Forsta %s not read: %s", name, exc)
    try:
        paths = due(loaded)
    except Exception as exc:   # noqa: BLE001   the database out of reach: the surveys just loaded still count
        log.warning("Fieldwork: the register was not read: %s", exc)
        paths = loaded
    for path in paths:
        try:
            save(file_of(path), snapshot(client, path))
            kept.append(path)
        except Exception as exc:   # noqa: BLE001
            log.warning("Fieldwork record of %s not read: %s", path, exc)
    return kept


def number(completions: dict, formula: str):
    """One funnel line of Forsta's completions summary (its rows are named by formula), or None."""
    row = next((r for r in completions.get("rows", []) if r.get("formula") == formula), None)
    return row["cells"][0].get("raw") if row and row.get("cells") else None


def summary(record: dict, wave: dict | None) -> dict:
    """One survey's line on the Fieldwork screen, and its pages for the drop-out funnel."""
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
    return {"path": record["path"], "survey_id": wave and wave["survey_id"], "title": info.get("title") or (wave or {}).get("title"),
            "wave_date": (wave or {}).get("wave_date"), "state": info.get("state"), "hibernated": record.get("hibernated", False),
            "launched": info.get("dateLaunched"), "closed": info.get("closedDate"), "questions": info.get("questions"),
            "opened": opened, "partial": number(completions, "partial"), "terminated": number(completions, "terminates"),
            "overquota": number(completions, "overquota"), "qualified": qualified,
            "incidence": round(100 * qualified / opened, 1) if opened and qualified is not None else None,
            "median_minutes": round(median / 60, 1) if median else None,
            "warnings": (record.get("warnings") or {}).get("counts") or {}, "pages": pages, "fetched_at": record.get("fetched_at"),
            "timeline": sorted(timeline), "terms": terms}


def publish(out: Path, write) -> int:
    """Called by etl/publish.py write_views: api/v1/admin/fieldwork.json.gz from the kept records and the published
    waves (to name each survey's wave). Returns the bytes written; nothing when no record is kept yet."""
    if not ROOT.is_dir():
        return 0
    waves = {w.get("source_ref"): w for w in json.loads(gzip.decompress((out / "api/v1/waves.json.gz").read_bytes()))}
    company = {"archived.json.gz", "warnings.json.gz", "retention.json.gz"}   # not a survey's record
    records = [read(f) for f in sorted(ROOT.glob("*.json.gz")) if f.name not in company]
    surveys = [summary(r, waves.get(r["path"])) for r in records if r and r.get("path")]
    surveys.sort(key=lambda s: s.get("launched") or "", reverse=True)
    latest = {}   # Forsta lists a survey once per archiving: its latest one decides when it goes
    for a in sorted(read(ROOT / "archived.json.gz") or [], key=lambda a: a.get("archived_at") or ""):
        latest[a.get("survey_path")] = a
    archive = sorted(({"path": path, "name": a.get("name"), "archived_at": a.get("archived_at"), "delete_at": a.get("delete_at"),
                       "held": path in waves} for path, a in latest.items()), key=lambda a: a["delete_at"] or "")
    return write(out / "api/v1/admin/fieldwork", {"surveys": surveys, "archive": archive, "retention": read(ROOT / "retention.json.gz") or []})
