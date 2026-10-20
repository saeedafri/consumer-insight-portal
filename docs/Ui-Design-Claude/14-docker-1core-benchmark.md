# 14 · Every stack on a 1-core Debian server: RAM, requests/s, latency, page and click time

**Run:** 20 Oct 2026, 22:22–23:20 IST, by Claude.

**Question:** the CIP servers are Debian Linux with **1 core**: staging has **4.5 GB** RAM and production **8–9 GB**. How much RAM does each stack use, how many requests per second can it serve, how fast is each response, and how fast is the screen for real users at the same time?

## The answer in one table

Same screen in every stack: a sector picker, the "Stores open" metric, an ECharts bar chart of 50 states and the 50-row table, over a 1 M-row table. Server pinned to **1 CPU**, staging cap **4.5 GB**.

| Stack | RAM idle → peak under load | Data requests/s, 10 conns | Response p50 / p99 | Page ready, 40 users (p50) | Click → result, 40 users (p50) | Verdict |
|---|--:|--:|--:|--:|--:|---|
| **React + Vite (static) + FastAPI** (recommended) | **52 → 91 MB** | **10,349** | **0.74 / 2.1 ms** | **1.13 s** | **0.13 s** | ✅ **Best for CIP** |
| React + Vite (static) + Node.js | 18 → 49 MB | **90,523** | 0.07 / 0.19 ms | 1.46 s | 0.24 s | ✅ Fastest server, no gain for users |
| Next.js static export + FastAPI | 52 → 98 MB | 10,418 | 0.74 / 1.6 ms | 1.86 s* | 0.33 s* | ✅ Same as Vite (it is the same model) |
| Next.js SSR (server rendering) | 65 → **477 MB** | 2,494 per click · 1,133 per page | 2.8 / 10.9 ms per click · 5.9 / 27.7 ms per page | 1.61 s | 0.50 s | ⚠️ 4–9× fewer requests/s, 5× the RAM |
| Dash (pure Python) | 58 → 72 MB | 5,022 callbacks | 1.6 / 5.2 ms | 3.01 s | **1.96 s** | ❌ Slow under concurrent users |
| Streamlit (written well) | 59 → 140 MB | not drivable by HTTP (websocket) | — | **6.92 s** | **3.59 s** | ❌ Grows ~0.1 s per extra user |
| Streamlit "load the table and show it" (SIP/MIP habit) | 59 → **1,532 MB at 10 users** | — | — | 3.17 s at 10 users | 3.45 s at 10 users | ❌❌ **Killed for running out of RAM at 4.5 GB** |

\* Re-run on its own after the harness's Chrome dropped its connection at the 40-user step (§4). Every SPA's 40-user page time is dominated by 40 Chrome windows rendering on the test Mac, not by the server. Differences under about 0.3 s between the first four rows are noise.

**Winner:** a static React + Vite front end on FastAPI.
- Its click is the fastest under load (0.13 s at 40 users).
- It uses under 100 MB.
- It serves about 10,000 data requests/s on one core.
- It keeps the ETL, statistics and API in one language, Python.

**Fastest raw server:** Node.js, about 8× FastAPI's requests/s.
- Users don't feel it: both answer in well under 1 ms, so the browser and network decide the time.
- Node is the upgrade path if requests/s ever becomes the limit. The static front end would not change.

**Losers:**
- **Streamlit** grows from 0.5 s to 3.6 s per click as users are added.
- **Streamlit the SIP/MIP way** runs out of RAM at 4.5 GB: the container was OOM-killed between 10 and 20 users. At 9 GB it survives, but 20 users wait **32 s** for the page and 18 s per click, at 2.7 GB.
- **Dash** takes 2 s per click at 40 users.
- **Next.js SSR** costs 4–9× the CPU per request and 5× the RAM of the static options, with no benefit behind a login.

## 1. How it was run

| Item | Value |
|---|---|
| Server OS | **Debian 13 (trixie)** containers: `python:3.13-slim-trixie`, `node:26-trixie-slim` |
| Limits | `--cpuset-cpus 0 --cpus 1` (exactly one core) and `--memory 4.5g` (staging) or `9g` (production), swap off |
| Host | Colima 0.10.3 Linux VM (6 vCPU, 12 GB) on the Apple M4 dev Mac, ARM64 |
| Load generator | `wrk 4.1.0` (Debian package) in its own container on **CPUs 2–5**, so it never takes the server's core. 4 threads, 20 s per step after a 5 s warm-up, 10 and 100 open connections |
| Memory | `docker stats` sampled about every second: cgroup usage minus inactive file cache. Peak reported |
| Users | `journey.py`: N real headless Chrome windows open the page at the same moment, then all change the sector at the same moment. "Ready" means the right number, the drawn chart and the full table are all on screen. One warm-up user first. |
| Versions | FastAPI 0.154.0 · Starlette 1.9.0 · Uvicorn 0.54.0 · Gunicorn 26.2.0 (1 worker) · Node 26.12.0 · Next.js 16.4.2 (Turbopack, `standalone`) · React 19.3.1 · Vite 8.3.4 · ECharts 6.1.0 · Dash 4.4.1 (1 worker × 4 threads) · Streamlit 1.55.0 (the SIP/MIP pin) · pandas 2.3.3 |

