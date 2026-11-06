# Forsta (Decipher) API: Comprehensive Platform & Endpoint Guide

**Document Purpose:** Complete technical catalog and strategic assessment of the Forsta (Decipher) API suite for Coresight Research as a premium client.  
**Audience:** Business leadership, research analytics, and engineering teams.  
**Current Date:** November 2026.  
**Primary Sources:** Official Decipher REST API OpenAPI specification (`decipher-api.yaml`, 175 endpoints, 227 operations), Forsta Technical Support communications (Tickets #1075439, #1079025, #1079724), and live implementation in `etl/forsta_client.py` / `etl/forsta_etl.py`.

---

## Executive Summary

1. **Brand & Platform Identification ("Fourstar"):**
   "Fourstar" refers to **Forsta** (formerly **FocusVision** and **Decipher**, which merged with **Confirmit** and acquired **Dapresy** under Press Ganey). Coresight Research's weekly consumer tracker (`CSI-US`) and ad-hoc/annual surveys are hosted and fielded on **Forsta Surveys (Decipher)** on the private cloud cluster (`https://se1.decipherinc.com`).
2. **Platform Scale:**
   The Decipher REST API provides **175 endpoints** across **227 operations** divided into **11 major functional domains**—spanning survey programming, live fielding management, data export/streaming, statistical crosstabs execution, rim weighting (raking), automated email campaigns, panel tracking, and advanced conjoint/MaxDiff modeling.
3. **Current Utilization (What We Are Using):**
   In this codebase, we use **5 endpoints** (~2.8% of the API footprint), strictly via **read-only `GET` calls**:
   - `GET /api/v1/rh/companies/all/surveys` (survey discovery and registration)
   - `GET /api/v1/surveys/{path}/datamap?format=json` (questionnaire schema and labels)
   - `GET /api/v1/surveys/{path}/data?format=json` (streamed respondent microdata)
   - `GET /api/v1/surveys/{path}/quota` (fieldwork progress tracking & hibernation detection)
   - `GET /api/v1/rh/users/self` (authentication and health verification)
4. **Immediate Strategic Opportunity (What We Are NOT Using):**
   The most critical unused endpoint is **`POST /api/v1/surveys/{survey}/unarchive`**. As confirmed by Forsta Support Agent Bee Lee in Ticket #1079724, this endpoint immediately resolves the HTTP 428 error ("Precondition Required: survey needs to be reactivated") on **43 hibernated weekly tracker waves and 8 annual/ad-hoc studies**, enabling a 100% automated backfill of historical data without manual portal clicking.

---

## Part 1: The Forsta Product & API Ecosystem

Forsta operates an enterprise-grade Experience and Market Research platform comprising six primary modules:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        FORSTA PLATFORM ECOSYSTEM                       │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
    ┌───────────────────────────────┼────────────────────────────────┐
    ▼                               ▼                                ▼
┌───────────────────────┐   ┌───────────────────────┐   ┌────────────────────────┐
│ Forsta Surveys        │   │ Forsta Plus           │   │ Forsta Visualizations  │
│ (Decipher Engine)     │   │ (Confirmit Horizons)  │   │ (Dapresy BI Engine)    │
│ • Complex Questionnaires│   │ • Multi-mode (CATI,   │   │ • Dynamic Dashboards   │
│ • Quota Management    │   │   CAPI, Web, SMS)     │   │ • Infographic Reports  │
│ • Raw Data Export     │   │ • Hierarchy Management│   │ • Stakeholder Portals  │
│ • Real-time Crosstabs │   │ • Enterprise Feedback │   │ • Real-time Charts     │
└───────────────────────┘   └───────────────────────┘   └────────────────────────┘
    │                               │                                │
    ┌───────────────────────────────┼────────────────────────────────┐
    ▼                               ▼                                ▼
┌───────────────────────┐   ┌───────────────────────┐   ┌────────────────────────┐
│ Forsta Video / Qual   │   │ Forsta Panels         │   │ Forsta Genius          │
│ (InterVu & Revelation)│   │ (Kinesis & Community) │   │ (AI Text & NLP)        │
│ • Digital Focus Groups│   │ • Panel Recruitment   │   │ • Sentiment Analysis   │
│ • Video Testimonials  │   │ • Sample Profiling    │   │ • Verbatim Theme Coder │
│ • Forensic Watermarks │   │ • Reward & Points API │   │ • Entity Extraction    │
└───────────────────────┘   └───────────────────────┘   └────────────────────────┘
```

The REST API powering `https://se1.decipherinc.com` is the **Forsta Surveys (Decipher) REST API v1.0**.

---

## Part 2: Complete Decipher REST API Catalog (All 11 Domains)

Every endpoint in the official OpenAPI specification (`decipher-api.yaml`) is categorized below into its functional domain.

### 1. Survey Management & Lifecycle (27 Operations)
Controls survey provisioning, project discovery, status transitions, and automated closing rules.

| HTTP Method | Endpoint Path | Operation ID | Purpose & Features |
|---|---|---|---|
| `GET` | `/rh/companies/{company}/surveys` | `getSurveys` | List all surveys belonging to a company (supports `all`). |
| `POST` | `/rh/companies/{company}/surveys` | `createSurvey` | Provision a new survey project programmatically. |
| `GET` | `/rh/surveys/current` | `getCurrentSurveys` | List surveys currently in testing or live fielding. |
| `GET` | `/rh/surveys/historical` | `getHistoricalSurveys` | Retrieve historical surveys list across all time. |
| `GET` | `/rh/surveys/archived` | `getArchivedSurveys` | Retrieve list of archived/cold surveys. |
| `POST` | `/surveys/{survey}/state/live` | `setSurveyStateLive` | Launch survey to live data collection. |
| `POST` | `/surveys/{survey}/state/close` | `setSurveyStateClose` | Terminate data collection and close survey fielding. |
| `GET` | `/surveys/{survey}/state/warnings`| `getSurveyStateWarnings`| Validate survey integrity and check pre-launch warnings. |
| `GET` | `/surveys/{survey}/state/live/warnings` | `getSurveyStateLiveWarnings` | Detailed launch blocker warnings. |
| `GET` | `/autoclose/planned` | `getAutoclosePlanned` | List surveys scheduled for automatic termination. |
| `GET` | `/rh/surveys/categories` | `getCategories` | List project taxonomy and categories. |
| `GET` | `/search` | `getSearch` | Global keyword search across surveys, questions, and metadata. |

### 2. Survey Design, Files & Section Editing (24 Operations)
Provides full read/write access to the survey source definition (`survey.xml`), static assets, and collaborative section editing.

| HTTP Method | Endpoint Path | Operation ID | Purpose & Features |
|---|---|---|---|
| `GET` | `/surveys/{survey}/files` | `getSurveyFiles` | List all files in the survey directory (XML, JS, CSS, images). |
| `GET` | `/surveys/{survey}/files/{filename}` | `getSurveyFile` | Download survey definition file (e.g., `survey.xml`). |
| `PUT` | `/surveys/{survey}/files/{filename}` | `putSurveyFile` | Upload, edit, or overwrite survey XML or custom assets. |
| `DELETE` | `/surveys/{survey}/files/{filename}` | `deleteSurveyFile` | Remove an asset from the survey repository. |
| `GET` | `/surveys/{survey}/sections` | `getSurveySections` | Inspect survey modular sections for multi-programmer workflows. |
| `POST` | `/surveys/{survey}/sections/{section}/checkout` | `checkoutSurveySection` | Lock/checkout a section to prevent merge conflicts. |
| `POST` | `/surveys/{survey}/sections/{section}/checkin` | `checkinSurveySection` | Commit and check-in modified section logic. |
| `POST` | `/surveys/{survey}/sections/{section}/sync` | `syncSurveySection` | Synchronize section changes back into master `survey.xml`. |
| `POST` | `/surveys/{survey}/sections/{section}/revert` | `revertSurveySection` | Abandon local section edits and revert to master. |
| `GET` | `/surveys/{survey}/sections/{section}/validate` | `validateSurveySection` | Syntax-check section logic prior to merging. |
| `GET` | `/libraries/{company}/elements` | `getCompanyElements` | Access reusable corporate question bank elements. |
| `POST` | `/libraries/{company}/elements` | `createCompanyElement` | Store standardized demographic/screener question in company library. |
| `POST` | `/surveys/{survey}/logic/{label}/trigger` | `triggerLogicNode` | Programmatically evaluate custom survey Python logic blocks. |
| `GET` | `/surveys/{survey}/logic/{label}/debug` | `debugLogicNode` | Debug Python runtime variables in logic nodes. |

### 3. Survey Data & Participant Responses (33 Operations)
The core microdata engine supporting 16 export formats, streaming, conditional filtering, and response manipulation.

| HTTP Method | Endpoint Path | Operation ID | Purpose & Features |
|---|---|---|---|
| `GET` | `/surveys/{survey}/datamap` | `getSurveyDatamap` | Download questionnaire schema (labels, types, variable codes, answer titles). Supported formats: `json`, `xml`, `html`, `tab`. |
| `GET` | `/surveys/{survey}/data` | `getSurveyData` | Stream respondent records. Supported formats: `json`, `jsonl`, `spss`, `spss16`, `spss16_oe`, `csv`, `tab`, `tab_uq`, `fw`, `fwu`, `pipe`, `flat`, `cb`. Supports Python filter conditions (`cond`), date bounds (`start`, `end`), and field projection (`fields`). |
| `GET` | `/surveys/{survey}/summary` | `getSurveySummary` | High-level participation metrics: completes, terminates, dropouts, incidence rate, median length of interview (LOI). |
| `POST` | `/surveys/{survey}/data/edit` | `createDataEdit` | Inject synthetic or offline respondent data records into survey. |
| `PUT` | `/surveys/{survey}/data/edit` | `updateDataEdit` | Modify existing respondent answers (e.g., data cleaning, recoding). |
| `DELETE` | `/surveys/{survey}/data/edit` | `deleteDataEdit` | Scrub, delete, or disqualify bad-faith respondent records. |
| `PUT` | `/surveys/{survey}/data/edit/markers` | `updateDataMarkers` | Tag respondent rows with quality flags (e.g., fraudulent, speeder). |
| `POST` | `/surveys/{survey}/respondents/import` | `importRespondents` | Bulk import participant datasets. |
| `GET` | `/datafeed/{feed}` | `getDatafeed` | Consume real-time event-driven data streaming feed. |
| `POST` | `/datafeed/{feed}/ack` | `ackDatafeed` | Acknowledge receipt of batch records in the feed. |
| `GET` | `/surveys/{survey}/simulated` | `getSimulatedData` | Generate automated Monte Carlo test respondents for stress testing. |
| `POST` | `/surveys/{survey}/evaluate` | `evaluateSurveyData` | Run real-time Python expression against respondent datasets. |

### 4. Quotas & Quota Management (2 Operations)
Fieldwork balancing and quota enforcement engine.

| HTTP Method | Endpoint Path | Operation ID | Purpose & Features |
|---|---|---|---|
| `GET` | `/surveys/{survey}/quota` | `getSurveyQuota` | Inspect all quota sheets, defined cells, target ceilings, and current completed counts. Returns HTTP 428 if survey is hibernated. |
| `PUT` | `/surveys/{survey}/quota/edit` | `editSurveyQuota` | Dynamically adjust quota targets (e.g., expand sample for hard-to-reach demographics). |

### 5. Hibernation, Archiving & Data Retention (10 Operations)
Long-term retention, cold storage lifecycle, and GDPR/CCPA compliance.

| HTTP Method | Endpoint Path | Operation ID | Purpose & Features |
|---|---|---|---|
| `POST` | `/surveys/{survey}/unarchive` | `createSurveyUnarchive` | **Awaken hibernated survey into active status.** Resolves HTTP 428 precondition blocks. |
| `POST` | `/surveys/{survey}/archive` | `createSurveyArchive` | Move completed survey into compressed cold storage. |
| `GET` | `/surveys/{survey}/can-archive` | `getCanArchive` | Check if project satisfies criteria for archival. |
| `GET` | `/hibernation/status` | `getHibernationStatus` | List all company surveys currently hibernating due to 90 days inactivity. |
| `GET` | `/archives/{company}/scheduled` | `getArchivesScheduled` | List surveys due for automated cold storage. |
| `GET` | `/archives/{company}/deletion` | `getArchivesDeletionReport` | Audit report of surveys scheduled for permanent destruction (after 365 days). |
| `GET` | `/archives/{company}/deletion/data` | `getParticipantDeletionReport`| Track participant privacy erasure requests (GDPR Right-to-be-Forgotten). |

### 6. Reporting, Analytics & Crosstabs (26 Operations)
Online statistical tabulation engine, rim weighting, and executive dashboard exports.

| HTTP Method | Endpoint Path | Operation ID | Purpose & Features |
|---|---|---|---|
| `POST` | `/surveys/{survey}/crosstabs/execute` | `executeCrosstabs` | Run multi-dimensional statistical cross-tabulations on-the-fly with chi-square / t-test significance testing. |
| `GET` | `/surveys/{survey}/crosstabs/configuration` | `getCrosstabsConfig` | Retrieve banner definitions, stubs, and stat testing configuration. |
| `PUT` | `/surveys/{survey}/crosstabs/weighting/rim/{var}` | `updateRimWeighting` | Configure enterprise rim weighting (iterative proportional fitting / raking) directly on the Forsta server. |
| `PUT` | `/surveys/{survey}/crosstabs/nets` | `updateCrosstabsNets` | Define automated Top-Box / Bottom-Box net calculations. |
| `GET` | `/surveys/{survey}/crosstabs/saved` | `getSavedCrosstabs` | List saved report templates configured by researchers. |
| `POST` | `/surveys/{survey}/crosstabs/saved/{id}/export/{fmt}` | `exportSavedCrosstab` | Export formatted crosstab report directly to Excel (`xlsx`), PowerPoint (`pptx`), or PDF. |
| `GET` | `/surveys/{survey}/dashboards` | `getSurveyDashboards` | List live web dashboards attached to the survey. |
| `POST` | `/surveys/{survey}/share` | `createShareLink` | Generate secure, authenticated public/client view links. |

### 7. Email Campaigns, Invites & Distribution (26 Operations)
Automated participant invitations, panel sampling, and deliverability tracking.

| HTTP Method | Endpoint Path | Operation ID | Purpose & Features |
|---|---|---|---|
| `GET` | `/surveys/{survey}/campaigns` | `getCampaigns` | List all invitation campaigns created for the project. |
| `POST` | `/surveys/{survey}/campaigns` | `createCampaign` | Initialize an invitation dispatch campaign. |
| `PUT` | `/surveys/{survey}/campaigns/{id}/list` | `uploadCampaignList` | Upload targeted email distribution list with custom recipient tokens. |
| `GET` | `/surveys/{survey}/campaigns/{id}/invite`| `getCampaignInvite` | Inspect email HTML template, subject line, and sender aliases. |
| `PUT` | `/surveys/{survey}/campaigns/{id}/invite`| `updateCampaignInvite` | Edit invitation email copy, personalized merge tags, and sender address. |
| `POST` | `/surveys/{survey}/campaigns/{id}/sends` | `createCampaignSend` | Schedule or execute immediate email blast. |
| `POST` | `/surveys/{survey}/campaigns/{id}/sends/{send}/cancel` | `cancelSend` | Abort a queued or executing email dispatch. |
| `GET` | `/surveys/{survey}/campaigns/{file}/bounces` | `getCampaignBounces` | Retrieve hard/soft email bounce records. |
| `GET` | `/surveys/{survey}/campaigns/{file}/optouts` | `getCampaignOptouts` | Pull unsubscribe requests. |
| `GET` | `/surveys/{survey}/campaigns/{file}/spam` | `getCampaignSpam` | Audit recipient spam complaints. |
| `PUT` | `/surveys/{survey}/campaigns/suppressions` | `updateSuppressions` | Enforce company-wide suppression and do-not-contact lists. |
| `POST` | `/distribute/email` | `distributeViaEmail` | Dispatch automated report notifications. |
| `POST` | `/distribute/slack` | `distributeViaSlack` | Push real-time fieldwork alerts into enterprise Slack channels. |
| `POST` | `/distribute/ftp` | `distributeViaSftp` | Automated delivery of completed data exports to corporate SFTP servers. |

### 8. Panels & Participant Management (13 Operations)
Integration with proprietary panels and longitudinal sample communities.

| HTTP Method | Endpoint Path | Operation ID | Purpose & Features |
|---|---|---|---|
| `GET` | `/surveys/{survey}/panels` | `getSurveyPanels` | List linked panel communities (e.g., Kinesis / Confirmit Panel). |
| `POST` | `/surveys/{survey}/panels/link` | `linkSurveyPanel` | Connect survey to a managed proprietary panel. |
| `GET` | `/panels/{panel}/datapoints` | `getPanelDatapoints` | Access longitudinal panelist profile attributes (historical buying habits, verified household data). |
| `GET` | `/surveys/{survey}/subscribers` | `getSurveySubscribers`| Manage internal stakeholders receiving automated project updates. |
| `GET` | `/surveys/{survey}/sources` | `getParticipantSources`| Track performance and completion rates across third-party panel vendors (e.g., Dynata, Lucid, Cint). |

### 9. Advanced Research Methodologies & Media (14 Operations)
Advanced choice modeling, conjoint analysis, and multimedia intelligence.

| HTTP Method | Endpoint Path | Operation ID | Purpose & Features |
|---|---|---|---|
| `GET` | `/surveys/{survey}/dqapi/{label}/mxd` | `getMaxDiffSawtooth` | Export MaxDiff design matrices and choice data in format ready for Sawtooth Software. |
| `GET` | `/surveys/{survey}/dqapi/{label}/hitrate` | `getMaxDiffHitrate` | Compute multinomial logit preference shares and utility hit-rates. |
| `GET` | `/surveys/{survey}/dqapi/{label}/tricked` | `getMaxDiffTricked` | Export stacked "tricked" choice tasks for econometric modeling. |
| `GET` | `/surveys/{survey}/conjoint/status` | `getConjointStatus` | Track Discrete Choice Experiment design balance and task completion. |
| `GET` | `/surveys/{survey}/conjoint/report/{q}` | `getConjointReport` | Extract part-worth utility values and attribute importance weights. |
| `GET` | `/surveys/{survey}/videos` | `getSurveyVideos` | Retrieve qualitative video responses recorded via webcam/mobile. |
| `POST` | `/surveys/{survey}/videos` | `uploadSurveyVideo` | Upload stimulus videos for multimedia concept testing. |
| `POST` | `/surveys/{survey}/videos/{id}/create_db_file` | `createWatermarkFile` | **Forensic Video Watermarking:** Generates individual per-respondent watermarked video streams to prevent leaked confidential retail concepts. |
| `PUT` | `/cati/server/{command}` | `manageCatiServer` | Manage computer-assisted telephone interviewing (CATI) telephony stations. |

### 10. Multilingual & Localization (14 Operations)
Global survey translation and multi-market deployment workflows.

| HTTP Method | Endpoint Path | Operation ID | Purpose & Features |
|---|---|---|---|
| `GET` | `/translation` | `getTranslations` | Export all questionnaire strings across target languages. |
| `POST` | `/translation` | `uploadTranslations` | Bulk upload translated question wordings and option labels. |
| `GET` | `/translation/delta` | `getTranslationDelta` | Identify untranslated or recently edited strings requiring localization. |
| `POST` | `/translation/delta/reservation` | `reserveTranslationDelta` | Lock translation strings for professional localization agencies. |
| `PUT` | `/surveys/{survey}/mls/languages/{lang}`| `setPrimaryLanguage` | Configure active market languages for a multi-country survey wave. |

### 11. Administration, Security & Users (38 Operations)
Enterprise access governance, credentials, audit logging, and billing usage.

| HTTP Method | Endpoint Path | Operation ID | Purpose & Features |
|---|---|---|---|
| `GET` | `/rh/apikeys` | `listApiKeys` | List all active API keys and their assigned permissions. |
| `POST` | `/rh/apikeys` | `createApiKey` | Provision a new API key with granular endpoint/IP whitelists. |
| `POST` | `/rh/apikeys/{key}/rekey` | `rekeyApiKey` | Rotate an existing API key without breaking assigned permission scopes. |
| `GET` | `/rh/users` | `listUsers` | Enumerate corporate users and privilege tiers. |
| `GET` | `/rh/users/{user}` | `getUser` | Inspect specific user details (supports `self` for whoami). |
| `POST` | `/rh/users/{user}/reset-2fa` | `resetUser2FA` | Administrative 2FA device reset for corporate security. |
| `GET` | `/rh/users/{user}/audit-log` | `getUserAuditLog` | Security audit trail of user logins, data exports, and configuration edits. |
| `GET` | `/rh/companies/{company}/preferences` | `getCompanyPreferences` | System-wide defaults for formatting, timezone, and security. |
| `GET` | `/rh/usage` | `calculateUsage` | Audit billable monthly active respondents, survey completes, and compute units. |

---

## Part 3: What We Are Actually Using in This Codebase

In our repository, the Forsta interaction is encapsulated within `etl/forsta_client.py` and orchestrated by `etl/forsta_etl.py` and `etl/forsta_api.py`.

### 1. The 5 Active Endpoints

```
[Forsta Surveys Cluster: se1.decipherinc.com]
                       │
       x-apikey: <FORSTA_API_KEY> (64-char hex)
                       │
  ┌────────────────────┼────────────────────┐
  │                    │                    │
  ▼ (1)                ▼ (2)                ▼ (3)
GET rh/companies/all/surveys  GET surveys/{path}/datamap  GET surveys/{path}/data
  │                    │                    │
  │ [Register sync]    │ [Schema parsing]   │ [Chunked streaming]
  ▼                    ▼                    ▼
cip_forsta_survey    ParsedQuestion       _json_records()
                       │                    │
                       └─────────┬──────────┘
                                 │
                                 ▼
                     Status decoding & PII strip
                                 │
                                 ▼
                             cip_answer
```

| # | Endpoint | Code Location | What It Does in Our Architecture |
|---|---|---|---|
| 1 | `GET /api/v1/rh/companies/all/surveys` | `etl/forsta_client.py:175`<br>`ForstaClient.surveys()` | **Automated Survey Discovery:** Discovers all surveys accessible to our service account. In `etl/forsta_etl.py:discover()`, it populates the `cip_forsta_survey` register table with path, title, state (`closed`, `testing`), launch/close timestamps, sample size, and tagging. |
| 2 | `GET /api/v1/surveys/{path}/datamap?format=json` | `etl/forsta_client.py:179`<br>`ForstaClient.survey_datamap()` | **Questionnaire Definition:** Retrieves question codes (`qlabel`), wording (`qtitle`), types (`single`, `multiple`, `grid`, `text`), variable layouts, answer choices (`values`), and bipolar grid statements. Translated by `etl/forsta_api.py` into normalized `ParsedQuestion` structures. |
| 3 | `GET /api/v1/surveys/{path}/data?format=json` | `etl/forsta_client.py:185`<br>`ForstaClient.iter_survey_data()` | **Streamed Microdata Extraction:** Streams all respondent rows chunk-by-chunk using a custom streaming JSON parser (`_json_records`) that parses 64 KB buffers directly to prevent out-of-memory errors on large waves. |
| 4 | `GET /api/v1/surveys/{path}/quota` | `etl/forsta_client.py:199`<br>`ForstaClient.survey_quota()` | **Fieldwork & Quota Monitoring:** Inspects quota cells (`defines`, `sheets`, `parts`, limits vs completes). Used by `etl/forsta_etl.py:quota_cells()` to detect when a wave reaches its 400-respondent ceiling or if a survey is in hibernation (returns HTTP 428). |
| 5 | `GET /api/v1/rh/users/self` | `etl/forsta_client.py:203`<br>`ForstaClient.whoami()` | **Connection & Health Check:** The lowest-cost call to prove credentials and network route without consuming survey quotas. Used in `scripts/weekly_forsta.py` and diagnostic scripts to confirm API key validity. |

### 2. Architectural Principles Enforced in Our Code
- **Strictly Read-Only (GET):** The client never alters, edits, launches, or closes a survey on Forsta.
- **PII Scrubbing on Ingestion:** Personal identifiers are never stored. `userAgent`, `url`, `session`, `dcua`, and `ipAddress` are dropped before database commit. The raw panel identifier (`RID`) is cryptographically keyed into a SHA-256 hash (`respondent_key`).
- **Numeric Status & Code Decoding:** Forsta API returns numeric status codes:
  - `1` = Terminated
  - `2` = Overquota
  - `3` = Qualified (the primary research population)
  - `4` = Partial
- **Streaming Parser:** Rather than loading a 20 MB JSON response into Python memory, `_json_records()` decodes incremental buffers, keeping memory footprint proportional to a single respondent record.

---

## Part 4: What We Are NOT Using (High-Value Opportunities)

Because CIP was originally architected with a strict read-only constraint, several powerful capabilities provided by our premium subscription remain unused. Below are the most impactful capabilities:

### 1. Awakening Hibernated Surveys via API (`POST /surveys/{survey}/unarchive`)
- **The Problem:** Surveys older than 90 days without activity enter hibernation. Forsta answers with **HTTP 428 Precondition Required**. As documented in Philip Moore's email, **43 weekly trackers, 2 annual studies, and 6 ad-hoc studies** are currently hibernated.
- **Support Guidance (Ticket #1079724):** Support Agent Bee Lee verified that `POST /api/v1/surveys/{path}/unarchive` immediately restores the survey to active status.
- **Actionable Opportunity:** Instead of having team members manually open 51 surveys in the web browser, a one-off Python script can awaken each survey, fetch the data, and allow the warehouse to complete its historical backfill.

### 2. Native Rim Weighting (Raking) Engine (`PUT /surveys/{survey}/crosstabs/weighting/rim/{var}`)
- **Current Setup:** In October 2026, CIP built its own Python raking engine (`etl/weighting.py`) that rakes respondent weights to US Census ACS targets.
- **Forsta Capability:** Forsta has a built-in rim weighting engine. Weights can be calculated and attached directly to the dataset on Forsta's servers, ensuring parity between internal CIP reports and reports generated by external agencies directly in Decipher.

### 3. Server-Side Statistical Crosstab Execution (`POST /surveys/{survey}/crosstabs/execute`)
- **Current Setup:** CIP aggregates answers into SQLite/DuckDB tables (`cip_agg_cell`) and computes significance testing in Python.
- **Forsta Capability:** Forsta's crosstab engine can compute complex n-way banner cross-tabs, significance netting, mean score tests, and standard error calculations natively, returning pre-calculated statistical tables in JSON.

### 4. Automated Fieldwork Life-Cycle Automation (`POST /state/close`)
- **Current Setup:** Fieldwork launch and closing are performed manually by researchers in the web portal. CIP polls the API every minute to see if quota has filled.
- **Forsta Capability:** The portal can trigger automated survey close when quotas are filled, or alert researchers via Slack (`POST /distribute/slack`).

### 5. Event-Driven Real-Time Data Feeds (`GET /datafeed/{feed}`)
- **Current Setup:** CIP polls the survey weekly on Monday nights.
- **Forsta Capability:** Forsta supports real-time event streaming (`/datafeed`). As each respondent submits a completed survey, records can be streamed instantly into the database, enabling real-time live-streamed tracker results.

### 6. Forensic Media Watermarking (`POST /surveys/{survey}/videos/{id}/create_db_file`)
- **Forsta Capability:** For consumer product testing and unreleased retail media concepts, Forsta dynamically stamps each respondent's individual ID, IP address, and timestamp into video frames to detect and deter leaks.

---

## Part 5: Production Examples & Recipes

### Example 1: Waking a Hibernated Survey (Solving Ticket #1079724)

#### cURL
```bash
curl -X POST "https://se1.decipherinc.com/api/v1/surveys/selfserve/58f/250901/unarchive" \
  -H "x-apikey: YOUR_64_CHAR_FORSTA_API_KEY" \
  -H "Accept: application/json"
```

#### Python
```python
import requests

def unarchive_survey(host: str, api_key: str, survey_path: str) -> bool:
    """Wakes a hibernated Forsta survey so its data can be read again without a 428 error."""
    url = f"https://{host}/api/v1/surveys/{survey_path.strip('/')}/unarchive"
    headers = {"x-apikey": api_key, "Accept": "application/json"}
    
    response = requests.post(url, headers=headers, timeout=60)
    if response.status_code == 200:
        print(f"Successfully unarchived: {survey_path}")
        return True
    elif response.status_code == 404:
        print(f"Survey not found: {survey_path}")
    else:
        print(f"Failed ({response.status_code}): {response.text}")
    return False
```

---

### Example 2: Streamed Qualified Data Export with Condition Filtering

To download only **qualified respondents** who answered a specific question, using Python conditions directly in the API:

#### cURL
```bash
curl -G "https://se1.decipherinc.com/api/v1/surveys/selfserve/58f/260907/data" \
  -H "x-apikey: YOUR_64_CHAR_FORSTA_API_KEY" \
  --data-urlencode "format=json" \
  --data-urlencode "cond=qualified and q1.r1" \
  --data-urlencode "fields=record,date,status,q1,D1,D2"
```

#### Python
```python
import requests

def stream_qualified_respondents(host: str, api_key: str, survey_path: str):
    """Fetches only qualified respondents, filtering on the server to save bandwidth."""
    url = f"https://{host}/api/v1/surveys/{survey_path.strip('/')}/data"
    headers = {"x-apikey": api_key, "Accept": "application/json"}
    params = {
        "format": "json",
        "cond": "qualified",
        "fields": "record,status,date,q1,D1,D2,D3"
    }
    
    with requests.get(url, headers=headers, params=params, stream=True) as resp:
        resp.raise_for_status()
        for chunk in resp.iter_lines():
            if chunk:
                # Process streamed line/record
                pass
```

---

### Example 3: Running a Server-Side Crosstab Calculation

#### cURL
```bash
curl -X POST "https://se1.decipherinc.com/api/v1/surveys/selfserve/58f/260907/crosstabs/execute" \
  -H "x-apikey: YOUR_64_CHAR_FORSTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "banner": ["gender", "age_band"],
    "stubs": ["q1", "q2"],
    "options": {
      "stat_testing": true,
      "confidence_levels": [95, 99],
      "unweighted": false
    }
  }'
```

---

### Example 4: Checking Quota Cell Details

#### cURL
```bash
curl -s "https://se1.decipherinc.com/api/v1/surveys/selfserve/58f/260907/quota" \
  -H "x-apikey: YOUR_64_CHAR_FORSTA_API_KEY"
```

#### Typical JSON Response
```json
{
  "defines": {
    "Male": {"description": "Gender: Male"},
    "Female": {"description": "Gender: Female"},
    "South": {"description": "Census Region: South"}
  },
  "sheets": {
    "Demographics": [
      {
        "name": "Male_South",
        "limit": 100,
        "completes": 98,
        "cells": ["Male", "South"]
      }
    ]
  }
}
```

---

## Part 6: Comparative Matrix: Used vs. Available

| Functional Domain | Total Endpoints | In Use by CIP? | Currently Used Endpoints | High-Value Unused Endpoints |
|---|---|---|---|---|
| **Survey Discovery & Register** | 27 | **Yes** | `GET /rh/companies/all/surveys` | `GET /rh/surveys/current`, `GET /search` |
| **Questionnaire Schema** | 24 | **Yes** | `GET /surveys/{path}/datamap` | `GET /surveys/{path}/files/survey.xml`, Section checkout |
| **Microdata Extraction** | 33 | **Yes** | `GET /surveys/{path}/data` | `GET /datafeed/{feed}`, `POST /surveys/{path}/data/edit` |
| **Quota Management** | 2 | **Yes** | `GET /surveys/{path}/quota` | `PUT /surveys/{path}/quota/edit` |
| **Health & Auth Verification**| 38 | **Yes** | `GET /rh/users/self` | `POST /rh/apikeys/{key}/rekey`, `GET /rh/usage` |
| **Hibernation & Archiving** | 10 | **No** | *None* | `POST /surveys/{path}/unarchive` *(Resolves Ticket #1079724)* |
| **Crosstabs & Statistics** | 26 | **No** | *None* | `POST /crosstabs/execute`, `PUT /weighting/rim/{var}` |
| **Fieldwork State Control** | 4 | **No** | *None* | `POST /state/live`, `POST /state/close` |
| **Email Campaigns & Invites** | 26 | **No** | *None* | `POST /campaigns`, `PUT /campaigns/{id}/list`, `/sends` |
| **Video & Media Testing** | 14 | **No** | *None* | `POST /videos/{id}/create_db_file` (Dynamic Watermarking) |
| **Choice Models (MaxDiff/Conjoint)**| 5 | **No** | *None* | `GET /dqapi/{label}/mxd`, `GET /conjoint/report/{q}` |
| **Multilingual Localization** | 14 | **No** | *None* | `GET /translation`, `POST /translation` |

---

## Summary & Action Plan for Coresight Research

1. **Immediate Action for Hibernated Historical Waves:**
   Create an administrative script in `scripts/unarchive_hibernated_waves.py` that iterates through the 43 hibernated tracker paths and calls `POST /api/v1/surveys/{path}/unarchive`. This immediately clears the 428 precondition status and allows `etl/forsta_etl.py --survey <path>` to backfill the full historical record from July 2025 to June 2026.
2. **Bandwidth & Performance Optimization:**
   In `etl/forsta_client.py:iter_survey_data`, we can pass `cond="qualified"` and `fields=...` when requesting `/data`. Currently, we stream all records (including terminators and overquotas) and filter in Python. Filtering on Forsta's server can reduce payload sizes by 25–40%.
3. **Exploration of Native Statistical Services:**
   As a premium client, Coresight Research has access to Forsta's cloud tabulation engine. If high-complexity crosstabs (e.g., 5-way nested banners with custom stat significance) are needed in future portal features, they can be calculated on Forsta's compute infrastructure rather than straining local server memory.
