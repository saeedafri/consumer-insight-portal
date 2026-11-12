# CIP competitive evaluation: Consumer Insight Portal vs the market (12 Nov 2026)

**What this is:** a strict comparison of the Consumer Insight Portal (CIP) with 46 national and international competitors,
public and private, plus a code audit for simplicity. The full table is
[CIP_Competitive_Evaluation_2026-11-12.xlsx](CIP_Competitive_Evaluation_2026-11-12.xlsx). This file explains it.
**Baseline:** [the 23 Oct 2026 study](../REA%20Claude%20Opus%202026-10-23/60-competitors-and-market-gaps.md), with every
gap it listed re-checked against today's code and staging.
**Evidence labels:** *observed* = seen on a vendor page, in a REA capture, in CIP's code or on staging today;
*vendor claim* = what a vendor says about itself, unverified; *inferred* = our reading.

---

## 1. The verdict in ten lines

1. **Strict score: CIP leads on 4 of 58 parameters, is level on 7, lags on 25, lacks 16, and 6 have no public benchmark**
   (workbook, Scorecard; formulas recompute when a score changes).
2. **CIP's average is 1.48 out of 3, 14th of 15 products.** Only Prosper (1.40) is lower. YouGov (2.43), Qualtrics (2.41) and
   GWI / Circana (2.32) top the list. The average is harsh on CIP: CIP is scored on all 58 parameters, while competitors are
   scored only where they make public claims. The head-to-head columns are fairer, and still against CIP. For example,
   Morning Consult is ahead on 16 parameters and CIP on 5.
3. **Where CIP truly leads:** research-grade honesty on every figure (base n, significance with false-discovery
   correction, margin of error, "not comparable" across wording changes), a reconciliation with the source (43,396 of 43,396
   cells), editable PowerPoint exports, alerts on significant moves, and speed (p95 under 0.35 s). No competitor reviewed
   shows uncertainty as consistently.
4. **The worst lag is trust, not features.** Ask Coresight on staging answered 3 of 3 hard questions partly wrong (section 5).
   Through MCP, those answers land in a client's Claude chat with no analyst checking them.
5. **The worst exposure is access.** In `config/access.yml`, unknown emails get the enterprise tier, and client-commissioned
   studies (T-Mobile and others) are visible to everyone. A client's paid study is readable by any outsider who signs in.
6. **The data gap is structural:**
   - CIP: about 400 respondents a week, unweighted by default, US and China only.
   - Morning Consult: 30,000 a day. CivicScience: millions a day. YouGov: a 30M+ panel.
   - Do not race on scale. Pool four weeks by default and weight properly.
7. **The AI gap is distribution and narrative.** CIP has an API and MCP. The gaps:
   - Not listed in the Claude or ChatGPT connector directories (needs OAuth).
   - No AI-written summaries or slides.
   - Ask is not grounded in Coresight's own written reports.

   Euromonitor, Mintel, Statista and eMarketer all cite their own research. Only Coresight has its reports, so this is the moat.
8. **Enterprise packaging is thin:**
   - no SOC 2 or ISO 27001;
   - no per-client SSO or SCIM;
   - one 1-vCPU worker;
   - no pricing;
   - scale numbers that disagree (PRODUCT.md: 144+ waves; public site: 370+).
9. **The code is lean but not yet simple:**
   - Almost no dead code. 523 tests pass and the TypeScript type-check is clean.
   - **Five copies of the significance test.** A research product cannot afford two screens that disagree.
   - About 2,400 lines of home-built speed and monitoring tooling (perf meter 1,027, monitoring 1,391) that platforms already provide.
   - 13 functions over 80 lines.
10. **Council recommendation:** position CIP as the evidence layer behind Coresight research, sold inside the subscription.
    It is not a rival to Morning Consult. First fix access, Ask correctness, the shared statistics module, data rights and
    pricing. Then ground Ask in the reports.

---

## 2. What was done (the ten requested tasks)