The code is in [`scripts/ui_benchmark/`](../../scripts/ui_benchmark/):
- [`bench_docker.py`](../../scripts/ui_benchmark/bench_docker.py) runs everything;
- [`stacks/Dockerfile`](../../scripts/ui_benchmark/stacks/Dockerfile) builds the images;
- [`stacks/vite-app`](../../scripts/ui_benchmark/stacks/vite-app/src/main.tsx) and [`stacks/next-app`](../../scripts/ui_benchmark/stacks/next-app/app/page.tsx) hold the React + Vite and Next.js versions of the screen.

What each stack does per request:

| Stack | Page | Data on a sector change |
|---|---|---|
| React + Vite + FastAPI / Node | Static `index.html` + JS from the API server | `GET /api/summary/{sector}`, cached JSON |
| Next.js static export + FastAPI | Static export | Same `GET` as above |
| Next.js SSR | The server queries SQLite and renders the full HTML per request | A soft navigation: the server re-renders the page as RSC (13 KB) |
| Dash | Layout JSON | `POST /_dash-update-component` |
| Streamlit | App shell | Websocket: the whole script re-runs per session |

## 2. Server capacity on 1 core: requests per second and response time

### Staging (1 CPU, 4.5 GB)

| Stack · endpoint | 10 connections: req/s · p50 · p90 · p99 | 100 connections: req/s · p50 · p90 · p99 |
|---|---|---|
| **FastAPI · data API** | **10,349 · 0.74 · 0.87 · 2.11 ms** | 9,802 · 9.9 · 12.1 · 25.3 ms |
| FastAPI · static page | 4,703 · 1.64 · 1.89 · 4.08 ms | 5,035 · 19.4 · 20.9 · 33.6 ms |
| **Node.js · data API** | **90,523 · 0.07 · 0.14 · 0.19 ms** | 86,577 · 1.1 · 1.3 · 2.2 ms |
| Node.js · static page | 104,950 · 0.06 · 0.12 · 0.23 ms | 113,392 · 0.9 · 1.0 · 1.7 ms |
| Next.js static · data API (FastAPI) | 10,418 · 0.74 · 0.83 · 1.62 ms | 10,378 · 9.7 · 11.1 · 18.7 ms |
| Next.js static · page (FastAPI) | 4,794 · 1.64 · 1.84 · 2.32 ms | 4,890 · 19.9 · 22.0 · 38.2 ms |
| **Next.js SSR · click (RSC)** | 2,494 · 2.78 · 4.71 · 10.87 ms | 2,077 · 46.3 · 54.5 · **898 ms** |
| **Next.js SSR · full page** | 1,133 · 5.85 · 10.23 · 27.69 ms | 1,161 · 80.4 · 114 · 244 ms |
| Dash · callback | 5,022 · 1.57 · 1.85 · 5.21 ms | 5,204 · 18.4 · 20.5 · 36.2 ms |
| Dash · layout page | 4,323 · 1.81 · 2.18 · 6.08 ms | 4,410 · 21.8 · 24.0 · 39.4 ms |
| Streamlit · shell page only | 7,524 · 1.04 · 1.09 · 1.43 ms | 7,900 · 12.2 · 13.5 · 23.5 ms |

How to read this table:
- **At 100 connections every stack is saturated.** The p50 there is mostly queueing: 100 requests waiting for one core.
- **The 10-connection row is the honest per-request response time.**
- FastAPI's static page is slower than its API because Starlette's `StaticFiles` reads the file each time. In production, nginx or the CDN serves the static files, so this row stops mattering.
- **The Streamlit and Dash "page" rows look fast but are only the empty shell.** The real work happens afterwards, which is why §3's user times are the ones that count.

### Production (1 CPU, 9 GB): same CPU, same result

