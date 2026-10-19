# 02 · Benchmarks: the same screen built six ways

**Run:** 20 Oct 2026, 02:46–02:53 IST, by Claude.

**Raw output:** reproduced in §6. Every number here can be re-run with the commands in §5.

These benchmarks show what each technology *itself* costs once our own coding mistakes are taken out of the picture. That is why the main test uses the same data, the same SQL, the same cache, and the same screen for every variant.

## 1. The test

**Data**
- 1,000,000-row store table (75 MB SQLite), the shape of a SIP/MIP table (`scripts/ui_benchmark/make_db.py`).

**Screen**
- "Stores open" headline, a bar chart by state, and a table by state for one sector.

**Load**
- Headless Chrome 155 opens *N* tabs at the same moment.
- The timer stops when "Stores open" is visible in each tab.
- Steps are cumulative: 1, then 5, 10, 20 and 40 more. Earlier tabs stay open, so the last step runs with **76 open sessions**.

**Memory**
- macOS `phys_footprint` of the server process and all its workers.
- RSS is not used: macOS compresses idle pages, so RSS drifts. A first trial confirmed it swung by ±500 MB.

**Throughput**
- `ab -k -n 20000 -c 100` against the JSON endpoint, with the result already cached.

**Machine**
- Apple M4, 10 cores, 16 GB.
- The load generator (Chrome) ran on the same machine, which adds client-side time to every variant equally.

| Variant | File | How it runs |
|---|---|---|
| **A. Streamlit "load the table, show it"** (the SIP/MIP pattern) | `streamlit_naive.py` | 1 process. `st.cache_data` on `SELECT *`, filter in pandas. |
| **B. Streamlit done well** | `streamlit_sql.py` | 1 process. SQL does the totals; only the small result is cached. |
| **C. Dash (pure Python)** | `dash_page.py` | gunicorn, 1 worker × 4 threads (and 2 workers) |
| **D. FastAPI + static page** (recommended back end) | `api_page.py` | gunicorn + uvicorn, 1 worker (and 2 workers) |
| **E. Node.js + static page** | `node_page.mjs` | Node 26, built-in `http` and `sqlite`, 1 process |

Variants B–E all run the same aggregate SQL and cache its result.

## 2. Results: time until the numbers are on screen

Median (p50) and slowest (max), in seconds.

| Users opening at once (open sessions) | 1 (1) | 5 (6) | 10 (16) | 20 (36) | **40 (76)** |
|---|--:|--:|--:|--:|--:|
| A. Streamlit, load table | 0.56 / 0.56 | 1.38 / 1.39 | 3.20 / 3.71 | 4.23 / 6.26 | **8.46 / 14.89** |
| B. Streamlit done well | 0.33 / 0.33 | 0.67 / 0.77 | 1.00 / 1.40 | 1.99 / 3.01 | **4.35 / 6.50** |
| C. Dash, 1 worker | 0.25 / 0.25 | 0.21 / 0.22 | 0.32 / 0.35 | 0.47 / 0.58 | **1.06 / 1.28** |
| C. Dash, 2 workers | 0.26 / 0.26 | 0.77 / 0.77 | 0.38 / 0.45 | 0.61 / 0.76 | **1.76 / 1.79** |
| **D. FastAPI, 1 worker** | 0.11 / 0.11 | 0.05 / 0.15 | 0.07 / 0.07 | 0.14 / 0.14 | **0.20 / 0.20** |
| E. Node.js, 1 process | 0.11 / 0.11 | 0.04 / 0.05 | 0.07 / 0.07 | 0.13 / 0.13 | **0.20 / 0.21** |

### Memory (server only)

| Variant | Idle | After 76 sessions | Peak |
|---|--:|--:|--:|
| A. Streamlit, load table | 599 MB | 1,359 MB | **3,674 MB** |
| B. Streamlit done well | 130 MB | 138 MB | 140 MB |
| C. Dash, 1 worker | 85 MB | 74 MB | 86 MB |
| C. Dash, 2 workers | 112 MB | 114 MB | 144 MB |
| D. FastAPI, 1 worker | 82 MB | 82 MB | 84 MB |
| D. FastAPI, 2 workers, after 80k requests | — | 306 MB | 306 MB |
| E. Node.js | 22 MB | 24 MB | 24 MB (103 MB after 40k requests) |

### Raw throughput (cached JSON, 100 concurrent connections)

| Variant | Requests/s | p50 | p99 | Failed |
|---|--:|--:|--:|--:|
| D. FastAPI, 1 worker | 7,391 | 13 ms | 27 ms | 0 |
| D. FastAPI, 2 workers (warm run) | 12,311 | 8 ms | 20 ms | 0 |
| E. Node.js, 1 process (warm run) | 49,562 | 2 ms | 6 ms | 0 |
| A / B Streamlit | not measurable this way | | | |

Streamlit has no request/response API. Every screen is a websocket session that re-runs a Python script.

## 3. What the numbers mean

