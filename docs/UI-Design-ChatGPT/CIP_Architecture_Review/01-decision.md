# 01. Technology decision

[Package index](README.md) | [Source register](08-sources.md)

## 1. Decision in plain language

**Keep the data engineering; change the customer-facing delivery architecture.**

The recommended starting stack is:

| Layer | Choice | Why it belongs |
|---|---|---|
| Customer UI | React + TypeScript | Explicit browser-side interactions, reusable product components, typed contracts and a controlled application shell |
| Build | Vite; static production assets | Avoid a mandatory JavaScript rendering server for an authenticated dashboard |
| API | FastAPI + Python, modular monolith | Reuse the demonstrated Python domain/data investment; expose bounded, independently testable operations |
| Database | Existing MySQL | Preserve the schema and pre-aggregated research data; optimize measured query paths before replacing the database |
| Data ingestion and research transformations | Existing Python ETL, refactored incrementally | Avoid translating valuable survey semantics into a second language without evidence of benefit |
| Background work | One initially bounded Python worker, durable job records, object storage for exports | Keep long-running work away from interactive requests; support retries and recovery |
| Browser data state | TanStack Query, explicitly configured | Deduplicate requests and control freshness rather than refetch every panel unnecessarily |
| Charts and tables | Apache ECharts plus a deliberately selected table component | Render bounded result sets; decide paid grid features separately rather than accidentally buying them |
| Authentication | Existing organizational identity provider through a complete OIDC integration | Reuse identities; keep application authorization separate |
| Operations | Existing Azure hosting, structured telemetry, backups and tested deployment/rollback | Start with the fewest necessary moving parts |