| Stack · endpoint, 10 connections | Staging 4.5 GB | Production 9 GB |
|---|--:|--:|
| FastAPI · data API | 10,349 req/s · p50 0.74 ms | 10,160 req/s · p50 0.74 ms |
| Node.js · data API | 90,523 · 0.07 ms | 79,394 · 0.08 ms |
| Next.js SSR · click | 2,494 · 2.78 ms | 1,599 · 3.71 ms |
| Next.js SSR · page | 1,133 · 5.85 ms | 755 · 9.20 ms |
| Dash · callback | 5,022 · 1.57 ms | 4,419 · 1.71 ms |

**More RAM doesn't buy more requests/s: one core is the limit.** The run-to-run spread is about ±10 % for FastAPI and Dash. Next.js SSR varies more (±30 %) because of V8 garbage collection. The only stack where RAM changes the outcome is the Streamlit "load the table" pattern (§3).

## 3. Real users at the same moment (staging: 1 CPU, 4.5 GB)

Each cell gives page ready / click → result, p50 in seconds. Server memory at 40 users is in the last column.

| Stack | 1 user | 5 | 10 | 20 | 40 | Server RAM |
|---|--:|--:|--:|--:|--:|--:|
| **React + Vite + FastAPI** | 0.12 / **0.04** | 0.20 / 0.05 | 0.32 / 0.07 | 0.68 / 0.12 | **1.13 / 0.13** | 81 MB |
| React + Vite + Node | see raw | — | 0.33 / 0.04 | 0.57 / 0.08 | 1.46 / 0.24 | 49 MB |
| Next.js static + FastAPI | 0.06 / 0.03 | 0.14 / 0.03 | 0.24 / 0.04 | 0.48 / 0.07 | 1.86 / 0.33* | 86 MB |
| Next.js SSR | see raw | — | 0.33 / 0.15 | 0.55 / 0.22 | 1.61 / 0.50 | 196 MB |
| Dash | see raw | — | 0.58 / 0.36 | 1.17 / 0.47 | 3.01 / **1.96** | 84 MB |
| Streamlit (well written) | see raw | — | 1.32 / 0.52 | 2.52 / 1.06 | **6.92 / 3.59** | 140 MB |
| Streamlit "load the table" | — | 2.01 / 1.60 | 3.17 / 3.45 | **OOM-killed** | — | 1,532 MB, then killed |
| Streamlit "load the table", **9 GB** | 0.57 / 0.53 | 6.29 / 4.72 | 9.75 / 9.64 | **32.2 / 17.8** | harness crashed | 2,666 MB |

Full per-step rows, including p95 and max, are in §5.

- **The click is what a user feels all day.** The static React options stay at 0.04–0.33 s. Next.js SSR doubles that, because every click is rendered on the server's one core. Dash and Streamlit go up 10–30×.
- **A first-visit page at 40 simultaneous users** is limited mainly by the test Mac running 40 Chrome windows at once. Real users each have their own device.

## 4. Honest limits

| Limit | Effect | What closes it |
|---|---|---|
| ARM64 VM on an Apple M4, not the Azure x86 server | Absolute requests/s are higher than on an Azure core. An Azure vCPU is probably 2–3× slower ([11](11-capacity-staging-production.md)). The **ranking and ratios** carry over. | Re-run `bench_docker.py` on the staging VM itself (Docker on Debian) |
| The browser users ran on the same Mac | Page times at 20–40 users include Chrome's own CPU contention | Run the journeys from a second machine |
| Chrome's DevTools socket reset at 40 windows twice | Next.js static's 40-user step was re-run alone. Streamlit-naive at 9 GB has no 40-user row | — |
| A synthetic 1 M-row store table, not CIP's survey tables | Same shape of work: a cached summary per filter value | The CIP API itself was measured against Azure in [STRESS-TEST-RESULTS](STRESS-TEST-RESULTS.md) |
| Streamlit's websocket can't be driven by `wrk` | No requests/s figure for Streamlit's real work | The browser rows in §3 are its real measure |

**What this means for CIP's capacity.**
- These runs confirm the earlier per-core estimate ([11](11-capacity-staging-production.md)): one core, CPU-bound, RAM not the limit.
- **Because production also has 1 core, it carries about the same number of users as staging.** That is about 8,600 active users each, on the conservative Azure-speed assumption. The earlier 17,500 for production assumed 2 cores.
- The extra RAM in production is headroom for the weekly ETL and the caches, not for more users.

## 5. Raw output

The Docker images rebuild from [`stacks/Dockerfile`](../../scripts/ui_benchmark/stacks/Dockerfile). To re-run:

```bash
cd scripts/ui_benchmark
docker build -f stacks/Dockerfile --target py -t bench-py .
docker build -f stacks/Dockerfile --target node -t bench-node .
docker build -f stacks/Dockerfile --target load -t bench-load .
cd ../.. && python scripts/ui_benchmark/bench_docker.py --db /path/stores.db --scratch ~/.cache/cip-bench --memory 4.5g --journeys
```

