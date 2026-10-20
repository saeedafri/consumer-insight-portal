# 16 · The CIP portal: every survey, Coresight colours, tested on a 1-core 4 GB staging box

**Built and tested:** 20–21 Oct 2026, by Claude.

**Code:**
- [`web/`](../../web/src): React 19 + Vite + TypeScript, ECharts;
- [`api/main.py`](../../api/main.py): FastAPI;
- [`deploy/Dockerfile`](../../deploy/Dockerfile): the one container for the server.

**Screenshots:** [`ui/portal/`](ui/portal/).

## The answer in one table

| Question | Answer |
|---|---|
| **How many people at once on staging (1 CPU, 4 GB)?** | **About 6,000 simultaneous users at p95 41 ms, with 0 errors.** 8,000 still had 0 errors, but p95 rose to 56–293 ms between runs. At 10,000 the single core is saturated. Each simulated user clicks every 10 s on average, and every click hits the server. |
| **How much RAM?** | The API peaked at **1.3 GB** at 10,000 users (580 MB at 4,000), against a 4 GB limit. The response cache is capped at 256 MB per worker, however big the archive gets. |
| **How fast is a screen in the browser?** | **0.34–0.52 s** from navigation until fully drawn, for every screen. Browser memory is 7–30 MB per screen, and 46 MB after 15 screens in one tab. |
| **Does it cover every survey?** | Yes: all **328 surveys and waves from 2018 to 2026**, trackers plus annual and ad hoc studies, with search across every question. |
| **Colours?** | Coresight 2026 palette and chart rules only (§2). |

## 1. What was built

The REA findings on the Lovable app (Evidence `ev_7a2eb49b…dcd2`):
- it's Vite + React with Recharts, in 4 JavaScript chunks (1.05 MB);
- it makes **no API calls**: all 56 questions of one wave are compiled into the bundle, so it can only ever show that survey.

We kept its layout ideas (dark rail, question list beside the chart, heat-map cross-tab, respondent-view preview) and rebuilt it on the API so that every survey works.

| Screen | What it does | Picture |
|---|---|---|
| **Survey library** | All 328 waves, latest tracker first, archive by year; filter by type, year, title or module | [01](ui/portal/01-library.png) |
| **Search questions** | Every question wording since 2018, with how many waves asked it. Opens in its latest wave or as a trend | [02](ui/portal/02-search.png) |
| **Overview** | The headline is the wave's biggest *significant* move, computed rather than hand-written. KPI cards, top 8 moves, comparison status, one chart per section. Demographic shifts (sample mix) are left out of "news" | [03](ui/portal/03-overview-oct19.png), [04](ui/portal/04-overview-oct12.png) |
| **Question explorer** | Bars, columns, stacked, donut and table, offering only the types valid for the question. Total, by gender, by generation or all columns; sort; grid rows; CSV | [05](ui/portal/05-explorer-bars.png)–[08](ui/portal/08-explorer-by-generation.png) |
| **Cross-tab matrix** | Base row first; blue heat ombre; **significance letters** (Qualtrics style) or **arrows against any column you click**; small bases faded and flagged | [09](ui/portal/09-crosstab-letters.png) |
| **Two cuts combined** | Any two of gender, age, generation, income, region and urbanicity, for one answer. Cells under 30 are hidden, under 50 flagged. **Pool the last 2 or 4 weeks**, with a warning when the question's base changed inside the pool | [10](ui/portal/10-crosstab-two-cuts-pooled.png) |
| **Trends** | Every wave of the question's tracker on a real date axis: **missing weeks stay gaps**, the focus answer is red, a white ring marks a significant week-on-week move. ±margin-of-error band, 4-week average, 3m/6m/1y/all, any banner column | [11](ui/portal/11-trend-margin-band.png), [12](ui/portal/12-trend-year.png) |
| **What changed** | Every answer against last week or last year, most significant first, filter by section, CSV. Routing changes are excluded from the test rather than shown as false moves | [13](ui/portal/13-what-changed.png) |
| **Survey preview** | The questionnaire as respondents saw it, with the questionnaire flow by section and the live result | [14](ui/portal/14-survey-preview.png) |
| **Any archive survey** | The same screens for annual and ad hoc studies (e.g. Holiday Shopping and Spending 2026) | [15](ui/portal/15-archive-annual-survey.png) |
| **Phone** | One column, the rail becomes a top bar, KPIs two across | [16](ui/portal/16-phone-overview.png), [17](ui/portal/17-phone-explorer.png) |

**Hover, on every chart and cell:**
- the answer and its % ± margin of error (95 %);
- about how many respondents that is, and the base;
- a small-base warning when it applies;
- vs last week, with the change and whether it's significant;
- vs last year;
- the question code and wave.

