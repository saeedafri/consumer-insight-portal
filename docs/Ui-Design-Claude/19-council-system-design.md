# 19 · LLM Council: the system-design decisions (21 Oct 2026)

Five independent advisors (Contrarian, First Principles, Expansionist, Outsider, Executor), five anonymous peer reviews, one chairman. The question, the five answers and the reviews follow the verdict.

## Council verdict (chairman)

### Where the council agrees
- **This is a publishing problem, not a serving problem.** The data changes weekly and is read-only, so the ETL should write the finished payloads (book, trend, overview, tiles) as pre-gzipped static files for nginx `gzip_static`. Python and MySQL are left only for ad hoc two-cut cross-tabs and search.
- **"No matter how many users" cannot be promised.** 6,000 users is an M4 number; on an Azure core it is about 2,000–3,000, still unmeasured. Four of five advisors reject unbounded wording.
- **Search:** SQLite FTS5 with trigram and a curated synonym list. No sidecar search service, no runtime embeddings.
- **Chatbot:** tool-calling over the typed API, never text-to-SQL. Every response carries base, significance and wave ID.
- **Configuration:** YAML in git; no admin UI yet.
- **Trust matters more than speed.** Three gaps: weighting is undecided, small bases aren't suppressed on the server, and the repo is public with a leaked DB password.

### Where the council clashes
- **The Expansionist vs everyone, on promises and scope:** a CDN, "any user count", embeddings, an MCP server, alerts. The upside is real (embeddable tiles, a narrative engine, an 8-year panel), but it comes after trust is fixed.
- **Runtime cache:** keep the LRU for cross-tabs; drop pre-warming once static files exist.
- **Where search runs:** in the browser vs on the server. The server (FTS5) wins, because the chatbot needs the same index.
- **Synonyms:** the business owns a sheet, the ETL converts it to YAML, and zero-result searches are logged and reviewed monthly.
- **Last-year rule:** default to the same wave number, with a per-module override, stamped in every payload and shown on screen. The two rules diverge around Thanksgiving.

### Blind spots the council caught
- **Database and statistics:**
  - the B2s database's CPU credits running out;
  - two workers on one core;
  - false "significant moves" from multiple comparisons;
  - weighted tests need the effective base;
  - two-cut bases of 5–15;
  - the Excel and the mock-up define metrics differently.
- **Missing from every advisor's answer:**
  - atomic publish (build directory → validate → symlink swap → rollback) with versioned ETags and a "data as of" stamp;
  - quality gates before publishing;
  - the ETL competing with the portal for the one core;
  - a 4 GB memory budget;
  - backup and restore;
  - a chatbot gold-question set and prompt-injection defence;
  - takeaways gated by suppression and significance checks, with a kill switch;
  - visible missing waves.

### The recommendation
1. **Latency.** The ETL publishes static gzipped files atomically and nginx serves them. FastAPI handles only cross-tab and search, with an LRU cache, a concurrency cap, `--backlog` and `limit_conn`, so overload gets a fast 503 with a retry page. The ETL runs off-hours under `nice`. Scale out when cross-tab p95 stays above 300 ms on Azure. The promise:
   > "Every standard screen loads in under 0.5 s (p95) on the production server, whatever the load. Custom two-way cuts load in under 2 s for up to N users at once (N measured on the production server). If the system is overloaded you see a clear 'busy, retry' message, never an error."
2. **Search.** FTS5 with BM25 and trigram, the index built by the ETL. The synonym pipeline as above. A test set of 30 real failed queries.
3. **Chatbot readiness.** Canonical question IDs across waves, a `metrics.yaml` metric catalogue (which also feeds the tiles), OpenAPI, base, significance, MoE and wave ID on every response, and a request log. The bot comes later, as tool-calling evaluated against a gold set.
4. **Configurability.** YAML in git, one file per module, validated by the ETL. Takeaways may only use numbers that passed the checks.
5. **What's missing.**
   - **Security first:** rotate the password, make the repo private, move the portal off the personal account, SSO via nginx or Azure.
   - **Statistics:** decide weighting now; enforce small bases server-side (hide n<30, flag n<50); apply Benjamini-Hochberg to "biggest moves"; show missing waves.
   - **Product:** CSV and PNG export with base; accessibility; backup and restore drill; monitoring.

