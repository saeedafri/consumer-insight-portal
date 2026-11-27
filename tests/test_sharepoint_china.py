"""The SharePoint watcher (etl/sharepoint_china.py) against a fake Microsoft Graph laid out as the analysts' folder:
2026/October/Survey of Oct 19 and Survey of Oct 26, each with Baidu's raw .csv and crosstab .xls. No network."""
from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text

from etl import sharepoint_china

FIXTURES = Path(__file__).resolve().parent / "fixtures"
WEEKS = {"Survey of Oct 19": ("baidu_raw_2026-10-26.csv", "baidu_topline_2026-10-29.xls"),
         "Survey of Oct 26": ("baidu_raw_2026-11-03.csv", "baidu_topline_2026-11-05.xls")}


class Answer:
    def __init__(self, body=None, content=b""):
        self.body, self.content = body, content

    def raise_for_status(self):
        pass

    def json(self):
        return self.body


class FakeGraph:
    """Folders and files by id; `etag` changes a file's version as replacing it in SharePoint would."""
    def __init__(self):
        self.items = {"root": [{"id": "y", "name": "2026", "folder": {}}],
                      "y": [{"id": "m", "name": "October", "folder": {}}],
                      "m": [{"id": f"w{i}", "name": name, "folder": {}} for i, name in enumerate(WEEKS)]}
        self.files = {}
        for i, (name, pair) in enumerate(WEEKS.items()):
            self.items[f"w{i}"] = [{"id": f"w{i}-{n}", "name": f, "eTag": "v1", "file": {}} for n, f in enumerate(pair)]
            self.items[f"w{i}"].append({"id": f"w{i}-en", "name": "week_EN.xlsx", "eTag": "v1", "file": {}})   # ignored
            self.files.update({f"w{i}-{n}": (FIXTURES / f).read_bytes() for n, f in enumerate(pair)})

    def get(self, url, timeout=None):
        if "/drive/root:/" in url:
            return Answer({"id": "root", "parentReference": {"driveId": "d"}})
        item = url.split("/items/")[1].split("/")[0]
        return Answer(content=self.files[item]) if url.endswith("/content") else Answer({"value": self.items[item]})


@pytest.fixture()
def graph(monkeypatch, tmp_path, csi_db):
    fake = FakeGraph()
    for name in ("CIP_SP_TENANT_ID", "CIP_SP_CLIENT_ID", "CIP_SP_CLIENT_SECRET", "CIP_CHINA_SITE", "CIP_CHINA_FOLDER"):
        monkeypatch.setenv(name, "x")
    monkeypatch.setattr(sharepoint_china, "sign_in", lambda found: fake)
    monkeypatch.setattr(sharepoint_china, "UPLOAD_DIR", tmp_path / "uploads")
    published = []
    monkeypatch.setattr("etl.publish.publish", lambda: published.append(1))
    fake.published = published
    fake.emailed = []   # the new-survey email, after the publish (etl/notify.py survey_loaded)
    monkeypatch.setattr("etl.notify.survey_loaded", lambda survey_id: fake.emailed.append((survey_id, list(published))))
    return fake


def test_each_week_folder_loads_once_named_by_its_folder_and_again_when_a_file_is_replaced(graph, csi_db):
    assert sharepoint_china.run(listing_only=True) == [
        "2026/October/Survey of Oct 19: would load baidu_raw_2026-10-26.csv + baidu_topline_2026-10-29.xls as 2026-10-19",
        "2026/October/Survey of Oct 26: would load baidu_raw_2026-11-03.csv + baidu_topline_2026-11-05.xls as 2026-10-26"]
    done = sharepoint_china.run()
    assert [line.split(": ")[1][:30] for line in done] == ["loaded week of 2026-10-19, 556", "loaded week of 2026-10-26, 550"]
    assert graph.published == [1]
    assert len(graph.emailed) == 2 and all(after == [1] for _, after in graph.emailed)   # each week emailed, once published
    assert sharepoint_china.run() == [] and graph.published == [1]   # nothing new: nothing loaded, nothing published
    assert len(graph.emailed) == 2

    graph.items["w1"][0]["eTag"] = "v2"                                # the analyst replaces the raw file
    assert sharepoint_china.run()[0].startswith("2026/October/Survey of Oct 26: loaded week of 2026-10-26")
    with csi_db.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM cip_survey WHERE survey_family = 'CSI-CN'")).scalar() == 2


