# 03 · Every viable technology, compared honestly

**The question:** what should CIP be built with?

**The constraints:**
- one Azure App Service per product: staging about 4.5 GB and 1 vCPU, production about 9.88 GB and 2 vCPU;
- MySQL with a verified Python data layer;
- a client product that must feel instant and serve many users;
- the same pattern reused for CIQ, MIP and MDB.

**Evidence keys:**
- **[B]** our benchmark, [02](02-benchmarks.md)
- **[P]** production and repository evidence, [01](01-evidence-from-sip-and-mip.md)
- **[W]** web sources, listed in [08](08-sources.md)

## 1. The short answer to "Node.js, TypeScript, JavaScript, Streamlit or Python?"

| Question | Answer | Why |
|---|---|---|
| **What runs in the browser?** | **TypeScript** (compiled to JavaScript) with **React** | Only code in the browser can answer a click in milliseconds (see [05](05-millisecond-ui.md)). TypeScript catches errors before release that plain JavaScript lets through. React has the biggest hiring pool:<br>• Stack Overflow 2026: 41.5 % of developers<br>• India postings: 5,653 React vs 131 Streamlit [W] |
| **What runs on the server?** | **Python** with **FastAPI** | CIP's verified data layer, significance logic, cube and harmonisation are already Python. One FastAPI worker served 7,391 req/s [B], about 100× what 300 active users need. FastAPI usage rose to 18.5 % in Stack Overflow 2026 [W]. |
| **Node.js?** | **Only as a build tool** (Vite), never as the server | Node served 4–7× more requests per second than FastAPI [B]. But the page time users saw was identical: 0.20 s for both at 40 users. Switching would mean rewriting verified Python for capacity nobody will use. |
| **Plain JavaScript?** | No | It is the same runtime as TypeScript without the type safety. There is no saving. |
| **Streamlit?** | **Only for internal staff pages** with a handful of users (Mappings, Data Health, Publications) | It is the fastest way to build a screen. But its time grows about 0.1 s per extra simultaneous user, even when well written and even on the new 1.66 server [B]. It cannot set an HttpOnly cookie from Python. In production its apps peak at 80–86 % of server memory [P]. |

## 2. Ranked: all options

**Weights reflect CIP's needs**

| Criterion | Weight |
|---|--:|
| Speed with many users | 20 |
| Memory on 4.5/9.88 GB | 15 |
| Security by default | 15 |
| UX and design ceiling | 15 |
| Reuse of verified Python / time to build | 15 |
| Team and hiring | 10 |
| Licence + hosting cost | 10 |

Scores are 1 (poor) to 5 (excellent), and the maximum is 500.

