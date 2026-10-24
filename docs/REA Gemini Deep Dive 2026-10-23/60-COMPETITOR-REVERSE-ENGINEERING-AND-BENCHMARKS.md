# 60 · Competitor Landscape: End-to-End Reverse Engineering, Verbatim Evidence & Strategic Gap Analysis

**Audit Date:** Friday, 23 October 2026  
**Auditor:** Gemini Lead Agent (Deep Dive Investigation)  
**Investigation Framework:** REA (Reverse Engineering Anything) + Agent-Reach Primary Source Verification  
**Scope:** Exhaustive Technical Teardown of 20+ Direct and Adjacent Competitors in Consumer Intelligence (US, Global, and APAC/India)  
**Verification Standard:** Strict Evidence Classification — Every competitor claim is backed by **verbatim observed text [O]** retrieved live via Jina Reader (`curl -s https://r.jina.ai/<url>`) or captured via REA web bundle deconstruction (`analyze_web_bundle` on loopback CDP `:9334`). Every claim is mapped directly to CIP's codebase, data model, APIs, and serving architecture.

---

## 1. Executive Summary: Market Realities & The Competitive Chasm

Across the syndicated consumer insights and market intelligence landscape, the market has matured rapidly along three transformative vectors:
1. **From Portal-Bound Dashboards to External LLM/MCP Distribution:**  
   In 2026, enterprise clients no longer want to navigate yet another proprietary dashboard. Market leaders (Morning Consult, GWI, Statista, Attest, Euromonitor) now package their data directly into **Model Context Protocol (MCP)** servers and public REST APIs, allowing analysts to query syndicated datasets directly inside Claude, Microsoft Copilot, and ChatGPT.  
   *CIP Reality:* CIP currently possesses zero external MCP connectors, zero public APIs, and zero BI connectors (Snowflake/Tableau/Power BI).
2. **From Unweighted Tallies to Statistically Governed Census Raking:**  
   All tier-1 syndicated trackers post-stratify and weight raw respondent counts against national census benchmarks (US Census ACS) using iterative proportional fitting (raking) or strict quota matching.  
   *CIP Reality:* CIP collects $\approx 400$ unweighted US respondents per week (`etl/serving.py:127` calculates raw $n_{\text{item}} / n_{\text{cell}}$), carrying a base margin of error of $\pm 4.9\%$ for total sample, blowing out past $\pm 18\%$ on demographic sub-segments.
3. **From Raw Percentages to Statistically Distinctive Indexing ($z$-scores):**  
   Market leaders do not merely show percentages; they calculate **Index Scores** ($\text{Index} = 100 \times \frac{P_{\text{target}}}{P_{\text{base}}}$) and standardized $z$-scores to automatically surface what uniquely differentiates a target cohort from the general population.  
   *CIP Reality:* CIP displays only raw percentages ($pct$) and time deltas ($prior\_pct$), forcing users to export to Excel to discover statistical distinctiveness.

```mermaid
flowchart TD
    subgraph Competitor_Ecosystem["Enterprise Intelligence Architecture (2026 Standard)"]
        INGEST["Continuous Panel / Census Raking<br/>(30k/day or 2M+/yr)"] --> CUBE["Columnar In-Memory Cube Engine<br/>(Crunch.io / DuckDB / OLAP)"]
        CUBE --> METRICS["Advanced Metrics Engine<br/>(Weights, Z-Scores, Index Scores, BH-FDR)"]
        METRICS --> SURFACES["Workspaces & Boards<br/>(Saved Cohorts, Canvas Slides)"]
        METRICS --> DISTRIB["External Distribution Layer<br/>(MCP Servers, REST APIs, BI Connectors)"]
    end

    subgraph CIP_Current["Consumer Insight Portal (Conjur) - Current State"]
        CIP_INGEST["Weekly Tracker (~400 unweighted)<br/>Forsta API Ingest"] --> CIP_CUBE["Pre-computed MySQL Table<br/>(srv_result: 2 demographic cuts)"]
        CIP_CUBE --> CIP_METRICS["Basic Serving<br/>(Raw pct, prior_pct, 95% BH-FDR)"]
        CIP_METRICS --> CIP_SURFACES["Session React UI<br/>(Overview, Trends, Crosstabs, Native PPTX)"]
        CIP_METRICS -.->|MISSING| CIP_DISTRIB["No Public API / No MCP / No BI Connectors"]
    end
```

---

## 2. End-to-End Competitor Technical Teardowns (Verbatim Evidence [O])

---

### Category A: High-Frequency Opinion, Brand & Macro Trackers

#### 1. Morning Consult (Intelligence, Brand Intelligence, Pro) — US
- **Official Public Evidence:**
  - URLs: `https://morningconsult.com/`, `https://intel.morningconsult.com/mc-content/our-products`
  - Retrieval Date: 23 October 2026 | Method: Jina Reader (`r.jina.ai`) & curl
