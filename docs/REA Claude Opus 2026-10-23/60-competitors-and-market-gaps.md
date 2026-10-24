# 60 · Competitors and market gaps (pre-launch audit)

**Date:** 23 Oct 2026. **Author:** Claude (Opus), one of six parallel pre-launch investigators. **Scope:** US and international competitors, notable India-based players, and the gaps that stop CIP reaching the top of the market.
**Source register:** [60-competitor-sources.json](60-competitor-sources.json). Every vendor claim below has a URL and retrieval date there.

**Evidence labels**
- **[O]** observed: read from an official vendor page or captured with REA on 23 Oct 2026, URL given.
- **[I]** inferred: our reading of the evidence, or industry knowledge not re-verified today.
- **[U]** unknown: not established.

All vendor statements are **what vendors advertise**. No vendor tenant was opened. Nothing was logged into, signed up for or submitted.

---

## 1. Summary

1. **CIP's feature surface is now close to the leaders. Its data asset is not.**
   - Statista Consumer Insights is the nearest product match. REA recovered its route table from the public bundle: consumer AI chat, target groups (saved audiences) with an applicability check, charts, crosstabs, boards, async exports, and add-to-board from chat, chart and crosstab [O].
   - CIP ships every one of those workflow surfaces except async export jobs.
   - The gap is the data behind them. CIP has about 400 unweighted US respondents a week. The leaders publish:
     - Morning Consult: 30,000+ surveys a day, 100+ countries [O];
     - YouGov: 30M+ panel members, 49–56 markets, daily BrandIndex surveys [O];
     - GWI: 2M+ interviews a year, 50+ markets [O];
     - Statista: 3M+ interviews, 30+ countries [O];
     - Numerator: 200k+ longitudinal panelists, 2B+ trips [O];
     - NIQ Homescan: 250k+ households in 25 countries [O];
     - Euromonitor Voice of the Consumer: about 1,000 usable, quota-matched responses per market [O].
2. **AI distribution has moved outside the vendor portal.** Over the past year the market moved from "chatbot in the portal" to MCP connectors and APIs:
   - Morning Consult: Claude, ChatGPT and Gemini MCP connectors, plus an aggregate daily-data API [O];
   - GWI: Agent Spark inside other LLMs, API+MCP priced by consumption [O];
   - YouGov Profiles: API and MCP [O];
   - Statista Connect: API and MCP [O];
   - Euromonitor Passport: answers "inside Claude, Microsoft Copilot" [O];
   - Attest: Results API to Power BI, Tableau, Looker and Snowflake, plus an MCP connector [O].

   **CIP has no public API, no MCP server and no BI connector.** This is the biggest product/distribution gap.
3. **CIP's real edges are narrow but defensible:**
   - weekly US retail-sector rotation with history since 2018;
   - research-grade honesty in every view: significance at 95%, small-base suppression at n<5 and flags, "not comparable" across question-version breaks;
   - a strictly grounded assistant that drops uncited claims;
   - native editable PPTX/XLSX;
   - analyst-written Coresight research context.

   No survey-data vendor reviewed shows uncertainty as consistently, according to the public pages and the REA captures in doc 18.
4. **The biggest blocker is trust/methodology, not features.** The data is unweighted, and no public methodology page says so. n≈400 a week gives a ±4.9 pt margin of error at 50% for the total and much wider for subgroups.
   - Every serious competitor either weights or quota-matches (Euromonitor states quota matching [O]; YouGov BrandIndex says "nationally representative samples in each market" [O]), or sells a different evidence type (receipts, POS).
   - A buyer comparing CIP with Morning Consult or YouGov will ask "representative of what?" on day one.
5. **Enterprise packaging is thin.**
   - SSO is via OIDC [O, repo `docs/08-authentication.md`].
   - Not present in the code reviewed: roles, client tenancy or entitlements, audit log, API keys and usage metering (`api/team.py` has owner-only deletes and nothing else).
   - Competitors gate SSO, API, regional servers and MFA into an enterprise tier, e.g. Displayr Enterprise "from $4,199 per user/billed annually" with SSO and APIs [O].

---

## 2. Method and sources

| Step | What was done | Tool |
|---|---|---|
| Prior work | Read `docs/REA Codex/competitor-landscape.md` and its sources (23 vendors, 21 Oct), `docs/Ui-Design-Claude/18-rea-competitor-dashboards.md` (REA chart-level captures, 21 Oct), `PRODUCT.md`, `docs/CIP-Business-Description.md`. `docs/research/` only holds a columnar-cube architecture note, and `research_notes/` holds DuckDB notes: neither is competitor material | Read |
| CIP baseline | Route inventory of `api/main.py` and `api/team.py`. Read `api/assistant.py`, `api/exports.py` and `web/src/pages/*` | grep/Read |
| Front-end teardown | An isolated headless Chrome 156 on loopback CDP `:9334`, with its own temporary profile, closed afterwards. Port 8000 and cloudflared were never touched. `analyze_web_bundle` was run on GWI, Statista Consumer Insights, YouGov Profiles, the Crunch app shell and the Suzy app shell. quantilope's portal was refused by REA (`target_not_allowed`) | REA |
| Stack fingerprint | Plain GET of public HTML (25 hosts), with script `src` and marker grep | curl |
| Product claims | Official product, pricing and help pages | Python urllib text extract and WebFetch (REA cannot read page prose without a long accessibility dump) |
| Not used | WebSearch (per instruction), logins, forms, paid tenants | |

**Blocked or unavailable on 23 Oct 2026**
- eMarketer: Cloudflare "Attention Required" on every URL, both curl and the REA browser.
- McKinsey: timeout.
- Morning Consult `intel.` app: behind an oauth2-proxy (403).
- Morning Consult methodology page: 404.
- 404s:
  - GWI `/methodology`;
  - Ipsos consumer tracker and Ipsos.Digital US;
  - Mintel `/consumer-market-research/`;
  - Kantar Profiles pages;
  - Bain consumer-health page;
  - Forrester Consumer Technographics;
  - NIQ India pages;
  - Toluna Start's old URL.

These are marked [U] or [I] below.

