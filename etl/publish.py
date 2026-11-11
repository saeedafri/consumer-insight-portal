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

The paths mirror the API's URLs and the bytes are the API's own (shared/data/payloads.py), so nginx and the API
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
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import text

from shared.core.database import get_engine
from shared.data import payloads
from etl import expectations, fieldwork, retailers, sectors, weekly_report

log = logging.getLogger("cip.publish")
ROOT = Path(os.environ.get("CIP_PUBLISH_DIR") or Path(__file__).resolve().parents[1] / "data/published")
POPULAR = 300   # after a deploy: the most-asked answers put back in nginx's cache (popular_urls)
WARM_WAVES = 1   # per weekly tracker (US, China): its newest wave, the one people open first (3 kept one core at 100 % for 97 s)
KEEP = 3
MAX_JOBS = 4     # app-role database reads per publish; shared MySQL must not get an unbounded pool
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


def worker_count(jobs: int | None = None) -> int:
    raw = jobs if jobs is not None else os.environ.get("CIP_PUBLISH_JOBS", "4")
    try:
        count = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("CIP publish jobs must be an integer from 1 to 4") from exc
    if not 1 <= count <= MAX_JOBS:
        raise ValueError("CIP publish jobs must be from 1 to 4")
    return count


def build(root: Path = ROOT, jobs: int | None = None) -> Path:
    """Write every standard payload into a new version folder and check it. A wave the ETL has not rebuilt since
    the live version (same srv_wave.built_at; loading a wave rebuilds the waves that compare against it too) is
    hard-linked from the live version, and so are the trends of a family with no rebuilt wave: no database work
    and no extra disk. Returns the folder; raises if a gate fails."""
    jobs = worker_count(jobs)
    version = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    out = root / f".build-{version}"
    out.mkdir(parents=True)
    try:
        return _build(out, version, root, jobs)
    except BaseException:   # a half-written version never stays: it would count toward KEEP and could be rolled back to
        shutil.rmtree(out, ignore_errors=True)
        raise


