# Council brief: Coresight Consumer Insight Portal (CIP) vs competitors, 12 Nov 2026

## The decision
Coresight Research (a US retail-research subscription firm, ~$ small, analysts in US + India build team) is preparing CIP for external
clients. Question for the council: **What must Coresight do in the next 6 months for CIP to lead its market segment, which lags are
most dangerous, and which competitor moves must it answer vs ignore?** Stakes: CIP is about to be sold to retail/brand clients who
already buy Morning Consult, YouGov, GWI, Statista, Numerator or Circana.

## CIP today (verified in code and on staging, 12 Nov 2026)
- Data: weekly US Consumer Survey since Dec 2020 (+2018-2020 annual/ad hoc), ~400 qualified US adults/week (wave 533 on 9 Nov: n=404),
  370+ waves, ~190k responses; China weekly survey (Baidu QSS, n≈550/week) added Oct 2026; client-commissioned studies (T-Mobile etc).
  Online opt-in panel (Forsta/Decipher source 114). Unweighted by default; a Census-weighted switch (raked gender x age x region, ACS
  2023, trimmed 0.2-5) exists. Significance: two-proportion z-test, p<0.05, Benjamini-Hochberg FDR, min 30 per side. Small base <50 flagged.
- Screens (30): Home, Survey library, wave Overview, Question explorer, Cross-tab (two cuts, 1 or 4 pooled weeks), Trends (with MoE),
  Compare waves, Audience index (over/under-index), What changed (significant movers), Weekly report (matches the analysts' PDF, Figure 6
  test), Sector databank, Retailer databank (shopper profiles), In-store vs online, Trackers, Expected vs actual, Survey preview, Search
  (typo/synonym tolerant), Ask Coresight (rules + local embedding model, exact figures with base and chart, no LLM needed, ms latency;
  optional gpt-4o-mini reading; $0.50/month cap), Boards (pin, comment, PPTX deck), Alerts (significant moves to Teams/email), Saved
  views, Exports (CSV/XLSX/native editable PPTX), Methodology page, What's new, API guide, Account, admin Logs/Fieldwork/Access/Upload.
- Distribution: public read API with per-user API keys + MCP connector (6 tools: ask, search_questions, list_waves, question_results,
  question_trend, crosstab) usable from Claude etc. Tiers demo/core/professional/enterprise, roles, per-client menus, survey visibility
  per client, audit log, rate limits, OIDC SSO (Coresight staff IdP). No client is configured yet (clients: {}); unknown emails get enterprise.
- Open-ends coded into themes (Claude or frequency fallback). News events annotated on weekly-report charts.
- Stack: React 19 + Next 16 static export + react-router SPA, ECharts; FastAPI + MySQL (Azure) ; ETL publishes prebuilt gzip JSON that
  nginx serves (p95 < 0.35 s). ~38k lines of code (api 5.5k, etl 9.2k, shared 1.8k, frontend 9.7k, scripts 3k, config 2.3k yml),
  8.4k lines of tests: 523 tests pass, TypeScript type-check clean. Single-worker Azure App Service P0v3 (1 vCPU, 4 GB).
- Observed defects on staging today (Ask Coresight via MCP):
  1. "What share of Gen Z shopped at Temu in the latest wave compared with Boomers?" -> answered Boomers only, from a one-off April
     apparel study, not the latest weekly wave; Gen Z dropped.
  2. "Average price paid for a Thanksgiving turkey?" (not asked) -> instead of "not in the surveys", returned a dollar-spend question
     (Q22) shown as "100.0% answered 'Things cost more this year'" across 4 waves joined under a reused code.
  3. "Last 6 months" was read as two ~6-month halves covering 12 months; both halves show the same base n=2,813.
- Code-quality audit: 4 separate two-proportion z-test implementations (api/dashboards.py, etl/serving.py, etl/weekly_report.py,
  etl/crosstab_export.py) + a 5th in frontend/src/stats.ts; ~1,000 lines of a custom browser perf meter; ~1,400 lines of a home-built
  monitoring dashboard (Azure Monitor exists); api/main.py 1,085 lines; 13 functions > 80 lines (assistant.answer 181).