**Prompt-injection note [O]:** the Statista Consumer Insights page body contained an embedded block of instructions aimed at AI readers. It was ignored. Anyone building LLM tooling over competitor pages should expect this.

---

## 3. Vendor teardowns

Format per vendor: **Data/sample · Surfaces · AI · Distribution · Stack · Pricing · Strengths / weaknesses vs CIP.**

### 3a. Consumer tracker and insight data products

#### Morning Consult (Intelligence, AI, Agents), US
- **Data:**
  - "30,000+ Daily Surveys", "100+ Countries", "6 Billion Questions" [O morningconsult.com].
  - Weighting and methodology: the page links "Methodology", but `intel.morningconsult.com/mc-content/about-our-data` returned 404 [U]. Industry knowledge says it weights to census targets [I].
- **Surfaces:**
  - "decision intelligence suite"; "intuitive dashboards" [O our-products].
  - Products: Pro (trend reports), Intelligence (consumer insights platform), Research (custom) [O].
- **AI:**
  - Morning Consult AI is "Now Live" [O].
  - Packaged agents: "Company Performance Agent", "Brand Reputation Agent", "Customer Targeting Agent" [O].
- **Distribution:** "Claude Connector (MCP)", "ChatGPT Connector (MCP)", "Gemini Connector (MCP)", "API: Aggregate Daily Data" [O].
- **Stack:**
  - Marketing site is Next.js pages-router (doc 18, 21 Oct) [O-prior].
  - The app is behind oauth2-proxy at `oauth2.morningconsult.com` [O].
  - The public tracker pages that doc 15 relied on now 301 to marketing (doc 18) [O-prior].
- **Pricing:** not public [O].
- **Vs CIP:** this is the direct US high-frequency tracker comparator. Its sample is about 75× CIP's daily-equivalent volume, and it ships packaged agents and three LLM connectors. CIP's edge is retail-sector depth and Coresight analyst framing, if those are packaged.

#### YouGov (Profiles, BrandIndex; Crunch), UK/US
- **Data:**
  - Profiles: "30 million+ panel members", "49 markets", "Data sets are refreshed each week", variables "collected daily and updated weekly" [O].
  - BrandIndex: "daily surveys in every core market", "56 markets", "16 vital brand health metrics", "nationally representative samples in each market" [O].
- **Surfaces:**
  - Audience builder ("Combine unique filters").
  - Cross-market comparison over time; **z-scores** to highlight what distinguishes a group.
  - Drag-and-drop dashboards with "multitables".
  - Re-contact audiences with follow-up questions [O].
- **AI:**
  - "conversational AI Agent" that surfaces segments; "automatic report builder" [O].
  - "BrandIndex Voices": an AI-powered interviewing tool [O].
- **Distribution:**
  - "via API or in your AI workflows via MCP"; RLD (respondent-level data).
  - Activation to "Google DV360, Meta, and The Trade Desk" [O].
- **Stack:**
  - Public site: Angular 21.2.7 SSR with Highcharts 12.6 (doc 18) [O-prior].
  - Marketing page today: OneTrust consent and New Relic browser agent (REA `ev_f27417…`) [O].
- **Crunch:** YouGov ownership of Crunch is not stated on crunch.io [U]. Industry knowledge says YouGov acquired Crunch.io [I].
- **Pricing:** not public [O].
- **Vs CIP:** z-score "what makes this group different" and recontact are workflow ideas CIP can copy cheaply; CIP already has significance vs Total. YouGov's public tracker shows no margin of error (doc 18), and CIP's does.

#### GWI (Platform, Agent Spark, Canvas), UK
- **Data:** "50+ global markets", "2M+ interviews annually", "4 waves of data per year", "15+ years of trended insight", "every respondent answers in their native language" [O gwi.com/data]. The integrations page says "1.4M+ always-on consumer surveys across 52+ markets" [O]: GWI's own figures disagree.
- **Surfaces:** "250K+ profiling points", custom and shared audiences, charts, dashboards, crosstabs [O].
- **AI:**
  - **Agent Spark** answers in plain language "inside the GWI Platform or in LLMs your team already uses" [O].
  - **GWI Canvas** generates presentation-ready slides [O].
- **Distribution:** "Programmatic and agentic access… through API and MCP. Priced by consumption" [O pricing]. Also RLD and audience activation [O].
- **Pricing model [O]:** four parts:
  - platform per seat (Pro and Team seats);
  - integrations by consumption;
  - bespoke research by complexity;
  - (fourth part not captured).
- **Stack:** HubSpot CMS marketing site (REA `ev_2e634a…`) [O]. App host `app.gwi.com` did not resolve publicly [O].
- **Vs CIP:** quarterly cadence (CIP is weekly) is a real CIP edge for fast-moving US retail topics such as tariffs, GLP-1 and holiday. GWI wins on scale, markets, AI distribution and slides.

#### Statista Consumer Insights, Germany
- **Data:** "3M+ interviews, 30+ countries, 275+ audience attributes, 15K+ brands" in four modules (Global, Brand KPIs, Pulse, Media & Touchpoints), "regularly updated" [O]. Weighting is not stated on the page [U].
- **Surfaces (REA, `ev_4ccad97…`) [O].** Route table recovered from the bundle:
  - AI: `consumer-ai`, `resources/consumer-ai-message(s)`, `history-consumer-ai`;
  - audiences: `target-groups/new|:id/edit|delete`, `target-group-applicability`, `target-group-attribute-catalog`, `source-population`, `proposal-population`;
  - analysis: `charts/:projectId/:surveyId`, `crosstabs/:projectId/:surveyId`, `crosstabs-survey-tree`;
  - boards: `boards/:boardId/widgets/:widgetId/delete`, `chat-add-to-board`, `charts-add-to-board`, `crosstabs-add-to-board`;
  - exports: `exports/:id/cancel|retry|download`;
  - sign-in: `sso-sign-in-link`.

  Reading [I]:
  - audiences are checked for *applicability* per survey and the population is previewed before saving;
  - exports run as background jobs;
  - AI answers can be pinned to boards.