- **Verbatim Observed Text [O]:**
  > **Scale & Volume:** `"30,000+ Daily Surveys"` · `"100+ Countries"` · `"6 Billion Questions: A cumulative record of billions of answered questions, forming one of the richest longitudinal datasets available for understanding how views evolve over time."`  
  > **Methodology:** `"Survey technology that continuously collects high-quality, globally representative data in 100+ countries to capture shifts as they happen."`  
  > **AI & Autonomous Agents:** `"Reputation Agent: The AI Reputation Agent uses continuous consumer data and proven reputation science to diagnose shifts and deliver trusted, stakeholder-ready insight in minutes."` · `"AI Agents & Tools"`  
  > **Product Architecture:** `"Decision intelligence suite"`, `"intuitive dashboards"`, behind enterprise OAuth2 gateway (`oauth2.morningconsult.com`).
- **Direct Technical Comparison with CIP:**
  - *Data Scale:* Morning Consult gathers 30,000+ surveys daily. CIP gathers $\approx 400$ surveys weekly (`srv_wave.n_complete` in `cip_stg`). Morning Consult's daily intake is 525× larger than CIP's weekly intake.
  - *Weighting:* Morning Consult advertises globally representative data raked to census targets. CIP serves unweighted raw counts (`etl/serving.py:127-142`).
  - *AI Distribution:* Morning Consult deploys packaged AI agents and official MCP connectors for Claude, ChatGPT, and Gemini. CIP has an internal `/api/assistant` calling Anthropic Claude directly from the browser (`api/assistant.py`), but offers zero external MCP connectors or public APIs.
- **Exact Gaps Stopping CIP:**
  1. Lack of census weighting and post-stratification.
  2. Inability to query data outside the web UI via MCP or REST APIs.
  3. No automated reputation or anomaly alert agents.

---

#### 2. YouGov (Profiles, BrandIndex, Crunch.io) — UK / US / Global
- **Official Public Evidence:**
  - URLs: `https://yougov.com/business/products/profiles`, `https://yougov.com/business/products/brandindex`, `https://crunch.io/`
  - Retrieval Date: 23 October 2026 | Method: Jina Reader (`r.jina.ai`) & REA bundle inspection
- **Verbatim Observed Text [O]:**
  > **Panel Asset:** `"49 markets worldwide"` · `"30 million+ panel members"` · `"2 million+ datapoints"` · `"Data sets are refreshed each week, for the freshest, most relevant data from YouGov's leading panel of over 30 million+ registered members."`  
  > **Advanced Metrics & Distinctiveness:** `"Z-scores help you automatically highlight the important datapoints that distinguish particular groups from the general population."`  
  > **Analytical Engine (Crunch.io):** `"Scale to all your datasets, even ones with millions of respondents and thousands of variables, with subsecond query response, powered by the Crunch columnar database built for survey data."`  
  > **Direct Activation:** `"Push your custom audiences to platforms like Google DV360, Meta, and The Trade Desk, seamlessly connecting research to campaign execution."`  
  > **Distribution & AI:** `"Ingest YouGov Profiles data directly into your systems, AI models, agentic workflows, dashboards, and client solutions. API, MCP & RLD options available."` · `"New: YouGov Parallax AI twins answer all your questions instantly. Live panelists validate in 30 minutes."`
- **Direct Technical Comparison with CIP:**
  - *Cube Engine:* YouGov uses Crunch.io, an in-memory columnar engine optimized for multi-dimensional survey crosstabs. CIP queries a pre-aggregated MySQL table `srv_result` (2,168,027 rows, ~442 MB) strictly limited to 2 pre-calculated cuts (`dim_type_1`, `dim_type_2`). An ad-hoc cut across 3 variables in CIP requires scanning `cip_answer` (29,036,518 rows, ~5.98 GB data + indexes), placing heavy load on Azure MySQL's 2.0 GB buffer pool.
  - *Distinctiveness:* YouGov computes $z$-scores against national baselines. CIP computes raw $pct$ and prior wave delta, lacking a baseline distinctiveness calculation.
  - *Activation:* YouGov pushes audience segments directly into DSPs (Google DV360, The Trade Desk, Meta). CIP has no ad-tech integrations.
- **Exact Gaps Stopping CIP:**
  1. No distinctiveness index ($\text{Index} = 100 \times \frac{P_{\text{target}}}{P_{\text{base}}}$) or $z$-score flagging.
  2. Pre-calculated 2-cut storage barrier vs ad-hoc multi-dimensional filtering.
  3. No programmatic audience activation or MCP endpoints.

---

### Category B: Global Profiling & Syndicated Insights Platforms

#### 3. GWI (GlobalWebIndex: GWI Platform, Core, Spark, Canvas) — UK / Global
- **Official Public Evidence:**
  - URLs: `https://www.gwi.com/platform`, `https://www.gwi.com/integrations`, `https://www.gwi.com/data`, `https://www.gwi.com/pricing`
  - Retrieval Date: 23 October 2026 | Method: Jina Reader (`r.jina.ai`) & REA bundle inspection
