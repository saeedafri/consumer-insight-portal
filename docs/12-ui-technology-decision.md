# CIP UI — Technology Decision and Evidence

> **Superseded (20 Oct 2026)** by [`docs/Ui-Design-Claude/`](Ui-Design-Claude/00-README.md). Re-verified evidence, corrections to this document's figures (the "5-user wall" was a laptop test; several SIP issues are fixed), new benchmarks and the marketplace comparison are there.

**Question from the business team:** "The data is in MySQL. We used Streamlit for
SIP and MIP. Why not connect Streamlit to MySQL and just show the data?"

**Answer:** For an internal tool used by a handful of analysts, that approach is
fine, and it is the fastest way to get a screen up. For CIP, a product sold to
clients that must serve hundreds of people from one server, it is the wrong
foundation. The evidence is our own: two years of SIP and MIP history, MIP's own
load test, and side-by-side measurements on the same data.

We recommend **React (TypeScript) screens served by a Python FastAPI service**
on the server and MySQL database we already have. The design is in
[13-ui-system-design.md](13-ui-system-design.md).

Status: proposed · 18 October 2026 · O = observed in code, logs or measurement;
I = inference.

---

## 1. Summary

| | Finding | Evidence |
|---|---|---|
| 1 | **Streamlit's per-server ceiling is about 5 people working at once.** MIP's own load test: median wait 6.3 s at 5 users, 16.1 s at 10, 61.8 s at 30; throughput flat at ~0.5 page loads/s, one CPU core at 97–99 % | MIP `docs/superpowers/specs/2026-10-01-mdp-full-e2e-timing-ram-capacity-report.md:158-166` (O) |
| 2 | **Even well-written Streamlit is 15× slower under load than the recommended design.** Same 1 M-row table, 20 people opening the page at once: Streamlit with SQL totals 1.80 s median; React page + API 0.12 s | §4, measured 18 Oct 2026 (O) |
| 3 | **The "load the table and show it" pattern exhausts the server.** Same test: 2,988 MB peak memory for one 75 MB table; the API version used 44 MB | §4 (O) |
| 4 | **About 38 % of SIP's 1,028 commits went to sign-in, performance and Streamlit workarounds; 27 % to features.** Sign-in alone: 295 commits (28.7 %) | §2 (O) |
| 5 | **MIP:** 22 % of 743 deployed commits and 26 % of changed lines went to the same three categories; `st.rerun` calls grew 21 → 144 and `session_state` uses 404 → 1,727 in eight months | §3 (O) |
| 6 | **Both apps carry critical security issues that come from working around the framework** (unverified session cookies, cookies readable by scripts, forgery protection off), plus avoidable ones (shell-command pages, secrets in repositories) | §5.3 (O) |
| 7 | **Not everything is Streamlit's fault.** Most of the memory and the multi-second stalls came from our own choices: whole tables pulled into pandas, unbounded caches, an untuned database. Fixing those helps on any stack | §5 (O/I) |
| 8 | **What Streamlit cannot fix:** one process and one core serve every user, the whole page re-runs on every click, and the server cannot set a secure cookie | §5.1, Streamlit docs (O) |
| 9 | **The recommended stack adds $0 in licences and needs no new servers.** Serving 300 people at once on Streamlit would need 20–60 instances ($2,480–$7,440 a month); the recommended design needs the one we have ($124) | §7 (I, from O inputs) |

**What this document does not say:** that SIP and MIP should be rewritten now.
MIP's own review (2026-10-17) found its remaining cost is "a few unbounded caches
and one websocket payload" and advised against a rewrite while it has no
external clients. We agree for MIP today. CIP is different: it is being built
now, it is for clients, and its data code is already separate from its screens.

---

## 2. What SIP's history shows

Repository: `Code-Base/Modular-Code` (SIP), 1,028 commits, 25 Nov 2024 – 14 Oct 2026.
Commits were classified by subject keywords, then by files touched; ambiguous
ones were read by hand.

### 2.1 Where the effort went (O)