- **AI:** "Consumer AI" chat; on the public chart pages, "Copy data for AI" and "Ask AI" (doc 18) [O].
- **Distribution:** "Statista Connect provides access via API, MCP, or direct integration with AI tools" [O].
- **Stack [O REA]:** React + React Router v7 framework mode (`entry.client`, `root`), built with Vite/rolldown (`rolldown-runtime`), i18next. This is the **same family as CIP (React 19 + Vite)**. Public chart pages use Highcharts 12.6 (doc 18).
- **Pricing:** not on page; "Book a demo" [O].
- **Vs CIP:** feature-for-feature the closest analogue. Two differences:
  - Statista asks "does this audience exist in this survey?" before analysis. CIP computes per wave and suppresses small cells afterwards.
  - Statista's exports are a queue (cancel and retry). CIP's are synchronous.

#### Numerator (Insights, Verified Voices, Nexa), US
- **Data:** "200k+ longitudinal panelists", "2500+ consumer attributes", "2B+ shopping trips captured", "updated daily" [O]. Receipt capture is not stated on this page [U]. Industry knowledge says it is receipt-based [I].
- **Surfaces:**
  - segmentation, people scorecards, basket affinity, source of volume, trip circuits, promo incrementality [O];
  - **Verified Voices**, "real research from real buyers": surveys sent to verified purchasers [O].
- **AI:** "Narratives" guided flows; "Nexa… turn complex analysis into a simple conversation" [O].
- **Stack:** WordPress marketing site [O curl].
- **Kantar Worldpanel:** `kantar.com/worldpanel` now redirects to a Kantar "Worldpanel" campaign page. `worldpanel.com` is an unrelated wood-panel company [O]. Whether Worldpanel now sits under Numerator was **not confirmed** on any page today [U].
- **Vs CIP:** buy-and-why linkage (survey a verified buyer) is something CIP structurally cannot do. It is the main reason a CPG buyer picks Numerator over a pure survey.

#### Circana (Unify+, Complete Consumer, Liquid AI), US
- **Data:**
  - Complete Consumer "blends receipt, loyalty card, scan panel, and survey data into a single solution"; "30+ channels" [O].
  - "Complete Consumer Survey" and "National Eating Trends" appear in the navigation [O].
- **Unify+ surfaces:** "visualize trends, work together, and build custom reports"; "Data alerts and performance narratives"; "tailored storyboards"; "templatize, and share reports"; "7,000 clients and partners" [O].
- **AI:** "Conversational and agentic AI embedded"; rankings "powered by Liquid AI™" [O].
- **Exports:** PowerPoint/Excel/PDF via the Analysis Builder (Codex source, 15 Sep 2026) [O-prior]. Not re-verified today.
- **Stack:** Wix marketing site (4,180 `wix` markers), React, d3 [O curl]. The page is client-rendered, so WebFetch got only the title.
- **Vs CIP:** POS and receipt truth plus narratives. Not the same evidence type: CIP should partner or position alongside, not compete.

#### NielsenIQ (Discover, Homescan, BASES), US
- **Data:**
  - Homescan: "more than 250,000 households across 25 countries" [O].
  - Discover: "Global data in 100+ markets", "POS-truth sets" [O].
- **Surfaces:** "KPI alerts", "guided flows and report building", "report templates with rich visualizations" [O].
- **AI:** **Ask Arthur** [O].
- **Distribution:** "Data Delivery Manager… centralized extract tool to power your data lake or 3rd party BI tools"; Discover Add-in for simple extracts [O].
- **BASES:** innovation and concept forecasting "validated to predict in-market outcomes" [O].
- **Stack:** WordPress marketing site with HubSpot [O curl].
- **NIQ India:** no India page resolved today [U]. NIQ's India retail audit and Homescan presence is industry knowledge [I].

#### Kantar (Worldpanel, Marketplace, Profiles), UK
- **Data:**
  - Worldpanel: "the largest consumer panel in the world", "choices of 6 billion* people"; PanelVoice listed [O].
  - Marketplace: "150 million consumers", "80+ countries", "pay as you go or commit to volume" [O].
- **Surfaces:** Marketplace offers self-serve ad, concept and pack testing with expert support [O-prior and O].
- **Kantar Profiles:** URLs 404 today [U].
- **Kantar India:** no India path resolved [U]. Kantar runs Worldpanel India and the IMRB legacy business [I].

#### Ipsos (FastFacts / Ipsos.Digital, What Worries the World), France
- **Data:** "6M+ authenticated, proprietary panelists", "90 Markets", "5,000+ clients" [O ipsos.com/en-us].
- **Surfaces:**
  - FastFacts DIY surveys with PPT/PDF/Excel/SPSS outputs (Codex, en-ca page) [O-prior].
  - "What Worries the World" is a public Flourish embed (doc 18) [O-prior].
  - The US consumer tracker URL is a 404 [O].
- **Vs CIP:** custom-fielding comparator. No syndicated US weekly retail tracker product was found publicly [U].

#### Mintel (Leap, GNPD, reports), UK
- **Data:** Leap is "built exclusively on Mintel's proprietary research and human analysis"; "50 years of rigour" [O].
- **AI:** a "closed-loop AI platform" with "links to sources"; claims users need not worry about "hallucinations" (a vendor claim) [O].
- **Pricing:**
  - "Market Intelligence Reports, individually priced";
  - On-Demand subscriptions;
  - "Unlimited seats… at licensed locations" [O mintel.com/pricing].
- **Vs CIP:** this is the **analyst-plus-data** model, the same one Coresight could run. Leap's answer format (short write-up plus links to every report and source) is the bar for Ask CIP.

#### Euromonitor (Passport, Voice of the Consumer), UK
- **Data:**
  - Voice of the Consumer: "Respondents are recruited through panel providers, screened and quota-matched to each market's population, with around 1,000 usable responses per market. We write the questionnaire in-house" [O passport page].
  - Passport: "210+ countries and territories", "5,700+ organisations", "65k active users" [O].
- **AI:** "AI-generated summaries and unified search"; answers "inside Claude, Microsoft Copilot, or whichever assistant your teams have standardised on" [O].
- **Distribution:** "Passport Connect APIs and plug-and-play integrations" [O].
- **Stack:** marketing site mentions AEM and Azure [O curl, weak].
- **Vs CIP:** discloses its methodology on the product page. CIP has no equivalent public statement.