**Build order:**
1. Security
2. Measure on Azure, then set N
3. Weighting and LY rule; metric catalogue and canonical IDs
4. Server-side suppression and the multiple-comparison correction
5. Atomic static publish with gates and a "data as of" stamp
6. nginx `gzip_static`, admission control, 503 page
7. FTS5 search
8. Module YAML: tiles and gated takeaways
9. Export, accessibility, backup, monitoring
10. Chatbot tools and the evaluation set

### The one thing to do first
Rotate the leaked MySQL password today, make the repo private and take the portal off the personal account. It is the only item on this list that is already live; everything else is design work.

## Council question: the final system design for Coresight's Consumer Insight Portal (CIP)

## Context (facts)
- Coresight Research runs a weekly US consumer survey (≈400 qualified respondents/week, ~55–60 questions/wave) plus annual and ad hoc studies. 328 surveys/waves are loaded (2018–2026) and older archives keep being added. Data arrives from Forsta (Decipher) API; a Python ETL loads raw answers (23 M rows), builds a cube, then screen-agnostic serving tables in Azure MySQL 8 (srv_result 1.9 M rows: every question × answer × standard cut with % and prior-week/last-year comparisons and flags; srv_answer 8.1 M rows: per-respondent answers with six cuts for any two-cut filter).
- Servers from IT: ONE Debian app server per environment, 1 CPU core each; staging 4.5 GB RAM, production 8–9 GB; MySQL is a separate Azure server (B2s 2 vCPU/4 GB). Owner priority: staging must be optimal with ≤4 GB, latency "below 0.5 s, no matter how many users", no errors.
- Current build: React 19 + Vite + TypeScript + ECharts SPA (static files) + FastAPI (2 gunicorn workers), byte-capped LRU response cache (256 MB/worker), pre-gzipped JSON, one /book request (23 KB gz) per wave feeds most screens. Screens: survey library, question search, overview (auto "biggest significant moves"), question explorer (5 chart types), cross-tab (significance letters, two-cut pooling), trends (gaps for missing waves, MoE band), what changed, survey preview. Coresight brand palette mandatory (red #D62E2F highlight, white #FAFAFA, black #2D2A29, blues; strict chart rules).
- Measured on a 1-core/4 GB container with real data: ~6,000 simultaneous heavy users (click every 10 s, 30 % archive cache misses) at p95 41 ms, 8,000 at p95 56–293 ms, 10,000 saturates (p95 1.5 s); RAM ≤1.3 GB. Screens draw in 0.34–0.5 s; browser heap 7–46 MB. (M4 ARM core; Azure core assumed 2–3× slower.)
- The business team's Excel ("Holiday Survey Databank") wants per-module "This week at a glance" tiles (not started / started / finished / bought past 7 days / #1 retailer, each vs prior week and vs LAST YEAR'S SAME WAVE NUMBER) plus auto-written "Key takeaways" sentences. A Lovable mock-up (one survey only, hard-coded data) adds: paired comparisons (in-store vs online; food vs non-food), index vs total ▲▼ (≥120/≤80), segment base tiles with low-base warnings, a "segments" small-multiples view, survey preview with live results, dark-mode toggle.
- Planned later: an AI chatbot for analysts ("Who was the best retailer in this survey?", "How did Gen Z holiday shopping change vs last year?") so they don't read Excel.

