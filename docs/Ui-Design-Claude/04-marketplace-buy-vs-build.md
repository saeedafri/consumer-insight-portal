# 04 · Marketplace: buy vs build (national and international)

**Researched 20 Oct 2026.** Prices are vendor list prices unless marked "3rd-party" (Vendr, G2, blogs). "Not public" means the vendor only quotes.

**What CIP needs from any product**
- question browser
- cross-tabs with banners and **significance letters** on **weighted / effective bases**
- trends across 320 waves (2018 →)
- cohort filters
- Excel/PNG export
- saved views
- SSO
- Coresight branding
- external client users with per-client data limits

## 1. Survey and market-research reporting platforms

These are the closest to CIP in function.

| Product (origin) | Price points | External clients · white-label · SSO | Sig letters / weighted bases | Fit |
|---|---|---|---|---|
| **Infotools Harmoni** (NZ; owned by **Ipsos**) | Creator $5,200/user/yr; Explorer $1,700–2,100; **viewers $500/yr per 10**; services $10–40k | Yes · client-branded · SAML/OAuth | **Yes / yes** (weights on Creator) | **Good on features.** But it is owned by a research competitor, and Coresight would run a second pipeline. |
| **Displayr** (AU) | Pro $3,359/user/yr; Enterprise $4,199/user/yr. Viewing metered in server hours: +1,000 h = $1,340. **Dashboards stop when hours run out.** External hosting fee not public. | Yes · subdomain/branding (Ent.) · SSO (Ent.) | **Yes** (letters, complement tests, minimum-base rules) / weights listed | **Partial–good.** Best stats engine, but risky metering. |
| **Crunch.io** (YouGov, UK) | Not public | Branded client dashboards (case study) | **Yes**: weighted pairwise tests on effective base (release note 29 Jan 2024) | **Partial–good.** Methods match; price unknown. |
| **Forsta Reportal / Dashboards / Dapresy** (Coresight already uses Forsta Surveys) | Not public | Shareable to end customers, with permissions | Yes | **Partial–good.** No data movement needed. **Ask the Forsta account manager for a quote.** It costs nothing to ask. |
| **Q Research Software** | $3,259/user/yr | Desktop only | Yes | Poor as a portal |
| **Protobi** (US) | $960/workspace (≤12 users); private instance quoted | Branded portal | Yes / yes | Partial. The 12-user model doesn't fit 300+ clients. |
| **MarketSight** (now Dynata) | Old list $995–1,495/user/yr; current not found | Shareable | Yes | Partial; product status unclear |
| **Qualtrics XM / CX** (US) | 3rd-party median about $28.5–30k/yr; $125–420/user/month | Yes | Stats iQ add-on | Poor–partial. Expensive; data would move into Qualtrics. |
| **QuestionPro** (India-founded, Pune office) | $83–99/user/month | Branding; SSO not found | Chi-square, weighting | Partial–poor |
| **Voxco** (Canada; India office) | Not public | Shared dashboards | Crosstabs with significance | Partial |
| **Zoho Survey** (India) | On page, INR | SAML on Enterprise | No | Poor |
| Alchemer, SurveyMonkey, Conjointly | $25–1,895/user | Limited | Limited | Poor |
| E-Tabs, Askia, Merlinco | Not public | — | Report automation / tables | Poor–unknown |

## 2. Embedded BI and analytics

| Product (origin) | Price points | Clients · white-label · SSO · row-level security | Survey stats | Fit |
|---|---|---|---|---|
| **Power BI Embedded** (Microsoft) | **F8 reserved $7,504/yr**; F16 $15,008/yr; A1 PAYG $8,831/yr; Pro $14/user/month (publishers only). **Viewers need no licence** ("embed for your customers"). | Yes · full white-label through the SDK · your own auth · effective identity | **None built in.** Sig letters and effective bases must be written in DAX. R/Python visuals are not supported in this embed mode. | **Partial–good.** Cheapest at scale, but the team must learn DAX, it looks like Power BI, and Coresight still needs its own app shell. |
| **Metabase** (US; open source + Pro) | OSS free; Pro $6,210/yr incl. 10 users + $130/user/yr; Enterprise from $20k | Pro: SSO/JWT, row and column security, white-label | None | Partial (internal) |
| **Apache Superset** / Preset | OSS free; Preset embed from $500/month per 50 viewers | Guest tokens with row-level filters; fork to white-label | None | Partial. Needs its own metadata DB and Redis, which is memory on a 4.5 GB box. |
| **Tableau Embedded** | 3rd-party about $414/viewer/yr (≈ $124k for 300) | Yes | None | Poor (cost) |
| **Looker** (Google) | 3rd-party $180–198k platform + $400/viewer | Yes | None | Poor |
| Sigma, Domo, ThoughtSpot, Qlik | Quotes / Vendr medians $50–57k | Yes | None | Poor |
| Grafana | $8/active user/month | Limited | None | Poor (built for monitoring) |
| **Zoho Analytics** (India) | About $30–575/month (2–50 users, 3rd-party); white-label quoted | White-label from Premium | None | Partial–poor |
| **FusionCharts** (India) | $1,329–2,379/yr (developers) | n/a (JS chart library) | n/a | Component only |
| Cube.dev (semantic layer) | Premium $80/developer + **$20/viewer/month** | Row-level via security context | None | Component only; viewer fees add up |
| Evidence.dev · Observable Framework · Rill | OSS free; Evidence Team $2,500/month *excludes* external viewers; Rill embed capped at 100 seats | — | None | Components / poor at scale |

