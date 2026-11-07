# Forsta (Decipher) Complete Read-Only API Reference & Menu Architecture Blueprint

**Document Reference:** CIP-DOC-2026-REF1  
**Audit Date:** 7 November 2026  
**Environment Verified:** Staging & Local Master (`cip_stg` database, Coresight Research Company 86 on `se1.decipherinc.com`)  
**Test Suite Status:** 460 of 460 tests passing (22.3s), Next.js 16.4.2 production build clean (11/11 static routes prerendered)  
**Security & Integrity Contract:** 100% read-only. Zero survey edits, zero variable modifications, and zero changes to Forsta data.

---

## Executive Summary & CIP Evolution Since Last Review

Since the initial investigation, the CIP codebase has undergone extensive production deployments on 7 November 2026:
1. **Read-Only POST Enforcement:** In `etl/forsta_client.py`, a strict regex guard (`READ_ONLY_POSTS`) was implemented. It permits only three computational POST operations (`crosstabs/execute`, `crosstabs/saved/{id}/execute`, `crosstabs/saved/{id}/export/{format}`) and raises `ForstaError` on any other POST, PUT, PATCH, or DELETE before network dispatch.
2. **Forsta Records Warehouse Table (`cip_forsta_record`):** A dedicated storage table was created (`sql/009_forsta_record.sql`) that persists raw gzip-compressed JSON payloads from Forsta's read-only endpoints without altering research tables.
3. **8 New Admin Screens Deployed:** A dedicated `/app/forsta/...` section was introduced with 8 modular views: Team Reports, Forsta vs CIP Reconciliation, Cross-Tab Setup, Sample & Devices, Warnings & Checks, Survey Files, Archive & Deletion, and Forsta Account.
4. **Fieldwork & Survey Screens (`/app/fieldwork/...`):** Real-time monitoring of live fieldwork, page-by-page drop-out attrition, quota pacing, and speeder screen-out rules.
5. **Reconciliation Proof:** Cell-by-cell verification proved that CIP counted **43,396 of 43,396 cells** identically to Forsta across 77 loaded surveys (100.0% exact match).

This document provides the definitive, exhaustive reference for **all 125 read-only operations** (117 `GET` endpoints and 8 read-only `POST` endpoints) in Forsta Surveys (Decipher), explaining what each does, how to use it, its live behavior on our account, where it is mapped in CIP today, and exact specifications for proposed new menus.

---

## Part 1: Exhaustive Catalog of All 125 Read-Only APIs

Every endpoint in the official Decipher REST API 1.0 specification is documented below, grouped across 13 functional domains.

```
┌────────────────────────────────────────────────────────────────────────┐
│                   FORSTA READ-ONLY API ARCHITECTURE                    │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
    ┌───────────────────────────────┼────────────────────────────────┐
    ▼                               ▼                                ▼
┌───────────────────────┐   ┌───────────────────────┐   ┌────────────────────────┐
│ 117 GET ENDPOINTS     │   │ 8 READ-ONLY POSTS     │   │ MULTI-PANEL MAPPING    │
│ • 36 in active use    │   │ • crosstabs/execute   │   │ • 8 Active Screens     │
│ • 16 need specific IDs│   │ • saved reports exec  │   │ • 6 Proposed New Menus │
│ • 65 for specialized  │   │ • saved reports export│   │ • Role-based access    │
│   features/modules    │   │ • filtered /data      │   │   (Admin/Analyst/Client│
└───────────────────────┘   └───────────────────────┘   └────────────────────────┘
```

---

### Domain 1: Survey Inventory, Lifecycle & State (14 Operations)

