"""Watches the analysts' China Consumer Survey folder on SharePoint and loads every new or replaced week by itself.

The analysts keep one folder per survey week, inside year and month folders ("2026/October/Survey of Oct 26"), each
holding Baidu's raw export (.csv) and its crosstab (.xls). Every 10 minutes (deploy/etl-loop.sh) this walks the folder
through Microsoft Graph, finds each week folder with both files, and loads any pair it has not loaded in that exact
version (a replaced file has a new eTag) through etl/baidu_qss_export.py load: the same checks as the Upload survey
page, so a pair whose counts differ from the crosstab is refused, written nowhere, and reported once (etl/notify.py).
After a load the published files are rebuilt (etl/publish.py). The folder name sets the wave ("Survey of Oct 26" is
2026-10-26); without one, the analysts' rule in baidu_qss_export.survey_week does.

Access (IT, docs/CHINA_SURVEY_PIPELINE.md): an Entra app with Microsoft Graph Sites.Selected (application) and read on
the one site. Settings, in the App Service: CIP_SP_TENANT_ID, CIP_SP_CLIENT_ID, CIP_SP_CLIENT_SECRET,
CIP_CHINA_SITE ("coresightresearch.sharepoint.com:/sites/CoreSightResearch") and CIP_CHINA_FOLDER (the folder's path in
the site's document library). Without them it does nothing.

    python -m etl.sharepoint_china          # one pass (what the scheduler runs)
    python -m etl.sharepoint_china --list   # what it sees and would load; loads nothing
"""
from __future__ import annotations

import argparse
import logging
import os
import re
from datetime import date, datetime
from pathlib import Path
from typing import Optional
from urllib.parse import quote

import requests
from sqlalchemy import text

from etl import baidu_qss_export, notify
from etl.loaders import Locked, finish_run, start_run
from shared.core.database import get_engine

log = logging.getLogger("cip.sharepoint")
GRAPH = "https://graph.microsoft.com/v1.0"
UPLOAD_DIR = Path(os.environ.get("CIP_UPLOAD_DIR") or Path(__file__).resolve().parents[1] / "data/uploads")
WEEK = re.compile(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2})", re.I)   # "Survey of Oct 26"


def settings() -> Optional[dict]:
    """The five App Service settings, or None while IT has not granted access."""
    names = ("CIP_SP_TENANT_ID", "CIP_SP_CLIENT_ID", "CIP_SP_CLIENT_SECRET", "CIP_CHINA_SITE", "CIP_CHINA_FOLDER")
    found = {name: os.environ.get(name, "").strip() for name in names}
    return found if all(found.values()) else None


def sign_in(found: dict) -> requests.Session:
    """A Graph session as the app itself (client credentials): no person's account, only what Sites.Selected grants."""
    answer = requests.post(f"https://login.microsoftonline.com/{found['CIP_SP_TENANT_ID']}/oauth2/v2.0/token", timeout=30,
                           data={"client_id": found["CIP_SP_CLIENT_ID"], "client_secret": found["CIP_SP_CLIENT_SECRET"],
                                 "scope": "https://graph.microsoft.com/.default", "grant_type": "client_credentials"})
    answer.raise_for_status()
    session = requests.Session()
    session.headers["Authorization"] = f"Bearer {answer.json()['access_token']}"
    return session


def get(session, url: str) -> dict:
    """One Graph read (a path, or a full nextLink), as JSON; any error status raises."""
    answer = session.get(url if url.startswith("https://") else GRAPH + url, timeout=60)
    answer.raise_for_status()
    return answer.json()


def children(session, drive: str, item: str) -> list[dict]:
    """A folder's files and folders, every page."""
    found, url = [], f"/drives/{drive}/items/{item}/children?$top=200&$select=id,name,eTag,folder,file,size"
    while url:
        page = get(session, url)
        found += page.get("value", [])
        url = page.get("@odata.nextLink")
    return found


def week_folders(session, drive: str, item: str, path: tuple = ()) -> list[tuple[tuple, list[dict]]]:
    """Every folder under the China folder that holds files, with its path of folder names. A year of weeks is ~60
    folders, one Graph call each per pass. ponytail: switch to /delta once the folder holds a few hundred folders."""
    inside = children(session, drive, item)
    files = [f for f in inside if "file" in f]
    found = [(path, files)] if files else []
    for folder in (f for f in inside if "folder" in f):
        found += week_folders(session, drive, folder["id"], path + (folder["name"],))
    return found


def pick_pair(files: list[dict]) -> tuple[Optional[dict], Optional[dict], str]:
    """(raw, crosstab, why not) from a week folder's files: the one .csv (or the one .xlsx that is not an "_EN"
    translation) and the one .xls. Anything else is left for a person to sort out."""
    named = lambda end: [f for f in files if f["name"].lower().endswith(end)]   # noqa: E731
    raws = named(".csv") or [f for f in named(".xlsx") if not f["name"].lower().endswith("_en.xlsx")]
    toplines = named(".xls")
    if len(raws) == 1 and len(toplines) == 1:
        return raws[0], toplines[0], ""
    return None, None, f"{len(raws)} raw files (.csv) and {len(toplines)} crosstabs (.xls); one of each is needed"


