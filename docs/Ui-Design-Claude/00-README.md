# Ui-Design-Claude: CIP technology decision and final system design

**Date:** 20 Oct 2026 · **Author:** Claude (Opus 5.5) · **Status:** recommendation for decision

**Scope:** CIP (Coresight Insight Platform), built on **one application server from IT plus one Azure MySQL**, and reusable for CIQ, MIP and MDB.

**Merges:**
- this investigation (REA method, benchmarks, production evidence);
- the ChatGPT review in [`docs/UI-Design-ChatGPT/`](../UI-Design-ChatGPT/ChatGPT-Recommended_design.md); comparison in [09](09-chatgpt-vs-claude.md).
- **1-core Debian benchmark of every stack (Docker, 20 Oct): [14](14-docker-1core-benchmark.md)**: RAM, requests/s and latency for FastAPI, Node, Next.js SSR and static, Dash and Streamlit at 4.5 GB and 9 GB.

**Replaces:** [`docs/12`](../12-ui-technology-decision.md) and [`docs/13`](../13-ui-system-design.md), both kept for history.

> **Stress test results: [STRESS-TEST-RESULTS.md](STRESS-TEST-RESULTS.md)** (Azure staging, 20 Oct 2026).
> - Serving design: **0.04 ms** per widget inside MySQL; the database carries **≈ 4,700 reads/s** with no cache.
> - **750,000 requests in 5 min** at p99 0.4 ms, 0 errors, flat memory.
> - **≈ 8,600 users at once on staging, ≈ 17,500 on production.**
>
> **ETL vs backend:** the ETL now ends at screen-agnostic serving tables ([10](10-database-serving-design.md)). Dashboards are backend-only; the Holiday dashboard is just a sample.

> **UI design: [13-ui-design.md](13-ui-design.md).** Recommended direction: the "research desk" (option C). Mockups of Overview, Explore, Analysis, Trends and phone are in [ui/images/](ui/images/), built from real CIP data.

## The answer

**Build CIP with these four pieces:**
1. **React 19 + TypeScript** in the browser, with an in-browser data engine.
2. **Python + FastAPI** on the server.
3. **One background worker.**
4. **Your Azure MySQL**, holding a versioned cube.

All of it runs on the one server. **Keep Streamlit only for internal staff pages.**

ChatGPT, reviewing independently, reached the same stack.

### Same screen, same data, timed until the chart and table are fully drawn [02 §0](02-benchmarks.md)

These are results at **40 users acting at the same moment**. The matched test was re-run after ChatGPT's critique.

| Variant | Page ready | Click → new result | Server memory |
|---|--:|--:|--:|
| Streamlit (written well) | 3.99 s | **2.85 s** | 135–149 MB |
| Dash (best pure Python) | 1.99 s | 0.98 s | 69–75 MB |
| FastAPI + React-style page | 0.77 s | **0.12 s** | 69 MB |
| Node.js + the same page | 0.80 s | 0.14 s | 28 MB |
| **FastAPI + data pack in the browser (the design)** | 0.93 s | **0.07 s**, and **0.02 s** with one user | 86 MB |
| Streamlit, "load the table and show it" (SIP/MIP habit) | 8.46 s (first run) | — | **3,674 MB peak** |

**What the numbers say**
- **Clicks.** Streamlit's click time rises in a straight line as more people act at once. Ours stays flat.
- **Node vs Python.** Node and FastAPI are the same for users, so the server language is not the lever.
- **The pack.** It gives a 20 ms click because no request leaves the browser.

## How many users, and the working dashboard (new)

The Holiday Survey Databank from the analysts' PDF is **built and running**:
- [`web/`](../../web/src/App.tsx) (React + TypeScript)
- [`api/main.py`](../../api/main.py) (FastAPI, Python)
- [`api/dashboards.py`](../../api/dashboards.py) (backend builder; reads the serving tables)

Every this-week and prior-week number matches the PDF ([12](12-holiday-dashboard.md)).

The database serving design is in [10](10-database-serving-design.md):
- the ETL's last step writes finished rows for every question × cut;
- the backend reads one primary-key range per widget and caches it.

| Measured | Staging (4.9 GB, 1 vCPU assumed) | Production (9.88 GB, 2 vCPU assumed) |
|---|--:|--:|
| API memory | 137 MB | 253 MB |
| Server time per request | 0.3–0.6 ms | 0.3–0.6 ms |
| Sustained capacity on Azure (≤ 50 % CPU) | ≈ 860 req/s | ≈ 1,750 req/s |
| **Active users at the same time** | **≈ 8,600** | **≈ 17,500** |
| Registered customers (10 % active at peak) | ≈ 86,000 | ≈ 175,000 |
| Open dashboard / switch wave | 0.07 s / 0.01 s | same |

Method, raw output and assumptions: [11](11-capacity-staging-production.md).

## Why not "MySQL + Streamlit, just show the data"?

The business team's question, answered with evidence:

| # | Finding | Evidence |
|--:|---|---|
| 1 | **Our Streamlit apps already fill their servers.**<br>• SIP production: 6.9 / 8 GB, worst response 22 s<br>• MIP production: 3.2 / 4 GB, worst 44.7 s<br>• MIP staging: a 240 s render | Azure export, logs ([01](01-evidence-from-sip-and-mip.md)) |
| 2 | **Every Streamlit click is a server re-run**, queued behind every other user in one Python process. There are no workers to add. | Measured slope ([02](02-benchmarks.md)); Streamlit docs |
| 3 | **Millisecond clicks need the data in the browser.**<br>• A whole wave is 60 KB gz, smaller than Streamlit's own 512 KB start-up script.<br>• From India every server round trip is ≥ 220 ms. | [05](05-millisecond-ui.md) |
| 4 | **About 38 % (SIP) and 22 % (MIP) of commits** went to sign-in, performance and Streamlit workarounds | Verified git history ([01](01-evidence-from-sip-and-mip.md)) |
| 5 | **Buying costs more and still lacks survey statistics:**<br>• Power BI $7.8–15k/yr (no significance letters)<br>• survey SaaS $19–54k/yr<br>• enterprise BI $100k–600k/yr | [04](04-marketplace-buy-vs-build.md) |
| 6 | **Hosting stays flat as clients grow:** about $1.8–2.7k/yr per product, against about $22k/yr for Streamlit at 300 active users | [07](07-cost-model.md) |

**Corrected honestly:**
- The old "5-user wall" was a laptop test.
- Several SIP memory disasters were our own bugs, since fixed.
- Most SIP/MIP security holes were our code, not the framework.
- Our first benchmark was unmatched; it was re-run.

The decision survives all of these corrections.

## The final system design: [06](06-system-design.md)

| Part | Choice |
|---|---|
| Browser | React 19 + TS (Vite static), ECharts, AG Grid Community, TanStack Query, **in-browser pivot over versioned wave packs**, significance letters in TS |
| Server | **One** server running: the front (TLS, brotli, static files), FastAPI workers, and **one** job worker. No Redis, broker, Node server or Kubernetes. |
| API | Modular FastAPI:<br>• OIDC + PKCE, HttpOnly session cookie<br>• entitlements default-deny<br>• private versioned packs<br>• byte-capped version-keyed cache<br>• single-flight, admission limits |
| Jobs | `cip_job` table with leases (MySQL 8 `SKIP LOCKED`): ETL, cube builds, exports to private Blob |
| Data | Azure MySQL **General Purpose** tier (staging today is Burstable B2s and peaks at 100 % CPU):<br>• **versioned cube + atomic published pointer**<br>• 3 DB roles (read / app / ETL)<br>• private endpoint |
| Memory | CIP alone: 2.6 GB of 4.5 (staging), 4.2 GB of 9.88 (production). All four products sharing: 3.6 / 6.1 GB. |
| Proof | A vertical slice on the real server → load + soak at 25–500 virtual users → client pilot at the Council gate (**Tue 1 Dec 2026**) |

## Documents

| File | Contents |
|---|---|
| [01-evidence-from-sip-and-mip.md](01-evidence-from-sip-and-mip.md) | Azure production numbers, logs, git history, security, verified claim by claim, with corrections |
| [02-benchmarks.md](02-benchmarks.md) | **§0: matched journey (load + click)**; first run; Streamlit 1.66; bundle sizes; raw output; how to re-run |
| [03-technology-comparison.md](03-technology-comparison.md) | 18 options scored: best, not optimal, worst, with reasons; Node / TS / JS / Python / Streamlit answered |
| [04-marketplace-buy-vs-build.md](04-marketplace-buy-vs-build.md) | 38 products (India-origin and international) with prices; cost at 300 and 1,000 viewers |
| [05-millisecond-ui.md](05-millisecond-ui.md) | Latency physics, budget and techniques |
| [06-system-design.md](06-system-design.md) | **The final one-server design**: architecture, packs, versioned publishing, jobs, security, memory, CPU, MySQL asks to IT, operations, rollout |
| [07-cost-model.md](07-cost-model.md) | Azure prices, capacity, 3-year TCO, developer time |
| [08-sources.md](08-sources.md) | Every source used |
| [09-chatgpt-vs-claude.md](09-chatgpt-vs-claude.md) | What each review got right, what was adopted, the merged answer |
| [10-database-serving-design.md](10-database-serving-design.md) | **What the ETL leaves behind**: screen-agnostic serving tables (`srv_wave`, `srv_result`), keys, the build procedure, why this design |
| [STRESS-TEST-RESULTS.md](STRESS-TEST-RESULTS.md) | **Stress test on Azure staging**: raw vs cube vs serving, database capacity, end-to-end, 5-minute soak, spike, users supported |
| [11-capacity-staging-production.md](11-capacity-staging-production.md) | **How many users**, staging and production: measured throughput, latency, memory, Azure arithmetic, limits |
| [13-ui-design.md](13-ui-design.md) | **UI design**: three directions compared on the same real data (Coresight portal, Chargebee-like console, research desk), the recommendation, design system, screens, component list, data contract, 5-week frontend plan. Images in [ui/images/](ui/images/). |
| [12-holiday-dashboard.md](12-holiday-dashboard.md) | The **sample** Holiday dashboard (backend-only, not part of the ETL): verified against the PDF; two data problems it exposes |

## How this was produced

- **REA skill**, applied to shipped artifacts:
  - the installed Streamlit and Dash bundles;
  - the MIP-FAST-React build;
  - the live CIP cube (read-only);
  - the Azure export, logs and git history.

  Normal tools were used for the source repositories, as REA directs.
- **Benchmarks** re-run on 20 Oct: page load and a matched journey.
- **Web research** for prices and framework facts, with URLs in [08](08-sources.md).
- **ChatGPT's review** read in full; its code findings were re-verified here ([09](09-chatgpt-vs-claude.md)).
- **REA Claude and LLM Council Claude** cover the pipeline fixes that must come first (gate 0).

**Model used: Claude.**