| Category | Commits | Share | Share of changed lines* |
|---|--:|--:|--:|
| Sign-in / logout / session / cookie | 295 | 28.7 % | 29.4 % |
| New features and data | 278 | 27.0 % | 32.9 % |
| Other bug fixes | 182 | 17.7 % | 11.6 % |
| Docs, tests, merges | 109 | 10.6 % | 10.2 % |
| Deploy / start-up | 68 | 6.6 % | 3.0 % |
| Performance / memory / caching | 49 | 4.8 % | 6.6 % |
| Streamlit workarounds | 47 | 4.6 % | 6.3 % |

\*Excluding four ~53,000-line revert/re-apply commits of September 2025.

Subjects undercount workarounds: **402 of 958 non-merge commits (42 %)** change
code that uses `st.rerun`, `session_state`, raw HTML or injected JavaScript.

Two sign-in crises account for 200 of the 295 sign-in commits:

- **September 2025 (91 commits).** Cookie, logout and infinite-loop fixes:
  `17cfbc1` "trying to fix infinite loop issue", `5de57f3` "Added Time sleep for
  Logout", `8f60cf0` "logout sleep increased", `10884c9` "Adding sleep for
  deleting Cookies".
- **April 2026 (109 commits, 22 on 9 April alone).** OIDC rewrite: `03e9fb1`
  "logout bridge … for streamlit version 1.45", `50547a0` "use st.html()
  instead of sandboxed components.html()", `9730a6c` "use meta-refresh after
  login so cookie is written before navigation".

Why sign-in is so hard on Streamlit (O, SIP code + Streamlit docs): Python code
cannot set a response cookie, `st.context.cookies` is read-only, so the cookie is
written by a JavaScript component that only arrives after another re-run. Hence
the sleeps, retries and meta-refresh redirects.

### 2.2 Performance and memory incidents (O, from SIP's own docs)

| When | What happened | Source |
|---|---|---|
| Jun–Jul 2026 | **With 1–2 users, memory reached ~3.4 GB on a ~4.9 GB server → out-of-memory kill → cold restart.** Real data frames were only ~450–500 MB | `docs/performance/enhancement-journey/02-problems-findings-fixes.md:36-53` |
| Jun 2026 | `st.cache_data` gave the Active page **~502 MB per user** (10 users ≈ 4.9 GB) | `sip_components/active_data.py:1647-1648` |
| Jun 2026 | One click = **2–4 full page re-runs**; 104 re-runs, 65 forced by `st.rerun()` | `02-problems-findings-fixes.md:112-118` |
| Jun 2026 | One click on Active ≈ **5.0–5.6 s**: dropdowns re-scan a 1.1 M-row frame, Plotly 2.2 s | `enhancement-journey/05-render-speed-research.md:17-24` |
| Jun 2026 | Clean-up code held Python's global lock and **froze all users** | `02-problems-findings-fixes.md:128-131` |
| Aug 2026 | **142 s stall** when the 24-hour cache expires | `docs/performance/2026-08-07-sip-speed-and-ram-investigation.md:91-96` |
| Oct 2026 | Store map click-to-render **max 221–242 s** (local run) | `server-logs/server-log.log` |
| Plan | Team's own estimate: **1 server per 10–15 users; 7–10 servers for 100 users** | `docs/performance/05-concurrency-and-scaling.md:55-60, 80-82` |

### 2.3 Code shape (O)

52,408 lines in 74 app files (+19,478 dead lines in `pages/old/`). Sign-in code
alone (`login.py` + `auth_utils.py`) is 4,295 lines touched by 267 commits.

| Pattern | Count | What it means |
|---|--:|---|
| `st.session_state` | 877 | State the framework would otherwise lose on every re-run |
| `unsafe_allow_html=True` | 194 | Raw HTML/CSS injected to get the look Streamlit does not offer |
| `st.rerun()` | 83 | Forced extra re-runs of the whole page |
| `<script` / `window.parent` | 34 / 21 | JavaScript reaching outside Streamlit's frame |
| Threads | 30 | Warm-up, clean-up and refresh work the framework has no hook for |
| `time.sleep` | 18 | Waiting for cookies and components |

Also: `patch_streamlit_splash.py` rewrites Streamlit's own installed `index.html`
at runtime to hide a white flash and its logo.

---

## 3. What MIP's history shows

Repositories: `market-data-stg` (deployed history: 743 non-merge commits,
Oct 2025 – Oct 2026, four authors) and `Code-Base/Real/CapIQReplacement`
(111 commits since June 2026).

### 3.1 Where the effort went (O, market-data-stg)