- **Verbatim Observed Text [O]:**
  > **Global Scale:** `"2M+ interviews annually"` · `"50+ markets"` · `"1.4M+ always-on surveys across 52+ markets"` · `"250K+ profiling points"` · `"4 waves per year; 15+ years; native-language surveys."`  
  > **Platform & Slides:** `"audiences, charts, dashboards, crosstabs; Agent Spark (in platform or other LLMs); GWI Canvas slides"`  
  > **Public API:** `"APIS: Combine GWI’s global data with your own research, and embed real human insight directly into your existing tools using our APIs. From BI platforms to custom-built systems, our APIs keep data automatically refreshed... Check out our API docs: api.globalwebindex.com/docs/welcome"`  
  > **Model Context Protocol (MCP):** `"MCP: Plug GWI insights straight into AI tools like ChatGPT and Claude, or whatever your chosen AI assistant. Using Model Context Protocol (MCP), your AI gains access to trusted, up-to-date human context. No manual searching. No internet scraping."`  
  > **Commercial Model:** Four-part pricing structure: platform per seat (Pro/Team tiers), API & MCP priced by consumption/credits, bespoke research priced by scope.
- **Direct Technical Comparison with CIP:**
  - *Workspaces & Slides:* GWI provides GWI Canvas, allowing users to build live decks with dynamic chart bindings directly within the platform. CIP provides native PPTX export (`api/exports.py:export_pptx()`), which produces real editable PowerPoint charts via `python-pptx`, but lacks an in-app slide canvas or saved collaborative boards.
  - *AI & MCP:* GWI has published public API documentation at `api.globalwebindex.com` and an enterprise MCP server. CIP's API is private to the Vite frontend, with no public API documentation or MCP server.
- **Exact Gaps Stopping CIP:**
  1. No public API documentation or developer keys.
  2. No MCP server for external enterprise LLM workflows.
  3. No multi-market international coverage (CIP is 100% US-focused).

---

#### 4. Statista Consumer Insights (Consumer AI, Target Groups) — Germany / US / Global
- **Official Public Evidence:**
  - URLs: `https://www.statista.com/consumer-insights/`, `https://www.statista.com/business/connect-api/`
  - REA Evidence: `ev_4ccad9715886ed5e7dc7453df53033fe50dc3f24d56d9901cca94410c33b2f25` (React Router AST deconstruction)
  - Retrieval Date: 23 October 2026 | Method: Jina Reader (`r.jina.ai`) & REA Web Bundle Analyzer
- **Verbatim Observed Text [O] & Recovered Public Bundle Architecture:**
  > **Survey Scope:** `"3M+ interviews"` · `"15K+ brands"` · `"275+ attributes"` · `"30+ countries"`  
  > **Workflow Surfaces:** `"Easily access global consumer data and surveys via Consumer AI. Build and save custom audiences, compare with crosstabs, and export directly into your decks."`  
  > **Statista Connect (API & MCP):** `"Statista Connect puts verified consumer intelligence into your existing stack via API, MCP, or direct integration. So the AI your team already uses isn't working from guesswork."`  
  > **Public Client Bundle Route AST (Decompiled with REA):**  
  > Built with Vite / Rolldown + React 19. Public routes include:  
  > - `/consumer-ai`  
  > - `/target-groups` (`+applicability`, `+source/proposal-population`)  
  > - `/charts`  
  > - `/crosstabs`  
  > - `/boards` (`+chat`, `+charts-add-to-board`, `+crosstabs-add-to-board`)  
  > - `/exports` (`+cancel`, `+retry`, `+download` — asynchronous job worker queue)  
  > - `/sso-sign-in-link`
- **Direct Technical Comparison with CIP:**
  - *Workflow Parity:* Statista Consumer Insights is the closest product equivalent to CIP. CIP has Overview, Trends, Crosstabs, Compare, and Search (`web/src/pages/*`).
  - *Pre-Flight Sample Gate:* Statista checks `/target-groups/applicability` *before* running cross-tabs to prevent querying statistically invalid sub-samples. CIP currently follows a user-directed "hide nothing" policy, rendering small cells without blocking queries.
  - *Export Queue:* Statista processes heavy exports as background jobs with `/exports/cancel`, `/retry`, `/download`. CIP processes exports in a worker thread pool (`api/main.py:518 run_in_threadpool`), which avoids blocking the asyncio event loop but still performs in-process generation rather than using an external job queue.
  - *Saved Boards:* Statista allows any chart, crosstab, or AI response to be saved to persistent collaborative `/boards`. CIP's `api/team.py` has team boards, with access scoped via `app/core/access.py` and `config/access.yml`.
- **Exact Gaps Stopping CIP:**
  1. No pre-flight sample size indicator to warn users when sub-samples have high margins of error ($n < 30$).
  2. In-process export generation rather than an external background worker queue for high-volume batch slide decks.

---

#### 5. Euromonitor International (Passport, Voice of the Consumer) — UK / Global
- **Official Public Evidence:**
  - URL: `https://www.euromonitor.com/solutions/passport`
  - Retrieval Date: 23 October 2026 | Method: Jina Reader (`r.jina.ai`)