def _build(out: Path, version: str, root: Path, jobs: int) -> Path:
    live = root / "current"
    try:
        last = json.loads((live / "manifest.json").read_text())
    except (OSError, ValueError):   # first publish
        last = {}
    rules = {"hidden_base": payloads.HIDDEN_BASE, "test_base": payloads.TEST_BASE,
             "zero_cells": 1,   # 1: an asked group's unchosen answer is 0 %, not blank (24 Oct 2026); bump on any book rule
             "weighted": 1,     # books carry Census-weighted figures (etl/weighting.py, 24 Oct 2026)
             "open_ends": 1,    # books chart coded open-ended questions (etl/open_ends.py, 24 Oct 2026)
             "cut_inventory": 1}  # each wave's complete cuts directory is the question discovery catalogue
    rules_changed = last.get("rules", {"hidden_base": 30}) != rules   # a new small-cell rule: every file is rebuilt
    before = {} if rules_changed else last.get("built", {})
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

    effective_workers = min(jobs, len(fresh)) if fresh else 0

    def wave(sid: int) -> int:   # the book, and per question what any two-cut crosstab needs
        wave_start = time.perf_counter()
        cut_start = time.perf_counter()
        with get_engine("app").connect() as conn:
            cuts = payloads.question_cuts(conn, [sid])
        cut_seconds = time.perf_counter() - cut_start
        cut_groups = sum(len(part["counts"]) for part in cuts.values())
        written = sum(write(out / f"api/v1/waves/{sid}/cuts/{qcode}", part)
                      for (_, qcode), part in cuts.items())
        del cuts
        people_start = time.perf_counter()
        with get_engine("app").connect() as conn:
            people = payloads.people(conn, sid)
        people_seconds = time.perf_counter() - people_start
        written += write(out / f"api/v1/waves/{sid}/people", people)
        del people
        written += write(out / f"api/v1/waves/{sid}/book", payloads.book(sid))
        log.info(
            "publish version=%s wave=%s fingerprint=srv_answer_group_and_extract "
            "expected_srv_answer_reads=2 workers_configured=%d workers_effective=%d "
            "cut_groups=%d cut_read_build_seconds=%.3f people_read_build_seconds=%.3f wall_seconds=%.3f",
            version, sid, jobs, effective_workers, cut_groups, cut_seconds, people_seconds,
            time.perf_counter() - wave_start,
        )
        return written
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        size += sum(pool.map(wave, fresh))
    for code, survey_id, body in boards:
        size += write(out / f"api/v1/dashboards/{code}/{survey_id}", body.encode())

    members: dict = {}
    for sid, (_, family, study) in waves.items():
        members.setdefault((family, study), []).append(int(sid))
    gone = bool(set(before) - set(waves))   # a wave removed: every trend of its family loses a point
    changed = {waves[str(sid)][1:] for sid in fresh}
    # every family, one-wave ones too: Compare and Audience read the question file of any wave (frontend/src/screens),
    # and an unpublished one was built from the database on the click (1-5 s, holding a build slot others queued on)
    multi = list(members)
    full = [f for f in multi if gone or rules_changed or not reuse(f"api/v1/questions/{f[0]}/{f[1]}")]
    # a new or reloaded wave changes only the files of the questions it asked (a question file lists the waves that
    # asked it): the family's other files stay linked to the live version, so a 268-wave tracker rebuilds ~60 questions
    partial = [f for f in multi if f in changed and f not in full]
    redo = full + partial
    # Each cuts file is written from srv_result's total rows and is therefore
    # the complete, version-matched question catalogue. Enumerating those
    # already-written files avoids another DISTINCT join over serving tables.
    questions = set()
    for family, study in redo:
        wave_ids = members[(family, study)] if (family, study) in full else [
            sid for sid in fresh if waves[str(sid)][1:] == (family, study)
        ]
        for sid in wave_ids:
            for path in (out / f"api/v1/waves/{sid}/cuts").glob("*.json.gz"):
                questions.add((family, study, path.name.removesuffix(".json.gz")))

    # a reloaded wave may have dropped a question: every linked file that lists a fresh wave is rebuilt too (and
    # removed when no wave asks it any more), so no file keeps a reloaded wave's old answers
    redone = set(questions)
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
    size += write_views(out)
    manifest = {"version": version, "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "serving_version": serving, "waves": len(ids), "books": len(ids), "dashboards": len(boards),
                "rebuilt_waves": len(fresh), "rebuilt_families": len(redo), "questions_written": len(done),
                "bytes_written": size, "seconds": round(time.perf_counter() - start, 1), "jobs": jobs, "rules": rules,
                "built": {sid: at for sid, (at, _, _) in waves.items()}}
    check(out, manifest, ids)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    log.info("Built %s: %d of %d waves and %d families rebuilt, %.1f MB written in %.0f s",
             version, len(fresh), len(ids), len(redo), size / 2**20, manifest["seconds"])
    return out


def check(out: Path, manifest: dict, ids: list[int]) -> None:
    """Quality gates before anything goes live: every wave has a readable book with questions and readable respondent
    bitsets, the picker lists every wave, no wave lost more than a tenth of its questions against the live version
    (a broken load or harmonisation, not a real change), and no file is empty or corrupt."""
    problems = []
    read = lambda rel, root=out: json.loads(gzip.decompress((root / rel).read_bytes()))
    live = out.parent / "current"
    if len(read("api/v1/waves.json.gz")) != len(ids):
        problems.append(f"picker does not list the {len(ids)} waves serving has")
    for sid in ids:
        try:
            doc = read(f"api/v1/waves/{sid}/book.json.gz")
            if doc["wave"]["survey_id"] != sid or not isinstance(doc["questions"], list):
                problems.append(f"book {sid}: wrong wave or no question list")
            if not isinstance(read(f"api/v1/waves/{sid}/people.json.gz").get("questions"), dict):
                problems.append(f"people {sid}: no respondent bitsets")
        except Exception as exc:   # missing, unreadable or truncated
            problems.append(f"book {sid}: {exc}")
            continue
        try:
            before = len(read(f"api/v1/waves/{sid}/book.json.gz", live)["questions"])
        except (OSError, ValueError, KeyError):   # a new wave, or no live version yet
            continue
        if isinstance(doc["questions"], list) and before >= 10 and len(doc["questions"]) < 0.9 * before:   # a small wave may lose one
            problems.append(f"book {sid}: {len(doc['questions'])} questions, {before} in the live version")
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
    # nginx's cached answers need no emptying: their key holds the published version (deploy/cip_locations.conf,
    # $realpath_root), so the new version starts new keys at once; the old ones are never asked for again and nginx
    # drops them itself (deploy/nginx.conf proxy_cache_path: unused for 7 days, or past 512 MB)