### 3b. Survey and analytics platforms a customer could self-build on

#### Qualtrics (XM, Crosstabs, Stats iQ), US
- **Crosstabs:**
  - banners;
  - chi-square, and pairwise column z-tests "where the sample size is larger (generally over 30)";
  - weighting;
  - bucketing [O help page].
- **Limits:** crosstabs "cannot bring… weighting, or custom fields into other reports, including any type of dashboard" [O]. Qualtrics' own crosstabs and dashboards are siloed. CIP's single pre-computed book feeds every screen, which is a real architectural edge.
- **Stats iQ:** URL 404 today [U].
- **Stack:** Drupal marketing site [O curl].

#### Forsta (Reporting / Reportal), UK/US
- "Drag and drop variables, apply filters… stat testing", "Apply weighting, stat testing, net creation", "Batch reporting: generate PowerPoint decks", "export decks direct to PowerPoint, PDF and Excel" [O datasheet].
- **Relevance:** CIP's own source system, Forsta Surveys, has reporting that analysts could use instead of CIP. CIP has to beat it on harmonised history (2018+, three platforms) and speed, not on crosstab features.
- **Displayr link:** the brief groups "Forsta (Reportal/Displayr)". Neither site states common ownership today [U].

#### Displayr / Q, Australia
- **Techniques menu:**
  - Research Agent, Tables & Crosstabs, Text Analytics, Statistical Testing, **Weighting**;
  - Driver, MaxDiff, Conjoint, TURF;
  - PowerPoint Automation, Automatic Updating, Dashboarding [O].
- **Pricing [O]:**
  - Enterprise "From $4,199 per user/billed annually" with "Enterprise-grade integrations with APIs, Single Sign-On (SSO)… Regional server… MFA";
  - each licence includes an AI Package of "200 million tokens";
  - extra viewer hours "USD $1340" per 1,000;
  - no monthly billing.
- **Stack:** the login page serves from `static-assets.prod.displayr.com/…/SharedWebUi` [O curl].
- **Vs CIP:** Displayr is what a Coresight client's insights team would use to analyse CIP data themselves if given respondent-level data. Its token-metered AI is a pricing pattern worth noting.

#### Crunch.io, US/UK
- "millions of respondents and thousands of variables, with subsecond query response, powered by the Crunch columnar database built for survey data"; "Build an interactive, no-coding dashboard in 5 minutes" [O].
- **Stack [O curl, REA `ev_95cf42…`]:**
  - app shell loads `react`, `d3`, `plotly`, `vega`, `lodash` and `ndarray` bundles from `s.crunch.io`;
  - the login flow is at `/authentication/workspace`.
- **Vs CIP:** Crunch shows that sub-second survey querying is table stakes for this category. CIP's p95 < 0.35 s (PRODUCT.md) is on par, not an edge.

#### Toluna Start, France (strong India operations)
- "81+ million consumers across 70 markets"; "1 million+ validated synthetic personas" [O].
- "Toluna's AI combines… synthetic personas with 80% correlation" [O homepage].
- Also on the page: QProbe AI follow-up on open ends, SmartCloud, interactive dashboards and "Infoboards", AI Auto Translate [O].
- **India:** an `english (india)` locale exists on toluna.com [O]. Toluna's Indian delivery operations are industry knowledge [I].

#### Attest, UK
- **Coverage:** "150M+ consumers", "59 global markets", "70 languages", ISO 27001 [O].
- **Pricing model [O]:**
  - credit = one answer to one question from one person;
  - "One flat audience fee", "no premium for… niche" audiences;
  - "Unlimited seats".
- **Distribution:** "Link your research directly to PowerBI, Tableau, Looker or Snowflake… Attest Results API"; "MCP connector: Ask your data anything… like Claude… across surveys, waves and markets" [O].
- **Vs CIP:** Attest's results API plus MCP over *waves* is exactly the integration CIP lacks.

#### quantilope, Germany
- **Products:** "Always-On Brand Tracking"; **quinn** AI "drafts questionnaires, audits survey logic, analyzes complex datasets, and synthesizes reports" [O].
- **Stack:**
  - `portal.quantilope.com` is a Vite build (module plus legacy polyfill entries) with Appcues onboarding [O curl].
  - REA refused that target (`target_not_allowed`).

#### Suzy, US
- **Data and methods:** "70+ panels of verified consumers", "130+ international markets", "Biotic" bot detection; quant, MaxDiff, TURF and AI-moderated interviews [O].
- **Stack [O REA `ev_6a4da4…`]:**
  - `app.suzy.com` is Angular (Zone.js, hashed `runtime/polyfills/main` bundles);
  - **7.3 MB main bundle**;
  - routes `brand`, `admin`, `auth`;
  - `requestCreditsForm` shows a credit-based commercial model.

#### Zappi, UK
- Ad, innovation and brand-tracking research; "AI Concept Creation"; "Agents" [O]. HubSpot site [O curl].

#### SurveyMonkey, US
- **Plans and prices** (geo-priced in INR when fetched from India):
  - Team Advantage ₹1,550/user/month: statistical significance, "Analyze with AI", thematic analysis.
  - Team Premier ₹3,800: crosstabs.
  - Enterprise: SSO; US, Canada or EU data centre.
  - Audience responses are sold separately [O].
- **Vs CIP:** the floor. CIP's 2018–2022 history came from SurveyMonkey.

### 3c. Retail-research peers of Coresight

| Vendor | Evidence today | Notes |
|---|---|---|
| **eMarketer** (Insider Intelligence) | **[U]**: Cloudflare challenge on all URLs, curl and REA | From industry knowledge [I]: forecasts and a charts database with PPT/XLS chart downloads, plus an AI assistant. It is the most direct "research subscription with data" peer to Coresight. Re-verify from a normal browser before quoting |
| **Forrester** | Research page lists Predictions, Planning Guides, Market Forecasts, Vendor Evaluation [O]. Consumer Technographics URL 404 [U] | Auth0 on site [O curl] |
| **Placer.ai** | "privacy-preserving panel", "+92% accuracy", property polygons, sales estimation, demographics [O] | Webflow, HubSpot and Contentful site [O curl]. Location, not survey, evidence |
| **McKinsey ConsumerWise / Bain** | McKinsey timed out; Bain URL 404 [U] | Free public trackers raise the bar for what a *free* US consumer sentiment read looks like. CIP's public value must exceed a free McKinsey chart [I] |

