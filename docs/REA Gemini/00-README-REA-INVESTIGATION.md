# Reverse Engineering Anything (REA) — Consumer Insight Portal (CIP)
## Comprehensive Reverse Engineering Investigation & System Dossier

**Target System:** Consumer Insight Portal (CIP / CSI)  
**Organization:** Coresight Research  
**Investigation Framework:** REA (Reverse Engineer Anything) v42  
**Date of Investigation:** 20 October 2026  
**Investigator:** Gemini Agent (Advanced Agentic Coding)  
**Database Profile:** MySQL 8.0 Flexible Server (`csr-mysql8-flex-stg.mysql.database.azure.com:3306`), Database: `cip_stg`  
**Application Host:** macOS ETL Daemon (`launchd`), Streamlit Portal (Port 8611), Planned Azure App Service (P1v3)

---

### Navigation Index

This dossier contains the complete reverse-engineered findings, architecture reconstructions, database specifications, gap analysis, target build plans, and evidence ledgers:

1. [**01-SYSTEM-ARCHITECTURE-RECONSTRUCTION.md**](file:///Users/mohdsaeedafri/All-Code-Base/consumer-insight-portal/docs/REA%20Gemini/01-SYSTEM-ARCHITECTURE-RECONSTRUCTION.md)
   * End-to-end component topology, data flows, external interfaces (Forsta Surveys REST API v1), scheduler topology (`launchd`), runtime execution models, and security boundaries.
2. [**02-DATABASE-AND-DATA-MODEL-REVERSE-ENGINEERING.md**](file:///Users/mohdsaeedafri/All-Code-Base/consumer-insight-portal/docs/REA%20Gemini/02-DATABASE-AND-DATA-MODEL-REVERSE-ENGINEERING.md)
   * Deep structural decomposition of all 33 `cip_` tables and 12 `v_cip_` views across 9 functional domains. Foreign key topology, orphan guard mechanisms, index profiles, storage footprints, and legacy DWH (`dwh_sm*`) migration evidence.
3. [**03-ETL-PIPELINE-AND-INTEGRATION-ANALYSIS.md**](file:///Users/mohdsaeedafri/All-Code-Base/consumer-insight-portal/docs/REA%20Gemini/03-ETL-PIPELINE-AND-INTEGRATION-ANALYSIS.md)
   * Algorithmic reverse engineering of the 11-stage weekly ETL pipeline (`discover` → `run_due` → `fetch` → `definitions` → `_write` → `verify` → `profiles` → `harmonise` → `cube` → `search` → `tracker_line` → `integrity` → `drift`). High-speed bulk loading (`LOAD DATA LOCAL INFILE`), reconciliation mathematical proof, and self-healing resilience.
4. [**04-APPLICATION-UI-AND-RUNTIME-DECONSTRUCTION.md**](file:///Users/mohdsaeedafri/All-Code-Base/consumer-insight-portal/docs/REA%20Gemini/04-APPLICATION-UI-AND-RUNTIME-DECONSTRUCTION.md)
   * Forensic analysis of the active Streamlit application (`app/main.py`), page hierarchy, custom navigation, cookie controller session state workarounds, query repository caching, and empirical proof of the 5-concurrent-user wall.
5. [**05-IDENTIFIED-GAPS-AND-DEFECT-LEDGER.md**](file:///Users/mohdsaeedafri/All-Code-Base/consumer-insight-portal/docs/REA%20Gemini/05-IDENTIFIED-GAPS-AND-DEFECT-LEDGER.md)
   * Concrete register of all observed defects, security vulnerabilities, infrastructure drifts, relational risks, and operational blockers categorized by severity (Critical, High, Medium, Low).
6. [**06-TARGET-BUILD-PLAN.md**](file:///Users/mohdsaeedafri/All-Code-Base/consumer-insight-portal/docs/REA%20Gemini/06-TARGET-BUILD-PLAN.md)
   * Comprehensive engineering modernization blueprint: transitioning from Streamlit prototype to production-grade FastAPI + React/TypeScript SPA, complete with Work Breakdown Structure (WBS), OpenAPI contract definitions, database optimizations, and deployment choreography.
7. [**07-EVIDENCE-BUNDLE-AND-LEDGER.md**](file:///Users/mohdsaeedafri/All-Code-Base/consumer-insight-portal/docs/REA%20Gemini/07-EVIDENCE-BUNDLE-AND-LEDGER.md)
   * Formal REA evidence ledger mapping code references, file paths, test execution records (237 passing tests), live database log metrics, and benchmark telemetry.

---

### Epistemic Conventions (REA v42)

Throughout this documentation, every finding is strictly classified according to verifiable evidence:
* **`[O]` (Observed):** Directly verified from source code, database schemas, test executions, execution logs, network payloads, or system metrics.
* **`[I]` (Inferred):** Logically deduced from observed evidence, architectural patterns, framework constraints, or operational behaviors.
* **`[U]` (Unknown):** Unobserved parameters, pending external inputs, unverified credentials, or external systems outside current environment access.
