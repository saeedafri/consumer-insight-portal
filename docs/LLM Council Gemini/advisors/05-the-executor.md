# Advisor 5: The Executor
## Ruthless Pragmatic Roadmap, Resource Constraints & Critical Path

**Perspective:** Operational reality, Monday morning actions, staging milestones, and risk-adjusted velocity.

---

The Expansionist wants an AI copilot, the First Principles Thinker wants to rethink data delivery, and the Contrarian wants to freeze everything. Here is what we actually do **Monday morning** to execute this without burning months of engineering time.

Your 6-milestone build plan in REA Gemini is logically sound, but it is sequenced incorrectly. You cannot build a React frontend while your pipeline is crashing on a local laptop. Here is the strict, linear critical path:

### Sprint 1 (Days 1–5): Triage & Operational Stability
1. **Clean the Security Breach:** Delete lines 67–69 of `.env` immediately. Rotate the database password on `10.2.1.9`. Eliminate the `python-dotenv` warning.
2. **Unblock Forsta Ingestion:** Send `docs/04-it-requirements-checklist.md` to IT with high urgency. Obtain the 64-character service account key for directory `58f`.
3. **Database Maintenance Window (15 minutes):** Execute:
   * `ALTER TABLE cip_answer DROP KEY ix_answer_respondent;` (saves 450 MB, speeds writes).
   * Apply cascade FKs to `cip_tracker_line` and `cip_forsta_survey`.
4. **Reactivate the 51 Surveys:** Batch-reactivate the hibernated surveys in Forsta so the pipeline can ingest them before the 365-day deletion threshold.

### Sprint 2 (Days 6–15): The Headless FastAPI Core
Do not build the React UI yet. Extract `api/` using FastAPI:
* Build the 3 essential endpoints: `/api/v1/surveys`, `/api/v1/questions`, and `/api/v1/analysis/crosstab`.
* Deploy this service into a Docker container on Azure App Service with private VNet peering to MySQL. Move the ETL cron into an Azure WebJob. The local MacBook is now 100% relieved of production duties.

### Sprint 3–4 (Days 16–30): The 2-Screen React MVP
Do not rebuild all 8 Streamlit pages. An enterprise client only needs two screens for Release 1:
1. **The Executive Explorer:** Search questions, view trend charts.
2. **The Cross-Tab Grid:** AG Grid with banner cuts and one-click Excel download.

Leave Mappings, Publications, and Data Health in the internal Streamlit portal for internal analysts. Ship the client-facing React MVP in 30 days.