| # | Endpoint & Method | Purpose & Description | Parameters & Usage | Live Account Status | Current CIP Menu / Proposed New Menu |
|---|---|---|---|---|---|
| 1 | `GET /rh/companies/{company}/surveys` | Lists all surveys belonging to a company account. | Path: `company` (or `all`). Returns path, state, title, dates. | Working (200) | **Active Menu:** In `etl/forsta_etl.py:discover` to build the survey register. |
| 2 | `GET /rh/surveys/current` | Returns surveys currently in active testing or live fielding. | Query: optional filters. Returns active surveys. | Working (Empty for our key) | **Proposed Menu:** *Fieldwork Pacing $\rightarrow$ Active Waves* |
| 3 | `GET /rh/surveys/historical` | Complete chronological catalog of past surveys across all years. | Returns array of historical survey objects. | Working (200) | **Active Menu:** `/app/forsta/account` ("In Forsta, not in CIP"). |
| 4 | `GET /rh/surveys/archived` | Lists all surveys moved into cold archive storage. | Returns paths, archive dates, deletion dates. | Working (200, 101 records) | **Active Menu:** `/app/forsta/deletion` ("Archive & Deletion"). |
| 5 | `GET /rh/surveys/{survey}` | High-level survey summary: question count, state, launch/close. | Path: `survey`. Returns survey metadata object. | Working (200) | **Active Menu:** `/app/fieldwork/:survey` ("In Forsta" card). |
| 6 | `GET /rh/surveys/{survey}/audit-log` | Audit log of survey timeline: cloned, launched, edited, closed. | Path: `survey`. Returns event list with timestamps. | Working (200) | **Active Menu:** `/app/fieldwork/:survey` (Audit Timeline). |
| 7 | `GET /rh/surveys/categories` | Returns project categories and taxonomy groupings. | Returns category IDs and display names. | Working (200) | **Active Menu:** `/app/forsta/account` (Category badge). |
| 8 | `GET /surveys/{survey}/state/warnings` | Structural logic checks and warnings. | Path: `survey`. | Returns 404 (uses state/live) | Merged into Launch Warnings. |
| 9 | `GET /surveys/{survey}/state/live/warnings` | Pre-launch checklist: verifies quotas, email links, test data. | Path: `survey`. Returns warning checks list. | Working (200) | **Active Menu:** `/app/forsta/warnings` (Launch checks). |
| 10 | `GET /surveys/{survey}/warnings` | Runtime survey errors: blocked sessions, server exceptions. | Path: `survey`. Returns warning dictionary. | Working (200) | **Active Menu:** `/app/forsta/warnings` (Runtime flags). |
| 11 | `GET /rh/warnings/summary` | Global count of warnings across all company surveys. | Returns `{survey_path: warning_count}`. | Working (200) | **Active Menu:** `/app/forsta/warnings` (Overview bar). |
| 12 | `GET /autoclose/planned` | Surveys scheduled for automatic close within $N$ days. | Query: `days`. Returns scheduled closures. | Working (200, 0 today) | **Active Menu:** `/app/forsta/deletion` (Auto-close schedule). |
| 13 | `GET /search` | Global keyword search across surveys, questions, and metadata. | Query: `q`. Returns matching survey paths. | Working (200) | **Proposed Menu:** *Global Survey Search* |
| 14 | `GET /parameters/list/{survey}` | Configurable programming parameters defined for the survey. | Path: `survey`. Returns parameter schema. | Working (200) | **Proposed Menu:** *Survey Setup $\rightarrow$ Project Parameters* |

---

### Domain 2: Questionnaire Schema, XML & Design (11 Operations)

| # | Endpoint & Method | Purpose & Description | Parameters & Usage | Live Account Status | Current CIP Menu / Proposed New Menu |
|---|---|---|---|---|---|
| 15 | `GET /surveys/{survey}/datamap` | Questionnaire schema: questions, types, codes, variables. | Query: `format=json\|xml\|html\|tab`. | Working (200) | **Active Menu:** Core load (`forsta_etl.py`) & `/app/w/:id/survey`. |
| 16 | `GET /surveys/{survey}/files` | File inventory of survey repository (XML, CSS, JS, datamaps). | Path: `survey`. Returns filenames, sizes, dates. | Working (200) | **Active Menu:** `/app/forsta/files` (Survey Files table). |
| 17 | `GET /surveys/{survey}/files/{filename}` | Downloads a specific survey asset (e.g., `survey.xml`). | Path: `survey`, `filename`. Streams file bytes. | Working (200) | **Active Menu:** Parsed by `etl/fieldwork.py` for question logic. |
| 18 | `GET /surveys/{survey}/files/headers` | HTTP headers and MIME metadata for uploaded survey assets. | Path: `survey`. Returns headers dictionary. | Working (200) | **Active Menu:** `/app/forsta/files` (File metadata). |
| 19 | `GET /surveys/{survey}/terms` | Screen-out and terminate conditions defined in the survey. | Path: `survey`. Returns termination rules. | Working (200) | **Active Menu:** `/app/fieldwork/:survey` (Speeder/Screen-out terms). |
| 20 | `GET /surveys/{survey}/sections` | Modular questionnaire sections for multi-programmer projects. | Path: `survey`. Returns section list. | 400 (Not configured) | **Proposed Menu A:** *Modular Section Manager* |
| 21 | `GET /surveys/{survey}/sections/{section}/editor` | Retrieves the username currently editing/locking a section. | Path: `survey`, `section`. Returns username. | 400 (No sections) | **Proposed Menu A:** *Modular Section Manager* |
| 22 | `GET /surveys/{survey}/sections/{section}/validate` | Validates section XML syntax without saving. | Path: `survey`, `section`. Returns syntax status. | 400 (No sections) | **Proposed Menu A:** *Modular Section Manager* |
| 23 | `GET /libraries/{company}/elements` | Standardized reusable question bank from company library. | Path: `company`. Returns question element list. | Working (200) | **Proposed Menu B:** *Corporate Question Bank Library* |
| 24 | `GET /libraries/{company}/elements/{eid}` | Retrieves specific corporate library question definition. | Path: `company`, `eid`. Returns element XML/JSON. | Working (200) | **Proposed Menu B:** *Corporate Question Bank Library* |
| 25 | `GET /libraries/{company}/surveys/{survey}/elements` | Library questions linked inside this specific survey. | Path: `company`, `survey`. Returns linked IDs. | Working (200) | **Proposed Menu B:** *Corporate Question Bank Library* |

---

### Domain 3: Microdata Extraction & Filtering (11 Operations)