## Decisions the council must settle (give a recommendation for each)
1. Latency promise: how to guarantee < 0.5 s p95 and zero errors on a 1-core 4 GB box as users grow (pre-computed payloads written by the ETL vs runtime cache, cache pre-warming, nginx micro-cache/CDN, admission control/queueing, when to scale out), and what to promise honestly.
2. Search: users must find any question regardless of typos/synonyms. Options: SQLite FTS5 (stdlib, BM25 + trigram) + synonym/YAML + spelling correction; DuckDB FTS; Meilisearch/Typesense sidecar; embeddings (semantic) — given 1 core/4 GB.
3. Chatbot readiness: tool-calling over the existing typed API (waves, search, book, trend, crosstab) vs text-to-SQL over serving tables vs a semantic layer/metric catalogue; what to build NOW so the bot is easy later (metadata, metric definitions, OpenAPI, audit, guardrails like always citing base and significance).
4. Configurability: module dashboards (tiles, lists, segments, takeaway sentence templates, LY rule = same wave number vs same calendar week) in YAML vs a DB-driven admin UI.
5. Anything the design is missing or getting wrong for a B2B research portal (security, export, accessibility, data governance, small-base suppression, weighting).

## Five anonymized advisor responses

## Response A
1. Latency. The ETL already writes srv_result — add one step that writes /book payloads as pre-gzipped files to disk; nginx `gzip_static` serves them, no Python, no MySQL in the path. That makes the 0.5 s promise a disk read, not a cache bet. Keep the runtime LRU only for crosstab/two-cut. Add gunicorn `--backlog` + `limit_conn` so overload returns a fast 503 instead of a 1.5 s pile-up. Promise in writing: "p95 < 0.5 s for pre-built screens at any load; ad hoc cross-tabs up to N users, measured on the real Azure core." The 6,000 is an M4 number — not a promise. Run the existing load test on staging this week. Scale out when crosstab p95 > 300 ms. Don't add CDN/micro-cache before that.
2. Search. SQLite FTS5 with trigram tokenizer + `synonyms.yaml`. Ships with Python, ~50 lines, ETL builds the index file. Trigram covers most typos. Skip Meilisearch (sidecar on one core is a liability) and embeddings until the chatbot needs them. Collect 30 real failed analyst queries as the test set.
3. Chatbot. Tool-calling over the typed API. No text-to-SQL. FastAPI gives OpenAPI free. Build now: every endpoint returns base_n, sig_flag, wave_date; a metrics.yaml defining each metric (which question/codes) — that file also feeds tiles. Defer audit log until the bot exists.
4. Configurability. YAML in repo, one file per module: tiles, takeaway templates, `ly_rule: wave_number`. ETL validates it. Admin UI is weeks of work for ~5 edits/year.
5. Missing, in order: small-base suppression (grey n<50, flag n<100) enforced in srv_result not UI — one wrong Gen Z number to a client is the real outage; security today (rotate leaked DB password, private repo, off personal account); SSO via nginx/Azure, don't build login; browser-side CSV export; decide weighting now (an ETL column; retrofitting later rebuilds everything); accessibility (text labels on ▲▼, run axe). Dark mode can wait. Monday: rotate password → measure on Azure core → pre-built book files → base suppression → FTS5.

## Response B
1. Latency. Nobody outside your team knows what p95, cache misses, or M4 vs Azure means. "Below 0.5 s no matter how many users" is a promise physics breaks. ~6,000 on a faster chip ≈ 2,000–3,000 on Azure. Do you even have that many analysts? Count real logins. Pre-built payloads so a request just serves a file, plus a polite "busy, retry" page. Promise plainly: "under half a second for up to N people at once, tested on the real server."
2. Search. Users type "black friday", not question codes. SQLite FTS5 + a synonym list the business team owns (a spreadsheet of "people say X, we mean Y"). No sidecar (one more thing IT patches), no embeddings yet.
3. Chatbot. Text-to-SQL invents numbers off tables nobody can explain. Tool-calling over the API. Cheap now: one plain-English description per question, base and significance note in every response, a log of what the bot was asked.
4. Configurability. If you edit it, YAML. If the business team edits it, they won't open YAML — give them an Excel template and load it. No admin UI yet. Decide LY in writing now.
5. Missing: hide/grey anything under a fixed minimum base by default (a client will screenshot a 15-person result); weighting never mentioned — say so on every chart; Excel/PowerPoint export day one; login/roles/client separation (B2B); repo public + leaked password — fix before features; one-line hover explanations for jargon (index, letters, MoE band); show which waves are missing (51 never loaded) or trends mislead quietly.