def blob(name: str) -> str:
    container, _, sas = BACKUP.partition("?")
    return f"{container.rstrip('/')}/{name}?{sas}"


def backup(version: Path) -> None:
    """The version as one tar in Azure Blob storage, then `latest` pointing at it (block blob, one PUT each); or, when
    CIP_PUBLISH_BACKUP_URL is a folder (App Service's /home, kept across deploys), the tar there, the older ones removed."""
    if BACKUP.startswith("/"):
        keep = Path(BACKUP)
        keep.mkdir(parents=True, exist_ok=True)
        part = keep / f"{version.name}.tar.part"
        with tarfile.open(part, mode="w") as tar:   # the payloads are gzip already
            tar.add(version, arcname=version.name)
        part.replace(keep / f"{version.name}.tar")
        (keep / "latest.part").write_text(version.name)
        (keep / "latest.part").replace(keep / "latest")
        for old in keep.glob("*.tar"):
            if old.name != f"{version.name}.tar":
                old.unlink(missing_ok=True)
        log.info("Backed up %s to %s", version.name, keep)
        return
    import requests   # only backups use it; the API imports this module and its image has no requests

    with tempfile.TemporaryFile() as tar_file:
        with tarfile.open(fileobj=tar_file, mode="w") as tar:     # the payloads are gzip already
            tar.add(version, arcname=version.name)
        tar_file.seek(0)
        headers = {"x-ms-blob-type": "BlockBlob", "x-ms-version": "2021-08-06"}
        requests.put(blob(f"{version.name}.tar"), data=tar_file, headers=headers, timeout=600).raise_for_status()
    requests.put(blob("latest"), data=version.name.encode(), headers=headers, timeout=60).raise_for_status()
    log.info("Backed up %s to Azure Blob storage", version.name)


def write_views(out: Path) -> int:
    """The views built from a version's files (the weekly reports, the sector tables, expected vs actual, the
    fieldwork record): by every
    publish, and again after a restore, so a new image's views appear at deploy without waiting for new data.
    Returns the bytes written."""
    size = weekly_report.publish(out, write)   # the weekly report of the recent tracker waves, from the question files
    size += sectors.publish(out, write)        # the Databank's sector tables, from the books and question files
    size += retailers.publish(out, write)      # the retailer comparison, from the weeks' respondent bitsets
    size += fieldwork.publish(out, write)      # the admins' Fieldwork screen, from Forsta's kept fieldwork records
    size += write(out / "api/v1/public/facts", site_facts(out))   # the public home page's live figures
    return size + expectations.publish(out, write)   # retail events: expected vs actual, plus the spend answers


def site_facts(out: Path) -> dict:
    """What the public home page shows (frontend/app/(site)/LiveFacts.tsx fetches it; nginx serves it without sign-in):
    the catalogue's counts, the latest weekly wave (date, size, topics, questions) and every weekly wave's date for its
    calendar. Counts and dates only: no survey answer is public. The site is built without the data (deploy/Dockerfile),
    so without this file it would show the figures frozen in pipeline.ts."""
    waves = json.loads(gzip.decompress((out / "api/v1/waves.json.gz").read_bytes()))
    family = weekly_report.settings()["family"]   # the US weekly tracker; China's weekly waves are not its weeks
    trackers = sorted((w for w in waves if w.get("study_type") == "tracker" and w.get("survey_family") == family),
                      key=lambda w: w["wave_date"])
    if not trackers:
        return {}
    latest, when = trackers[-1], date.fromisoformat(trackers[-1]["wave_date"])
    book = out / "api/v1/waves" / str(latest["survey_id"]) / "book.json.gz"
    questions = len(json.loads(gzip.decompress(book.read_bytes())).get("questions") or []) if book.exists() else None
    return {"waves": len(waves), "responses": sum(w.get("qualified_n") or 0 for w in waves), "trackers": len(trackers),
            "annual": sum(w.get("study_type") == "annual" for w in waves), "adhoc": sum(w.get("study_type") == "adhoc" for w in waves),
            "latestDate": latest["wave_date"], "latestLabel": f"Week of {when:%B} {when.day}, {when.year}", "latestId": latest["survey_id"],
            "latestN": latest.get("qualified_n"), "latestTopics": latest.get("modules") or [], "questions": questions,
            "trackerDates": [w["wave_date"] for w in trackers], "firstTracker": trackers[0]["wave_date"]}


