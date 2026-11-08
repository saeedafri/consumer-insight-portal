"""The Upload survey page's API (admins only): check a week of the China Consumer Survey, then load it.

Baidu QSS, which fields the China survey, has no API reachable from outside China, so an analyst downloads two files
from it each week (the raw export and Baidu's topline) and uploads both here.
  POST /api/v1/admin/survey/preview  both files read and every count checked against the topline; writes nothing
  POST /api/v1/admin/survey/publish  the same check, then the wave loaded (etl/baidu_qss_export.py load) and the
                                     published files rebuilt in the background (python -m etl.publish)

Called by: frontend/src/screens/Ingest.tsx (/app/ingest). Both are plain `def`, so FastAPI runs them in its thread
pool and the event loop keeps answering everyone else; a week's load takes seconds. The ETL is imported inside each
call, so the API's idle memory carries none of it.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import tempfile
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from api.signin import admin

log = logging.getLogger("cip.api.ingest")
router = APIRouter(prefix="/api/v1/admin/survey", tags=["admin"])
ROOT = Path(__file__).resolve().parents[1]
UPLOAD_DIR = Path(os.environ.get("CIP_UPLOAD_DIR") or ROOT / "data/uploads")   # every loaded week's two files, kept
MAX_BYTES = 10 * 1024 * 1024   # per file; api/main.py allows two in one request, nginx 20m (deploy/cip_locations.conf). A week is ~0.4 MB
RAW_TYPES, TOPLINE_TYPES = {".csv", ".xlsx"}, {".xls", ".xlsx"}


def save_upload(file: UploadFile, kinds: set[str], folder: Path, what: str) -> Path:
    """The upload written to `folder` under a name CIP makes, never the sender's (no ../ tricks)."""
    # a file downloaded from SharePoint can arrive as "Original 7.csv.aspx": the .aspx is the download page's, not the file's
    suffix = Path((file.filename or "").lower().removesuffix(".aspx")).suffix
    if suffix not in kinds:
        raise HTTPException(400, f"The {what} must be {' or '.join(sorted(kinds))}, not {suffix or 'a file without one'}")
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:8]}-{what}{suffix}"
    data = file.file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, f"The {what} is over {MAX_BYTES // 2**20} MB: is it Baidu's export?")
    path.write_bytes(data)
    return path


@router.post("/preview")
def preview_survey(raw: UploadFile = File(...), topline: UploadFile = File(...), _: dict = Depends(admin)) -> dict:
    """What the files would load and whether every count equals the topline. The copies are deleted afterwards."""
    from etl import baidu_qss_export
    with tempfile.TemporaryDirectory(prefix="cip-upload-") as folder:
        raw_path = save_upload(raw, RAW_TYPES, Path(folder), "raw")
        topline_path = save_upload(topline, TOPLINE_TYPES, Path(folder), "topline")
        try:
            return baidu_qss_export.preview(raw_path, topline_path)
        except Exception as exc:   # an unreadable upload is the file's fault, whatever the library raised
            log.warning("Survey upload not readable: %s", exc)
            raise HTTPException(422, f"Could not read the files: {exc}")


@router.post("/publish")
def publish_survey(raw: UploadFile = File(...), topline: UploadFile = File(...), wave: Optional[str] = Form(None),
                   who: dict = Depends(admin)) -> dict:
    """Load the week (the same week again replaces it), then rebuild the published files in the background."""
    from etl import baidu_qss_export
    from etl.loaders import Locked
    if wave:
        try:
            date.fromisoformat(wave)
        except ValueError:
            raise HTTPException(422, "The wave date must be YYYY-MM-DD")
    raw_path = save_upload(raw, RAW_TYPES, UPLOAD_DIR, "raw")
    topline_path = save_upload(topline, TOPLINE_TYPES, UPLOAD_DIR, "topline")
    try:
        result = baidu_qss_export.load(raw_path, topline_path, wave)
    except (Locked, ValueError) as exc:   # nothing was written, so the copies are not kept either
        raw_path.unlink(missing_ok=True)
        topline_path.unlink(missing_ok=True)
        if isinstance(exc, Locked):
            raise HTTPException(409, "Another CIP run (a scheduled load or a publish) is busy: try again in a few minutes")
        raise HTTPException(422, str(exc))   # problems found by the check, or not Baidu's files
    log.info("%s loaded China wave %s (survey %s) from %s and %s", who.get("email"), result["wave"],
             result["survey_id"], raw.filename, topline.filename)
    start_publish()
    return result


PUBLISH = """for try in 1 2 3 4 5 6; do nice -n 15 "$0" -m etl.publish && exit 0; sleep 300; done; exit 1"""


def start_publish() -> None:
    """Rebuild the published files (python -m etl.publish: only the new wave and its family's trends are built, the
    rest is linked from the live version) in its own low-priority process, so the API's memory and CPU stay with
    visitors. etl.publish takes the ETL lock itself, so it never runs alongside a scheduled run; when one holds the
    lock it is tried again every 5 minutes for half an hour (until then the API builds the new wave's pages itself)."""
    (ROOT / "logs").mkdir(exist_ok=True)
    with (ROOT / "logs/publish.log").open("ab") as out:
        subprocess.Popen(["sh", "-c", PUBLISH, sys.executable], cwd=ROOT, stdout=out, stderr=subprocess.STDOUT,
                         start_new_session=True)
