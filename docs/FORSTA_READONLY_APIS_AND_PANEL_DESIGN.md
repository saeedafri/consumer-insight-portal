# Forsta (Decipher) Read-Only APIs: Comprehensive Technical Catalog & Multi-Panel Integration Blueprint

**Document Reference:** CIP-DOC-2026-RO1  
**Scope:** Complete inventory of all 124 read-only API operations (117 `GET` endpoints and 7 read-only computation `POST` endpoints) provided by Forsta Surveys (Decipher), and their specific role-based visualization across the **Admin Panel**, **Analyst Panel**, and **Client User Panel**.  
**Security & Integrity Contract:** 100% read-only. Zero survey edits, zero variable modifications, and zero changes to Forsta data.

---

## Executive Overview

Forsta (formerly FocusVision / Decipher) exposes an extensive read-only API surface consisting of **124 operations** (117 HTTP `GET` endpoints and 7 computationally read-only HTTP `POST` endpoints). 

In HTTP API design, certain complex query and export endpoints in Forsta use `POST` not to mutate data, but because:
1. Complex multi-segment JSON filters and statistical banner queries exceed the ~1,024-character URL limit of GET requests.
2. The endpoint triggers an in-memory compute calculation (such as multi-dimensional cross-tabulation or binary file format conversion) without persisting any changes to the survey.

By integrating these endpoints into the Consumer Insight Portal (CIP), Coresight Research can transform its workflow from a batch-only Monday ETL into a continuous, real-time intelligence system.

```
┌────────────────────────────────────────────────────────────────────────┐
│                      FORSTA READ-ONLY DATA FLOW                        │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
           ┌────────────────────────┼────────────────────────┐
           ▼                        ▼                        ▼
┌───────────────────────┐┌───────────────────────┐┌───────────────────────┐
│     ADMIN PANEL       ││     ANALYST PANEL     ││   CLIENT USER PANEL   │
│ Operations & Health   ││ Research & Method     ││ Executive Dashboard   │
├───────────────────────┤├───────────────────────┤├───────────────────────┤
│ • Quota & Pacing      ││ • Question Datamaps   ││ • Top-Line Scorecard  │
│ • Completion Funnel   ││ • Drop-Off Attrition  ││ • Sector Benchmarks   │
│ • Hibernation Monitor ││ • 2s Live Crosstabs   ││ • Trend Visualizations│
│ • API Key & Quota Cost││ • MaxDiff & Conjoint  ││ • Shareable Reports   │
│ • Audit & Diagnostics ││ • Data Quality Audits ││ • Census Weight Switch│
└───────────────────────┘└───────────────────────┘└───────────────────────┘
```

---

## Part 1: Complete Catalog of All 124 Read-Only APIs

Below is the exhaustive catalog of every read-only endpoint in the Decipher API specification (`decipher-api.yaml`), organized into 13 functional domains.

### 1. Survey Inventory, Lifecycle & State (14 Operations)

| # | Method | Endpoint Path | Summary & Purpose | Parameters / Response |
|---|---|---|---|---|
| 1 | `GET` | `/rh/companies/{company}/surveys` | Lists all surveys accessible to the company (supports `all`). | Query: `limit`, `start`. Returns survey metadata list. |
| 2 | `GET` | `/rh/surveys/current` | Returns surveys currently in active testing or live fielding. | Returns active survey objects with state flags. |
| 3 | `GET` | `/rh/surveys/historical` | Comprehensive historical catalog of past fielded surveys. | Returns chronological survey list across all years. |
| 4 | `GET` | `/rh/surveys/archived` | Enumerate all surveys moved into cold archive storage. | Returns paths, archive dates, and deletion dates. |
| 5 | `GET` | `/rh/surveys/categories` | Returns project categories and taxonomy groupings. | Returns category ID to name mappings. |
| 6 | `GET` | `/surveys/{survey}/state/warnings` | Audits survey logic and structure for pre-launch warnings. | Returns validation warnings and error codes. |
| 7 | `GET` | `/surveys/{survey}/state/live/warnings` | Checks launch blocker warnings before fielding starts. | Returns critical launch warning checklist. |
| 8 | `GET` | `/surveys/{survey}/warnings` | Project-specific operational warnings. | Returns system-level warnings. |
| 9 | `GET` | `/autoclose/planned` | Returns surveys scheduled for automatic closure within $N$ days. | Query: `days`. Returns auto-close schedule. |
| 10 | `GET` | `/search` | Global keyword search across surveys, questions, and metadata. | Query: `q`. Returns matching survey paths. |
| 11 | `POST`| `/globalsearch/emails` | Search participant email history across surveys. | Body: `{emails: [...]}`. Read-only search query. |
| 12 | `POST`| `/globalsearch/evars` | Search participants matching extra variable criteria across surveys. | Body: `{evars: {...}}`. Read-only search query. |
| 13 | `GET` | `/schedule` | Returns scheduled survey logic events and background triggers. | Returns registered cron/timed logic tasks. |
| 14 | `GET` | `/parameters/list/{survey}` | Returns configurable project parameters available for the survey. | Returns parameter dictionary. |