| # | Task | Done how | Result |
|---|---|---|---|
| 1 | Find competitors with Agent Reach | Agent Reach web channel (Exa) | First query worked (Coresight, Kantar MONITOR, Ipsos Market Essentials, Rasmussen, CivicScience Consumer Compass, OnePulse, Konfidant). Then the provider failed with an upstream JSON error on every call, so per the skill's rules it was not retried in a loop. The other 36 searches used the built-in web search |
| 2 | Reverse-engineer competitors (REA) | Isolated headless Chrome on port 9334, closed afterwards. `analyze_web_bundle` on Statista Consumer Insights, Deloitte ConsumerSignals and Numerator. Plain-GET stack fingerprints of 31 sites | Statista's route table (56 routes, React + Vite): consumer-AI streaming, chat history editing, target-group applicability and population preview, an export queue with cancel / retry. REA refused the Attest and YouGov app sign-in shells (`target_not_allowed`). Morning Consult's app is behind oauth2 + Cloudflare |
| 3 | Compare every competitor feature with CIP | 58 parameters x 14 core competitors, scored 0-3 | Workbook, Parameter matrix |
| 4 | Excel table: where they excel, where we lead, where we lag, minor shortfalls included | One row per parameter; best competitor and verdict by formula; 66-row lag register | Workbook, Parameter matrix, Lag register, Where CIP leads |
| 5 | Named competitors, exact lags, improvements, suggestion box | Lag register (exact evidence, who excels, fix, effort, priority); Suggestion box (21 moves with KPIs and an owner column) | Workbook |
| 6 | National and international, public and private | 46 companies: US, UK, Germany, France, Australia, India, China; listed, private, PE-owned, non-profit, subsidiaries | Workbook, Competitor register |
| 7 | LLM Council, five perspectives | 5 advisors in parallel, 5 anonymous peer reviews, chairman | [02-council-verdict.md](02-council-verdict.md), [91-council-transcript.md](91-council-transcript.md) |
| 8 | Strict analysis | Everything checked against live code, config and staging; three Ask probes; one council claim checked and narrowed | Sections 4-5 |
| 9 | Ponytail review and audit | `ponytail-audit` across the repo; `ponytail-review` on the uncommitted diff | Section 6, workbook Code audit |
| 10 | Simple code for complex problems | Readability measures (headers, docstrings, long functions, duplicates) | Section 6 |

---

## 3. Who the competitors are

The full list, with HQ, ownership, segment, threat and latest move, is in the workbook's Competitor register. By threat to CIP:

**Very high (the deal is against them)**
- **Morning Consult** (US, private). 30k interviews a day. In September 2026 it shipped a Claude MCP connector in alpha,
  free to Intelligence subscribers. Its tools: `morningconsult_data`, `morningconsult_query` (SQL), datasource discovery,
  `search_questions`, and tenant switching. Gemini is next.
- **YouGov** (UK, LSE: YOU). Profiles weekly and BrandIndex daily in 56 markets. It owns Crunch. It added MCP for Profiles
  and Crunch in June 2026 and for BrandIndex in October 2026 (BrandIndex licensed separately).
- **Numerator / Worldpanel by Numerator** (Kantar group, private). A receipt panel combined with Worldpanel, plus Verified
  Voices surveys of verified buyers and a free monthly sentiment tracker.

**High**
- **GWI** (UK, private). Agent Spark runs in ChatGPT, Claude and Copilot (January 2026). Spark MCP v0.5 shipped in
  September 2026, followed by an agentic portfolio in October.
- **Statista Consumer Insights** (Germany, a Ströer unit reportedly being divested). Statista MCP with citations;
  applicability checks.
- **CivicScience** (US, private). Millions of responses a day and 2,000+ always-on questions. A free Poll of the Day since
  April 2026.
- **Circana** (US, private). An AI survey writer (June 2026) and an insights agent in Analysis Builder (Q4 2026).
- **eMarketer** (US, Axel Springer). The closest peer to Coresight's business model: an AI research assistant and EM Connect.
- **Prosper Insights & Analytics** (US, private). A monthly US survey of about 7,500-8,000 people since 2002. The NRF's
  partner; sells on AWS Marketplace.