def restore_views(version: Path) -> None:
    """After a restore: the views rebuilt by this image's code (seconds). A failure (the database out of reach) keeps the
    restored version's own views; the next publish writes them anyway."""
    try:
        write_views(version)
    except Exception as exc:
        log.warning("Rebuilding the views of the restored version failed: %s", exc)


def restore(root: Path = ROOT) -> Path:
    import requests   # only backups use it; the API imports this module and its image has no requests
    if not BACKUP:
        raise RuntimeError("CIP_PUBLISH_BACKUP_URL is not set: rebuild with `python -m etl.publish` instead")
    root.mkdir(parents=True, exist_ok=True)
    if BACKUP.startswith("/"):
        name = (Path(BACKUP) / "latest").read_text().strip()
        with tarfile.open(Path(BACKUP) / f"{name}.tar") as tar:
            tar.extractall(root, filter="data")
        restore_views(root / name)
        swap(root, root / name)
        return root / name
    name = requests.get(blob("latest"), timeout=60).text.strip()
    with requests.get(blob(f"{name}.tar"), stream=True, timeout=600) as r, tempfile.TemporaryFile() as tar_file:
        r.raise_for_status()
        shutil.copyfileobj(r.raw, tar_file)
        tar_file.seek(0)
        with tarfile.open(fileobj=tar_file) as tar:
            tar.extractall(root, filter="data")
    restore_views(root / name)
    swap(root, root / name)
    return root / name


def behind(version: Path) -> bool:
    """Has the database gained or rebuilt a wave since this version was built? A backup taken before a load (the China
    weeks loaded on 11 Nov 2026 straight into the database) would otherwise be served after every deploy until the next
    scheduled load published, and the survey list would miss those waves."""
    manifest = json.loads((version / "manifest.json").read_text())
    with get_engine("app").connect() as conn:
        now = [str(x) for x in conn.execute(text("SELECT COUNT(*), MAX(built_at) FROM srv_wave")).one()]
    return manifest.get("serving_version") != now


def publish(root: Path = ROOT, jobs: int | None = None) -> Path:
    out = build(root, jobs)
    swap(root, out)
    log.info("Published %s", out.name)
    try:
        warm_nginx(out)
    except Exception as exc:                       # people still get every answer; the first asker waits a little
        log.warning("Warming the nginx cache failed: %s", exc)
    if BACKUP:
        try:
            backup(out)
        except Exception as exc:                   # the portal is live from disk either way; the next publish retries
            log.warning("Backup to Azure Blob storage failed: %s", str(exc).split("?")[0])
    return out


def warm_nginx(out: Path, waves: int = WARM_WAVES) -> int:
    """Ask nginx (CIP_NGINX_URL) for every this-week cross-tab of each weekly tracker's newest wave, as the screen asks for them (each
    question, both orders of every pair of cuts), so the first people to open a new wave find them already cached.
    One at a time, resting as long as each took: at most half the one core, people's requests always go first. Other
    weeks and waves are built on their first click (tens of ms) and cached from then on."""
    base = os.environ.get("CIP_NGINX_URL", "").rstrip("/")
    if not base:
        return 0
    from urllib.parse import quote
    from etl.serving import CUTS
    listed = sorted(json.loads(gzip.decompress((out / "api/v1/waves.json.gz").read_bytes())),
                    key=lambda w: (w["wave_date"], w["survey_id"]), reverse=True)
    # each weekly tracker's newest waves (CSI-US and CSI-CN), not only the newest of all: China's week is always older
    # than the US one and would otherwise be built on its first click
    trackers = [w for w in listed if w.get("study_type", "tracker") == "tracker"] or listed
    newest = [w for w in trackers if sum(o.get("survey_family") == w.get("survey_family") for o in
                                         trackers[:trackers.index(w) + 1]) <= waves]
    urls = [f"{base}/api/v1/waves/{w['survey_id']}/crosstab?q={quote(q['id'], safe='')}&by={a},{b}&weeks={weeks}"
            for w in newest for q in json.loads(gzip.decompress((out / f"api/v1/waves/{w['survey_id']}/book.json.gz").read_bytes()))["questions"]
            for a in CUTS for b in CUTS if a != b for weeks in (1,)]
    time.sleep(2)   # nginx looks at the swapped "current" once a second (open_file_cache_valid): warm the new version's keys
    return ask_nginx(urls, f"cross-tabs of {len(newest)} waves")


