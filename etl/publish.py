"""Publish the portal's standard screens as static files, after the ETL has built the serving tables.

The data changes once a week, so the payloads every visitor asks for are written once, here, and served by nginx
straight from disk (by nginx, deploy/nginx.conf, or the API itself): no database on the request path, so those
screens stay fast whatever the number of users. Only search and not-yet-published waves are built live.

  <root>/.build-<version>/api/v1/waves.json.gz                      the survey picker
                          api/v1/waves/<id>/book.json.gz            every wave's questions × banner (one per wave)
                          api/v1/dashboards/<code>/<id>.json.gz     module dashboards (the business Databank tiles)
                          api/v1/questions/<family>/<study>/<qcode>.json.gz   (every wave and cut: Compare, Trends)
                                                                    every question of every multi-wave family × banner
                          api/v1/waves/<id>/cuts/<qcode>.json.gz    answers counted by every cut (any two-cut crosstab)
                          api/v1/waves/<id>/people.json.gz          respondent bitsets for Audiences (read by the API only)
                          manifest.json                             version, counts, each wave's built_at
  <root>/current → .build-<version>                                 swapped atomically after the gates pass

The paths mirror the API's URLs and the bytes are the API's own (app/data/payloads.py), so nginx and the API
answer identically. A failed gate leaves the previous version live. The last KEEP versions stay for rollback:
`python -m etl.publish --rollback` points current at the one before.

    python -m etl.publish                    # build, check, swap (CIP_PUBLISH_DIR, default data/published)
    python -m etl.publish --rollback
    python -m etl.publish --restore          # a lost disk: the last version back from Azure Blob storage

Durability: the server's disk (/srv/cip/published on the VM's managed disk) holds the live files; with
CIP_PUBLISH_BACKUP_URL set (an Azure Blob container URL with a SAS token: read, write, create) every publish
also uploads its version there as one tar (~40 MB) plus a `latest` pointer. Without either, `python -m etl.publish`
rebuilds everything from the database (~16 min).
"""
from __future__ import annotations

import argparse
import gzip
import json
import logging
import os
import shutil
import sys
import tarfile
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import bindparam, text

from app.core.database import get_engine
from app.data import payloads

log = logging.getLogger("cip.publish")
ROOT = Path(os.environ.get("CIP_PUBLISH_DIR") or Path(__file__).resolve().parents[1] / "data/published")
KEEP = 3
BACKUP = os.environ.get("CIP_PUBLISH_BACKUP_URL", "").strip()   # https://<account>.blob.core.windows.net/<container>?<sas>


