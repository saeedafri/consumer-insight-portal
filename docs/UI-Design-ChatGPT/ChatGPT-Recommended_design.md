## My recommendation

**Build CIP with React + TypeScript + Vite for the frontend, Python + FastAPI for the API, and your existing MySQL database and Python ETL underneath.** Run ingestion, heavy analysis and exports in a separately controlled background worker.

**Keep Streamlit for internal research and operational tools—not as the default foundation for CIP’s long-term subscriber-facing interface.**

This is the best-fit recommendation for the code and requirements you supplied. It is **not** a claim that FastAPI is universally faster than Node.js, or that React is universally faster than Vue or Svelte.

### Your documentation

**:chatgpt-content-reference{index="10"}[Download the complete Markdown report](sandbox:/mnt/data/CIP_Full_Report.md)**

**CIP_Architecture_Review\.zip[Download the full documentation and evidence package](sandbox:/mnt/data/CIP_Architecture_Review.zip)**

The package contains eight chapters covering the decision, code audit, technology and marketplace comparisons, system design, performance testing, costs and migration, UI specifications, and **51 primary-source references**. It also includes the local measurement results and the scripts used for the bounded checks.

---

## 1. What I found in your ZIP

### It is not just an ETL codebase

The archive contains an existing **eight-page Streamlit application**, alongside the ETL. I found **77 Python files** and **33 table definitions** in the principal schema.

The implementation includes survey ingestion, question harmonization, cohorts, precomputed aggregate cells, analysis, trends, publications, saved views and operational tooling. However, the ZIP does **not** contain two separate SIP and MIP production implementation repositories. Some existing reports refer to those applications, but their referenced code is outside this archive.

The source locations and evidence are recorded in the 02-code-audit.md[code audit](sandbox:/mnt/data/cip_review/deliverables/02-code-audit.md).

### There is valuable work you should preserve

Your main analysis path already attempts to use **precomputed SQL aggregates**. That is a useful foundation.

It would be inaccurate to characterize the entire application as “load all MySQL data into Streamlit and display it.” Some paths are much less bounded, but the existing aggregate-first design should be retained—not rewritten merely to change languages.

### Several important problems are independent of the framework

| Finding in the supplied code                                                                 | Why it matters                                                                                   |
| -------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| Whole-wave numeric responses and verbatims are fetched without pagination in one report path | The application can process much more data than the user needs to see                            |
| There are 23 Streamlit data-cache decorators, with TTLs but no entry limits                  | Large results and many filter combinations can increase memory pressure                          |
| Aggregate refresh deletes existing cells before rebuilding them                              | A failed or overlapping refresh can change the serving path and its performance                  |
| Cohort-change detection uses member count and the sum of respondent IDs                      | Different memberships can produce the same signature and avoid a necessary refresh               |
| Login contains an explicit one-second sleep                                                  | That delay exists regardless of how fast Python or the database is                               |
| Subscription permissions and administrative authorization need further implementation        | A successful login does not establish permission to access every product or modify research data |

**Security note:** the archive contains populated credential settings. Rotate the affected credentials and review where the archive has been distributed. I excluded their values and the original source archive from the deliverables.

I also reproduced a narrowly scoped session-validation issue: an **existing in-memory session** can remain valid when its database lookup fails or returns no row. This does **not** demonstrate an arbitrary unauthenticated login bypass; the separate cookie-recovery path behaves differently. The distinction is documented in the audit.

---

## 2. What the performance evidence actually proves

I ran a local synthetic experiment using **one million rows**, comparing two ways to produce the same summary.

| Measured operation              | Load all rows, then filter/group in Python | Filter/group in SQL, then return the summary |
| ------------------------------- | -----------------------------------------: | -------------------------------------------: |
| Rows returned from the database |                                  1,000,000 |                                           50 |
| Median measured duration        |                            **2,326.89 ms** |                                 **92.46 ms** |
| Dataframe size                  |                      **209,099,220 bytes** |                              **3,932 bytes** |
| Final summary rows              |                                         50 |                                           50 |

The summaries matched.

**This is not a Streamlit-versus-FastAPI benchmark. Both alternatives were Python.** It demonstrates the value of reducing data before transferring and processing it in the application.

It was a five-repeat local SQLite experiment—not Azure, MySQL, a browser test or a concurrency test. Its approximately **25× difference must not be presented as a framework speedup or production forecast**. The raw results and limitations are included in the package.

The important architectural conclusion is:

> **Small authorized queries, precomputed results and bounded responses can matter far more than changing the API language.**

Your existing aggregate-first analysis path already follows part of this approach.

### The benchmark reports inside the ZIP need qualification

The supplied API benchmark renders a heading and a plain table. The Streamlit comparison includes a selector, metric, chart and dataframe. The browser timing script waits for a text marker—not completion of the entire interactive experience.

That is **not a matched workload**, so I would not use those reports to tell management that a particular framework is definitively several times faster for CIP. The audit explains the additional timing, session-count and environment limitations.

