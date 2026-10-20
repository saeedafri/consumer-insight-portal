# 11 · How many users can use it: staging and production

> **Azure staging results (20 Oct, later the same day) are in [STRESS-TEST-RESULTS.md](STRESS-TEST-RESULTS.md):** database capacity per approach, end-to-end, a 5-minute soak and a spike. This file holds the earlier API and browser tests.

**Measured on 20 Oct 2026** against the real Holiday dashboard, served by the real API (`api/main.py`) from the real published payloads in `cip_stg`.

**Short answer** (assumptions and arithmetic in §4):

| | Staging (4.9 GB, assumed 1 vCPU) | Production (9.88 GB, assumed 2 vCPU) |
|---|--:|--:|
| API workers | 1 | 2 |
| Server memory used by the API | **137 MB** (measured) | **253 MB** (measured) |
| Sustained API capacity on Azure (planned at ≤ 50 % CPU) | **≈ 860 requests/s** | **≈ 1,750 requests/s** |
| **People actively using dashboards at the same time** | **≈ 8,600** | **≈ 17,500** |
| Registered customers (if 10 % are active at peak) | ≈ 86,000 | ≈ 175,000 |
| Server time per request | 0.3–0.6 ms (p50) | 0.3–0.6 ms (p50) |
| Wave switch / sort / filter in the dashboard | **≈ 10 ms**, in the browser | same |

Even if an Azure vCPU turns out **5× slower** than the test machine (not 3×), staging still carries about **5,000** active users and production about **10,000**.

**What limits it, in order:**
1. **CPU**, at about 200 µs per request on the test machine.
2. **Network distance:** 28 ms from the US East coast, about 220 ms from India.

**What does not limit it:**
- **Memory:** about 0 MB per extra user.
- **MySQL:** no queries per request.

## 1. What was tested

| Item | Value |
|---|---|
| Server | `gunicorn api.main:app -k uvicorn.workers.UvicornWorker -w 1` (staging shape) and `-w 2` (production shape) |
| Request | `GET /api/v1/dashboards/holiday_tracker/412`, with a signed session cookie and `Accept-Encoding: gzip` → 200, **1,305 bytes** |
| What the server does per request | Checks the HMAC signature, does a dict lookup, sends the stored gzip bytes. **Zero SQL.** |
| Machine | Apple M4, 10 cores, 16 GB. The load generator ran on the same machine. |
| Tools | `ab` (closed loop); [`scripts/ui_benchmark/rate_test.py`](../../scripts/ui_benchmark/rate_test.py) (open loop: fixed arrival rate, latency timed from the *scheduled* send so queueing counts); [`journey.py`](../../scripts/ui_benchmark/journey.py) (real Chrome windows) |
| CPU per request | Worker CPU time before and after each run, divided by requests |

## 2. Results

### 2.1 Saturation: how many requests per second before it is full (closed loop, `ab -k`)

| Workers | Connections | Requests/s | p50 | p95 | p99 | Failed | CPU per request |
|--:|--:|--:|--:|--:|--:|--:|--:|
| 1 | 1 | 2,830 | 0 ms | 0 ms | 0 ms | 0 | 196 µs |
| 1 | 50 | **5,184** | 9 ms | 15 ms | 35 ms | 0 | 203 µs |
| 2 | 1 | 3,235 | 0 ms | 0 ms | 0 ms | 0 | 202 µs |
| 2 | 50 | 10,254 | 5 ms | 6 ms | 10 ms | 0 | 207 µs |
| 2 | 100 | **10,521** | 9 ms | 11 ms | 23 ms | 0 | 203 µs |

Above about 128 connections opening at once, **macOS** resets new connections, because its listen backlog (`somaxconn`) is 128. That is a limit of this test machine, not of the API. Linux servers default to 4096.

### 2.2 Real-world arrival: requests arrive at a steady rate (open loop, 200 connections)

| Workers | Arrival rate | Achieved | p50 | p95 | p99 | max |
|--:|--:|--:|--:|--:|--:|--:|
| 1 | 500/s | 500/s | 0.9 ms | 2.0 ms | 8.4 ms | 25 ms |
| 1 | 1,000/s | 999/s | 0.6 ms | 0.9 ms | 29.4 ms | 86 ms |
| 1 | 2,500/s | 2,499/s | **0.3 ms** | **0.4 ms** | 1.6 ms | 18 ms |
| 1 | 4,000/s | 3,998/s | 0.4 ms | 0.5 ms | 14.7 ms | 60 ms |
| 2 | 1,000/s | 1,000/s | 0.6 ms | 0.9 ms | 2.8 ms | 16 ms |
| 2 | 2,500/s | 2,499/s | **0.3 ms** | **0.4 ms** | 3.3 ms | 55 ms |
| 2 | 5,000/s | 4,996/s | 0.6 ms | 9.1 ms | 48 ms | 133 ms |
| 2 | 7,500/s | 7,491/s | 6.4 ms | 23.4 ms | 60 ms | 90 ms |