- Known gaps: no BI/warehouse connector (Snowflake/Power BI), no respondent-level data delivery, no recontact/custom-question path,
  no audience applicability check before analysis, no AI-written narrative/slides, Ask not grounded in Coresight's written reports,
  no SOC 2/ISO collateral, external client IdP (SAML per tenant) and SCIM missing, sample ~400/week (MoE ±4.9 pts total), US + China only,
  pricing/packaging undecided, public scale numbers inconsistent across docs.

## Competitors (public evidence, Oct-Nov 2026)
- Morning Consult (US, private): 30k interviews/day, 40+ markets, daily ICS; AI Research Agents; MCP connector for Claude (alpha,
  Enterprise, free to Intelligence subscribers) with SQL query tool + tenant switching; Gemini coming; aggregate daily-data API.
- YouGov (UK, LSE-listed): Profiles 30M+ panel weekly refresh, BrandIndex daily 56 markets; Profiles AI agent; MCP for Profiles + Crunch
  (Jun 2026) and BrandIndex (Oct 2026, licensed separately); owns Crunch (survey DB, sub-second) and KnowledgeHound.
- GWI (UK, private): 50+ markets, quarterly waves; Agent Spark live in ChatGPT/Claude/Copilot (Jan 2026); Spark MCP v0.5 (Sep 2026),
  API priced by consumption; Oct 2026 "agentic portfolio".
- Statista Consumer Insights (DE, Ströer, unit reportedly being divested): 3M+ interviews, 30-56 countries; Consumer AI chat (now
  streaming), target groups with applicability check + population preview, crosstabs, boards, async export queue (REA route table
  12 Nov); Statista MCP + Connect API, Claude/Copilot/Perplexity, citations.
- CivicScience (US, private): ~1-5M responses/day, 130M profiles, 2,000+ always-on questions, 10+ yrs, real-time alerts, InsightStore,
  free daily Poll of the Day (Apr 2026), weighted.
- Numerator / Worldpanel by Numerator (Kantar, private): receipts panel 200k+, merged with Worldpanel (5,800 staff, ~5bn consumers);
  free monthly Consumer Sentiment Tracker (6,000+ responses/month); Verified Voices (survey verified buyers); Nexa AI.
- Circana (US, private): receipt+loyalty+scan+survey; Liquid Survey AI question writer (Jun 2026); Unify+ Analysis Builder insights
  agent (Q4 2026).
- NIQ (US, NYSE-listed 2025): Homescan 250k HH 25 countries; Ask Arthur -> NIQ Optiq agent with "Optiq Bridge" to enterprise LLMs.
- Euromonitor Passport (UK, private): AI rebuild Jun 2026, MCP for Claude/ChatGPT with citations, Copilot agent; VoC ~1,000/market quota-matched.
- Mintel (UK, private): Leap closed-loop AI with links to sources; China Consumers and AI 2026 report.
- eMarketer (US, Axel Springer): AI research assistant, EM Connect into AI tools, AI Visibility Index.
- Prosper Insights & Analytics (US, private): monthly ~7,500-8,000 US adults since 2002, NRF's partner, data on AWS Marketplace, US Signals forecasts.
- Free public benchmarks: U. Michigan (monthly), Conference Board, Deloitte ConsumerSignals (1,000/country x 20 countries monthly,
  public dashboard), McKinsey ConsumerWise (quarterly, n≈4,000), Ipsos Consumer Tracker (biweekly since 2020, public toplines),
  PYMNTS (monthly, weighted, n≈2,500-2,900), Harris Poll weekly data (Stagwell, NASDAQ).
- Survey platforms: Qualtrics (Edge synthetic panels, 0.07 SD claim), Forsta (CIP's own source; reporting/PPT), Displayr (Research Agent,
  $4,199/user/yr enterprise), Attest (Results API to BI + read-only MCP), Suzy, quantilope, Toluna (synthetic personas), SurveyMonkey.
- Synthetic/AI-native: Simile ($200M at $2B, Jul 2026), Aaru ($1B valuation), Electric Twin ($14M), Listen Labs ($69M), Conveo ($50M).
- Transaction data: Bloomberg Second Measure, Consumer Edge (+Earnest), Facteus; Placer.ai (foot traffic + surveys).
- India: Redseer Benchmarks (monthly AI market intelligence, 20+ sectors), Axis My India CSI (monthly), LSEG-Ipsos PCSI India,
  Kantar India, NIQ India, Market Xcel panel. China: QuestMobile (mobile MAU), iResearch (UserTracker), Kantar Worldpanel China (now
  Numerator), CBNData, Mintel China.