---

## 3. Which technologies are better—and which are not optimal?

These are **fit judgments for CIP**, not fabricated benchmark rankings.

| Option                                    | My assessment for CIP                                    | Reason                                                                                                                                       |
| ----------------------------------------- | -------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| **React + TypeScript + FastAPI**          | **Recommended default**                                  | Separates the browser experience from data delivery while retaining your Python research logic                                               |
| **React + TypeScript + Node.js/Fastify**  | **Strongest alternative**                                | Prefer it when your team is substantially stronger in production TypeScript backend development                                              |
| **Vue or Svelte + a well-designed API**   | **Fully credible alternatives**                          | There is no evidence here that React would necessarily render your application faster                                                        |
| **Optimized Streamlit**                   | **Good for internal research and a comparison baseline** | Builds directly on existing code; use for customers only when its UX and measured capacity meet the requirements                             |
| **Plotly Dash**                           | **Conditional analytics-focused option**                 | Worth considering for Python-centric analytical applications, but it does not remove the need for product permissions and operational design |
| **Django**                                | **Strong when already established internally**           | Particularly sensible when existing account, administration and application infrastructure can be reused                                     |
| **Go or ASP.NET Core**                    | **Conditional, not an initial rewrite**                  | Consider with existing expertise or evidence that API CPU/memory—not SQL or network—is the limiting factor                                   |
| **Next.js**                               | **Use when its rendering features are needed**           | Do not introduce dynamic server rendering merely because it is popular; static export is also possible                                       |
| **Full Rust/Java/other-language rewrite** | **Not justified by the supplied evidence**               | Adds translation and maintenance risk without an established CIP bottleneck it would solve                                                   |

The report provides the supporting framework documentation and fuller tradeoffs, including Flask, Spring Boot and Laravel.

### Why FastAPI rather than Node.js as the default?

**Because your demonstrated investment is Python—not because Python wins a universal speed contest.**

Your data interpretation, cohort handling, transformations and research logic already exist in Python. A FastAPI boundary lets you reuse that work while delivering a completely different browser experience.

Node.js/Fastify is a legitimate alternative. However, it would still need to integrate with the Python ETL, and any duplicated research rules would require additional maintenance.

