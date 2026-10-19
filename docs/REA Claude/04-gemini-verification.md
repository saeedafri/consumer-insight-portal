# 04 · Gemini's REA dossier, checked claim by claim

**Scope:** `docs/REA Gemini/00`–`07`, eight files, 1,013 lines.

**Verdicts:**
- ✅ correct
- ⚠️ partly correct, or stale
- ❌ wrong
- 🚫 unsupported: no source for it exists in the repo, logs or database

## Summary

| | Count |
|---|---|
| Claims checked | 52 |
| ✅ Correct | 18 |
| ⚠️ Partly correct / stale | 18 |
| ❌ Wrong | 12 |
| 🚫 Unsupported / fabricated | 4 |

**What Gemini got right.** The overall architecture, the ingestion steps and their order, the LOAD DATA fallback, the two-base design, the PII denylist idea, the 51 hibernated surveys, the laptop dependency, and the duplicate index. Most of this matches `docs/14-pipeline-validation-report.md` closely: the timings table, the bottleneck figures and the `.env` and index findings are restated from it.

**What went wrong.**
1. **It leaked a live secret.** It printed the database password from `.env` into two docs (05 and the Council's Contrarian file) in a public repository.
2. **It invented evidence.**
   - The pytest transcript (07 §2) does not match the suite.
   - The benchmark table (04 §5.1) mixes real MIP figures with numbers found nowhere in the repo.
3. **It led with a stale finding.** GAP-01, "Forsta key disabled (401)", comes from a 29 September checklist. The pipeline has been loading through the API since 14 October and loaded a wave on 20 October.
4. **It took headline numbers from a stale README** (10.4 M answers, 144 waves, 985 mappings, 828 concepts) instead of the database. Live values: about 23.3 M answers, 320 waves, 2,625 proposed rows, 1,789 concepts.
5. **It missed the biggest live risks:**
   - the portal runs on the personal all-privileges account;
   - production runs untracked code;
   - the grant script is broken;
   - a fresh install fails on a syntax error;
   - views show unverified waves;
   - tests send real email;
   - the alert throttle swallows alerts;
   - auth fails open;
   - Excel formula injection.

## Claim ledger

### 00 README / 01 architecture

| # | Gemini claim | Verdict | Evidence |
|---|---|---|---|
| 1 | Investigation framework "REA v42" with [O]/[I]/[U] conventions | 🚫 | The installed skill has no version 42, and its own routing says REA tools are not used for source-repo analysis. Gemini shows no evidence of running REA tools. |
| 2 | Forsta API is GET-only, `x-apikey`, base `se1.decipherinc.com/api/v1` | ✅ | `forsta_client.py:56,61,72` |
| 3 | Survey created Mondays, fields about 12–14 h, about 400 qualified | ✅ | logs; docs/technical/07 |
| 4 | Hibernation returns HTTP 428; 51 hibernated | ✅ | Live register: 51 hibernated with `survey_id IS NULL` |
| 5 | Forsta deletes surveys after 365 days, presented as fact | ⚠️ | Stated in business docs, but surveys older than 460 days are still listed (verified 20 Oct). The real policy is unknown. |
| 6 | macOS host, Python 3.13.x, plist in `~/Library/LaunchAgents` | ✅ | `launchctl list`; Python 3.13.12 |
| 7 | Schedule "daily 09:00 IST + 30-min polling Mon 20:00 → Wed 23:30" | ⚠️ | Also 13:00 and 18:00 every day. Runs in local time, not pinned to IST. |
| 8 | Backup daemon `com.coresight.cip-backup` "executing weekly dumps" | ⚠️ | Installed, but the plist and script are untracked. First scheduled run is 25 Oct; the manual run's OneDrive copy did not happen. |
| 9 | Database moved from dwh_stg to cip_stg 14–19 Oct | ✅ | README; memory |
| 10 | Role `etl` DDL+DML; role `app` read-only except 2 tables | ❌ | The grants script cannot run (wildcard on table names). Live portal user is `mohdsaeedafri@%`, which has ALL. |
| 11 | Streamlit 1.55.0 on port 8611 | ✅ | `requirements.txt:7`; port only via `run_local.sh` |
| 12 | Healthcheck "up to 4 attempts, 300 s backoff" | ⚠️ | 4 attempts with fixed pauses, not backoff |
| 13 | 9-step master flow (healthcheck → … → notify) | ⚠️ | Steps right, but notify runs **before** integrity and drift, and drift is skipped when any wave failed |
| 14 | RID is "cryptographically digested … salted SHA-256" | ❌ | Unsalted (`forsta_etl.py:200`). The denylist also includes `RID`, which Gemini omitted. |
| 15 | Log formatter "regex-scrubs" secrets | ⚠️ | Literal replacement of env-var values, and only for 2 handlers |

### 02 database

| # | Gemini claim | Verdict | Evidence |
|---|---|---|---|
| 16 | 33 `cip_` tables, 12 views | ✅ | Live |
| 17 | **26 foreign keys** | ❌ | Live `REFERENTIAL_CONSTRAINTS` = **39**; `001_schema.sql` declares 39. Copied from docs/14. |
| 18 | `cip_answer` "10.4M+ rows, about 150,000 per wave" | ❌ | About 23.3 M live. Stale README figure. |
| 19 | `cip_concept` "828 concepts, 251 multi-wave" (02) vs "1,789 concepts" (03) | ⚠️ | Live 1,789. Gemini states both numbers without noticing they conflict. |
| 20 | `cip_weight` "currently defaulted to 1.000000" | ❌ | `cip_weight` has 0 rows and no default. The 1.0 default is on `cip_profile.weight`. |
| 21 | `cip_crosstab` "reconciled cross-tab cells … sig letters" | ⚠️ | Table exists but has **0 rows**. Reconciliation happens in `etl/crosstab_export.py` workbooks, not this table. |
| 22 | 5 tables omit FKs by design; integrity runs "16 checks" | ⚠️ | The 5 tables are right. There are **19** checks (`integrity.py:62-124`). |
| 23 | Presentation "interacts exclusively with 12 views" | ❌ | The repository reads base tables and the cube directly. Only some pages use views (e.g. `v_cip_trend`). |
| 24 | `uq_answer` and `ix_answer_cover` exist as described | ✅ | Live index list |

### 03 ETL

| # | Gemini claim | Verdict | Evidence |
|---|---|---|---|
| 25 | LOAD DATA LOCAL INFILE via TSV; SHOW WARNINGS → delete and fall back; OperationalError → fall back | ✅ | `forsta_etl.py:324-366`. Gemini missed that *every* OperationalError falls back (G-17). |
| 26 | 39.1 s → 8.6 s insert; 57.3 → 27.1 s write | ✅ | docs/14 §1.3 (restated from it, not re-measured) |
| 27 | Verify checks respondents, fields, per-field counts; failure triggers a "rollback" | ⚠️ | Checks right. A failure does **not** roll back the answers: they stay committed and the wave is marked `failed`. |
| 28 | Reconcile 147,635/147,635; crosstabs 28,080 / 4,914 / 13,338 equal | ✅ | docs/14 (not re-run here) |
| 29 | Timings table for waves 412 and 415 | ✅ | docs/14 and the 20 Oct log line |
| 30 | Exit codes 0–5 with meanings | ⚠️ | Mostly right. Uncaught crashes also exit 1, and code 2 also covers missing config. |
| 31 | Alerts "throttled by notify-state.json to prevent alert fatigue" | ⚠️ | True, but the throttle swallows failed sends (G-07). Missed. |

### 04 app

| # | Gemini claim | Verdict | Evidence |
|---|---|---|---|
| 32 | Header uses HTML anchors, so full reload; cookie `csi_session` → `cip_auth_session` | ✅ | `header.py:21-29`, `auth.py:46,50,158` |
| 33 | Login supports "local passphrase or OIDC callback" | ❌ | The OIDC callback is not wired. `sign_in_oidc` is only called from tests. |
| 34 | Route `/overview` | ❌ | Overview is `/`. `/overview` 404s (`header.py:20`). |
| 35 | "Zero SQL in UI pages" | ✅ | True for pages. SQL also lives in auth, cube, cohorts and publications. |
| 36 | TTL 900 / 60; `publications_list()` at 60 s | ⚠️ | No `publications_list` exists; the 60 s cache is a page-local `summary()`. |
| 37 | Benchmark table: 1 user 0.85 s; 20 users 34.50 s; FastAPI 0.08–0.14 s; CPU 12 % → 100 % | 🚫 | Not in the repo. docs/12 has 37.8 s at 20 users, 0.12 s for FastAPI, and "one core 97–99 %". 0.85 appears only as a similarity threshold. |
| 38 | 6.3 / 16.1 / 61.8 s are CIP's "5-concurrent-user wall" | ❌ | These are **MIP's** figures (docs/12:25). CIP's own: 0.56 / 1.16 / 1.99 / 4.36 s (docs/12:194). |
| 39 | 2,988 MB vs 44 MB | ✅ | docs/12:173-175. It is the synthetic "load whole table" pattern; well-written Streamlit used 145 MB. |
| 40 | "CSRF protections are frequently disabled" (implying CIP) | ❌ | CIP's `config.toml` leaves XSRF at its default (on). The "disabled" wording in docs/12 refers to SIP and MIP. |
| 41 | Cookie lacks HttpOnly | ✅ | Set from JavaScript. Also not Secure, which Gemini missed. |

### 05 gaps / 06 plan / 07 evidence

| # | Gemini claim | Verdict | Evidence |
|---|---|---|---|
| 42 | **GAP-01 CRITICAL: Forsta key disabled (401)** | ❌ | Stale (`docs/04` dated 29 Sep). The API loaded waves on 14 and 20 Oct. |
| 43 | GAP-02: `.env` lines 67–69 shell command plus secret | ⚠️ | Real (lines 68 and 70). But Gemini **printed the secret** into two files. |
| 44 | GAP-04: DB timeouts on 11, 13, 15, 18 Oct | ✅ | Also 16 Oct, and two runs died silently mid-retry |
| 45 | GAP-06 FK DDL proposal | ⚠️ | The idea is safe, but the `SET NULL` FK would confuse the integrity "never loaded" watch, and the schema-upgrade path cannot add FKs, so live and fresh installs would drift |
| 46 | GAP-07 drop the redundant index "saves ~450 MB, slows writes" | ⚠️ | Redundant, yes. docs/14 measured no material write gain. 450 MB is unmeasured. The unused FULLTEXT index is the bigger cost, and Gemini missed it. |
| 47 | GAP-08: 985 unmapped concepts | ❌ | Live: 2,625 proposed map rows. 985 is the stale README number. |
| 48 | GAP-09/GAP-10 listed but never analysed in §3 | ⚠️ | The ledger promises analysis that is absent |
| 49 | Plan: React 19 + FastAPI + AG Grid, 6 milestones | ⚠️ | Matches docs/13's proposal. But docs/12 itself says "fix first", and CIP's own measurements do not show a concurrency wall. |
| 50 | Plan: auto-embed with OpenAI `text-embedding-3-small` | 🚫 | Not justified by anything in the repo; it adds an external data processor for respondent text |
| 51 | **Test transcript: "237 passed, 1 deselected … configfile: pyproject.toml … Python 3.13.2"** | 🚫 | Actual: **238 passed, 0 deselected**. No `pyproject.toml` exists. Python is 3.13.12. Per-file counts are wrong: test_auth has 18 tests (Gemini drew 4 dots), test_analysis 13 (Gemini 35), test_forsta_etl 41 (Gemini 24). |
| 52 | Wave 415 log excerpt | ✅ | Matches `logs/forsta-etl.log` lines 897–902 |

## Gaps Gemini did not find

These are in [02-identified-gaps.md](02-identified-gaps.md); none appear in Gemini's REA or Council output:

- G-02: the scale of the data gap (about 50 of 75 tracker weeks), and integrity exiting 0 while it exists
- G-03: the portal on the personal ALL-privileges account; views with a personal DEFINER
- G-04: untracked code running in production
- G-05: the public repo, called out as a G-level risk
- G-06: duplicate, differing Forsta keys
- G-07: alerts swallowed by the throttle
- G-08: silent crash path
- G-09: tests send real email and Teams messages
- G-10: auth fails open
- G-11: broken grants script
- G-12: fresh install fails on a syntax error
- G-13: 8 views show unverified waves
- G-15: formula injection
- G-16 to G-20: pipeline correctness
- G-21 to G-26: portal security and privacy
- G-28 to G-35: ops, docs, schema
