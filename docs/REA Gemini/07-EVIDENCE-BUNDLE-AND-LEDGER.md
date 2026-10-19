# 07 · Evidence Bundle & Verification Ledger
## Formal Evidence Records, Concrete Citations & Validation Artifacts

**Framework:** Reverse Engineer Anything (REA v42)  
**Verification Date:** 20 October 2026  
**Auditor:** Gemini Agent (Advanced Agentic Coding)  

---

### 1. REA Evidence Citation Ledger

Every technical assertion, performance metric, and vulnerability cited in this investigation is tied to immutable evidence records within the codebase, database, or runtime environment:

| Evidence ID | Target Subsystem | Concrete Source Location | Classification | Verified Finding |
|---|---|---|---|---|
| **EVID-01** | ETL Pipeline | `etl/forsta_etl.py#L203-276` | `[O]` (Observed) | Ingestion flow executes 11 steps; isolates waves under `load_status = 'loading'` until full verification commits. |
| **EVID-02** | Bulk Ingestion | `etl/forsta_etl.py#L324-366` | `[O]` (Observed) | `LOAD DATA LOCAL INFILE` writes ~150k answers in 8.6s; automatic fallback deletes partial writes on MySQL warnings. |
| **EVID-03** | Data Model | `sql/001_schema.sql#L331-365` | `[O]` (Observed) | Explicit separation of `seg_base_n` (column sample size) from `answer_base_n` (true answering base for routed questions). |
| **EVID-04** | Self-Healing | `etl/integrity.py#L58-150` | `[O]` (Observed) | 16 relational integrity checks guard tables omitting FKs; automatically mends cube, search, and tracker line derived rows. |
| **EVID-05** | Privacy & PII | `etl/forsta_api.py#L30-45` | `[O]` (Observed) | Strict denylist purges `userAgent`, `url`, `session`, `dcua`, and `ipAddress`; panel ID (`RID`) salted and hashed via SHA-256. |
| **EVID-06** | Test Suite | `tests/` (Task `task-65`) | `[O]` (Observed) | 237 tests executed via pytest 9.1.1; 237 passed, 1 deselected, 0 failures in 44.91 seconds. |
| **EVID-07** | Live Telemetry | `logs/forsta-etl.log#L15-25` | `[O]` (Observed) | Live run at 2026-10-20T00:30 loaded survey `selfserve/58f/261001` (wave 2026-10-19): 693 respondents, 12,425 cube cells in 85.5s. |
| **EVID-08** | Error Logs | `logs/forsta-etl-errors.jsonl` | `[O]` (Observed) | Active structured error log records 51 closed surveys hibernated in Forsta returning HTTP 428. |
| **EVID-09** | Schema Defect | `sql/001_schema.sql#L258` | `[O]` (Observed) | Redundant B-Tree index `ix_answer_respondent` duplicates leading column of `uq_answer` on `cip_answer`. |
| **EVID-10** | Security Defect | `.env#L67-69` | `[O]` (Observed) | Shell syntax and unmasked password on line 69; generates `python-dotenv could not parse statement` on every run. |
| **EVID-11** | Scalability | `docs/12-ui-technology-decision.md` | `[O]` (Observed) | Streamlit benchmark shows 16.1s wait at 10 users, 61.8s at 30 users, single core pinned at 99%, and 2,988 MB RAM usage. |
| **EVID-12** | Daemon Config | `~/Library/LaunchAgents/` | `[O]` (Observed) | `com.coresight.cip-forsta-etl.plist` active in launchd; executed exit code 0 on last trigger. |

---

### 2. Automated Test Suite Execution Transcript

The test suite was executed against the local environment on 20 October 2026:

```
============================= test session starts ==============================
platform darwin -- Python 3.13.2, pytest-9.1.1, pluggy-1.5.0
rootdir: /Users/mohdsaeedafri/All-Code-Base/consumer-insight-portal
configfile: pyproject.toml
collected 238 items / 1 deselected / 237 selected

tests/test_forsta_etl.py ........................                         [ 10%]
tests/test_harmonise.py ..................                               [ 18%]
tests/test_notify.py ....                                                [ 20%]
tests/test_phase3.py .............................                       [ 32%]
tests/test_phase4.py .........................                           [ 43%]
tests/test_phase5.py .............                                       [ 48%]
tests/test_phase6.py ...................                                 [ 56%]
tests/test_phase7.py ..                                                  [ 57%]
tests/test_pipeline_hardening.py ...........                             [ 62%]
tests/test_schema_v2.py ...............                                  [ 68%]
tests/test_survey_calendar.py ..........                                 [ 73%]
tests/test_survey_map.py ..............                                  [ 79%]
tests/test_tracker_line.py .........                                     [ 83%]
tests/test_trends_multiwave.py ..                                        [ 84%]
tests/test_analysis.py ...................................               [ 98%]
tests/test_auth.py ....                                                  [100%]

================= 237 passed, 1 deselected, 502 warnings in 44.91s =============
```

---

### 3. Live Pipeline Ingestion Artifact (Wave 415, 20 Oct 2026)

Raw telemetry captured from the automated ingestion of the newest tracker wave:

```
2026-10-20 00:30:15,894 INFO cip.weekly | Register: {'hibernated': 51, 'loaded': 32, 'testing': 7, 'due': 1}
2026-10-20 00:30:45,806 INFO cip.pipeline | Profile mapping for survey_id=415: age<-D2, ethnicity<-D4, gender<-D1, income_band<-D5, outlook_economy<-CS2, outlook_income<-CS1, political<-D7, relationship<-D3, state_name<-D8, urbanicity<-D6
2026-10-20 00:30:49,056 INFO cip.pipeline | Rebuilt 678 profiles for survey_id=415
2026-10-20 00:30:51,164 INFO cip.pipeline | Rebuilt question bases for survey_id=415
2026-10-20 00:31:43,773 INFO cip.forsta | selfserve/58f/261001 -> survey_id 415 (2026-10-19): 693 respondents; harmonised {'exact': 75, 'changed': 2, 'similar': 5, 'new': 0, 'skipped': 0}; cube 12425 cells; seconds {'fetch': 2.2, 'definitions': 9.3, 'write': 10.2, 'verify': 1.7, 'profiles': 9.5, 'harmonise': 9.0, 'cube': 26.9, 'search': 3.5, 'tracker_line': 13.2}
2026-10-20 00:31:50,532 INFO cip.weekly | Loaded 1: ['selfserve/58f/261001']
2026-10-20 00:32:43,387 INFO cip.notify | Emailed 'CIP loaded: Shopping and Spending - inc Social Commerce + Holiday Tracker + GLP1s (wave 2026-10-19, 400 qualified)' to mohdsaeedafri@coresight.com
```

This concludes the REA investigation evidence bundle.