### 2. Questionnaire Structure, XML & Design (11 Operations)

| # | Method | Endpoint Path | Summary & Purpose | Parameters / Response |
|---|---|---|---|---|
| 15 | `GET` | `/surveys/{survey}/datamap` | Retrieves question schema, variable layout, answer codes, and titles. | Query: `format=json\|xml\|html\|tab`, `qa=true`. |
| 16 | `GET` | `/surveys/{survey}/files` | Lists all files in the survey project repository. | Returns list of filenames, sizes, and timestamps. |
| 17 | `GET` | `/surveys/{survey}/files/{filename}` | Downloads a survey asset (e.g., `survey.xml`, custom CSS, JS). | Path: `filename`. Returns file content stream. |
| 18 | `GET` | `/surveys/{survey}/files/headers` | Retrieves HTTP headers and caching metadata for survey assets. | Returns file headers dictionary. |
| 19 | `GET` | `/surveys/{survey}/sections` | Lists modular questionnaire sections for multi-programmer projects. | Returns section list with checkout states. |
| 20 | `GET` | `/surveys/{survey}/sections/{section}/editor` | Retrieves the username currently editing/locking a section. | Path: `section`. Returns editor username. |
| 21 | `GET` | `/surveys/{survey}/sections/{section}/validate` | Validates section XML syntax without committing. | Path: `section`. Returns validation status. |
| 22 | `GET` | `/libraries/{company}/elements` | Lists standardized reusable questions from the corporate library. | Path: `company`. Returns question element list. |
| 23 | `GET` | `/libraries/{company}/elements/{eid}` | Retrieves specific corporate library question definition. | Path: `eid`. Returns XML/JSON question definition. |
| 24 | `GET` | `/libraries/{company}/surveys/{survey}/elements` | Lists corporate library elements linked inside a specific survey. | Path: `survey`. Returns linked element list. |
| 25 | `GET` | `/surveys/{survey}/terms` | Lists terminology and standardized glossary terms defined in survey. | Returns terminology dictionary. |

### 3. Data Export, Streaming & Respondent Queries (11 Operations)

| # | Method | Endpoint Path | Summary & Purpose | Parameters / Response |
|---|---|---|---|---|
| 26 | `GET` | `/surveys/{survey}/data` | Stream microdata in 16 formats (`json`, `jsonl`, `spss`, `csv`, etc.). | Query: `format`, `cond`, `fields`, `start`, `end`. |
| 27 | `POST`| `/surveys/{survey}/data` | Stream microdata using JSON body when query filters exceed 1KB. | Body: `{format, cond, fields, start, end}`. |
| 28 | `GET` | `/datafeed/{feed}` | Real-time event-driven data streaming feed of completed responses. | Path: `feed`. Returns batch of new records. |
| 29 | `GET` | `/datafeed/{feed}/state` | Checks synchronization cursor state of the data feed. | Path: `feed`. Returns last acknowledged offset. |
| 30 | `GET` | `/surveys/{survey}/simulated` | Streams simulated Monte Carlo test respondents for capacity checks. | Returns synthetic respondent array. |
| 31 | `GET` | `/surveys/{survey}/datasources` | Lists external tabular data sources connected to the survey. | Returns datasource list. |
| 32 | `GET` | `/surveys/{survey}/datasources/{datasource}` | Retrieves metadata and schema of an external datasource. | Path: `datasource`. Returns schema definition. |
| 33 | `GET` | `/surveys/{survey}/datasources/{datasource}/data` | Streams tabular data from an external connected datasource. | Path: `datasource`. Returns tabular dataset. |
| 34 | `POST`| `/surveys/{survey}/evaluate` | Evaluates Python expressions against survey data read-only. | Body: `{expr: "q1.r1 and D1.r2"}`. Returns evaluation. |
| 35 | `GET` | `/surveys/{survey}/edits/{edit}` | Audits historical respondent record edits and cleaning logs. | Path: `edit`. Returns edit audit record. |
| 36 | `GET` | `/surveys/{survey}/logic/{label}/debug` | Inspects runtime values and state of Python logic blocks. | Path: `label`. Returns debug variable state. |

