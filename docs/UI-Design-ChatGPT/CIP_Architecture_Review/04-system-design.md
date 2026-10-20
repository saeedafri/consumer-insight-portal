# 04. Proposed system design

[Package index](README.md) | [Source register](08-sources.md)

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

Generate TypeScript API types from a reviewed schema, but also validate inputs on the server. Compile-time types do not make an untrusted HTTP request safe. Fastify has a comparable schema-validation approach if that backend is selected. [S06](08-sources.md#s06), [S11](08-sources.md#s11).

## 4. Request and query lifecycle

An ordinary analysis request follows this sequence:

1. Resolve the authenticated principal and applicable tenant/product permissions.
2. Validate the allowed metric, dimensions, filters, requested version and result-size limits.
3. Resolve one published dataset version and a compatible metric-definition version.
4. Build a canonical access-scoped cache key; return a cached authorized response when valid.
5. Execute a bounded query against aggregate cells, or an explicitly approved bounded fallback.
6. Return a compact typed response with provenance, base, weighting and version metadata.
7. Record timing, query class, cache outcome and request ID without logging sensitive response content.

The browser does not connect to MySQL and never receives a database credential. A hidden button is not authorization. Every direct endpoint, export download and saved-view operation must enforce the same policy. [S27](08-sources.md#s27).

### Query execution rules

Prefer SQL aggregation and small result objects. Do not construct a pandas dataframe simply to serialize 40 database rows. Preserve pandas where it is useful for research transformations and exports in the worker.

The current PyMySQL path is synchronous. An initial FastAPI implementation may use synchronous endpoints and a bounded execution pool. Alternatively, use a supported asynchronous MySQL dialect intentionally. Merely adding `async def` around a blocking database function does not make it asynchronous. Do not share a mutable ORM session across concurrent requests. [S08](08-sources.md#s08), [S25](08-sources.md#s25).

Create indexes from representative query plans: published dataset/version, survey/question/concept, cohort and breakdown dimensions. Index order and covering choices depend on selectivity and actual access patterns; no specific composite index is declared universally optimal from source inspection alone. Bound wave counts, dimensions, top-N categories and page sizes at the API. Expensive custom cohorts should be rejected with an explanation or moved to a job rather than silently using an unbounded fallback. [S23](08-sources.md#s23).

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

The API sets a Secure, HttpOnly session cookie, uses CSRF protection for state-changing requests and validates the session according to a documented revocation policy. Tokens and signing material stay out of frontend bundles, source archives and routine logs. Define whether transient identity-store failure rejects requests or serves a narrowly scoped last-known state; do not leave an accidental fail-open branch. [S28](08-sources.md#s28).

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

Run one heavy ETL/export task at a time until peak memory and CPU measurements justify more. Enforce per-user and global queue limits so one subscriber cannot exhaust the host. Small priority interactive work must not be blocked behind a long export. Azure's background-job guidance highlights contention and the need for reliable execution patterns. [S30](08-sources.md#s30).

Use the existing database for a modest initial durable queue only when database load and operational requirements permit. Azure Storage Queue is a sensible next option when already available; avoid deploying a full broker stack merely for the first export feature. In-process request background tasks are not the durability boundary.

Store completed exports privately in object storage with expiry and cleanup. Recheck permissions on download; do not disclose predictable public object URLs. Spreadsheet/CSV export should neutralize formula-like untrusted text, apply approved disclosure/suppression rules and record the exact data version.

## 10. Deployment, recovery and scaling

A VM deployment may serve static assets and proxy the API through the existing web server, with separate controlled API/worker services. An App Service deployment must use the plan's supported runtime, process and job arrangements. Build frontend assets in CI, not on the memory-constrained production host. Vite's preview server is not the production hosting strategy. [S07](08-sources.md#s07).

**Do not infer that the host is an Azure VM, a particular App Service SKU or a given vCPU count from the supplied RAM figures.** Apps and deployment slots on an App Service plan can share the plan's resources; confirm placement before calculating capacity. [S29](08-sources.md#s29).

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