def test_a_mismatched_pair_is_refused_once_and_reported(graph, csi_db):
    graph.files["w1-1"] = graph.files["w0-1"]                          # Oct 26's raw beside Oct 19's crosstab
    from etl import notify
    first = sharepoint_china.run()
    assert first[1].startswith("2026/October/Survey of Oct 26: refused: ")
    assert ("email", "CIP pipeline FAILED: China survey 2026/October/Survey of Oct 26 not loaded") in notify.sent
    assert sharepoint_china.run() == []                                # the same versions are not tried again


def test_without_its_settings_the_watcher_does_nothing(monkeypatch):
    monkeypatch.delenv("CIP_SP_CLIENT_SECRET", raising=False)
    assert sharepoint_china.run() == []


def test_a_load_that_fails_on_the_way_is_tried_again_next_pass(graph, csi_db, monkeypatch):
    from etl import baidu_qss_export
    real = baidu_qss_export.serving.build_wave
    monkeypatch.setattr(baidu_qss_export.serving, "build_wave", lambda sid: (_ for _ in ()).throw(RuntimeError("database gone")))
    assert sharepoint_china.run()[0] == "2026/October/Survey of Oct 19: failed: RuntimeError: database gone"
    monkeypatch.setattr(baidu_qss_export.serving, "build_wave", real)
    again = sharepoint_china.run()
    assert again[0].startswith("2026/October/Survey of Oct 19: loaded week of 2026-10-19")
    assert again[1].startswith("2026/October/Survey of Oct 26: loaded week of 2026-10-26")


def test_the_webhook_is_created_once_then_renewed(graph, monkeypatch):
    assert sharepoint_china.subscribe().startswith("webhook not set up")
    monkeypatch.setenv("CIP_SP_WEBHOOK_URL", "https://cip.example/api/v1/admin/sharepoint/notify")
    monkeypatch.setenv("CIP_SP_WEBHOOK_SECRET", "s" * 40)
    graph.subscriptions, sent = [], []
    plain_get = graph.get
    graph.get = lambda url, timeout=None: Answer({"value": graph.subscriptions}) if url.endswith("/subscriptions") else plain_get(url)

    def post(url, json=None, timeout=None):
        sent.append(("POST", json))
        graph.subscriptions.append({"id": "sub1", "notificationUrl": json["notificationUrl"], "resource": json["resource"]})
        return Answer()
    graph.post = post
    graph.patch = lambda url, json=None, timeout=None: sent.append(("PATCH", url)) or Answer()
    assert sharepoint_china.subscribe().startswith("webhook created")
    assert sent[0][1]["resource"] == "/drives/d/root" and sent[0][1]["clientState"] == "s" * 40
    assert sharepoint_china.subscribe().startswith("webhook renewed")
    assert sent[1] == ("PATCH", "https://graph.microsoft.com/v1.0/subscriptions/sub1")


def test_the_pass_publishes_under_the_etl_lock_and_waits_its_turn(graph, csi_db, monkeypatch):
    """15 Nov 2026 audit #5: the pass published without the ETL lock, so the 30-minute check, seeing the database ahead,
    could build at the same moment: two builds on the one CPU, both writing .current-next in publish.swap."""
    from contextlib import contextmanager
    from etl.loaders import Locked
    held = []

    @contextmanager
    def lock(wait=0):
        held.append(True)
        yield
        held.append(False)
    monkeypatch.setattr(sharepoint_china, "etl_lock", lock, raising=False)
    monkeypatch.setattr("etl.publish.publish", lambda: graph.published.append(held[-1:] == [True]))
    sharepoint_china.run()
    assert graph.published == [True]                                  # built while the pass held the lock

    def taken(wait=0):
        raise Locked("another CIP run holds the lock")
    monkeypatch.setattr(sharepoint_china, "etl_lock", taken)
    graph.items["w1"][0]["eTag"] = "v2"
    assert sharepoint_china.run()[-1].startswith("publish: another CIP run holds the lock")
    assert graph.published == [True]


