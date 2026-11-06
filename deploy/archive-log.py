"""Packs a full log into a .zip that is kept for good, then empties the live file (called by deploy/etl-loop.sh when a
log passes 20 MB). Logs are never deleted: they are the record of what happened and when.

    python deploy/archive-log.py logs/nginx-access.log
      -> logs/archive/nginx-access-20261106-0910.zip   (the full file, about a tenth of its size)
      -> logs/nginx-access.log.1                       (a plain copy of the last full file: the Logs page's dashboard
                                                        finishes counting its lines from it, api/metrics.py)
      -> logs/nginx-access.log                         emptied; nginx and the API keep writing to the same open file

.zip because every laptop and phone opens it with no extra app (Windows, macOS, iPhone, Android).
The admins download the archives from the Logs page (api/logs.py archives)."""
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

log = Path(sys.argv[1])
archive = log.parent / "archive"
archive.mkdir(exist_ok=True)
stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
copy = log.with_name(log.name + ".1")
shutil.copyfile(log, copy)                      # first a whole copy, so nothing written meanwhile is lost to the zip
log.open("w").close()                           # then empty the live file (the writers keep their open handle)
target = archive / f"{log.stem}-{stamp}.zip"
with zipfile.ZipFile(target.with_suffix(".zip.part"), "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    z.write(copy, arcname=f"{log.stem}-{stamp}{log.suffix}")
target.with_suffix(".zip.part").replace(target)  # whole archives only: a stopped container never leaves half a zip
print(f"archive-log: {log} -> {target} ({copy.stat().st_size // 1024} KB -> {target.stat().st_size // 1024} KB)")
