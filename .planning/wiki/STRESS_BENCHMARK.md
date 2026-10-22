# Stress benchmark: 50 analysts at once

22 Oct 2026, on a second API instance (port 8001) with the live data in `cip_stg`. The live server on port 8000 was not touched. Strict counting: anything but 200 or 304 is an error. Each analyst keeps one connection and pauses 20-120 ms between requests.

Mix: 50% cross-tabs (two random cuts out of six, 1, 2 or 4 weeks pooled), 30% question search, 20% full-history trend files. Questions are real codes from wave 415.

| Round (30 s each) | Requests | Req/s | Errors | p50 | p95 | p99 | max |
|---|---|---|---|---|---|---|---|
| 1 | 20,208 | 671 | 0 | 1.2 ms | 3.6 ms | 10.0 ms | 41 ms |
| 2 | 20,256 | 673 | 0 | 1.3 ms | 2.9 ms | 5.3 ms | 33 ms |
| 3 | 20,273 | 673 | 0 | 1.2 ms | 2.7 ms | 6.4 ms | 54 ms |

By route (round 1): cross-tab p50 1.2 / p95 4.5 ms; search 1.2 / 3.0 ms; question trend files 1.2 / 2.9 ms.

## Memory (server process RSS)

Peaks 166, 165 and 157 MB; ends 165, 137 and 139 MB. It grows while the response caches fill in round 1 and then stays flat across rounds 2 and 3: no leak. (`/healthz` reports 4,743 cached results, 74 MB.)

## Database pool

After the run: pool size 10, 0 checked out. Published answers (cross-tabs, trends, search, books) never touch the database, so the pool is idle under this load. Reads that do reach MySQL pay the India-to-Azure round trip of about 270 ms.

## Database queries (read-only EXPLAIN and timing)

| Query | Index used | Time |
|---|---|---|
| One wave and question counted by two cuts (`srv_answer`) | PRIMARY, range on `(survey_id, qcode)`, ~272 rows | 287 ms p50, 293 p95 |
| Same by all six cuts at once (what publish does) | PRIMARY | 295 / 296 ms |
| Result rows for two cuts (`srv_result`) | PRIMARY | 291 / 293 ms |
| One question across all waves of a family | `ix_srv_wave_family` then PRIMARY | 294 / 300 ms |
| `SELECT 1` | none | 269 ms |

Every query is an index range read; none scans the table. Subtracting the 269 ms round trip, the server work is about 20 ms, so p95 is under 0.35 s. No index was added: the primary keys already are the composite `(survey_id, qcode, dim, dim_value, ...)` indexes, and another would cost storage and ETL time for nothing.

## Caveats

- Loopback test on one Mac; the 1-core servers will be slower on CPU. Re-run on staging before sizing.
- The first version of this test opened a new connection per request and exhausted local ports (an artifact of the test, not the server). It was rewritten to keep connections.
- The earlier stress script in `scripts/stress_benchmark.py` hides some of its own errors and needs a warm cache; this test does not.

## Production budget: 1 core, 768 MB (22 Oct 2026, later run)

The API image (`deploy/Dockerfile`, 2 workers, `CIP_CACHE_MB=128`) in Docker with `--cpus=1 --memory=768m`, the live published files mounted read-only, the database on Azure. Same mix and strict counting as above; the load generator ran on the same Mac.

| Run | Requests/s | Errors | p50 | p95 | p99 | Memory peak |
|---|---|---|---|---|---|---|
| 50 analysts, cold caches | 575 | 0 | 2.8 ms | 70 ms | 163 ms | 361 MB |
| 50 analysts, warm | 669 | 0 | 1.2 ms | 7.0 ms | 24 ms | 394 MB |
| 200 analysts, no pause between requests (saturation) | 1,274 | 0 | 134 ms | 274 ms | 380 ms | 446 MB |

- One core serves about 1,270 requests a second before requests queue. An analyst clicking every few seconds makes well under one request a second, so one core carries hundreds of people working at once.
- Memory stays under 450 MB in a 768 MB cap: each worker's response cache is capped at 128 MB, and the cache is the only part that grows. With nginx (128 MB cap) the portal fits in 1 GB.
- Boot is 2 to 18 s: the time is three startup queries and the dashboard payloads over the 270 ms Azure link, not the container (2 s on a local database, see the CI smoke test).
- The first requests after a start or a new publish are slower (p95 70 ms) while each worker reads and caches the published files; after that, p95 is under 10 ms.

## Streamlit done well vs CIP, same optimised tables, same budget (22 Oct 2026)