| Category | Commits | Share | Share of Python lines changed |
|---|--:|--:|--:|
| New features and data | 323 | 43.5 % | 47 % |
| Bug fixes | 199 | 26.8 % | 21 % |
| Sign-in | 72 | 9.7 % | 11.2 % (32,000 lines) |
| Performance | 53 | 7.1 % | 10.8 % |
| Streamlit workarounds | 41 | 5.5 % | 3.9 % |

- **Workaround code keeps spreading.** 239 of 743 commits add re-run, raw HTML,
  script or overlay code.
- **Workaround patterns grew fast.** Between February and October 2026:
  - `st.rerun` grew from 21 to 144.
  - `session_state` grew from 404 to 1,727.
  - Threads grew from 2 to 43.
- **Some fixes are trial and error.** About 100 commit subjects read that way, for example "still fixing login" and seven login commits on 14 May 2026.

MIP's `OIDC_FLOW.md` (2,118 lines) documents the sign-in workarounds:
- **Cookies:** the component frame cannot write cookies, so injected JavaScript checks `document.cookie` every 50 ms.
- **Login code exchange:** re-runs repeat the single-use exchange, so the app needs file-based deduplication in `/tmp`.
- **Logout:** it needs six fallbacks.

### 3.2 Incidents (O, MIP specs and logs)

| Date (2026) | What happened |
|---|---|
| 2 Jul | Audit: 0 of 24 actions met the 1 s target; median cold 12.7 s. Screening 23.5 s, of which ~0.9 s was SQL and the rest **nine page re-runs** |
| 3 Jul | Newsroom: 758 queries, 465 k rows into session memory, 92.9 s; memory 2,764 MB |
| 17 Jul | Home page blank 24–62 s: start-up code ran on **every re-run** |
| 19 Jul | A 2-second auto-refresh section crash-looped the app: 18 restarts, 503 errors |
| 30 Jul | A 136 MB file sent inside one websocket message broke the connection |
| 30 Sep | A PDF loop froze the server for every user |
| **1 Oct** | **Load test: throughput flat at ~0.5 page loads/s from 5 users; median wait 6.3 s (5 users), 16.1 s (10), 37.8 s (20), 61.8 s (30); one core at 97–99 %** |
| 17 Oct | Independent review: about 8 MB per extra session; 189 of 198 caches unbounded; recommends fixing, not rewriting |

The 1 October test is the single most important number in this document: it is
MIP's own team, on MIP's own staging server, showing that **every extra user
just queues** because one Python process does all the work.

---

## 4. What we measured

### 4.1 Same data, three ways (O)

A synthetic 1,000,000-row store table (75 MB, the shape of a SIP/MIP table) in
SQLite. One page: pick a sector, show stores open, a bar chart and a table by
state. Opened by 1, 5, 10 and 20 headless Chrome tabs at the same moment;
timer stops when the numbers are on screen. Memory sampled every 0.3 s.

| Pattern | Peak memory | Median, 1 user | Median, 20 at once | Slowest, 20 at once |
|---|--:|--:|--:|--:|
| **A. "Load the table, show it" in Streamlit** (`st.cache_data` on `SELECT *`, filter in pandas) | **2,988 MB** | 2.07 s (cold) | **5.91 s** | 8.17 s |
| **B. Streamlit done well** (SQL does the totals, only the small result cached) | 145 MB | 0.53 s | **1.80 s** | 2.71 s |
| **C. Recommended** (static page + FastAPI JSON, SQL totals, cached) | **44 MB** | 0.25 s (cold) | **0.12 s** | 0.12 s |

C also served **5,627 requests/s** from one worker at 100 concurrent
connections, 99th percentile 26 ms.

Reading it honestly:
- A → B is our own coding: aggregate in SQL, cache only small results. That fix
  takes memory from 2,988 MB to 145 MB **and must be done whatever the stack**.
- B → C is the framework. Same SQL, same cache; the only difference is that
  Streamlit re-runs a Python script per visitor in one process, and C hands out
  ready-made numbers. That costs **15× at 20 users** and grows with every user.

### 4.2 The real CIP page (O)

Today's CIP Overview page (Streamlit, already written the "B" way) against the
same page as static HTML + FastAPI, both on the CIP data copy:

| People opening at once | 1 | 5 | 10 | 20 |
|---|--:|--:|--:|--:|
| CIP on Streamlit, median | 0.56 s | 1.16 s | 1.99 s | **4.36 s** |
| Same page, recommended design | 0.13 s | 0.04 s | 0.06 s | **0.12 s** |

FastAPI on CIP data: 1 worker 5,744 req/s cached, 1,614 req/s with a database
query each time; 4 workers 16,483 and 3,746. About 140 MB per worker, flat.

### 4.3 Limits of these tests

- They ran on an Apple-silicon laptop, which is roughly 2–3× faster per core
  than an Azure vCPU (I). Absolute times on Azure will be higher; the ratios
  hold because both sides ran on the same machine.
- SQLite stood in for MySQL. Database time is the same for B and C, so it
  does not change the comparison.
- MIP's 1 October test (§3.2) ran on real Azure staging and agrees with the
  shape of these results.

### 4.4 How to re-run

```bash
cd consumer-insight-portal
python scripts/ui_benchmark/make_db.py /tmp/stores.db                       # 1 M rows
streamlit run scripts/ui_benchmark/streamlit_naive.py --server.port 8698 -- /tmp/stores.db
streamlit run scripts/ui_benchmark/streamlit_sql.py   --server.port 8696 -- /tmp/stores.db
NAIVE_DB=/tmp/stores.db uvicorn api_page:app --app-dir scripts/ui_benchmark --port 8697
# headless Chrome with DevTools on 9333, then for each server:
python scripts/ui_benchmark/page_load.py http://127.0.0.1:8698/ "Stores open" <server pid> 1,5,10,20
```

---

## 5. Framework or our code?

### 5.1 Built into Streamlit (cannot be coded away)