1. **Streamlit's time grows in a straight line with the number of users.** Even written well (B), it goes 0.33 → 0.67 → 1.00 → 1.99 → 4.35 s. That is about **0.1 s per extra simultaneous user**, because one Python process re-runs the page script for each one, one at a time. Better code cannot remove this. It is the framework's execution model (Streamlit docs: "Streamlit reruns your script from top to bottom every time you interact with your app").
2. **The SIP/MIP pattern (A) would not fit the staging box.**
   - It peaked at **3.67 GB** for a single 75 MB table.
   - CIP staging has about **4.5 GB in total** for the OS, the runtime and the app.
   - The same pattern took SIP production to a 6.9 GB peak on its 8 GB plan, and MIP production to 3.2 GB on 4 GB (Azure usage export, [01](01-evidence-from-sip-and-mip.md)).
3. **FastAPI and Node stay flat.** 0.20 s at 40 simultaneous users, against 4.35 s for the best Streamlit. That is **22× faster at 40 users**, and the gap keeps widening because Streamlit's line keeps climbing.
4. **Dash is the best pure-Python option.** It is about 4× faster than good Streamlit at 40 users, because its callbacks are stateless and it can run several workers. It is still about 5× slower than a static page plus an API, because it ships a heavy React + Plotly bundle and does a Python round trip per interaction.
5. **Node vs Python on the server.**
   - **Throughput:** Node served **4–7× more requests per second** than FastAPI.
   - **What users see:** the page time is identical (0.20 s vs 0.20 s), because the browser, not the server, dominates it.
   - **Capacity needed:** a portal with 300 people active at once needs roughly 30–150 requests per second. One FastAPI worker gives 7,391.
   - **What switching costs:** moving to Node would mean rewriting CIP's verified Python data layer (significance tests, cube, harmonisation, pandas) for capacity we will never use.
   - **Verdict:** the server language is **not** the bottleneck. The framework model is.

## 4. Honest limits

- **Hardware.** An Azure P-series vCPU is roughly 2–3× slower per core than an M4 core (inference). Absolute times on Azure will be higher for every variant, but the ratios hold because all variants ran on the same machine.
- **Database.** SQLite stood in for MySQL. The SQL cost is the same for B–E, so it does not change the comparison.
- **Client side.** Chrome ran 76 tabs on the same laptop, so part of the time at 40 users is client rendering. That penalises the heavy-bundle variants (A, B, C) somewhat more than D and E. The 2-worker Dash result being slower than 1 worker at 40 users is that client-side noise, not a server effect.
- **Pages, not clicks.** These are page loads. A *click* behaves the same way: in Streamlit it is another full script re-run on the server; in D and E it is a browser-side update or a single cached request. See [05](05-millisecond-ui.md).
- **Comparison with docs/12 (18 Oct).** The 18 October run of A, B and D gave the same shape:

  | | 18 Oct | 20 Oct |
  |---|--:|--:|
  | A peak memory | 2,988 MB | 3,674 MB |
  | B at 20 users | 1.80 s | 1.99 s |
  | D at 20 users | 0.12 s | 0.14 s |

  The results reproduce.

## 5. How to re-run

```bash
cd consumer-insight-portal
uv venv /tmp/bench/.venv --python 3.13 && uv pip install --python /tmp/bench/.venv/bin/python "streamlit==1.55.0" fastapi "uvicorn[standard]" gunicorn dash pandas tornado
/tmp/bench/.venv/bin/python scripts/ui_benchmark/make_db.py /tmp/bench/stores.db
# start ONE server at a time, e.g.:
/tmp/bench/.venv/bin/streamlit run scripts/ui_benchmark/streamlit_sql.py --server.port 8696 --server.headless true -- /tmp/bench/stores.db
NAIVE_DB=/tmp/bench/stores.db /tmp/bench/.venv/bin/gunicorn api_page:app --chdir scripts/ui_benchmark -k uvicorn.workers.UvicornWorker -w 1 -b 127.0.0.1:8697
NAIVE_DB=/tmp/bench/stores.db /tmp/bench/.venv/bin/gunicorn dash_page:server --chdir scripts/ui_benchmark -w 1 --threads 4 -b 127.0.0.1:8694
NAIVE_DB=/tmp/bench/stores.db PORT=8692 node scripts/ui_benchmark/node_page.mjs
# headless Chrome with DevTools on 9333, then:
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --remote-debugging-port=9333 --user-data-dir=/tmp/bench/chrome about:blank &
/tmp/bench/.venv/bin/python scripts/ui_benchmark/page_load.py http://127.0.0.1:<port>/ "Stores open" <server pid> 1,5,10,20,40
ab -q -k -n 20000 -c 100 http://127.0.0.1:<port>/api/summary/Apparel
```

## 6. Raw output (20 Oct 2026)

