"""Publish the portal's standard screens as static files, after the ETL has built the serving tables.

The data changes once a week, so the payloads every visitor asks for are written once, here, and served by nginx
straight from disk (deploy/nginx.conf, gzip_static): no Python and no database on the request path, so those
screens stay fast whatever the number of users. Only ad hoc requests (cross-tabs, trends, search) reach the API.

  <root>/.build-<version>/api/v1/waves.json(.gz)                    the survey picker
                          api/v1/waves/<id>/book.json(.gz)          every wave's questions × banner (one per wave)
                          api/v1/dashboards/<code>/<id>.json(.gz)   module dashboards (the business Databank tiles)
                          api/v1/trends/<family>/<study>/<qcode>/<dim>/<value>.json(.gz)
                                                                    every question of every multi-wave family × banner
                          manifest.json                             version, counts, source serving version
  <root>/current → .build-<version>                                 swapped atomically after the gates pass

The paths mirror the API's URLs and the bytes are the API's own (app/data/payloads.py), so nginx and the API
answer identically. A failed gate leaves the previous version live. The last KEEP versions stay for rollback:
`python -m etl.publish --rollback` points current at the one before.

    python -m etl.publish                    # build, check, swap (CIP_PUBLISH_DIR, default /srv/cip/published)
    python -m etl.publish --rollback
"""
from __future__ import annotations

import argparse
import gzip
import json
import logging
import os
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text

from app.core.database import get_engine
from app.data import payloads

log = logging.getLogger("cip.publish")
ROOT = Path(os.environ.get("CIP_PUBLISH_DIR", "/srv/cip/published"))
KEEP = 3


def write(path: Path, data) -> int:
    """data → path.json and path.json.gz (what nginx's gzip_static sends to browsers that accept gzip)."""
    body = data if isinstance(data, bytes) else payloads.encode(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.with_suffix(".json").write_bytes(body)
    path.with_suffix(".json.gz").write_bytes(gzip.compress(body, 9))
    return len(body)


def build(root: Path = ROOT, jobs: int = 4) -> Path:
    """Write every standard payload into a new version folder and check it. Returns the folder; raises if a gate fails."""
    version = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    out = root / f".build-{version}"
    out.mkdir(parents=True)
    start = time.perf_counter()
    with get_engine("app").connect() as conn:
        ids = [r[0] for r in conn.execute(text("SELECT survey_id FROM srv_wave ORDER BY survey_id"))]
        serving = [str(x) for x in conn.execute(text("SELECT COUNT(*), MAX(built_at) FROM srv_wave")).one()]
        boards = conn.execute(text(
            "SELECT p.dashboard_code, p.survey_id, d.payload_json FROM cip_dash_published p"
            " JOIN cip_dash_payload d ON d.build_id = p.build_id")).all()
    by_wave: dict = {}
    for code, survey_id, _ in boards:
        by_wave.setdefault(survey_id, []).append(code)
    size = write(out / "api/v1/waves", payloads.waves(by_wave))
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        size += sum(pool.map(lambda sid: write(out / f"api/v1/waves/{sid}/book", payloads.book(sid)), ids))
    for code, survey_id, body in boards:
        size += write(out / f"api/v1/dashboards/{code}/{survey_id}", body.encode())
    with get_engine("app").connect() as conn:   # trends: one query per question gives all its banner columns
        questions = conn.execute(text(
            "SELECT DISTINCT w.survey_family, w.study_type, r.qcode FROM srv_result r JOIN srv_wave w ON w.survey_id = r.survey_id"
            " WHERE r.dim = 'total' AND (w.survey_family, w.study_type) IN (SELECT survey_family, study_type FROM srv_wave"
            " GROUP BY survey_family, study_type HAVING COUNT(*) > 1)")).all()
    def trends(q) -> tuple[int, int]:
        family, study, qcode = q
        made = payloads.family_trends(family, study, qcode)
        return len(made), sum(write(out / "api/v1/trends" / family / study / qcode / dim / value, t) for (dim, value), t in made.items())
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        done = list(pool.map(trends, questions))
    trend_files = sum(n for n, _ in done)
    size += sum(b for _, b in done)
    manifest = {"version": version, "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "serving_version": serving, "waves": len(ids), "books": len(ids), "dashboards": len(boards), "trends": trend_files,
                "bytes": size, "seconds": round(time.perf_counter() - start, 1)}
    check(out, manifest, ids)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    log.info("Built %s: %d books, %d dashboards, %.1f MB in %.0f s", version, len(ids), len(boards), size / 2**20, manifest["seconds"])
    return out


def check(out: Path, manifest: dict, ids: list[int]) -> None:
    """Quality gates before anything goes live: every wave has a readable book with questions, the picker lists
    every wave, and no file is empty or corrupt."""
    problems = []
    picker = json.loads((out / "api/v1/waves.json").read_text())
    if len(picker) != len(ids):
        problems.append(f"picker lists {len(picker)} waves, serving has {len(ids)}")
    for sid in ids:
        path = out / f"api/v1/waves/{sid}/book.json"
        try:
            doc = json.loads(path.read_text())
            if doc["wave"]["survey_id"] != sid or not isinstance(doc["questions"], list):
                problems.append(f"book {sid}: wrong wave or no question list")
            gzip.decompress((path.with_suffix(".json.gz")).read_bytes())
        except Exception as exc:   # missing, unreadable or truncated
            problems.append(f"book {sid}: {exc}")
    if problems:
        shutil.rmtree(out, ignore_errors=True)
        raise RuntimeError(f"publish gates failed, previous version stays live: {problems[:5]}")


def swap(root: Path, target: Path) -> None:
    """Point current at target in one atomic rename (readers see the old version or the new one, never a mix)."""
    link = root / ".current-next"
    link.unlink(missing_ok=True)
    link.symlink_to(target.name)
    os.replace(link, root / "current")
    versions = sorted(p for p in root.glob(".build-*") if p.is_dir())
    for old in versions[:-KEEP]:
        shutil.rmtree(old, ignore_errors=True)


def publish(root: Path = ROOT, jobs: int = 4) -> Path:
    out = build(root, jobs)
    swap(root, out)
    log.info("Published %s", out.name)
    return out


def rollback(root: Path = ROOT) -> Path:
    live = (root / "current").resolve().name
    versions = sorted(p.name for p in root.glob(".build-*") if p.is_dir())
    older = [v for v in versions if v < live]
    if not older:
        raise RuntimeError("no earlier version to roll back to")
    swap(root, root / older[-1])
    return root / older[-1]


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s | %(message)s")
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument("--jobs", type=int, default=4)
    p.add_argument("--rollback", action="store_true")
    a = p.parse_args()
    print(rollback(a.root) if a.rollback else publish(a.root, a.jobs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
