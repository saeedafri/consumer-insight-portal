# STRESS TEST RESULTS: CIP serving design on Azure staging

**Run:** 20 Oct 2026, 14:41–15:01 IST, by Claude.

**Target:** the Azure staging MySQL that holds `cip_stg`: `csr-mysql8-flex-stg`, MySQL 8.0.46, **Burstable B2s, 2 vCPU / 4 GB**, 2 GB buffer pool, `max_connections` 341.

**Data:** the full warehouse, plus the new serving layer built by the ETL. 320 waves, 1,901,023 `srv_result` rows (357 MB data + 126 MB indexes).

**Raw output:** reproduced in §10. Every test can be re-run (§9).

## The answer in one table

| Question | Answer |
|---|---|
| **Which approach is best?** | **Serving table + result cache.**<br>• The ETL writes finished rows (`srv_result`).<br>• The backend reads one primary-key range per widget and caches it until the next wave. |
| **How fast is the database for one widget?** | **0.03–0.04 ms** (serving), against 0.10–0.15 ms (cube with joins) and **20–312 ms** (raw answers). Measured inside MySQL. |
| **How much can the database take?** | About **4,700 widget reads per second** with no cache at all, on this small 2-vCPU burstable server. Raw answers saturate at **29 per second**. |
| **How fast is the whole request with the cache?** | **p50 0.3 ms, p99 0.4 ms** at 2,500 req/s sustained for 5 min (750,000 requests, 0 errors). At 8,000 req/s: p99 49 ms. |
| **Does memory grow?** | No: **240 MB** for the API before, during and after 750,000 requests |
| **How many users?** | **Staging ≈ 8,500 people using it at the same time. Production ≈ 17,000.** That is about 85,000 / 170,000 registered customers if 10 % are online at peak. The limit is API CPU. The database could carry about 23,000 active users even with no cache. |
| **Two filters combined** (Gen Z × female)? | **0.7–1.3 ms** inside MySQL from a per-respondent serving table, about 1,000–1,900 uncached reads/s. Raw answers: 4–34 ms, 40–220/s. But 92 % of two-cut cells have under 50 respondents in one wave, so the UI must flag them or pool weeks ([§11](#11-two-cuts-combined-eg-gen-z--female)). |

## 1. The three approaches tested

The same screen widget each time: *holiday-shopping status (XM3) by generation, wave 412* (15 numbers).

| Approach | What happens per request |
|---|---|
| **A. Raw** (the "MySQL + Streamlit, just show it" habit) | Aggregate the 23 M-row answer table: 5 joins + GROUP BY |
| **B. Cube** | Read the pre-aggregated cube (`cip_agg_cell`); join question and option; compute % at request time. No prior-week / last-year comparison (that would need two more joins). |
| **C. Serving (chosen)** | Read `srv_result` by primary key `(survey_id, qcode, dim)`. Labels, %, comparisons and flags are already there. |

## 2. Database execution time, measured inside MySQL (`EXPLAIN ANALYZE`, 4 runs)

| Approach | Server time per query | Plan |
|---|--:|---|
| **C. Serving** | **0.04 · 0.12 · 0.03 · 0.04 ms** | `Index lookup on srv_result using PRIMARY`, 15 rows |
| B. Cube | 0.11 · 0.10 · 0.10 · 0.15 ms | Nested loop, 3 tables |
| A. Raw | **312 · 139 · 20 · 80 ms** | Temporary table + GROUP BY over the answer table |

The serving read is **3× faster than the cube and 500–8,000× faster than raw**. It also returns the comparisons and flags, which the other two don't.

## 3. Database capacity with no cache (queries run inside MySQL, no network)

Each session loops the query thousands of times inside a temporary stored procedure, which was dropped afterwards. This shows what the database alone can do.

| Approach | 1 session | 2 | 4 | 8 | 16 |
|---|--:|--:|--:|--:|--:|
| **C. Serving** | 917/s | 1,361/s | 2,493/s | 3,237/s | **4,733/s** |
| B. Cube | 333/s | 478/s | **781/s** | — | — |
| A. Raw | 17/s | 24/s | **29/s** | — | — |

The loop adds stored-procedure overhead, so these are conservative: serving costs about 1 ms per call here against 0.04 ms in §2.

**Ceiling on this small server:**

| Approach | Ceiling | Compared with serving |
|---|--:|---|
| Serving | **≥ 4,700 widget reads/s** | — |
| Cube | about 800/s | 6× less |
| Raw | about 30/s | **160× less** |

## 4. Many users at once, from outside Azure (64–128 parallel connections over the VPN)

| Approach | Connections | Queries/s | p50 | p95 | p99 |
|---|--:|--:|--:|--:|--:|
| C. Serving | 1 → 128 | 3 → **406** | 279 → 285 ms | 352 → 319 ms | 358 → 362 ms |
| B. Cube | 1 → 128 | 3 → 423 | 285 → 290 ms | 345 → 352 ms | 390 → 405 ms |
| A. Raw | 1 → 128 | 3 → **103** (saturated) | 349 → **1,102 ms** | 466 → **2,164 ms** | 518 → **2,699 ms** |

Every request pays the **274 ms VPN round trip** (`SELECT 1` = 274.5 ms), so absolute times are network.

**What matters is the shape:**
- Serving and cube stay **flat**: the database is idle.
- Raw **saturates the database at about 100 queries/s**, and latency triples, then quadruples.

That is the "it gets slow when more people use it" problem, measured.

## 5. The full request: API → Azure MySQL

The widget used here: XM1 + XM2 + XM3 × total + generation, which is 164 finished rows, 2.2 KB gzipped.

| Mode | Rate | p50 | p95 | p99 | Errors |
|---|--:|--:|--:|--:|--:|
| Cache **off** (every request queries Azure) | 25/s | 291 ms | 2,728 ms* | 2,856 ms | 0 |
| | 50/s | 277 ms | 726 ms | 2,744 ms | 0 |
| | 100/s | 1,240 ms | 1,791 ms | 2,622 ms | 0 |
| | 150/s → achieved 116/s | 3,094 ms | 4,229 ms | 4,339 ms | 0 |
| **Cache on** (the design) | 1,000/s | **0.7 ms** | 0.9 ms | 2.8 ms | 0 |
| | 2,500/s | **0.3 ms** | 0.4 ms | 0.4 ms | 0 |
| | 5,000/s | **0.6 ms** | 0.8 ms | 3.3 ms | 0 |

\* The first requests also open the TLS connections to Azure.

**Cache off** is limited by the laptop: 2 workers × 30 pooled connections × the 274 ms VPN round trip. It is **not** limited by the database (§3 shows about 4,700/s is available). With the API in Azure next to the database (round trip about 1 ms), the uncached path is bounded by the database's ~4,700/s instead.

## 6. Soak and spike: does it stay fast and stable? (cache on, 2 workers)

| Phase | Requests | p50 | p95 | p99 | max | Errors | API memory |
|---|--:|--:|--:|--:|--:|--:|--:|
| Before | — | — | — | — | — | — | 240 MB |
| **Soak: 2,500/s for 5 minutes** | **750,000** | **0.3 ms** | **0.4 ms** | **0.4 ms** | 237 ms | **0** | **240 MB** |
| **Spike: 8,000/s for 15 s** | 120,000 | 12.3 ms | 21.9 ms | 49.0 ms | 64 ms | **0** | 240 MB |
| Recovery: 1,000/s right after | 15,000 | 0.7 ms | 0.8 ms | 1.6 ms | 4.5 ms | 0 | 240 MB |

**CPU during the soak:** 133.9 CPU-seconds for 750,000 requests, which is **178 µs per request**.

**Memory did not move.** There is no leak and no per-user state.

## 7. How many users: the arithmetic

| Step | Staging (≈ 4.9 GB, 1 vCPU assumed) | Production (≈ 9.88 GB, 2 vCPU assumed) |
|---|--:|--:|
| API CPU per request, measured (laptop M4) | 178–205 µs | 178–205 µs |
| Same on an Azure vCPU (assumed 3× slower) | ≈ 600 µs | ≈ 600 µs |
| Saturation per vCPU | ≈ 1,700 req/s | ≈ 1,700 req/s |
| **Planned at ≤ 50 % CPU** | **≈ 860 req/s** | **≈ 1,750 req/s** |
| Requests per active user (one screen ≈ 5 API calls/min; everything else in the browser) | 0.1 req/s | 0.1 req/s |
| **People using it at the same time** | **≈ 8,600** | **≈ 17,500** |
| Registered customers (10 % online at peak) | ≈ 86,000 | ≈ 175,000 |
| API memory | 137 MB (1 worker) | 240–253 MB (2 workers) |
| Database load at that traffic, cache hit ≥ 95 % | ≈ 40 queries/s (1 % of its 4,700/s) | ≈ 90 queries/s (2 %) |
| Database load if the cache were **off** | 860/s (18 %) | 1,750/s (37 %) |

**Even if Azure is 5× slower than the laptop** (not 3×): about 5,000 active users on staging and 10,000 on production.

**With the raw approach**, the database alone would cap the whole system at about 30 widget reads/s, i.e. **about 300 active users**, with 1–2-second waits ([§3](#3-database-capacity-with-no-cache-queries-run-inside-mysql-no-network), [§4](#4-many-users-at-once-from-outside-azure-64128-parallel-connections-over-the-vpn)).

## 8. Honest limits

| Limit | Effect | What closes it |
|---|---|---|
| **The API ran on the dev Mac, not on Azure.** CIP has no Azure App Service yet; the Azure export lists only SIP's and MIP's. | API CPU numbers are from an M4, scaled by an assumed 3×. End-to-end numbers include the 274 ms VPN. | IT provisions the CIP App Service. Then re-run `rate_test.py` and `db_stress.py` from inside Azure ([§9](#9-re-run)). |
| **The staging DB was not idle.** A DBeaver session ran an `ALTER TABLE` on `coreiq_av_ear…` (another project) for about 90 min during the tests. | Database numbers are, if anything, pessimistic | Re-run when it's quiet |
| **Burstable B2s** | Sustained load spends CPU credits; production should be General Purpose ([06 §9](06-system-design.md)) | IT database tier |
| The load generator shared the laptop with the API | Slightly pessimistic at the highest rates | Separate machine on Azure |
| No `performance_schema` access | Server timing came from `EXPLAIN ANALYZE` and in-server loops instead | — |

## 9. Re-run

```bash
# database: execution time and capacity per approach (read-only except the temporary benchmark procedures)
PYTHONPATH=. .venv/bin/python scripts/ui_benchmark/db_stress.py --survey 412 --levels 1,16,64,128 --seconds 20
# two cuts combined: builds two prototype tables for one wave in cip_stg, measures, drops them
PYTHONPATH=. .venv/bin/python scripts/ui_benchmark/two_cut.py --survey 412
# API: start it (cache on / off), then drive it at fixed arrival rates
APP_ENV=LOCAL CIP_SESSION_SECRET=<random> .venv/bin/gunicorn api.main:app -k uvicorn.workers.UvicornWorker -w 2 -b 127.0.0.1:8000
APP_ENV=LOCAL CIP_SESSION_SECRET=<random> CIP_RESULT_CACHE=0 .venv/bin/gunicorn api.main:app -k uvicorn.workers.UvicornWorker -w 2 -b 127.0.0.1:8002
COOKIE=$(APP_ENV=LOCAL CIP_SESSION_SECRET=<same> PYTHONPATH=. .venv/bin/python -c "from api.main import issue; print(issue('loadtest@coresight.com'))")
.venv/bin/python scripts/ui_benchmark/rate_test.py "http://127.0.0.1:8000/api/v1/waves/412/results?q=XM1,XM2,XM3&dim=total,generation" --cookie "cip_session=$COOKIE" --rates 1000,2500,5000
.venv/bin/python scripts/ui_benchmark/rate_test.py "...same..." --cookie "cip_session=$COOKIE" --rates 2500 --seconds 300   # soak
```

## 10. Raw output

```
== Azure staging MySQL (csr-mysql8-flex-stg, Burstable B2s 2 vCPU / 4 GB), from the dev Mac over VPN, 2026-10-20 14:41
-- EXPLAIN ANALYZE, wave 412, XM3 by generation
serving  server execution time (ms), 4 runs: 0.04, 0.12, 0.03, 0.04
   plan: -> Index lookup on srv_result using PRIMARY (survey_id=412, qcode='XM3', dim='generation')  (cost=1.76 rows=15)
cube     server execution time (ms), 4 runs: 0.11, 0.10, 0.10, 0.15
   plan: -> Nested loop left join  (cost=9.64 rows=1.5) (actual time=0.0557..0.154 rows=15 loops=1)
raw      server execution time (ms), 4 runs: 312.00, 139.00, 20.30, 79.70
   plan: -> Table scan on <temporary>  (actual time=79.7..79.7 rows=15 loops=1)
-- concurrency over the VPN
network round trip (SELECT 1, 1 connection): p50=274.5 ms
serving  conns=1   rows=15  qps=     3.4  p50=  278.9ms p95=  352.1ms p99=  358.2ms
serving  conns=16  rows=15  qps=    47.9  p50=  292.4ms p95=  310.4ms p99=  355.4ms
serving  conns=64  rows=15  qps=   197.0  p50=  288.2ms p95=  308.0ms p99=  342.0ms
serving  conns=128 rows=15  qps=   406.1  p50=  285.0ms p95=  319.1ms p99=  362.0ms
cube     conns=1   rows=15  qps=     3.4  p50=  284.6ms p95=  345.4ms p99=  390.4ms
cube     conns=16  rows=15  qps=    53.2  p50=  291.4ms p95=  334.7ms p99=  394.1ms
cube     conns=64  rows=15  qps=   211.5  p50=  293.7ms p95=  339.4ms p99=  378.7ms
cube     conns=128 rows=15  qps=   423.0  p50=  289.6ms p95=  351.6ms p99=  405.2ms
raw      conns=1   rows=15  qps=     2.8  p50=  349.2ms p95=  465.5ms p99=  517.9ms
raw      conns=16  rows=15  qps=    39.8  p50=  379.6ms p95=  525.9ms p99=  607.7ms
raw      conns=64  rows=15  qps=    95.8  p50=  605.5ms p95= 1128.2ms p99= 1444.0ms
raw      conns=128 rows=15  qps=   103.2  p50= 1101.7ms p95= 2164.0ms p99= 2699.4ms
-- capacity inside MySQL (temporary procedures, dropped afterwards)
serving  1 session(s) x  20000 runs inside MySQL:    1.064 ms per query,       917 queries/s total
serving  2 session(s) x  20000 runs inside MySQL:    1.375 ms per query,      1361 queries/s total
serving  4 session(s) x  20000 runs inside MySQL:    1.433 ms per query,      2493 queries/s total
serving  8 session(s) x  10000 runs inside MySQL:      3237 queries/s total
serving  16 session(s) x  10000 runs inside MySQL:      4733 queries/s total
cube     1 session(s) x   5000 runs inside MySQL:    2.884 ms per query,       333 queries/s total
cube     2 session(s) x   5000 runs inside MySQL:    3.782 ms per query,       478 queries/s total
cube     4 session(s) x   5000 runs inside MySQL:    4.480 ms per query,       781 queries/s total
raw      1 session(s) x     40 runs inside MySQL:   44.978 ms per query,        17 queries/s total
raw      2 session(s) x     40 runs inside MySQL:   64.873 ms per query,        24 queries/s total
raw      4 session(s) x     40 runs inside MySQL:  107.963 ms per query,        29 queries/s total
== End-to-end: API (laptop, 2 workers) -> Azure staging MySQL; one request = XM1+XM2+XM3 x total+generation, 164 rows, 2.2 KB gz
-- result cache OFF
rate=   25/s  done=375 ok=375  achieved=25/s  p50=290.6ms p95=2728.3ms p99=2856.2ms max=3001.3ms
rate=   50/s  done=750 ok=750  achieved=49/s  p50=276.8ms p95=725.7ms p99=2744.3ms max=2802.6ms
rate=  100/s  done=1500 ok=1500  achieved=96/s  p50=1239.5ms p95=1790.7ms p99=2622.2ms max=2900.9ms
rate=  150/s  done=2250 ok=2250  achieved=116/s  p50=3094.4ms p95=4228.6ms p99=4339.0ms max=4417.1ms
-- result cache ON
rate= 1000/s  done=15000 ok=15000  achieved=1000/s  p50=0.7ms p95=0.9ms p99=2.8ms max=65.1ms
rate= 2500/s  done=37500 ok=37500  achieved=2499/s  p50=0.3ms p95=0.4ms p99=0.4ms max=11.7ms
rate= 5000/s  done=75000 ok=75000  achieved=4997/s  p50=0.6ms p95=0.8ms p99=3.3ms max=80.3ms
== Soak + spike, API 2 workers, cached serving endpoint
memory before: 240 MB; worker cpu-seconds before: 59.6
rate= 2500/s  done=750000 ok=750000  achieved=2499/s  p50=0.3ms p95=0.4ms p99=0.4ms max=236.5ms
memory after soak: 240 MB; worker cpu-seconds after: 193.5
rate= 8000/s  done=120000 ok=120000  achieved=7989/s  p50=12.3ms p95=21.9ms p99=49.0ms max=63.8ms
rate= 1000/s  done=15000 ok=15000  achieved=1000/s  p50=0.7ms p95=0.8ms p99=1.6ms max=4.5ms
memory after spike: 240 MB
```

Earlier local tests (frameworks, browsers, first visit): [02-benchmarks.md](02-benchmarks.md) and [11-capacity-staging-production.md](11-capacity-staging-production.md).

## 11. Two cuts combined (e.g. Gen Z × female)

**Run:** 20 Oct 2026, same Azure staging server. Wave 412 (12 Oct, 404 qualified), cuts gender × generation. Questions: XM3 (single choice) and XM2 (retailers, multi-select, 26 items).

`srv_result` holds one cut at a time, so a combined filter needs something else. Three options were measured:

| Option | What it is | Server time (`EXPLAIN ANALYZE`, p50) | Uncached reads/s (16 sessions, inside MySQL) | Size, all 320 waves | Filters it can answer |
|---|---|--:|--:|--:|---|
| **Raw answers** | Aggregate `cip_answer` (5 joins) per request | 4.0 ms single · **33.3 ms** multi | 222 · **41** | 0 (exists) | Anything |
| **Per-respondent table** (recommended) | One row per qualified single-choice answer and per multi-select item *chosen*, plus one base row per respondent per multi question, each carrying the six cuts. GROUP BY two cuts per request. | **0.68 ms** single · **1.24 ms** multi | **1,930 · 1,075** | Built: **7.9 M rows, 0.98 GB** (estimated 5.5 M / 1.2 GB) | Any 2 or 3 cuts, cohorts, pooled weeks, "people who bought X" |
| **Pre-built pairs** | All 15 pairs of cuts counted by the ETL; one primary-key read | 0.05 ms · 0.14 ms | 12,676 · 6,403 | ≈ 11 M rows, **2.1 GB** (4× `srv_result`) | Exactly two of the six standard cuts |
| *One cut (`srv_result`), for reference* | *today's design* | *0.03 ms* | *13,925* | *1.9 M rows, 0.5 GB* | *One cut* |

**Correctness:** for both questions, the two-cut counts and bases summed over generation equal `srv_result`'s gender rows exactly: 10/10 rows for XM3 and 56/56 for XM2.

**This run's loop differs from §3's.** It returns one count per call, and serving reached 13,925/s here against 4,700/s in §3. Compare the options within this table, not across sections. Measured that way, a two-cut costs about 7–13× a one-cut read and is still sub-millisecond.

### The real limit is the sample, not the speed

| Wave 412, XM3 | GenZ | Millennial | GenX | Boomer |
|---|--:|--:|--:|--:|
| Female | **21** | 61 | 59 | 59 |
| Male | **19** | 58 | 52 | 71 |

Across every question and pair of cuts in this wave:
- **92 %** of two-cut cells have a base under 50, the small-base line;
- **76 %** are under 30.

At about 400 respondents a week, most two-cut numbers are noise.

### Recommendation

1. **Serve combined filters from a per-respondent table, built by the ETL next to `srv_result`.**
   - It costs 0.7–1.3 ms in the database.
   - The API caches it like every other result, so repeat views are the same 0.3 ms as today (§5).
   - Built, it takes 0.98 GB for all waves; with `srv_result` (0.51 GB) that's 1.5 GB against a 2 GB buffer pool. Only recent waves are read often, so the busy part stays in memory.
   - The cube already builds exactly these rows in a temporary table (`cip_tmp_cube` in `app/data/cube.py`), so keeping them adds little ETL work.
2. **Don't pre-build pairs.** They're about 10× faster per read, but:
   - they double the serving data again (2.1 GB) and no longer fit the buffer pool alongside it;
   - they answer only two standard cuts;
   - most of their cells are too small to show anyway.
3. **Never read raw answers per request.** The multi-select two-cut takes 33 ms and tops out at about 40 per second for the whole server.
4. **UI rules for two cuts:**
   - flag cells under 50 (amber, as today), and show "too few respondents" instead of a number under 30;
   - offer "pool the last 4 weeks" on two-cut views. Measured on the built table, that takes Gen Z × female (XM3) from 21 to **61**. Only 3 waves pooled: the 21 Sep wave didn't ask the holiday questions, and the response says `weeks: 3`.

**Not measured yet:**
- three cuts at once (the endpoint takes two);
- the API running inside Azure: CIP still has no App Service.

### Built: `srv_answer` + `/crosstab` (20 Oct 2026, 21:41–22:04 IST)

The recommendation above is now built:
- `sql/005_serving.sql`: the `srv_answer` table;
- `etl/serving.py`: `store_answers()`, in the same transaction as `srv_result`;
- `api/main.py`: `GET /api/v1/waves/{id}/crosstab?q=&by=a,b&weeks=1..4`;
- `tests/test_serving.py`: 2 new tests. One checks that two-cut sums equal `srv_result` on a real load; the other covers suppression, small base, pooling across waves by answer label, and the routing-change warning.

| What | Measured |
|---|---|
| Backfill, all 320 waves (`python -m etl.serving --all --jobs 4`, rebuilds `srv_result` too) | **984 s** (16 min), 0 errors |
| `srv_answer` | **7,870,531 rows** in 315 waves, about 25,000 per wave (34,960 for 12 Oct). **978 MB** data + index. 5 waves have none: CSI-US, 19 Sep – 24 Oct 2022, with no answers loaded (`rows_built` = 0 there too). |
| `srv_result` after the rebuild | 1,901,023 rows, unchanged; 506 MB |
| `/crosstab` count query, wave 412, generation × gender (`EXPLAIN ANALYZE`, p50 of 15) | XM3: **0.71 ms** (404 rows read). XM2: **1.07 ms** (598 rows) |
| Same, pooled `weeks=4` (3 waves had the question) | XM3: **2.74 ms** (1,208 rows). XM2: **3.48 ms** (1,553 rows) |
| Response size, XM2 pooled | 18.5 KB JSON, **2.0 KB gzipped** (260 rows: 52 clean, 78 small base, 130 suppressed) |
| API, **cache on**, 2 workers, `XM2 by generation,gender, weeks=4` | 1,000/s: p50 0.6 ms, p99 20 ms · **2,500/s: p50 0.3 ms, p99 1.5 ms** · 5,000/s: p50 1.1 ms, p99 33 ms. 0 errors |
| API, **cache off**, from the laptop over the VPN | 5–25/s: **p50 ≈ 800 ms**, which is 3 round trips × 274 ms VPN. p95 about 3.1 s while connections open. 0 errors |
| Errors | `by=generation,generation` and `weeks=5` → 422; unknown question → 404; no session → 401 |

**What a user will see from Azure:**
- Cached: the same sub-millisecond response as `/results`.
- Uncached, with the API next to the database (about 1 ms round trip): about 3 round trips + 1–3.5 ms of query ≈ **5–7 ms on the server**, plus the user's own network.

That last figure is an estimate, to be re-run once IT provides the App Service. The p99 of 20–33 ms at 1,000 and 5,000/s comes from the laptop running the load generator and the API together; the earlier `/results` runs show the same pattern (§5–6).

### Raw output

```
built prototype tables for wave 412 in 13.6 s
check vs srv_result (XM3 by gender): 10/10 rows match (count and base)
check vs srv_result (XM2 by gender): 56/56 rows match (count and base)
size tmp_two_cut_respondent   this wave   34,960 rows    7.4 MB  → all 320 waves ≈   5.5 M rows, 1.16 GB
size tmp_two_cut_pairs        this wave   84,883 rows   16.3 MB  → all 320 waves ≈  11.0 M rows, 2.12 GB
size srv_result               this wave   14,639 rows    3.9 MB  → all 320 waves ≈   1.9 M rows, 0.51 GB
two-cut cells: 59,276; base under 50: 92%; under 30: 76%
gender × generation bases for XM3: [('Female', 'Boomer', 59), ('Female', 'GenX', 59), ('Female', 'GenZ', 21), ('Female', 'Millennial', 61), ('Male', 'Boomer', 71), ('Male', 'GenX', 52), ('Male', 'GenZ', 19), ('Male', 'Millennial', 58), ('Non-binary / third gender', 'GenZ', 2), ('Non-binary / third gender', 'Millennial', 2)]

query                 rows   server p50   queries/s  (16 sessions, in MySQL)
raw single              33      4.03 ms         222
raw multi              260     33.30 ms          41
respondent single       33      0.68 ms       1,930
respondent multi       163      1.24 ms       1,075
pairs single            33      0.05 ms      12,676
pairs multi            153      0.14 ms       6,403
serving (one cut)       10      0.03 ms      13,925
dropped prototype tables
```