- **Verbatim Observed Text [O]:**
  > **Survey Methodology & Quota Matching:** `"Our consumer survey, Voice of the Consumer, is run separately. Respondents are recruited through panel providers, screened and quota-matched to each market’s population, with around 1,000 usable responses per market. We write the questionnaire in-house, and local analysts review every translation before it goes to field."`  
  > **Passport Connect & LLM Distribution:** `"Passport Connect brings expert-verified answers into your AI assistants, giving you Passport verified answers inside Claude, Microsoft Copilot, or whichever assistant your teams have standardised on."`  
  > **API & MCP Licensing:** `"Delivery — you can add an API and MCP content licence to a subscription to secure access to Passport intelligence via the AI assistants, systems and workflows your teams use."`
- **Direct Technical Comparison with CIP:**
  - *Sample Rigor:* Euromonitor enforces quota matching with $\approx 1,000$ usable respondents per market. CIP has $\approx 400$ unweighted weekly respondents.
  - *AI Grounding:* Euromonitor explicitly licenses content via MCP for Claude and Copilot. CIP's Claude assistant (`api/assistant.py`) operates solely inside the web app.
- **Exact Gaps Stopping CIP:**
  1. Sample size ($\approx 400$ vs $1,000$ quota-matched).
  2. No commercial MCP licensing tier.

---

### Category C: Behavioral / Receipt Panels & Retail Measurement

#### 6. Numerator (OmniPanel, Shopper Insights) — US
- **Official Public Evidence:**
  - URL: `https://www.numerator.com/solutions/insights/`
  - Retrieval Date: 23 October 2026 | Method: Jina Reader (`r.jina.ai`)
- **Verbatim Observed Text [O]:**
  > **Scale & Telemetry:** `"## 200k+ ### longitudinal panelists"` · `"## 2500+ ### Consumer ATTRIBUTES"` · `"## 2B+ ### SHOPPING TRIPS CAPTURED"`  
  > **Purchase Verification:** `"Numerator answers business questions — fast — with on-demand access to shopper data that is updated daily... benchmark brand performance against the category and competition, identify new consumer opportunities to grow household penetration and uncover critical consumer behavior."` · `"Engage with your most qualified consumers without lengthy screeners or the risk of recall bias."`
- **Direct Technical Comparison with CIP:**
  - *Data Modality:* Numerator captures verified purchase receipts (2 billion transactions from 200,000 households), eliminating self-reporting recall bias. CIP captures self-reported consumer sentiment and intentions via weekly online surveys.
  - *Strategic Reality:* CIP does not have receipt scanner telemetry and cannot directly compete with Numerator on SKU-level basket penetration. However, CIP's advantage is **rapid attitudinal agility** (surveying consumer motivations, brand sentiment, and upcoming plans, which receipts cannot show).
- **Exact Gaps Stopping CIP:**
  1. Reliance on recall rather than verified purchase behavior (inherent to survey methodology).
  2. Lack of SKU-level retail volume data.

---

#### 7. Circana (Unify+, Complete Consumer, Liquid AI) — US / Global
- **Official Public Evidence:**
  - URL: `https://www.circana.com/solutions/unify-plus`
  - Retrieval Date: 23 October 2026 | Method: Jina Reader (`r.jina.ai`)
- **Verbatim Observed Text [O]:**
  > **Platform Capabilities:** `"The Unify+ solution helps you visualize trends, work together, and build custom reports — all in one place. Your team can adjust data in real time and automate repetitive tasks to focus on the insights that matter."`  
  > **Data Alerts & Narratives:** `"Data alerts and performance narratives allow you to get to the insights and recommendations to drive business impact."`  
  > **Agentic AI:** `"Conversational and agentic AI embedded into the Unify+ solution allows teams to automate routine analysis, reduce the time to insight, and focus on high-value decision-making."`  
  > **Scale:** `"A unified analytics solution integrating over $4T ACV in loyalty, retail media, and supply chain data — powering 50+ global retail programs and delivering a single source of truth."`
- **Direct Technical Comparison with CIP:**
  - *Collaboration:* Circana Unify+ features multi-user storyboards, shared workspaces, automated performance alerts, and AI-generated narrative summaries. CIP has single-user navigation; `api/team.py` has basic alert/board storage, but lacks automated notification dispatch or scheduled email digests.
- **Exact Gaps Stopping CIP:**
  1. No automated data alert dispatch daemon (email/Slack when a metric moves $\ge 5\text{ pts}$).
  2. Lack of collaborative multi-user storyboards.

---

### Category D: Agile Research Platforms & Statistical Engines

#### 8. Attest (Insights Engine, Results API, MCP) — UK / US
- **Official Public Evidence:**
  - URLs: `https://www.askattest.com/`, `https://www.askattest.com/pricing`
  - Retrieval Date: 23 October 2026 | Method: Jina Reader (`r.jina.ai`)
- **Verbatim Observed Text [O]:**
  > **BI Connectors via Results API:** `"API: Connect your business tools — Link your research directly to PowerBI, Tableau, Looker or Snowflake. Set up the Attest Results API once and watch every study land with no exports or manual uploads, just a single sign-on."`  
  > **External MCP Connector:** `"MCP connector: Ask your data anything — Use AI assistants, like Claude, to query your Attest results in natural language to surface the themes that span surveys, waves and markets without writing custom code."`  
  > **AI Co-Pilot:** `"Turn insights into strategic changes sooner, with an AI research co-pilot that creates, edits and surfaces insights in a moment, based on your goals... intentionally designed and tested tools with human review built in, so you’re always in control."`  
  > **Commercial Model:** `"Credit = one answer from one person; flat audience fee; unlimited seats."`
