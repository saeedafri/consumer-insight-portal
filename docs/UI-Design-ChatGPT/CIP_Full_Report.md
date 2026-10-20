# CIP: Architecture, technology decision and source review

**Prepared October 20, 2026**  
**Recommended:** React + TypeScript + Vite; FastAPI + Python; existing MySQL and Python ETL; bounded background jobs.  
**Evidence status:** source-reviewed with limited local probes; not production-load-qualified.

This standalone report combines eight chapters. Raw measurements, reproduction scripts and test-collection evidence are in the companion ZIP. Relative evidence-file links require that package.

## Contents

1. [01. Technology decision](#chapter-1)
2. [02. Source audit and evidence ledger](#chapter-2)
3. [03. Technology and marketplace comparison](#chapter-3)
4. [04. Proposed system design](#chapter-4)
5. [05. Performance evidence and qualification plan](#chapter-5)
6. [06. Infrastructure, cost and migration](#chapter-6)
7. [07. UI specification and interaction design](#chapter-7)
8. [08. Primary source register](#chapter-8)


---

<a id="chapter-1"></a>

# 01. Technology decision

[Contents](#contents) | [Source register](#chapter-8)

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

These are design recommendations, not measured runtime winners. Vite documents static deployment; TypeScript adds compile-time checking rather than a faster JavaScript runtime; FastAPI documents both asynchronous I/O and the memory consequences of worker replication. [S06](#s06), [S07](#s07), [S08](#s08), [S09](#s09).

**Do not introduce Next.js server rendering, Kubernetes, Kafka, a separate search cluster, a second analytics database or a distributed cache merely to make the diagram look enterprise-ready.** Add an operational component only when a requirement or measurement justifies its cost.

## 2. What the upload changes about the decision

The archive is not merely an ETL script. It contains an eight-page Streamlit application, a normalized survey model, cohorts, harmonization, precomputed aggregate cells, publication tracking, saved views and ETL verification paths. There are 77 Python files and 33 table definitions in the principal schema. No production React frontend or substantial API service is present. The included small FastAPI project is a synthetic benchmark, not the CIP API. See evidence E01-E05 in [the audit](#chapter-2).

That makes a wholesale rewrite of the backend particularly difficult to justify. The valuable work is the interpretation of questions, denominators, respondents, cohorts, concepts and publication snapshots. A browser UI does not require throwing those rules away.

It also means the claim that this application simply reads every MySQL row into Streamlit is inaccurate. The main analysis path already attempts to use precomputed aggregate cells. Certain report and ETL paths remain much less bounded, but those are specific findings, not a description of the entire codebase.

## 3. The business team's proposal: right for a dashboard, incomplete for a product

"Put the data in MySQL and display it in Streamlit" can be a sensible way to validate an internal analysis. It is not a complete specification for a paid, multi-product research platform.

A subscriber product must decide which person may access which product, dataset, publication and export; retain research definitions; publish a consistent data version; respond predictably when several users act together; recover when a process fails; and deliver understandable loading, empty and error states. These responsibilities exist in every stack. React does not supply authorization automatically, and Streamlit does not make authorization impossible. OWASP recommends default-deny authorization and permission checks on each request. [S27](#s27).

The architectural improvement is therefore **separating browser interaction, authorized data delivery and background computation**. The chosen frameworks support that separation; the framework name is not the outcome.

A useful message to the business team is:

> MySQL and the current Python work remain the foundation. Streamlit helped us establish the analysis, and we should retain that investment. For CIP, the extra work is a product layer: secure subscription access, small and fast data requests, reusable interactions, reliable exports and consistent published results. We should prove the benefit on one real user journey before migrating more screens.

## 4. Why FastAPI instead of Node.js as the default

The reason is **reuse and delivery risk**, not a claim that Python is the fastest API language.

The repository demonstrates thousands of lines of Python implementation. It does not demonstrate an equally mature TypeScript API or reveal the team's actual frontend expertise. Keeping Python behind a stable HTTP contract permits incremental extraction of pure business functions, SQL repositories and research tests. The browser can still be fully TypeScript.

For the intended common request, the API should validate access, perform a cache lookup or small indexed query, and serialize a compact result. Avoid spending the request doing a full-wave transformation. With that design, the database, network and payload can dominate the response; selecting a different API runtime may have a smaller effect than changing the data path. This is an inference to validate with production traces, not an assumed performance ratio.

FastAPI is not permission to put synchronous PyMySQL calls into an `async def` endpoint and call the service non-blocking. Initially, either use ordinary synchronous endpoints with bounded thread and connection pools, or intentionally migrate the serving repository to a compatible asynchronous driver. Keep CPU-heavy transformations out of both variants. [S08](#s08), [S25](#s25).

**Choose Node.js + TypeScript + Fastify instead when** the delivery team already has stronger production TypeScript capability, the API can remain primarily SQL/orchestration, and maintaining a Python ETL plus TypeScript API is less costly than training for FastAPI. Node's own documentation warns against blocking its event loop with long-running work. The same job separation is still required. [S10](#s10), [S11](#s11).

## 5. Why not make Streamlit the subscriber shell

Streamlit's normal interaction model executes Python on the server, while its caching, forms and fragments can reduce repeated work. Its documentation explicitly describes copying cached data results and sharing cached resources with the associated safety constraints. These are tradeoffs, not proof of an inherently unusable platform. [S02](#s02), [S03](#s03), [S04](#s04).

For CIP, a dedicated browser application is the preferred direction because the desired product includes persistent navigation, independent panel updates, rich filtering, paid-access workflows and multiple related applications. Explicit client state and a reusable API make those boundaries easier to design and test. That is an engineering judgment about this product, not a universal framework ranking.

An optimized Streamlit implementation remains viable when the audience is controlled, the workflows fit its interaction model, and it passes the same responsiveness and reliability requirements. Streamlit also supports OIDC login; it is incorrect to say that the framework cannot support authentication. Application permissions remain a separate task. [S05](#s05).

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

The installed catalog did not contain REA. The authentic public REA skill was consulted; it directs ordinary full-source architecture analysis to normal repository tools rather than binary reverse-engineering tooling. This review follows that distinction, with source evidence, bounded execution, an evidence ledger and explicit unknowns. It does not claim to have run the REA MCP server or observed a live application through REA. [S01](#s01).

---

<a id="chapter-2"></a>

# 02. Source audit and evidence ledger

[Contents](#contents) | [Source register](#chapter-8)

## 1. Scope and archive identity

This is a targeted architecture, security-boundary, data-flow and performance review of the supplied source. It is not a complete penetration test, a formal proof of correctness or a production certification.

Archive SHA-256:

```text
b4a36b579f2f619000548778a52b3fb20b2b1c6be284c02ab2d9403978f20d0b
```

The ZIP contained 855 file entries. Excluding macOS metadata left 393 retained files. The principal source groups are:

| Group | Python files | Source lines |
|---|---:|---:|
| `app/` | 29 | 4,949 |
| `etl/` | 15 | 3,638 |
| `tests/` | 18 | 3,165 |
| `scripts/` | 15 | 1,022 |
| **Total** | **77** | **12,774** |

All 77 Python files parsed successfully with Python's AST parser. That verifies syntax under the inspection interpreter; it does not establish dependency compatibility or runtime correctness. The main schema contains 33 `CREATE TABLE` definitions. The source pins Streamlit to 1.55.0. Other requirements are mostly lower bounds rather than a fully reproducible environment lock.

**Scope correction:** this is a CIP codebase with an existing Streamlit UI and supporting documents. Separate SIP and MIP production implementation repositories are not present. Historical reports reference files and incidents outside this archive; those claims were not treated as independently verified.

## 2. Reconstructed application

```text
Forsta/Decipher API --------+
Legacy survey warehouse ---+--> Python ingestion and source adapters
File export fallback ------+        |
                                    v
                           Source definitions + responses
                                    |
                         Verification / respondent profiles
                                    |
                      Concepts, harmonization and cohorts
                                    |
                     Precomputed aggregate cells in MySQL
                                    |
               +--------------------+----------------------+
               |                    |                      |
         Streamlit pages      Publications/drift     Exports/notifications
               |
     Overview / survey report / analysis builder / trends
     Mappings / publications / data health / sign in
```

The source adapter is named **Forsta/Decipher**, not Forrester. Configuration files describe cohorts, survey mappings, calendars, tracker lines and crosstab banners. The existing implementation already separates several data responsibilities into modules, although repository functions still depend on Streamlit caching.

## 3. Evidence ledger

Locations are relative to the extracted archive root. Line references identify the reviewed version, not a future repository revision.

| ID | Evidence and location | Finding and implication | Type / confidence |
|---|---|---|---|
| E01 | `app/main.py:28-45`; `sql/001_schema.sql`; inventory JSON | Eight registered Streamlit pages and 33 table definitions; not ETL alone | Observed / high |
| E02 | `etl/forsta_etl.py:203-276`; related source adapters | Ingestion includes loading state, definitions, response writing, validation, profiles, harmonization and aggregate refresh | Observed / high |
| E03 | `app/data/repository.py:418-567` | Standard analysis is aggregate-first, with a raw-query fallback; preserve this investment | Observed / high |
| E04 | `app/data/repository.py:123-148` | Wave report fetches numeric responses and verbatims for the wave without pagination; not bounded to the displayed viewport | Observed / high |
| E05 | `app/data/repository.py:8`; cache inventory | 23 `st.cache_data` decorators, with TTLs but no `max_entries`; repository layer is coupled to Streamlit | Observed / high |
| E06 | `.env`; `app/core/config.py:117-155` | Populated credentials are distributed in the archive; empty app-specific credentials allow the app role to fall back to staging writer credentials | Observed / high |
| E07 | `app/core/auth.py:173-193`, `230-283` | Existing in-memory sessions can remain valid after session-store failure or a missing session row; cookie recovery has a separate fail-closed path | Observed + bounded probe / high |
| E08 | `app/pages/0_Login.py:32-43`; `app/core/auth.py:302-351` | SSO authorization link and a function accepting preverified claims exist, but a complete token-exchange/callback flow was not found in the supplied app | Bounded source search / high for supplied tree |
| E09 | `app/pages/7_Mappings.py:25-48`; `app/pages/8_Publications.py:27-37`; app-wide authorization search | Authentication gates exist, but product entitlements and role-specific guards for sensitive administration are not implemented in the reviewed paths | Observed / high |
| E10 | `app/data/cube.py:171-181`; `etl/forsta_etl.py:203-276` | Aggregate refresh deletes old cells before rebuilding; publication is not one immutable-version pointer switch | Observed / high |
| E11 | `app/data/cube.py:145-168` | Cohort-change detection uses member count and ID sum; distinct member sets can collide | Observed + mathematical probe / high |
| E12 | `scripts/ui_benchmark/api_page.py:20-25`; `streamlit_sql.py:13-18`; `page_load.py:29-53` | Supplied API and Streamlit UI workloads differ; marker timing is not full interaction-ready timing | Observed / high |
| E13 | `evidence/test-collection-output.txt` | Full pytest collection failed with 10 import errors; the suite was not successfully run | Executed / high |
| E14 | `evidence/data-path-results.json` | Local synthetic SQL reduction was materially cheaper than full-dataframe loading for the same summary | Measured locally / high; transfer to production unknown |
| E15 | `app/core/config.py:47-50,101-110`; `app/core/database.py:63-125`; `requirements.txt` | Large default pool potential per process, synchronous SQL, unknown environment fallback and incomplete dependency locking require deployment discipline | Observed / high |
| E16 | `app/pages/0_Login.py:49-57`; `app/components/header.py:101-140`; non-login page entrypoints | Explicit one-second login sleep, raw anchor navigation and health checks before authentication add work unrelated to language speed | Observed / high |
| E17 | `app/data/repository.py:698-743` | Saved-view ownership predicates exist, but globally shared views are not scoped to a customer tenant | Observed / high |

## 4. Security findings: fix before subscriber launch

### 4.1 Credential distribution and privilege separation

The archive contains populated database, survey-API, authentication, email and webhook credential settings. The values are intentionally not reproduced. Rotation is warranted because source-review archives are easily copied; the review does not establish that any value remains valid or that an account was compromised.

More importantly, configuring a connection as the "app" role does not make it read-only. The configuration falls back to staging credentials when dedicated app credentials are absent, which is the state of the supplied settings. Introduce separate database identities for research reads, narrowly scoped application-state writes and ETL administration. The public API process must not load the ETL writer credential merely to record login sessions.

Unknown `APP_ENV` values currently fall back to `LOCAL`. Replace this with explicit validation and startup failure. Ensure debug/development bypasses cannot activate in a deployed environment through an unexpected value. Explicitly require verified database TLS in deployed environments; inspect actual driver settings and negotiated behavior rather than assume an empty SSL dictionary proves either secure or insecure transport. [S26](#s26).

### 4.2 Existing-session validation can fail open

The exact `_session_is_live` function returned `True` in the bounded offline probe when the fake session store raised an exception and when it returned no session row. It returned `False` for revoked and expired rows. This behavior matches the inspected source.

The scope matters: `_load_session`, used when recovering identity from a cookie, returns no user on database failure or a missing row. Therefore the evidence supports **continued validity of an already-held in-memory session**, not a demonstrated unauthenticated login bypass. Existing-session revocation and availability policy should be explicit rather than accidentally delegated to exception handling.

For production, use a tested server-side session implementation with server-set Secure, HttpOnly cookies, appropriate SameSite behavior, CSRF protection for state changes and bounded session lifetimes. The current client-side CookieController path does not provide a server-set HttpOnly cookie boundary. [S28](#s28).

### 4.3 Authentication is not finished authorization

The local shared-passphrase/email-allowlist path does not independently prove ownership of the entered email. The OIDC helper says it expects claims verified elsewhere; an authorization URL alone is not a completed OIDC integration.

Even a completed login does not establish a paid subscription, ownership of an export or permission to change concept mappings. Add server-side policies for product access, dataset scope, saved views, publications, exports and administrative writes. Avoid relying on hidden navigation items. The framework's own OIDC support does not supply all these business permissions. [S05](#s05), [S27](#s27).

Saved-view delete operations already include an owner predicate, which is worth retaining. However, `is_shared = 1` currently means shared beyond the owner without a tenant predicate. Do not carry that interpretation unchanged into a multi-customer application.

## 5. Correctness and publication integrity

### 5.1 Preserve current verification; strengthen the publication boundary

The ETL marks loading/verified status and performs substantial verification. Listing only verified surveys is a useful safeguard. This does not prove that every direct-ID read, cached result and background computation observes a single consistent published version.

`refresh_wave` commits deletion of aggregate cells before attempting a rebuild. The code deliberately falls back to raw responses after certain failures. That can change query cost and availability under load. It should not be described as proof of an observed production outage; no live refresh was performed.

The target design should build the next data version separately, validate it, and atomically change a current-version pointer. In-flight requests retain the version they resolved. Keep the last known good version available when ingestion or cube generation fails. This protects both performance and scientific reproducibility.

### 5.2 Cohort signatures can miss real membership changes

The current signature combines count and sum of respondent IDs. These two cohorts have the same signature:

```text
Before: {1, 4} -> count 2, sum 5
After:  {2, 3} -> count 2, sum 5
```

The membership is different. Prefer explicit cohort-definition/data versioning or deterministic membership comparison/digests with an intentional collision policy. A cheap aggregate signature is not sufficient to guarantee that a derived cube remains current. The counterexample proves the weakness of the test, not that the production data actually encountered it.

## 6. Performance and memory findings

The positive finding is that standard `analyse` requests already have an aggregate-first path. Preserve it and measure indexes with MySQL `EXPLAIN`, and where appropriate `EXPLAIN ANALYZE` on safe representative reads. `EXPLAIN ANALYZE` executes the query; it is not a harmless metadata-only action on a live overloaded system. [S23](#s23).

The principal concerns are boundedness and repeated work:

| Path | Concern | Refactoring direction |
|---|---|---|
| Whole-wave numeric/verbatim report | Potentially large transfer and sensitive response material | Separate aggregate summaries from paginated authorized details |
| 23 TTL caches without entry bounds | Filter combinations and large return objects can grow the working set | Cache small versioned responses; set entry and byte budgets |
| ETL `list(...)` and full answer-row construction | Full-wave data held before bulk loading | Stream or chunk where verification permits; retain idempotent staging |
| Mappings and publication drift work in UI paths | Heavy maintenance can compete with browsing | Admin job submission, bounded worker and progress status |
| One-second login sleep | Guaranteed additional delay after local login | Remove decorative sleep; show immediate completion |
| Raw header anchors | Full browser navigation and new session recovery | Product router or appropriate native navigation API |
| Health check before auth on page execution | Extra database work and unnecessary unauthenticated dependency | Dedicated health endpoint, distinct readiness checks and cached operational status |
| Multi-question report loops | One analysis call per question may create a serial waterfall | Cap request breadth; batch compatible queries; bound any concurrency |

The code has no `st.fragment` calls. A fair optimized-Streamlit baseline should evaluate forms/fragments, bounded caches and navigation changes before claiming unavoidable slow interactions. Verify features against the pinned Streamlit release; live documentation may include later additions. [S03](#s03), [S04](#s04).

The configured `pool_size=10` and `max_overflow=20` allow up to 30 connections **per engine per process**, not 30 for the entire organization. Multiple products, roles, workers and job processes multiply the ceiling. Pools allocate according to use, so this is potential demand, not an observed open-connection count. [S24](#s24).

## 7. Why the existing speed claims are not decision-grade

The included architecture documents report impressive synthetic improvements. The supplied scripts do not establish a matched comparison of complete CIP experiences:

- The FastAPI page renders a heading and plain table. The Streamlit SQL page includes a selector, metric, bar chart and dataframe. That is not the same UI workload.
- The browser script checks for a text marker, at 100 ms polling intervals, rather than verifying that the chart, table and controls are fully ready.
- Load steps add tabs without closing previous tabs. Steps 1, 5, 10 and 20 therefore leave 36 total open sessions at the end; the newest batch is not the whole session population.
- The experiment uses local SQLite and a macOS memory utility. Its ratios cannot be asserted to hold on Azure/MySQL or across different CPUs without measurement.
- Product authentication, entitlements, mixed query patterns, ETL overlap and realistic exports are not established by this synthetic page.

The reported historical throughput and "300 active users" calculations must therefore remain unverified claims, not CIP capacity commitments. TechEmpower results are similarly useful as server-test evidence, not a substitute for the application's own UI and database workload. [S33](#s33).

## 8. Validation actually performed

**Performed:** safe extraction; source inventory; AST parsing; selected source inspection; isolated session-function probes; mathematical cohort-signature counterexample; five-repeat synthetic data-path experiment with equivalent outputs.

**Attempted but unsuccessful:** full pytest collection. Dependencies including Streamlit, PyMySQL and tenacity were unavailable, and dependency installation was blocked by the environment's package-network resolution. Collection ended with 10 import errors. The supplied `.env` was not loaded into that test run; a sanitized copy and network-blocking guard were used.

**Not performed:** running all application pages, browser timing of CIP, validating SSO against the real provider, authenticating to MySQL/Forsta, testing Azure, measuring all live datasets or load-testing SIP/MIP. The local data-path test used pandas 2.2.3, below the repository's declared minimum, and is not a compatibility qualification.

## 9. Remediation priority

**Before any subscriber exposure:** rotate exposed credentials; remove development authentication/bypasses from deployment; finish OIDC; enforce permissions; fix session-store policy; separate database roles and enforce environment/TLS validation.

**Before performance approval:** bound whole-wave detail reads and exports; establish dataset-version publication; fix cohort invalidation; move maintenance work out of requests; measure cache and connection ceilings; qualify the real deployment.

**Before broad migration:** create pure Python domain/repository boundaries, reproducible locked environments and working MySQL integration tests. Retain the parts that are already correct rather than buying risk through a wholesale language translation.

---

<a id="chapter-3"></a>

# 03. Technology and marketplace comparison

[Contents](#contents) | [Source register](#chapter-8)

## 1. Compare the right layers

Node.js is a runtime. Python, JavaScript and TypeScript are languages, with TypeScript transpiled to JavaScript. Streamlit, FastAPI, Django and Fastify are frameworks serving different roles. React, Vue and Svelte are browser UI technologies. MySQL is the database. Comparing them in a single "fastest language" chart would conceal the architecture rather than evaluate it. [S06](#s06).

For CIP, evaluate **complete candidate architectures** under the same user journey, dataset, permissions and infrastructure. The judgments below are fit assessments, not measured performance scores. The shortlist covers credible options for this workload, rather than claiming to benchmark every framework in existence.

## 2. Custom-build shortlist

| Candidate | Why it is viable | Main CIP tradeoff | Decision |
|---|---|---|---|
| React/TypeScript/Vite + FastAPI | Independent browser UI with a Python service; retains current domain logic | Requires frontend engineering and production API/security work | **Recommended custom-product default** |
| React/TypeScript/Vite + Node.js/Fastify | Typed frontend/backend, schema-driven API validation/serialization | Python ETL still remains; translating domain rules can add duplication | **Strongest alternative; choose with stronger TypeScript delivery capability** |
| Vue/TypeScript or Svelte + either API | Full client UI; performance guidance/compiler approach are credible | New frontend conventions and component selection must fit the team | **Valid substitutes; no evidence React is universally faster** |
| Next.js + Python/Node services | Supports public-site rendering and integrated web features | Dynamic SSR can add runtime/caching complexity unnecessary for private dashboards | **Conditional; justified by public rendering or existing team capability** |
| Django + a client UI, or selective server-rendered interactions | Mature Python application structure; attractive when account/admin workflows dominate | More framework surface and mixed sync/async integration to manage | **Strong when already standard in the organization** |
| Flask + a client UI | Small Python web foundation | More assembly for validation, contracts, auth and operational conventions; async alone does not change its worker model | **Viable, but little reason to prefer a new Flask API over FastAPI here** |
| Plotly Dash | Python-centric analytics; client-side and background callbacks can reduce expensive server work | Complex subscriber UX and browser state need deliberate custom development | **Useful for analytics-heavy internal or constrained products** |
| Optimized Streamlit | Fastest path from current code to improved internal analysis | Server-oriented interaction/session model; less direct control of the full product shell | **Retain internally; customer use only after matched qualification** |
| Browser UI + Go API | Plausible compact service and high throughput for suitable handlers | Python research logic becomes a separate integration; added language/maintenance cost | **Profile-driven option, not an initial rewrite** |
| Browser UI + ASP.NET Core | Capable production APIs and established performance practices | Requires demonstrated .NET delivery expertise and integration with Python | **Strong alternative with an existing .NET team** |
| Browser UI + Java/Spring Boot | Capable enterprise backend; native-image options complicate stereotypes about Java memory | More implementation/build decisions for a team whose demonstrated assets are Python | **Not rejected for speed; not justified as the default here** |
| Browser UI + PHP/Laravel | Conventional application workflows can be built effectively; long-lived worker options exist | Survey/domain code still needs Python integration; worker state requires care | **Conditional on existing Laravel expertise, not a latency rescue** |
| Rust API + browser UI | Can be considered for specifically identified low-level hot paths | No Rust assets in the archive; rewrite and specialist-maintenance cost are unproven | **Not justified as an initial full-platform choice** |
| Plain JavaScript/custom frontend without a shared component system | Can be very lightweight for a small screen | CIP's growing workflows need consistent contracts, state and accessible components | **Reasonable for a tiny embed; not preferred for the full portal** |

Capability references: FastAPI [S08-S09](#s08); Fastify [S11](#s11); Vue [S15](#s15); Svelte [S16](#s16); Next.js [S12](#s12); Django [S13](#s13); Flask [S51](#s51); Dash [S14](#s14); ASP.NET [S34](#s34); Go diagnostics [S35](#s35); Spring native images [S46](#s46); Laravel Octane [S47](#s47).

## 3. Streamlit: the strongest fair case for and against it

### Adopt or retain it when

The application is mainly internal research; a small Python team needs to change analyses quickly; the standard widgets fit the workflow; and measured peak concurrency is comfortably within the resource envelope. Its existing role in the organization is a real asset: researchers can use their current language and domain functions.

A serious optimized baseline should use the existing aggregate-first SQL path, forms to group filter changes, fragments where supported, bounded small-result caches, suitable navigation, pagination and external jobs. It should use real identity and authorization, not a shared passphrase.

### Do not make it the default here when

The core product requirements are a persistent commercial application shell, independently updating panels, rich interactive state, multiple product modules, subscription-aware discovery, external integrations and a long-lived public API. A client application plus explicit service boundary is the preferred engineering shape for those requirements.

### Claims to reject

"Streamlit cannot scale," "it cannot authenticate users," "it has no partial reruns," and "each user always gets a complete permanent copy of every table" are not supported general claims. Its documented architecture, caching, fragments and OIDC features are more nuanced. On the other hand, replacing every `cache_data` call with `cache_resource` is not a safe universal memory fix: shared mutable resources require thread safety and strict access scoping. [S03](#s03), [S04](#s04), [S05](#s05), [S48](#s48).

## 4. Why React is a recommendation, not a speed trophy

The decision favors a reusable typed client product, not a brand of virtual DOM. Vue and Svelte can implement the same successful architecture. Choose the UI framework the team can maintain well, and make the data contract independent of that choice.

Use lazy loading for secondary routes and heavy chart modules. Configure browser-query freshness and retry behavior explicitly. A virtualized table reduces rendered rows; it does not reduce SQL work or the downloaded dataset unless server-side pagination is also implemented. React supports lazy component loading, and TanStack documents these query and table concerns separately. [S17](#s17), [S18](#s18), [S19](#s19).

No measured evidence here supports a statement such as "React is 30% faster than Vue for CIP." A poorly designed React screen can ship too much code, trigger request waterfalls or rerender expensive charts and perform worse than a carefully bounded alternative.

## 5. Indian and international marketplace options

The relevant buy/build choice is not a country's programming language. It is control over the product versus delivery speed, licensing, operational footprint, data governance and the team's ability to maintain it. Zoho is a concrete India-origin vendor in this shortlist; Appsmith and ToolJet are also relevant options for an India-based procurement/delivery team. No current legal domicile, data residency or support promise is inferred from a company's origin. [S45](#s45).

| Option | Appropriate use | Concrete evidence or constraint | CIP recommendation |
|---|---|---|---|
| **Zoho Analytics Embedded** | Buy a dashboard/reporting experience rather than build every visualization | Vendor documents embedding, SSO and branding capabilities; embedded pricing requires an applicable quote | **Best first India-origin buy-option to evaluate for a dashboard-first scope** |
| **Appsmith** | Internal operations, mapping tools and low-code workflows; client portals require a scoped evaluation | Current self-hosting guidance starts at 2 vCPU/8 GB and explicitly says this is not a production-capacity guarantee | **Do not assume it fits a shared 4.5 GB staging host** |
| **ToolJet** | Low-code internal tools and workflow applications | Current documentation lists a 4 GB app VM and separate PostgreSQL/cache requirements | **Not a lightweight all-in-one fit merely because the app VM says 4 GB** |
| **Metabase** | Rapid dashboards and embedded reporting | Free guest embedding has conditions; fuller embedded SDK/SSO/white-label options and license terms differ | **Strong global dashboard buy-option; evaluate exact embed and tenant needs** |
| **Power BI Embedded** | Reporting-centric product, particularly with existing Microsoft BI models and skills | Production embedding requires an appropriate paid capacity; authoring/licensing and architecture remain separate considerations | **Good conditional option, not a free MySQL-to-portal layer** |
| **Apache Superset** | Self-hosted BI exploration and embedded dashboards | Official SDK supports server-issued guest tokens and row-level rules; you still operate a BI service | **Useful BI option; not a replacement for all CIP product workflows** |
| **Retool** | Admin and operational application delivery | Pricing distinguishes deployment/features and user arrangements; external application terms need procurement review | **Evaluate for internal back-office work; do not assume best external-user economics** |
| **Custom React + API** | Distinct research workflows, entitlements, consistent product UX and extensibility | Highest direct control; engineering and operations remain your responsibility | **Preferred for CIP's stated full-product ambition** |

Official sources: Zoho [S36](#s36), [S37](#s37); Appsmith [S38](#s38); ToolJet [S39](#s39); Metabase [S40](#s40), [S41](#s41); Microsoft [S42](#s42); Superset [S44](#s44); Retool [S43](#s43).

**Important sizing distinction:** Appsmith's published starting point is above the entire stated staging allowance. ToolJet's current database guidance separately lists 8 GB for PostgreSQL plus Redis memory; that is not a claim that every deployment always consumes this much, but it invalidates the assumption that its complete documented stack fits inside a 4.5 GB shared host. Managed/cloud deployment can move the resource demand elsewhere, at a different cost and trust boundary.

For embedding, validate data isolation with two real test tenants, not just a successful dashboard screenshot. Ask each vendor for written terms covering external viewers, active users versus named users, tenant/workspace counts, SSO, white-labeling, exports, development environments, usage overages and exit/export rights. Evaluate region availability and residency contractually; an Indian vendor does not automatically mean every selected service stores data in India.

## 6. Licensing choices that can quietly change the budget

Do not assume that every advanced data-grid feature is included in a free edition. AG Grid distinguishes community and enterprise features, and its Excel export is an enterprise feature. A customer-facing pivoting experience may need a paid component or a custom implementation. [S20](#s20), [S21](#s21).

Start with a deliberately limited table contract: bounded columns, sorting, pagination, selection, accessible navigation and server-generated authorized exports. Evaluate the total implementation cost before choosing between a headless table, a community grid and a commercial grid. Server export generation is not automatically cheaper once research formatting and maintenance are included.

## 7. Choices not justified at launch

**Kubernetes/microservices everywhere:** a single modest host provides neither meaningful service isolation nor high availability merely because more processes are deployed. Prefer a modular API and a bounded job worker.

**An immediate database replacement:** the code already has MySQL aggregates. A second analytics engine should be justified by measured query patterns, data volume or workload isolation needs, not the claim that MySQL can never power analytics.

**A compulsory distributed cache:** first establish cache value, object sizes and hit rate. An additional service costs memory and operations. Versioned process-local caches can be adequate initially, acknowledging duplication and consistency limitations.

**Mandatory SSR for private dashboards:** Next.js can also export static content. The rejected default is unnecessary dynamic rendering complexity, not the framework itself. [S12](#s12).

**A complete Rust/Go/Java migration to chase a framework leaderboard:** server microbenchmarks measure specific handlers, not survey correctness, a user's network, chart rendering or subscription workflows. Use them to generate candidates, not to promise CIP speed. [S33](#s33).

## 8. Bottom-line ranking by actual objective

| Objective | Preferred starting point |
|---|---|
| Fastest improvement to existing internal analysis | Optimize current Streamlit and SQL |
| Best custom subscriber-product fit using the supplied assets | React/TypeScript/Vite + FastAPI + MySQL + Python worker |
| Best custom alternative with a strong TypeScript team | React/TypeScript/Vite + Fastify + MySQL + Python worker |
| Lowest initial engineering for fixed dashboards | Evaluate Zoho Analytics or Metabase; Power BI where already established |
| Best raw API throughput or lowest RSS | **Undetermined for CIP**; benchmark optimized candidates on the real workload |
| Worst practical pattern | Unbounded raw-data web processing and inline heavy work, regardless of language |

The procurement decision should remain reversible: own your dataset definitions, product entitlements and publication metadata even when buying the presentation layer.

---

<a id="chapter-4"></a>

# 04. Proposed system design

[Contents](#contents) | [Source register](#chapter-8)

**Status:** design proposal, not an implemented or load-qualified system. Component boundaries are chosen to preserve the existing Python research investment while making the subscriber experience independently evolvable.

## 1. Requirements and non-goals

CIP must provide a fast authenticated research experience; preserve question bases, cohorts, definitions and publication versions; enforce product subscriptions; support controlled exports and saved work; and remain operable within a small initial Azure allocation.

The initial product should prioritize U.S. survey data and source-API integration. China-specific expansion is not assumed to be part of the initial release. Existing SIP/MIP subscriber benefits should not be removed to manufacture an upgrade opportunity. Additional CIP access should be explicit and additive.

Initial non-goals are unrestricted user SQL, arbitrary executable chart configuration, real-time respondent-level data streaming, a microservice per screen, and a distributed analytics platform before scale requires one.

## 2. Logical architecture

```text
                       CUSTOMER BROWSER
              React + TypeScript, built with Vite
           Router / filters / charts / query state
                             |
                   HTTPS, same-origin API
                             |
                AZURE EDGE / HOST REVERSE PROXY
             TLS, compressed static assets, limits
                             |
                 CIP MODULAR API (FastAPI)
   +-----------------------------------------------------+
   | Identity/session | Product authorization | Rate limits|
   | Catalog          | Metrics/analysis      | Saved views|
   | Publications     | Export jobs           | Admin API  |
   | Request tracing  | Bounded versioned response cache  |
   +-----------------------------------------------------+
          | read-only research role       | restricted app-state role
          v                               v
   MySQL serving data                 MySQL application state
   Published versions                 Sessions/entitlements references
   Aggregate cells                    Saved views / jobs / audit records
   Canonical concepts                 Publications / current-version pointer
          ^                               ^
          | publish after validation      | claim/update durable jobs
          +--------------------+----------+
                               |
                     BOUNDED PYTHON WORKER
         ETL adapters / validation / harmonization / cubes
                exports / publication checks / cleanup
                    |                          |
       Forsta / legacy sources          Azure Blob/object storage
                                        private export artifacts

       Existing organizational identity provider <-- OIDC --> API
       Structured logs + metrics <-- API, worker, database, browser
```

This is a **modular monolith plus a worker**, not a large microservices estate. The API can contain several well-separated modules in one process deployment. The worker can reuse the same domain package without allowing ETL tasks to run inside a web request.

MySQL and object storage are shown as separate logical services. Their physical placement must be established from the actual deployment; the RAM plan in chapter 06 assumes the database is not consuming the application host's allocation.

## 3. Code structure and reuse boundary

Proposed organization:

```text
cip/
  frontend/                 # React/TypeScript; production build -> static dist/
  backend/
    api/                    # HTTP schemas, routes, auth dependencies
    domain/                 # Survey definitions, bases, concepts, policies
    repositories/           # MySQL queries; no Streamlit imports
    services/               # Analysis, publications, views, exports
    infrastructure/         # DB pools, sessions, cache, storage, telemetry
  worker/                   # Job dispatch, leases, source adapters, ETL commands
  shared_contracts/         # Generated TS types from versioned API schemas
  config/                   # Validated non-secret product/metric configuration
  migrations/               # Version-controlled schema changes
  tests/                    # Unit, real-MySQL integration, permissions, browser
```

Move existing functions rather than translate them wholesale. First remove `st.cache_data` wrappers from domain/repository functions; apply caching at the serving boundary. Streamlit can import the pure package or call the API during migration. Avoid two independently implemented percentage or cohort calculations.

Generate TypeScript API types from a reviewed schema, but also validate inputs on the server. Compile-time types do not make an untrusted HTTP request safe. Fastify has a comparable schema-validation approach if that backend is selected. [S06](#s06), [S11](#s11).

## 4. Request and query lifecycle

An ordinary analysis request follows this sequence:

1. Resolve the authenticated principal and applicable tenant/product permissions.
2. Validate the allowed metric, dimensions, filters, requested version and result-size limits.
3. Resolve one published dataset version and a compatible metric-definition version.
4. Build a canonical access-scoped cache key; return a cached authorized response when valid.
5. Execute a bounded query against aggregate cells, or an explicitly approved bounded fallback.
6. Return a compact typed response with provenance, base, weighting and version metadata.
7. Record timing, query class, cache outcome and request ID without logging sensitive response content.

The browser does not connect to MySQL and never receives a database credential. A hidden button is not authorization. Every direct endpoint, export download and saved-view operation must enforce the same policy. [S27](#s27).

### Query execution rules

Prefer SQL aggregation and small result objects. Do not construct a pandas dataframe simply to serialize 40 database rows. Preserve pandas where it is useful for research transformations and exports in the worker.

The current PyMySQL path is synchronous. An initial FastAPI implementation may use synchronous endpoints and a bounded execution pool. Alternatively, use a supported asynchronous MySQL dialect intentionally. Merely adding `async def` around a blocking database function does not make it asynchronous. Do not share a mutable ORM session across concurrent requests. [S08](#s08), [S25](#s25).

Create indexes from representative query plans: published dataset/version, survey/question/concept, cohort and breakdown dimensions. Index order and covering choices depend on selectivity and actual access patterns; no specific composite index is declared universally optimal from source inspection alone. Bound wave counts, dimensions, top-N categories and page sizes at the API. Expensive custom cohorts should be rejected with an explanation or moved to a job rather than silently using an unbounded fallback. [S23](#s23).

## 5. Data model additions

Retain the existing normalized survey and aggregate model. Add or formalize these logical entities through reviewed migrations:

| Entity | Essential purpose |
|---|---|
| `product` and `dataset_product` | Define commercial access boundaries independent of UI routes |
| `principal` and organization/tenant mapping | Identify people by verified identity-provider subject, not only mutable email |
| `entitlement` or synchronized entitlement reference | Record allowed product scope, validity and entitlement version |
| `dataset_version` | Identify immutable source/processing revisions, validation status and provenance |
| `published_dataset` | Point each dataset to the currently published version |
| `metric_definition_version` | Preserve denominator, transformation, weighting and suppression rules |
| `saved_view` with owner/tenant scope | Store validated configuration and optional pinned dataset version |
| `job` | Store owner, authorized scope, inputs, lease, status, retries and result reference |
| `publication_snapshot` | Pin research output to data/definition versions and preserve audit history |
| `audit_event` | Record security and publication changes with bounded retention |

These are logical boundaries, not a prescription to duplicate tables that already satisfy the purpose. Migrate existing entities after inspecting keys, foreign keys and dependencies.

### Publish safely

```text
Fetch source revision
       -> write staging version
       -> verify counts, keys, bases and definitions
       -> compute profiles/cohorts/aggregate cells
       -> verify serving queries and selected golden results
       -> atomically update current published-version pointer
       -> invalidate/prewarm bounded version-aware caches
       -> retain prior version for rollback/reproducibility
```

Use idempotency keyed to source and revision, not the time a retry happens to run. Never delete the only good serving cube before the replacement passes validation. Do not precompute every imaginable demographic combination; precompute common approved views and use limits/jobs for high-cardinality combinations.

Version consistency must extend to pagination, exports and multi-panel pages. An export uses the requested authorized version, not whichever version becomes latest halfway through generation. Old published versions also require authorization; knowing a version ID is not a permission.

## 6. Identity and permissions

Use a complete OIDC authorization-code flow with the appropriate state, nonce and PKCE protections through a maintained library or approved organizational auth service. Validate issuer, audience, signature, expiry and callback configuration. Key a user to the verified provider subject/issuer; treat email as an attribute.

The API sets a Secure, HttpOnly session cookie, uses CSRF protection for state-changing requests and validates the session according to a documented revocation policy. Tokens and signing material stay out of frontend bundles, source archives and routine logs. Define whether transient identity-store failure rejects requests or serves a narrowly scoped last-known state; do not leave an accidental fail-open branch. [S28](#s28).

### Commercial access model

| Principal | Allowed experience |
|---|---|
| Registered limited user | Approved samples/previews and a safe catalog; no accidental access to full datasets |
| Selected-product subscriber | Only purchased product scope, whether one product or several |
| All-data subscriber | All products covered by that contract; not automatically administrative privileges |
| Research analyst | Specific internal editing capabilities separate from commercial plan |
| Administrator | Explicit administrative permissions, with audit trails and least privilege |

Authorization intersects tenant context, product entitlement, dataset scope, action and ownership. Global research data need not be copied per tenant, but customer-private objects must be tenant-scoped. Do not assume MySQL automatically applies the application's required row-level policy.

Show the existence of additional data only through approved discoverability metadata. A locked dataset card must not include restricted values in HTML, API responses or browser memory. Preserve existing subscription rights while presenting additional CIP value honestly.

## 7. API contracts

Use versioned JSON contracts. The following endpoints are proposed; no such production API was found in the archive.

| Endpoint | Responsibility and limits |
|---|---|
| `GET /api/v1/me` | Current identity and UI-relevant permitted capabilities; no secrets |
| `GET /api/v1/catalog` | Authorized dataset/catalog metadata with bounded pagination |
| `GET /api/v1/datasets/{id}/overview` | Compact latest or explicitly pinned published summary |
| `POST /api/v1/analyses/query` | Validated metric/filter query; bounded synchronous path or explicit job transition |
| `GET /api/v1/datasets/{id}/trends` | Bounded wave range and compatible definitions |
| `GET/POST /api/v1/views` | List/save validated owner- or tenant-scoped views |
| `POST /api/v1/exports` | Validate access, create durable export job and return `202` |
| `GET /api/v1/jobs/{id}` | Owner/role-authorized progress and safe error information |
| `GET /api/v1/exports/{id}/download` | Recheck access before issuing a short-lived download or streaming content |
| `POST /api/v1/admin/publications` | Role-gated publication job; idempotent command |
| `GET /health/live` and `/health/ready` | Separate process liveness from dependency readiness |

Illustrative bounded query, not a live CIP schema:

```json
{
  "dataset_id": "us-consumer-survey",
  "dataset_version": "published-version-id",
  "metric_id": "purchase_intent_share",
  "metric_definition_version": "definition-version-id",
  "dimensions": ["age_group"],
  "filters": [{"field": "wave_id", "op": "eq", "value": "wave-id"}],
  "limit": 100
}
```

The response includes rows, `n`, eligible base, weighting status, suppressed/missing flags, dataset/definition versions, source, as-of time and request ID. Never encode missing or suppressed values as genuine zeroes. Multi-response questions require the correct question-specific denominator rather than a forced total of 100%.

Allowlist queryable identifiers and operations; use parameterized values. Do not accept raw SQL, Python, JavaScript or executable expressions as user chart configuration. An eventual natural-language interface must produce the same validated query contract and obey the same authorization. It must not obtain a parallel unrestricted database path.

## 8. Caching and browser state

Start with compact response caching only where measurement shows repeated useful work. An example logical key is:

```text
product + dataset_version + metric_definition_version
+ canonical_filters + dimensions + sort + page
+ effective_access_scope_version + tenant_scope_when_applicable
```

Check authorization before serving a cached response. Include user identity only when results are user-specific; scope-equivalent shared research results can share entries after authorization. Scope hashes are not a substitute for permission checks.

Enforce a byte budget as well as entry count and TTL. Use single-flight request coalescing for popular misses to avoid many identical queries. Record hit rate, evictions and object size. Process-local caches duplicate across workers and require version-aware invalidation; a distributed cache becomes justified when those tradeoffs are measured, not by default.

Browser query caches are in-memory and clear on logout, account switch and material entitlement changes. Default sensitive API responses to `Cache-Control: no-store`; separately approve any private revalidation policy. Do not put subscriber results in a public CDN cache. Public content-hashed static assets can be cached aggressively without caching private data.

## 9. Jobs and exports

A request creates a durable job with validated parameters, owner, access scope and version. Initially one worker claims jobs using transactional compare-and-set/lease logic. Record attempts, lease expiry and progress; renew leases while working; cap retries; move persistent failures to an inspectable failed state. At-least-once retries require idempotent side effects.

Run one heavy ETL/export task at a time until peak memory and CPU measurements justify more. Enforce per-user and global queue limits so one subscriber cannot exhaust the host. Small priority interactive work must not be blocked behind a long export. Azure's background-job guidance highlights contention and the need for reliable execution patterns. [S30](#s30).

Use the existing database for a modest initial durable queue only when database load and operational requirements permit. Azure Storage Queue is a sensible next option when already available; avoid deploying a full broker stack merely for the first export feature. In-process request background tasks are not the durability boundary.

Store completed exports privately in object storage with expiry and cleanup. Recheck permissions on download; do not disclose predictable public object URLs. Spreadsheet/CSV export should neutralize formula-like untrusted text, apply approved disclosure/suppression rules and record the exact data version.

## 10. Deployment, recovery and scaling

A VM deployment may serve static assets and proxy the API through the existing web server, with separate controlled API/worker services. An App Service deployment must use the plan's supported runtime, process and job arrangements. Build frontend assets in CI, not on the memory-constrained production host. Vite's preview server is not the production hosting strategy. [S07](#s07).

**Do not infer that the host is an Azure VM, a particular App Service SKU or a given vCPU count from the supplied RAM figures.** Apps and deployment slots on an App Service plan can share the plan's resources; confirm placement before calculating capacity. [S29](#s29).

Keep schema migrations separate from every web-worker startup. Use backward-compatible expand/migrate/contract changes, smoke tests, retained artifacts and a rollback procedure. A blue/green deployment or staging slot can temporarily double application footprint; reserve that headroom or use a controlled maintenance deployment rather than promise zero downtime without resources.

Failure behavior:

| Failure | Required behavior |
|---|---|
| Source API or ETL failure | Continue serving the last validated published version; show freshness honestly |
| Database unavailable | Reject dependent requests clearly; do not silently return partial data or grant access |
| Cache failure | Fall back only within database admission limits; prevent a miss storm |
| Worker crash | Lease expires, safe retry occurs, no duplicate publication or unbounded artifact leak |
| API restart | Recover sessions/views from durable state; no essential user state trapped in process memory |
| Data validation failure | Block new publication and retain previous version |
| Host loss | Restore from tested backups; acknowledge outage under a single-host design |

Define business recovery objectives explicitly. An initial planning discussion might consider one-hour recovery-point and four-hour recovery-time objectives, but neither is achieved by this proposal. They require suitable database backup/PITR, storage policy, recovery automation and timed restore tests.

Scale in order of observed constraint: fix a query/payload; constrain/cache repeated work; move heavy jobs off the host; increase or isolate application capacity; then add redundant API instances and suitable database/storage availability. Stateless request handling helps scale out, but active request buffers, caches, pools and jobs still consume memory. A single host remains a single point of failure regardless of language.

## 11. Operations and release quality

Collect per-route latency distributions, browser interaction/result timing, request/response bytes, cache hit/miss and eviction counts, pool waits, database query duration, CPU, process RSS, worker peak memory, queue age, ETL freshness and publication failures. Bound log retention and avoid storing raw survey answers or credentials in traces.

Use golden research-result tests, authorization matrices, database integration tests, real browser journeys, accessibility checks and deployment smoke tests. Test tenant isolation, subscription expiry, session revocation, export ownership, old-version access and failure recovery explicitly. Build a dependency lock, scan for secrets and known vulnerabilities, and pin supported runtime versions during implementation rather than copying an unreviewed `latest` image.

The architectural goal is a predictable, inspectable product. No individual library replaces these operational controls.

---

<a id="chapter-5"></a>

# 05. Performance evidence and qualification plan

[Contents](#contents) | [Source register](#chapter-8)

## 1. What "milliseconds" must mean

Distinguish three outcomes: a control reacts visually; an API completes; the user sees correct new results. A fast spinner is not a fast analysis. The browser's INP metric evaluates responsiveness to the next paint, not the completion of every later network result. Its documented good threshold is 200 ms or less at the 75th percentile of field page views. [S32](#s32).

A useful latency decomposition is:

```text
Click-to-result = browser scheduling
                + request network transit
                + server queue/pool wait
                + authorization and cache/query work
                + serialization and response transfer
                + browser parsing, chart/table rendering and paint
```

Local interaction can avoid a network trip. Fetching a result from a remote server cannot avoid its transit time simply by choosing a compiled language. Consequently, "every operation in 1-10 ms worldwide" is not a credible requirement for this architecture.

## 2. Actual local experiment: reduce data before transferring it

The experiment created one million synthetic store rows in temporary SQLite storage. Both alternatives produced the same Apparel-by-state summary: store count, open count and revenue, checked with a floating-point tolerance. Each path ran in a separate process with five repetitions.

| Measured quantity | Full dataframe, then filter/group | SQL filter/group, then dataframe |
|---|---:|---:|
| Rows returned from database | 1,000,000 | 50 |
| Final result rows | 50 | 50 |
| Median measured data-path duration | **2,326.89 ms** | **92.46 ms** |
| Dataframe deep size | **209,099,220 bytes** | **3,932 bytes** |
| Serialized dataframe size | 71,110,320 bytes | 2,352 bytes |
| Median standalone pickle-deserialization time | 157.20 ms | 0.058 ms |
| Process peak RSS high-water mark | 1,192,992 KiB | 102,316 KiB |

The observed median data-path ratio was approximately **25.2x** in this experiment. It is **not a Streamlit-versus-FastAPI ratio**. Both paths were Python. The result supports pushing filtering/aggregation into the database and keeping web responses small; optimized Streamlit benefits from exactly the same change.

Raw output: [data-path-results.json](evidence/data-path-results.json). Script: [data_path_probe.py](validation/data_path_probe.py).

### Environment and limitations

Python 3.13.5, pandas 2.2.3, Linux x86-64, five reported logical CPUs, seed 1, SQLite database about 75 MB. The environment is not the user's Azure server. pandas is below the repository's declared minimum, so this is not application-runtime qualification.

OS page caches were not flushed and the full-dataframe path ran before the SQL-summary path. Only five samples per path were gathered; these do not justify p95/p99 claims. RSS is a process high-water mark including pandas, temporary objects and the pickle-copy phase, **not incremental RAM per user**. The pickle measurement illustrates data-copy cost; it does not run Streamlit's cache implementation.

There was no browser, chart, authentication, network, MySQL, Streamlit, FastAPI or Node workload in this experiment. It cannot establish how many users the production server supports or which framework wins.

### Reproduction

Run in an isolated development environment with pandas available, never inside the production web process:

```bash
python validation/data_path_probe.py --out local-results.json --rows 1000000 --repeats 5
```

The million-row full-data path exceeded 1 GiB process peak RSS in this run. Start with fewer rows on a constrained machine. The script uses Python's Unix `resource` API; the recorded RSS units and result above are from Linux. On macOS, `ru_maxrss` has different units, so normalize before comparing memory. The package does not claim Windows compatibility for this probe.

## 3. Source-function probes and full-suite status

The second script extracts only selected functions from the supplied source AST and supplies fake database objects. It does not import the application or connect to real services.

```bash
python validation/source_probes.py /path/to/extracted/repository --out source-probes.json
```

It reproduced `_session_is_live` returning true on store error or missing row, and false on revoked/expired rows. It also demonstrates that equal count and ID sum do not prove equal cohort membership. See [source-probes.json](evidence/source-probes.json).

These probes were successfully executed. They are not substitutes for the full test suite. Full pytest collection was attempted in a sanitized offline copy and stopped with **10 import errors** because required dependencies were unavailable. No claim is made that the application's tests passed.

## 4. Why previous framework numbers cannot be adopted

The uploaded benchmark API serves a smaller UI than the Streamlit alternative. The timing script waits for a text marker, not complete chart/table readiness, and polls at 100 ms. Accumulating tab counts also differ from the size of the newest load batch. These details prevent treating the report's ratios as a controlled measure of framework overhead. See E12 in [the code audit](#chapter-2).

Do not use API requests per second as a substitute for interactive users. Do not use TechEmpower's controlled server tests as a UI or Azure/MySQL forecast. Those results answer their defined benchmark questions; CIP must answer its own. [S33](#s33).

## 5. Proposed acceptance targets, not achieved results

The following are initial engineering targets to negotiate against actual regions, devices and workloads. They are not statements that the current code meets them.

| Metric | Proposed initial target | Boundary |
|---|---|---|
| Local control acknowledgement | p95 <= 100 ms | Expanding a filter, selecting a local tab, acknowledging a click |
| INP | p75 <= 200 ms | Field responsiveness, segmented by desktop/mobile |
| First-load LCP | p75 <= 2.5 s | Supported devices and representative user networks |
| Cached compact API response | p95 <= 100 ms | Server-side duration, including authorization; excludes WAN |
| Common indexed aggregate API | p95 <= 300 ms | Server-side duration with bounded input/output |
| Ordinary click to correct results | p95 <= 800 ms | Full browser journey in defined primary-market network profiles |
| Expensive custom analysis | Explicit job transition when outside synchronous budget | Do not hold a request indefinitely |
| Export/job submission | p95 <= 300 ms server-side | Acknowledgement, not full file creation |
| Unexpected error rate under target load | < 0.5% | Exclude deliberately rejected invalid/unauthorized inputs; report these separately |

INP and LCP reference thresholds come from web.dev; the API, click-to-result and error targets are proposed CIP policy. [S32](#s32), [S49](#s49).

Do not sum p95 values from separate components and call the sum an exact end-to-end p95. Measure the actual journey distribution. Track p99 and worst-case examples as well; an attractive median can conceal a painful tail.

## 6. Browser implementation budget

Prioritize operations that do not need the server: opening navigation, expanding filters, switching chart presentation of already-authorized small results and reordering a small loaded view. Use server requests for filtering or sorting the full dataset; sorting only one page must not pretend to sort all results.

A starting payload policy is a typical compact response of roughly 100-250 KB compressed or less, with explicit exceptions and separate exports. This is a proposed budget, not an observed CIP size. Limit chart points, page rows and rendered columns; enforce these limits server-side. Lazy-load expensive chart/editor modules, avoid repeated full chart recreation, and cancel or ignore obsolete requests when a user changes filters rapidly.

For text search, a proposed 150-250 ms debounce can reduce redundant requests; display typing immediately. An explicit Apply action suits multi-filter analyses and avoids recomputing after each partial selection. TanStack Query defaults require intentional freshness configuration, while virtualization is distinct from database pagination. [S17](#s17), [S18](#s18), [S19](#s19).

## 7. Capacity model: users are not requests

A purely illustrative workload:

```text
300 simultaneously active people
x one action per 10 seconds
x two API requests per action
= 60 API requests/second

At an assumed 80% useful response-cache hit rate:
60 x 20% = 12 cache-miss requests/second

At an assumed three database queries per miss:
12 x 3 = 36 database queries/second

At an assumed mean request residence time of 0.15 seconds:
60 x 0.15 = 9 average in-flight API requests
```

This arithmetic is not evidence that the server can handle 300 active users. Change the action rate, cache locality, query duration, auth-store traffic or export activity and the result changes. Authentication queries may still occur on cache hits; account for them separately rather than omit them from database load.

Registered users, active sessions, open tabs, active people, concurrent requests and sustained arrival rate are different quantities. Capacity depends on CPU, database limits, query distribution, network latency, memory, background jobs and neighboring products, not RAM alone.

## 8. A fair proof-of-concept comparison

Build one real vertical slice in **optimized Streamlit** and **the recommended web/API architecture**. Add a Fastify implementation of the same API only if the team/language decision remains material. Do not build every candidate into a full product.

Hold constant: actual MySQL data/version; research calculations; permissions; authentication; visible selector/chart/table; output rows; payload meaning; export behavior; server allocation; browser/network profiles. Match cache semantics, including cold-cache work and version invalidation, rather than compare a globally cached API with uncached authenticated data reads.

The comparison must include selecting a survey, applying filters, viewing the updated chart and table, paging details, saving a view, starting an export and revisiting the same page. Browser tests should confirm correct content and an interactive control after the result is painted, not merely locate a heading.

### Test matrix

| Dimension | Required coverage |
|---|---|
| Load | Step through 5, 25, 50, 100, 250 and 500 active virtual users until a limit is reached; do not assume all steps pass |
| Arrival model | Both realistic think-time sessions and controlled request arrival rates; record dropped/queued work |
| Duration | Warm-up, steady-state, spike and extended soak runs; repeat comparisons |
| Cache | Cold, warm, low-locality and publication/invalidation bursts |
| Data | Small/common, largest wave, wide permitted breakdown, empty and suppressed results |
| Identity | Several accounts and tenants; selected-product versus all-data entitlements |
| Geography | Representative India and U.S. network profiles; actual intended server region |
| Contention | Other hosted products active; ETL, export and backup overlap |
| Failure | DB delays, worker restart, API recycle, session revocation and failed publication |

The user counts above are test inputs, not promised capacity. Browser-level tests are needed for Streamlit and the client application. API-only load tests may characterize the new API separately, but cannot be compared directly with full Streamlit page timing as if they measured the same boundary.

### Record these outputs

For each run, capture commit, environment lock, Azure SKU, vCPU, RAM basis, database SKU/version/location, seed/data version, account scopes, cache state, active sibling applications and arrival pattern. Report completed user actions, requests/second, p50/p95/p99 latency, unexpected error rate, CPU, process peak RSS, cache bytes/hit rate, pool waits, connections, query duration, job queue age and payload bytes.

Verify the load generator is not the bottleneck. Record client-side saturation and coordinated-omission risks rather than claiming the absence of slow requests when the generator simply stopped issuing work. Keep artifacts and raw samples; a screenshot of a single fast request is not release evidence.

## 9. Performance acceptance gate

Release only when the selected architecture meets the agreed normal-load SLOs, remains correct under permissions/version tests, maintains memory headroom during representative jobs, and recovers from the specified failures. Establish the safe operating envelope below the observed saturation point rather than operate at the largest load that survived once.

When a candidate fails, use traces to attribute the limit: SQL, lock/pool wait, payload, CPU, event-loop blocking, chart rendering, network or background contention. Only replace the framework when framework-related cost is material after reasonable optimization. This is how a performance decision becomes defensible rather than ideological.

---

<a id="chapter-6"></a>

# 06. Infrastructure, cost and migration

[Contents](#contents) | [Source register](#chapter-8)

## 1. Use the supplied limits, not the old report's assumptions

The current brief gives approximately **4.5 GB for staging** and **9.88 GB for production**, with the same configuration mentioned for CIQ, MIP and MDB. Previous documents in the archive discuss different RAM figures and App Service SKUs. Those older assumptions are not adopted.

RAM does not identify vCPU count, disk throughput, host type, available CPU credits, database capacity or an Azure price. Confirm whether these numbers mean provisioned RAM, a container limit or currently free memory, and whether they are GB or GiB. This report preserves the brief's approximate GB convention for planning.

## 2. Hosting scenarios

| Actual arrangement | Consequence |
|---|---|
| One VM shared by CIP, CIQ, MIP and MDB | One total CPU/RAM envelope; worker peaks, backups and deployments compete with every app |
| Multiple apps on one App Service plan | App separation is not dedicated compute; count all apps and deployment slots against the plan |
| Separate VM/plan per product with identical sizing | Each product has its own allocation and corresponding infrastructure cost |
| MySQL also on the application host | Database buffers, connections, storage and backup work must be added; the sample allocation below is invalid until recalculated |
| Staging and production share physical capacity | Testing can affect live work; isolate or strictly control qualification tests |

Microsoft documents resource sharing among apps and slots within an App Service plan. The word "server" in the brief is not enough to establish which scenario applies. [S29](#s29).

## 3. Illustrative shared-host memory allocation

**These are budgeting placeholders, not observed RSS, proven minimums or deployed limits.** The purpose is to expose contention before purchasing or configuring anything. This table assumes MySQL and object storage are external to the application host.

| Allocation bucket | Staging GB | Production GB |
|---|---:|---:|
| Host/runtime, proxy, telemetry and operational overhead | 0.65 | 1.00 |
| CIP API processes, excluding the separately budgeted response cache | 0.60 | 1.20 |
| CIP bounded response cache, total across processes | 0.15 | 0.40 |
| One bounded CIP job worker | 0.65 | 1.40 |
| Provisional combined reserve for CIQ, MIP and MDB | 1.35 | 3.60 |
| Unallocated headroom for peaks and deployment | 1.10 | 2.28 |
| **Total** | **4.50** | **9.88** |

There is no evidence that the three sibling products fit their provisional reserve or that the current full-wave ETL fits the proposed worker bucket. The synthetic experiment alone demonstrates how quickly a dataframe path can exceed 1 GiB process RSS. Measure actual worker peaks before setting a limit; chunk, reschedule or externalize jobs when necessary.

If the siblings already consume the available memory, adding a new framework cannot create safe capacity. A smaller cache, one API worker and scheduled ETL may help, but host isolation or an increased allocation may be the honest requirement.

Start staging with one API process. Production might use one or two, **only if measured CPU and memory support it**. More workers can improve parallelism while duplicating code, imports, caches and connection pools. FastAPI's deployment guidance explicitly warns that worker processes generally do not share memory. [S09](#s09).

## 4. Connection and concurrency budgets

Start from the database's safe connection/query budget and allocate it across all products. A proposed per-API-process read pool might be five connections with zero to two overflow connections; this is a test configuration, not an optimal universal setting.

For illustration:

```text
4 products x 2 API processes x (5 pool + 2 overflow)
= 56 potential research-read connections

Application-state pools, ETL connections, admin sessions and deployment overlap
must be added separately.
```

By contrast, the archive's 10 + 20 default permits 30 connections per engine/process. Four products with two processes each could therefore allow 240 connections for one role if all used that configuration. These are maximum-potential calculations, not observed open connections. SQLAlchemy pool documentation explains allocation and overflow behavior. [S24](#s24).

Admission limits matter more than a large pool. Prefer a bounded wait with a useful error/job response over allowing hundreds of expensive queries to compete. A user session should not permanently reserve a database connection.

## 5. What actually lowers long-run cost

The strongest mechanisms are reuse of existing research logic, shared tested UI/auth contracts across products, less data copied per request, fewer redundant queries, reusable product configuration, reduced incident/rework burden and deferred infrastructure upgrades.

**A faster application does not automatically lower the current Azure bill.** When a fixed host remains provisioned, efficiency usually creates headroom rather than a direct monthly saving. Savings require a real pricing change, such as a smaller plan, fewer instances, less paid capacity, lower metered consumption or avoiding an otherwise necessary upgrade.

Likewise, open-source frameworks are not a free operating model. Engineering, security maintenance, on-call work, backups, identity services, database hosting, storage, observability and third-party components still cost money. Compare custom engineering against applicable vendor quotes, not against a vendor's cheapest unrelated internal-user tier.

## 6. Three-year cost model

Use the same scope and service level for every alternative:

```text
36-month TCO = initial design/build/migration cost
             + 36 x (hosting + database + storage + identity + monitoring
                     + software licenses + maintenance/support)
             + expected incident/recovery cost
             + exit/migration cost
```

Separate the cost already spent on ETL from the incremental cost of retaining or replacing it. Include frontend capability-building when comparing FastAPI/React with an optimized existing Streamlit implementation. Include the additional Python/TypeScript integration burden when comparing a Node API with a Python API.

### Illustrative break-even, not a market quote

Assume a custom product layer costs an additional **400 engineering hours** at an assumed blended **INR 1,500/hour**:

```text
Initial incremental cost = 400 x 1,500 = INR 600,000

If net maintenance/rework savings are 20 hours/month:
Monthly savings = 20 x 1,500 = INR 30,000
Infrastructure savings assumed = INR 0
Break-even = 600,000 / 30,000 = 20 months

If net savings are only 5 hours/month:
Monthly savings = INR 7,500
Break-even = 80 months
```

The hourly rate, effort and savings are hypothetical planning inputs, not observed company costs or national salary benchmarks. The sensitivity is the point: the rewrite is not automatically economical. If it does not improve delivery, adoption, reliability or capacity enough to offset its cost, retaining a simpler solution is rational.

For Azure, calculate using the actual region, service/SKU, operating system, billing arrangement, database, storage, data transfer and monitoring retention. RAM alone is insufficient to quote a monthly bill. Use the official pricing calculator and the existing bill rather than a guessed dollar amount. [S31](#s31).

## 7. Migration gates

| Gate | Work | Evidence required to proceed |
|---|---|---|
| 0. Secure the baseline | Rotate credentials; fix environment validation, sessions, SSO, roles and permissions | Negative authorization tests; secrets absent from build artifacts |
| 1. Make the code testable | Extract pure domain/repository functions; pin dependencies; establish real-MySQL integration tests | Reproducible test run and golden research results |
| 2. Deliver one vertical slice | Overview plus one realistic analysis journey in optimized Streamlit and web/API | Same results, matched functionality, actual Azure/network measurements |
| 3. Establish publication/jobs | Immutable data versions, bounded exports, leases/retries and rollback | Failed ETL retains last good version; crash/retry and ownership tests pass |
| 4. Complete subscriber workflow | Catalog, entitlements, saved views, trends, publications and approved previews | End-to-end tests across commercial plans and tenant scopes |
| 5. Qualify operations | Load/soak, restore, upgrade/rollback and telemetry | Measured operating envelope with headroom and recovery evidence |
| 6. Expand selectively | Reuse proven contracts/components for other products | Per-product cost/benefit and regression review; no forced big-bang migration |

These are dependency gates, not delivery-date promises. A failure at gate 2 can justify staying with Streamlit longer, choosing Fastify, or changing the resource constraint. The entire SIP/MIP interface should not be rewritten before the CIP slice proves useful.

## 8. When to add infrastructure

| Observed constraint | First response | Later escalation |
|---|---|---|
| Slow SQL / large scanned rows | Index/query/aggregate redesign; correct result bounds | Separate analytics serving engine only with measured need |
| Worker peak affects UI | Chunk work, one heavy job at a time, scheduling | Isolate the worker onto separate compute |
| Duplicate cache/query work across processes | Versioned keys and request coalescing | Shared cache after measuring its benefit and footprint |
| API CPU dominates after query optimization | Profile serialization and handlers | Compare additional compute or a focused Go/.NET/Node service |
| Single-host availability unacceptable | Define outage/recovery requirement | Redundant API instances and appropriate database/storage HA |
| Shared products exhaust host | Enforce budgets and identify the largest workload | Split plans/hosts rather than hide contention with bigger pools |

Do not install Kubernetes merely because the word scalable is in the brief. The first scale improvement is often workload isolation or a second suitable instance, not a new orchestration platform.

## 9. Commercial success measures

Track time to first useful insight, successful search-to-analysis conversion, repeat use, saved-view reuse, successful exports, trusted publication consumption, support tickets and conversion to genuinely additional product access. These measures test whether the engineering investment serves the business.

A language does not attract subscribers by itself. Reliable relevant data, clear access and fast understandable workflows are the proposed adoption levers; measure them rather than promise growth from the stack.

## 10. Deployment inputs still required

Before committing capacity or a purchase, establish exact host type/SKU/region/vCPU, the meaning of the RAM figures, which products/slots share resources, database placement/version/limits, actual peak process memory, largest survey and export sizes, expected active-user behavior, identity-provider requirements, frontend/backend team capability and recovery objectives.

These are implementation qualification inputs, not reasons to delay the architectural recommendation. The recommended starting architecture remains deliberately small and reversible while they are measured.

---

<a id="chapter-7"></a>

# 07. UI specification and interaction design

[Contents](#contents) | [System design](#chapter-4)

**Status:** proposed information architecture and wireframes, not a shipped frontend or a pixel-validated design file.

## 1. Design objective

Make it easy to find a trusted answer, understand its source/base and return to the same analysis. The primary interface should feel like one research product rather than a collection of scripts. Maintain the established direction of top navigation, compact page headers, collapsible filters and efficient use of screen space.

The initial content emphasis is U.S. consumer/survey research. Do not populate navigation with unavailable regions or promise datasets not yet published.

## 2. Application shell

```text
+--------------------------------------------------------------------------------+
| CORESIGHT  |  CIP                         Search research...  Help  [Account]    |
| Overview     Explore data     Analysis     Trends     Publications     Saved     |
+--------------------------------------------------------------------------------+
| Consumer insights                                         Data as of: [date]   |
| Dataset: [name]  Wave: [period]  Source: [source]  Version: [published revision]   |
+--------------------------------------------------------------------------------+
| Filters [collapsed / expanded]     Active filters: [chip] [chip]   Clear         |
+--------------------------------------------------------------------------------+
| [Research summary / eligible base] [Selected metric] [Comparable prior wave]     |
+--------------------------------------------------------------------------------+
| Main chart                                         | Context and methodology   |
|                                                    | Base / weighting / notes  |
|                                                    | Related permitted data    |
+--------------------------------------------------------------------------------+
| Table view   [sort] [columns]                       Save view   Export           |
| Bounded rows, clear denominator, paging                                         |
+--------------------------------------------------------------------------------+
```

The account area shows plan/capability information only where useful. Administrative tools are role-gated and separated from the subscriber navigation. Consistent branding does not require copying every SIP screen; CIP has a different analytical task.

## 3. Core screens

| Screen | User task | Required components |
|---|---|---|
| Overview | Understand what is new and relevant | Latest published waves, curated insights, saved work, freshness and methodology links |
| Explore data | Discover an answerable question | Search, source/topic/wave filters, clear scope, approved additional-product previews |
| Analysis Builder | Create an authorized comparison | Dataset/question selection, validated cohort filters, breakdown, chart/table, base and save/export |
| Trends | Compare compatible waves | Concept mapping, wave range, visible definition changes and comparability notes |
| Publications | Use stable research output | Published snapshot, source/version, notes and authorized download |
| Saved | Resume a prior workflow | Owned/shared views, permission scope, pinned-versus-latest behavior |
| Account/access | Understand current rights and additional options | Purchased scope, approved upgrade/contact workflow, session/account settings |
| Internal operations | Maintain data safely | Mapping queue, quality failures, publication jobs and audit history behind research/admin roles |

The first release should perfect Overview and one Analysis journey rather than launch every route with shallow functionality.

## 4. Analysis Builder wireframe

```text
+--------------------------------------------------------------------------------+
| Analysis Builder                                           [Save] [Export]      |
| Dataset [v]   Question/concept [search...]   Published version [v]                |
+------------------------+-------------------------------------------------------+
| ANALYSIS SETTINGS      | [Chart] [Table] [Methodology]                          |
| Wave [v]               |                                                       |
| Cohort [v]             | Selected question / metric                            |
| Breakdown [v]          | Chart with bounded categories and accessible labels   |
| Measure [v]            |                                                       |
|                        | Base: ...  Weighting: ...  Source: ...                |
| Active filters         | Missing/suppressed values explained                   |
| [filter] [filter]      +-------------------------------------------------------+
|                        | Table: category | estimate | n | base | notes         |
| [Apply]  Reset         | [Previous]     Page ...      [Next]                   |
+------------------------+-------------------------------------------------------+
| Result scope / version / freshness / request status                             |
+--------------------------------------------------------------------------------+
```

On narrower screens, collapse settings into a drawer and preserve the result context. Keep filters in the URL or a saved definition where safe, so navigation and sharing retain the analysis without sharing credentials or private tokens.

## 5. Interaction rules for speed and clarity

Opening a menu or filter panel should be local browser work. Keep chart/table presentation changes local when they reuse the same small authorized result. Apply full-dataset filters and sorts through the server contract; never imply that sorting one downloaded page sorts the whole dataset.

Use an Apply action for combined cohort/breakdown changes. Show the pending selection without replacing the current valid result until the new request completes. Cancel or disregard obsolete responses so an older slow request cannot overwrite the latest selection. Keep previous data visible with an explicit updating state where appropriate; do not label it as the new result.

Fetch shared page metadata once. Avoid one redundant request per widget. Load chart editors and administration code only when needed. Virtualize long tables, but also limit rows returned. Treat query freshness, retries and focus refetches as deliberate choices rather than library defaults. [S17](#s17), [S18](#s18), [S19](#s19).

Use subtle skeletons for initial loading and a clear progress state for jobs. Avoid decorative sleeps, artificial progress percentages and animations that delay the next useful action.

## 6. Research trust is part of the UI

Every result should disclose enough context to prevent misinterpretation: question/concept, wave period, source, data version/as-of date, eligible base, displayed count, weighting status and applicable methodological notes.

Question bases must remain question-specific. A missing answer, a suppressed result and a measured zero need distinct representations. Do not imply statistical significance simply because two percentages differ or automatically add significance markers without approved methodology. A multi-response question can legitimately have category percentages that do not sum to 100%.

Define small-base suppression, respondent-level access and disclosure rules with the research/privacy owners. A hard-coded arbitrary threshold is not a substitute for a policy, and repeated filtered queries can reveal information even when individual tables suppress cells. Restrict raw verbatims and respondent detail separately from aggregate access.

Keep publication snapshots reproducible. A saved view should clearly state whether it follows the newest published data or pins a version; changing a metric definition must not silently rewrite the meaning of a published figure.

## 7. Empty, unavailable and restricted states

| State | User-facing meaning | Product behavior |
|---|---|---|
| No matching results | The permitted data exists, but the filters match nothing | Preserve filters and offer reset/edit |
| No published data yet | Dataset exists but is not ready | Show approved availability context, not invented values |
| Additional subscription required | An approved catalog entry is outside current access | Describe the additional scope without leaking restricted values |
| Data delayed | Latest successful publication is older than expected | Display its real as-of time and a status message |
| Suppressed result | Policy prevents displaying a value | Explain the suppression, not a zero or a blank chart |
| System error | A request failed | Preserve user work, show retry and a support request ID |

These distinctions prevent an upgrade opportunity from misleading a user into thinking the platform lacks relevant data. Existing SIP/MIP entitlements must continue to provide their agreed benefits.

## 8. Configuration without arbitrary code

Use version-controlled, schema-validated configuration for navigation labels, permitted page templates, metric definitions, default filters, chart types, source notes and feature flags. Separate those from runtime entitlements and secrets.

A metric definition should specify allowed dimensions, denominator rules, weighting, compatible waves, display units, suppression policy and version. A chart configuration should reference an allowed metric and presentation options, not arbitrary SQL or executable JavaScript.

Share design tokens, core components and API contracts across CIP/CIQ/MIP/MDB where appropriate. Keep product-specific research definitions modular. Avoid generating one unmaintainable global configuration document that requires coordinated release of all products.

## 9. Accessibility and responsive behavior

Adopt WCAG 2.2 AA as a design/QA target, not a certification claim. Provide keyboard-accessible filters and dialogs, visible focus, meaningful field labels, sufficient contrast, non-color-only distinctions and text/table alternatives to charts. Ensure focus remains sensible after updates and that status/error messages are announced appropriately. [S50](#s50).

Test dense tables at realistic zoom levels and smaller viewports. A desktop-first research application can prioritize wide analysis layouts without making account, saved-view and overview tasks unusable on mobile.

## 10. UI release acceptance

A user must be able to sign in, find an entitled dataset, understand its scope, apply a comparison, inspect the correct base, save the view, reopen it and request an authorized export without losing context. The same workflow must remain understandable during slow requests, empty results and session expiry.

Assess perceived responsiveness and click-to-correct-result timing separately. Track time to first useful insight, successful analysis completion, saved-view reuse and export success. These outcomes determine whether the UI is helping attract and retain users; a frontend framework name does not.

---

<a id="chapter-8"></a>

# 08. Primary source register

[Contents](#contents)

**Research date:** October 20, 2026. Sources below are official project, vendor, standards or cloud documentation inspected for this review. Live pages can change; pin and revalidate the versions selected for implementation.

The source register supports capability, licensing and deployment statements. It does **not** convert vendor claims, microbenchmarks or documentation examples into measured CIP results. Source-code observations are separately indexed as E01-E17 in chapter 02. Local measurements are in the accompanying JSON files.

No current Azure monthly price, vendor quote, precise user capacity or application-level framework speed ranking was established. License summaries here identify procurement questions, not a substitute for reviewing the applicable contract.

<a id="s01"></a>
### S01. REA public skill instructions

[Official source](https://raw.githubusercontent.com/illumi-ai/REA/main/skills/reverse-engineer-anything/SKILL.md)

**Used for:** Routing ordinary source-repository work to repository tools; distinguish source observations from runtime evidence.

<a id="s02"></a>
### S02. Streamlit: Architecture and execution

[Official source](https://docs.streamlit.io/develop/concepts/architecture)

**Used for:** Execution-model background. Check feature behavior against the repository pin, not only live documentation.

<a id="s03"></a>
### S03. Streamlit: Fragments

[Official source](https://docs.streamlit.io/develop/concepts/architecture/fragments)

**Used for:** Partial reruns are supported; do not treat every interaction as unavoidably requiring full-page work.

<a id="s04"></a>
### S04. Streamlit: Caching overview

[Official source](https://docs.streamlit.io/develop/concepts/architecture/caching)

**Used for:** Cache-data copying, shared resources, TTL and max_entries. These mechanisms do not provide a CIP capacity benchmark.

<a id="s05"></a>
### S05. Streamlit: Authentication and user information

[Official source](https://docs.streamlit.io/develop/concepts/connections/authentication)

**Used for:** OIDC login support; authentication is distinct from application authorization.

<a id="s06"></a>
### S06. TypeScript: TypeScript for the New Programmer

[Official source](https://www.typescriptlang.org/docs/handbook/typescript-from-scratch.html)

**Used for:** TypeScript adds static checks and produces JavaScript; it is not a separate faster browser runtime.

<a id="s07"></a>
### S07. Vite: Deploying a static site

[Official source](https://vite.dev/guide/static-deploy.html)

**Used for:** Build/deployment model for static frontend assets; preview is not a production server.

<a id="s08"></a>
### S08. FastAPI: Concurrency and async / await

[Official source](https://fastapi.tiangolo.com/async/)

**Used for:** Synchronous versus asynchronous handlers and I/O; async syntax does not remove blocking work.

<a id="s09"></a>
### S09. FastAPI: Deployment concepts

[Official source](https://fastapi.tiangolo.com/deployment/concepts/)

**Used for:** Replication, process memory, startup, restarts and deployment tradeoffs.

<a id="s10"></a>
### S10. Node.js: Do not block the event loop

[Official source](https://nodejs.org/learn/asynchronous-work/dont-block-the-event-loop)

**Used for:** Long-running computation can harm event-loop responsiveness; Node is not immune to heavy request work.

<a id="s11"></a>
### S11. Fastify: Validation and serialization

[Official source](https://fastify.dev/docs/latest/Reference/Validation-and-Serialization.md)

**Used for:** Schema-based validation/serialization capabilities. This is not a matched CIP benchmark.

<a id="s12"></a>
### S12. Next.js: Static exports

[Official source](https://nextjs.org/docs/app/guides/static-exports.md)

**Used for:** Next.js can export static assets; dynamic server features have different deployment requirements.

<a id="s13"></a>
### S13. Django 5.2: Asynchronous support

[Official source](https://docs.djangoproject.com/en/5.2/topics/async/)

**Used for:** ASGI and sync/async integration considerations; version-specific documentation, not a declaration of the latest release.

<a id="s14"></a>
### S14. Plotly Dash: Performance

[Official source](https://dash.plotly.com/performance.md)

**Used for:** Caching and callback-related optimization options; Dash is not fairly represented as having no browser-side optimization.

<a id="s15"></a>
### S15. Vue: Performance

[Official source](https://vuejs.org/guide/best-practices/performance)

**Used for:** Architecture, bundles and rendering strategies relevant to a credible React alternative.

<a id="s16"></a>
### S16. Svelte: Overview

[Official source](https://svelte.dev/docs/svelte/overview)

**Used for:** Compiler-based UI model. It does not establish which framework is fastest for CIP.

<a id="s17"></a>
### S17. React: lazy

[Official source](https://react.dev/reference/react/lazy)

**Used for:** On-demand component-code loading for route/chart splitting.

<a id="s18"></a>
### S18. TanStack Query: Important defaults

[Official source](https://tanstack.com/query/latest/docs/framework/react/guides/important-defaults)

**Used for:** Freshness, refetch and cache defaults should be intentionally configured.

<a id="s19"></a>
### S19. TanStack Table: Virtualization guide

[Official source](https://tanstack.com/table/latest/docs/framework/react/guide/virtualization.md)

**Used for:** Virtualization integration; rendering fewer rows does not itself implement server pagination.

<a id="s20"></a>
### S20. AG Grid: Community and Enterprise

[Official source](https://www.ag-grid.com/javascript-data-grid/community-vs-enterprise.md)

**Used for:** Feature/edition distinctions relevant to grid licensing decisions.

<a id="s21"></a>
### S21. AG Grid: Excel export

[Official source](https://www.ag-grid.com/javascript-data-grid/excel-export.md)

**Used for:** Excel-export edition requirements; verify the complete proposed component license.

<a id="s22"></a>
### S22. Apache ECharts

[Official source](https://echarts.apache.org/en/index.html)

**Used for:** Official charting-project reference for the proposed visualization layer.

<a id="s23"></a>
### S23. MySQL 8.4: EXPLAIN

[Official source](https://dev.mysql.com/doc/refman/8.4/en/explain.html)

**Used for:** Query-plan inspection and EXPLAIN ANALYZE. Validate actual deployed database version and safe execution context.

<a id="s24"></a>
### S24. SQLAlchemy 2.0: Connection pooling

[Official source](https://docs.sqlalchemy.org/en/20/core/pooling.html)

**Used for:** Pool sizing, overflow, disconnect and multiprocessing considerations.

<a id="s25"></a>
### S25. SQLAlchemy 2.0: MySQL dialects

[Official source](https://docs.sqlalchemy.org/en/20/dialects/mysql.html)

**Used for:** Driver choices, including synchronous and asynchronous integrations.

<a id="s26"></a>
### S26. PyMySQL: Connections

[Official source](https://pymysql.readthedocs.io/en/latest/modules/connections.html)

**Used for:** TLS-related connection options. Inspect actual negotiated behavior before declaring deployment security.

<a id="s27"></a>
### S27. OWASP: Authorization Cheat Sheet

[Official source](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html)

**Used for:** Default-deny, per-request authorization and access-control design.

<a id="s28"></a>
### S28. OWASP: Session Management Cheat Sheet

[Official source](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)

**Used for:** Session lifecycle, cookies and protective attributes.

<a id="s29"></a>
### S29. Microsoft: Azure App Service plans

[Official source](https://learn.microsoft.com/en-us/azure/app-service/overview-hosting-plans)

**Used for:** Apps and slots can share plan resources; do not assume each app receives a dedicated allocation.

<a id="s30"></a>
### S30. Microsoft Azure Architecture Center: Background jobs

[Official source](https://learn.microsoft.com/en-us/azure/architecture/best-practices/background-jobs)

**Used for:** Background workload contention, execution and reliability design.

<a id="s31"></a>
### S31. Microsoft Azure: Pricing calculator

[Official source](https://azure.microsoft.com/en-us/pricing/calculator/)

**Used for:** Use actual region/SKU/service details to estimate cost; no Azure price was inferred from RAM.

<a id="s32"></a>
### S32. web.dev: Interaction to Next Paint

[Official source](https://web.dev/articles/inp)

**Used for:** INP meaning and the 200 ms good threshold at field p75; not a complete network-result latency metric.

<a id="s33"></a>
### S33. TechEmpower: Web Framework Benchmarks

[Official source](https://www.techempower.com/benchmarks/)

**Used for:** Controlled server benchmarks. Their workloads/hardware differ from CIP UI and Azure/MySQL.

<a id="s34"></a>
### S34. Microsoft: ASP.NET Core performance best practices

[Official source](https://learn.microsoft.com/en-us/aspnet/core/fundamentals/best-practices?view=aspnetcore-10.0)

**Used for:** Asynchronous work, pagination and allocation practices for a credible backend alternative.

<a id="s35"></a>
### S35. Go: Diagnostics

[Official source](https://go.dev/doc/diagnostics)

**Used for:** Official profiling/diagnostics guidance; proposed language migrations should be profile-driven.

<a id="s36"></a>
### S36. Zoho Analytics: Embedded analytics

[Official source](https://www.zoho.com/analytics/embedded-solutions.html)

**Used for:** Vendor capabilities for embedding, identity integration and branding. Marketing cost-savings claims were not adopted as independent evidence.

<a id="s37"></a>
### S37. Zoho Analytics: Pricing

[Official source](https://www.zoho.com/analytics/pricing.html)

**Used for:** Procure the applicable embedded offering; a generic dashboard price is not a CIP external-user quote.

<a id="s38"></a>
### S38. Appsmith: Infrastructure and capacity planning

[Official source](https://docs.appsmith.com/getting-started/setup/infrastructure-sizing)

**Used for:** Current 2-vCPU/8-GB starting guidance, deployment dependencies and explicit capacity caveats.

<a id="s39"></a>
### S39. ToolJet: System requirements

[Official source](https://docs.tooljet.com/docs/setup/system-requirements/)

**Used for:** App-VM requirements and separate PostgreSQL/Redis guidance; do not omit supporting services.

<a id="s40"></a>
### S40. Metabase: License

[Official source](https://www.metabase.com/license)

**Used for:** Open-source, embedding and commercial license distinctions. Obtain appropriate procurement review.

<a id="s41"></a>
### S41. Metabase: Is Metabase embedding free?

[Official source](https://www.metabase.com/articles/is-metabase-embedding-free)

**Used for:** Guest-embedding versus fuller paid capabilities. Conditions must match the intended customer product.

<a id="s42"></a>
### S42. Microsoft: Power BI embedded capacity

[Official source](https://learn.microsoft.com/en-us/power-bi/developer/embedded/embedded-capacity)

**Used for:** Production embedded capacity requirements; no fixed capacity-price assumption was made.

<a id="s43"></a>
### S43. Retool: Pricing

[Official source](https://retool.com/pricing)

**Used for:** Verify feature/deployment/external-user terms against the intended usage.

<a id="s44"></a>
### S44. Apache Superset: Embedded SDK

[Official source](https://apache.googlesource.com/superset/%2B/refs/heads/master/superset-embedded-sdk/README.md)

**Used for:** Server-issued guest-token embedding and row-level rules. Application policy still requires careful configuration.

<a id="s45"></a>
### S45. Zoho: Our story

[Official source](https://www.zoho.com/ourstory.html)

**Used for:** India-origin context for the national/international procurement shortlist; not a data-residency guarantee.

<a id="s46"></a>
### S46. Spring Boot: Introducing GraalVM native images

[Official source](https://docs.spring.io/spring-boot/reference/packaging/native-image/introducing-graalvm-native-images.html)

**Used for:** Native-image capabilities and constraints; blanket Java-memory stereotypes are not a sound architecture decision.

<a id="s47"></a>
### S47. Laravel: Octane documentation

[Official source](https://laravel.com/framework/docs/master/octane.md)

**Used for:** Long-lived worker performance and state/memory considerations. Master documentation is not a recommendation to deploy a development branch.

<a id="s48"></a>
### S48. Streamlit: Client-server architecture

[Official source](https://docs.streamlit.io/develop/concepts/architecture/architecture)

**Used for:** Browser/server sessions and deployment architecture. Do not infer pinned-version internal server implementations from live docs.

<a id="s49"></a>
### S49. web.dev: Largest Contentful Paint

[Official source](https://web.dev/articles/lcp)

**Used for:** LCP definition and good-performance threshold; distinct from API latency.

<a id="s50"></a>
### S50. W3C: Web Content Accessibility Guidelines 2.2

[Official source](https://www.w3.org/TR/WCAG22/)

**Used for:** Source for the proposed WCAG 2.2 AA design/testing target; this report does not certify compliance.

<a id="s51"></a>
### S51. Flask: Using async and await

[Official source](https://flask.palletsprojects.com/en/stable/async-await/)

**Used for:** Async integration and worker-model limitations; alternative framework capability reference.

