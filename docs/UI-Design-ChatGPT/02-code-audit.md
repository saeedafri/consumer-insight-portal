# 02. Source audit and evidence ledger

[Package index](README.md) | [Source register](08-sources.md)

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

Unknown `APP_ENV` values currently fall back to `LOCAL`. Replace this with explicit validation and startup failure. Ensure debug/development bypasses cannot activate in a deployed environment through an unexpected value. Explicitly require verified database TLS in deployed environments; inspect actual driver settings and negotiated behavior rather than assume an empty SSL dictionary proves either secure or insecure transport. [S26](08-sources.md#s26).

### 4.2 Existing-session validation can fail open

The exact `_session_is_live` function returned `True` in the bounded offline probe when the fake session store raised an exception and when it returned no session row. It returned `False` for revoked and expired rows. This behavior matches the inspected source.

The scope matters: `_load_session`, used when recovering identity from a cookie, returns no user on database failure or a missing row. Therefore the evidence supports **continued validity of an already-held in-memory session**, not a demonstrated unauthenticated login bypass. Existing-session revocation and availability policy should be explicit rather than accidentally delegated to exception handling.

For production, use a tested server-side session implementation with server-set Secure, HttpOnly cookies, appropriate SameSite behavior, CSRF protection for state changes and bounded session lifetimes. The current client-side CookieController path does not provide a server-set HttpOnly cookie boundary. [S28](08-sources.md#s28).

### 4.3 Authentication is not finished authorization

The local shared-passphrase/email-allowlist path does not independently prove ownership of the entered email. The OIDC helper says it expects claims verified elsewhere; an authorization URL alone is not a completed OIDC integration.

Even a completed login does not establish a paid subscription, ownership of an export or permission to change concept mappings. Add server-side policies for product access, dataset scope, saved views, publications, exports and administrative writes. Avoid relying on hidden navigation items. The framework's own OIDC support does not supply all these business permissions. [S05](08-sources.md#s05), [S27](08-sources.md#s27).

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

The positive finding is that standard `analyse` requests already have an aggregate-first path. Preserve it and measure indexes with MySQL `EXPLAIN`, and where appropriate `EXPLAIN ANALYZE` on safe representative reads. `EXPLAIN ANALYZE` executes the query; it is not a harmless metadata-only action on a live overloaded system. [S23](08-sources.md#s23).

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

The code has no `st.fragment` calls. A fair optimized-Streamlit baseline should evaluate forms/fragments, bounded caches and navigation changes before claiming unavoidable slow interactions. Verify features against the pinned Streamlit release; live documentation may include later additions. [S03](08-sources.md#s03), [S04](08-sources.md#s04).

The configured `pool_size=10` and `max_overflow=20` allow up to 30 connections **per engine per process**, not 30 for the entire organization. Multiple products, roles, workers and job processes multiply the ceiling. Pools allocate according to use, so this is potential demand, not an observed open-connection count. [S24](08-sources.md#s24).

## 7. Why the existing speed claims are not decision-grade

The included architecture documents report impressive synthetic improvements. The supplied scripts do not establish a matched comparison of complete CIP experiences:

- The FastAPI page renders a heading and plain table. The Streamlit SQL page includes a selector, metric, bar chart and dataframe. That is not the same UI workload.
- The browser script checks for a text marker, at 100 ms polling intervals, rather than verifying that the chart, table and controls are fully ready.
- Load steps add tabs without closing previous tabs. Steps 1, 5, 10 and 20 therefore leave 36 total open sessions at the end; the newest batch is not the whole session population.
- The experiment uses local SQLite and a macOS memory utility. Its ratios cannot be asserted to hold on Azure/MySQL or across different CPUs without measurement.
- Product authentication, entitlements, mixed query patterns, ETL overlap and realistic exports are not established by this synthetic page.

The reported historical throughput and "300 active users" calculations must therefore remain unverified claims, not CIP capacity commitments. TechEmpower results are similarly useful as server-test evidence, not a substitute for the application's own UI and database workload. [S33](08-sources.md#s33).

## 8. Validation actually performed

**Performed:** safe extraction; source inventory; AST parsing; selected source inspection; isolated session-function probes; mathematical cohort-signature counterexample; five-repeat synthetic data-path experiment with equivalent outputs.

**Attempted but unsuccessful:** full pytest collection. Dependencies including Streamlit, PyMySQL and tenacity were unavailable, and dependency installation was blocked by the environment's package-network resolution. Collection ended with 10 import errors. The supplied `.env` was not loaded into that test run; a sanitized copy and network-blocking guard were used.

**Not performed:** running all application pages, browser timing of CIP, validating SSO against the real provider, authenticating to MySQL/Forsta, testing Azure, measuring all live datasets or load-testing SIP/MIP. The local data-path test used pandas 2.2.3, below the repository's declared minimum, and is not a compatibility qualification.

## 9. Remediation priority

**Before any subscriber exposure:** rotate exposed credentials; remove development authentication/bypasses from deployment; finish OIDC; enforce permissions; fix session-store policy; separate database roles and enforce environment/TLS validation.

**Before performance approval:** bound whole-wave detail reads and exports; establish dataset-version publication; fix cohort invalidation; move maintenance work out of requests; measure cache and connection ceilings; qualify the real deployment.

**Before broad migration:** create pure Python domain/repository boundaries, reproducible locked environments and working MySQL integration tests. Retain the parts that are already correct rather than buying risk through a wholesale language translation.