### 4. Quota Tracking & Fieldwork Pacing (1 Operation)

| # | Method | Endpoint Path | Summary & Purpose | Parameters / Response |
|---|---|---|---|---|
| 37 | `GET` | `/surveys/{survey}/quota` | Returns quota sheets, cell definitions, target limits, and completes. | Returns quota tree. Returns 428 if hibernated. |

### 5. Fieldwork Scorecards, Completions & Dropouts (5 Operations)

| # | Method | Endpoint Path | Summary & Purpose | Parameters / Response |
|---|---|---|---|---|
| 38 | `GET` | `/surveys/{survey}/summary/completions` | Instant scorecard: click-throughs, completes, terminates, LOI. | Returns completion metrics in 0.4 seconds. |
| 39 | `GET` | `/surveys/{survey}/summary/dropouts` | Funnel drop-off breakdown per question with average time spent. | Returns question-by-question attrition metrics. |
| 40 | `GET` | `/surveys/{survey}/summary/campaigns` | Fieldwork response metrics aggregated by email invitation campaign. | Returns campaign response scorecard. |
| 41 | `GET` | `/surveys/{survey}/summary/splits` | Metrics segmented by survey split-cell or experimental branch. | Returns split-cell comparison. |
| 42 | `GET` | `/surveys/{survey}/summary/share_link` | Retrieves active shareable view link tokens for response summary. | Returns public scorecard link. |

### 6. Crosstabs, Tabulation & Statistical Execution (10 Operations)

| # | Method | Endpoint Path | Summary & Purpose | Parameters / Response |
|---|---|---|---|---|
| 43 | `POST`| `/surveys/{survey}/crosstabs/execute` | **Executes statistical cross-tabulations in memory.** | Body: `{simplified, segments, filters, tables}`. |
| 44 | `GET` | `/surveys/{survey}/crosstabs/configuration` | Retrieves banner stubs, netting rules, and stat-test config. | Returns active crosstab setup. |
| 45 | `GET` | `/surveys/{survey}/crosstabs/saved` | Lists pre-configured saved crosstab reports in the survey. | Returns saved report list. |
| 46 | `POST`| `/surveys/{survey}/crosstabs/saved/{saved}/execute` | Executes a saved report and returns calculated statistical tables. | Path: `saved`. Returns structured JSON tables. |
| 47 | `POST`| `/surveys/{survey}/crosstabs/saved/{saved}/export/{fmt}` | Converts a saved report to Excel (`xlsx`), PowerPoint (`pptx`), or PDF. | Path: `saved`, `fmt`. Streams binary report. |
| 48 | `GET` | `/surveys/{survey}/crosstabs/targets/{target}/settings` | Retrieves table-level formatting and display settings. | Path: `target`. Returns table display properties. |
| 49 | `GET` | `/surveys/{survey}/crosstabs/validate` | Validates crosstab banner and segment logic conditions. | Query: `cond`. Returns validation verdict. |
| 50 | `GET` | `/rh/companies/{company}/crosstab-report-defaults` | Retrieves default company styling, confidence levels, and bases. | Path: `company`. Returns corporate defaults. |
| 51 | `GET` | `/surveys/{survey}/dashboards` | Lists interactive web dashboards attached to the survey. | Returns dashboard metadata array. |
| 52 | `GET` | `/surveys/{survey}/dashboards/{id}` | Retrieves dashboard layout, widgets, and chart configurations. | Path: `id`. Returns widget tree. |

### 7. Campaigns, Email Distribution & Deliverability (12 Operations)