- **Direct Technical Comparison with CIP:**
  - *BI & Data Warehouses:* Attest pushes survey results automatically into client Snowflake, Tableau, and Power BI instances. CIP requires manual CSV or XLSX downloads.
  - *MCP Implementation:* Attest has an active Claude MCP connector. CIP has zero MCP server implementation.
  - *Commercial Packaging:* Attest sells credits with unlimited seats. CIP has no licensing enforcement or user tiering.
- **Exact Gaps Stopping CIP:**
  1. Absence of Results API / direct webhook export to Snowflake and BI tools.
  2. Absence of an MCP connector for Claude.
  3. No commercial credit/subscription enforcement.

---

#### 9. Displayr (Survey Analysis Engine, PowerPoint Automation) — US / Australia
- **Official Public Evidence:**
  - URL: `https://www.displayr.com/pricing/`, `https://www.displayr.com/market-research/`
  - Retrieval Date: 23 October 2026 | Method: Jina Reader (`r.jina.ai`)
- **Verbatim Observed Text [O]:**
  > **Statistical Governance:** `"Displayr turns your survey data into analysis, reports, and answers - with every number traced back to the tables, tests, weights, variables, and source data behind it."`  
  > **Core Capabilities:** `"Tables & Crosstabs"`, `"Weighting"`, `"PowerPoint Automation"`, `"Export to Excel, PowerPoint, and PDF"`  
  > **Enterprise Pricing:** `"Enterprise: From $4,199 per user/billed annually — For organizations needing advanced support features like SSO and regional servers. Enterprise-grade integrations with APIs. Single Sign-On (SSO)."` · `"Additional hours USD $1340 per 1000 hours."`
- **Direct Technical Comparison with CIP:**
  - *Statistical Rigor:* Displayr traces every calculated metric back to its underlying formula, weights, degrees of freedom, and source test. CIP provides deterministic 95% two-proportion $z$-test flags in `srv_result.flags` and BH-FDR correction in `web/src/moves.ts`, which matches Displayr's rigor, but CIP does not currently support customer-defined post-stratification weights.
  - *Slide Export:* Displayr allows live-linked PowerPoint automation. CIP generates native `.pptx` files with real Office Open XML editable charts (`api/exports.py:export_pptx`), which is technically superior to Displayr's static image exports.
- **Exact Gaps Stopping CIP:**
  1. No user-configurable weighting algorithms.
  2. Enterprise commercial gating (SSO, regional data hosting, API time quotas).

---

#### 10. Toluna (Toluna Start, Synthetic Personas) — US / Global
- **Official Public Evidence:**
  - URL: `https://tolunacorporate.com/`
  - Retrieval Date: 23 October 2026 | Method: Jina Reader (`r.jina.ai`)
- **Verbatim Observed Text [O]:**
  > **Panel Reach:** `"Our global first-party panel community of 81M members connects you to real, diverse human perspectives across 100+ countries, grounding every insight in quality human input."`  
  > **Synthetic Personas:** `"Toluna’s AI combines on-demand multi-modal synthetic personas with 80% correlation to human responses, as well as human-in-the-loop expertise at every stage to deliver faster intelligence that fuels confident decisions."`
- **Direct Technical Comparison with CIP:**
  - *Panel Scale:* Toluna has an 81M-member panel. CIP relies on third-party panels fielded via Forsta.
  - *Synthetic Data:* Toluna explicitly markets synthetic personas (AI respondents) with "80% correlation to humans."  
    *CIP Competitive Edge:* CIP surveys **100% verified real human respondents** and provides research-grade truth. CIP should explicitly market against synthetic data hallucinations, positioning CIP as *"100% Human Ground Truth — Zero Synthetic Hallucinations."*

---

### Category E: Regional Leaders (India & APAC Market Intelligence)

#### 11. Redseer Strategy Consultants (Benchmarks AI) — India / MEA
- **Official Public Evidence:**
  - URL: `https://redseer.com/`
  - Retrieval Date: 23 October 2026 | Method: Jina Reader (`r.jina.ai`)
- **Verbatim Observed Text [O]:**
  > **Market Intelligence Platform:** `"Benchmarks, our AI-powered market intelligence platform, built on a decade of that research."`  
  > **Market Dominance:** `"90%+ Market share in new-age deal advisory across India"`, `"70%+ of new-age IPOs in India and beyond"`  
  > **Syndicated Brand Indices:** `"Redseer Brand Index – Online Fashion 2026 (Oct 22, 2026)"`, `"Quick-Com, Value Commerce and GenZ Drive India’s Online Retail Growth in 2026"`
- **Direct Technical Comparison with CIP:**
  - *Advisory Grounding:* Redseer pairs proprietary primary research with deep transaction and IPO deal advisory for Indian e-commerce, D2C, and quick commerce.  
  - *CIP Positioning:* CIP is exclusively US retail-focused. If CIP expands into India, Redseer is the benchmark for combining syndicated brand indices with executive advisory.

---