| # | Endpoint & Method | Purpose & Description | Parameters & Usage | Live Account Status | Current CIP Menu / Proposed New Menu |
|---|---|---|---|---|---|
| 26 | `GET /surveys/{survey}/data` | Stream respondent records across 16 formats (`json`, `spss`, `csv`). | Query: `format`, `cond`, `fields`, `start`, `end`. | Working (200) | **Active Menu:** Core load (`etl/forsta_etl.py`). |
| 27 | `POST /surveys/{survey}/data` | **Read-Only POST:** Stream microdata with large body filter. | Body: `{format, cond, fields, start, end}`. | Working (200, 1.1s) | **Active Backend:** Available for complex queries exceeding 1KB. |
| 28 | `GET /datafeed/{feed}` | Real-time push stream of completed responses as they finish. | Path: `feed`. Returns batch of new records. | Needs feed setup | **Proposed Menu C:** *Live Streaming Fieldwork Ingestion* |
| 29 | `GET /datafeed/{feed}/state` | Synchronization cursor offset of the data feed. | Path: `feed`. Returns last acknowledged offset. | Needs feed setup | **Proposed Menu C:** *Live Streaming Fieldwork Ingestion* |
| 30 | `GET /surveys/{survey}/simulated` | Generates Monte Carlo test respondents for capacity testing. | Path: `survey`. Returns synthetic rows. | Working (200) | **Proposed Menu D:** *Testing & Monte Carlo Stress Test* |
| 31 | `GET /surveys/{survey}/datasources` | Lists external connected data lookup tables. | Path: `survey`. Returns datasource array. | Working (200) | **Active Menu:** `/app/forsta/account` (Datasources count). |
| 32 | `GET /surveys/{survey}/datasources/{datasource}` | Schema definition of an external lookup datasource. | Path: `survey`, `datasource`. Returns schema. | Needs datasource | **Proposed Menu E:** *External Datasources & Lookup Tables* |
| 33 | `GET /surveys/{survey}/datasources/{datasource}/data` | Tabular rows of an external connected datasource. | Path: `survey`, `datasource`. Returns data. | Needs datasource | **Proposed Menu E:** *External Datasources & Lookup Tables* |
| 34 | `GET /surveys/{survey}/layouts` | Data export column layouts configured for the survey. | Path: `survey`. Returns layout definitions. | Working (200) | **Active Menu:** `/app/forsta/account` (Layout count). |
| 35 | `GET /surveys/{survey}/layouts/{layout_id}` | Detailed variable mapping of a specific export layout. | Path: `survey`, `layout_id`. Returns column map. | Needs layout ID | **Proposed Menu F:** *Custom Export Layouts & Slices* |
| 36 | `GET /surveys/{survey}/edits/{edit}` | Audit log of data cleaning edits applied to respondents. | Path: `survey`, `edit`. Returns edit audit record. | Needs edit ID | Merged into Survey Audit Log. |

---

### Domain 4: Quota Tracking & Fieldwork Pacing (1 Operation)

| # | Endpoint & Method | Purpose & Description | Parameters & Usage | Live Account Status | Current CIP Menu / Proposed New Menu |
|---|---|---|---|---|---|
| 37 | `GET /surveys/{survey}/quota` | Complete quota tree: sheets, defines, limits, and completes. | Path: `survey`. Returns quota JSON. | Working (200) | **Active Menu:** Core load (`forsta_etl.py`) & `/app/fieldwork/:survey`. |

---

### Domain 5: Fieldwork Scorecards, Completions & Dropouts (5 Operations)

| # | Endpoint & Method | Purpose & Description | Parameters & Usage | Live Account Status | Current CIP Menu / Proposed New Menu |
|---|---|---|---|---|---|
| 38 | `GET /surveys/{survey}/summary/completions` | Instant scorecard: click-throughs, completes, terminates, LOI. | Path: `survey`. Returns completions dictionary. | Working (200, 0.4s) | **Active Menu:** `/app/fieldwork/:survey` (Funnel summary card). |
| 39 | `GET /surveys/{survey}/summary/dropouts` | Question-by-question attrition funnel with seconds per page. | Path: `survey`. Returns page dropout table. | Working (200, 0.4s) | **Active Menu:** `/app/fieldwork/:survey` (Drop-out analysis table). |
| 40 | `GET /surveys/{survey}/summary/splits` | Fieldwork metrics segmented by sample source, OS, browser. | Path: `survey`. Returns split breakdown. | Working (200) | **Active Menu:** `/app/forsta/samples` (Sample & Devices screen). |
| 41 | `GET /surveys/{survey}/summary/campaigns` | Completion statistics segmented by email invite campaign. | Path: `survey`. Returns campaign summary. | Working (Empty for panel) | Merged into Campaign Reporting. |
| 42 | `GET /surveys/{survey}/summary/share_link` | Retrieves active shareable view link token for survey summary. | Path: `survey`. Returns share URL. | Working (200) | **Proposed Menu:** *Shareable Fieldwork Link* |

---

### Domain 6: Crosstabs, Tabulation & Statistical Execution (10 Operations)

