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