Every request succeeded in every run.

### 2.3 Real browsers: open the dashboard, then switch wave (1 worker)

Each simulated user:
1. signs in (redirect), loads the app (71 KB gz) and the latest wave;
2. switches to wave 3.

"Ready" means all tiles, 5 takeaways and 14 bars are drawn with the right numbers.

| People at the same moment | 1 | 5 | 10 | 20 | 40 |
|---|--:|--:|--:|--:|--:|
| Open → fully drawn (p50) | 0.07 s | 0.14 s | 0.22 s | 0.33 s | 0.67 s |
| Switch wave → fully drawn (p50) | **0.01 s** | 0.02 s | 0.05 s | 0.11 s | 0.17 s |
| Server memory | 135 MB | 135 MB | 134 MB | 134 MB | 134 MB |

**Wave switches never call the server.** All waves are prefetched (about 1.3 KB each), so the switch is pure browser rendering. Its 10 ms for one user is the true figure. The rise at 20–40 users is 40 Chrome windows sharing this laptop's CPU, not the server.

**For comparison:** the same-shape screen in Streamlit took **2.85 s per click** at 40 users ([02 §0](02-benchmarks.md)).

### 2.4 First visit: static files (1 worker, uncompressed)

| File | Size | Requests/s | p95 |
|---|--:|--:|--:|
| `index.html` | 421 B | 1,891 | 34 ms |
| `assets/index-*.js` | 227 KB (71 KB if gzipped) | 1,718 | 36 ms |

These are fetched **once per user per release**, because hashed files are cached for a year (`immutable`, verified header). In production, put them behind the front proxy or a CDN with compression. Static files hold no data, so a CDN is safe for them.

## 3. Memory: why 4.9 GB is far more than enough

| Process | Measured |
|---|--:|
| gunicorn master + 1 API worker | 137 MB |
| gunicorn master + 2 API workers | 253 MB |
| Change from 1 to 40 simultaneous browsers | **−1 MB** (134–137 MB) |
| Change after 210,000 requests | none |

Memory does not grow with users: there is no per-user server state, and every payload is shared.

| | Staging 4.9 GB | Production 9.88 GB |
|---|--:|--:|
| OS / platform (assumed) | 1.0 GB | 1.0 GB |
| API workers | 0.14 GB (1) | 0.25 GB (2) |
| Job worker for the ETL and dashboard builds (budget) | 1.0 GB | 1.5 GB |
| **Total planned** | **2.1 GB (43 %)** | **2.8 GB (28 %)** |

More workers would not help on a 1-vCPU box: the limit is CPU, not memory.

## 4. From test machine to Azure: the arithmetic

**Step 1: capacity per vCPU**
- Measured saturation on M4: about 5,200 requests/s per worker (one core), about 200 µs CPU each.
- An Azure App Service vCPU is assumed **3× slower** per core. This is conservative: Pv3 is a hyper-threaded Xeon/EPYC core, roughly 2–3× slower than an M4 performance core in single-thread work.
- So about **1,730 requests/s per vCPU at saturation**.

**Step 2: plan at no more than 50 % CPU**, so latency stays at sub-millisecond server time with headroom for bursts and the weekly ETL:

| | Calculation | Sustained capacity |
|---|---|--:|
| Staging | 1 vCPU × 1,730 × 0.5 | ≈ **860 requests/s** |
| Production | 2 vCPU × 1,730 × 0.5 | ≈ **1,750 requests/s** (measured 2-worker scaling was ×2.0) |

**Step 3: requests per active user.** One dashboard visit costs 1 latest-wave request + 4 prefetches = **5 API requests**; switches and sorting then cost 0. A *very* active user opening a dashboard every minute makes 5/60 ≈ 0.083 requests/s. This design uses **0.1 requests/s per active user**.

**Step 4: users**

| | Active users at once | Registered customers (10 % active at peak) |
|---|--:|--:|
| Staging | 860 ÷ 0.1 = **8,600** | ≈ 86,000 |
| Production | 1,750 ÷ 0.1 = **17,500** | ≈ 175,000 |

**Burst check: the Tuesday e-mail.** If 2,000 clients open the dashboard within the same minute, that is 10,000 requests in 60 s ≈ 170/s. That is 10 % of production's sustained capacity.

**Sensitivity:** if Azure is 5× slower than the M4, divide the user numbers by 1.67. Staging still carries about 5,100 active users and production about 10,500.

## 5. What these numbers do NOT cover (be honest with the business)

