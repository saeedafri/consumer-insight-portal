"""Gemini isolated regression tests for high-impact defects found in the 20 Nov 2026 audit.

Run against an unpatched snapshot to confirm RED (reproduces each defect), and after applying
Gemini-patch-01..03 to confirm GREEN (verifies each fix without regressing existing behavior).
"""
from __future__ import annotations

import asyncio
import gzip
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest


def test_api_write_does_not_inherit_etl_owner_credentials(monkeypatch):
    """NEW-SEC-01: api_write must prefer APP_DB_USER (or API_WRITE_DB_USER), never STG_DB_USER."""
    from shared.core.config import Config

    monkeypatch.setenv("APP_ENV", "STAGING")
    monkeypatch.setenv("STG_DB_HOST", "db.invalid")
    monkeypatch.setenv("STG_DB_NAME", "cip_stg")
    monkeypatch.setenv("STG_DB_USER", "cip_etl_owner")
    monkeypatch.setenv("STG_DB_PASSWORD", "etl-pw")
    monkeypatch.setenv("APP_DB_USER", "cip_app_user")
    monkeypatch.setenv("APP_DB_PASSWORD", "app-pw")
    cfg = Config()
    assert cfg.database("api_write").user == "cip_app_user"


def test_access_scope_separates_internal_staff_from_external_clients():
    """NEW-SEC-02: staff with a disabled feature must never share a cache scope key with external clients."""
    from shared.core import access

    all_features = list(access.rules()["features"])
    staff_minus_export = {
        "email": "staff@coresight.com", "role": "analyst", "client": None, "tier": "enterprise",
        "study_types": "*", "features": [f for f in all_features if f != "export"],
    }
    external_client = {
        "email": "ext@partner.com", "role": "client", "client": None, "tier": "enterprise",
        "study_types": "*", "features": all_features,
    }
    assert access.scope(staff_minus_export) != access.scope(external_client)


def test_session_renew_fails_closed_when_database_is_unavailable(monkeypatch):
    """NEW-SEC-06: renew() must return False (fail closed) on DB failure, not extend revoked cookies."""
    from api import signin

    def broken_engine(_role):
        raise RuntimeError("db down")

    monkeypatch.setattr(signin, "get_engine", broken_engine)
    assert signin.renew("some-session-id") is False


def test_publish_swap_preserves_just_activated_older_target(tmp_path):
    """NEW-PUB-01: swap() must never delete the directory it just pointed `current` to."""
    from etl import publish

    dirs = [tmp_path / f".build-202611{d:02d}T000000Z" for d in (10, 15, 16, 17)]
    for d in dirs:
        (d / "api/v1").mkdir(parents=True)
        (d / "manifest.json").write_text("{}")
    publish.swap(tmp_path, dirs[0])
    assert dirs[0].is_dir()
    assert (tmp_path / "current").exists()
    assert (tmp_path / "current").resolve() == dirs[0].resolve()


def test_readyz_requires_manifest_and_valid_waves(tmp_path, monkeypatch):
    """ETL-03: /readyz must return 503 when manifest.json is missing."""
    from api import main as api

    cur = tmp_path / "current"
    v1 = cur / "api/v1"
    v1.mkdir(parents=True)
    (v1 / "waves.json.gz").write_bytes(gzip.compress(json.dumps([{"survey_id": 1}]).encode()))
    monkeypatch.setattr(api, "PUBLISHED", cur)
    resp = asyncio.run(api.readyz())
    assert resp.status_code == 503


def test_cohorts_config_path_resolves_inside_repo():
    """NEW-ETL-COHORTS: etl/cohorts.py CONFIG must point to repo/config/cohorts.yml."""
    from etl import cohorts

    assert cohorts.CONFIG.exists()
    assert cohorts.CONFIG.parent.name == "config"


def test_sharepoint_folder_week_does_not_misparse_month_year():
    """NEW-ETL-SP: 'May 2026' must not parse as 2026-05-20."""
    from etl import sharepoint_china

    assert sharepoint_china.folder_week(("2026", "May 2026")) is None
    assert sharepoint_china.folder_week(("2026", "May 20")) == "2026-05-20"


def test_ask_blocks_weighted_overlap_union_and_mean_bypasses(tmp_path):
    """NEW-ASK-GUARDS: Close phrasing bypasses for weighted, overlap/union, and mean-spend requests."""
    from api import assistant
    from api.ask_index import Index

    root = tmp_path / "CSI-US" / "tracker"
    root.mkdir(parents=True)
    data = {
        "qcode": "XQ1", "waves": [[100, "2026-10-26", 1]], "versions": ["Which retailers have you bought from?"],
        "answers": [["", 1, "Amazon"], ["", 2, "Walmart"], ["", 3, "Target"]],
        "cuts": [["total", "Total"]], "w": [0, 0, 0], "c": [0, 0, 0], "a": [0, 1, 2],
        "n": [170, 150, 90], "b": [400, 400, 400],
    }
    (root / "XQ1.json.gz").write_bytes(gzip.compress(json.dumps(data).encode()))
    idx = Index(tmp_path, [{"survey_id": 100, "wave_date": "2026-10-26"}])
    for q in (
        "Weighted Amazon Prime membership share in the latest wave",
        "Compare weighted vs unweighted Amazon Prime membership",
        "How many people bought both groceries and clothing online?",
        "What is the overlap between Amazon and Walmart shoppers?",
        "How many shopped at either Walmart or Target?",
        "What is the mean amount spent on holiday gifts?",
        "How much on average did consumers spend on Thanksgiving turkey?",
    ):
        found = assistant.answer(q, idx, {100}, quick=True, key="CSI-US/tracker/XQ1")
        assert found["mode"] == "none", f"Expected refusal for {q!r}, got {found.get('mode')!r}"


def test_ask_spelling_does_not_leak_hidden_survey_vocabulary(tmp_path):
    """NEW-ASK-01: correct_spelling must not leak terms from surveys outside the caller's visible set."""
    from api import assistant
    from api.ask_index import Index

    pub_q = tmp_path / "PUBLIC_FAM" / "tracker"
    priv_q = tmp_path / "CLIENT_SECRET" / "adhoc"
    pub_q.mkdir(parents=True)
    priv_q.mkdir(parents=True)
    d_pub = {"qcode": "Q1", "waves": [[1, "2026-10-26", 1]], "versions": ["Do you buy groceries?"],
             "answers": [["", 1, "Yes"]], "cuts": [["total", "Total"]], "w": [0], "c": [0], "a": [0], "n": [50], "b": [100]}
    d_priv = {"qcode": "S1", "waves": [[2, "2026-10-26", 1]], "versions": ["Have you purchased Zephyrium widgets?"],
              "answers": [["", 1, "Zephyrium"]], "cuts": [["total", "Total"]], "w": [0], "c": [0], "a": [0], "n": [50], "b": [100]}
    (pub_q / "Q1.json.gz").write_bytes(gzip.compress(json.dumps(d_pub).encode()))
    (priv_q / "S1.json.gz").write_bytes(gzip.compress(json.dumps(d_priv).encode()))
    idx = Index(tmp_path, [{"survey_id": 1, "wave_date": "2026-10-26"}, {"survey_id": 2, "wave_date": "2026-10-26"}])
    res = assistant.ask("How many bought Zephryium?", idx, visible={1}, scope="client:other", quick=True)
    assert res.get("corrected") is None
