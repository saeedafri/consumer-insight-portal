# 03. Technology and marketplace comparison

[Package index](README.md) | [Source register](08-sources.md)

## 1. Compare the right layers

Node.js is a runtime. Python, JavaScript and TypeScript are languages, with TypeScript transpiled to JavaScript. Streamlit, FastAPI, Django and Fastify are frameworks serving different roles. React, Vue and Svelte are browser UI technologies. MySQL is the database. Comparing them in a single "fastest language" chart would conceal the architecture rather than evaluate it. [S06](08-sources.md#s06).

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

Capability references: FastAPI [S08-S09](08-sources.md#s08); Fastify [S11](08-sources.md#s11); Vue [S15](08-sources.md#s15); Svelte [S16](08-sources.md#s16); Next.js [S12](08-sources.md#s12); Django [S13](08-sources.md#s13); Flask [S51](08-sources.md#s51); Dash [S14](08-sources.md#s14); ASP.NET [S34](08-sources.md#s34); Go diagnostics [S35](08-sources.md#s35); Spring native images [S46](08-sources.md#s46); Laravel Octane [S47](08-sources.md#s47).

## 3. Streamlit: the strongest fair case for and against it

### Adopt or retain it when

The application is mainly internal research; a small Python team needs to change analyses quickly; the standard widgets fit the workflow; and measured peak concurrency is comfortably within the resource envelope. Its existing role in the organization is a real asset: researchers can use their current language and domain functions.

A serious optimized baseline should use the existing aggregate-first SQL path, forms to group filter changes, fragments where supported, bounded small-result caches, suitable navigation, pagination and external jobs. It should use real identity and authorization, not a shared passphrase.

### Do not make it the default here when

The core product requirements are a persistent commercial application shell, independently updating panels, rich interactive state, multiple product modules, subscription-aware discovery, external integrations and a long-lived public API. A client application plus explicit service boundary is the preferred engineering shape for those requirements.

### Claims to reject

"Streamlit cannot scale," "it cannot authenticate users," "it has no partial reruns," and "each user always gets a complete permanent copy of every table" are not supported general claims. Its documented architecture, caching, fragments and OIDC features are more nuanced. On the other hand, replacing every `cache_data` call with `cache_resource` is not a safe universal memory fix: shared mutable resources require thread safety and strict access scoping. [S03](08-sources.md#s03), [S04](08-sources.md#s04), [S05](08-sources.md#s05), [S48](08-sources.md#s48).

## 4. Why React is a recommendation, not a speed trophy

The decision favors a reusable typed client product, not a brand of virtual DOM. Vue and Svelte can implement the same successful architecture. Choose the UI framework the team can maintain well, and make the data contract independent of that choice.

Use lazy loading for secondary routes and heavy chart modules. Configure browser-query freshness and retry behavior explicitly. A virtualized table reduces rendered rows; it does not reduce SQL work or the downloaded dataset unless server-side pagination is also implemented. React supports lazy component loading, and TanStack documents these query and table concerns separately. [S17](08-sources.md#s17), [S18](08-sources.md#s18), [S19](08-sources.md#s19).

No measured evidence here supports a statement such as "React is 30% faster than Vue for CIP." A poorly designed React screen can ship too much code, trigger request waterfalls or rerender expensive charts and perform worse than a carefully bounded alternative.

## 5. Indian and international marketplace options

The relevant buy/build choice is not a country's programming language. It is control over the product versus delivery speed, licensing, operational footprint, data governance and the team's ability to maintain it. Zoho is a concrete India-origin vendor in this shortlist; Appsmith and ToolJet are also relevant options for an India-based procurement/delivery team. No current legal domicile, data residency or support promise is inferred from a company's origin. [S45](08-sources.md#s45).

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

Official sources: Zoho [S36](08-sources.md#s36), [S37](08-sources.md#s37); Appsmith [S38](08-sources.md#s38); ToolJet [S39](08-sources.md#s39); Metabase [S40](08-sources.md#s40), [S41](08-sources.md#s41); Microsoft [S42](08-sources.md#s42); Superset [S44](08-sources.md#s44); Retool [S43](08-sources.md#s43).

**Important sizing distinction:** Appsmith's published starting point is above the entire stated staging allowance. ToolJet's current database guidance separately lists 8 GB for PostgreSQL plus Redis memory; that is not a claim that every deployment always consumes this much, but it invalidates the assumption that its complete documented stack fits inside a 4.5 GB shared host. Managed/cloud deployment can move the resource demand elsewhere, at a different cost and trust boundary.

For embedding, validate data isolation with two real test tenants, not just a successful dashboard screenshot. Ask each vendor for written terms covering external viewers, active users versus named users, tenant/workspace counts, SSO, white-labeling, exports, development environments, usage overages and exit/export rights. Evaluate region availability and residency contractually; an Indian vendor does not automatically mean every selected service stores data in India.

## 6. Licensing choices that can quietly change the budget

Do not assume that every advanced data-grid feature is included in a free edition. AG Grid distinguishes community and enterprise features, and its Excel export is an enterprise feature. A customer-facing pivoting experience may need a paid component or a custom implementation. [S20](08-sources.md#s20), [S21](08-sources.md#s21).

Start with a deliberately limited table contract: bounded columns, sorting, pagination, selection, accessible navigation and server-generated authorized exports. Evaluate the total implementation cost before choosing between a headless table, a community grid and a commercial grid. Server export generation is not automatically cheaper once research formatting and maintenance are included.

## 7. Choices not justified at launch

**Kubernetes/microservices everywhere:** a single modest host provides neither meaningful service isolation nor high availability merely because more processes are deployed. Prefer a modular API and a bounded job worker.

**An immediate database replacement:** the code already has MySQL aggregates. A second analytics engine should be justified by measured query patterns, data volume or workload isolation needs, not the claim that MySQL can never power analytics.

**A compulsory distributed cache:** first establish cache value, object sizes and hit rate. An additional service costs memory and operations. Versioned process-local caches can be adequate initially, acknowledging duplication and consistency limitations.

**Mandatory SSR for private dashboards:** Next.js can also export static content. The rejected default is unnecessary dynamic rendering complexity, not the framework itself. [S12](08-sources.md#s12).

**A complete Rust/Go/Java migration to chase a framework leaderboard:** server microbenchmarks measure specific handlers, not survey correctness, a user's network, chart rendering or subscription workflows. Use them to generate candidates, not to promise CIP speed. [S33](08-sources.md#s33).

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