def test_a_crashing_load_is_told_once_spares_the_other_weeks_and_is_not_loaded_every_pass(graph, csi_db, monkeypatch):
    """15 Nov 2026 audit #6: only HTTPError was caught, so a pair that crashed the loader ended the pass with no email,
    left the weeks after it unloaded, and was downloaded and loaded again every 10 minutes."""
    from etl import baidu_qss_export, notify
    read_raw = baidu_qss_export.read_raw
    monkeypatch.setattr(baidu_qss_export, "read_raw",   # Oct 19's raw file crashes the reader (a ragged row, say)
                        lambda path, codebook: [][0] if "w0-0" in path.name else read_raw(path, codebook))
    first = sharepoint_china.run()
    assert first[0] == "2026/October/Survey of Oct 19: failed: IndexError: list index out of range"
    assert first[1].startswith("2026/October/Survey of Oct 26: loaded week") and graph.published == [1]
    retries = [sharepoint_china.run() for _ in range(sharepoint_china.ATTEMPTS)]   # 3 tries in all: a database blip
    assert [len(lines) for lines in retries] == [1] * (sharepoint_china.ATTEMPTS - 1) + [0]   # before its run looks the same

    monkeypatch.setattr(baidu_qss_export.serving, "build_wave", lambda sid: (_ for _ in ()).throw(RuntimeError("bug")))
    graph.items["w1"][0]["eTag"] = "v2"                                # replaced by a pair that fails after its write
    passes = [sharepoint_china.run() for _ in range(sharepoint_china.ATTEMPTS + 1)]
    assert [len(lines) for lines in passes] == [1] * sharepoint_china.ATTEMPTS + [0]   # tried again, not every pass
    assert sum(subject.startswith("CIP pipeline FAILED: China survey") for _, subject in notify.sent) == 2   # once each


def test_a_folder_graph_cannot_reach_is_told_too(graph, monkeypatch):
    """Only HTTPError was told: Graph out of reach (a connection error, a timeout) ended every pass with a log line and
    no email, so no China week loaded and nobody heard (15 Nov 2026)."""
    import requests
    from etl import notify
    monkeypatch.setattr(sharepoint_china, "sign_in", lambda found: (_ for _ in ()).throw(requests.ConnectionError("no route")))
    monkeypatch.setattr("sys.argv", ["sharepoint_china"])
    assert sharepoint_china.main() == 1
    assert ("email", "CIP pipeline FAILED: China survey SharePoint watcher cannot read the folder") in notify.sent


def test_a_loaded_week_is_judged_for_alerts_and_a_pass_that_meets_the_lock_keeps_no_copies(graph, csi_db, monkeypatch):
    """China weeks never reached the team's alerts, and a pass that met the lock kept both downloaded files: two more
    every 10 minutes (15 Nov 2026)."""
    from etl import baidu_qss_export, notify
    judged = []
    monkeypatch.setattr(notify, "alerts", judged.append)
    real = baidu_qss_export.load

    def busy(*args, **kwargs):
        raise sharepoint_china.Locked("another CIP run holds the lock")

    monkeypatch.setattr(baidu_qss_export, "load", busy)
    assert sharepoint_china.run()[-1].endswith("another CIP run holds the lock; next pass")
    assert list(sharepoint_china.UPLOAD_DIR.iterdir()) == []
    monkeypatch.setattr(baidu_qss_export, "load", real)
    assert len(sharepoint_china.run()) == 2 and [len(ids) for ids in judged] == [1, 1]


def test_a_month_and_year_folder_is_not_read_as_a_day():
    # "May 2026" was read as 20 May 2026 (review of 20 Nov 2026)
    assert sharepoint_china.folder_week(("2026", "May 2026")) is None
    assert sharepoint_china.folder_week(("2026", "May 20")) == "2026-05-20"