This follows the tooltip spec from the competitor research ([15](15-competitor-patterns.md)).

**Everything in the URL:** the view, cut, reference column, weeks pooled, time range and the answers shown. A link opens the same view for a colleague.

## 2. The Coresight palette, applied as the style guide says

| Rule in the guide | Where it shows |
|---|---|
| Red `#D62E2F` highlights; white `#FAFAFA` background; black `#2D2A29` text | Page background, text, the top answer in every bar chart, KPI values, the red bar before headings (as in the reports), the active screen in the rail |
| "Always include red in the charts" | The top answer is red. With several columns, Total is red and the cuts are blue. In donuts the first slice is red. In trends the focus line is red |
| One callout plus an ombre of blues (the opacity trick) | Cuts in grouped bars, other donut slices, the cross-tab heat map, other trend lines |
| Greys for negatives, blue for neutral, reds for positives | Scale questions in the stacked view (q6: decreases grey, no change light blue, increases rose/red), detected from the answer wording |
| Horizontal bars for long labels; never angle text | Bars are horizontal by default; column labels wrap instead of rotating |
| Line charts: circular markers, ≤ 1.75 pt lines | Trends: circle markers (dropped when over 30 points), 1.5–2.25 px lines |
| Contrast at least 3:1; never light blue on white for text | Data labels are ink on light blue and white on red or dark. Secondary text is ink at 75 % (6.6:1). Light blue is only a fill |
| "Coresight look": white card, thin outline, red bold text | Every card; red eyebrows and question codes |
| Dark-grey table header with white text | Every table |
| Green only as positive against red | Not used: survey changes are not good or bad by themselves |

## 3. Staging test: one server like IT's staging box

| Item | Value |
|---|---|
| API server | The production image (`deploy/Dockerfile`): Debian 13, FastAPI, gunicorn with **2 workers**. Pinned to **1 CPU**, **4 GB RAM**, swap off |
| Database | MySQL 8.0.46 in its own container on 2 CPUs and 4 GB with a 2 GB buffer pool, the Azure staging tier. Loaded with a copy of `cip_stg`'s serving tables: 328 waves, 8.1 M `srv_answer` rows, 1.9 M `srv_result` rows |
| Load | [`user_mix.py`](../../scripts/ui_benchmark/user_mix.py) on 3 other CPUs. Each simulated user opens the library, opens a wave (**70 % one of the last 8 weeks, 30 % any archive wave, so caches miss**), then 1–3 more clicks (a two-cut cross-tab, a trend or a search). Think time averages 10 s. Each step ramps for 20 s, then measures for 60 s |
| Host | Colima ARM VM on the Apple M4 dev Mac |

### Results (final image, warm-up step first)

| Users at once | Requests/s | p50 | p95 | p99 | Errors | API CPU (of 1 core) | API RAM | MySQL CPU |
|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 1,000 | 100 | 2.0 ms | 17.8 ms | 39 ms | 0 | 23 % | 266 MB | 9 % |
| 4,000 | 398 | 1.1 ms | 16.6 ms | 287 ms | 0 | 43 % | 580 MB | 15 % |
| **6,000** | **597** | **1.6 ms** | **41 ms** | **123 ms** | **0** | **60 %** | **913 MB** | **20 %** |
| 8,000 | 797 | 3.8 ms | 293 ms | 639 ms | 0 | 76 % | 1,165 MB | 26 % |
| 10,000 | 958 | 300 ms | 1,511 ms | 1,663 ms | 0 | 97 % (saturated) | 1,317 MB | 31 % |

**Same steps, the previous run** (open-file limit not yet raised): 8,000 users gave p95 **56 ms**. The spread between runs at 8,000 is the edge of the core, so the safe planning figure is **6,000**.

### What the test changed in the code

