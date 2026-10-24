# 70 · Benchmark: speed, stack and UI against the market, plus a UI spec for both themes

**Date:** 23 Oct 2026 · **Author:** Claude (Opus), benchmark analyst in the 4-agent team.
**Inputs:** [60-competitors-and-market-gaps.md](60-competitors-and-market-gaps.md) and its source register, [40-frontend-ui.md](40-frontend-ui.md), `PRODUCT.md`, `DESIGN.md`, `web/src/theme.ts`, `web/src/styles.css`, `web/src/components/*`, `web/src/pages/*`.
**Evidence:** screenshots and raw JSONL in [screens/benchmark/](screens/benchmark/). Labels: **[O]** observed today, **[I]** inferred, **[U]** unknown.

---

## 1. Verdict in one screen

| Question | Answer |
|---|---|
| **Speed** | CIP is the **lightest product in the set by a wide margin**: 389 KB and 20 requests on a cold load, from one host, with 0 ms blocking time. The median public vendor page is about 2.4 MB and 104 requests from 15+ hosts. Warm screens become ready in 0.4–1.0 s. CIP loses on one number: **first paint on a cold load (1.5 s desktop, 2.1 s throttled phone)**, because the SPA paints nothing until 307 KB of JS has arrived and run. The fix is cheap (§3.4). |
| **Stack** | Competitive and current. React 19 + Vite + React Router 7 is the **same family as Statista Consumer Insights**, the nearest product match. ECharts 6 is a free equivalent of the Highcharts used by YouGov and Statista. No framework change is needed. Make three small changes: an inline app shell, a registered ECharts theme, and removing the unused dependencies (§4). |
| **UI** | CIP is already ahead of every public competitor data surface on **dark mode**: none of the 8 vendor pages probed responds to `prefers-color-scheme: dark`. It is also ahead on **uncertainty display**. It is behind the best on four things: **restraint with red** (three solid red banners on Overview), **toolbar clutter** (11 buttons in 3 rows on Questions), **mobile layout** (the question list fills the first phone screen), and **loading states** (text spinners, no skeletons). Dark mode has three contrast failures (§5.3). |
| **To be "best-looking research desk in both themes"** | Apply the token set in §6.1, which passes WCAG AA in both themes. Then do the top 10 items in §7. All of them are CSS and component work inside `web/src`, and none needs an API change. |

---

## 2. Method and honesty notes