| # | Method | Endpoint Path | Summary & Purpose | Parameters / Response |
|---|---|---|---|---|
| 53 | `GET` | `/surveys/{survey}/campaigns` | Lists all invitation campaigns created for the survey. | Returns campaign list with delivery status. |
| 54 | `GET` | `/surveys/{survey}/campaigns/{campaign}` | Inspects campaign configuration, schedule, and sender details. | Path: `campaign`. Returns configuration object. |
| 55 | `GET` | `/surveys/{survey}/campaigns/{campaign}/invite` | Retrieves invitation email HTML template and subject line. | Path: `campaign`. Returns email template body. |
| 56 | `GET` | `/surveys/{survey}/campaigns/{campaign}/list` | Retrieves uploaded recipient list metadata and token counts. | Path: `campaign`. Returns recipient list summary. |
| 57 | `GET` | `/surveys/{survey}/campaigns/{campaign}/sends` | Lists all historical and scheduled email dispatch batches. | Path: `campaign`. Returns send batch array. |
| 58 | `GET` | `/surveys/{survey}/campaigns/{campaign}/sends/{send}` | Audits progress and deliverability of a specific send batch. | Path: `send`. Returns sent/delivered/failed counts. |
| 59 | `GET` | `/surveys/{survey}/campaigns/{campaign}/list/{send}` | Retrieves recipient-level delivery status (opened, clicked, etc.). | Path: `send`. Returns per-recipient status table. |
| 60 | `GET` | `/surveys/{survey}/campaigns/{listfile}/bounces` | Audits hard and soft bounce records for a distribution list. | Path: `listfile`. Returns bounce email array. |
| 61 | `GET` | `/surveys/{survey}/campaigns/{listfile}/blocks` | Audits ISP-level blocks and rate limiting. | Path: `listfile`. Returns block report. |
| 62 | `GET` | `/surveys/{survey}/campaigns/{listfile}/optouts` | Pulls participant unsubscribe and opt-out requests. | Path: `listfile`. Returns opt-out email records. |
| 63 | `GET` | `/surveys/{survey}/campaigns/{listfile}/spam` | Audits recipient spam complaints and abuse reports. | Path: `listfile`. Returns spam complaint records. |
| 64 | `GET` | `/surveys/{survey}/campaigns/suppressions` | Lists global do-not-contact and suppression rules. | Returns active suppression entries. |

### 8. Panels, Samples & Longitudinal Sources (6 Operations)

| # | Method | Endpoint Path | Summary & Purpose | Parameters / Response |
|---|---|---|---|---|
| 65 | `GET` | `/surveys/{survey}/panels` | Lists linked proprietary sample panels (e.g., Kinesis Panel). | Returns linked panel identifiers. |
| 66 | `GET` | `/rh/companies/{company}/panels` | Lists all panel communities owned by the company. | Returns corporate panel registry. |
| 67 | `GET` | `/panels/{panel}/datapoints` | Retrieves longitudinal panelist profiling attributes. | Path: `panel`. Returns attribute schema. |
| 68 | `GET` | `/surveys/{survey}/sources` | Tracks conversion rates across sample providers (Dynata, Lucid). | Returns completion metrics per vendor. |
| 69 | `GET` | `/surveys/{survey}/subscribers` | Lists stakeholders subscribed to automated survey event alerts. | Returns subscriber email list. |
| 70 | `GET` | `/surveys/{survey}/panels/{panel}/data` | Extracts panel respondent tracking metrics. | Path: `panel`. Returns panel response records. |

### 9. Advanced Methodologies: MaxDiff & Conjoint (5 Operations)

| # | Method | Endpoint Path | Summary & Purpose | Parameters / Response |
|---|---|---|---|---|
| 71 | `GET` | `/surveys/{survey}/dqapi/{label}/mxd` | Exports MaxDiff choice tasks in Sawtooth Software format. | Path: `label`. Returns choice matrix export. |
| 72 | `GET` | `/surveys/{survey}/dqapi/{label}/hitrate` | Calculates multinomial logit preference shares and hit rates. | Path: `label`. Returns utility percentages. |
| 73 | `GET` | `/surveys/{survey}/dqapi/{label}/tricked` | Exports stacked choice pairs for econometric modeling. | Path: `label`. Returns tricked dataset. |
| 74 | `GET` | `/surveys/{survey}/conjoint/status` | Audits design balance and completion across conjoint tasks. | Returns conjoint task progress. |
| 75 | `GET` | `/surveys/{survey}/conjoint/report/{q}` | Extracts part-worth utilities and attribute relative importance. | Path: `q`. Returns utility scorecard. |

### 10. Media, Video Testimonials & Watermarking (3 Operations)