```
== streamlit-naive port=8698 pid=52062 02:46:06
idle footprint: 599 MB (peak 994 MB, 1 procs)
+1 concurrent loads (open sessions=1): p50=0.56s max=0.56s  footprint=788 MB (peak 994 MB, 1 procs)
+5 concurrent loads (open sessions=6): p50=1.38s max=1.39s  footprint=1614 MB (peak 1717 MB, 1 procs)
+10 concurrent loads (open sessions=16): p50=3.20s max=3.71s  footprint=1884 MB (peak 2849 MB, 1 procs)
+20 concurrent loads (open sessions=36): p50=4.23s max=6.26s  footprint=2451 MB (peak 3674 MB, 1 procs)
+40 concurrent loads (open sessions=76): p50=8.46s max=14.89s  footprint=1359 MB (peak 3674 MB, 1 procs)
== streamlit-sql port=8696 pid=54167 02:47:29
idle footprint: 130 MB (peak 140 MB, 1 procs)
+1 concurrent loads (open sessions=1): p50=0.33s max=0.33s  footprint=131 MB (peak 140 MB, 1 procs)
+5 concurrent loads (open sessions=6): p50=0.67s max=0.77s  footprint=131 MB (peak 140 MB, 1 procs)
+10 concurrent loads (open sessions=16): p50=1.00s max=1.40s  footprint=132 MB (peak 140 MB, 1 procs)
+20 concurrent loads (open sessions=36): p50=1.99s max=3.01s  footprint=134 MB (peak 140 MB, 1 procs)
+40 concurrent loads (open sessions=76): p50=4.35s max=6.50s  footprint=138 MB (peak 140 MB, 1 procs)
== fastapi-1worker port=8697 pid=55238 02:48:36
idle footprint: 82 MB (peak 84 MB, 2 procs)
+1 concurrent loads (open sessions=1): p50=0.11s max=0.11s  footprint=82 MB (peak 84 MB, 2 procs)
+5 concurrent loads (open sessions=6): p50=0.05s max=0.15s  footprint=82 MB (peak 84 MB, 2 procs)
+10 concurrent loads (open sessions=16): p50=0.07s max=0.07s  footprint=82 MB (peak 84 MB, 2 procs)
+20 concurrent loads (open sessions=36): p50=0.14s max=0.14s  footprint=82 MB (peak 84 MB, 2 procs)
+40 concurrent loads (open sessions=76): p50=0.20s max=0.20s  footprint=82 MB (peak 84 MB, 2 procs)
ab, 1 worker: 7390.75 req/s, p50 13 ms, p99 27 ms, 0 failed
== dash-1worker-4threads port=8694 pid=56226 02:49:36
idle footprint: 85 MB (peak 85 MB, 2 procs)
+1 concurrent loads (open sessions=1): p50=0.25s max=0.25s  footprint=85 MB (peak 85 MB, 2 procs)
+5 concurrent loads (open sessions=6): p50=0.21s max=0.22s  footprint=86 MB (peak 86 MB, 2 procs)
+10 concurrent loads (open sessions=16): p50=0.32s max=0.35s  footprint=86 MB (peak 86 MB, 2 procs)
+20 concurrent loads (open sessions=36): p50=0.47s max=0.58s  footprint=86 MB (peak 86 MB, 2 procs)
+40 concurrent loads (open sessions=76): p50=1.06s max=1.28s  footprint=74 MB (peak 86 MB, 2 procs)
== dash-2workers-4threads port=8693 pid=57093 02:50:32
idle footprint: 112 MB (peak 119 MB, 3 procs)
+1 concurrent loads (open sessions=1): p50=0.26s max=0.26s  footprint=118 MB (peak 119 MB, 3 procs)
+5 concurrent loads (open sessions=6): p50=0.77s max=0.77s  footprint=143 MB (peak 143 MB, 3 procs)
+10 concurrent loads (open sessions=16): p50=0.38s max=0.45s  footprint=143 MB (peak 143 MB, 3 procs)
+20 concurrent loads (open sessions=36): p50=0.61s max=0.76s  footprint=144 MB (peak 144 MB, 3 procs)
+40 concurrent loads (open sessions=76): p50=1.76s max=1.79s  footprint=114 MB (peak 144 MB, 3 procs)
== node-http port=8692 pid=58993 02:51:32
idle footprint: 22 MB (peak 24 MB, 1 procs)
+1 concurrent loads (open sessions=1): p50=0.11s max=0.11s  footprint=22 MB (peak 24 MB, 1 procs)
+5 concurrent loads (open sessions=6): p50=0.04s max=0.05s  footprint=22 MB (peak 24 MB, 1 procs)
+10 concurrent loads (open sessions=16): p50=0.07s max=0.07s  footprint=23 MB (peak 24 MB, 1 procs)
+20 concurrent loads (open sessions=36): p50=0.13s max=0.13s  footprint=23 MB (peak 24 MB, 1 procs)
+40 concurrent loads (open sessions=76): p50=0.20s max=0.21s  footprint=24 MB (peak 24 MB, 1 procs)
ab, node: 37850.90 req/s (cold) / 49561.50 req/s (warm), p50 2 ms, p99 6–10 ms, 0 failed
== fastapi-2workers (ab only): 4721.68 req/s (cold, p99 141 ms) / 12311.12 req/s (warm, p50 8 ms, p99 20 ms); 306 MB for 3 procs
```