| Item | Detail |
|---|---|
| Browser | Scratch headless Chrome 156 on CDP `127.0.0.1:9335`, with its own `--user-data-dir` in the session scratchpad, **closed afterwards**. Port 8000 and cloudflared were not touched. `npm run build` was not run. |
| Probe | `bench.mjs` (scratchpad) uses raw CDP. It reads Navigation Timing (TTFB), Paint Timing (FCP), a `largest-contentful-paint` observer (LCP), a `longtask` observer (TBT = Σ(task − 50 ms)) and a **ready** time. Ready is the first moment `main` has content, no `.spinner` is present and the document is complete. **TTI here = max(ready, end of the last long task)**, which is a proxy and not Lighthouse TTI. Bytes are CDP `encodedDataLength` (wire bytes). |
| Profiles | **Desktop:** 1440×900, no throttling. **Mid-range phone:** 390×844 @2x, Android UA, **CPU 4× slowdown, 150 ms RTT, 1.6 Mbps down / 750 kbps up** (the Lighthouse "slow 4G" profile). |
| Live CIP | Link `cheque-bought-dust-successfully.trycloudflare.com`. Signed in with `dev-login`, which is a GET. There were 12 page loads and about 85 network requests in total, inside the 100 cap. There were no clicks except the theme toggle, which is client-side, made 0 extra API calls on four screens and was restored after each capture. No form submits. `/healthz` returned 200 before and after. |
| Cold vs warm | *Cold* means the browser cache was cleared. *Warm* means the hashed assets were cached; each warm screen was a full reload, so API calls happen again (CIP's API is fast on a cache hit, 1–2 ms). |
| Single samples | Each figure is **one run** through a Cloudflare quick tunnel from India, so run-to-run variance is ±200–400 ms. Treat the figures as orders of magnitude. |
| Competitors | **Public pages only.** Nothing was logged into, signed up for or submitted, and **cookie banners were left as they were**, with no consent given. The vendor *apps* (GWI, Morning Consult, YouGov Profiles, Statista CI, Displayr, Attest, quantilope) are gated. Their marketing pages are **not** their logged-in apps, so marketing-page speed is a proxy for engineering culture and CDN, not for in-app speed. The closest app-like pages measured are Statista's public statistic page, YouGov's public tracker, Civiqs, a Datawrapper YouGov BrandIndex chart and the Crunch app shell (login). |
| AI-aimed instructions | The Statista Consumer Insights page has an embedded block aimed at AI readers (also noted in doc 60). It was **ignored**. Nothing else was seen. |
| Not used | WebSearch (per brief), REA bundle re-runs on the live CIP link (to stay inside the request cap; CIP's bundle figures come from doc 40's scratch build), and Lighthouse. |

---

## 3. Speed

### 3.1 CIP on the live link [O]

**Desktop (1440×900, unthrottled)**

| Screen | Load | TTFB | FCP | LCP | Ready (≈TTI) | TBT | Transferred | API calls on the screen |
|---|---|---|---|---|---|---|---|---|
| Library `/` | **cold** | 632 ms | **1,516 ms** | 1,840 ms | 1,569 ms | 0 | **389 KB / 20 req** (JS 307, CSS 8, fonts 37, img 14, API 21) | waves 273 ms, team/views 547, alerts 529, boards 533 |
| Library `/` | warm | 94 | 128 | 496 | 471 | 0 | ~0 KB | 4 (waves from cache) |
| Overview `/w/415` | first visit | 305 | 344 | **2,384** | **2,362** | 47 | 35 KB (API 27) | book 320 ms, 3 × dashboards ~300 ms, boards |
| Questions `/w/415/questions` | first visit | 325 | 352 | 852 | 838 | 0 | 7 KB | book 2 ms (cached), boards |
| Cross-tab `/w/415/crosstab` | first visit | 287 | 332 | 760 | 642 | 0 | 5 KB | book 1 ms, boards |
| Trends `/w/415/trends` | first visit | 313 | 344 | 676 | 974 | 0 | 63 KB (API 57) | `questions/CSI-US/tracker/q1` 292 ms (57 KB) |
| Trends | warm | 68 | 96 | 448 | 425 | 0 | ~0 KB | all cached |

**Mid-range phone (CPU 4×, slow 4G)**

| Screen | Load | TTFB | FCP | LCP | Ready (≈TTI) | TBT | Transferred |
|---|---|---|---|---|---|---|---|
| Library | **cold** | 819 | **2,104** | **4,016** | 3,967 | 25 | 389 KB |
| Overview | warm assets | 68 | 236 | 1,184 | 1,215 | **243** | 35 KB |
| Questions | warm assets | 67 | 196 | 592 | 585 | 17 | 7 KB |
| Cross-tab | warm assets | 74 | 208 | 556 | 538 | 0 | 5 KB |
| Trends | warm assets | 71 | 212 | 560 | 1,101 | 54 | 63 KB |

**What the numbers say**
1. **Once loaded, CIP is very fast.** Questions and Cross-tab become ready in about 0.6–0.8 s even on a throttled phone, because one 23 KB `/book` feeds both and is cached by React Query.
2. **The cold first paint is the weak spot.** The gap from TTFB to FCP is about 900 ms on desktop and 1.3 s on the phone. `index.html` ships an empty `<div id="root">`, so nothing paints until the 119 KB gzipped entry chunk has run [O `web/index.html`].
3. **Overview is the slowest screen.** On this desktop run it was ready in 2.4 s with LCP 2.4 s, and the phone shows 243 ms TBT. Four requests are chained after `/book`: three `/dashboards/*`, then the count-up and chart animations. The phone run, with the dashboards warm on the server, was ready in 1.2 s, so part of the desktop figure is a cold server cache [I].
4. **Deep-link HTML is slower than `/`**: TTFB is 287–325 ms on a deep link and 68–94 ms on `/`. Nginx/Cloudflare seem to revalidate or miss the SPA fallback for `/w/...` paths [I]. Check `Cache-Control` on the HTML fallback.
5. **The live bundle still calls `/api/v1/boards` on every screen** (about 300–530 ms each) [O]. The source has already been changed to fetch it only while the pin dialog is open (`components/PinDialog.tsx:15`), so this is **fixed in source and not yet deployed**. That change is someone else's; it was not made by this agent.
6. On the first Library load `/alerts` took 529 ms and `team/views` 547 ms. Doc 40 saw `/alerts` take 2.9 s once. The Library hero does not need either of them to paint.

### 3.2 Competitor public pages [O]

Cold cache for every row. † = the throttled run had not finished at the 60 s cut-off, so its bytes are partial and its timings are a lower bound.

| Vendor page (type) | Desktop TTFB / FCP / LCP | Desktop TTI≈ / TBT | Desktop transfer (JS) / req / hosts | Phone FCP / LCP / TTI≈ |
|---|---|---|---|---|
| **CIP Library (app, cold)** | **632 / 1,516 / 1,840** | **1,569 / 0** | **389 KB (307) / 20 / 1** | **2,104 / 4,016 / 3,967** |
| Statista Consumer Insights (marketing) | 626 / 804 / 1,244 | 1,671 / 338 | 1,527 KB (974) / 105 / 7 | 2,708 / 3,020 / 9,921 |
| Statista public statistic (data page) | 149 / 180 / 912 | 304 / 0 | 2,105 KB (1,739) / 58 / 10 | 1,480 / 1,708 / 1,480 † |
| GWI platform (marketing) | 117 / 852 / 852 | 10,297 / 19 | 2,131 KB (1,473) / 103 / 32 | 660 / 660 / 9,949 |
| Morning Consult home (marketing) | 104 / 1,516 / 1,592 | 5,041 / 41 | **7,194 KB** (2,088) / 152 / 42 | 708 / 7,852 / 24,165 |
| YouGov Profiles (marketing) | 766 / 988 / 1,376 | 3,380 / 82 | 1,823 KB (1,241) / 210 / 19 | 856 / 6,640 / 9,997 |
| YouGov public tracker (data page) | 1,256 / 1,424 / 2,760 | 3,562 / 162 | 2,267 KB (1,775) / 131 / 19 | 1,960 / 4,072 / 6,386 † |
| Qualtrics home (marketing) | 123 / 436 / 520 | 1,944 / 0 | **11,612 KB** (1,916) / 276 / 54 | 3,420 / 46,640 / 35,457 |
| Displayr home (marketing) | 391 / 488 / 3,900 | 849 / 0 | 938 KB (272) / 93 / 11 | 2,240 / 3,040 / 2,240 † |
| Attest home (marketing) | 347 / 484 / 484 | 1,854 / 137 | 1,524 KB (824) / 158 / 16 | 1,844 / 1,844 / 9,793 |
| Crunch home (marketing) | 536 / 1,644 / 3,736 | 4,493 / 0 | 3,186 KB (705) / 44 / 22 | 952 / 2,024 / 952 † |
| **Crunch app shell** (login page of the app) | 1,344 / **3,604** / 3,604 | 3,604 / 369 | **5,272 KB (4,771 JS)** / 34 / 11 | no paint by 11 s † |
| quantilope home (marketing) | 63 / 1,652 / 1,672 | 2,027 / 0 | 3,157 KB (367) / 111 / 15 | 1,252 / 1,320 / 23,538 |
| Civiqs results (public data app) | 6,102 / 6,784 / 7,400 | 9,220 / 46 | 3,371 KB (1,314) / 80 / 24 | 2,392 / 2,392 / 2,392 † |
| Datawrapper YouGov BrandIndex chart (embed) | 362 / 488 / 500 | 717 / 0 | 2,610 KB (354) / 29 / 5 | 4,920 / 4,920 / 13,969 |
| Suzy app (doc 60, REA) | n/a | n/a | **7.3 MB main bundle** | n/a |

**Medians across the 14 vendor desktop rows:**
- transfer about **2.4 MB**;
- **104 requests**;
- FCP about **0.92 s**;
- LCP about **1.48 s**;
- TTI≈ about **2.7 s**;
- TBT about **10 ms**.

**CIP against those medians:**
- **about 6× lighter** and **5× fewer requests**, from one host against 15+;
- TTI≈ 1.6 s against 2.7 s, with zero blocking time;
- **FCP is 0.6 s worse** and **LCP is 0.36 s worse** on a cold load, because marketing pages are server-rendered HTML and CIP is a client-rendered SPA behind an India-hosted tunnel;
- warm, CIP's FCP is 0.1 s and LCP 0.5 s, which beats every vendor row.

**Like for like:** the only gated *app* bundles that can be seen are:
- Crunch's app shell: 4.8 MB of JS, first paint at 3.6 s on desktop and none within 11 s on the phone;
- Suzy: 7.3 MB main bundle.

CIP's 307 KB of JS is **15–25× smaller**. Statista Consumer Insights' app is the same React Router + Vite family and its public pages ship 1–1.7 MB of JS [O, REA `ev_4ccad97…` in doc 60].

### 3.3 Speed verdict
- **Payload, request count, blocking time and warm navigation:** CIP leads the market sample.
- **Cold first paint:** CIP is behind. A client would notice it once per session.
- **The tunnel is the biggest single cost:** TTFB is 632–819 ms cold. A production host with a real CDN edge should land under 150 ms [I]. That alone moves cold FCP to about 1.0 s on desktop.

### 3.4 Speed changes, in priority order (all in `web/`, no API change)

| # | Change | Where | Expected gain [I] |
|---|---|---|---|
| S1 | **Inline app shell.** Put static HTML for the dark rail, the topbar outline and a page-heading skeleton inside `<div id="root">`, with ~1.5 KB of critical CSS (tokens from §6.1). React's `createRoot` replaces it. | `web/index.html` | Cold FCP from 1.5 s to about TTFB + 50 ms, so about 0.7 s on the tunnel and about 0.2 s behind a CDN. Phone: 2.1 s to about 0.9 s |
| S2 | `<link rel="modulepreload">` for the Library and Overview route chunks, plus `<link rel="preload" as="font">` for the latin Montserrat woff2 | `web/index.html` or a Vite `transformIndexHtml` plugin in `vite.config.ts` | About 100–300 ms off the first route render. Avoids a font swap reflow |
| S3 | Deploy the `/boards` gating that is already in source | `components/PinDialog.tsx:15` (done in source) | One fewer 300–530 ms request on every screen |
| S4 | Overview: start the three `dashboards/*` queries in parallel with `/book` instead of after it. The dashboard codes come from `/waves`, which is already cached. Alternatively publish them inside the book | `pages/Overview.tsx:50`, `components/Glance.tsx` | Overview ready from about 2.4 s to about 1.0 s |
| S5 | Library: `content-visibility: auto; contain-intrinsic-size: auto 72px` on `.wave-row`. The page has 5,359 DOM nodes and is 26,000 px tall | `styles.css` `.wave-row` | Much less style/layout work on phones. One CSS line |
| S6 | Long-cache the HTML fallback for `/w/*` with revalidation (ETag), the same as `/` | nginx config (ops) | Deep-link TTFB from about 300 ms to about 80 ms |
| S7 | Move `perf.ts` and `PerfHUD` out of the entry chunk behind `?perf=1` with a dynamic `import()` (doc 40) | `main.tsx`, `components/PerfHUD.tsx` | About 10–15 KB gzipped off the critical path |

---

## 4. Tech stack

| Product | Front-end framework | Charts | Rendering | CDN / edge | JS shipped (public page) | Source |
|---|---|---|---|---|---|---|
| **CIP** | **React 19.3 + React Router 7.18 + TanStack Query 5, Vite 8** | **ECharts 6.1** (tree-shaken: bar, line, pie; canvas) | SPA, static published JSON (`/book`), FastAPI + MySQL behind | nginx → Cloudflare quick tunnel (h2) | **307 KB wire** (entry 119 KB gz + charts 187 KB gz, split) | repo, doc 40 [O] |
| Statista Consumer Insights | React + React Router v7 framework mode, Vite/rolldown, i18next | Highcharts 12.6 (public stat pages) | SSR + hydrate | own CDN | 974 KB (CI page), 1.7 MB (stat page) | REA doc 60; fingerprint today [O] |
| YouGov (Profiles, trackers) | **Angular 21.2.7** SSR | Highcharts 12.6 | SSR + hydrate | own; OneTrust, New Relic | 1.2–1.8 MB | fingerprint `ng-version` today [O] |
| GWI | HubSpot CMS (marketing); app host not public | U | SSR CMS | HubSpot CDN | 1.5 MB | [O] |
| Morning Consult | HubSpot (marketing today; doc 18 saw Next.js); app behind oauth2-proxy | U | SSR CMS | 42 hosts | 2.1 MB | [O] |
| Qualtrics | Drupal (marketing) | U | SSR CMS | 54 hosts | 1.9 MB JS, 11.6 MB total | [O] |
| Displayr | WordPress (marketing); app on `static-assets.prod.displayr.com/SharedWebUi` | U | SSR CMS | | 272 KB | [O] |
| Attest | WordPress (marketing) | U | SSR CMS | | 824 KB | [O] |
| Crunch | App: React + d3 + Plotly + Vega + lodash + ndarray bundles from `s.crunch.io` | d3, Plotly, Vega | SPA | `s.crunch.io` | **4.8 MB** (app shell) | doc 60 REA + today [O] |
| quantilope | HubSpot (marketing); portal is a Vite build + Appcues | U | SPA (portal) | | 367 KB (marketing) | [O] |
| Suzy | Angular (Zone.js) | U | SPA | | **7.3 MB main** | doc 60 REA [O] |
| Civiqs | React Router / Remix | custom SVG (d3-like) | SSR + hydrate | | 1.3 MB | fingerprint today [O] |
| Datawrapper | Datawrapper (Svelte) | own d3-based | static embed | `dwcdn.net` | 354 KB | [O] |

**Stack verdict**
1. **Keep the stack.** React 19 + Vite + React Router 7 matches the nearest competitor's (Statista CI). It is the most mainstream React toolchain of 2026 and it produces the smallest bundle in the set.
   - Angular (YouGov, Suzy) and Plotly/Vega stacks (Crunch) are not better for this job.
   - SSR is not needed. CIP is an authenticated app with no SEO need, and S1 (inline shell) gives the paint benefit of SSR without a Node server on the 1-core box.
2. **Keep ECharts.**
   - It is free under Apache-2.0, while Highcharts needs a commercial licence for YouGov- or Statista-type use.
   - Its canvas renderer handles 371-wave trend lines easily.
   - It already emits ARIA descriptions.

   What CIP lacks is a **registered theme** (§6.6), not a different library.
3. **Remove dead weight:** `mermaid`, `@mermaid-js/mermaid-cli`, `reactflow`, `@xyflow/react` and `react-scan` from `dependencies` (0 imports in `src`, per doc 40). This does not change the browser bundle, but it removes the two `npm audit` findings and about 800 MB from `node_modules`.
4. **The server side is the real moat.** A static published JSON book (23 KB gzipped) served from nginx is the same "small JSON per chart" pattern as YouGov's 775-byte tracker series and Datawrapper (doc 18), and it is lighter than Statista's or Civiqs' inline-everything pages.
5. **Not needed:** Next.js or Remix migration, a service worker or offline mode, a micro-frontend, a WebGL chart engine, or a CSS framework. Tailwind would be a rewrite for no user gain, since `styles.css` is 748 lines and 8 KB gzipped.

---

## 5. UI comparison

### 5.1 What was captured
- **CIP, ten desktop and ten phone captures, light and dark:**
  - `cip-d-{library,overview,questions,crosstab,trends}-{light,dark}.png`
  - `cip-m-{library,overview,questions,crosstab,trends}-{light,dark}.png`
  - The theme is toggled by `.theme-btn` in `components/Shell.tsx:268` and stored in `localStorage["cip-theme"]` (`theme.ts:28`). `index.html` applies it before first paint and falls back to `prefers-color-scheme`.
- **Competitors:**
  - `v-d-*.png`: the 14 vendor pages at desktop size. Cookie banners are visible because none was dismissed.
  - `v-grid-public-trackers.png`: Statista statistic, YouGov tracker, Civiqs, Datawrapper/YouGov BrandIndex.
- **Dark-mode probe [O]:** each of 8 vendor pages was loaded with emulated `prefers-color-scheme: light` and then `dark`, and the mean luminance of the two screenshots was compared. The difference was 0–3 levels for Statista (both pages), YouGov tracker, Civiqs, Datawrapper, GWI, Displayr and Crunch, so **none ships a dark theme**. Doc 18 said Datawrapper embeds follow the system theme. That is a per-chart publisher option, and this chart has it off.

### 5.2 Scorecard (1 = poor, 5 = best in class)

Competitor scores cover their **public data surfaces**, not their gated apps (see §2).

| Dimension | **CIP light** | **CIP dark** | Statista stat page | YouGov tracker | Civiqs | Datawrapper (YouGov BI) |
|---|---|---|---|---|---|---|
| Hierarchy | **4**: red-bar page title, KPI row, clear question header. Overview's three solid red banners compete with the title | **3**: the red banners are louder on dark, and the rail merges with the paper (1.07:1) | 3: ads, a cookie wall and nav compete with the chart | 3: the cookie modal covers the page; the title is strong | 4: clear title, population and n, refine-by rail | **5**: title, subtitle, chart, source, nothing else |
| Data density | **4**: n everywhere; banner columns; 52-question nav | 4 | 3 | 3 | **5**: subgroup rail, events, uncertainty | 3: one chart |
| Typography | **4**: Montserrat, tabular numbers, sentence case. Uppercase nav headers break `DESIGN.md`'s own rule; 11 px chart labels | 4 | 3 | 4 | 3: rotated 9–10 px event labels | 4 |
| Chart clarity | **4**: red focus series, end labels, significance rings, MoE band. Sky bars are 1.9:1 on white. Trends shows 3 jagged weekly series with MoE off by default | **3**: sky (8.4:1) and red (3.3:1) read as the same weight; the "others" series is about 1.6:1 | 4: Highcharts, labelled points | 3: rotated dates, no MoE | 4: uncertainty band, end labels; rotated event labels clutter | **5**: moving average stated, direct labels, clean grid |
| Colour / contrast (WCAG) | **3**: text passes (ink 13.6:1, ink-2 6.6:1). Input borders `#B2B2B2` 2.1:1 and sky bars 1.9:1 fail 1.4.11 | **3**: heat cell text at the 0.46–0.55 alpha band is 3.9:1 (fails 1.4.3); "others" lines fail 3:1 | 4 | 4 | 3 | 4 |
| Dark-mode quality | n/a | **3.5**: real token swap, no flash, charts re-themed. Loses points on red banners, rail separation and the heat-text failure | **1**: none | **1**: none | **1**: none | **1**: off on this chart |
| Empty / loading states | **2**: "Loading data…" text spinner (`bits.tsx:64`); layout jumps when content arrives | 2 | U | U | U | n/a |
| Mobile | **3**: no horizontal scroll; tables scroll inside their box. The 3-row topbar takes 164 px, and on Questions, Cross-tab and Trends the question list fills the first screen, so the chart is below the fold | 3 | 3 | 3 | 2 | 4 |
| **Mean** | **3.4** | **3.2** | 3.0 | 2.9 | 3.1 | 3.7 (single chart, not an app) |

The gated vendor apps could not be scored. Their marketing screenshots (`v-d-gwi`, `v-d-morningconsult`, `v-d-attest`) show the 2026 house style: large neutral surfaces, one accent colour, generous whitespace and product screenshots with skeleton-like placeholders. That is the visual bar a buyer brings to a CIP demo [I].

### 5.3 Specific defects found in the captures [O]

| # | Theme | Screen | Defect | Evidence |
|---|---|---|---|---|
| D1 | both | Overview | Each "at a glance" block has a **solid `#D62E2F` header**, three of them stacked. This contradicts `DESIGN.md` ("never used as generic decorative background") and makes the significance red meaningless. On dark it is the loudest object on screen | `cip-d-overview-*.png`; `styles.css:470` `.glance-head { background: var(--red) }` |
| D2 | both | Overview | Cards nested inside a card: `.glance-tile` sits inside `.glance-block` (`DESIGN.md` "Don't nest cards") | `styles.css:469-498` |
| D3 | dark | Cross-tab | `inkOn()` switches to dark ink when alpha > 0.45. At alpha 0.50 the cell is `#68757C` and dark ink `#141211` gives **3.93:1** (13 px bold text needs 4.5:1). The ombre also jumps from about `#68757C` to `#8EA5B0` (the dead-zone skip), so the matrix reads as two tones instead of a ramp | `theme.ts:43-55`; `cip-d-crosstab-dark.png` |
| D4 | light | all charts | The default bar fill `#A3C0CE` on white is **1.91:1**, under the 3:1 non-text minimum. Data labels mitigate it | `theme.ts:10`, `QuestionChart.tsx:129-135` |
| D5 | both | Trends | Lower-ranked series use the alpha ombre `rgba(series, 0.25)`, about 1.6:1 on dark. In dark the sky (`#A3C0CE`) and red lines have similar visual weight | `theme.ts:37-40` `blues()`, `cip-d-trends-dark.png` |
| D6 | light | inputs, selects | Control borders use `--silver #B2B2B2`, which is **2.12:1** on white and fails 1.4.11 for UI boundaries | `styles.css:79,82` (switcher, search), `.btn`, `.qnav input` |
| D7 | dark | frame | The rail (`#141211`) on the paper (`#1B1918`) is **1.07:1**, so there is no visible edge. The surface on the paper is 1.23:1, so cards rely on the 1 px `#45413F` border | `styles.css:24-32` |
| D8 | both | Questions | **11 actions in 3 rows** above the chart: CSV, Excel, PowerPoint, Board, Alert me, Download PNG, Copy link, Cross-tab matrix, Trends, Compare waves, plus the view and cut segments. Datawrapper and OWID show 1–2 | `cip-d-questions-*.png` |
| D9 | both | Questions, Cross-tab, Trends | **No `<h1>`**: the probe found `h1 = null`. The question text is the natural h1 | bench JSONL `h1: null` |
| D10 | both | qnav | `text-transform: uppercase` on section headers ("AI AND GENAI SHOPPING"), against `DESIGN.md` "No all-caps" | `styles.css:272` (also 584, 606, 620) |
| D11 | phone | split screens | `.qnav` comes first and is up to 340 px tall, so on a 390×844 phone the chart or matrix starts below the fold. The topbar wraps to 3 rows, 164 px | `cip-m-crosstab-*.png`, `styles.css:418-446` |
| D12 | both | everywhere | Loading is text plus spinner, with no reserved height, so content jumps (CLS) and the wait feels longer than it is | `components/bits.tsx:64` (`Loading`), 53 call sites in `pages/` |
| D13 | both | rail | The "✓ Verified sample" badge is shown unconditionally (doc 40 UI audit) and the green accent is not needed | `Shell.tsx:103` |

---

## 6. UI improvement spec (for a frontend engineer)

Scope: `web/src` only. Keep every Coresight brand colour (red `#D62E2F`, white `#FAFAFA`, black `#2D2A29`, blues `#005F8F` / `#A3C0CE`). New hexes are **tints and shades of those blues and of the warm greys** (the guide's "opacity trick", made solid so contrast is predictable). The only non-brand accents kept are warn amber and the positive green, which already exist and are used only for meaning. Every pair below was computed with the WCAG 2.x relative-luminance formula (`scratchpad/bench/contrast.py`).

### 6.1 Design tokens

Replace the `:root` and `:root[data-theme="dark"]` blocks in `web/src/styles.css:3-34`, and mirror the values in `LIGHT`/`DARK` in `web/src/theme.ts`.

| Token | Light | Dark | Use | Contrast (light / dark) |
|---|---|---|---|---|
| `--paper` | `#FAFAFA` | `#1B1918` | page canvas | n/a |
| `--surface` | `#FFFFFF` | `#242120` | cards, tables | dark surface vs paper 1.10 (separation comes from the border) |
| `--raised` | `#FFFFFF` | `#2D2A29` (brand black) | popovers, tooltips, dialogs, sticky headers | n/a |
| `--fill` | `#F2F1F0` | `#332F2D` | segments, chips, base row | n/a |
| `--hover` | `#F5F4F3` | `#2B2826` | row hover | n/a |
| `--line` (was `--mist`) | `#E5E3E1` | `#3D3937` | hairlines, card borders, grid | decorative |
| `--line-strong` (**new**) | `#8A8684` | `#77726F` | **input, select, button and checkbox borders** | **3.61 / 3.37** (1.4.11 pass; was 2.12) |
| `--ink` | `#2D2A29` | `#FAFAFA` | primary text | 13.6 on paper / 15.3 on surface |
| `--ink-2` | `#5F5C5B` | `#C9C5C3` | secondary text | 6.6 / 9.3 |
| `--ink-3` (**new**) | `#757170` | `#A39F9D` | tertiary text, placeholders, axis names | 4.8 / 6.1 |
| `--red` | `#D62E2F` | `#D62E2F` | fills: logo, active nav, primary button, code pill, focus series bar | white on red 4.89; red on dark surface 3.27 (graphics pass) |
| `--red-line` (**new**) | `#D62E2F` | `#E5484A` | the focus **line** on dark charts | 4.89 / 4.08 |
| `--red-text` | `#C42829` | `#FF8A8A` | red as text | 5.7 / 7.05 |
| `--red-wash` | `#FBEAEA` | `rgba(214,46,47,.20)` | selected rows, sig chip background | n/a |
| `--sig` | `#A61F20` | `#FF8A8A` | significant text on wash | 6.4 / 7.0 |
| `--blue` | `#005F8F` | `#A3C0CE` | links, primary series | 6.9 / 8.4 |
| `--focus` (**new**) | `#D62E2F` | `#FF8A8A` | focus ring | 4.69 on paper / 7.72 on paper (brand red on dark paper is under 4) |
| `--warn` / `--warn-wash` | `#8A5A00` / `#FFF4D6` | `#FEBC20` / `rgba(254,188,32,.14)` | small base, breaks | 5.4 / 9.5 |
| `--ok` / `--ok-wash` | `#2E6B40` / `#E6F2E9` | `#8FCB9F` / `rgba(97,165,117,.18)` | significant positive only | 5.5 / 8.5 |
| `--rail` | `#2D2A29` | `#121010` + `border-right: 1px solid #2D2A29` | nav rail | dark: the edge comes from the border (D7) |
| `--head` / `--head-ink` | `#2D2A29` / `#FFFFFF` | `#2D2A29` / `#FAFAFA` | table headers | 14.3 / 13.6 |
| `--shadow-1` | `0 1px 2px rgba(45,42,41,.06)` | `0 1px 2px rgba(0,0,0,.4)` | cards (drop the 16 px blur on cards) | n/a |
| `--shadow-2` | `0 8px 24px rgba(45,42,41,.12)` | `0 8px 24px rgba(0,0,0,.5)` | popovers, dialogs | n/a |

**Data-series ramps (solid hex, replacing `rgba(series, α)` in `theme.ts:37-40` `blues()`):**

| Role | Light hex | vs white | Dark hex | vs `#242120` |
|---|---|---|---|---|
| Focus / highlight | `#D62E2F` | 4.89 | `#E5484A` (lines) / `#D62E2F` (fills) | 4.08 / 3.27 |
| Series 1 | `#005F8F` | 6.92 | `#A3C0CE` | 8.37 |
| Series 2 | `#357599` | 5.05 | `#7FA7BC` | 6.21 |
| Series 3 | `#5B8FAD` | 3.51 | `#5C8DA8` | 4.44 |
| Other / context series | `#8A8684` | 3.61 | `#8C8785` | 4.51 |
| Default single-series bar fill | `#A3C0CE` **with a 1 px `#5B8FAD` border** (`itemStyle.borderColor`) | border 3.51 | `#A3C0CE` | 8.37 |

Rules:
- At most **four coloured series**; everything else uses "other" grey with direct end labels.
- In dark, distinguish focus from series 1 by **width** (focus 2.5 px, others 1.5 px), not by colour alone.

**Cross-tab heat: six solid steps**, replacing `heat()`, `heatAlpha()` and `inkOn()` in `theme.ts:42-55`. Bin `v / max` into 6 equal steps.

| Step | Light fill | Text | Ratio | Dark fill | Text | Ratio |
|---|---|---|---|---|---|---|
| 1 | `#F1F6F9` | ink `#2D2A29` | 13.1 | `#2C3134` | `#FAFAFA` | 12.6 |
| 2 | `#D3E2EA` | ink | 10.7 | `#344550` | `#FAFAFA` | 9.5 |
| 3 | `#A3C0CE` | ink | 7.5 | `#41606F` | `#FAFAFA` | 6.4 |
| 4 | `#6E9CB7` | ink | 4.8 | `#5C8DA8` | `#141211` | 5.2 |
| 5 | `#357599` | white | 5.1 | `#86AEC2` | `#141211` | 7.9 |
| 6 | `#005F8F` | white | 6.9 | `#B9D2DE` | `#141211` | 11.9 |

Every cell passes 4.5:1, which fixes D3, and the ramp is monotone in both themes. Update the legend in `pages/Crosstab.tsx:176` to show all six swatches.

**Scale palette** (`scaleColours`, `theme.ts:64-76`): keep the logic. In dark, use `#C9C5C3` (strong) and `#8C8785` (mild) for negatives, `#E5484A` (strong) and `#D07676` (mild) for positives and `#A3C0CE` for neutral. All of them are ≥4:1 against `#242120` (8.3, 4.5, 4.1, 5.0 and 8.4). In dark the strongest end is the lightest.

### 6.2 Typography (Montserrat Variable, already self-hosted)

| Token | Size / line-height / weight | Use | Change from today |
|---|---|---|---|
| `--t-display` | 28 / 1.2 / 700, `letter-spacing: -0.01em` | page `h1` | same; 24 px at ≤900 px (today 22) |
| `--t-h2` | 20 / 1.3 / 700 | question text (**make it the `h1` on Questions, Cross-tab and Trends**, D9), section titles | was 21/600 or 22/700, so unify |
| `--t-h3` | 16 / 1.35 / 600 | card titles | was 15–18, mixed |
| `--t-body` | 14 / 1.5 / 400 | body | same |
| `--t-data` | 13 / 1.4 / 500, `tabular-nums` | tables, cross-tab cells (600 in cells) | same |
| `--t-meta` | 12 / 1.4 / 500 | n, bases, footnotes, chips | unify the 11, 11.5, 12 and 12.5 px variants (about 20 distinct sizes in `styles.css` today) |
| `--t-kpi` | 34 / 1.05 / 700, `letter-spacing: -0.02em`, `tabular-nums` | KPI figures | tighter tracking |
| chart axis | 12 / 500, `--ink-3` | ECharts `axisLabel` | from 11 px in `ink`, which is too loud and too small |
| chart data label | 12 / 600, `--ink` | bar labels | from 11 px |

- Remove every `text-transform: uppercase` (`styles.css:272, 584, 606, 620`) and use 12/700 `--ink-2` in sentence case instead (D10).
- Use at most 3 weights per screen (500, 600, 700). Never 400 for numbers.

### 6.3 Spacing and shape
- Use a 4-pt scale as tokens `--s-1 … --s-8` = 4, 8, 12, 16, 20, 24, 32, 48 px:
  - card padding `--s-5` (20);
  - grid gap `--s-4` (16);
  - section gap `--s-7` (32);
  - main gutter 28 px on desktop and 16 px at ≤900 px (as today).
- Radii stay: 10 px cards, 8 px controls, 6 px badges, 999 px chips.
- Cross-tab cell gap: change it from 3–4 px tiles to a **1 px `--line` grid** (`border-spacing: 1px`). Cells read as a matrix rather than as buttons, and about 15% more columns fit on a laptop.

### 6.4 Component changes per screen

| P | Screen / component | Change | Files |
|---|---|---|---|
| **P0** | Overview "at a glance" | Replace the solid red header with a **surface card that has a 4 px red left bar** (the same motif as `.page-head h1`). Title in `--ink` 16/700, meta in `--ink-2`. Flatten the tiles: no nested shadowed cards, use a 1 px `--line` divider grid inside one card. Red then appears only where it means "focus" or "significant" (D1, D2) | `styles.css:469-520`, `components/Glance.tsx` |
| **P0** | Cross-tab | 6-step solid heat (§6.1), 1 px grid, sticky first column and header (already sticky top), six-step legend. Keep the amber outline on small-base columns. Make cell detail tap/focus-able (a `<button>` in the cell opening the hover card; doc 40 UI-08) | `theme.ts`, `pages/Crosstab.tsx:176-271`, `styles.css` `.xt` |
| **P0** | All controls | Borders to `--line-strong`. Focus: `outline: 2px solid var(--focus); outline-offset: 2px`, plus for text inputs `box-shadow: 0 0 0 3px color-mix(in srgb, var(--focus) 25%, transparent)` (D6) | `styles.css:42,79-90`, `.btn`, `.seg`, `.qnav input`, `components/ui/input.tsx` |
| **P0** | Loading | Add `Skeleton`, `SkeletonKpis`, `SkeletonChart({height})` and `SkeletonTable({rows, cols})` to `components/bits.tsx`, with the same outer dimensions as the real component, so the layout does not shift. Replace `<Loading/>` on Overview, Questions, Cross-tab, Trends and Library first. Keep `role="status"` and the sr-only "Loading…" text (D12) | `components/bits.tsx:64`, `pages/*.tsx` |
| **P1** | Questions toolbar | Collapse the 11 buttons into one row (D8):<br>• left: a `Bars | Columns | Table` segment and a `Total | Gender | Generation | All` segment;<br>• right: **Export ▾** (CSV, Excel, PowerPoint, PNG), **Pin**, and **⋯** (Alert me, Copy link).<br>• Move "Cross-tab / Trends / Compare" to a **tab strip under the question title**, shared by the four question views. They are sibling views, not actions | `pages/Explorer.tsx`, `pages/Crosstab.tsx`, `pages/Trends.tsx`, `pages/Compare.tsx`, a new `components/QuestionTabs.tsx` |
| **P1** | Question header | The question text becomes the `<h1>` (20/700), with the code pill and base chip above it (D9) | `components/QuestionNav.tsx` or the page headers |
| **P1** | Phone: split screens | At ≤900 px, hide `.qnav` and show a full-width **"Question q1 of 52 ▾"** button that opens the list in a `<dialog>` sheet (the PinDialog already uses `<dialog>`), so the chart is above the fold (D11) | `styles.css:418-446`, `components/QuestionNav.tsx` |
| **P1** | Phone: topbar | One 56 px row: menu, compact wave select (`Oct 19 · n=400`), search icon (opens the search as a sheet), theme. Today it is three rows and 164 px | `components/Shell.tsx:146-290`, `styles.css:187-196` |
| **P1** | Mobile drawer | `<dialog>` or focus trap, Escape and focus restore (doc 40 UI-18) | `components/Shell.tsx:43-57,187-196` |
| **P1** | Trends | Default to **4-week average on, raw points as 3 px dots** for ranges ≥6m (the YouGov and Datawrapper pattern). Show the **MoE band for the focus series by default**, since the brand promise is uncertainty. At most four coloured lines plus grey "others"; direct end labels already exist. Focus line `--red-line` 2.5 px | `pages/Trends.tsx:155-230` |
| **P1** | Dark frame | The rail gets a 1 px right border `#2D2A29`, and cards move to `--surface #242120` with `--line #3D3937` (D7) | `styles.css:24-34,60-70` |
| **P2** | Library | `content-visibility` on rows (S5). Collapse past years into `<details>` with a count. The hero "latest wave" card gets a KPI sparkline of n per wave (ECharts line, 40 px tall) | `pages/Library.tsx`, `styles.css` `.wave-row` |
| **P2** | KPI tiles | One style: label 12/600 `--ink-2`, value 34/700, delta chip, base note. Keep the dark "lead" tile in both themes but use `--raised` in dark so it stays distinct (today `--head #141211` almost disappears on the paper) | `styles.css:120-130` |
| **P2** | Empty states | One `Empty` component in `bits.tsx`: a 20 px lucide icon in `--ink-3`, one sentence, one action. Use it for "no waves match", "no audience cells ≥ 5", "fielded once" and similar | `components/bits.tsx`, `pages/*.tsx` |
| **P2** | Rail badge | Show "Verified sample" only when the backend says so, and in `--ink-2` rather than green (D13; doc 40) | `components/Shell.tsx:103` |

### 6.5 Motion
- Tokens:
  - `--ease: cubic-bezier(.2,.8,.2,1)`;
  - `--dur-1: 120ms` (hover, press);
  - `--dur-2: 200ms` (popover, sheet, segment);
  - `--dur-3: 320ms` (chart update; already `animationDurationUpdate: 320`).
- Chart entry stays at 480 ms. The count-up stays at 450 ms, and only on KPI tiles.
- Theme switch: drop the `<main key={theme}>` remount (`Shell.tsx:93`). Call `chart.setTheme()` (ECharts 6) or re-init through the registered theme (§6.6), and fade the background with `transition: background-color var(--dur-2), color var(--dur-2)` on `body`, `.card` and `.rail`. This keeps scroll position and focus on a theme switch, which today are lost.
- Skeleton shimmer:
  `background: linear-gradient(90deg, var(--fill) 25%, var(--hover) 50%, var(--fill) 75%); background-size: 200% 100%; animation: shimmer 1.2s linear infinite;`
- Under `prefers-reduced-motion: reduce`: no shimmer (solid `--fill`), no count-up, and chart `animation: false`. `REDUCED_MOTION` already exists in `EChart.tsx:21`.
- Remove `transform: translateY(-1px)` on `.glance-tile:hover` (`styles.css:498`). Lifting cards in a dense data view adds motion without meaning.

### 6.6 ECharts theme

Register two themes once in `components/EChart.tsx` and init with `echarts.init(el, savedTheme() === "dark" ? "cip-dark" : "cip-light")`. Today every option reads `C.*` at render time and `<main key={theme}>` remounts everything.

```ts
const base = (t: typeof LIGHT) => ({
  color: [t.redLine, t.s1, t.s2, t.s3, t.other],
  backgroundColor: "transparent",
  textStyle: { fontFamily: "Montserrat Variable, sans-serif", color: t.ink, fontSize: 12 },
  grid: { left: 8, right: 56, top: 16, bottom: 24, containLabel: true },
  categoryAxis: { axisLine: { lineStyle: { color: t.lineStrong } }, axisTick: { show: false },
                  axisLabel: { color: t.ink2, fontSize: 12 }, splitLine: { show: false } },
  valueAxis:    { axisLine: { show: false }, axisTick: { show: false },
                  axisLabel: { color: t.ink3, fontSize: 12 }, splitLine: { lineStyle: { color: t.line, type: [2, 3] } } },
  timeAxis:     { axisLine: { lineStyle: { color: t.lineStrong } }, axisLabel: { color: t.ink3, fontSize: 12, hideOverlap: true } },
  bar:  { itemStyle: { borderRadius: [0, 3, 3, 0] }, barMaxWidth: 26 },
  line: { symbol: "circle", symbolSize: 5, lineStyle: { width: 1.5 }, emphasis: { focus: "series" } },
  tooltip: { backgroundColor: t.raised, borderColor: t.line, borderWidth: 1, padding: [10, 12],
             textStyle: { color: t.ink, fontSize: 12 }, extraCssText: `box-shadow:${t.shadow2};border-radius:8px` },
  legend: { textStyle: { color: t.ink2, fontSize: 12 }, icon: "roundRect", itemWidth: 10, itemHeight: 10 },
  aria: { enabled: true, decal: { show: false } },
});
echarts.registerTheme("cip-light", base(LIGHT));
echarts.registerTheme("cip-dark", base(DARK));
```

Chart rules, to be enforced in `QuestionChart.tsx` and `Trends.tsx`:
1. **Data labels on every bar**, 12/600: `--ink` outside the bar, `labelOn()` inside it.
2. **Dashed 1 px horizontal grid only.** No vertical grid and no y-axis line.
3. **The top answer in red, everything else in sky.** This is already the rule; add the 1 px `#5B8FAD` border on sky bars in light.
4. **The MoE band in the focus series' colour at 14% opacity.** Today it is hard-coded `rgba(214,46,47,.16)` (`Trends.tsx:207`); use the token.
5. **Never rotate axis labels.** Use `hideOverlap` (already) and a 2-line `formatter` for long bar labels (cap at 32 characters plus an ellipsis, with the full text in the tooltip).
6. **Significance rings:** a `--surface` fill with a 2 px series-colour stroke (already). Add an `aria` description of "significant change at <date>".
7. **PNG export:** `downloadPng` (`EChart.tsx:24-50`) should always render on the **light** theme, whatever the UI theme, because PNGs go into decks. Export with `getDataURL` from an off-screen chart initialised with `cip-light`.

### 6.7 Focus and accessibility
- Global: `:focus-visible { outline: 2px solid var(--focus); outline-offset: 2px; border-radius: inherit }`. On red primary buttons, use an `outline-offset: 3px` ring in `--ink` so it does not disappear into the red.
- Chart canvases (`tabIndex=0`, `EChart.tsx:102`) get the same ring. Arrow keys move an `axisPointer` through the points via `dispatchAction({type:'showTip'})`, so keyboard users can read values (Highcharts' keyboard navigation is the bar: YouGov and Statista have it).
- Hit targets: 36 px minimum on desktop and **44 px on phones** (`.seg button` is 30 px today, `styles.css:170`).
- The skip link exists. Add `aria-current="page"` on the active rail link if it is missing.

### 6.8 Acceptance checks (to be run on a :8001 or `vite preview` copy, never on :8000)
1. axe-core or Lighthouse accessibility ≥ 95 on the five screens in both themes.
2. Every text/background pair in §6.1 is re-measured in DevTools.
3. Cold FCP ≤ 0.8 s on desktop (through the tunnel) after S1. CLS ≤ 0.02 with skeletons.
4. Phone: the chart or matrix is visible in the first 844 px on Questions, Cross-tab and Trends.
5. Theme switch: no request, scroll position kept, all charts re-themed in under 100 ms.
6. PNG export identical in both UI themes.

---

## 7. Top 10 UI items, in priority order

1. **Token set (§6.1):** `--line-strong` for control borders, `--focus`, `--ink-3`, a dark `--surface #242120` and a rail border, mirrored in `theme.ts`. It fixes D6 and D7 and makes both themes AA. Files: `styles.css:3-34`, `theme.ts:3-22`.
2. **Overview "at a glance" without red wallpaper.** A surface card with a 4 px red bar and flat tiles. Red is kept for meaning only. Files: `styles.css:469-520`, `Glance.tsx`.
3. **Cross-tab six-step solid heat ramp** with per-step ink, all cells ≥4.5:1 in both themes, a 1 px grid and a six-swatch legend. It fixes the dark 3.9:1 failure. Files: `theme.ts:42-55`, `Crosstab.tsx:176-271`.
4. **Skeleton loaders** in `bits.tsx` that match the real dimensions, replacing the text spinner on the five main screens.
5. **Inline app shell in `index.html`** (S1), plus modulepreload and font preload. Cold first paint from 1.5 s to about 0.7 s on the tunnel.
6. **Registered ECharts themes** `cip-light` and `cip-dark` (§6.6): solid series ramps, 12 px axes, dashed grid, a sky-bar border in light, a brighter red focus line in dark, light-only PNG export, and no `<main key={theme}>` remount.
7. **Questions toolbar collapsed to one row** (Export ▾, Pin, ⋯) plus a shared **Cross-tab / Trends / Compare tab strip**. The question text becomes the `<h1>`.
8. **Phone layout:** the question list becomes a "Question ▾" sheet, the topbar becomes one 56 px row, and hit targets are 44 px. The chart is above the fold.
9. **Trends defaults:** 4-week average with raw dots, the MoE band on for the focus series, at most four coloured lines plus grey others, and a 2.5 px focus line.
10. **Typography clean-up:** a 7-step scale, no uppercase, 12 px meta and axis text, KPI tracking at −0.02em, and a theme cross-fade instead of a remount (§6.2, §6.5).

---

## 8. Evidence files

All in `screens/benchmark/`:
- `cip-desktop.jsonl`, `cip-mobile.jsonl`, `vendors.jsonl`: raw per-visit metrics, including the request list and API timings;
- `finger.jsonl`: framework fingerprints;
- `cip-{d,m}-<screen>-{light,dark}.png`: 20 CIP captures;
- `v-d-<vendor>.png`: 14 vendor captures;
- `v-grid-public-trackers.png`: composite of 4 public data pages.

The probe scripts are in the session scratchpad and are not in the repo:
- `bench/bench.mjs`;
- `bench/finger.mjs`;
- `bench/darkprobe.mjs`;
- `bench/contrast.py`.
