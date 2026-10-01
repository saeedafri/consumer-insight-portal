# Forsta API Adapter — Phase 7 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** When IT delivers a working Forsta API key, each weekly wave loads, verifies and re-checks every publication with no one at the keyboard — and gives exactly the numbers the Excel exports give today.

**Status of the exit test:** the live test (spec §11: *weekly wave loads and verifies unattended*) needs a working key — the key on file is rejected ("account disabled"). Everything else is built and proven here against API-shaped fixtures made from the real 09/21/26 export; the first live run is one command once the key is in `.env`.

**Architecture:** `etl/forsta_api.py` adapts the API to the loader the Excel path already proves (667/667 and 788/788 cells): `questions_from_datamap(payload)` reads Forsta's JSON datamap *per question* (its `questions` list with `variables` and `values`), and `to_record(api_record, questions)` turns an API record — **codes**, numeric status — into the label record the loader consumes (`"Yes"`, `"NO TO: <item>"`, `"Qualified"`). `run_pipeline.ingest_api` uses both, detects the wave (Monday of the earliest fielding date) when asked, and verifies the load against the payload it received. `scripts/weekly_forsta.py` is the unattended run: fetch → load → verify → harmonise → cube → drift, exit non-zero on any failure, one log line per step.

**Defects in the existing API path this fixes** (found reading it, 1 Oct 2026): (1) the datamap parser iterated the flat `variables` list, so every checkbox row became its own question; (2) API status is numeric (3 = qualified) but the loader maps labels — no respondent would have counted as qualified; (3) API values are codes but the loader resolves labels — single-choice answers would have loaded as NULL.

## Forsta JSON shapes assumed (Decipher API v1; to confirm on the first live call)

```json
datamap: {"questions": [{"qlabel": "q2", "qtitle": "Which, if any…", "type": "multiple",
                         "variables": [{"label": "q2r1", "row": "r1", "rowTitle": "Met up…"}],
                         "values": [{"value": 0, "title": "Unchecked"}, {"value": 1, "title": "Checked"}]}],
          "variables": [...]}
data:    [{"record": 12, "uuid": "…", "status": 3, "date": "09/21/2026 10:05", "qtime": 412.3,
           "q2r1": 1, "q2r2": 0, "d2": 34, "hq1": 2}]
```

Status codes: 1 Terminated, 2 Overquota, 3 Qualified, 4 Partial (the loader's own map).

## Global Constraints

- The Excel path stays the reference: an API-loaded wave must equal the Excel-loaded one answer for answer.
- The key is read from `.env` (`FORSTA_API_KEY`); never logged, never printed.
- Scheduling is documented, not installed (a persistent job is the user's / IT's call).
- Never commit/push; no attribution.

## Tasks

1. **Datamap** — tests on a hand-written Decipher-shaped datamap (single, multiple, grid via `grouping: rows` with a single-coded scale, number, text) → `ParsedQuestion`s with the right types, rows and options.
2. **Records** — tests: codes → labels, multi 1/0 → label / `NO TO:` label, numeric status → label, unknown code kept as text, missing values skipped.
3. **Parity with the Excel path** — build the API-shaped datamap + records from `Raw Data 09_21_26.xlsx` (skipped when `CSI_TEST_RAW` is unset), load them through `ingest_api` with a fake client into one database and the Excel file into another; every (respondent, field, code) equal.
4. **Verify + weekly runner** — `verify_api_load(survey_id, records)` compares respondents and per-field counts with the payload; `scripts/weekly_forsta.py` (auth check → ingest → verify → drift; exit 1 on failure); tests with a fake client.
5. **Live check (blocked)** — `scripts/test_connection.py` still reports the key status; document the one command for the first live run and how to schedule it (cron / Azure WebJob); docs.