| # | Endpoint & Method | Purpose & Description | Parameters & Usage | Live Account Status | Current CIP Menu / Proposed New Menu |
|---|---|---|---|---|---|
| 43 | `POST /surveys/{survey}/crosstabs/execute` | **Read-Only POST:** Computes n-way crosstabs in memory. | Body: `{simplified, segments, filters, tables}`. | Working (200, 1.35s) | **Active Menu:** `/app/forsta/check` ("Forsta vs CIP" audit). |
| 44 | `POST /surveys/{survey}/crosstabs/saved/{id}/execute` | **Read-Only POST:** Executes saved team report in memory. | Path: `survey`, `id`. Returns JSON tables. | Working (200) | **Active Menu:** `/app/forsta/reports` ("Team reports" screen). |
| 45 | `POST /surveys/{survey}/crosstabs/saved/{id}/export/{fmt}` | **Read-Only POST:** Converts saved report to Excel, PPTX, PDF. | Path: `survey`, `id`, `fmt` (`excel\|pdf\|pptx`). | Working (Streams file) | **Active Menu:** `/app/forsta/reports` (Export download button). |
| 46 | `GET /surveys/{survey}/crosstabs/saved` | Lists all saved crosstab reports created by research team. | Path: `survey`. Returns report list. | Working (200, 5 in 261003) | **Active Menu:** `/app/forsta/reports` (Team reports roster). |
| 47 | `GET /surveys/{survey}/crosstabs/configuration` | Banner definitions, stubs, netting rules, and stat-test setup. | Path: `survey`. Returns crosstab config JSON. | Working (200) | **Active Menu:** `/app/forsta/crosstab` ("Cross-tab setup"). |
| 48 | `GET /rh/companies/{company}/crosstab-report-defaults` | Company-wide default banner settings, font styling, and colors. | Path: `company`. Returns corporate defaults. | Working (200) | **Active Menu:** `/app/forsta/crosstab` (Company defaults). |
| 49 | `GET /surveys/{survey}/crosstabs/validate` | Validates crosstab banner and segment logic expressions. | Query: `cond`. Returns syntax verdict. | Working (200) | **Proposed Menu:** *Crosstab Logic Validator* |
| 50 | `GET /surveys/{survey}/crosstabs/targets/{target}/settings` | Display and formatting settings for a specific report target. | Path: `target`. Returns settings object. | Needs target ID | Merged into Crosstab Setup. |
| 51 | `GET /surveys/{survey}/dashboards` | Lists interactive web dashboards attached to the survey. | Path: `survey`. Returns dashboard array. | Working (Empty today) | **Proposed Menu:** *Forsta Dashboard Linkage* |
| 52 | `GET /surveys/{survey}/dashboards/{id}` | Layout and widget configurations of an interactive dashboard. | Path: `survey`, `id`. Returns widget tree. | Needs dashboard ID | **Proposed Menu:** *Forsta Dashboard Linkage* |

---

### Domain 7: Campaigns, Email Invites & Deliverability (12 Operations)

| # | Endpoint & Method | Purpose & Description | Parameters & Usage | Live Account Status | Current CIP Menu / Proposed New Menu |
|---|---|---|---|---|---|
| 53 | `GET /surveys/{survey}/campaigns` | Lists invitation campaigns created for direct email fielding. | Path: `survey`. Returns campaign array. | Working (Empty for panel) | **Proposed Menu G:** *Email Campaign & Dispatch Monitor* |
| 54 | `GET /surveys/{survey}/campaigns/{campaign}` | Configuration, schedule, and sender details of a campaign. | Path: `campaign`. Returns config object. | Needs campaign | **Proposed Menu G:** *Email Campaign & Dispatch Monitor* |
| 55 | `GET /surveys/{survey}/campaigns/{campaign}/invite` | Invitation email HTML template, subject line, sender address. | Path: `campaign`. Returns email template. | Needs campaign | **Proposed Menu G:** *Email Campaign & Dispatch Monitor* |
| 56 | `GET /surveys/{survey}/campaigns/{campaign}/list` | Recipient email distribution list metadata and token counts. | Path: `campaign`. Returns list summary. | Needs campaign | **Proposed Menu G:** *Email Campaign & Dispatch Monitor* |
| 57 | `GET /surveys/{survey}/campaigns/{campaign}/sends` | Historical and scheduled email dispatch batches. | Path: `campaign`. Returns batch list. | Needs campaign | **Proposed Menu G:** *Email Campaign & Dispatch Monitor* |
| 58 | `GET /surveys/{survey}/campaigns/{campaign}/sends/{send}` | Progress and deliverability metrics of an active send batch. | Path: `send`. Returns send status. | Needs send ID | **Proposed Menu G:** *Email Campaign & Dispatch Monitor* |
| 59 | `GET /surveys/{survey}/campaigns/{campaign}/list/{send}` | Recipient-level delivery audit (sent, delivered, opened, clicked). | Path: `send`. Returns recipient status table. | Needs send ID | **Proposed Menu G:** *Email Campaign & Dispatch Monitor* |
| 60 | `GET /surveys/{survey}/campaigns/{listfile}/bounces` | Hard and soft bounce records for an email distribution list. | Path: `listfile`. Returns bounce email array. | Needs list file | **Proposed Menu G:** *Email Campaign & Dispatch Monitor* |
| 61 | `GET /surveys/{survey}/campaigns/{listfile}/blocks` | ISP-level blocks and rate-limiting rejections. | Path: `listfile`. Returns block report. | Needs list file | **Proposed Menu G:** *Email Campaign & Dispatch Monitor* |
| 62 | `GET /surveys/{survey}/campaigns/{listfile}/optouts` | Participant unsubscribe and opt-out requests. | Path: `listfile`. Returns opt-out email records. | Needs list file | **Proposed Menu G:** *Email Campaign & Dispatch Monitor* |
| 63 | `GET /surveys/{survey}/campaigns/{listfile}/spam` | Spam complaints and abuse reports received from ISPs. | Path: `listfile`. Returns spam complaint records. | Needs list file | **Proposed Menu G:** *Email Campaign & Dispatch Monitor* |
| 64 | `POST /bulk/bounced` | **Read-Only POST:** Checks list of emails against bounce registry. | Body: `{emails: [...]}`. Checks bounce status. | Working (Staff only) | **Proposed Menu G:** *Email Campaign & Dispatch Monitor* |

