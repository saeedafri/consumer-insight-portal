# DWH Production Review — What `dwh_pro` Holds for Surveys

Reviewed 30 September 2026 with the read-only account IT issued
(`GRANT SELECT ON dwh_pro.*` only; the session was also set `READ ONLY`).
Nothing was written. Server: MySQL 8.0.30, `csrdbpro01.csr.internal`
(`10.2.1.9`, reachable over the VPN).

## Findings

| Question | Answer |
|---|---|
| Does production have more survey data than `dwh_stg`? | **No.** Identical: 312 surveys (Jan 2018 – Aug 2025), 161,748 responses, 5,460,048 answer rows; no survey differs in either count |
| Are Shiva's Forsta tables filled on production? | **No.** `dwh_surveydetails`, `dwh_surveyquestions`, `dwh_surveyquestionsresponse` exist (migrations 0273–0280, applied 29 Aug – 9 Sep 2025) but hold 0 rows |
| Where did the 10 Forsta surveys in the walkthrough come from? | Shiva's **local** MySQL (the Workbench title in the recording reads "Local instance 3306"); schema named `dwh_prod` there |
| Is the May 2025 Beauty + Inflation + Tariffs wave anywhere? | Not in `dwh_pro` or `dwh_stg` — the Qualtrics Excel export is its only source |

## Why the Forsta tables are empty

1. `automation/forsta_survey.py` calls `HOST = "https://dwh-stg.coresight.com"` — the
   comment says to switch it to production on deploy; it was not switched, so the
   production job never writes production.
2. The staging endpoint cannot fetch either: the Forsta key in
   `Dwh/credentials.yml` is rejected (`401 account disabled`).
3. `save_all_survey_details` / `save_all_survey_questions_and_response` catch every
   exception and return a string, and `/forsta_api_call` still answers
   "Data saved" — so the failure is silent.
4. In `automation/runall.py` the Qualtrics and survey-trend jobs are commented
   out — the reason the legacy history stops in April 2025 and
   `dwh_smsurveytrend` (147 surveys) stops in March 2025.

## How analysts used the survey pages (`dwh_activitylog`)

Logging stopped on 10 Sep 2025. Before that:

| Page | Views | Users | Last used |
|---|---|---|---|
| All surveys | 606 | 40 | Sep 2025 |
| Trend | 590 | 26 | Nov 2024 |
| Weekly | 383 | 34 | Sep 2025 |
| Adhoc | 218 | 22 | Jul 2023 |

The survey list, trends and the weekly tracker are what the portal must serve
first.

## Consequences for the CIP plan

- **Phase 3 (legacy history) reads `dwh_stg`** — identical to production, and
  already reachable with the account the ETL uses. `dwh_pro` adds nothing for surveys.
- **May 2025 Beauty wave:** load from the Qualtrics Excel export.
- **Forsta Aug 2025 → onward** (walkthrough paths `selfserve/58f/250600`, `250701`,
  `250702`, `beauty`, `coresightconnect`, `deptstores`, `ecommerce`,
  `homeimprovement`, `luxury`, `smcommerce`) exist in **no** Coresight database.
  They need a working Forsta API key, or Excel exports of each wave.