def folder_week(path: tuple) -> Optional[str]:
    """The wave from the folders' names: the week folder's "Oct 26" and the year folder's "2026"."""
    year = next((int(name) for name in path if re.fullmatch(r"20\d\d", name.strip())), None)
    found = WEEK.search(path[-1]) if path else None
    if not (year and found):
        return None
    return datetime.strptime(f"{found[1][:3].title()} {found[2]} {year}", "%b %d %Y").date().isoformat()


def seen(key: str) -> bool:
    """Has this exact pair (file ids and versions) been loaded, or refused by the check (a run with no survey)? A load
    that failed on the way (the database, say) is tried again next pass."""
    with get_engine("etl").connect() as conn:
        return conn.execute(text("SELECT 1 FROM cip_load_log WHERE source_ref = :k AND (status = 'success' OR survey_id IS NULL)"
                                 " LIMIT 1"), {"k": key[:500]}).first() is not None


def download(session, drive: str, item: dict, folder: Path) -> Path:
    """A file's bytes into `folder` under a name CIP makes; kept, like the Upload survey page's copies."""
    path = folder / f"{datetime.now():%Y%m%d-%H%M%S}-{item['id'][-8:]}{Path(item['name']).suffix.lower()}"
    answer = session.get(f"{GRAPH}/drives/{drive}/items/{item['id']}/content", timeout=120)
    answer.raise_for_status()
    path.write_bytes(answer.content)
    return path


def run(listing_only: bool = False) -> list[str]:
    """One pass over the folder. Returns what it did, one line per week folder that needed something."""
    found = settings()
    if not found:
        log.info("SharePoint watcher not set up (CIP_SP_* and CIP_CHINA_* settings missing): nothing to do")
        return []
    session = sign_in(found)
    root = get(session, f"/sites/{found['CIP_CHINA_SITE']}/drive/root:/{quote(found['CIP_CHINA_FOLDER'].strip('/'))}")
    drive = root["parentReference"]["driveId"]
    done = []
    for path, files in week_folders(session, drive, root["id"]):
        where = "/".join(path) or found["CIP_CHINA_FOLDER"]
        raw, crosstab, why = pick_pair(files)
        if not raw:
            if any(f["name"].lower().endswith((".csv", ".xls")) for f in files):
                done.append(f"{where}: skipped, {why}")
            continue
        key = f"sharepoint:{raw['id']}@{raw['eTag']}|{crosstab['id']}@{crosstab['eTag']}"
        if seen(key):
            continue
        wave = folder_week(path)
        if listing_only:
            done.append(f"{where}: would load {raw['name']} + {crosstab['name']} as {wave or 'the analysts rule'}")
            continue
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        raw_path, crosstab_path = download(session, drive, raw, UPLOAD_DIR), download(session, drive, crosstab, UPLOAD_DIR)
        try:
            result = baidu_qss_export.load(raw_path, crosstab_path, wave, source=key)
        except Locked:
            done.append(f"{where}: another CIP run holds the lock; next pass")
            break
        except ValueError as exc:   # the check refused it: nothing was loaded. Recorded, so it is reported once
            finish_run(start_run(None, "api", "data", key), 0, 0, error=str(exc)[:2000])
            notify.failure(f"China survey {where} not loaded", str(exc))
            done.append(f"{where}: refused: {str(exc)[:300]}")
            continue
        done.append(f"{where}: loaded week of {result['wave']}, {result['respondents']} respondents, "
                    f"{result['matched']} figures equal to the crosstab")
        notify.teams(f"China Consumer Survey, week of {date.fromisoformat(result['wave']):%d %b %Y}: "
                     f"{result['respondents']} respondents loaded from SharePoint")
    if any(": loaded week" in line for line in done):
        from etl import publish   # here: only a pass that loaded something rebuilds the published files
        try:
            publish.publish()
        except Locked:   # a scheduled run is publishing or loading; it, or the next load, publishes this week too
            done.append("publish: another CIP run holds the lock; the week opens now and is listed after its publish")
    return done


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s | %(message)s")
    parser = argparse.ArgumentParser(description="Load new China survey weeks from SharePoint")
    parser.add_argument("--list", action="store_true", help="show what would load; load nothing")
    args = parser.parse_args()
    try:
        for line in run(listing_only=args.list):
            log.info(line)
    except requests.HTTPError as exc:   # a revoked secret or a moved folder: say so once, try again next pass
        notify.failure("China survey SharePoint watcher cannot read the folder", str(exc)[:1000])
        log.error("SharePoint: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