### 3d. India

| Vendor | Evidence today | Relevance |
|---|---|---|
| **Redseer** | "strategy consulting firm"; "Benchmarks: AI-powered market intelligence platform, built on a decade of that research"; Redseer Brand Index – Online Fashion 2026 (published 22 Oct 2026) [O]. Site is Next.js plus WordPress [O curl] | India-focused consulting with an AI benchmark platform. The closest *business-model* twin to Coresight (research firm adding a data platform) in India |
| **Market Xcel** | "Xcel Global Panel… more than 5 million panellists"; "Indian rural community" initiative; Brandxcel brand ranking; "AI-backed analytics and data science platform" [O]. Framer site [O curl] | Possible fielding or panel partner if CIP expands to India. Not a platform competitor today |
| **Kantar India / NIQ India** | No India product page resolved [U] | Worldpanel India and NIQ retail audit are industry knowledge [I] |
| **Toluna India** | `english (india)` locale [O] | Panel supplier and Start platform |
| **QuestionPro** (US/India origin) | Redirects to `/in/`; "22+ million respondents"; Advanced plan "$99 per user / per month"; synthetic data [O] | Self-build survey SaaS |
| **SurveySensum** (India/SEA) | "500+ Companies", "40+ Countries", AI CX platform [O] | CX-focused, not syndicated |
| **Zoho Survey** (India) | Survey builder with logic and integrations [O] | Commodity survey tool |

**India conclusion [I]:** no Indian vendor offers a syndicated, weekly, research-grade US consumer tracker portal. The India-based build team is a cost advantage, not a market conflict.

---

## 4. Feature matrix

Rows are capabilities, columns are vendors, and CIP is first.
- **Y** = advertised or observed; **P** = partial; **N** = not found on public pages (absence of evidence, not proof); **U** = unknown.
- CIP evidence is from the repo (file noted). Competitor evidence is in the JSON register.

### 4a. Syndicated data products

| Capability | **CIP** | Statista CI | GWI | YouGov Profiles/BI | Morning Consult | Numerator | Circana Unify+ | NIQ Discover | Euromonitor | Mintel Leap |
|---|---|---|---|---|---|---|---|---|---|---|
| Sample per period | **P**: ~400/wk US | Y 3M+ total | Y 2M+/yr | Y 30M panel | Y 30k+/day | Y 200k panel | Y | Y 250k HH | Y ~1k/mkt | U |
| Cadence | **Y weekly** | P "regularly" | P quarterly | Y daily/weekly | Y daily | Y daily | Y | U | P annual [I] | U |
| Multi-country | **N** US only | Y 30+ | Y 50+ | Y 49–56 | Y 100+ | P | Y | Y 100+ | Y 210+ | Y |
| Weighting/representativeness disclosed | **N** unweighted, undisclosed | U | P | Y "nationally representative" | U (page 404) | n/a | n/a | n/a | Y quota-matched | U |
| History | **Y** 2018→ | U | Y 15+ yrs | Y | Y | Y | Y | Y | Y | Y |
| Behavioural link (receipts/POS) | **N** | N | N | N | N | **Y** | **Y** | **Y** | P | P |
| Question explorer + wording | **Y** `Explorer.tsx` | Y | Y | Y | Y | n/a | n/a | n/a | P | P |
| Crosstabs + sig testing | **Y** 95%, small-base | Y | Y | Y z-scores | U | P | P | P | U | N |
| Trends with uncertainty band | **Y** MoE band (doc 18) | P | P | N (public tracker) | U | Y | Y | Y | Y | N |
| Audience builder (saved) | **Y** `/audiences` | Y + applicability | Y 250k points | Y | U | Y | P | P | N | N |
| Boards/dashboards + comments | **Y** `/boards`, comments | Y | Y | Y | Y | U | Y storyboards | Y | Y | N |
| Alerts | **Y** sig-move → Teams/email (`due_alerts`) | N | U | U | U | U | Y | Y KPI alerts | U | N |
| AI assistant, grounded and cited | **Y** `assistant.py` (latest wave only) | Y | Y Spark | Y | Y + agents | Y Nexa | Y | Y Ask Arthur | Y | Y |
| AI-generated slides/decks | **P** board → PPTX, no AI narrative | Y deck export | Y Canvas | Y report builder | U | Y Narratives | Y narratives | U | U | U |
| PPTX native editable | **Y** `exports.py` | Y | Y | U | U | U | Y [prior] | U | U | U |
| XLSX | **Y** | Y | U | Y crosstab XLSX | U | U | Y | Y | U | U |
| Public API | **N** | Y Connect | Y | Y | Y aggregate daily | U | U | Y DDM | Y | P |
| MCP / LLM connectors | **N** | Y | Y | Y | **Y** Claude/ChatGPT/Gemini | U | U | U | Y Claude/Copilot | U |
| BI/warehouse connector | **N** (CSV only) | U | Y "blend" | Y RLD | U | U | U | Y data lake/BI | Y | P |
| Respondent-level data delivery | **N** | U | Y RLD | Y RLD | U | U | U | U | U | U |
| Audience activation (ads) | **N** | N | Y | Y DV360/Meta/TTD | Y targeting agent | Y | Y | Y | N | N |
| Recontact / follow-up survey | **N** | N | Y bespoke | **Y** | Y custom | Y Verified Voices | U | Y BASES | N | N |
| Open-ends coding / text analytics | **N** (no open-end handling in `api/`, `etl/`, `web/src`) | U | U | P Voices | U | U | U | U | U | U |
| SSO | **P** OIDC (`docs/08`) | Y `sso-sign-in-link` | U | U | Y oauth2 | U | U | U | U | U |
| Roles, tenancy, entitlements, audit | **N** | U | Y Pro/Team seats | U | U | U | Y role-based reports | U | U | Y licensed locations |
| Public pricing | N | N | P model | N | N | N | N | N | N | P |