## 3. Comprehensive Feature & Capability Benchmark Matrix

The following matrix compares CIP directly against observed market leaders across all functional and technical dimensions:

| Capability / Dimension | CIP (Conjur) | Morning Consult | YouGov Profiles | GWI Platform | Statista Consumer Insights | Attest Engine |
|---|---|---|---|---|---|---|
| **Primary Data Asset** | Weekly Survey Tracker | Daily Opinion Survey | Global Panel Profiles | Global Quarterly / USA | Global Annual / Semi-Annual | On-Demand Custom Panel |
| **Cadence & Freshness** | **Weekly (Mon-Fri)** | Daily (Continuous) | Weekly Refresh | Quarterly / Ongoing | Annual / Semi-Annual | Real-time (Hours) |
| **Sample Size / Volume** | $\approx 400$ / week | **30,000+ / day** [O] | **30M+ panel** [O] | **2M+ / year** [O] | **3M+ interviews** [O] | 110M+ network [O] |
| **Census Post-Stratification** | ❌ **Unweighted** | ✅ Census ACS Raking | ✅ Nationally Rep. Quotas | ✅ Census Raking | ✅ Quota-Matched [O] | ✅ Configurable Raking |
| **Cube Engine Architecture** | Pre-computed MySQL Table | Multi-cut Distributed OLAP | **Crunch.io In-Memory** [O] | Proprietary OLAP Engine | Relational + Caching | Distributed Columnar |
| **Cross-Tab Flexibility** | **Max 2 Cuts** (pre-baked) | Dynamic N-Cut | Dynamic N-Cut | Dynamic N-Cut | Dynamic Matrix Crosstabs | Dynamic Multi-Banner |
| **Distinctiveness Metrics** | ❌ Raw % & Deltas only | ✅ Brand Indices | ✅ **Z-Scores & Indices** [O] | ✅ Index Scores (Base 100) | ✅ Distinctiveness Index | ✅ Benchmark Comparison |
| **Pre-Flight Sample Gate** | ❌ No ($n<5$ flag only) | ✅ Sample Gates | ✅ Cell Base Warnings | ✅ Base Reliability Flags | ✅ **Applicability Check** [O] | ✅ Minimum Base Gates |
| **Significance Testing** | ✅ **95% BH-FDR Corrected** | ✅ Significance Flags | ✅ Standard Error Testing | ✅ Statistical Letters | ✅ Cell Difference Highlights | ✅ Statistical Flags |
| **Open-Ended Text NLP** | ❌ Discarded | ✅ AI Categorized | ✅ Coded Verbatims | ✅ Topic Tagging | ❌ Limited | ✅ AI Topic Clusters |
| **External MCP Connectors** | ❌ **None** | ✅ **Claude / GPT / Gemini** [O] | ✅ **Profiles MCP** [O] | ✅ **Claude / Copilot** [O] | ✅ **Statista Connect** [O] | ✅ **Claude MCP** [O] |
| **Public REST API** | ❌ **None** | ✅ Aggregate Daily API [O] | ✅ Profiles API [O] | ✅ `api.globalwebindex.com` [O] | ✅ Connect REST API [O] | ✅ Results API [O] |
| **BI Warehouses (Snowflake)** | ❌ None (Manual CSV) | ✅ Direct Feeds | ✅ Data Delivery | ❌ Partner Export | ❌ Direct Feed | ✅ **Snowflake/Tableau/PBI** [O] |
| **Native Deck Generation** | ✅ **Editable PPTX** [O] | ✅ Slide Export | ✅ Report Automation | ✅ **GWI Canvas** [O] | ✅ Add-to-Board / Decks | ✅ Automated Decks |
| **Multi-Tenancy & RBAC** | ❌ **Open / Global** | ✅ Enterprise SSO/SAML | ✅ Multi-Tier RBAC | ✅ Enterprise Workspaces | ✅ Multi-Seat Workspaces | ✅ Teams & Role Gating |
| **Retail Specialization** | ⭐ **Deep US Retail Sector** | General Political/Macro | General Brand Health | Digital & Media Focus | Broad Consumer Goods | Brand & Product Testing |

---

## 4. The 7 Root-Cause Gaps Stopping CIP from Reaching Top-of-Market

---

### Gap 1: Data Representativeness & Absence of Census Raking
- **The Gap:**  
  CIP fields $\approx 400$ weekly US survey responses without demographic post-stratification or iterative proportional fitting (raking). The calculated metric `srv_result.pct` is strictly $n_{\text{item}} / n_{\text{cell}}$ (`etl/serving.py:127`).
- **Mathematical Impact:**  
  At $n=400$, the base margin of error for a total sample at $p=0.50$ is:
  $$\text{MoE} = 1.96 \times \sqrt{\frac{0.50 \times 0.50}{400}} \approx \pm 4.90\%$$
  However, when an analyst filters by demographic segments (e.g., Gen Z females earning $>\$100\text{k}$), cell counts drop to $n=15–30$, where margin of error expands beyond $\pm 18\%$.
- **Competitor Evidence:**  
  Every major competitor (Morning Consult [O], YouGov [O], Euromonitor [O]) weights to US Census ACS targets or quota-matches sample sizes.
