# 05. Performance evidence and qualification plan

[Package index](README.md) | [Source register](08-sources.md)

## 1. What "milliseconds" must mean

Distinguish three outcomes: a control reacts visually; an API completes; the user sees correct new results. A fast spinner is not a fast analysis. The browser's INP metric evaluates responsiveness to the next paint, not the completion of every later network result. Its documented good threshold is 200 ms or less at the 75th percentile of field page views. [S32](08-sources.md#s32).

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

The uploaded benchmark API serves a smaller UI than the Streamlit alternative. The timing script waits for a text marker, not complete chart/table readiness, and polls at 100 ms. Accumulating tab counts also differ from the size of the newest load batch. These details prevent treating the report's ratios as a controlled measure of framework overhead. See E12 in [the code audit](02-code-audit.md).

Do not use API requests per second as a substitute for interactive users. Do not use TechEmpower's controlled server tests as a UI or Azure/MySQL forecast. Those results answer their defined benchmark questions; CIP must answer its own. [S33](08-sources.md#s33).

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

INP and LCP reference thresholds come from web.dev; the API, click-to-result and error targets are proposed CIP policy. [S32](08-sources.md#s32), [S49](08-sources.md#s49).

Do not sum p95 values from separate components and call the sum an exact end-to-end p95. Measure the actual journey distribution. Track p99 and worst-case examples as well; an attractive median can conceal a painful tail.

## 6. Browser implementation budget

Prioritize operations that do not need the server: opening navigation, expanding filters, switching chart presentation of already-authorized small results and reordering a small loaded view. Use server requests for filtering or sorting the full dataset; sorting only one page must not pretend to sort all results.

A starting payload policy is a typical compact response of roughly 100-250 KB compressed or less, with explicit exceptions and separate exports. This is a proposed budget, not an observed CIP size. Limit chart points, page rows and rendered columns; enforce these limits server-side. Lazy-load expensive chart/editor modules, avoid repeated full chart recreation, and cancel or ignore obsolete requests when a user changes filters rapidly.

For text search, a proposed 150-250 ms debounce can reduce redundant requests; display typing immediately. An explicit Apply action suits multi-filter analyses and avoids recomputing after each partial selection. TanStack Query defaults require intentional freshness configuration, while virtualization is distinct from database pagination. [S17](08-sources.md#s17), [S18](08-sources.md#s18), [S19](08-sources.md#s19).

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