| Behaviour | Streamlit's own documentation | Effect we saw |
|---|---|---|
| Whole script re-runs on every interaction | "Streamlit reruns your script from top to bottom every time you interact with your app." ([session state](https://docs.streamlit.io/develop/concepts/architecture/session-state)) | 2–4 renders per click (SIP); 9 re-runs for one Screening visit (MIP); start-up code run on every click (MIP, 17 Jul) |
| Fragments help only partly | "When a user interacts with an input widget outside a fragment, the full script reruns as usual." ([fragments](https://docs.streamlit.io/develop/concepts/architecture/fragments)) | SIP uses 5, MIP 8; most pages still full re-runs |
| One session per tab, held by the server | "Each browser tab or window creates its own WebSocket connection, resulting in a separate session." ([architecture](https://docs.streamlit.io/develop/concepts/architecture/architecture)) | Memory and CPU grow with every open tab |
| Scaling out needs sticky sessions | "Enable session affinity (also known as stickiness) in your proxy." (architecture) | Every extra server repeats every cache |
| Cached data is copied per caller | "Within each user session, an `@st.cache_data`-decorated function returns a *copy* of the cached return value." ([caching](https://docs.streamlit.io/develop/concepts/architecture/caching)) | ~502 MB per user (SIP) |
| State is lost when the tab closes | "As soon as you close the tab, everything stored in Session State is lost." (session state) | Filters lost on refresh; SIP built `local_storage_manager.py` |
| One Python process serves all sessions (I, from architecture + measurement) | — | MIP flat at 0.5 pages/s; SIP clean-up froze all users |
| The server cannot set an HttpOnly cookie of its own; custom cookies go through JavaScript components (O, code) | — | 295 + 72 sign-in commits; sleeps and meta-refreshes |
| No control of first paint | — | SIP and MIP both patch Streamlit's installed `index.html` |
| All traffic over one websocket; App Service cannot time it | — | Azure averages of 15–60 ms hide 22–45 s peaks |

### 5.2 Fair points in Streamlit's favour

- **Native sign-in exists.** Since version 1.42, `st.login()` does OIDC and
  stores the identity cookie for you
  ([docs](https://docs.streamlit.io/develop/api-reference/user/st.login)). SIP
  moved to OIDC in April 2026 but kept its hand-made cookie. Part of SIP's
  sign-in pain was therefore avoidable (I). Whether coresight.com's WordPress
  identity provider works with `st.login` is untested.
- **URL state is possible.** `st.query_params` exists; MIP uses it 121 times.
  It is not the same as real routes, but "no URL state" would be unfair.
- **It is genuinely the fastest way to a working screen,** and for internal
  pages with a few users the ceiling never bites.

### 5.3 Our own choices (avoidable on any stack)

| Problem | SIP | MIP |
|---|---|---|
| Whole tables pulled into pandas instead of totals from SQL | ~1.1 M rows per page | 465 k rows for Newsroom |
| Caches with no size limit | 180 MB per month viewed, kept forever | 189 of 198 caches |
| Database tuning | 2 GiB buffer pool; 16 MB in-memory temp limit → 170 s query | 2 GB buffer pool against a 355 GB schema; unindexed scans 13–84 s |
| Heavy work in the web process | Excel build 2.3 GB | 10-K parsing 3.7 GB spike |
| Unpinned dependencies | all but Streamlit and aggrid | — |
| Secrets in repositories | `.streamlit/secrets.toml`, DB password fallbacks | committed `.env2` with production credentials |
| Pages that run shell commands | `pages/logs.py`, no login | `app/pages/logs.py`, no login |
| Pages with the login check commented out | 7 | 6 |

**Balanced conclusion.** Our choices made the problems *big*; Streamlit decided
their *shape* and turned every one of them into per-user memory and a
queue behind a single core. CIP's data layer already does the right things
(SQL aggregation, a pre-computed cube, verified numbers), so the remaining
limit for CIP is exactly the part that cannot be coded away.

---

## 6. Every option, ranked

Weights reflect CIP's needs: a client product on one 4–8 GB server.
Scores are 1 (poor) to 5 (excellent); the reasons follow the table.

| Criterion | Weight |
|---|--:|
| Speed with many users at once | 20 |
| Memory on a 4–8 GB server | 15 |
| Security by default | 15 |
| Design and user-experience ceiling | 15 |
| Reuse of CIP's verified data code / time to build | 15 |
| Team skills and hiring pool | 10 |
| Licence and hosting cost | 10 |

| Rank | Option | Speed | Memory | Security | UX | Reuse | Team | Cost | **Score /500** | Verdict |
|--:|---|--:|--:|--:|--:|--:|--:|--:|--:|---|
| 1 | **React SPA (Vite, or Next.js static export) + FastAPI** | 5 | 5 | 5 | 5 | 4 | 4 | 5 | **475** | **Best** |
| 2 | Vue or Svelte + FastAPI | 5 | 5 | 5 | 5 | 4 | 2 | 5 | 455 | Good tech, weaker team fit |
| 3 | React + Go or .NET API | 5 | 5 | 5 | 5 | 2 | 3 | 5 | 435 | Rewrite of verified data code for speed we do not need |
| 4 | Angular + FastAPI | 4 | 5 | 5 | 5 | 3 | 2 | 5 | 420 | Heavier, nobody on the team uses it |
| 5 | Dash (Plotly) | 3 | 4 | 3 | 3 | 4 | 3 | 5 | 350 | **Best pure-Python option**; acceptable for internal analytics |
| 6 | Streamlit written well (SQL totals, `st.login`, fragments) | 2 | 3 | 3 | 2 | 5 | 4 | 5 | 325 | Acceptable for internal tools under ~10 concurrent users |
| 7 | Power BI Embedded | 4 | 5 | 4 | 2 | 2 | 3 | 1 | 315 | Not optimal: ~$736/month and a Microsoft look |
| 8 | Reflex, NiceGUI, Panel, Shiny, Solara, Taipy | 2 | 2 | 3 | 3 | 4 | 2 | 5 | 290 | Not optimal: Streamlit's stateful model with smaller communities |
| 9 | Superset / Metabase | 3 | 2 | 3 | 2 | 2 | 3 | 4 | 265 | Not optimal: heavy to run, branding and embedding cost |
| 10 | **Streamlit, "load the table and show it"** (the SIP/MIP pattern) | 1 | 1 | 2 | 2 | 5 | 4 | 5 | **260** | **Worst realistic option** for a client portal |
| 11 | Gradio, Mesop | 1 | 2 | 1 | 1 | 3 | 2 | 5 | 195 | Ruled out: AI-demo tools; Mesop archived 2 Oct 2026; Gradio has many path-traversal advisories |

### Why the winner wins

- **Speed under load:** measured 0.12 s at 20 simultaneous users where
  Streamlit took 1.80–5.91 s (§4). The browser does sorting, filtering and
  chart toggles itself, with no server round trip.
- **Memory:** about 140 MB per worker, flat as users grow (§4.2). Production
  runs three workers in under 0.5 GB.
- **Security:** a normal request/response server sets an HttpOnly, Secure,
  SameSite session cookie and checks it on every call; React escapes output by
  default; anti-forgery tokens are standard. These are the exact controls SIP
  and MIP could not get from Streamlit.
- **Experience:** real routes, shareable links, Back button, no flashes or
  full-page re-runs, and full control of Coresight's look.
- **Reuse:** CIP's ~5,000-line data layer moves behind FastAPI unchanged, so
  its verified 667/667 and 788/788 cell matches carry over.
- **Team:** React is already used on SMS-UI and ems-frontend; FastAPI is
  Python, the language of every data project we have. React is used by 44.7 %
  of developers (Stack Overflow 2025), the largest hiring pool.
- **Cost:** MIT/Apache licences; runs on the existing App Service.

### Why not the runners-up

- **Next.js in server mode:**
  - It would add a Node process to the one box.
  - It had two critical vulnerabilities in 2025: CVE-2025-29927, a middleware sign-in bypass rated CVSS 9.1, and CVE-2025-55182, remote code execution through Server Components rated CVSS 10.
  - We don't need server rendering behind a login.
  - Next.js as a static export is fine and counts as option 1.
- **Go, .NET or Node backends:**
  - They are faster on paper. TechEmpower Round 23 with a database query: ASP.NET Core 609,967 req/s, FastAPI 109,167.
  - FastAPI's figure is already several hundred times CIP's need.
  - Switching would mean rewriting the data code we have already verified.
- **Dash:**
  - Its callbacks are stateless and scale with workers, so it is the right answer if the team must stay pure Python.
  - It has a lower design ceiling, and Plotly is 1.4 MB gzipped.
  - It still runs a Python round trip per interaction.

### Why the worst are worst

- **"Load the table and show it" on Streamlit:**
  - Measured 2,988 MB for one table at 20 users. That is three-quarters of a 4 GB staging server, for one page.
  - SIP's history shows where this leads: out-of-memory restarts with 1–2 users.
  - MIP's history shows the same: 18 restarts in one day.
- **Gradio and Mesop:** these are built for AI demos. Mesop's repository is archived, and Gradio has a long list of 2024–2026 file-access advisories.
- **Power BI Embedded and Tableau:**
  - The smallest Power BI capacity costs more each month than six production servers.
  - Clients would see a Microsoft or Tableau interface instead of Coresight's.

---

## 7. Long-run cost

### 7.1 Hosting (I, inputs O)

| Users working at the same moment | Streamlit servers needed* | Streamlit monthly (P1v3 $124) | Recommended servers | Recommended monthly |
|--:|--:|--:|--:|--:|
| 10 | 1–2 | $124–248 | 1 | $124 |
| 50 | 4–10 | $496–1,240 | 1 | $124 |
| 100 | 7–20 | $868–2,480 | 1 | $124 |
| 300 | 20–60 | $2,480–7,440 | 1 | $124 |

\*Low end: SIP's own estimate of 10–15 users per server
(`05-concurrency-and-scaling.md`). High end: MIP's measured ~5 users per core
before waits pass 6 s. Prices: Azure App Service Linux, Central US, P1v3
$0.17/h. Streamlit also needs sticky sessions, and every server repeats every
cache.

### 7.2 Developer time (I, inputs O)

| | SIP (23 months) | MIP (12 months) |
|---|--:|--:|
| Commits on sign-in + performance + framework workarounds | 391 of 1,028 (38 %) | 166 of 743 (22 %) |
| Commits on new features and data | 278 (27 %) | 323 (43.5 %) |

- **Sign-in becomes a one-off cost.** On the recommended stack, sign-in is a standard OIDC library flow, written once in the shared `coresight-platform` package and reused by CIP, CIQ, MIP and MDB. SIP spent 295 commits on it and MIP 72.
- **Performance work moves to the database layer, not the framework.** It is still needed (§5.3), but it stops multiplying per user.
- **Workaround work largely disappears.** There's no rerun control, no `session_state` bookkeeping and no HTML injection to maintain.

**Estimate for one product:**
- **Plumbing share:** if it falls from about 30 % (the SIP/MIP average) to about 10 %, roughly 20 % of a developer's year (about 10 weeks) moves to features. The 10 % is an assumption based on typical web projects; it was not measured here.
- **Across four products,** that is about 40 developer-weeks a year.

**Upfront cost, honestly:**
- **More work at first.** The first product on the new stack takes longer than another Streamlit app, an estimated 11 weeks for CIP, since its data layer and Streamlit pages already exist.
- **Repaid within the first year.** The time saved in §7.2 covers this.
- **Shared kit.** CIQ, MIP and MDB then start from the shared UI kit and service core.

### 7.3 Risk cost

Both current apps carry security findings that would be expensive in a client
product:
- unverified session cookies
- cookies readable by page scripts
- forgery protection switched off
- pages that run shell commands without a login
- production credentials committed to a repository

A data leak or a breach report to clients costs more than any line above. The
recommended stack removes the framework-driven ones by design (§6). The others
need fixing regardless and are tracked separately with engineering.

---

## 8. When we would choose differently

| If… | Then… |
|---|---|
| The screen is internal, for fewer than ~10 people at once | Streamlit written well (§5.2) is the cheapest choice. CIP's Mappings, Data Health and Publications pages stay on it |
| The team cannot staff any JavaScript | Dash, with all state in the browser (`dcc.Store`) and multiple gunicorn workers |
| Clients only need monthly static reports | Generate Excel/PDF from the existing data layer; no portal needed |
| One page needs heavy ad-hoc analytics over hundreds of millions of rows | Add DuckDB inside the service with a memory cap before considering ClickHouse |
| An existing Streamlit app (SIP, MIP) is slow today | Fix its data handling first (§5.3), as MIP's own review recommends. Migrate only when it gets external clients or needs more than ~10 concurrent users |

---

## 9. Sources

Our evidence (repository paths):
- SIP: `Code-Base/Modular-Code` git history; `docs/performance/**`;
  `sip_components/active_data.py`; `.streamlit/config.toml`; `pages/logs.py`
- MIP: `market-data-stg` git history; `Code-Base/Real/CapIQReplacement/docs/superpowers/specs/2026-10-01-mdp-full-e2e-timing-ram-capacity-report.md`,
  `2026-10-17-independent-investigation-design.md`, `2026-10-17-independent-audit-and-build-plan-design.md`, `OIDC_FLOW.md`
- Azure usage export `SIP & MIP Info.xlsx` (last 3 months)
- Benchmarks: `scripts/ui_benchmark/` (this repository), run 18 Oct 2026

Public sources:
- Streamlit: [architecture](https://docs.streamlit.io/develop/concepts/architecture/architecture),
  [session state](https://docs.streamlit.io/develop/concepts/architecture/session-state),
  [caching](https://docs.streamlit.io/develop/concepts/architecture/caching),
  [fragments](https://docs.streamlit.io/develop/concepts/architecture/fragments),
  [st.login](https://docs.streamlit.io/develop/api-reference/user/st.login)
- [Dash: sharing data between callbacks](https://dash.plotly.com/sharing-data-between-callbacks)
- [Reflex state overview](https://reflex.dev/docs/state/overview/) · [Mesop repository (archived)](https://github.com/mesop-dev/mesop)
- [Azure App Service Linux pricing](https://azure.microsoft.com/en-us/pricing/details/app-service/linux/)
- [Azure MySQL Flexible Server tiers](https://learn.microsoft.com/en-us/azure/mysql/flexible-server/concepts-service-tiers-storage)
- [TechEmpower Round 23](https://www.techempower.com/blog/2025/03/17/framework-benchmarks-round-23/)
- [Stack Overflow Developer Survey 2025](https://survey.stackoverflow.co/2025/technology)
- [CVE-2025-29927](https://fastly.com/blog/cve-2025-29927-authorization-bypass-in-next-js) ·
  [CVE-2025-55182](https://rapid7.com/blog/post/etr-react2shell-cve-2025-55182-critical-unauthenticated-rce-affecting-react-server-components)
- [Power BI Embedded capacity](https://learn.microsoft.com/en-us/power-bi/developer/embedded/embedded-capacity) ·
  [Metabase pricing](https://metabase.com/pricing)