### 4b. Self-build platforms

| Capability | **CIP** | Qualtrics | Forsta | Displayr | Crunch | Toluna Start | Attest | quantilope | Suzy | SurveyMonkey |
|---|---|---|---|---|---|---|---|---|---|---|
| Owns panel/fielding | **N** (uses Forsta panel 114) | Y | Y | N | N | Y 81M | Y 150M | Y | Y 70+ panels | Y Audience |
| Weighting | **N** | Y | Y | Y | Y | U | U | U | U | U |
| Crosstabs + stat tests | **Y** | Y | Y | Y | Y | Y | Y | Y | Y | Y (Premier) |
| Harmonised multi-year, multi-platform history | **Y** (SM→Qualtrics→Forsta) | N | N | P | P | N | P | P | N | N |
| PPT automation | **P** | U | Y batch decks | Y | U | U | U | Y | U | U |
| AI agent | **Y** (Q&A) | Y | Y | Y Research Agent | U | Y | Y copilot | Y quinn | Y | Y |
| API / MCP / BI | **N** | Y | Y | Y (Enterprise) | Y | U | **Y** Results API + MCP | U | U | Y |
| SSO | **P** | Y | Y | Y (Enterprise) | U | U | Y "single sign-on" | U | U | Y (Enterprise) |
| Front-end stack (observed) | React 19 + Vite + ECharts | Drupal (marketing) | WordPress (marketing) | SharedWebUi assets | React + d3/plotly/vega | U | U | Vite | Angular, 7.3 MB | Next.js (marketing) |

---

## 5. Where CIP wins (real, evidenced)

1. **Weekly US retail-sector rotation with ~8 years of harmonised history.**
   - 12 lead sectors, each returning every 12 weeks; topical modules (tariffs, GLP-1, GenAI, financial health, holiday) (`docs/CIP-Business-Description.md` §3).
   - GWI is quarterly [O]. Statista is "regularly updated" [O]. No vendor reviewed advertises a *retail-sector* weekly tracker.
2. **Uncertainty is shown everywhere:**
   - base n on every figure;
   - significance at 95%;
   - small-base fade and suppression (<5 hidden, flags);
   - "not comparable" across question-version breaks.

   YouGov's public tracker shows no margin of error, and Qualtrics' crosstab stats don't carry into dashboards [O]. CIP's position here is defensible and on-brand for a research house.
3. **Grounded assistant with hard citation enforcement.**
   - `api/assistant.py`: the model may only quote the provided figures; code drops any citation that is not a real source; with no sources the answer is "no source"; only aggregates leave the server.
   - Mintel and GWI make similar claims [O], but CIP's enforcement is in code and auditable.
4. **One pre-computed book feeds every screen and export.** The same numbers appear in Explorer, crosstab, trend, PPTX and the assistant. Qualtrics explicitly can't carry crosstab weighting into dashboards [O].
5. **Native editable PPTX charts in brand palette** (`api/exports.py`), plus a board → deck export. Most vendors advertise PPT export, and editability is rarely stated.
6. **Analyst context.** Coresight publishes retail research. With Mintel Leap ("proprietary research and human analysis") as the template, CIP can ground answers in both the survey and Coresight reports. Today the assistant uses survey data only.
7. **Cost-to-serve.** CIP's per-wave book is about 23 KB gzipped (doc 18) and it runs on one core (memory note). Suzy ships a 7.3 MB main bundle [O]. This lets Coresight price low or bundle CIP free into subscriptions.

---

## 6. Market gap register

Severity: **S1** blocks being taken seriously by buyers; **S2** loses competitive deals; **S3** polish or parity.
Priority: **P1** do before or at launch; **P2** next quarter; **P3** later.

### Data

| ID | Sev/Pri | Gap | Competitor evidence | What closing it takes |
|---|---|---|---|---|
| MKT-01 | S1/P1 | **Unweighted, with no representativeness statement.** Results are percentages of "qualified US adults who answered" (`assistant.py` system prompt), with no rim weights to census age, gender, region or income | YouGov "nationally representative samples"; Euromonitor "quota-matched to each market's population" [O] | Decide on weights: rake to ACS on age × gender × region × income, keeping the unweighted figure viewable. Publish a methodology page. Re-test significance with effective n (design effect). Until then, label every view "unweighted" |
| MKT-02 | S1/P2 | **Sample size.** ~400 a week gives ±4.9 pt total MoE and subgroups that fall under small-base thresholds quickly | MC 30k+/day; GWI 2M/yr; Statista 3M [O] | Raise to n≈1,000 a week (±3.1 pt), or offer **pooled 4-week rolling** as the default view (n≈1,600). Pooling is cheaper and needs product, not budget. Show the effective n |
| MKT-03 | S2/P3 | **US only** | GWI 50+, YouGov 49–56, MC 100+, Euromonitor 210+ [O] | Don't chase breadth. If clients ask, add UK or India via a panel partner (Toluna, Market Xcel [O]) with the same questionnaire, starting at n≈1,000 a quarter |
| MKT-04 | S2/P2 | **No behavioural linkage** (receipts or POS) | Numerator Verified Voices; Circana Complete Consumer "receipt, loyalty card, scan panel, and survey" [O] | Partner, don't build. Licensed overlay of category sales indices next to survey trends, with source-type labels and no joined denominators |
| MKT-05 | S2/P2 | **Open-ends discarded.** No open-end handling anywhere in `api/`, `etl/` or `web/src` | Toluna QProbe; Displayr Text Analytics; YouGov BrandIndex Voices [O] | Load verbatims (PII-scrubbed), LLM-code them to themes with a human-review queue, and show themes with counts and example quotes. A strong AI story that stays grounded |
| MKT-06 | S3/P2 | **No respondent-level or microdata delivery** | GWI and YouGov "RLD" [O] | Weighted RLD extract (SPSS/Parquet) per wave for enterprise tier clients, with a disclosure-control review |

### Product and workflow

