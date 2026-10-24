# For Gemini: what is already fixed, what in this folder is out of date (24 Oct 2026)

Written by Claude (Opus) after checking this folder's claims against the live database `cip_stg`, the code and
the competitors' own sites on 24 Oct 2026. **Re-verify any finding against the current code and data before
reporting it again.** The current state lives in `docs/REA Claude Opus 2026-10-23/91-gap-closure-and-reanalysis.md`.

## 1. The five strategic gaps: addressed on 24 Oct 2026

| Gap in 60-/00- | Status | Where |
|---|---|---|
| Census weighting (raking) | **Built.** Each wave is raked to US adult shares by gender, age and region (ACS), trimmed to 0.2–5× and averaging 1; every book carries weighted figures (`row.w`) for Total, gender and generation, prior week and last year. A **Weighted** switch in the header; unweighted stays the default (matches Forsta and the team's Excel files). | `etl/weighting.py`, `config/weighting.yml`, `app/data/payloads.weighted`, `web/src/weight.ts` |
| Index scores / distinctiveness | **Built.** Audience table has an Index column (100 × audience % ÷ everyone's %); "What sets this audience apart" ranks significant over- and under-indexing answers across every question of the wave. | `api/team.py` `_compare`, `audience_profile`; `POST /api/v1/waves/{id}/audience/profile` |
| Open-ended text "discarded" | **Built.** Text questions are coded into themes (Claude when `ANTHROPIC_API_KEY` is set, else frequency coding) and charted in the book like any question; emails and phone numbers are stripped; runs in the weekly ETL. | `etl/open_ends.py`, `scripts/weekly_forsta.py` |
| No public API | **Built.** Personal API keys (`Authorization: Bearer cip_…`), SHA-256 stored outside the repo, same access and rate limits as the person; nginx passes them to the API. | `app/core/api_keys.py`, `api/signin.user`, `deploy/cip_auth.js` |
| No MCP server | **Built.** `POST /mcp` (streamable HTTP, stateless JSON-RPC): `search_questions`, `list_waves`, `question_results`, `question_trend`, `crosstab`, by API key. No vector database is needed (reasoning below). | `api/mcp.py` |

Also: search now understands plain-English questions (`api/search.py`): "what do people think about tariffs"
returned 1,586 loose fragment matches and now returns the 275 tariff questions, tariffs first.

**Why no vector database:** the library is ~3,700 question wordings; SQLite FTS5 with stemming, synonyms, typo
correction and question-word removal answers in about a millisecond. Through MCP the client's model does the
semantic step (it rephrases and calls `search_questions` again). A vector index adds an embedding model and a
service to run for no measured gain; revisit only if the zero-result search log (`api/main.search`) shows
meaning-level misses.

## 2. Findings in this folder that were already fixed before you wrote them

| Your finding | Live state on 24 Oct |
|---|---|
| Survey 97 Q7: YouTube/Facebook at 0 % | Facebook 63.3 %, YouTube 47.3 % in `srv_result`; serving keys cells by `(question_id, item_id, option_id)` (`etl/serving._own`) |
| 766 lost cells (label-keyed serving) | Fixed by the same keying |
| 0 of 27,064 rows carry `concept_option_id` | Wave 415: 12,183 of 12,425; wave 412: 12,291 of 14,639 |
| 4-decimal `qtime` abort | Fixed and tested |
| "Deploy `app/core/access.py` / `config/access.yml`" | Both exist: roles admin/analyst/client, tiers, per-study visibility |
| Ad hoc studies visible to all | The owner's decision (23 Oct), one line per study in `config/access.yml` |
| `/auth/dev-login` open bypass | Demo sign-in only when `CIP_DEMO_LOGIN=1`, on purpose for the demo |
| Suppress cells under n = 10 | Contradicts the owner's rule (23 Oct): nothing is hidden, however small |

## 3. Claims in this folder that are wrong

- **Competitor latencies (100–800 ms) and margins of error (< ±1 %)**: not measured and not published by the vendors; no source. Remove or mark as assumptions.
- **"35+ competitors reverse engineered"**: the documents cover 8.
- **"Competitors export static images or locked PDFs"**: your own matrix lists PPTX export for all of them.
- **"Exports run on the FastAPI main thread"**: `api/main.export` uses `run_in_threadpool`.
- **"srv_answer is un-indexed; crosstabs scan 10M rows in 1.8–3.2 s"**: its primary key starts `(survey_id, qcode, …)`; a crosstab reads one wave's rows.
- **"Redundant `idx_survey`, `idx_question`, `idx_survey_question` waste 1.1 GB"**: no such indexes exist on `cip_answer` (it has PRIMARY, `fk_answer_field`, `ix_answer_cover`, `uq_answer`).
- **Table sizes contradict each other**: `srv_result` is 2.2M rows (you give 1.45M and 2.5M); `cip_answer` 27.8M (you give 11.9M and 27.8M).
- **"Unbroken 8-year weekly history 2018–2026"**: the weekly tracker starts 28 Dec 2020 (268 waves); 2018–2020 are annual studies.
- **"BH-FDR guarantees flagged moves are significant at p < 0.05"**: BH controls the expected share of false discoveries among flagged moves at 5 %; it does not make each flag p < 0.05.
- **"Asterisk when n < 5, `api/main.py:182`"**: that line is search-catalogue code; the under-5 rule was removed on 23 Oct.
- **"Claude 3.5 Haiku"** for coding: superseded; the coder uses `claude-haiku-5-5` (`CIP_CODING_MODEL`).
- **Live link `cheque-bought-dust-successfully…`**: Cloudflare dropped that quick tunnel on 24 Oct; the live link is `https://beam-yields-thu-pet.trycloudflare.com`.

## 4. What remains open (fair game for your next round)

- Permanent hosting on the Azure VM (IT, expected ~26 Oct); until then a quick-tunnel URL can expire.
- Weighted figures cover the wave screens and the MCP connector; Trends, Compare, the topic dashboards and cross-tabs are still unweighted.
- Open-ended coding uses frequency until a Claude key is configured on the server.
- The API key list is managed from the command line (`python -m app.core.api_keys`); there is no admin screen yet.
- ACS targets in `config/weighting.yml` are rounded; check them against the latest ACS release before quoting weighted figures to clients.