| # | Option | Speed | Mem | Sec | UX | Reuse | Team | Cost | **/500** | Verdict |
|--:|---|--:|--:|--:|--:|--:|--:|--:|--:|---|
| 1 | **React + TypeScript SPA (Vite) + FastAPI** | 5 | 5 | 5 | 5 | 4 | 4 | 5 | **475** | **Adopt** |
| 2 | Vue 3 + FastAPI | 5 | 5 | 5 | 5 | 4 | 3 | 5 | 465 | Good; React wins on team fit and hiring |
| 3 | Svelte 5 / SvelteKit (static) + FastAPI | 5 | 5 | 5 | 5 | 4 | 2 | 5 | 455 | Good tech, small hiring pool (India: 42 postings) |
| 4 | Angular + FastAPI | 4 | 5 | 4 | 5 | 4 | 3 | 5 | 430 | Heavier. Many 2024–26 advisories (1 critical, 29 high) [W]. |
| 5 | HTMX 2 + FastAPI/Jinja (server-rendered) | 4 | 5 | 4 | 3 | 5 | 3 | 5 | 415 | Good for simple pages. Every interaction is a server round trip (≥ 220 ms from India). Rich grids and charts still need JS. |
| 6 | React + Node (Fastify/NestJS) back end | 5 | 5 | 4 | 5 | 1 | 4 | 5 | 415 | Rewrites verified Python for unneeded speed |
| 7 | React + Go or .NET back end | 5 | 5 | 5 | 5 | 1 | 2 | 5 | 410 | Same, plus a skills gap |
| 8 | Next.js in server mode | 5 | 4 | 2 | 5 | 3 | 4 | 5 | 400 | Adds a Node server. **2026 so far: 5 critical and 15 high advisories**, including React2Shell, CVSS 10, and its follow-ups [W]. A static export is fine (= option 1). |
| 9 | **Dash 4 (pure Python)** | 3 | 4 | 3 | 3 | 5 | 3 | 5 | 365 | **Best pure-Python option.**<br>• Stateless and runs multiple workers<br>• 1.06 s at 40 users, 4× better than Streamlit [B]<br>• But a heavy bundle (Plotly 1.48 MB gz) and a server round trip per callback |
| 10 | **Streamlit, written well** (SQL totals, `st.login`, fragments) | 2 | 4 | 3 | 2 | 5 | 4 | 5 | 340 | **Not optimal for clients.** Fine for under ~10 concurrent internal users. |
| 11 | Blazor Server / Phoenix LiveView | 3 | 4 | 4 | 4 | 1 | 1 | 5 | 315 | A persistent connection per user. Microsoft itself recommends keeping UI latency under 250 ms, which India → US already uses up [W]. New language for the team. |
| 12 | Survey SaaS (Harmoni, Displayr, Crunch) | 4 | 5 | 4 | 3 | 1 | 3 | 1 | 315 | **Not optimal.** Per-viewer cost, a second pipeline, competitor ownership or metering ([04](04-marketplace-buy-vs-build.md)) |
| 13 | Power BI Embedded (buy) | 4 | 5 | 4 | 2 | 1 | 2 | 3 | 310 | **Not optimal.** No survey statistics; DAX; Microsoft look ([04](04-marketplace-buy-vs-build.md)) |
| 14 | Reflex, NiceGUI, Panel, Shiny, Solara, Taipy | 2 | 2 | 3 | 3 | 4 | 2 | 5 | 290 | **Not optimal.** The same server-side session model as Streamlit, with smaller communities. NiceGUI had 21 advisories, 6 of them high, since 2024 [W]. |
| 15 | Low-code (Retool, Appsmith, ToolJet, Budibase) | 3 | 4 | 3 | 2 | 2 | 3 | 2 | 275 | **Not optimal.** Per-user fees, SSO only on Enterprise tiers, no survey statistics |
| 16 | Superset / Metabase (self-host) | 3 | 2 | 3 | 2 | 2 | 3 | 4 | 265 | **Not optimal.** Extra services (metadata DB, Redis), no survey stats, branding limits |
| 17 | **Streamlit, "load the table and show it"** (the SIP/MIP habit) | 1 | 1 | 2 | 2 | 5 | 4 | 5 | **260** | **Worst realistic option** |
| 18 | Gradio, Mesop | 1 | 2 | 1 | 1 | 3 | 2 | 5 | 195 | **Ruled out.**<br>• Built for AI demos<br>• Gradio: 24 advisories since 2024<br>• Mesop: archived 2 Oct 2026 [W] |

## 3. Why the winner wins

1. **Speed under load.** It stayed flat: 0.20 s at 40 simultaneous users, against 4.35 s for the best Streamlit (22×) [B]. Clicks after the first load are answered in the browser in under 16 ms ([05](05-millisecond-ui.md)).
2. **Memory.**
   - About 82–100 MB per API worker, and it does not grow with users [B].
   - The whole production plan uses about 4.2 GB of 9.88 GB ([06 §7](06-system-design.md)).
   - Compare: Streamlit "load the table" peaked at 3.67 GB for one 75 MB table [B]. SIP production peaked at 6.9 GB of 8 GB [P].
3. **Security, by construction.**
   - A normal request/response server sets an HttpOnly + Secure session cookie and checks it on every call.
   - React escapes output.
   - Anti-forgery headers are standard.
   - Caveat [P]: MIP-FAST-React kept an unsigned, script-readable cookie even on FastAPI. The controls in 06 §6 must actually be built.
4. **User experience.**
   - Real URLs for every view, so share links and the Back button work.
   - No full-page re-runs and no white flash.
   - Coresight's own look.
   - In SIP and MIP, every one of these needed hacks [P]:
     - 194 `unsafe_allow_html`
     - 34 `<script>`
     - two patched Streamlit `index.html` files
5. **Reuse.** CIP's Python data layer moves behind FastAPI unchanged, so its verified results carry over: 147,635/147,635 answers equal to Forsta; 667/667 and 788/788 published cells reproduced.
6. **Team and hiring.**
   - React is already used in SMS-UI, ems-frontend and MIP-FAST-React.
   - FastAPI is Python, the language of every data project here.
   - India postings: React 5,653; FastAPI 1,136; Streamlit 131 [W].