---

### Domain 8: Panels, Samples & Vendor Performance (6 Operations)

| # | Endpoint & Method | Purpose & Description | Parameters & Usage | Live Account Status | Current CIP Menu / Proposed New Menu |
|---|---|---|---|---|---|
| 65 | `GET /surveys/{survey}/panels` | Lists linked proprietary sample communities (Kinesis Panel). | Path: `survey`. Returns linked panel IDs. | Working (Empty for company 86) | **Proposed Menu H:** *Panel Community Management* |
| 66 | `GET /rh/companies/{company}/panels` | Registry of all panel communities owned by the company. | Path: `company`. Returns panel registry. | Working (Empty) | **Proposed Menu H:** *Panel Community Management* |
| 67 | `GET /panels/{panel}/datapoints` | Longitudinal panelist profiling attributes and demographics. | Path: `panel`. Returns attribute schema. | Needs panel | **Proposed Menu H:** *Panel Community Management* |
| 68 | `GET /surveys/{survey}/panels/{panel}/data` | Response tracking data for panelists in this survey. | Path: `survey`, `panel`. Returns records. | Needs panel | **Proposed Menu H:** *Panel Community Management* |
| 69 | `GET /surveys/{survey}/sample/{listId}/links` | Sample vendor survey entry links. | Path: `listId`. | Returns 404 for source 114 | Merged into Sample Sources. |
| 70 | `POST /surveys/{survey}/samplesources/{id}/verify` | **Read-Only POST:** Verifies security signature on sample links. | Path: `id`. Verifies cryptographic signature. | Working (200) | **Proposed Menu:** *Sample Link Integrity Checker* |

---

### Domain 9: Advanced Methodologies: MaxDiff & Conjoint (5 Operations)

| # | Endpoint & Method | Purpose & Description | Parameters & Usage | Live Account Status | Current CIP Menu / Proposed New Menu |
|---|---|---|---|---|---|
| 71 | `GET /surveys/{survey}/dqapi/{label}/mxd` | Exports MaxDiff choice tasks in Sawtooth Software format. | Path: `label`. Returns choice matrix export. | Working (When MXD exists) | **Proposed Menu I:** *MaxDiff & Conjoint Analysis Suite* |
| 72 | `GET /surveys/{survey}/dqapi/{label}/hitrate` | Calculates multinomial logit preference shares and hit rates. | Path: `label`. Returns utility percentages. | Working (When MXD exists) | **Proposed Menu I:** *MaxDiff & Conjoint Analysis Suite* |
| 73 | `GET /surveys/{survey}/dqapi/{label}/tricked` | Exports stacked choice pairs for econometric modeling. | Path: `label`. Returns tricked dataset. | Working (When MXD exists) | **Proposed Menu I:** *MaxDiff & Conjoint Analysis Suite* |
| 74 | `GET /surveys/{survey}/conjoint/status` | Audits design balance and completion across conjoint tasks. | Path: `survey`. Returns task balance JSON. | Working (When CBC exists) | **Proposed Menu I:** *MaxDiff & Conjoint Analysis Suite* |
| 75 | `GET /surveys/{survey}/conjoint/report/{q}` | Extracts part-worth utilities and attribute relative importance. | Path: `q`. Returns utility scorecard. | Working (When CBC exists) | **Proposed Menu I:** *MaxDiff & Conjoint Analysis Suite* |

---

### Domain 10: Qualitative Media & Video Testimonials (3 Operations)

| # | Endpoint & Method | Purpose & Description | Parameters & Usage | Live Account Status | Current CIP Menu / Proposed New Menu |
|---|---|---|---|---|---|
| 76 | `GET /surveys/{survey}/videos` | Lists webcam/mobile qualitative video responses collected. | Path: `survey`. Returns video inventory. | Working (When videos exist) | **Proposed Menu J:** *Qualitative Video Testimonials Vault* |
| 77 | `GET /surveys/{survey}/videos/{video_id}` | Video streaming URL, duration, transcript, and metadata. | Path: `video_id`. Returns video stream object. | Needs video ID | **Proposed Menu J:** *Qualitative Video Testimonials Vault* |
| 78 | `GET /surveys/{survey}/videos/{id}/watermark_videos` | Audits forensic individual watermarked video streams. | Path: `id`. Returns watermarked stream list. | Needs video ID | **Proposed Menu J:** *Qualitative Video Testimonials Vault* |

---

### Domain 11: Multilingual Localization (MLS) (4 Operations)

| # | Endpoint & Method | Purpose & Description | Parameters & Usage | Live Account Status | Current CIP Menu / Proposed New Menu |
|---|---|---|---|---|---|
| 79 | `GET /translation` | Exports questionnaire strings across all translated languages. | Query: `survey`, `lang`. Returns text catalog. | Working (200) | **Proposed Menu K:** *Multi-Market Translation Manager* |
| 80 | `GET /translation/delta` | Identifies newly added or modified strings requiring translation. | Returns untranslated string delta. | Working (200) | **Proposed Menu K:** *Multi-Market Translation Manager* |
| 81 | `GET /translation/delta/reservation` | Inspects translation reservation locks held by translation agencies. | Returns active localization locks. | Working (200) | **Proposed Menu K:** *Multi-Market Translation Manager* |
| 82 | `GET /surveys/{survey}/mls/application/data` | Application-level localized strings for the survey player UI. | Returns UI localized text assets. | Working (200) | **Proposed Menu K:** *Multi-Market Translation Manager* |