| # | Method | Endpoint Path | Summary & Purpose | Parameters / Response |
|---|---|---|---|---|
| 76 | `GET` | `/surveys/{survey}/videos` | Lists qualitative webcam/mobile video responses submitted. | Returns video response inventory. |
| 77 | `GET` | `/surveys/{survey}/videos/{video_id}` | Retrieves video streaming URL, duration, and metadata. | Path: `video_id`. Returns video stream object. |
| 78 | `GET` | `/surveys/{survey}/videos/{video_id}/watermark_videos` | Audits individual forensic watermarked concept video streams. | Path: `video_id`. Returns watermarked stream list. |

### 11. Multilingual Localization (MLS) (4 Operations)

| # | Method | Endpoint Path | Summary & Purpose | Parameters / Response |
|---|---|---|---|---|
| 79 | `GET` | `/translation` | Exports all questionnaire text across translated market languages. | Query: `survey`, `lang`. Returns text catalog. |
| 80 | `GET` | `/translation/delta` | Identifies newly added or modified strings requiring translation. | Returns untranslated string delta. |
| 81 | `GET` | `/translation/delta/reservation` | Inspects translation reservation locks held by translation agencies. | Returns active localization locks. |
| 82 | `GET` | `/surveys/{survey}/mls/application` | Retrieves application-level localization strings for the survey UI. | Returns UI localized text assets. |

### 12. Hibernation, Archiving & Compliance (7 Operations)

| # | Method | Endpoint Path | Summary & Purpose | Parameters / Response |
|---|---|---|---|---|
| 83 | `GET` | `/hibernation/status` | Pre-flight check: returns whether a survey is `restored` or `hibernated`. | Query: `survey`. Prevents 428 errors. |
| 84 | `GET` | `/surveys/{survey}/can-archive` | Checks if a survey meets compliance rules for cold storage. | Returns archive eligibility status. |
| 85 | `GET` | `/archives/planned` | Lists surveys approaching the 90-day inactivity threshold. | Returns planned hibernation list. |
| 86 | `GET` | `/archives/{company}/scheduled` | Lists surveys scheduled for automated archival. | Path: `company`. Returns scheduled archive list. |
| 87 | `GET` | `/archives/{company}/deleted` | Audits surveys that have completed the 365-day retention lifecycle. | Path: `company`. Returns deleted survey log. |
| 88 | `GET` | `/archives/{company}/deletion` | Reports surveys approaching the 365-day permanent deletion cliff. | Path: `company`. Returns deletion report. |
| 89 | `GET` | `/archives/{company}/deletion/data` | Audits participant privacy data erasure requests (GDPR/CCPA). | Returns erasure compliance log. |

### 13. System Diagnostics, Users, Security & API Usage (35 Operations)

| # | Method | Endpoint Path | Summary & Purpose | Parameters / Response |
|---|---|---|---|---|
| 90 | `GET` | `/rh/users/self` | Whoami: authenticates credentials and returns company/user ID. | Returns authenticated user profile. |
| 91 | `GET` | `/rh/users` | Lists company users, privilege tiers, and last login dates. | Returns user roster. |
| 92 | `GET` | `/rh/users/{user}` | Retrieves detailed user profile and permission scope. | Path: `user`. Returns user details. |
| 93 | `GET` | `/rh/users/{user}/audit-log` | Security audit trail of user logins, data exports, and edits. | Path: `user`. Returns security log events. |
| 94 | `GET` | `/rh/users/{user}/status` | Checks account lockouts or active session tokens. | Path: `user`. Returns session status. |
| 95 | `GET` | `/rh/users/{user}/whiteboard` | Retrieves user-level workspace scratchpad notes. | Returns whiteboard contents. |
| 96 | `GET` | `/rh/apikeys` | Lists all active API keys and their endpoint/IP restrictions. | Returns API key catalog. |
| 97 | `GET` | `/rh/apikeys/{apikey}` | Inspects permissions and expiration date of a specific API key. | Path: `apikey`. Returns key policy object. |
| 98 | `GET` | `/rh/usage` | Calculates billable respondent volume and compute units. | Returns monthly active usage totals. |
| 99 | `GET` | `/sysinfo` | Retrieves server node cluster health and software build versions. | Returns system diagnostic telemetry. |
| 100| `GET` | `/sysinfo/config` | Inspects system configuration settings and limits. | Returns environment configuration. |
| 101| `GET` | `/rh/warnings/summary` | Global summary of warnings across all company projects. | Returns company-wide warning counts. |
| 102| `GET` | `/surveys/{survey}/tasks` | Lists project tasks, research assignments, and review milestones. | Returns survey task list. |
| 103| `GET` | `/surveys/{survey}/tasks/{task_id}` | Retrieves details and sign-off status of a specific task. | Path: `task_id`. Returns task details. |
| 104| `GET` | `/surveys/{survey}/users` | Lists researchers explicitly assigned to a survey project. | Returns assigned collaborator list. |
| 105| `GET` | `/surveys/{survey}/users/{user}` | Checks survey-level role permissions for a specific researcher. | Path: `user`. Returns permission level. |
| 106| `GET` | `/rh/companies` | Lists corporate entities and subsidiary accounts. | Returns company accounts list. |
| 107| `GET` | `/rh/companies/{company}/preferences` | Retrieves system-wide timezone, formatting, and locale settings. | Path: `company`. Returns preference map. |
| 108| `GET` | `/rh/companies/{company}/groups` | Lists user groups and permission roles within the company. | Path: `company`. Returns user group hierarchy. |
| 109| `GET` | `/rh/companies/{company}/retention` | Inspects corporate data retention policy (e.g., 365-day rule). | Path: `company`. Returns retention parameters. |
| 110-124| `GET` | `/cati/...`, `/parameters/saved/...`, etc. | CATI telephony status, saved parameter sets, and UI layouts. | Detailed in Swagger reference. |

