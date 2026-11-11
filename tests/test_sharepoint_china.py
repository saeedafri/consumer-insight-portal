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
    return fake


def test_each_week_folder_loads_once_named_by_its_folder_and_again_when_a_file_is_replaced(graph, csi_db):
    assert sharepoint_china.run(listing_only=True) == [
        "2026/October/Survey of Oct 19: would load baidu_raw_2026-10-26.csv + baidu_topline_2026-10-29.xls as 2026-10-19",
        "2026/October/Survey of Oct 26: would load baidu_raw_2026-11-03.csv + baidu_topline_2026-11-05.xls as 2026-10-26"]
    done = sharepoint_china.run()
    assert [line.split(": ")[1][:30] for line in done] == ["loaded week of 2026-10-19, 556", "loaded week of 2026-10-26, 550"]
    assert graph.published == [1]
    assert sharepoint_china.run() == [] and graph.published == [1]   # nothing new: nothing loaded, nothing published

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
    with pytest.raises(RuntimeError):
        sharepoint_china.run()
    monkeypatch.setattr(baidu_qss_export.serving, "build_wave", real)
    again = sharepoint_china.run()
    assert again[0].startswith("2026/October/Survey of Oct 19: loaded week of 2026-10-19")
    assert again[1].startswith("2026/October/Survey of Oct 26: loaded week of 2026-10-26")