---

### Domain 12: Hibernation, Archiving & Compliance (7 Operations)

| # | Endpoint & Method | Purpose & Description | Parameters & Usage | Live Account Status | Current CIP Menu / Proposed New Menu |
|---|---|---|---|---|---|
| 83 | `GET /hibernation/status` | Pre-flight check: returns whether a survey is `restored` or `hibernated`. | Query: `survey`. Returns status string. | Working (200) | **Active Menu:** Checked before every read; skips hibernated waves. |
| 84 | `GET /surveys/{survey}/can-archive` | Checks if a survey meets compliance rules for cold storage. | Path: `survey`. Returns archive eligibility. | Working (200) | **Active Menu:** `/app/fieldwork/:survey` ("In Forsta" card). |
| 85 | `GET /archives/planned` | Lists surveys approaching the 90-day inactivity threshold. | Returns planned hibernation list. | Working (200) | **Active Menu:** `/app/forsta/deletion` (Planned archives table). |
| 86 | `GET /archives/{company}/scheduled` | Lists surveys scheduled for automated archival. | Path: `company`. Returns scheduled archive list. | Working (200) | **Active Menu:** `/app/forsta/deletion` (Scheduled archives table). |
| 87 | `GET /archives/{company}/deleted` | Audits surveys that have completed the 365-day retention lifecycle. | Path: `company`. Returns deleted survey log. | Working (200) | **Active Menu:** `/app/forsta/deletion` (Deleted surveys log). |
| 88 | `GET /archives/{company}/deletion` | Reports surveys approaching the 365-day permanent deletion cliff. | Path: `company`. Returns deletion report. | Working (200) | **Active Menu:** `/app/forsta/deletion` (Deletion report). |
| 89 | `GET /archives/{company}/deletion/data` | Audits participant privacy data erasure requests (GDPR/CCPA). | Path: `company`. Returns erasure compliance log. | Working (200) | **Active Menu:** `/app/forsta/deletion` (Data deletion log). |

---

### Domain 13: System Diagnostics, Users, Security & API Usage (36 Operations)

| # | Endpoint & Method | Purpose & Description | Parameters & Usage | Live Account Status | Current CIP Menu / Proposed New Menu |
|---|---|---|---|---|---|
| 90 | `GET /rh/users/self` | Whoami: authenticates credentials and returns company/user ID. | Returns user object (Mohd Saeed Afri, ID 879). | Working (200) | **Active Menu:** Connection check (`scripts/weekly_forsta.py`). |
| 91 | `GET /rh/companies/{company}/retention` | Corporate data retention rule (e.g., 365 days after archiving). | Path: `company`. Returns retention parameters. | Working (200) | **Active Menu:** `/app/forsta/deletion` (Company retention rule). |
| 92 | `GET /meta` | Forsta's own machine-readable list of all its API endpoints. | Returns endpoint list with methods and schemas. | Working (200) | **Active Menu:** `/app/forsta/account` (API endpoints explorer). |
| 93 | `GET /surveys/{survey}/tasks` | Lists project tasks and milestone sign-offs for the survey. | Path: `survey`. Returns task array. | Working (200) | **Active Menu:** `/app/fieldwork/:survey` (Tasks count). |
| 94 | `GET /surveys/{survey}/tasks/{task_id}` | Detailed status and comments on a specific survey task. | Path: `survey`, `task_id`. Returns task details. | Needs task ID | Merged into Survey Tasks. |
| 95 | `GET /rh/users` | Forsta's user directory for Company 86. | Returns user list with roles and emails. | Working (200) | Not shown: user privacy. |
| 96 | `GET /rh/users/{user}` | Detailed profile of a specific Forsta user account. | Path: `user`. Returns profile object. | Working (200) | Used for supervisor checks. |
| 97 | `GET /rh/users/{user}/audit-log` | Audit log of a specific user's actions inside Forsta. | Path: `user`. Returns event trail. | Working (200) | Survey audit log used instead. |
| 98 | `GET /rh/users/{user}/status` | Lockout and session status of a specific user. | Path: `user`. Returns status flags. | Working (200) | Account security. |
| 99 | `GET /rh/users/{user}/whiteboard` | User scratchpad notes stored in Forsta. | Path: `user`. Returns text content. | Working (200) | Developer scratchpad. |
| 100| `GET /rh/apikeys` | Lists all API keys issued under Company 86. | Returns key IDs and policies. | Working (Returns keys) | Hidden: security rule. |
| 101| `GET /rh/apikeys/{apikey}` | Inspects permissions and IP whitelist of a specific API key. | Path: `apikey`. Returns policy object. | Working (200) | Hidden: security rule. |
| 102| `GET /rh/companies` | Lists corporate accounts and subsidiaries. | Returns company roster. | Working (200) | Finds Company 86 ID. |
| 103| `GET /rh/companies/{company}/preferences` | Default corporate formatting, timezone, and locale settings. | Path: `company`. Returns preference map. | Working (200) | Forsta internal settings. |
| 104| `GET /rh/companies/{company}/groups` | Lists user groups and permission roles in Company 86. | Path: `company`. Returns group hierarchy. | Working (200) | Forsta internal settings. |
| 105| `GET /surveys/{survey}/users` | Users explicitly assigned to a survey project. | Path: `survey`. Returns collaborator list. | Working (200) | Not shown: user privacy. |
| 106| `GET /surveys/{survey}/users/{user}` | Permissions of a specific researcher on a survey project. | Path: `survey`, `user`. Returns permission level. | Working (200) | Not shown: user privacy. |
| 107| `GET /surveys/{survey}/subscribers` | Stakeholders subscribed to automated survey event notifications. | Path: `survey`. Returns subscriber list. | Working (200) | Not shown: user privacy. |
| 108| `POST /globalsearch/emails` | **Read-Only POST:** Search participant email history across surveys. | Body: `{emails: [...]}`. Returns match array. | Working (Staff only) | Not used: no email sample. |
| 109| `POST /globalsearch/evars` | **Read-Only POST:** Search participants matching extra variable criteria. | Body: `{evars: {...}}`. Returns participant array. | Working (Staff only) | Not used: no evars. |
| 110| `GET /rh/usage` | Calculates billable respondent volume and compute units. | Query: `start`, `end`. Returns billing usage. | 403 (Requires Admin) | Restricted on our key. |
| 111| `GET /sysinfo` | Node cluster health and software build versions. | Returns diagnostic telemetry. | 403 (Restricted) | Restricted on our key. |
| 112| `GET /sysinfo/config` | System-wide configuration limits and worker thresholds. | Returns environment config. | 403 (Restricted) | Restricted on our key. |
| 113| `GET /misc/scoreboard` | Lightweight server load scoreboard. | Returns cluster load metrics. | 403 (Restricted) | Restricted on our key. |
| 114| `GET /exceptions/search` | Queries system-level stack traces by exception ID. | Query: `id`. Returns exception traceback. | Needs exception ID | Error diagnostics. |
| 115| `GET /status` | Checks status of an asynchronous background job. | Query: `id`. Returns job status. | Needs job ID | Async job tracking. |
| 116| `GET /status/content` | Streams content of a completed asynchronous background job. | Query: `id`. Returns job result. | Needs job ID | Async job tracking. |
| 117| `GET /hello` | Simple liveness ping. | Returns `{"hello": "world"}`. | Working (200) | Replaced by `rh/users/self`. |
| 118-125| `GET /cati/...` | Telephony server status, saved project parameters. | CATI telephony management. | Not used (Online panel) | CATI call centers only. |