def write(path: Path, data) -> int:
    """data → path.json.gz, the only copy kept: every browser accepts gzip (nginx adds the header; the API
    unzips for the rare client that does not). Returns the JSON size."""
    body = data if isinstance(data, bytes) else payloads.encode(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    target = path.with_name(path.name + ".json.gz")
    target.unlink(missing_ok=True)   # it may be a hard link to the live version's file: never write through it
    target.write_bytes(gzip.compress(body, 6))
    return len(body)


def build(root: Path = ROOT, jobs: int = 4) -> Path:
    """Write every standard payload into a new version folder and check it. A wave the ETL has not rebuilt since
    the live version (same srv_wave.built_at; loading a wave rebuilds the waves that compare against it too) is
    hard-linked from the live version, and so are the trends of a family with no rebuilt wave: no database work
    and no extra disk. Returns the folder; raises if a gate fails."""
    version = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    out = root / f".build-{version}"
    out.mkdir(parents=True)
    live = root / "current"
    try:
        before = json.loads((live / "manifest.json").read_text()).get("built", {})
    except (OSError, ValueError):   # first publish, or one from before incremental builds
        before = {}
    start = time.perf_counter()
    with get_engine("app").connect() as conn:
        waves = {str(sid): (str(at), family, study) for sid, at, family, study in conn.execute(text(
            "SELECT survey_id, built_at, survey_family, study_type FROM srv_wave ORDER BY survey_id"))}
        serving = [str(x) for x in conn.execute(text("SELECT COUNT(*), MAX(built_at) FROM srv_wave")).one()]
        boards = conn.execute(text(
            "SELECT p.dashboard_code, p.survey_id, d.payload_json FROM cip_dash_published p"
            " JOIN cip_dash_payload d ON d.build_id = p.build_id")).all()
    ids = [int(sid) for sid in waves]

    def reuse(rel: str) -> bool:
        if not (live / rel).is_dir():
            return False
        shutil.copytree(live / rel, out / rel, copy_function=os.link)
        return True

    fresh = [sid for sid in ids if before.get(str(sid)) != waves[str(sid)][0]
             or not (live / f"api/v1/waves/{sid}/people.json.gz").exists() or not reuse(f"api/v1/waves/{sid}")]
    by_wave: dict = {}
    for code, survey_id, _ in boards:
        by_wave.setdefault(survey_id, []).append(code)
    size = write(out / "api/v1/waves", payloads.waves(by_wave))

    def wave(sid: int) -> int:   # the book, and per question what any two-cut crosstab needs
        with get_engine("app").connect() as conn:
            cuts = payloads.question_cuts(conn, [sid])
            people = payloads.people(conn, sid)
        return write(out / f"api/v1/waves/{sid}/book", payloads.book(sid)) + write(out / f"api/v1/waves/{sid}/people", people) + sum(
            write(out / f"api/v1/waves/{sid}/cuts/{qcode}", part) for (_, qcode), part in cuts.items())
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        size += sum(pool.map(wave, fresh))
    for code, survey_id, body in boards:
        size += write(out / f"api/v1/dashboards/{code}/{survey_id}", body.encode())

    members: dict = {}
    for sid, (_, family, study) in waves.items():
        members.setdefault((family, study), []).append(int(sid))
    gone = bool(set(before) - set(waves))   # a wave removed: every trend of its family loses a point
    changed = {waves[str(sid)][1:] for sid in fresh}
    multi = [f for f, m in members.items() if len(m) > 1]
    full = [f for f in multi if gone or not reuse(f"api/v1/questions/{f[0]}/{f[1]}")]
    # a new or reloaded wave changes only the files of the questions it asked (a question file lists the waves that
    # asked it): the family's other files stay linked to the live version, so a 268-wave tracker rebuilds ~60 questions
    partial = [f for f in multi if f in changed and f not in full]
    redo = full + partial
    questions = []
    if redo:
        with get_engine("app").connect() as conn:   # one query per question gives every wave and every cut
            questions = conn.execute(text(
                "SELECT DISTINCT w.survey_family, w.study_type, r.qcode FROM srv_result r JOIN srv_wave w ON w.survey_id = r.survey_id"
                " WHERE r.dim = 'total' AND r.survey_id IN :ids").bindparams(bindparam("ids", expanding=True)),
                {"ids": [sid for f in full for sid in members[f]] + [sid for sid in fresh if waves[str(sid)][1:] in partial] or [-1]}).all()

    # a reloaded wave may have dropped a question: every linked file that lists a fresh wave is rebuilt too (and
    # removed when no wave asks it any more), so no file keeps a reloaded wave's old answers
    redone = {tuple(q) for q in questions}
    for family, study in partial:
        for path in (out / "api/v1/questions" / family / study).glob("*.json.gz"):
            listed = {w[0] for w in json.loads(gzip.decompress(path.read_bytes()))["waves"]}
            if listed & set(fresh):
                redone.add((family, study, path.name.removesuffix(".json.gz")))
    questions = sorted(redone)

    def question(q) -> int:   # Compare and Trends both read it
        family, study, qcode = q
        data, target = payloads.question(family, study, qcode), out / "api/v1/questions" / family / study / qcode
        if not data["waves"]:   # no wave asks it any more
            target.with_name(target.name + ".json.gz").unlink(missing_ok=True)
            return 0
        return write(target, data)
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        done = list(pool.map(question, questions))
    size += sum(done)
    manifest = {"version": version, "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "serving_version": serving, "waves": len(ids), "books": len(ids), "dashboards": len(boards),
                "rebuilt_waves": len(fresh), "rebuilt_families": len(redo), "questions_written": len(done),
                "bytes_written": size, "seconds": round(time.perf_counter() - start, 1),
                "built": {sid: at for sid, (at, _, _) in waves.items()}}
    check(out, manifest, ids)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    log.info("Built %s: %d of %d waves and %d families rebuilt, %.1f MB written in %.0f s",
             version, len(fresh), len(ids), len(redo), size / 2**20, manifest["seconds"])
    return out


def check(out: Path, manifest: dict, ids: list[int]) -> None:
    """Quality gates before anything goes live: every wave has a readable book with questions, the picker lists
    every wave, and no file is empty or corrupt."""
    problems = []
    read = lambda rel: json.loads(gzip.decompress((out / rel).read_bytes()))
    if len(read("api/v1/waves.json.gz")) != len(ids):
        problems.append(f"picker does not list the {len(ids)} waves serving has")
    for sid in ids:
        try:
            doc = read(f"api/v1/waves/{sid}/book.json.gz")
            if doc["wave"]["survey_id"] != sid or not isinstance(doc["questions"], list):
                problems.append(f"book {sid}: wrong wave or no question list")
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


def blob(name: str) -> str:
    container, _, sas = BACKUP.partition("?")
    return f"{container.rstrip('/')}/{name}?{sas}"


def backup(version: Path) -> None:
    """The version as one tar in Azure Blob storage, then `latest` pointing at it (block blob, one PUT each)."""
    import requests   # only backups use it; the API imports this module and its image has no requests

    with tempfile.TemporaryFile() as tar_file:
        with tarfile.open(fileobj=tar_file, mode="w") as tar:     # the payloads are gzip already
            tar.add(version, arcname=version.name)
        tar_file.seek(0)
        headers = {"x-ms-blob-type": "BlockBlob", "x-ms-version": "2021-08-06"}
        requests.put(blob(f"{version.name}.tar"), data=tar_file, headers=headers, timeout=600).raise_for_status()
    requests.put(blob("latest"), data=version.name.encode(), headers=headers, timeout=60).raise_for_status()
    log.info("Backed up %s to Azure Blob storage", version.name)


def restore(root: Path = ROOT) -> Path:
    import requests   # only backups use it; the API imports this module and its image has no requests
    if not BACKUP:
        raise RuntimeError("CIP_PUBLISH_BACKUP_URL is not set: rebuild with `python -m etl.publish` instead")
    name = requests.get(blob("latest"), timeout=60).text.strip()
    root.mkdir(parents=True, exist_ok=True)
    with requests.get(blob(f"{name}.tar"), stream=True, timeout=600) as r, tempfile.TemporaryFile() as tar_file:
        r.raise_for_status()
        shutil.copyfileobj(r.raw, tar_file)
        tar_file.seek(0)
        with tarfile.open(fileobj=tar_file) as tar:
            tar.extractall(root, filter="data")
    swap(root, root / name)
    return root / name


def publish(root: Path = ROOT, jobs: int = 4) -> Path:
    out = build(root, jobs)
    swap(root, out)
    log.info("Published %s", out.name)
    if BACKUP:
        try:
            backup(out)
        except Exception as exc:                   # the portal is live from disk either way; the next publish retries
            log.warning("Backup to Azure Blob storage failed: %s", str(exc).split("?")[0])
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
    p.add_argument("--restore", action="store_true")
    a = p.parse_args()
    print(rollback(a.root) if a.rollback else restore(a.root) if a.restore else publish(a.root, a.jobs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
