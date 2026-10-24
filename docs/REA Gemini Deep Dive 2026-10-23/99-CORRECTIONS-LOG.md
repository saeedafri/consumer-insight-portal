# 99 · Corrections & Verification Log (23–24 Oct 2026)

This log records discrepancies, historical stale claims, and their exact reconciliation against the live Azure MySQL database (`cip_stg`), local codebase, and external competitor evidence.

---

## 1. Audit Reconciliation Against Live System & External Review (24 Oct 2026)

| Area | Stale / Inaccurate Claim | Verified Live Reality (Audited Today) | Action Taken |
|---|---|---|---|
| **Survey 97 Q7** | Stated YouTube & Facebook at 0.000% due to choice shift. | **Already resolved in live database.** Direct SQL query confirms Facebook is **63.26%** ($n=818 / 1,293$) and YouTube is **47.33%** ($n=612 / 1,293$). Fix was already executed in `etl/legacy_dwh.py`. | Removed from open defects register; marked as resolved. |
| **Lost Cells** | Stated 766 cells lost across 8 waves due to label keying. | **Already resolved in codebase.** `etl/serving.py:128-130` explicitly defines cell identity by ID tuple: `_own(c) = (c["question_id"], c["item_id"], c["option_id"], c["dim"], c["dim_value"])`. | Removed from open defects register; marked as resolved. |
| **Concept Mapping** | Stated "0 of 27,064 rows" linked to `concept_option_id` on waves 415/412. | **Already resolved in live database.** Direct SQL query confirms: Wave 415 has **12,183 of 12,425** rows linked (98.1%); Wave 412 has **12,291 of 14,639** rows linked (84.0%). | Corrected across all documentation files. |
| **Numeric Crash** | Stated 4-decimal values crash bulk inserts permanently. | **Already resolved and tested.** Handled via numeric rounding in `forsta_etl.py` and covered by passing test suite (`pytest tests/test_etl_fixes.py`). | Removed from open defects register. |
| **Access Control** | Listed "deploy access.py and access.yml" as a pending decision. | **Already exists in working tree.** `app/core/access.py` and `config/access.yml` are fully authored, defining roles (`admin`, `analyst`, `client`), tiers (`demo`, `core`, `professional`, `enterprise`), and survey visibility rules. | Reclassified from missing feature to existing capability. |
| **Export Threading** | Stated exports run synchronously on the FastAPI main thread. | **Inaccurate.** `api/main.py:518` runs exports in a background worker thread pool via `run_in_threadpool`, complete with rate limiting (`access.spend`) and audit logging. | Corrected in docs 30 and 60. |
| **Table Row Counts** | Inconsistent row counts cited across earlier drafts (1.45M vs 2.5M for results; 11.9M for answers). | **Exact counts verified via direct live SQL `COUNT(*)`:**<br>• `srv_result`: **2,168,027 rows** (~2.2M)<br>• `cip_answer`: **29,036,518 rows** (~29.0M)<br>• `srv_answer`: **9,532,424 rows** (~9.5M) | All inconsistent figures replaced with exact live counts. |
| **Tracker Scope** | Stated "unbroken 8-year weekly history since 2018". | **Inaccurate timeline.** The weekly tracker began in December 2020 (**268 weekly waves**). Longitudinal data back to 2018 exists, but stems from periodic annual/benchmark studies, not weekly waves. | Clarified in executive summary and competitor comparisons. |
| **BH-FDR Definition** | Stated BH-FDR "guarantees every flagged move is significant at 5%". | **Statistically inaccurate phrasing.** Benjamini-Hochberg controls the False Discovery Rate (the expected proportion of false discoveries across multiple simultaneous tests at $q \le 0.05$), rather than providing an individual hypothesis-level error guarantee. | Rephrased with exact statistical rigor. |
| **User Product Choices** | Flagged demo login, public ad-hoc study visibility, and lack of under-10 suppression as vulnerabilities. | **These reflect deliberate user decisions:**<br>• Demo login is intentionally enabled for the demo (`CIP_DEMO_LOGIN=1`).<br>• Ad-hoc study visibility is set to `all` by design in `config/access.yml`.<br>• Small-cell display follows the user's explicit "hide nothing" instruction. | Removed from defect lists; cataloged as user configuration policies. |

---

## 2. Real Gaps Confirmed and Validated

The following 5 strategic gaps remain genuine, verified, and high-impact:

1. **Sample Weighting / Representativeness:** Weekly tracker is unweighted ($n \approx 400$, $\text{MoE} = \pm 4.9\%$, expanding to $\pm 18\%$ at $n=30$). Competitors (Morning Consult, YouGov, Euromonitor) weight to Census ACS targets or quota-match.
2. **Distinctiveness Index Scores:** UI lacks Index Scores ($\text{Index} = 100 \times \frac{P_{\text{target}}}{P_{\text{base}}}$) and $z$-scores to highlight over-indexing cohorts. This is the fastest analytical win because base data is already present in `srv_result`.
3. **External Distribution (FastMCP & Public API):** GWI, Statista Connect, Attest, and Morning Consult provide official MCP connectors for Claude/ChatGPT/Copilot and public REST APIs. CIP has no public API or external MCP connector.
4. **Open-Ended Text NLP:** Verbatim "Other, please specify" responses are excluded from analytical cubes and search. Competitors use LLMs to code text into structured themes.
5. **Production Cloud Hosting:** The live stack is hosted on a developer MacBook behind a temporary quick tunnel. Moving to the provisioned Azure East US Ubuntu VM is the primary infrastructure milestone.