## 3. Low-code app builders

| Product (origin) | Price | SSO / white-label | Survey stats | Fit |
|---|---|---|---|---|
| Retool | External users $4–8/month in bands; SSO + white-label **Enterprise only** | Enterprise | None | Poor–partial |
| **Appsmith** (Indian founders) | Business $15/user, **capped at 99 users**; Enterprise $2,500/month per 100 users | Enterprise | None | Poor |
| **ToolJet** (Bangalore) | $199/builder/month with 100 end users; Enterprise quoted | From Team | None | Poor |
| Budibase | $299/month + $5/end user/month | Business | None | Poor |

None of these can do significance letters or weighted bases. Coresight would build all the survey logic anyway, inside the tool's UI limits.

## 4. Annual licence cost at 300 and 1,000 client viewers

Licence only. CIP's own hosting is in [07](07-cost-model.md).

| Option | 300 viewers / yr | 1,000 viewers / yr |
|---|--:|--:|
| **Build (this design)** | **$0 licence.** Hosting about $1.5–2.2k (07) | **$0 licence.** Same hosting |
| Power BI Embedded, F8 / F16 reserved + 2 Pro | $7,840 | $15,344 |
| Infotools Harmoni (1 Creator + viewer bundles) | $19,200 + $10–40k services | $54,200 + services |
| Displayr Enterprise (2 seats, 2 h/viewer/month) | $19,118 + hosting fee | $40,558 + hosting fee |
| Retool Business (banded) | $24,000 (no SSO) | $62,400 |
| Budibase Business | $21,588 | $63,588 |
| Preset (Superset) | $36,720 | $120,720 (before discounts) |
| Metabase Pro, per-user | $43,910 | $134,910 |
| Cube Premium | $73,920 | $241,920 |
| Tableau (3rd-party) | ≈ $124,200 | ≈ $414,000 |
| Looker (3rd-party) | $300–318k | $580–598k |

**Assumptions behind the table**
- Power BI capacity sizes (F8 for 300 viewers, F16 for 1,000) are estimates.
- Displayr assumes 2 viewing hours per viewer per month.
- Every buy option except Power BI and Harmoni hides part of its price behind a quote.

## 5. Verdict on buying

**The three best buy options, and why each still loses to build for CIP**

1. **Power BI Embedded** (about $7.8–15.3k/yr)
   - **For:** Azure-native, viewers need no licence, white-label.
   - **Why it loses:**
     - No survey statistics. Effective-base z-tests and column letters would have to be written in DAX, a language nobody on the team uses.
     - Python visuals are blocked when embedded.
     - Shared capacity throttles under load.
     - It looks like Power BI, not Coresight.
     - Coresight still needs a shell for the question browser, saved views and SSO.
     - It is a second semantic layer next to the verified cube.
2. **Infotools Harmoni** (about $19–54k/yr + services)
   - **For:** built for market research.
   - **Why it loses:**
     - It is owned by Ipsos, a direct competitor that would host Coresight's data.
     - It means a second ETL.
     - The services fees are significant.
     - It is "client-branded", not white-label.
3. **Displayr** (about $19–41k/yr + fee)
   - **For:** the best stats engine.
   - **Why it loses:**
     - Viewer-hour metering takes **dashboards offline when hours run out**. That is unacceptable for paying clients.
     - Data sits in Displayr's cloud.
     - Branding is limited to a subdomain.

**Why build wins here**
- CIP already has the hard parts, verified: ETL, harmonisation, a 2.1 M-cell cube, and reconciliation against Forsta.
- Significance letters are a small, known piece of code: the column-proportion z-test on effective base that Crunch adopted.
- Hosting is a fixed $1.5–2.2k/yr however many clients sign up, while every buy option charges per viewer or by capacity.
- **Growth makes build cheaper per client; it makes buy more expensive.**

**Worth one email before committing:** a Forsta Reportal quote. It is the only buy option with zero data movement.

## 6. Sources

**Azure and Microsoft**
- Prices: Azure Retail Prices API (prices.azure.com, queried 20 Oct 2026)
- App Service Linux pricing, Static Web Apps, Front Door pricing
- Power BI Embedded and Fabric pricing pages
- learn.microsoft.com: embedded-analytics-power-bi (2025-12-15), embedded-capacity (2026-05-12)
- Power BI Pro price change (fabric community blog; The Register, 2 Apr 2025)

**Survey platforms**
- displayr.com/pricing
- qresearchsoftware.com/pricing
- crunch.io/release-notes/2024-01-29
- crunch.io/case-studies/prodege
- forsta.com/resources/reporting
- infotools.com/pricing
- protobi.com
- questionpro.com/pricing
- conjointly.com/pricing
- surveymonkey.com/pricing
- voxco.com/voxco-analytics

**BI and analytics tools**
- metabase.com/pricing
- superset.apache.org embedding docs
- preset.io/pricing
- grafana.com/pricing
- thoughtspot.com/pricing
- qlik.com/pricing
- sigmacomputing.com/pricing
- zoho.com/analytics/pricing
- cart.fusioncharts.com
- cube.dev/pricing
- evidence.dev/pricing
- rilldata.com/pricing

**Low-code builders**
- retool.com/pricing
- appsmith.com/pricing
- tooljet.com/pricing
- budibase.com/pricing

**Third-party price sources**
- vendr.com (Tableau, Sigma)
- explo.co (Looker)
- capterra and getapp (Harmoni)
- chattermill and uxtweak (Qualtrics)