---

## Part 2: CIP Menu & Screen Blueprint (Existing Screens + 6 Proposed New Menus)

To provide total visibility over the Forsta suite, CIP’s interface is organized into **8 existing deployed screens** and **6 proposed new modular menus**:

```
CIP NAVIGATION ARCHITECTURE
├── EXISTING DEPLOYED SCREENS (Nov 7 Deploy)
│   ├── /app/fieldwork               (Cross-Survey Fieldwork Monitor)
│   ├── /app/fieldwork/:survey       (Per-Survey Funnel, Drop-Outs & Terms)
│   └── /app/forsta/*                (Forsta Admin Suite)
│       ├── reports                  (Team Reports & File Exports)
│       ├── check                    (Forsta vs CIP Reconciliation)
│       ├── crosstab                 (Cross-Tab Banners & Defaults)
│       ├── samples                  (Funnel by Sample, OS, Browser, Device)
│       ├── warnings                 (Blocked Sessions, Errors, Launch Checks)
│       ├── files                    (Survey Files & XML Assets)
│       ├── deletion                 (Archive & Deletion 365-Day Schedule)
│       └── account                  (Categories, Endpoints & Unloaded Waves)
│
└── PROPOSED NEW MENUS (Blueprint Below)
    ├── Menu A: /app/forsta/layouts   (Custom Data Layouts & Variable Slices)
    ├── Menu B: /app/forsta/sources   (External Datasources & Lookup Tables)
    ├── Menu C: /app/forsta/choice    (MaxDiff & Conjoint Choice Modeling)
    ├── Menu D: /app/forsta/languages (Multi-Market Translation Manager)
    ├── Menu E: /app/forsta/media     (Qualitative Video Testimonials Vault)
    └── Menu F: /app/forsta/streaming (Live Fieldwork Streaming Ingest Monitor)
```

---

### Detailed Specification of the 6 Proposed New Menus

#### Proposed Menu A: Custom Data Layouts & Variable Slices
- **Target URL:** `/app/forsta/layouts`
- **APIs Consumed:** `GET /surveys/{survey}/layouts`, `GET /surveys/{survey}/layouts/{layout_id}`
- **Who It Is For:** Analysts & Data Engineers.
- **What It Displays:**
  - Lists all custom data layouts saved in Forsta for each survey wave.
  - Displays variable column mappings and projected variable subsets.
  - Allows analysts to trigger filtered microdata exports using predefined layouts without downloading all 395 variables.