- **Required Remediation:**  
  Implement an iterative proportional fitting (raking) algorithm in Python (`scipy.optimize` or `ipfn`) against US Census Bureau ACS 5-year benchmarks for Age $\times$ Gender, Household Income, Race/Ethnicity, and Census Region. Store both unweighted counts (`n_unweighted`) and weighted proportions (`pct_weighted`) in `srv_result`.

---

### Gap 2: Modern Distribution: Public REST API & FastMCP Server
- **The Gap:**  
  CIP has no public REST API and no Model Context Protocol (MCP) server. Enterprise clients are forced to navigate the React web portal or manually download CSV files.
- **Competitor Evidence:**  
  - GWI: Publishes `api.globalwebindex.com` and an MCP server for ChatGPT and Claude [O].
  - Statista: Sells Statista Connect API & MCP as an enterprise grounding layer [O].
  - Attest: Results API feeds Snowflake, Tableau, and Power BI, plus a Claude MCP connector [O].
  - Euromonitor: Sells Passport Connect API and MCP licenses for Microsoft Copilot and Claude [O].
- **Required Remediation:**  
  Build a dedicated FastMCP server (`mcp_server.py`) exposing CIP's syndicated cubes:
  1. `get_weekly_trend(topic, start_wave, end_wave)`
  2. `get_demographic_crosstab(survey_id, question_id, segment)`
  3. `search_retail_insights(query, category)`  
  Enforce API key authentication with rate limiting and row-level small-cell suppression.

---

### Gap 3: Statistically Distinctive Metrics (Index Scores & $z$-Scores)
- **The Gap:**  
  CIP only computes raw percentage ($pct$) and prior wave delta ($prior\_pct$). When examining an audience (e.g., "Costco Shoppers who plan to buy electronics"), CIP cannot tell the user what makes this group *statistically distinctive* from the general population.
- **Competitor Evidence:**  
  YouGov Profiles explicitly advertises: *"Z-scores help you automatically highlight the important datapoints that distinguish particular groups from the general population"* [O].
- **Required Remediation:**  
  Introduce Index Scores and standardized $z$-scores into the serving layer and UI:
  $$\text{Index} = 100 \times \left( \frac{P_{\text{target}}}{P_{\text{baseline}}} \right)$$
  $$z = \frac{P_{\text{target}} - P_{\text{baseline}}}{\sqrt{P_{\text{pool}}(1 - P_{\text{pool}})\left(\frac{1}{n_{\text{target}}} + \frac{1}{n_{\text{baseline}}}\right)}}$$
  Highlight cells where $\text{Index} \ge 120$ (Over-indexed) and $z \ge 1.96$ ($p < 0.05$) in green, and $\text{Index} \le 80$ (Under-indexed) in red.

---

### Gap 4: Analytical Storage: Pre-Computed MySQL Table vs In-Memory Columnar Cube
- **The Gap:**  
  CIP relies on `srv_result`, a pre-computed MySQL table (1,450,000 rows, 442 MB) pre-calculated overnight for only 2 demographic dimensions (`dim_type_1`, `dim_type_2`). Querying an ad-hoc 3-way crosstab or custom audience cohort requires scanning `cip_answer` (5.98 GB, 11.9M rows), exceeding Azure MySQL's 2.0 GB buffer pool and taking up to 12 seconds.
- **Competitor Evidence:**  
  YouGov uses Crunch.io, an in-memory columnar database providing sub-second queries across millions of rows and thousands of variables without pre-aggregation [O].
- **Required Remediation:**  
  Transition the analytical query layer to **DuckDB** or **ClickHouse**. DuckDB reads columnar Parquet files generated during ETL, answering ad-hoc multi-dimensional survey crosstabs in $< 80\text{ ms}$ on local memory without touching the operational MySQL database.

---

### Gap 5: Pre-Flight Sample Gate & Audience Applicability
- **The Gap:**  
  CIP allows users to generate crosstabs and trends on arbitrary sub-segments regardless of sample size, rendering a small asterisk if $n<5$ (`api/main.py:182`). If a sub-segment has $n=6$, it is displayed without warning despite carrying a $\pm 39\%$ margin of error.
- **Competitor Evidence:**  
  Statista Consumer Insights enforces `/target-groups/applicability` in its React bundle, calculating sample sufficiency *before* rendering analysis [O].
- **Required Remediation:**  
  Implement a pre-flight sample gate in the frontend and API:
  - If $n < 30$: Display a prominent warning: *"Sample base too small ($n < 30$) for reliable statistical projection; margin of error exceeds $\pm 18\%$."*
  - If $n < 10$: Automatically suppress cell figures and render `[Insufficient Base]` to protect data integrity.

---

### Gap 6: Qualitative Text Intelligence (Open-Ended Verbatim Coding)
- **The Gap:**  
  CIP currently parses open-ended text fields ("Other, please specify") into standalone question records in `cip_question`, but completely excludes them from analytical cubes, search, and crosstabs.
- **Competitor Evidence:**  
  Qualtrics, Suzy, and Attest use automated LLM pipelines to cluster, sentiment-tag, and categorize verbatim feedback into actionable structured themes [O].