**Medium**
- NIQ (NYSE: NIQ; Optiq agent and Optiq Bridge).
- Euromonitor (MCP with citations).
- Mintel (Leap).
- Ipsos (EPA: IPS; free biweekly US tracker).
- Kantar.
- Qualtrics (Edge synthetic panels).
- Forsta (CIP's own source system, a substitute).
- Attest (Results API and read-only MCP).
- Suzy and Toluna.
- Placer.ai.
- Free benchmarks a buyer compares CIP against: Deloitte ConsumerSignals, McKinsey ConsumerWise, PYMNTS, Harris Poll
  (NASDAQ: STGW), U. Michigan and the Conference Board.
- Transaction data: Bloomberg Second Measure, Consumer Edge (+ Earnest), Facteus.

**Emerging**
- Synthetic respondents: Simile ($2B valuation, July 2026), Aaru, Electric Twin.
- AI interviews: Listen Labs, Conveo.

**India**
- Redseer Benchmarks.
- Axis My India CSI.
- LSEG-Ipsos PCSI India.
- Kantar India / NIQ India.
- Market Xcel (a partner, not a rival).
- No Indian vendor runs a weekly, research-grade US retail tracker.

**China** (relevant to the new China survey)
- QuestMobile.
- iResearch.
- Worldpanel China (now Numerator).
- Mintel China.

**Internal**
- Coresight's own public Databank (WordPress + Highcharts) gives shopper profiles away free. Decide whether CIP replaces it.

---

## 4. The strict comparison, by area

Scores and evidence for every row are in the workbook. Here are the findings that decide deals.

### Data (CIP 1.45 vs best competitor 2.90)
- **Lags:**
  - **Sample size.** About 400 a week means ±4.9 pts on the total.
  - **Weighting.** Unweighted by default. Only gender, age and region are raked; no income, education or race.
    Significance is always tested on unweighted counts.
  - **Geography.**
  - **Data quality.** CIP has no fraud screening of its own: the methodology page says "the portal adds no cleaning of
    its own".
  - **Custom questions.** Fielding is manual through Forsta.
  - **Numeric questions.** A dollar question is stored as one answer, "$" = 100% (staging, survey 179, Q22).
- **Missing:**
  - Purchase-data linkage (Numerator, Circana, NIQ).
- **Leads or level:**
  - Retail-sector depth for a survey product.
  - Weekly cadence beats GWI (quarterly) and Prosper (monthly).
  - Reconciliation with the source.

### Analysis (CIP 1.81 vs 2.56)
- **Leads:**
  - Margin of error.
  - Question-version breaks.
- **Level:**
  - Significance (with Qualtrics).
  - Trends.
  - Exact wording with the base.
- **Lags:**
  - Cross-tabs: two cuts, no banners or nets.
  - Audiences: no multi-condition audiences.
  - The "what makes this group different" index across all questions (YouGov).
  - Rolling averages outside cross-tabs.
  - Forecasts (Prosper, eMarketer).
  - Small-base policy: `min_audience: 1` shows groups of one person.
- **Missing:**
  - An applicability check before analysis (Statista).
  - A benchmark overlay against U. Michigan or the Conference Board.

### AI (CIP 1.00 vs 3.00)
- **Level:**
  - Grounding and citations. CIP never takes a number from a model.
- **Leads, but without a benchmark:**
  - Speed.
- **Lags:**
  - Q&A accuracy (section 5).
- **Missing:**
  - Narrative, summaries and slides (GWI Canvas, Circana Analysis Builder, YouGov report builder).
  - Packaged agents (Morning Consult, GWI, NIQ Optiq).
  - Grounding in written reports (Mintel, Euromonitor, eMarketer).
  - Synthetic respondents and AI survey drafting are scored as missing, but the advice is **do not build them**.

### Distribution (CIP 1.30 vs 3.00)
- **Level or leads:**
  - Exports (native editable PowerPoint).
  - Alerts.
- **Lags:**
  - MCP: 6 tools, keys only. Morning Consult adds SQL, discovery, tenants and OAuth.
  - API: no metering, no OpenAPI download.
  - Boards: no external sharing or auto-refresh.
  - Public charts and embeds.
- **Missing:**
  - Connector directory listings.
  - BI and warehouse feeds (Attest, NIQ).
  - Respondent-level data.
  - Background export jobs.

### Enterprise (CIP 1.29 vs 2.86)
- **Leads or level:**
  - Methodology disclosure, with Euromonitor.
- **Lags:**
  - SSO is for staff only.
  - Roles exist but no client is configured, and unknown emails get enterprise.
  - Audit log has no client export.
  - One worker.
- **Missing:**
  - SOC 2 / ISO 27001.
  - Pricing.

### Experience and engineering
- **Leads (no public benchmark):**
  - Speed.
  - Calculation tests against the analysts' PDFs.
- **Lags:**
  - English only (GWI, Statista, Euromonitor localise).
  - Analyst context is not linked next to figures.
  - Code simplicity (section 6).

---

## 5. Defects observed today (staging, through CIP's own MCP connector)

| Question asked | What came back | Why it matters |
|---|---|---|
| "What share of Gen Z shopped at Temu in the latest wave compared with Boomers?" | Boomers only, from a one-off April 2026 apparel study (survey 494). Gen Z was dropped, and it did not use the latest weekly wave | A comparison answered by halves reads as wrong |
| "What is the average price consumers paid for a Thanksgiving turkey?" (never asked) | Q22, a dollar-spend question, shown as "100.0% answered 'Things cost more this year'" across 4 waves (2023-2024) | A made-up answer is worse than "not in the surveys" |
| "How has the share worried about tariffs changed over the last 6 months?" | Two ~6-month halves (12 months in all), each with base n=2,813 | The wrong period, and identical bases that look suspicious |

**A council claim, checked:** reviewers suspected that the Q22 join also corrupts Cross-tab, Trends and Alerts.
- Staging's served Trends for Q22 holds **one wave only**, so the 4-wave join and the borrowed answer label come from Ask's
  concept layer (`api/ask_index.py`), not from the published data.
- A separate real defect showed up: the published data stores Q22 as a single answer, "$" = 100%, with no mean or median.

The deployed staging build may be older than the code in cip-test (several Ask items are "Waiting for deploy" in
status/README.md), so re-run the three questions after the next deploy. They are worth adding to `scripts/ask_golden.yml`.

---

## 6. Code: ponytail audit, ponytail review, simplicity

**Measured:**
- **Code size:** api 5,500 lines; etl 9,156; shared 1,814; frontend 9,697; scripts 2,991; config 2,298 (yml); tests 8,408.
- **Tests:** 523 passed in 37.7 s. `tsc --noEmit` exit 0.
- **Dead code:** 1 function used only by a test; 2 of 310 CSS classes unused.
- **Headers:** every file but one (`scripts/generate_pipeline_diagram.py`) opens with a plain-English header.
- **Python functions with a docstring:** api 63%, etl 67%, shared 61%, scripts 24%.

**ponytail-audit, ranked biggest cut first** (lines are estimates; full list in the workbook's Code audit sheet)

- `yagni` Custom browser speed meter and badge: `perf.ts` (584 lines), `PerfHUD.tsx` (434), `Profiled.tsx`. Chrome DevTools
  and React Profiler already do this. **-950**
- `native` Home-built monitoring dashboard: `api/metrics.py` (706 lines), `Logs.tsx` (541), `api/logs.py`. Azure Monitor /
  Application Insights covers it; keep the raw-log viewer. **-900.** This is a user-requested feature, so the user decides
  before it is cut.
- `yagni` Historical reload loaders for sources frozen since August 2025: `etl/legacy_dwh.py`, `etl/qualtrics_export.py`.
  Move them to an archive branch unless the 2018-2022 history must stay rebuildable. **-673**
- `yagni` SQLite dialect converter: `shared/core/sqlite_compat.py`. One MySQL container for CI and laptops replaces it. **-165**
- `delete` One-shot scripts that already ran: `scripts/move_legacy_source.py`, `scripts/rekey_respondents.py`. **-137**
- `shrink` **Five significance-test copies:** `api/dashboards.py:84`, `etl/serving.py:206`, `etl/weekly_report.py:153`,
  `etl/crosstab_export.py:187` (a Forsta n-1 variant) and `frontend/src/stats.ts`. Replace them with one `shared/stats.py`
  that applies the design effect for weighted figures. **-40.** This is the one that matters most for trust.
- `shrink` Four one-line `load_config()` wrappers around `yaml.safe_load`. These are banned by CLAUDE.md as
  one-expression wrappers. Use one `read_rules(name)`. **-12**
- `shrink` Repeated local `import pandas as pd` (6 in `etl/tracker_line.py`, 5 in `etl/notify.py`). **-9**
- `shrink` Readability, no line saving:
  - `api/main.py` is 1,085 lines with 36 routes; split it into routers by screen family.
  - 13 functions are over 80 lines (`assistant.answer` 181, `publish._build` 124, `loaders.load_definitions` 119).
- `native` `numpy` is used by the API but declared only through pandas. Add it to `requirements.txt`.
- `shrink` `requirements.txt` says `anthropic` is for Ask (`api/assistant.py`). It is used only by `etl/open_ends.py`.
- `delete` 394 MB of old local builds in `web/`. They are git-ignored, so this is local only.

net: -2,893 lines possible (about 7.6% of 38k), -1 dependency possible (`anthropic`, if open_ends uses urllib like ask_model).

**ponytail-review of the uncommitted diff** (7 files: Ask country routing and a small-base note; another session's work)

- `api/assistant.py:L48: shrink: SMALL_BASE = 50 redefined. from etl.serving import SMALL_BASE (already shared).`
- `api/ask_reader.py:L16-20: shrink: second reader of countries.yml. Reuse shared/data/payloads.py COUNTRIES.`
- `api/ask_reader.py:L143-144: shrink: loop of per-country subs. One ANY_COUNTRY regex built once.`
- Out of scope, so routed to a normal review: the new question log opens a file inside `ANSWERS_LOCK` on every answer,
  and stores the question text even though its comment says "no names kept". People type names into questions.

net: -4 lines possible.

**Is it "simple code solving complex problems"?** Mostly yes:
- One prebuilt book feeds every screen, the API and MCP.
- Rules live in `config/*.yml`.
- Files open with plain-English headers.

What stops a non-programmer from following the flow end to end:
- the duplicated statistics;
- the 1,085-line `api/main.py`;
- the long functions;
- the ~2,400 lines of tooling that the platform already provides.

---

## 7. Council verdict (summary; full text in 02-council-verdict.md)

- **Agree:**
  - Trust is the most dangerous lag.
  - "Not in the surveys" must be a first-class answer.
  - Don't race on scale, markets or synthetic panels.
  - The moat is Ask grounded in Coresight's reports.
  - Merge the z-tests.
  - The sales basics (pricing, one set of scale numbers, a configured client) are missing.
- **Clash:**
  - SOC 2 now or later. The chairman sided with now, because Type I takes months.
  - Expand (buy-side alt-data, a weekly India wave, a free MCP funnel, licensing data to synthetic vendors) or focus.
    Four of five said focus.
- **Blind spots found in peer review:**
  - Data rights: the Forsta panel terms for resale and API/MCP, and PIPL for the China data.
  - Commissioned-study leakage.
  - Design-effect correction for weighted significance.
  - Opt-in panel fraud.
  - A public benchmark against U. Michigan.
- **First step:** unknown emails get no access, and each commissioned study is visible only to its client.

---

## 8. Suggestion box: how CIP leads its segment (full list with KPIs and owners in the workbook)

**The segment to lead:** the weekly US retail shopper, measured honestly, inside the client's own AI tools, explained by
Coresight analysts. No vendor combines weekly retail-sector rotation, research-grade uncertainty, MCP and an analyst brand.

- **Day 1:**
  - Unknown emails refused.
  - Commissioned studies visible only to their client.
  - `min_audience` 10 for client tiers.
  - First client configured.
- **Days 0-30:**
  - Fix the three Ask defects and the "$ = 100%" numeric questions.
  - 50 real analyst questions as the release gate.
  - One shared statistics module.
  - One source for scale numbers.
  - Legal opinion on data rights.
  - Sign the SOC 2 Type I readiness contract.
- **Days 30-90:**
  - OAuth on MCP, then a directory listing.
  - Ask grounded in Coresight reports, with citations.
  - Board "draft summary" before PowerPoint export.
  - Weighting with income and education, effective n, and weighted by default for clients.
  - Pooled four weeks as the default for subgroups.
  - A U. Michigan benchmark.
  - Bot and attention screening.
  - Per-client SSO and SCIM.
- **Days 90-180:**
  - Paid "ask this next Monday" custom questions.
  - A retail nowcast back-tested against Census retail sales.
  - Parquet / Snowflake feed and a Power BI template.
  - Embeddable chart cards on every Coresight article.
  - Pricing: Core bundled, Pro per seat, API/MCP metered.
- **Do not chase:**
  - synthetic respondents;
  - 50-country breadth;
  - receipt panels;
  - DIY survey building.
- **Success at 6 months:** 3-5 paying subscribers using CIP inside their subscription, and a log of the questions Ask
  could not answer. That log is the roadmap.

---

## 9. Limits of this evaluation

- No competitor app behind a sign-in was opened (no logins, trials or forms). Competitor scores rest on public pages and
  press, so a blank means "not shown publicly", not "absent".
- Ownership and listing are from public reports. Check filings before quoting externally.
- Agent Reach answered one search, then its provider failed. REA analysed three public bundles and refused two app shells.
- The workbook's formulas were checked with the `formulas` engine: 517 formulas, 0 errors. LibreOffice is not installed on
  this Mac, so the xlsx skill's own recalc step could not run. Excel recomputes everything on open (fullCalcOnLoad).
- The staging probes test the deployed build. status/README.md (Stuck) says staging runs build 1216c61e, behind cip-stg, so the local search model and the 12 Nov Ask fixes are not on it, and staging runs Ask without the AI model. Re-run the three probes after the next deploy before calling them current defects.