#### Proposed Menu B: External Datasources & Reference Tables
- **Target URL:** `/app/forsta/sources`
- **APIs Consumed:** `GET /surveys/{survey}/datasources`, `GET /surveys/{survey}/datasources/{datasource}`, `GET /surveys/{survey}/datasources/{datasource}/data`
- **Who It Is For:** Data Engineers & Methodologists.
- **What It Displays:**
  - External tabular databases attached to surveys (such as store location lists, stock ticker lookups, or US Census regional tables).
  - Schema browser displaying column types and row counts.
  - Verification that survey runtime lookup functions have access to complete reference data.

#### Proposed Menu C: Advanced Choice Modeling (MaxDiff & Conjoint)
- **Target URL:** `/app/forsta/choice`
- **APIs Consumed:** `GET /surveys/{survey}/conjoint/status`, `GET /surveys/{survey}/conjoint/report/{q}`, `GET /surveys/{survey}/dqapi/{label}/hitrate`, `GET /surveys/{survey}/dqapi/{label}/mxd`
- **Who It Is For:** Senior Econometricians, Brand Analysts, and Advisory Clients.
- **What It Displays:**
  - Automated analysis for client ad-hoc studies featuring discrete choice experiments (e.g., pricing trade-offs, package bundles).
  - **Part-Worth Utilities Chart:** Displays relative attribute importance weights (e.g., Brand vs. Price vs. Fit).
  - **Sawtooth Export Link:** One-click download of stacked `.mxd` choice matrices ready for Sawtooth CBC/HB estimation.

#### Proposed Menu D: Multi-Market Translation & Localization Manager
- **Target URL:** `/app/forsta/languages`
- **APIs Consumed:** `GET /translation`, `GET /translation/delta`, `GET /translation/delta/reservation`, `GET /surveys/{survey}/mls/application/data`
- **Who It Is For:** International Research Directors & Localization Project Managers.
- **What It Displays:**
  - Complete language matrix for multi-country survey expansions (UK, Canada, Mexico, Europe, Asia).
  - **Translation Delta Alert:** Lists newly introduced or revised English questions that require translation in other language versions.
  - **Agency Reservation Tracker:** Displays strings currently checked out by localization partners.

#### Proposed Menu E: Qualitative Video Testimonials Vault
- **Target URL:** `/app/forsta/media`
- **APIs Consumed:** `GET /surveys/{survey}/videos`, `GET /surveys/{survey}/videos/{video_id}`, `GET /surveys/{survey}/videos/{video_id}/watermark_videos`
- **Who It Is For:** Qualitative Researchers & Retail Strategists.
- **What It Displays:**
  - Grid of webcam/mobile video responses submitted by verified consumers during unboxing or retail visits.
  - Video player with embedded transcripts, sentiment tags, and respondent demographic badges.
  - **Watermark Compliance:** Verifies forensic watermark IDs burned into concept stimulus videos to prevent leaks of confidential designs.

#### Proposed Menu F: Live Streaming Fieldwork Ingest Monitor
- **Target URL:** `/app/forsta/streaming`
- **APIs Consumed:** `GET /datafeed/{feed}`, `GET /datafeed/{feed}/state`
- **Who It Is For:** System Administrators & Data Operations.
- **What It Displays:**
  - Real-time throughput graph showing completed surveys streaming into CIP minute-by-minute during live Monday fieldwork.
  - Stream synchronization offset, latency metrics, and connection health indicators.

---

## Part 3: Implementation Guide & Code Recipes

### Recipe 1: Calling Any Read-Only GET Endpoint in CIP
```python
from etl.forsta_client import ForstaClient

def fetch_survey_layouts(client: ForstaClient, survey_path: str) -> list[dict]:
    """Reads survey layouts using the standardized read_json client method."""
    endpoint = f"surveys/{survey_path.strip('/')}/layouts"
    return client.read_json(endpoint)
```

### Recipe 2: Calling a Verified Read-Only POST Endpoint
```python
from etl.forsta_client import ForstaClient

def run_custom_crosstab(client: ForstaClient, survey_path: str, banner: list[str], stubs: list[str]) -> dict:
    """Executes a cross-tabulation in memory without writing to Forsta."""
    endpoint = f"surveys/{survey_path.strip('/')}/crosstabs/execute"
    payload = {
        "simplified": True,
        "segments": [{"title": "Total", "cond": "ALL"}, {"title": "Male", "cond": "D1.r1"}],
        "filters": ["qualified"],
        "tables": [f"{s}$" for s in stubs]
    }
    # read_post enforces READ_ONLY_POSTS regex guard before sending
    resp = client.read_post(endpoint, payload)
    return resp.json()
```

### Recipe 3: Registering a New Menu Section in CIP
To add a proposed new menu to the Forsta Admin Suite:
1. Update `frontend/src/forstaSections.ts`:
```typescript
export const SECTIONS: [string, string, string][] = [
  // ... existing sections ...
  ["layouts", "Data layouts", "Saved column layouts and variable slices configured in Forsta."],
  ["choice", "Choice models", "MaxDiff preference shares and Conjoint part-worth utilities."],
  ["languages", "Translations", "Multi-market translations and localization delta tracking."],
];
```
2. Add the corresponding rendering tab in `frontend/src/screens/Forsta.tsx`.
3. In `etl/fieldwork.py`, add the endpoint to `SURVEY_READS` or `COMPANY_READS` to persist the payload into `cip_forsta_record`.
