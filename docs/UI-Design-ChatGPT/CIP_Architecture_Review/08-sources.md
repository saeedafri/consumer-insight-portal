# 08. Primary source register

[Package index](README.md)

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