| Not covered | Why it matters | When to measure |
|---|---|---|
| **Azure itself** | The vCPU speed factor is assumed | Gate 2: re-run `rate_test.py` from a second Azure machine against the real server |
| **OIDC sign-in** | Each sign-in costs one IdP round trip (seconds, once per session); every later request uses the signed cookie | With the real IdP |
| **Ad-hoc analysis** (custom cohorts on raw answers) | These hit MySQL; capacity is then set by the database tier, not the API | Gate 3 load test with a query mix |
| **Weekly ETL running at the same time** | The job worker competes for the same vCPU(s) | Soak test during a Tuesday load |
| **Shared server** with CIQ / MIP / MDB | They share the CPU (App Service apps share the plan) | Ask IT. Divide capacity by the number of busy apps. |
| **Network** | 28 ms (US East) to ≈ 220 ms (India) added to every server call; zero for in-browser switches | Real-user monitoring (INP/LCP) in production |

## 6. Re-run

```bash
# server (staging shape: -w 1; production shape: -w 2)
APP_ENV=LOCAL CIP_SESSION_SECRET=<random> .venv/bin/gunicorn api.main:app -k uvicorn.workers.UvicornWorker -w 1 -b 127.0.0.1:8001
# a signed test cookie
COOKIE=$(APP_ENV=LOCAL CIP_SESSION_SECRET=<same> PYTHONPATH=. .venv/bin/python -c "from api.main import issue; print(issue('loadtest@coresight.com'))")
# saturation
ab -q -k -n 40000 -c 50 -C "cip_session=$COOKIE" -H "Accept-Encoding: gzip" http://127.0.0.1:8001/api/v1/dashboards/holiday_tracker/412
# steady arrival rate, latency including queueing
.venv/bin/python scripts/ui_benchmark/rate_test.py http://127.0.0.1:8001/api/v1/dashboards/holiday_tracker/412 --cookie "cip_session=$COOKIE" --rates 500,1000,2500,4000
```

## 7. Raw output

```
== staging-shape: 1 worker
check: 200 1305 bytes (gzip)
c=1    rps=2830.49   p50=0ms p95=0ms p99=0ms max=15ms failed=0 non2xx=0 cpu_per_req=196µs
c=50   rps=5184.11   p50=9ms p95=15ms p99=35ms max=56ms failed=0 non2xx=0 cpu_per_req=203µs
memory: 137 MB total (master + workers)
== open-loop, 1 worker, 200 connections
rate=  500/s  done=7500 ok=7500  achieved=500/s  p50=0.9ms p95=2.0ms p99=8.4ms max=25.3ms
rate= 1000/s  done=15000 ok=15000  achieved=999/s  p50=0.6ms p95=0.9ms p99=29.4ms max=85.6ms
rate= 2500/s  done=37500 ok=37500  achieved=2499/s  p50=0.3ms p95=0.4ms p99=1.6ms max=18.4ms
rate= 4000/s  done=60000 ok=60000  achieved=3998/s  p50=0.4ms p95=0.5ms p99=14.7ms max=59.5ms
== production-shape: 2 workers
check: 200 1305 bytes (gzip)
c=1    rps=3235.21   p50=0ms p95=0ms p99=0ms max=5ms failed=0 non2xx=0 cpu_per_req=202µs
c=50   rps=10254.47  p50=5ms p95=6ms p99=10ms max=44ms failed=0 non2xx=0 cpu_per_req=207µs
-- 100 connections (ab -t 20): total_rps=10521 requests=210415 failed=0 p50=9ms p95=11ms p99=23ms cpu_per_req=203µs
memory: 253 MB total (master + workers)
== open-loop, 2 workers, 200 connections
rate= 1000/s  done=15000 ok=15000  achieved=1000/s  p50=0.6ms p95=0.9ms p99=2.8ms max=16.0ms
rate= 2500/s  done=37500 ok=37500  achieved=2499/s  p50=0.3ms p95=0.4ms p99=3.3ms max=55.0ms
rate= 5000/s  done=75000 ok=75000  achieved=4996/s  p50=0.6ms p95=9.1ms p99=48.0ms max=132.7ms
rate= 7500/s  done=112500 ok=112500  achieved=7491/s  p50=6.4ms p95=23.4ms p99=60.3ms max=89.5ms
== real CIP dashboard, 1 worker: open (sign-in redirect + app + latest wave) then switch to wave 3
  1 users | load-to-ready p50=0.07s | click-to-result p50=0.01s | server 135 MB
  5 users | load-to-ready p50=0.14s | click-to-result p50=0.02s | server 135 MB
 10 users | load-to-ready p50=0.22s | click-to-result p50=0.05s | server 134 MB
 20 users | load-to-ready p50=0.33s | click-to-result p50=0.11s | server 134 MB
 40 users | load-to-ready p50=0.67s p95=0.71s | click-to-result p50=0.17s p95=0.19s | server 134 MB
== first-visit static files, 1 worker (no compression in StaticFiles)
/  421 bytes  1891.00 req/s  p95=34ms
/assets/index-*.js  227072 bytes  1718.28 req/s  p95=36ms
```