Neither runtime makes heavy request-time computation harmless. Node’s documentation warns against blocking the event loop; FastAPI likewise requires an intentional distinction between synchronous work, asynchronous I/O and replicated worker processes. [Node.js](https://nodejs.org/learn/asynchronous-work/dont-block-the-event-loop)

### Why not Streamlit as the default customer shell?

Streamlit’s execution model, caching and session behavior are tradeoffs for the richer subscriber experience you describe. But **it is incorrect to say Streamlit cannot be optimized, cannot authenticate users or cannot partially rerun an application**. Its documentation covers caching, fragments and OIDC authentication. [Streamlit Docs](https://docs.streamlit.io/develop/concepts/architecture/caching)

My concern is the long-term fit for independently updating panels, persistent navigation, subscription-aware discovery, saved workflows, reusable interfaces across products and a stable API.

**The worst choice is the architecture pattern—not simply a language:** large raw datasets in the web process, repeated server-side work, inline exports/ETL, unbounded caches and incomplete permissions. Rebuilding that pattern in Node.js would not fix it.

---

## 4. The system design I recommend

```text
Customer browser
React + TypeScript
Navigation, filters, charts, tables, saved-view state
                    |
             HTTPS / compact JSON
                    |
             FastAPI modular API
 Authentication | Product permissions | Query validation
 Analysis | Publications | Saved views | Export jobs
                    |
       Bounded, version-aware response cache
                    |
                   MySQL
 Published research data | Precomputed aggregates
 Application state | Job records | Publication versions
                    ^
                    |
          Controlled Python worker
 ETL | Verification | Cohorts | Aggregates | Exports
                    |
       Source APIs and private object storage
```

### The important boundaries

**The browser owns ordinary interface interactions.** Opening a filter panel or changing the presentation of a small, already-loaded result should not require recomputing the analysis on the server.

**The API owns access and bounded data delivery.** It checks identity, subscription, dataset scope and permitted query parameters before returning a result. Hiding a UI element is not an authorization control. [OWASP Cheat Sheet Series](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html)

**The database handles appropriate filtering and aggregation.** Keep the existing aggregate tables and inspect real query plans before replacing MySQL.

**The worker owns expensive work.** An export request creates a durable job; it does not keep the interactive request busy until the file is finished.

**Publication becomes versioned.** Build and validate the next dataset version, then switch the published pointer. Keep the previous valid version available if processing fails.

Start with **one modular API and a bounded worker**, not a collection of microservices. The full design covers sessions, entitlements, cache keys, API contracts, job retries, deployment, backups, failure behavior and scaling.

Using Vite for a static frontend also means you do not need a separate production Node.js rendering service solely to serve the UI. The build artifacts can be served through the selected production hosting arrangement. [vitejs](https://vite.dev/guide/static-deploy.html)

---

## 5. What “milliseconds” should mean

Use separate targets for immediate feedback and completion of the actual result.

| Metric                                    |             Proposed initial target—not a measured result |
| ----------------------------------------- | --------------------------------------------------------: |
| Local control acknowledgement             |                                              p95 ≤ 100 ms |
| Browser INP                               |                                              p75 ≤ 200 ms |
| Compact cached API response, server-side  |                                              p95 ≤ 100 ms |
| Common indexed aggregate API, server-side |                                              p95 ≤ 300 ms |
| Ordinary click to correct new results     |      p95 ≤ 800 ms under defined network/device conditions |
| Export submission acknowledgement         | p95 ≤ 300 ms server-side; file generation runs separately |

The **200 ms INP threshold** is documented web-performance guidance. The other values above are proposed CIP acceptance targets. INP measures responsiveness to the next paint; it does not prove that a later network result has completed. [web.dev](https://web.dev/articles/inp)

A promise that every operation will finish in 1–10 milliseconds for users internationally would be misleading. Network transit, database work, queueing and browser rendering remain part of the experience.

### Your RAM figures do not establish a user limit

I cannot honestly derive “500 concurrent users” or “5,000 subscribers” from **4.5 GB staging and 9.88 GB production**.

Most importantly, determine whether CIP, CIQ, MIP and MDB share the same physical host or App Service plan. Apps and deployment slots on an App Service plan can share its resources; they do not automatically receive a dedicated copy of the plan’s memory. [Microsoft Learn](https://learn.microsoft.com/en-us/azure/app-service/overview-hosting-plans)

The report includes a shared-host planning allocation, but labels it as **unvalidated budgeting**, not measured consumption. Database placement, CPU, sibling-application usage and ETL peaks still need qualification.

**A single host also remains a single point of failure, regardless of language.**

---

## 6. Marketplace options and long-run cost

For a predominantly dashboard-based product, buying more of the presentation layer may be cheaper than building it.

**Zoho Analytics Embedded** is the first India-origin dashboard buy-option I would evaluate. Its documented embedding capabilities make it relevant, but the applicable commercial quote must cover your external-user and branding requirements. **Metabase** is another strong dashboard shortlist candidate; free guest embedding and fuller paid embedding capabilities have different conditions. **Power BI Embedded** is sensible where Microsoft BI models and skills already exist, but production embedding requires suitable capacity. [Zoho](https://www.zoho.com/analytics/embedded-solutions.html)

I would be more cautious about treating self-hosted low-code platforms as lightweight additions to your server. Appsmith’s current guidance starts at **2 vCPU and 8 GB**, while ToolJet lists application requirements separately from PostgreSQL and Redis requirements. Those are not evidence that the complete platforms fit comfortably inside a shared 4.5 GB staging allowance. [Appsmith](https://docs.appsmith.com/getting-started/setup/infrastructure-sizing)

For the **full custom research product** you describe, I still prefer the custom frontend/API architecture.

The long-run cost argument is primarily about **preserving Python research logic, reducing repeated processing, sharing tested components across products, and reducing rework and incidents**.

It is not “React makes Azure cheaper.” A fixed Azure host costs the same until you actually change the purchased resources or avoid an otherwise necessary upgrade. The report includes a three-year cost model and a clearly labelled break-even example rather than invented Azure prices or guaranteed savings.

---

## 7. What should happen before committing to a full migration?

**Build one complete, representative CIP journey—not the whole replacement first.**

Use real authentication and permissions, the same MySQL data, the same chart/table/filter functionality, and the actual Azure allocation. Compare an optimized Streamlit version with the proposed web/API version. Measure correctness, click-to-result timing, memory, CPU, database waits and behavior while background work runs.

Then expand the architecture that meets the agreed requirements with the lowest maintainable cost.

That gives your business team a defensible answer:

> **We are not replacing MySQL or discarding the Python work. We are adding a product layer that delivers the data securely, efficiently and consistently. We will prove its value on a real workflow before migrating more of the application.**

### Review limits

I extracted the archive, traced the principal code paths and ran the bounded checks described above. **I did not load-test your Azure environment or successfully run the complete application test suite.** Test collection stopped with ten missing-dependency import errors; the evidence is included.

REA was not installed in this environment. I consulted its published guidance, which directs ordinary full-source architecture analysis to repository inspection rather than binary reverse-engineering tooling. The report documents that method and distinguishes source observations, local measurements and design proposals. [GitHub](https://raw.githubusercontent.com/illumi-ai/REA/main/skills/reverse-engineer-anything/SKILL.md)

**The decision is therefore clear, but appropriately bounded: React/TypeScript + FastAPI is the recommended starting architecture for CIP; the fastest production implementation and safe user capacity must be established through a matched test—not a framework claim.**