def popular_urls(limit: int = POPULAR) -> list[str]:
    """The cached answers people asked for most (cross-tabs, results, trends, search), from nginx's request log, which
    lives on /home and so survives a deploy (deploy/start.sh links logs/ there): what to put back in a new container's
    empty nginx cache. Only answers nginx caches (its log names a cache status) that came back 200."""
    logs = Path(os.environ.get("CIP_LOG_DIR") or ROOT.parent / "logs")
    asked: Counter = Counter()
    for name in ("nginx-access.log.1", "nginx-access.log"):   # the rotated copy first, then the current file
        path = logs / name
        if not path.exists():
            continue
        with path.open("rb") as f:
            for raw in f:
                try:
                    entry = json.loads(raw)
                except ValueError:
                    continue
                if (entry.get("method") == "GET" and entry.get("status") == 200 and entry.get("cache")
                        and str(entry.get("path", "")).startswith("/api/")):
                    asked[entry["path"]] += 1
    return [path for path, _ in asked.most_common(limit)]


def ask_nginx(urls: list[str], what: str) -> int:
    """Ask nginx (CIP_NGINX_URL) for each URL as a signed-in reader would, so its answer is cached. One at a time,
    resting as long as each took: at most half the core, people's requests always go first."""
    base = os.environ.get("CIP_NGINX_URL", "").rstrip("/")
    if not base or not urls:
        return 0
    from urllib.request import Request, urlopen
    from shared.core.session import issue
    # a full-length cookie: nginx sends a shorter one to the API instead of its cache (api/signin.stale_before; the
    # 1 h one warmed 0 of 1,740 cross-tabs after the 7 Nov 2026 deploy)
    cookie = f'cip_session="{issue("publish@cip")}"'

    def get(url: str) -> bool:
        took = time.perf_counter()
        try:
            with urlopen(Request(url if url.startswith("http") else base + url,
                                 headers={"Cookie": cookie, "Accept-Encoding": "gzip"}), timeout=60) as r:
                r.read()
                return r.status == 200
        except OSError:
            return False
        finally:
            time.sleep(time.perf_counter() - took)   # rest as long as it took: half the core at most
    start = time.perf_counter()
    ok = sum(map(get, urls))
    log.info("Warmed nginx: %d of %d %s in %.0f s", ok, len(urls), what, time.perf_counter() - start)
    return ok


def warm_after_restore(out: Path) -> None:
    """A deploy starts a new container, whose nginx cache is empty although the data has not changed: once nginx and
    the API answer, put back this week's cross-tabs and the answers people asked for most (popular_urls)."""
    base = os.environ.get("CIP_NGINX_URL", "").rstrip("/")
    if not base:
        return
    from urllib.request import urlopen
    for _ in range(90):   # the API takes a few seconds to start beside us (deploy/start.sh)
        try:
            with urlopen(base + "/healthz", timeout=5) as r:
                if r.status == 200:
                    break
        except OSError:
            time.sleep(2)
    try:
        warm_nginx(out)
        ask_nginx(popular_urls(), "most-asked answers from the request log")
    except Exception as exc:   # people still get every answer; the first asker of each waits a little
        log.warning("Warming the nginx cache after a restore failed: %s", exc)


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
    p.add_argument("--jobs", type=int, default=None,
                   help="1-4 workers (default: CIP_PUBLISH_JOBS or 4)")
    p.add_argument("--rollback", action="store_true")
    p.add_argument("--restore", action="store_true")
    p.add_argument("--wait", type=int, default=0, help="seconds to queue for the ETL lock (deploy/start.sh: 6 h)")
    a = p.parse_args()
    from etl.loaders import etl_lock   # one writer of the published files at a time (the scheduled run publishes too)
    # --wait: the restore at a container's start queues for the lock (a load between waves frees it for a moment): at a
    # deploy the old container's run, or a load from elsewhere, holds it, and giving up at once left the new container
    # with no published files (11 Nov 2026: Retailers, Sectors and every prebuilt view 404 on staging for hours)
    with etl_lock(wait=a.wait):
        out = rollback(a.root) if a.rollback else restore(a.root) if a.restore else publish(a.root, a.jobs)
        if a.restore and behind(out):   # newer waves in the database: build only those, link the rest
            log.info("The restored version is behind the database: publishing the new waves")
            out = publish(a.root, a.jobs)
    print(out)
    if a.restore:   # outside the lock: refilling the cache must not hold up a scheduled ETL run
        warm_after_restore(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