These are design recommendations, not measured runtime winners. Vite documents static deployment; TypeScript adds compile-time checking rather than a faster JavaScript runtime; FastAPI documents both asynchronous I/O and the memory consequences of worker replication. [S06](08-sources.md#s06), [S07](08-sources.md#s07), [S08](08-sources.md#s08), [S09](08-sources.md#s09).

**Do not introduce Next.js server rendering, Kubernetes, Kafka, a separate search cluster, a second analytics database or a distributed cache merely to make the diagram look enterprise-ready.** Add an operational component only when a requirement or measurement justifies its cost.

## 2. What the upload changes about the decision

The archive is not merely an ETL script. It contains an eight-page Streamlit application, a normalized survey model, cohorts, harmonization, precomputed aggregate cells, publication tracking, saved views and ETL verification paths. There are 77 Python files and 33 table definitions in the principal schema. No production React frontend or substantial API service is present. The included small FastAPI project is a synthetic benchmark, not the CIP API. See evidence E01-E05 in [the audit](02-code-audit.md).

That makes a wholesale rewrite of the backend particularly difficult to justify. The valuable work is the interpretation of questions, denominators, respondents, cohorts, concepts and publication snapshots. A browser UI does not require throwing those rules away.

It also means the claim that this application simply reads every MySQL row into Streamlit is inaccurate. The main analysis path already attempts to use precomputed aggregate cells. Certain report and ETL paths remain much less bounded, but those are specific findings, not a description of the entire codebase.

## 3. The business team's proposal: right for a dashboard, incomplete for a product

"Put the data in MySQL and display it in Streamlit" can be a sensible way to validate an internal analysis. It is not a complete specification for a paid, multi-product research platform.

A subscriber product must decide which person may access which product, dataset, publication and export; retain research definitions; publish a consistent data version; respond predictably when several users act together; recover when a process fails; and deliver understandable loading, empty and error states. These responsibilities exist in every stack. React does not supply authorization automatically, and Streamlit does not make authorization impossible. OWASP recommends default-deny authorization and permission checks on each request. [S27](08-sources.md#s27).

The architectural improvement is therefore **separating browser interaction, authorized data delivery and background computation**. The chosen frameworks support that separation; the framework name is not the outcome.

A useful message to the business team is:

> MySQL and the current Python work remain the foundation. Streamlit helped us establish the analysis, and we should retain that investment. For CIP, the extra work is a product layer: secure subscription access, small and fast data requests, reusable interactions, reliable exports and consistent published results. We should prove the benefit on one real user journey before migrating more screens.

## 4. Why FastAPI instead of Node.js as the default

The reason is **reuse and delivery risk**, not a claim that Python is the fastest API language.

The repository demonstrates thousands of lines of Python implementation. It does not demonstrate an equally mature TypeScript API or reveal the team's actual frontend expertise. Keeping Python behind a stable HTTP contract permits incremental extraction of pure business functions, SQL repositories and research tests. The browser can still be fully TypeScript.

For the intended common request, the API should validate access, perform a cache lookup or small indexed query, and serialize a compact result. Avoid spending the request doing a full-wave transformation. With that design, the database, network and payload can dominate the response; selecting a different API runtime may have a smaller effect than changing the data path. This is an inference to validate with production traces, not an assumed performance ratio.

FastAPI is not permission to put synchronous PyMySQL calls into an `async def` endpoint and call the service non-blocking. Initially, either use ordinary synchronous endpoints with bounded thread and connection pools, or intentionally migrate the serving repository to a compatible asynchronous driver. Keep CPU-heavy transformations out of both variants. [S08](08-sources.md#s08), [S25](08-sources.md#s25).

**Choose Node.js + TypeScript + Fastify instead when** the delivery team already has stronger production TypeScript capability, the API can remain primarily SQL/orchestration, and maintaining a Python ETL plus TypeScript API is less costly than training for FastAPI. Node's own documentation warns against blocking its event loop with long-running work. The same job separation is still required. [S10](08-sources.md#s10), [S11](08-sources.md#s11).

## 5. Why not make Streamlit the subscriber shell

Streamlit's normal interaction model executes Python on the server, while its caching, forms and fragments can reduce repeated work. Its documentation explicitly describes copying cached data results and sharing cached resources with the associated safety constraints. These are tradeoffs, not proof of an inherently unusable platform. [S02](08-sources.md#s02), [S03](08-sources.md#s03), [S04](08-sources.md#s04).

For CIP, a dedicated browser application is the preferred direction because the desired product includes persistent navigation, independent panel updates, rich filtering, paid-access workflows and multiple related applications. Explicit client state and a reusable API make those boundaries easier to design and test. That is an engineering judgment about this product, not a universal framework ranking.

An optimized Streamlit implementation remains viable when the audience is controlled, the workflows fit its interaction model, and it passes the same responsiveness and reliability requirements. Streamlit also supports OIDC login; it is incorrect to say that the framework cannot support authentication. Application permissions remain a separate task. [S05](08-sources.md#s05).

**The poorest fit is not the word Streamlit; it is a design that loads large raw datasets into the web process, repeats work on interactions, runs exports/ETL inline, and has no enforceable user or query boundaries.** Reimplementing that pattern in Node.js would not make it a good architecture.

## 6. What would change this recommendation

| New evidence | Decision consequence |
|---|---|
| Strong existing TypeScript backend team and limited Python web expertise | Prefer Fastify while keeping Python ETL |
| Existing Django platform with proven identity, admin and operations | Prefer Django over creating those platform capabilities again |
| Small internal-only audience; optimized Streamlit meets all agreed targets | Keep Streamlit and avoid unnecessary frontend spending |
| Product is mainly embedded fixed dashboards, with limited custom workflows | Price Zoho Analytics, Metabase and Power BI Embedded against custom development |
| Profiling shows API CPU/serialization, not SQL or network, dominates cost | Benchmark Go or ASP.NET Core for that service, not an automatic whole-product rewrite |
| Public SEO pages are central to acquisition | Add an appropriate public-site rendering strategy; do not force every private dashboard through SSR |
| Single host cannot meet peak memory/availability requirements | Change deployment constraints; a language change cannot manufacture isolation or redundancy |

## 7. Confidence and approval boundaries

**High confidence:** the supplied code has useful Python/MySQL assets; the architecture needs stronger authorization, bounded data paths and deployment evidence; RAM alone cannot establish user capacity.

**Moderate confidence:** React/TypeScript with FastAPI is the lowest-risk custom-product default given the demonstrated code investment and requested UX. Frontend delivery capability remains an important unknown.

**Not established:** that FastAPI is faster than Fastify for CIP; a maximum number of supported users; actual Azure p95 latency; future cost savings; complete test-suite health; the true production behavior of SIP or MIP.

Approve a vertical slice and an evidence gate, not an unqualified full rewrite. The initial slice should use real authentication and permissions, the same bounded MySQL data, a complete chart/table/filter experience, and the actual Azure allocation. Compare it with an optimized Streamlit version before expanding scope.

## 8. REA methodology note

The installed catalog did not contain REA. The authentic public REA skill was consulted; it directs ordinary full-source architecture analysis to normal repository tools rather than binary reverse-engineering tooling. This review follows that distinction, with source evidence, bounded execution, an evidence ledger and explicit unknowns. It does not claim to have run the REA MCP server or observed a live application through REA. [S01](08-sources.md#s01).