| ID | Sev/Pri | Gap | Competitor evidence | What closing it takes |
|---|---|---|---|---|
| MKT-07 | S2/P1 | **No audience applicability check before analysis**: users find out a segment is too small only after cells fade | Statista routes `target-group-applicability`, `proposal-population`, `source-population` [O REA] | On audience save, compute n per wave over the last 12 waves and show "available in X of 12 waves, median n=…". Block or flag below the threshold |
| MKT-08 | S2/P2 | **No "what makes this group different" (index/z-score) view** | YouGov Profiles z-scores [O] | One endpoint: for an audience, rank all answers by index vs Total, keeping only significant ones. The data is already in the book |
| MKT-09 | S3/P2 | **Exports are synchronous**: one request builds the file | Statista `exports/:id/cancel\|retry\|download` [O REA] | Fine for single charts. Move board decks and full-question downloads to a job queue once boards get large |
| MKT-10 | S2/P2 | **No recontact or follow-up research path** | YouGov recontact, Numerator Verified Voices, Kantar Marketplace [O] | "Ask this in next week's survey" request form routed to the Coresight research team, with an SLA. A sales lever, not code |
| MKT-11 | S3/P3 | **No event annotations** on trends (Prime Day, tariff dates, CPI) | Civiqs News & Events (doc 18) | `cip_event` table plus markLine (doc 18 gap 6) |

### AI

| ID | Sev/Pri | Gap | Competitor evidence | What closing it takes |
|---|---|---|---|---|
| MKT-12 | S2/P1 | **Ask CIP answers from the latest wave only, with 5 sources** (`SOURCES = 5`, "latest wave's results"). It cannot answer "how has X changed since 2024" | MC agents; GWI Spark; Numerator Nexa [O] | Add trend and crosstab tools (tool use over `/trend` and `/crosstab`) with the same citation enforcement. Keep "never compute new percentages" |
| MKT-13 | S2/P2 | **No AI narrative or slides.** Boards export decks but no written summary | GWI Canvas; Circana "performance narratives"; YouGov "automatic report builder" [O] | Per-board "draft summary" by Claude over pinned items, cited per slide, editable before export |
| MKT-14 | S2/P2 | **No grounding in Coresight research reports** | Mintel Leap "proprietary research and human analysis" with links to sources [O] | Index Coresight report text, with entitlement checks, and let Ask CIP cite both survey figures and report passages, labelled by type |
| MKT-15 | S3/P2 | **No published AI evaluation** | Toluna claims "80% correlation" for synthetic personas; Mintel says no hallucinations [O]. These are vendor claims | Publish a small eval: N questions, citation precision, no-source rate. It turns a trust story into evidence. Do **not** add synthetic respondents |

### Distribution and integration

| ID | Sev/Pri | Gap | Competitor evidence | What closing it takes |
|---|---|---|---|---|
| MKT-16 | **S1/P1** | **No public API, no MCP server, no BI connector.** Every route is a session-cookie internal API (`/api/v1/*`, `/auth/check`) | MC Claude/ChatGPT/Gemini MCP and API; GWI API+MCP; YouGov API+MCP; Statista Connect; Euromonitor in Claude/Copilot; Attest Results API to Power BI, Tableau, Looker, Snowflake [O] | Read-only MCP server exposing `search_questions`, `get_result`, `get_trend` and `crosstab`, returning the same cited aggregates as Ask CIP, authenticated with per-client API keys and metered. Then a CSV/Parquet feed or Snowflake share for BI. This is the single highest-leverage gap |
| MKT-17 | S2/P2 | **No embeds** for Coresight articles | Datawrapper and Flourish embeds (doc 18) | `/embed/` route for chart cards with provenance, to drive traffic from Coresight research to CIP |
| MKT-18 | S3/P3 | **No audience activation** | YouGov DV360/Meta/TTD [O] | Out of scope for an unweighted 400/week panel without identity rights. Do not pursue |

### Trust and methodology

| ID | Sev/Pri | Gap | Competitor evidence | What closing it takes |
|---|---|---|---|---|
| MKT-19 | **S1/P1** | **No public methodology page**: panel source, quotas, qualification, fielding window, weighting (none), data-quality checks, small-base rule | Euromonitor states recruitment, quota-matching and n per market on the product page [O]; YouGov BrandIndex states methodology [O] | One page, linked from every chart footer: panel 114; ~400 qualified of ~500–800 starts; Monday–Wednesday fielding; unweighted; sig test; n<5 suppression; question-version breaks |
| MKT-20 | S2/P1 | **Data quality and fraud story missing** (bot and speeder removal) | Suzy "Biotic" bot detection; Toluna QSphere; Attest human quality review [O] | Document the qualification and cleaning that already exist (the qualified flag, 0-difference reconciliation), and add speeder/straight-liner flags if absent |
| MKT-21 | S2/P1 | **Inconsistent self-reported scale** in CIP docs: `PRODUCT.md` says "144+ waves… 71,000 respondents"; the business description (13 Oct) says 318 waves and 166k; the brief says ~371 and ~190k | n/a | Generate scale numbers from `/healthz` and serving tables, and never hard-code them in marketing copy |

### Commercial and packaging

| ID | Sev/Pri | Gap | Competitor evidence | What closing it takes |
|---|---|---|---|---|
| MKT-22 | S2/P1 | **No packaging decided** (seats, tiers, what clients see vs analysts) | GWI: per seat Pro/Team, API by consumption [O]. Displayr: per user, Enterprise $4,199+, token AI [O]. Attest: credits, unlimited seats [O]. Mintel: unlimited seats at licensed locations [O] | Suggested model [I]: CIP Core bundled with a Coresight research subscription (unlimited seats, read-only); CIP Pro per seat (audiences, alerts, boards, exports); API/MCP metered |
| MKT-23 | S3/P2 | **No self-serve trial** | Displayr free trial; SurveyMonkey self-serve [O] | Public sample dashboard (one topic, last 4 weeks, unweighted label) as lead generation |

### Profile, entitlement and enterprise

