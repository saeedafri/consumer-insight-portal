# Consumer Insight Portal — Features

What the portal provides, grouped the way it is demoed. Public pages need no sign-in; everything under **Portal** is behind a work-account login.

## Public site (SEO, no sign-in)

| Page | What it is |
|---|---|
| **Home** | The pitch, headline numbers (370+ waves, 190,000+ responses, weekly since Dec 2020), and links in. Carries page title, description, canonical URL, Open Graph preview and search-engine data (JSON-LD). |
| **Features** | Every capability below, as cards. |
| **Methodology** | Panel, qualification, fielding, weighting, data quality, small-base rule and significance testing — in plain language. |
| **Sign in** | Continue with a Coresight or client work account. |
| sitemap.xml / robots.txt | So search engines index the public pages and skip the app. |

## Portal — exploring the data

| Feature | What it does |
|---|---|
| **Survey library** | Every tracker, annual and ad hoc wave, newest first, each with fielding dates, base and source. |
| **Wave overview** | A wave's headline numbers at a glance, click any to open it. |
| **Question explorer** | Any question by total, generation, gender, income, region and more, with significance against the previous wave. |
| **Cross-tabs** | One question by two cuts at once, for one week or the last four pooled. |
| **Trends** | A question across every wave it was asked, with year-on-year comparison; wording changes kept apart. |
| **Compare waves** | Any waves of one question side by side, with what moved and whether it is significant. |
| **Audience index** | Pick a group (e.g. Gen Z shoppers) and see where they over- and under-index. |
| **Survey preview** | The questionnaire as fielded, question by question. |
| **What changed** | Per wave, the answers that moved significantly. |

## Portal — finding and asking

| Feature | What it does |
|---|---|
| **Plain-English search** | Questions by words, codes or answer labels; typo- and synonym-tolerant. |
| **Ask CIP** | A question in plain words, answered only from published figures, every source cited. |

## Portal — saving and sharing

| Feature | What it does |
|---|---|
| **Boards** | Pin charts to a board; download a board as a slide deck. |
| **Saved views** | Keep an exact view (wave, screen, question, cuts) under a name. |
| **Alerts** | Be told when a tracked figure moves. |
| **Exports** | Any table to CSV and Excel; decks to PowerPoint. |

## Data and trust

- **Unweighted by default**, with a Census-weighting toggle; significance always tested on unweighted counts.
- Every wave **reconciled with the survey platform** before it is marked verified.
- **Small bases flagged** (groups under 50); every figure shown regardless.
- A reworded question is a **new version** — trends never join two versions.

## Access and integration

- **Subscriptions / access control** — people see only the products and waves they are entitled to.
- **API keys** — programmatic access to the same figures.
- **MCP connector** at `/mcp` — use the portal's data from AI tools by API key.
- **Audit log** — who opened what, for admins.

## Delivery

- **Next.js static export + FastAPI** — public pages are plain pre-built HTML (fast, indexable); the portal is a single-page app; the database stays on Azure.
- **Everything precomputed in the ETL** — screens open in milliseconds; measured at p95 ~2 ms for 16,000 users at once on one CPU core.