7. **Cost.** MIT and Apache licences, on the App Service we already pay for ([07](07-cost-model.md)).

## 4. Why the worst are worst

**Streamlit "load the table and show it"** (#17)
- In our benchmark: 3.67 GB peak and 8.46 s median at 40 users [B].
- In production [P]:
  - SIP peaked at 6.9 GB of 8 GB, with a 22 s worst response.
  - MIP peaked at 3.2 GB of 4 GB, with a 44.7 s worst response.
  - MIP staging logged a 240 s render (15 Oct).
- On a 4.5 GB staging box, two such pages would push it to out-of-memory.

**Gradio and Mesop** (#18)
- Built for AI demos, not client portals.
- Gradio had a cluster of high-severity file-access advisories in 2024–2026.
- Mesop is no longer maintained.

**Looker, Tableau, Sigma, Domo**
- Not ranked: $100k–600k a year at 300–1,000 viewers ([04](04-marketplace-buy-vs-build.md)), with no survey statistics.

## 5. Why "not optimal" is not "bad"

**Streamlit written well** (#10)
- Our benchmark: 0.33 s → 4.35 s from 1 to 40 users [B].
- MIP's staging-like test: about 10 heavy users per process before p95 passes 5 s [P].
- Fine for the 3–5 internal staff pages. So CIP keeps Streamlit for Mappings, Data Health and Publications.
- For clients it fails because:
  - the slope is set by the framework and cannot be coded away;
  - it cannot scale by adding workers, only by sticky load-balancing whole servers;
  - every click needs a server round trip, which from India is already ≥ 220 ms before any work.

**Dash** (#9)
- Its server is stateless, so workers really do add capacity: 1.06 s at 40 users [B].
- Choose it **only if the team cannot staff any TypeScript**.
- Limits:
  - a design ceiling;
  - Plotly weighs 1.48 MB gz, against 368 KB for ECharts [W];
  - each interaction is still a Python round trip.

**HTMX + FastAPI** (#5)
- Light and simple, with no build step.
- Good for forms and admin pages.
- But each filter change is a server round trip. Cross-tab pivoting, sorting and charts are better done in the browser.

**Node or Go back ends** (#6, #7)
- Faster on paper: Node 49,562 req/s vs FastAPI 7,391 on the same machine [B]; TechEmpower R23 shows a similar ordering [W].
- But the user-visible time is identical [B], so it is a rewrite with no benefit.

**Power BI Embedded** (#13)
- The cheapest buy option ($7.8–15.3k/yr) [W].
- It loses on survey statistics, look and lock-in ([04](04-marketplace-buy-vs-build.md)).

## 6. Facts that changed since docs/12 (18 Oct)

| Topic | Change |
|---|---|
| **Streamlit 1.57+** (current 1.66.0, 14 Oct 2026) | Runs on Starlette/Uvicorn instead of Tornado. Our re-run shows the same per-user slope (4.04 s at 40 users vs 4.35 s on 1.55) [B]. There is still no multi-worker mode; scaling remains load balancer + sticky sessions [W]. |
| **Versions** | React 19.3, Vite 8, React Router 8, SvelteKit 3, Angular 22, Python 3.15 released, FastAPI 0.149 [W] |
| **TechEmpower** | Sunset 24 Mar 2026; no Round 24 [W] |
| **MIP "5-user wall"** | It was a laptop test. Tuned Streamlit holds about 10 heavy users per process [P]. docs/12's 20–60 server estimate for 300 users is replaced by the model in [07](07-cost-model.md). |

## 7. When we would choose differently

| If… | Then… |
|---|---|
| A screen is internal, for fewer than ~10 concurrent staff | Streamlit written well |
| No one can maintain TypeScript | Dash with stateless callbacks and gunicorn workers |
| Clients only need monthly static reports | Generate Excel/PDF from the data layer; no portal |
| Clients demand a vendor product and accept per-viewer fees | Get a quote from Forsta Reportal (no data movement), then Power BI Embedded |
| Ad-hoc analytics over hundreds of millions of rows in the browser | Add Perspective or DuckDB-WASM for that one screen. DuckDB-WASM is 7.6 MB gz [W], so not for the default path. |