| ID | Sev/Pri | Gap | Competitor evidence | What closing it takes |
|---|---|---|---|---|
| MKT-24 | **S1/P1** (for external clients) | **No roles, tenancy or entitlements.** Saved views, audiences, boards and alerts are global, with only owner checks on delete (`team.py: owned()`). Every signed-in user sees every board | Circana "reports… for their specific roles" [O]; GWI Pro vs Team seats [O]; Mintel licensed locations [O] | Add `org_id` to users and every team table, and a role (viewer/analyst/admin). Scope boards and audiences per org. Gate module entitlements (e.g. holiday study, client projects) per org |
| MKT-25 | S2/P1 | **No audit log** of who exported or asked what | Enterprise expectation [I]; Displayr Enterprise MFA and regional servers [O] | Append-only audit table for exports, Ask CIP queries, sign-ins and board shares. Exports already carry provenance (`docs/08`) |
| MKT-26 | S2/P2 | **SSO is Coresight-staff OIDC only.** External client IdPs (SAML/OIDC per tenant), SCIM and MFA are not present | Displayr Enterprise SSO+MFA; SurveyMonkey Enterprise SSO; Statista `sso-sign-in-link` [O] | Per-tenant IdP configuration through a broker (e.g. Entra External ID or WorkOS-type), with SCIM for de-provisioning |
| MKT-27 | S3/P2 | **No data-residency or security collateral** (SOC 2/ISO) | Attest ISO 27001; Toluna ISO 20252; SurveyMonkey US/CA/EU data centres [O] | Security one-pager. The repo being public and the 20 Oct leaked-password incident (memory) must be resolved before any client security review |

**Top five to fix for launch:**
1. MKT-19 methodology page;
2. MKT-01 weighting decision, or at minimum an "unweighted" label;
3. MKT-24 tenancy/roles;
4. MKT-16 read-only API/MCP, which can follow launch but should be on the roadmap;
5. MKT-12 trend-aware Ask CIP.

---

## 7. What prior docs got wrong or left stale

| Prior claim | Where | Correction (23 Oct 2026) |
|---|---|---|
| Portal "did not establish persistent React dashboards, collaboration or AI routes" | Codex `competitor-landscape.md` finding 5 | **Outdated.** CIP now has `/boards` (with comments and deck export), `/audiences`, `/alerts`, `/ask` and `/team/views` (`api/team.py`, `api/main.py`). The "workflow gap" narrative is mostly closed; the gap is now data, API/MCP and enterprise |
| CIP exports are "CSV only" | UI doc 18 §5 gap 2 | **Outdated.** Native XLSX and PPTX are in `api/exports.py`, and a board → PPTX deck is in `team.py` |
| "Copy data for AI / Ask AI — defer" | doc 18 §5 gap 12 | The market moved to MCP connectors (MC, GWI, YouGov, Statista, Euromonitor, Attest [O]). Defer the button, not the MCP server |
| Morning Consult page URL `pro.morningconsult.com/our-products` | Codex C07 | Now 301s to `intel.morningconsult.com/mc-content/our-products`. The product line has added agents and three MCP connectors [O] |
| YouGov Profiles URL `business.yougov.com/product/profiles` (brief) | brief | Lives at `yougov.com/business/products/profiles` [O] |
| Crunch grouped under YouGov; Displayr under Forsta | brief | Neither ownership is stated on the vendors' current pages [U]. Treat them as separate products |
| `PRODUCT.md` "144+ waves, 71,000+ respondents, 828+ concepts" | `PRODUCT.md` | Stale against the business description (318 waves, 166k on 13 Oct) and the brief (~371, ~190k). See MKT-21 |
| Codex did not cover India peers, AI distribution via MCP, or enterprise packaging | Codex | Added here (§3d, MKT-16, MKT-22 to MKT-27) |
| Codex retrieved 22 of 23 sources | Codex | Today several of those URLs 404 or are blocked (MC methodology, GWI methodology, Ipsos US, Mintel consumer, Kantar Profiles, eMarketer). Public evidence decays fast, so re-verify before quoting externally |

---

## 8. Unknowns

| # | Unknown | Why it matters | How to resolve |
|---|---|---|---|
| U1 | Morning Consult and Statista weighting and per-wave n | Fair comparison with CIP's unweighted n≈400 | Vendor methodology PDFs, or a sales call |
| U2 | eMarketer product surface (blocked by Cloudflare) | The closest Coresight peer | Normal browser session, no login |
| U3 | Whether Kantar Worldpanel is now part of Numerator | Competitive map for US panels | Press release check |
| U4 | Competitor in-app chart stack (GWI, MC apps are gated) | Design parity | Only from public demos or trials. Not attempted |
| U5 | Pricing for all syndicated vendors (none public) | Packaging (MKT-22) | Analyst reports or procurement contacts |
| U6 | Whether CIP's OIDC supports external tenants | MKT-26 scope | Read `auth.py` and confirm with IT |
| U7 | Panel 114 identity and its own weighting or quotas | MKT-01/19 | Forsta and panel vendor documentation |
| U8 | Indian SaaS doing syndicated survey analytics at CIP's level | Possible build or partner | None found. Low confidence that none exists |
| U9 | Exact Circana and Statista export editability | PPTX differentiation claim (§5.5) | Trial or demo |

**REA evidence IDs (23 Oct 2026, CDP `127.0.0.1:9334`, isolated profile)**
- `ev_2e634a448a6238a866335d67ac9e0d59e6b9b52009c426db6a61972f0dbbcbb5`: GWI platform bundle (HubSpot CMS).
- `ev_4ccad9715886ed5e7dc7453df53033fe50dc3f24d56d9901cca94410c33b2f25`: Statista Consumer Insights bundle (React, Vite/rolldown, route table).
- `ev_f27417534a701a2b7754754f2d35e580eade46480105d859980b4b0041e9d056`: YouGov Profiles page (OneTrust, New Relic).
- `ev_95cf4294842c272317a5993f85279260dd3e0698eea027b12efe0583c0c73be3`: Crunch app shell (`/authentication/workspace`).
- `ev_6a4da48455e69c9d6f25d10f450c24ef975719dd946fb2a37f16875466880201`: Suzy app (Angular, 7.3 MB main, credits).
- `ev_1e73318fa446125cee993380fb86b9110802786bed745be2fd37e305e1a46def`: target list (eMarketer Cloudflare challenge).