## Response C
1. Latency. The number is wrong at the root: 6,000 on an M4; Azure 2–3× slower → maybe 2–3k, unmeasured on the real box. Worse: MySQL is a burstable B2s — when credits run out mid-week, every miss hits a throttled DB. Two gunicorn workers on one core: one slow crosstab blocks half your capacity. ETL should emit static pre-gzipped book/trend/overview files served by nginx. Admission control only on dynamic two-cut endpoints, 503 + retry. Promise "<0.5 s p95 up to N measured users on the production SKU" — never "no matter how many".
2. Search. FTS5 + trigram + synonym YAML is enough; embeddings on 1 core/4 GB is latency pain for an unproven need; Meilisearch is a second process for ~20k texts. Trap: the synonym YAML rots unless owned — log zero-result searches and review monthly.
3. Chatbot. Text-to-SQL over srv_answer is a liability: invents cuts, ignores bases, can leak respondent rows. Tool-calling; the API must return base, MoE and significance alongside every number. Missing: a metric catalogue defining "bought", "finished", "#1 retailer" — the Excel and the mock-up already disagree; the bot will amplify ambiguity confidently.
4. Configurability. YAML in git; a DB admin UI without auth/audit/preview is a production-breaking button. Trap: LY rule — same wave number vs same calendar week diverge around Thanksgiving; pick per module, stamp it in the payload, show it on screen.
5. Wrong/missing: weighting (unweighted → every "Gen Z vs LY" claim is suspect; weighted → significance needs effective base, not raw n); six cuts × two-cut on 400 people gives bases of 5–15 — suppress <30 server-side; multiple comparisons: "biggest significant moves" across ~60 questions × cuts at p<.05 flags false positives weekly — correct it or the takeaways mislead; security: no auth/entitlements, public repo, leaked password; 51 hibernated surveys = gaps the business reads as real; export with base, WCAG contrast on brand red, audit log.

## Response D
1. Latency. Precompute everything; the ETL writes final gzipped JSON per wave/module/tile set as static files, nginx gzip_static, CDN in front. FastAPI only for ad hoc two-cuts and search. The 6,000 ceiling becomes irrelevant. Bigger upside: those static payloads become a product — embeddable charts for reports, newsletters, articles. Promise "<0.5 s on every published view, any user count" — true because nothing is computed at read time.
2. Search. FTS5 now, but build it as a concept index: map every question to a canonical concept ID so "holiday spend", "gift budget", "how much will you spend" become one concept tracked across eight years. Add small ONNX embeddings (<100 MB) as an offline second pass in the ETL. That concept graph is exactly what the chatbot needs; "find every question ever asked about X" becomes a headline feature.
3. Chatbot. Tool-calling over the typed API, designed for external clients from day one: publish OpenAPI + a metric catalogue (definition, base, LY rule, significance test, suppression); expose it as an MCP server so clients ask in Claude/Copilot and get answers with base and significance cited — every answer a citable, linkable tile. Skip text-to-SQL.
4. Configurability. YAML in git now, structured so an admin UI can sit on top later. Takeaway templates are a narrative engine: tiles + templates → the weekly email, slide, client brief. LY rule per module, shown on screen.
5. Missing: PPTX/PNG export in Coresight style one click from any chart (analysts live in decks); client entitlements row-level (turns an internal tool into a subscription tier) — private repo first; alerts/subscriptions ("notify me when Gen Z Amazon share moves significantly"), flags already computed; weighting toggle + small-base suppression as the credibility moat; market the 8-year weekly archive as a longitudinal panel.