| Found | Effect | Fix |
|---|---|---|
| The load client asked for uncompressed JSON (browsers don't) | 8,000 users: p95 **3.5 s** | Answer gzip clients with the pre-compressed bytes (23 KB per wave instead of 122 KB). Same step: p95 **56 ms** |
| Search was recomputed for every request | CPU per search | Cached like every other response |
| 1 worker on 1 core | **3,324 errors** at 6,000 users | 2 workers (the image default) |
| The container's open-file limit was 1,024 | One worker runs out of sockets above about 1,000 open connections | The image raises it to the hard limit at start-up |
| `app/core/database.py` imported pandas for a Streamlit-only helper | About 60 MB per worker and slower start-up | Imported lazily: an API worker now idles at about 70 MB |
| The old `index.html` stayed in browser caches after a release | Users kept old screens after a deploy | `index.html` is served `no-cache`; hashed `/assets` stay cached for a year |
| A count-capped cache (5,000 responses) | RAM grows with payload size as the archive grows | **LRU capped by bytes**: 256 MB per worker (`CIP_CACHE_MB`) |

### What this means on the real staging and production servers

- **The ranking and the shape carry over; the absolute numbers don't.** An Azure vCPU is about 2–3× slower than an M4 core ([11](11-capacity-staging-production.md)), so plan on **about 2,000–3,000 simultaneous heavy users per server**.
- **Users here are heavier than real ones.** Every simulated click goes to the server. In the app, changing chart type, banner, sort or question within a wave, and the whole Survey preview, run in the browser on data already loaded.
- **Production also has 1 core, so it carries the same number.** Its extra RAM is headroom for the ETL and caches, not for more users.
- **The real gate is to run the same scripts on the staging VM.** That needs Docker on the VM and a copy of `cip_stg` as here (§6).

## 4. In the browser

| Item | Value |
|---|---|
| First visit | App shell 112 KB + charts 187 KB + font 70 KB (gzipped). Each screen is a separate 2–4 KB chunk, loaded when opened |
| Repeat visits | Every asset is content-hashed and cached for a year; only `index.html` and data are fetched |
| Data per wave | One `/book` request (23 KB gzipped) feeds Overview, Explorer, Cross-tab banner, What changed and Survey preview |
| Screen fully drawn | 0.34–0.52 s on every screen (local network) |
| Browser memory | 7 MB on the library, 13–30 MB on a wave's screens, 46 MB after 15 screens in one tab. Phone: 15 MB |

## 5. Your two questions

**"Only 40 users and 10,000 requests? I expected more."**
- **40 was the number of real Chrome windows the test Mac can run at once.** It's a limit of the test machine, not of the server.
- **10,000 was requests per second on one core.** One person clicks perhaps once every 10–30 s, so 10,000 requests/s is far more than 40 people.
- That's why this test simulates users at the HTTP level: **6,000 simultaneous users** on one core and 4 GB, with zero errors.

**"React + Vite + FastAPI vs Next.js static + FastAPI: what's the difference?"**
- **For users, none.** Both build the same kind of thing: plain HTML, JS and CSS files that the browser runs, with FastAPI answering the data. The 1-core test confirmed it ([14](14-docker-1core-benchmark.md)): the same API speed, and clicks of 0.13 s vs 0.33 s at 40 users, which is within the test machine's noise.
- **The differences are in the tooling, and they favour Vite:**
  - Lovable's own code is Vite + React, so its pieces drop straight in.
  - Vite builds in about 0.2 s here.
  - Next.js's extra features (server rendering, image optimisation, API routes) are switched off in a static export anyway.
- **Next.js only differs in server mode:** 4–9× fewer requests per second and 5× the RAM on one core.

## 6. Re-run

```bash
# images
docker build -f deploy/Dockerfile -t cip-portal .
docker build -f scripts/ui_benchmark/stacks/Dockerfile --target py -t bench-py scripts/ui_benchmark
# database: a MySQL 8 container loaded with mysqldump of srv_wave srv_result srv_answer cip_survey cip_question
#           cip_topic cip_profile cip_respondent cip_wave_module (read-only on Azure), plus sql/006_dashboards.sql
docker run -d --name cip-api --network bench --cpuset-cpus 0 --cpus 1 --memory 4g --memory-swap 4g --env-file api.env -p 8100:8000 cip-portal
sh scripts/ui_benchmark/docker_stats.sh cip-api cip-mysql > stats.log &
docker run --rm --network bench --cpuset-cpus 3-5 --ulimit nofile=200000:200000 -v "$PWD/scripts/ui_benchmark:/s:ro" bench-py \
  python -u /s/user_mix.py http://cip-api:8000 --users 1000,4000,6000,8000,10000 --think 10 --seconds 60 --ramp 20
# screens: headless Chrome on :9333, then
python scripts/ui_benchmark/shots.py http://127.0.0.1:8100 out/ / /w/412 /w/412/crosstab/q2 /w/412/trends/XM3
```

`api.env` holds `APP_ENV`, `LOCAL_DB_*` and `CIP_SESSION_SECRET`; never commit it.

## 7. Not done yet

| Gap | Why it matters |
|---|---|
| Run the test on the real staging VM | The Azure core speed is still assumed |
| Sign-in (OIDC) and entitlements | The portal uses the local dev login; production needs the identity provider |
| Topic mapping for about 20 questions per wave | They show module or code-letter sections (e.g. "DNM block") instead of a topic |
| Nets / Top-2-box, saved views, PPT/PNG export | From the competitor list (patterns 11, 14, 15) |
| Weighting | Figures are unweighted, as the cube is today |