`stores.db` comes from `python scripts/ui_benchmark/make_db.py stores.db`. Headless Chrome must listen on port 9333 for `--journeys`.

```
#### 2026-10-20 22:22  Debian 13 containers, server on 1 CPU, --memory 4.5g
== fastapi-vite  memory cap 4.5g, 1 CPU  | up in 0.5 s | idle 52 MB
   page     c=10      4,703 req/s  p50=   1.64 ms  p90=   1.89 ms  p99=   4.08 ms  mem now 54 MB  
   page     c=100     5,035 req/s  p50=  19.44 ms  p90=  20.92 ms  p99=  33.61 ms  mem now 61 MB  
   api      c=10     10,349 req/s  p50=   0.74 ms  p90=   0.87 ms  p99=   2.11 ms  mem now 79 MB  
   api      c=100     9,802 req/s  p50=   9.94 ms  p90=  12.10 ms  p99=  25.30 ms  mem now 82 MB  
   peak memory under load: 91 MB
   (the first 1-user row is a warm-up: it fills every server's cache for both sectors)
   idle footprint: 81 MB
     1 users | load-to-ready p50=0.14s p95=0.14s max=0.14s ok=1/1 | click-to-result p50=0.15s p95=0.15s max=0.15s ok=1/1 | server 83 MB
     1 users | load-to-ready p50=0.12s p95=0.12s max=0.12s ok=1/1 | click-to-result p50=0.04s p95=0.04s max=0.04s ok=1/1 | server 81 MB
     5 users | load-to-ready p50=0.20s p95=0.20s max=0.20s ok=5/5 | click-to-result p50=0.05s p95=0.07s max=0.07s ok=5/5 | server 81 MB
    10 users | load-to-ready p50=0.32s p95=0.35s max=0.35s ok=10/10 | click-to-result p50=0.07s p95=0.09s max=0.09s ok=10/10 | server 81 MB
    20 users | load-to-ready p50=0.68s p95=0.70s max=0.70s ok=20/20 | click-to-result p50=0.12s p95=0.15s max=0.16s ok=20/20 | server 81 MB
    40 users | load-to-ready p50=1.13s p95=1.18s max=1.18s ok=40/40 | click-to-result p50=0.13s p95=0.23s max=0.23s ok=40/40 | server 81 MB
== node-vite  memory cap 4.5g, 1 CPU  | up in 0.5 s | idle 18 MB
   page     c=10    104,950 req/s  p50=   0.06 ms  p90=   0.12 ms  p99=   0.23 ms  mem now 35 MB  
   page     c=100   113,392 req/s  p50=   0.86 ms  p90=   0.98 ms  p99=   1.70 ms  mem now 45 MB  
   api      c=10     90,523 req/s  p50=   0.07 ms  p90=   0.14 ms  p99=   0.19 ms  mem now 48 MB  
   api      c=100    86,577 req/s  p50=   1.12 ms  p90=   1.25 ms  p99=   2.23 ms  mem now 48 MB  
   peak memory under load: 49 MB
   (the first 1-user row is a warm-up: it fills every server's cache for both sectors)
   idle footprint: 47 MB
     1 users | load-to-ready p50=0.11s p95=0.11s max=0.11s ok=1/1 | click-to-result p50=0.12s p95=0.12s max=0.12s ok=1/1 | server 49 MB
     1 users | load-to-ready p50=0.09s p95=0.09s max=0.09s ok=1/1 | click-to-result p50=0.03s p95=0.03s max=0.03s ok=1/1 | server 49 MB
     5 users | load-to-ready p50=0.19s p95=0.20s max=0.20s ok=5/5 | click-to-result p50=0.03s p95=0.03s max=0.03s ok=5/5 | server 49 MB
    10 users | load-to-ready p50=0.33s p95=0.35s max=0.35s ok=10/10 | click-to-result p50=0.04s p95=0.06s max=0.06s ok=10/10 | server 49 MB
    20 users | load-to-ready p50=0.57s p95=0.58s max=0.58s ok=20/20 | click-to-result p50=0.08s p95=0.10s max=0.10s ok=20/20 | server 49 MB
    40 users | load-to-ready p50=1.46s p95=1.52s max=1.53s ok=40/40 | click-to-result p50=0.24s p95=0.32s max=0.33s ok=40/40 | server 49 MB
== next-ssr  memory cap 4.5g, 1 CPU  | up in 0.7 s | idle 65 MB
   page     c=10      1,133 req/s  p50=   5.85 ms  p90=  10.23 ms  p99=  27.69 ms  mem now 297 MB  
   page     c=100     1,161 req/s  p50=  80.37 ms  p90= 114.07 ms  p99= 244.27 ms  mem now 415 MB  
   click    c=10      2,494 req/s  p50=   2.78 ms  p90=   4.71 ms  p99=  10.87 ms  mem now 359 MB  
   click    c=100     2,077 req/s  p50=  46.34 ms  p90=  54.47 ms  p99= 898.48 ms  mem now 476 MB  
   peak memory under load: 477 MB
   (the first 1-user row is a warm-up: it fills every server's cache for both sectors)
   idle footprint: 475 MB
     1 users | load-to-ready p50=0.16s p95=0.16s max=0.16s ok=1/1 | click-to-result p50=0.06s p95=0.06s max=0.06s ok=1/1 | server 475 MB
     1 users | load-to-ready p50=0.08s p95=0.08s max=0.08s ok=1/1 | click-to-result p50=0.04s p95=0.04s max=0.04s ok=1/1 | server 178 MB
     5 users | load-to-ready p50=0.24s p95=0.24s max=0.24s ok=5/5 | click-to-result p50=0.08s p95=0.08s max=0.08s ok=5/5 | server 182 MB
    10 users | load-to-ready p50=0.33s p95=0.35s max=0.35s ok=10/10 | click-to-result p50=0.15s p95=0.17s max=0.17s ok=10/10 | server 187 MB
    20 users | load-to-ready p50=0.55s p95=0.75s max=0.76s ok=20/20 | click-to-result p50=0.22s p95=0.25s max=0.25s ok=20/20 | server 193 MB
    40 users | load-to-ready p50=1.61s p95=1.69s max=1.70s ok=40/40 | click-to-result p50=0.50s p95=0.64s max=0.64s ok=40/40 | server 196 MB
== next-static  memory cap 4.5g, 1 CPU  | up in 0.5 s | idle 52 MB
   page     c=10      4,794 req/s  p50=   1.64 ms  p90=   1.84 ms  p99=   2.32 ms  mem now 55 MB  
   page     c=100     4,890 req/s  p50=  19.92 ms  p90=  22.02 ms  p99=  38.22 ms  mem now 64 MB  
   api      c=10     10,418 req/s  p50=   0.74 ms  p90=   0.83 ms  p99=   1.62 ms  mem now 82 MB  
   api      c=100    10,378 req/s  p50=   9.66 ms  p90=  11.05 ms  p99=  18.68 ms  mem now 84 MB  
   peak memory under load: 98 MB
   (the first 1-user row is a warm-up: it fills every server's cache for both sectors)
   idle footprint: 83 MB
     1 users | load-to-ready p50=0.08s p95=0.08s max=0.08s ok=1/1 | click-to-result p50=0.12s p95=0.12s max=0.12s ok=1/1 | server 88 MB
     1 users | load-to-ready p50=0.06s p95=0.06s max=0.06s ok=1/1 | click-to-result p50=0.03s p95=0.03s max=0.03s ok=1/1 | server 86 MB
     5 users | load-to-ready p50=0.14s p95=0.15s max=0.15s ok=5/5 | click-to-result p50=0.03s p95=0.03s max=0.03s ok=5/5 | server 86 MB
    10 users | load-to-ready p50=0.24s p95=0.25s max=0.25s ok=10/10 | click-to-result p50=0.04s p95=0.05s max=0.05s ok=10/10 | server 86 MB
    20 users | load-to-ready p50=0.48s p95=0.49s max=0.49s ok=20/20 | click-to-result p50=0.07s p95=0.09s max=0.09s ok=20/20 | server 86 MB
   Multiple exceptions in yield list
   ConnectionResetError: [Errno 54] Connection reset by peer
   Multiple exceptions in yield list
   ConnectionResetError: [Errno 54] Connection reset by peer
   Multiple exceptions in yield list
   ConnectionResetError: [Errno 54] Connection reset by peer
   Multiple exceptions in yield list
   ConnectionResetError: [Errno 54] Connection reset by peer
   Multiple exceptions in yield list
   ConnectionResetError: [Errno 54] Connection reset by peer
   Multiple exceptions in yield list
   ConnectionResetError: [Errno 54] Connection reset by peer
   Multiple exceptions in yield list
   ConnectionResetError: [Errno 54] Connection reset by peer
   Multiple exceptions in yield list
   ConnectionResetError: [Errno 54] Connection reset by peer
   Multiple exceptions in yield list
   ConnectionResetError: [Errno 54] Connection reset by peer
   Multiple exceptions in yield list
   ConnectionResetError: [Errno 54] Connection reset by peer
   Multiple exceptions in yield list
   ConnectionResetError: [Errno 54] Connection reset by peer
   Multiple exceptions in yield list
   ConnectionResetError: [Errno 54] Connection reset by peer
   Multiple exceptions in yield list
   ConnectionResetError: [Errno 54] Connection reset by peer
   Multiple exceptions in yield list
   ConnectionResetError: [Errno 54] Connection reset by peer
   Multiple exceptions in yield list
   ConnectionResetError: [Errno 54] Connection reset by peer
   Multiple exceptions in yield list
   ConnectionResetError: [Errno 54] Connection reset by peer
   Multiple exceptions in yield list
   ConnectionResetError: [Errno 54] Connection reset by peer
   Multiple exceptions in yield list
   ConnectionResetError: [Errno 54] Connection reset by peer
   Multiple exceptions in yield list
   ConnectionResetError: [Errno 54] Connection reset by peer
   Multiple exceptions in yield list
   ConnectionResetError: [Errno 54] Connection reset by peer
   Multiple exceptions in yield list
   ConnectionResetError: [Errno 54] Connection reset by peer
       return future_cell["future"].result()
   ConnectionResetError: [Errno 54] Connection reset by peer
== dash  memory cap 4.5g, 1 CPU  | up in 0.5 s | idle 58 MB
   page     c=10      4,323 req/s  p50=   1.81 ms  p90=   2.18 ms  p99=   6.08 ms  mem now 60 MB  
   page     c=100     4,410 req/s  p50=  21.81 ms  p90=  23.95 ms  p99=  39.44 ms  mem now 61 MB  
   callback c=10      5,022 req/s  p50=   1.57 ms  p90=   1.85 ms  p99=   5.21 ms  mem now 71 MB  
   callback c=100     5,204 req/s  p50=  18.39 ms  p90=  20.54 ms  p99=  36.21 ms  mem now 72 MB  
   peak memory under load: 72 MB
   (the first 1-user row is a warm-up: it fills every server's cache for both sectors)
   idle footprint: 71 MB
     1 users | load-to-ready p50=0.46s p95=0.46s max=0.46s ok=1/1 | click-to-result p50=0.07s p95=0.07s max=0.07s ok=1/1 | server 72 MB
     1 users | load-to-ready p50=0.22s p95=0.22s max=0.22s ok=1/1 | click-to-result p50=0.06s p95=0.06s max=0.06s ok=1/1 | server 75 MB
     5 users | load-to-ready p50=0.40s p95=0.43s max=0.43s ok=5/5 | click-to-result p50=0.09s p95=0.09s max=0.09s ok=5/5 | server 84 MB
    10 users | load-to-ready p50=0.58s p95=0.60s max=0.60s ok=10/10 | click-to-result p50=0.36s p95=0.37s max=0.37s ok=10/10 | server 84 MB
    20 users | load-to-ready p50=1.17s p95=1.18s max=1.19s ok=20/20 | click-to-result p50=0.47s p95=0.49s max=0.49s ok=20/20 | server 84 MB
    40 users | load-to-ready p50=3.01s p95=3.27s max=3.27s ok=40/40 | click-to-result p50=1.96s p95=1.96s max=1.96s ok=40/40 | server 84 MB
== streamlit  memory cap 4.5g, 1 CPU  | up in 1.5 s | idle 59 MB
   page = the static app shell only; Streamlit's data travels over a websocket, so wrk cannot drive it
   page     c=10      7,524 req/s  p50=   1.04 ms  p90=   1.09 ms  p99=   1.43 ms  mem now 60 MB  
   page     c=100     7,900 req/s  p50=  12.21 ms  p90=  13.51 ms  p99=  23.48 ms  mem now 62 MB  
   peak memory under load: 62 MB
   (the first 1-user row is a warm-up: it fills every server's cache for both sectors)
   idle footprint: 61 MB
     1 users | load-to-ready p50=0.85s p95=0.85s max=0.85s ok=1/1 | click-to-result p50=0.23s p95=0.23s max=0.23s ok=1/1 | server 131 MB
     1 users | load-to-ready p50=0.29s p95=0.29s max=0.29s ok=1/1 | click-to-result p50=0.16s p95=0.16s max=0.16s ok=1/1 | server 131 MB
     5 users | load-to-ready p50=0.72s p95=0.86s max=0.86s ok=5/5 | click-to-result p50=0.23s p95=0.23s max=0.23s ok=5/5 | server 132 MB
    10 users | load-to-ready p50=1.32s p95=1.87s max=1.87s ok=10/10 | click-to-result p50=0.52s p95=0.53s max=0.53s ok=10/10 | server 135 MB
    20 users | load-to-ready p50=2.52s p95=3.68s max=3.85s ok=20/20 | click-to-result p50=1.06s p95=1.26s max=1.26s ok=20/20 | server 137 MB
    40 users | load-to-ready p50=6.92s p95=10.91s max=10.91s ok=40/40 | click-to-result p50=3.59s p95=3.61s max=3.61s ok=40/40 | server 140 MB
== streamlit-naive  memory cap 4.5g, 1 CPU  | up in 1.2 s | idle 59 MB
   page = the static app shell only; Streamlit's data travels over a websocket, so wrk cannot drive it
   page     c=10      7,585 req/s  p50=   1.04 ms  p90=   1.08 ms  p99=   1.53 ms  mem now 60 MB  
   page     c=100     8,103 req/s  p50=  12.10 ms  p90=  12.81 ms  p99=  19.56 ms  mem now 62 MB  
   peak memory under load: 62 MB
   (the first 1-user row is a warm-up: it fills every server's cache for both sectors)
   idle footprint: 61 MB
     1 users | load-to-ready p50=2.61s p95=2.61s max=2.61s ok=1/1 | click-to-result p50=0.36s p95=0.36s max=0.36s ok=1/1 | server 743 MB
     1 users | load-to-ready p50=0.44s p95=0.44s max=0.44s ok=1/1 | click-to-result p50=0.33s p95=0.33s max=0.33s ok=1/1 | server 955 MB
     5 users | load-to-ready p50=2.01s p95=2.04s max=2.04s ok=5/5 | click-to-result p50=1.60s p95=1.63s max=1.63s ok=5/5 | server 1480 MB
    10 users | load-to-ready p50=3.17s p95=4.93s max=4.93s ok=10/10 | click-to-result p50=3.45s p95=4.11s max=4.11s ok=10/10 | server 1532 MB
       return future_cell["future"].result()
       print(f"{n:>3} users | load-to-ready {summary(loads)} | click-to-result {summary(clicks)} | server {footprint(a.pid):.0f} MB", flush=True)
       return docker_memory(pid[7:])
       number, unit = float(value[:-3]), value[-3:]
   ValueError: could not convert string to float: ''
   CONTAINER DIED: OOMKilled=true
#### rerun of the crashed 40-user step
== next-static  memory cap 4.5g, 1 CPU  | up in 0.5 s | idle 52 MB
     1 users | load-to-ready p50=0.18s p95=0.18s max=0.18s ok=1/1 | click-to-result p50=0.12s p95=0.12s max=0.12s ok=1/1 | server 87 MB
    40 users | load-to-ready p50=1.86s p95=1.93s max=1.94s ok=40/40 | click-to-result p50=0.33s p95=0.38s max=0.39s ok=40/40 | server 86 MB

#### 2026-10-20 22:39  Debian 13 containers, server on 1 CPU, --memory 9g
== fastapi-vite  memory cap 9g, 1 CPU  | up in 0.5 s | idle 52 MB
   page     c=10      4,499 req/s  p50=   1.67 ms  p90=   2.02 ms  p99=   6.52 ms  mem now 54 MB  
   page     c=100     4,751 req/s  p50=  20.19 ms  p90=  23.79 ms  p99=  37.80 ms  mem now 61 MB  
   api      c=10     10,160 req/s  p50=   0.74 ms  p90=   0.91 ms  p99=   3.13 ms  mem now 79 MB  
   api      c=100     9,729 req/s  p50=  10.02 ms  p90=  12.44 ms  p99=  26.67 ms  mem now 82 MB  
   peak memory under load: 96 MB
== node-vite  memory cap 9g, 1 CPU  | up in 0.5 s | idle 27 MB
   page     c=10    100,300 req/s  p50=   0.07 ms  p90=   0.12 ms  p99=   0.25 ms  mem now 34 MB  
   page     c=100   106,560 req/s  p50=   0.88 ms  p90=   1.10 ms  p99=   2.53 ms  mem now 43 MB  
   api      c=10     79,394 req/s  p50=   0.08 ms  p90=   0.16 ms  p99=   0.49 ms  mem now 58 MB  
   api      c=100    74,121 req/s  p50=   1.28 ms  p90=   1.57 ms  p99=   2.89 ms  mem now 59 MB  
   peak memory under load: 59 MB
== next-ssr  memory cap 9g, 1 CPU  | up in 0.7 s | idle 64 MB
   page     c=10        755 req/s  p50=   9.20 ms  p90=  17.37 ms  p99=  41.87 ms  mem now 255 MB  
   page     c=100       795 req/s  p50= 117.86 ms  p90= 170.10 ms  p99= 645.93 ms  mem now 365 MB  
   click    c=10      1,599 req/s  p50=   3.71 ms  p90=   9.81 ms  p99=  20.04 ms  mem now 331 MB  
   click    c=100     1,685 req/s  p50=  54.94 ms  p90=  70.81 ms  p99= 640.45 ms  mem now 420 MB  
   peak memory under load: 420 MB
== next-static  memory cap 9g, 1 CPU  | up in 0.5 s | idle 53 MB
   page     c=10      4,267 req/s  p50=   1.79 ms  p90=   2.23 ms  p99=   3.55 ms  mem now 55 MB  
   page     c=100     4,424 req/s  p50=  21.94 ms  p90=  25.44 ms  p99=  36.05 ms  mem now 64 MB  
   api      c=10      9,183 req/s  p50=   0.83 ms  p90=   1.02 ms  p99=   1.55 ms  mem now 81 MB  
   api      c=100     9,099 req/s  p50=  10.78 ms  p90=  12.99 ms  p99=  22.44 ms  mem now 84 MB  
   peak memory under load: 98 MB
== dash  memory cap 9g, 1 CPU  | up in 0.5 s | idle 59 MB
   page     c=10      4,236 req/s  p50=   1.82 ms  p90=   2.46 ms  p99=   6.32 ms  mem now 60 MB  
   page     c=100     4,091 req/s  p50=  23.74 ms  p90=  27.06 ms  p99=  43.08 ms  mem now 61 MB  
   callback c=10      4,419 req/s  p50=   1.71 ms  p90=   2.50 ms  p99=   6.30 ms  mem now 71 MB  
   callback c=100     4,347 req/s  p50=  21.88 ms  p90=  27.27 ms  p99=  41.82 ms  mem now 72 MB  
   peak memory under load: 72 MB
== streamlit  memory cap 9g, 1 CPU  | up in 1.4 s | idle 61 MB
   page = the static app shell only; Streamlit's data travels over a websocket, so wrk cannot drive it
   page     c=10      6,375 req/s  p50=   1.10 ms  p90=   1.58 ms  p99=  26.79 ms  mem now 62 MB  
   page     c=100     7,149 req/s  p50=  13.15 ms  p90=  16.30 ms  p99=  29.48 ms  mem now 64 MB  
   peak memory under load: 64 MB
== streamlit-naive  memory cap 9g, 1 CPU  | up in 1.3 s | idle 61 MB
   page = the static app shell only; Streamlit's data travels over a websocket, so wrk cannot drive it
   page     c=10      6,481 req/s  p50=   1.18 ms  p90=   1.38 ms  p99=   3.47 ms  mem now 62 MB  
   page     c=100     4,252 req/s  p50=  16.92 ms  p90=  62.63 ms  p99= 218.91 ms  mem now 63 MB  
   peak memory under load: 64 MB
#### 2026-10-20 22:49  Debian 13 containers, server on 1 CPU, --memory 9g
== streamlit-naive  memory cap 9g, 1 CPU  | up in 9.3 s | idle 61 MB
   page = the static app shell only; Streamlit's data travels over a websocket, so wrk cannot drive it
   page     c=10      5,174 req/s  p50=   1.34 ms  p90=   2.09 ms  p99=  38.66 ms  mem now 62 MB  
   page     c=100     5,829 req/s  p50=  14.13 ms  p90=  24.90 ms  p99= 102.29 ms  mem now 64 MB  
   peak memory under load: 64 MB
   (the first 1-user row is a warm-up: it fills every server's cache for both sectors)
   idle footprint: 63 MB
     1 users | load-to-ready p50=5.10s p95=5.10s max=5.10s ok=1/1 | click-to-result p50=0.36s p95=0.36s max=0.36s ok=1/1 | server 744 MB
     1 users | load-to-ready p50=0.57s p95=0.57s max=0.57s ok=1/1 | click-to-result p50=0.53s p95=0.53s max=0.53s ok=1/1 | server 926 MB
     5 users | load-to-ready p50=6.29s p95=6.29s max=6.29s ok=5/5 | click-to-result p50=4.72s p95=4.86s max=4.86s ok=5/5 | server 1790 MB
    10 users | load-to-ready p50=9.75s p95=10.88s max=10.88s ok=10/10 | click-to-result p50=9.64s p95=9.77s max=9.77s ok=10/10 | server 2200 MB
    20 users | load-to-ready p50=32.18s p95=37.09s max=37.09s ok=20/20 | click-to-result p50=17.75s p95=18.96s max=18.96s ok=20/20 | server 2666 MB
       return future_cell["future"].result()
   ConnectionResetError: [Errno 54] Connection reset by peer
```