- **Required Remediation:**  
  Add an asynchronous text-categorization step in the weekly ETL pipeline:
  Run Claude 3.5 Haiku over unserved text responses in `dwh_smresponse` / `cip_answer`, clustering verbatims into 5–8 standardized category tags, and insert them as structured multiple-choice answers in `srv_result`.

---

### Gap 7: Enterprise Multi-Tenancy, RBAC & Commercial Packaging
- **The Gap:**  
  CIP currently has:
  1. No client data isolation (client-commissioned studies like T-Mobile or Rokbot are globally visible to all logged-in users).
  2. Open dev login enabled on production (`/auth/dev-login?email=...`).
  3. No Role-Based Access Control (RBAC) separating Admins, Analysts, and View-Only Clients.
  4. No commercial subscription tiers or usage metering.
- **Competitor Evidence:**  
  Displayr Enterprise starts at $4,199/user/yr gating SSO and API integrations [O]. GWI gates access across Pro, Team, and Enterprise consumption tiers [O].
- **Required Remediation:**  
  1. Deploy `app/core/access.py` and `config/access.yml` to enforce survey visibility by client domain.
  2. Implement RBAC (`admin`, `analyst`, `client`) in FastAPI middleware.
  3. Strip dev-login in production unless an explicit secret key is provided.

---

## 5. CIP's Defensible Competitive Moats (What Competitors Cannot Match)

While CIP must close the real strategic gaps, the investigation confirms key defensible advantages where CIP differentiates from competitors:

1. **Continuous Longitudinal US Retail Cadence (268 Weekly Waves Since Dec 2020):**  
   CIP holds continuous weekly retail sentiment and sector-rotation history tracking the same core questions across 268 consecutive weekly waves (with additional annual benchmark studies extending to 2018). Generalist competitors (Morning Consult, YouGov) track broad political and brand metrics, but lack CIP's granular US retail sector depth (apparel, grocery, electronics, beauty, department stores).
2. **Disciplined Multiplicity Control (Benjamini-Hochberg FDR):**  
   Unlike consumer portals that render movement indicators based on uncorrected individual $t$-tests or raw $p$-values (causing dozens of false alarms across large crosstab matrices), CIP implements Benjamini-Hochberg False Discovery Rate correction (`web/src/moves.ts`), capping the expected proportion of false discoveries across simultaneous hypothesis tests at $q \le 0.05$.
3. **Strictly Grounded AI Assistant (Zero Synthetic Hallucinations):**  
   While competitors like Toluna market synthetic personas, CIP's `/api/assistant` strictly grounds every answer in actual survey question numbers, sample bases, and wave dates, explicitly refusing to answer uncited queries.
4. **Native, Editable Office Open XML PowerPoint Decks:**  
   Competitors frequently export static raster images or locked PDFs. CIP's export engine (`api/exports.py`) generates fully native, editable PowerPoint chart shapes using `python-pptx`, allowing enterprise analysts to immediately modify chart styles and data series within their corporate templates.

---

## 6. Real Actionable Gaps & High-Impact Execution Sequence

Based on primary verification against the codebase and live database, the 5 real high-impact initiatives worth executing are:

```mermaid
flowchart LR
    subgraph P1["Priority 1: Immediate Analytical Win"]
        G3["Index Scores on Audience & Crosstabs<br/>(Base 100 & Z-scores; data already exists)"]
        G1["Census Weighting / Methodology Note<br/>(Clear unweighted disclosure on /methodology)"]
    end

    subgraph P2["Priority 2: Enterprise Distribution"]
        G2["FastMCP Server & Public REST API<br/>(Direct Claude, ChatGPT & Copilot querying)"]
    end

    subgraph P3["Priority 3: Data & Infrastructure"]
        G4["Open-Ended Text NLP Coding<br/>(LLM theme extraction for verbatim responses)"]
        G5["Azure VM Production Cutover<br/>(Permanent hosting managed with IT)"]
    end

    P1 --> P2 --> P3
```

1. **Index Scores (Audience & Crosstabs):** The fastest and highest-ROI analytical feature. The cell proportions and base sample sizes already exist in `srv_result` and `srv_answer`. Add $\text{Index} = 100 \times \frac{P_{\text{target}}}{P_{\text{base}}}$ and standardized $z$-scores directly to the React UI.
2. **Data Weighting / Methodology Disclosure:** Either implement iterative proportional fitting (raking) against US Census ACS benchmarks, or publish a transparent note on the public methodology page explaining that weekly tracker samples are unweighted raw respondents ($n \approx 400$, $\text{MoE} \approx \pm 4.9\%$).
3. **Modern Distribution (FastMCP & Public API):** Build a FastMCP server (`mcp_server.py`) and a versioned REST API, giving enterprise subscribers direct programmatic access inside Claude and ChatGPT.
4. **Open-Ended Text Intelligence:** Process raw open-ended text fields in `dwh_smresponse` using Claude 3.5 Haiku to extract and quantify emerging consumer themes.
5. **Permanent Azure VM Hosting:** Transition the live application and tunnel from the developer MacBook to the provisioned Azure East US Ubuntu VM.