Both in Docker with 1 core and 1 GB, on the same Azure database. Streamlit: a simple app (`scripts/ui_benchmark/streamlit_cip.py`) reading the pre-computed serving table `srv_result`, results cached with `st.cache_data`, showing a metric, a chart and a table. CIP: the Cross-tab screen (two cuts). `scripts/ui_benchmark/journey.py` opens N real browser windows at the same moment (open page until drawn), then all N change the cut to Income at the same moment (click until the new numbers are drawn).

| Users at once | Streamlit: open page (p95) | CIP: open page (p95) | Streamlit: change cut (p95) | CIP: change cut (p95) |
|---|---|---|---|---|
| 1 | 0.30 s | 0.37 s | 0.44 s | 0.04 s |
| 5 | 1.04 s | 0.47 s | 0.38 s | 0.06 s |
| 10 | 1.84 s | 0.51 s | 0.67 s | 0.18 s |
| 20 | 3.75 s | 0.77 s | 1.25 s | 0.24 s |
| 40 | 10.49 s | 1.82 s | 4.37 s | 1.43 s |

Server memory: Streamlit 131 MB idle, 149 MB at 40 users; CIP 230 MB throughout (2 workers and their cache). Every request succeeded on both.

- With optimised tables Streamlit is fine for one person, and lean on memory. But each user is a session on one Python process that re-runs the whole script on every click, so the wait grows with every extra person: 40 people opening the page wait over 10 s.
- CIP's server answers each request in about 1 ms; at 40 users most of the 1.4–1.8 s is the 40 browser windows drawing on the one test Mac, not the server.
- Caveat: 40 is the most windows this Mac drives reliably, so the gap at hundreds of users is not measured here; the HTTP tests above (about 670 to 1,270 requests a second on one core) cover CIP at that scale, and Streamlit has no HTTP equivalent to test (its work runs over one WebSocket per session).

## nginx answers everything repeatable (22 Oct 2026, evening)

Change: nginx now checks the signed session cookie itself (`deploy/cip_auth.js`, the API's own HMAC rule) and caches every answer that is the same for every signed-in user (cross-tabs, results, trends, search) until the next publish; the publish step empties that cache and pre-asks every cross-tab of the 3 newest waves (14,040 answers in 36 s). Python computes each distinct answer once per publish. Setup: nginx and the API pinned together to ONE CPU (1 GB in all), load generators on other CPUs, live published data, Azure database.

Sustained, every user requesting back to back with no pause (wrk, mixed: 50 % cross-tabs over 2,340 URLs, 30 % search, 20 % trends): about 13,500 requests/s, 0 errors up to 5,000 users; from 10,000 continuous users some connections time out.

Same instant, each of N people (each with their own signed cookie) sends one request at the same moment, warm cache:

| People at once | Median | 95 % within | Slowest | Errors |
|---|---|---|---|---|
| 1,000 | 43 ms | 79 ms | 82 ms | 0 |
| 2,000 | 99 ms | 163 ms | 167 ms | 0 |
| 5,000 | 258 ms | 505 ms | 533 ms | 0 |
| 10,000 | 442–527 ms | 834–934 ms | 869–968 ms | 0 |
| 20,000 | 740–847 ms | 1.43–1.53 s | 1.50–1.59 s | 0 |

Inside nginx every one of those requests took 0.0 ms once read (its own `$request_time`); the connections were opened before the burst, so the time is queueing for the one core: at about 13,500 requests/s, 10,000 requests need about 0.75 s of that core however fast each one is. Going lower at 10,000+ at once takes a second core (or a CDN in front), not faster code. Before this change the same bursts took 2.5 s (1,000), 4 s (2,000) and 7 s with 17 % retries (5,000).

Cold (a publish nobody has opened yet, without the pre-warm): 5,000 at once p95 1.8 s, 0 errors; 10,000 at once dropped most connections because Python shared the one core with nginx. The pre-warm exists for this case.

Memory: nginx 56 MB (master 12, worker 40, cache manager 4.5); API 2 workers, now capped at 32 MB of their own cache each (about 300 MB). On disk: published files 69 MB, nginx answer cache 75 MB for 14,046 answers (capped 512 MB, emptied each publish).

## Stacks on the same workload (1 core, 1 GB, wrk at 10 and 100 connections)

| Stack | Page req/s | Data req/s | Peak memory |
|---|---|---|---|
| FastAPI + Vite (CIP) | 4,595 | 9,927 | 91 MB |
| Next.js static export + FastAPI | 4,871 | 8,926 | 98 MB |
| Next.js server rendering (16.4.2) | 686 | 1,616 (interaction) | 228 MB |
| Plain Node + Vite | 106,476 | 86,374 | 46 MB |

`scripts/ui_benchmark/bench_docker.py`, the store-table workload of docs/12. Next.js server rendering is 7 times slower than the static setups and uses 2.5 times the memory; as a static export it is the same as CIP's setup. Plain Node is fast at handing out ready answers, which nginx (C) already does for CIP.