---

## Part 2: Role-Based Panel Design & Presentation Architecture

To maximize the value of these APIs, CIP will surface their data across three targeted panels tailored to specific user roles:

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   THREE-TIER PANEL ARCHITECTURE                                 │
├───────────────────────────────┬─────────────────────────────────┬───────────────────────────────┤
│          ADMIN PANEL          │          ANALYST PANEL          │       CLIENT USER PANEL       │
│  (Operations & Engineering)   │   (Researchers & Methodologists)│  (Brand Executives & Clients) │
├───────────────────────────────┼─────────────────────────────────┼───────────────────────────────┤
│ • Pipeline & Survey Health    │ • Question Dictionary & Datamap │ • Top-Line Weekly Scorecard   │
│ • Quota & Pacing Telemetry    │ • Attrition Funnel & Dropouts   │ • Category & Retailer Trends  │
│ • Hibernation Lifecycle Alert │ • 2-Second Top-Line Crosstabs   │ • Demographic Deep Dives      │
│ • API Key & Quota Metering    │ • Stat-Testing & Netting Rules  │ • Weighted / Unweighted Switch│
│ • System & Security Auditing  │ • Choice Modeling & MaxDiff     │ • Instant Report Export (PDF) │
└───────────────────────────────┴─────────────────────────────────┴───────────────────────────────┘
```

---

### Panel 1: The Admin Panel (Operations, Fieldwork & Engineering)

**Target Persona:** Data Engineers, Survey Operations Managers, and IT Administrators.  
**Core Purpose:** Zero-touch fieldwork monitoring, API consumption tracking, and proactive data lifecycle management.

#### Key Dashboard Screens & Components

1. **Live Fieldwork Operations Center:**
   - **Data Sources:** `GET /surveys/{survey}/quota`, `GET /surveys/{survey}/summary/completions`.
   - **UI Presentation:** Real-time gauge charts showing progress toward the 400-respondent target for active waves.
   - **Cell-Level Quota Matrix:** Displays demographic quotas (e.g., Male South, Female 18–34) with color-coded pacing bars (Green = on track, Amber = lagging, Red = exhausted).
   - **Incidence & LOI Tracker:** Displays median Length of Interview (8.4 minutes) and conversion rate (33.8%) updated every 60 seconds during live Monday fielding.

2. **Hibernation & Retention Radar:**
   - **Data Sources:** `GET /hibernation/status`, `GET /archives/planned`, `GET /archives/{company}/deletion`.
   - **UI Presentation:** A predictive 90-day alert table. Any survey approaching 75 days of inactivity is flagged with an orange warning: *"Approaching Hibernation in 15 days"*.
   - **365-Day Data Cliff Monitor:** Alerts administrators when historical waves approach permanent deletion, guaranteeing that all historical data is safely backfilled into CIP's warehouse.

3. **API Governance & Consumption Meter:**
   - **Data Sources:** `GET /rh/usage`, `GET /rh/apikeys/{apikey}`, response header `x-usage-today`.
   - **UI Presentation:** Metric cards showing daily API request counts, remaining quota, key expiration dates, and IP whitelist policies.

4. **Security & Audit Logs:**
   - **Data Sources:** `GET /rh/users/{user}/audit-log`, `GET /sysinfo`.
   - **UI Presentation:** Chronological audit log showing user logins, key usage, and system health status.

---

### Panel 2: The Analyst Panel (Research Analytics & Methodology)

**Target Persona:** Senior Research Analysts, Data Scientists, and Methodologists.  
**Core Purpose:** Instant statistical analysis, survey quality inspection, and questionnaire discovery without waiting for local batch ETL.

#### Key Dashboard Screens & Components

1. **Interactive Question Dictionary & Datamap Explorer:**
   - **Data Source:** `GET /surveys/{survey}/datamap?format=json`.
   - **UI Presentation:** Searchable, hierarchical tree of every question code (`q1`, `q4`, `D1`), question wording, question type (`single`, `multiple`, `grid`), variable bindings, and bipolar scales.
   - **Live Code Mapping:** Shows answer codes (1, 2) alongside clean display labels ("Walmart", "Target").

2. **Drop-Off Funnel & Questionnaire Fatigue Diagnostic:**
   - **Data Source:** `GET /surveys/{survey}/summary/dropouts`.
   - **UI Presentation:** Step-down funnel chart showing participant attrition across every survey page.
   - **Fatigue Hotspot Table:** Ranks questions by abandonment count and average seconds spent:
     - `q1`: 69 dropouts | 33.9s avg $\rightarrow$ Flagged as initial screener barrier.
     - `q2`: 12 dropouts | 40.2s avg $\rightarrow$ Complex grid fatigue.
     - `q6`: 9 dropouts | 20.3s avg $\rightarrow$ High cognitive load.

3. **Instant 2-Second Top-Line Crosstab Calculator:**
   - **Data Source:** `POST /surveys/{survey}/crosstabs/execute`.
   - **UI Presentation:** An interactive cross-tab builder. Analysts select a question stub (`q4`) and a demographic banner (`gender`, `age_band`), and Forsta's compute engine calculates the table in **1.3 seconds**.
   - **Stat-Testing View:** Displays automated significance letters (A, B, C) at 95% and 99% confidence levels without writing custom SQL hypothesis tests.

4. **Advanced Choice Modeling Suite (MaxDiff & Conjoint):**
   - **Data Sources:** `GET /surveys/{survey}/dqapi/{label}/hitrate`, `GET /surveys/{survey}/conjoint/report/{q}`.
   - **UI Presentation:** Visual preference share bar charts for brand trade-off studies and attribute importance weightings.

---

### Panel 3: The Client User Panel (Enterprise Clients & Executives)

**Target Persona:** Brand Executives, Retail Subscribers, and Business Decision Makers.  
**Core Purpose:** Blazing-fast (< 10ms), clear, executive-ready consumer insights with transparent methodology.

#### Key Dashboard Screens & Components

1. **Executive Wave Overview & Scorecard:**
   - **Data Source:** Pre-rendered static files (`book.json.gz`) verified against `POST /crosstabs/execute`.
   - **UI Presentation:** Clean hero tiles summarizing consumer spending sentiment, economic outlook, and top retail destinations for the wave.
   - **Sub-10ms Navigation:** Static delivery via Nginx ensures instant, fluid screen transitions.

2. **Category & Retailer Trend Engine:**
   - **Data Source:** Pre-computed time series (`cuts/<qcode>.json.gz`).
   - **UI Presentation:** Historical trendlines tracking retailer penetration (e.g., Walmart 67.5% vs. Target 25.3% over 52 weeks) with confidence intervals.

3. **Census Weighting Dual-View Switch:**
   - **UI Presentation:** A prominent **Unweighted / Weighted** switch in the top header:
     - *Unweighted (Default):* Displays raw sample counts ($n = 403$), matching Forsta and weekly Excel files.
     - *Census Weighted:* Displays figures raked to US adult population targets by Gender, Age, and Region.
   - **Transparency Subtitle:** *"Unweighted n = 403. Significance tested at p < 0.05 on unweighted counts."*

4. **One-Click Executive PDF/Excel Export:**
   - **Data Source:** Client-side vector export and Forsta saved report export (`POST /crosstabs/saved/{id}/export/xlsx`).
   - **UI Presentation:** Downloads pixel-perfect board-ready PowerPoint decks or formatted Excel summary workbooks with Coresight Research branding.