## Response E
What are we solving? One analyst getting a trustworthy answer, with base and significance, from survey data that changes weekly. Read-only, weekly-rebuilt data: a publishing problem, not a serving problem.
1. Latency. Wrong question. A B2B portal has tens to low hundreds of users. Data that changes weekly should never be computed at request time: ETL writes every /book, trend and overview payload as pre-gzipped static files; nginx gzip_static with long cache headers (CDN if IT allows). The promise becomes "nginx sends a file" — true. FastAPI only for ad hoc two-cuts with a semaphore and fast 503-retry. Promise: "every standard screen <0.5 s; custom cuts <2 s." Delete the runtime LRU and pre-warming — they are workarounds for not having the files.
2. Search. ~20k question texts. Ship the index to the browser as JSON and fuzzy-match client-side: zero server cost, instant. Hand-curated synonym list (BNPL / buy now pay later / Klarna is domain knowledge). No sidecar, no embeddings; the chatbot will cover semantic search later.
3. Chatbot. The real blocker is question identity across waves: wave 47 of 2025 and 47 of 2026 must share a canonical question ID, answer codes harmonised, wording changes versioned. Build that catalogue now; then tool-calling over the typed API with base, significance and wave IDs in every response. Never text-to-SQL.
4. Configurability. YAML in git; probably two editors; admin UI is a second product. Decide LY (same wave number) once, in the catalogue, not per dashboard.
5. The two real dangers: weighting — if the 400/week isn't weighted to census, every "biggest move" is partly sample composition; settle before more screens. Exposure — public repo, leaked password: rotate now. Also: small-base suppression in serving tables (n<50 flag, n<30 hide) not the UI; entitlements if clients ever log in; CSV export of exactly what's on screen. Speed is largely solved; trust in the numbers isn't.

## Advisor identities (de-anonymized): A = The Executor, B = The Outsider, C = The Contrarian, D = The Expansionist, E = The First Principles Thinker

## Peer reviews (5 reviewers; lenses: general, 1-core feasibility, analyst/client UX, statistical rigour & chatbot, operations)
R1: Strongest E (publishing reframe, weighting+exposure before speed, canonical question identity, honest <0.5 s standard / <2 s custom). C second (multiple comparisons, effective base, B2s credits). Blind spot D (any-user-count promise, CDN+embeddings vs 1-core, feature creep, buries security). All missed: atomic publish/rollback of static payloads + stale-data banner + versioned ETags; ETL data-quality gates before publish; backup/restore; takeaways must pass suppression/significance/multiple-comparison checks; terms of use/licensing for exports; observability; single-server failure plan.
R2: Strongest E (static files, client-side search costs zero server). Blind spot D (CDN privacy, scope creep). All missed: atomic publish (build dir + symlink swap + validate), ETL competing for the single core (schedule off-hours / nice), a 4 GB memory budget (nginx + 2 workers × 256 MB + SQLite + page cache), backup/DR, credential handling, SLO monitoring, reconciliation of published numbers vs source.
R3: Strongest C (B2s credits, 2 workers/1 core, metric-definition conflict Excel vs Lovable, multiple comparisons, effective base, synonym rot, 5–15 bases). E close second. Blind spot D. All missed: data-freshness UX (what analysts see mid-publish/ETL failure, "data as of" stamp), takeaways need analyst review + "why flagged" drilldown + kill switch, versioned snapshots/citations for reproducibility, ops (backup/rollback/alerting), usability testing with real analysts.
R4: Strongest C (only one deep on statistics). E second. Blind spot B (generic) / D. All missed: chatbot evaluation (gold-question test set), prompt-injection via survey text, LLM data egress/cost, answer-level provenance; rounding/n/a semantics; trend handling of wording changes & missing waves; sample-design shift validity for LY; data versioning; ETL reconciliation; Forsta dependency.
R5: Strongest C (ops depth), A second (concrete Monday sequence, backlog/limit_conn). Blind spot D (no sizing, concept-graph ownership, security as revenue). All missed: cache/file invalidation and atomic publish (build dir + symlink + rollback, content-hashed URLs), IT ownership of nginx/TLS/patching/monitoring, DR (backup/restore, promotion staging→prod, no failover), restatement versioning when old waves re-run.
Tally: strongest C×3, E×2; blind spot D×4, B×1.
