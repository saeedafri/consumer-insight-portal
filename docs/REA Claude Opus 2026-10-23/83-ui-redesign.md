# 83 · UI redesign: both themes (implements doc 70 §6–§7)

**Date:** 23 Oct 2026 · **Scope:** `web/src/*` and `web/index.html` only. Builds on [82-fixes-frontend.md](82-fixes-frontend.md) without undoing any of it.

**Guard rails:**
- `web/dist` was not written (its timestamp is still 22 Oct) and `npm run build` was not run.
- Port 8000 and cloudflared were not touched. `/healthz` on the public link returned 200 after the work.
- Nothing was committed and no dependency was added.

**Not deployed:** the live link still serves the old bundle. Deploying means building into `web/dist`, and that is the user's decision.

## Verification

| Check | Result |
|---|---|
| `npx tsc --noEmit -p web` | clean |
| `node web/src/stats.check.ts` | passes |
| Scratch build `vite build --outDir <scratchpad>/ui-dist` | succeeds (sizes below) |
| Live walk | Scratch Vite on :5179 proxied to the public tunnel, GET only. Headless Chrome (playwright-core, closed after). 5 screens × 2 themes × 2 sizes, before and after. 0 page errors, 0 console errors (apart from the known /me and /methodology 404s), 0 non-GET requests |
| Headings | exactly one `<h1>` on every screen captured |
| Horizontal overflow | 0 px at 1440 and at 390 px |
| Theme switch (Trends) | 0 requests. `<main>` is not remounted (a DOM marker survives). Scroll stays at 400 px. Canvas and heat cells re-colour in place |
| PNG export | The file is byte-identical whether the UI is dark or light (sha1 `f9f2bfc8074f` both times) |
| Export menu | Opens with Enter and closes with Escape. Focus returns to the summary |
| Phone question sheet | Opens with all 52 questions. Picking one navigates (`/w/415/crosstab/D31`) and closes the sheet |
| Phone touch targets | 0 visible top-bar, segment, button or sheet controls under 44 px |
| Contrast | 31 key pairs measured with the WCAG 2.x formula in both themes, **0 failures** (table below) |

## Spec item → change

| # (doc 70 §7) | Change | Where |
|---|---|---|
| **1 Tokens** | Implemented the §6.1 token set for both themes:<br>• new `--line`, `--line-strong`, `--ink-3`, `--raised`, `--focus`, `--shadow-2`, `--rail-edge`;<br>• dark `--surface #242120`, `--raised #2D2A29`, rail `#121010` with a 1 px `#2D2A29` right edge (fixes D7);<br>• every control border moved from `--silver` to `--line-strong` (fixes D6);<br>• focus ring is `--focus`, with an ink ring offset 3 px on red buttons;<br>• card shadow is a 1 px lift only.<br>`--mist` is kept as an alias of `--line`, so no other rule had to change. `theme.ts` mirrors the tokens: solid series ramp `s1–s3` plus `other`, `redLine`, `lineStrong`, `ink3`, `raised`, the scale colours per theme (§6.1 dark values), and six heat steps with their own ink | `styles.css:6-62`; `theme.ts:4-41` |
| **2 Overview** | "At a glance" is now **one plain surface card with a 4 px red left bar**. The title is in ink at 16/700 and the meta in ink-2. Tiles are **flat on a 1 px `--line` grid** inside the card, with no nested cards, no shadow and no hover lift (fixes D1 and D2). Key takeaways sit inside the same card. **Speed:** `useQueries` starts every `/dashboards/*` request **at the same moment as `/book`**: measured start times were 331, 332, 333 and 333 ms, against "after the book" before. `api.ts` gained a `dashboardQuery()` that both `useDashboard` and Overview use | `styles.css:488-508`; `Glance.tsx:45,64-68`; `Overview.tsx:22-26`; `api.ts:139-142` |
| **3 Cross-tab** | `heatStep(v/max)` gives **six solid steps with their own ink** (§6.1 hexes). Every cell measures ≥4.8:1 in light and ≥5.2:1 in dark, which fixes D3's 3.9:1. Tiles became a **1 px `--line` grid** (`border-spacing: 1px`) with an outline instead of a scale on hover. A **six-swatch legend** replaces the two-swatch one. The sticky column shadow is gone, and the amber small-base outline stays | `theme.ts:77-80`; `Crosstab.tsx:56,182,222,276`; `styles.css:322-341` |
| **4 Skeletons** | Added `Skeleton` and `SkeletonScreen({kind: page \| library \| overview \| question})`, whose boxes match the real page's boxes (page-head, hero and KPIs, glance block, KPI row, split with qnav, header card and chart card). It keeps `role="status"` and an sr-only "Loading…". There is a shimmer, which becomes solid `--fill` under reduced motion. Used on:<br>• Library, Overview, Questions, Cross-tab, Trends and Compare;<br>• the Trends chart and the Compare table;<br>• Glance;<br>• the route `Suspense` fallback | `bits.tsx:76-102`; `styles.css:747-753`; `main.tsx:30` |
| **5 App shell** | `index.html` has an **inline shell**: dark rail with brand text, a 56 px top bar, and a heading skeleton with the red bar. It uses about 1.3 KB of themed critical CSS, so both themes paint correctly before JS. The **first route chunk** (Library or Overview) is requested before React renders (`main.tsx:82`). **The font preload was tried, measured and removed** (see Performance) | `web/index.html`; `main.tsx:81-83` |
| **6 ECharts themes** | `cip-light` and `cip-dark` are registered (§6.6: 12 px axes, category in ink-2, values in ink-3, dashed horizontal grid only, the series ramp, the raised tooltip). Charts init with the current theme and call **`setTheme()` on a switch**. `<main key={theme}>` is removed, and screens rebuild their option with the new palette through `useTheme()`. **PNG export always uses light:** the option is rebuilt with `inLight()` on an off-screen `cip-light` chart, and the header and footer are drawn in LIGHT colours | `EChart.tsx:13-58,84-108`; `theme.ts:46-62`; `Shell.tsx:45-47,120`; `QuestionChart.tsx:62-64` |
| **7 Toolbar and tabs** | **The Questions toolbar is now one row** at 1440 px:<br>• left: `Bars \| Columns \| Table` and `Total \| Gender \| Generation \| All`;<br>• right: **Export ▾** (CSV, Excel, PowerPoint, PNG image), **Pin** and **⋯** (sort by value, copy link, alert me).<br>`ExportButtons` became the Export menu plus Pin on every screen that uses it. `Menu` is native `<details>` that closes on Escape and on an outside click. The new **`QuestionTabs`** strip (Chart, Cross-tab, Trends, Compare waves; `aria-current`, gated on /me) sits under the question in all four views. The question text was already the `<h1>` (82, UI-17) and is now 20/700 | `Explorer.tsx:126-158`; `bits.tsx:181-220`; `QuestionTabs.tsx`; Crosstab, Trends and Compare headers |
| **8 Phone** | **Question ▾ sheet:** below 900 px the side list is hidden. A "q1 · question… · 1 of 52 ▾" button opens the same list in a modal `<dialog>` (Escape, backdrop tap). The duplicate breadcrumb and prev/next row is hidden. **The top bar is one 56 px row:** menu, wave select, a search icon that opens the search as a row under the bar, save and theme. Before, it was 3 rows and 164 px. Targets are **44 px**. On phones the horizontal-bar labels narrow to 130 px so the bars get room. **Chart above the fold:** Questions 864 → **583 px**, Cross-tab 725 → **716 px**, Trends 826 → **733 px** (viewport 844) | `QuestionNav.tsx:68-86`; `Shell.tsx:268-273`; `styles.css:781-817`; `QuestionChart.tsx:126` |
| **9 Trends** | For ranges of 6 months or more the default is **4-week average on**, with the **raw waves as 3 px dots**. The significance rings moved onto the raw dots, so they still show with the average. **The MoE band is on by default** for the focus series, at 14 % of its colour. **At most four colours** (red, then s1–s3, then grey `other`). The **focus line is `--red-line` at 2.5 px** (`#E5484A` in dark). Both defaults stay in the link once changed (`avg=0`, `band=0`) | `Trends.tsx:28-31,163-230` |
| **10 Type and motion** | **Seven-step type scale** as tokens (`--t-display` 28, `--t-h2` 20, `--t-h3` 16, body 14, data 13, meta 12, `--t-kpi` 34). The 10.5/11/11.5/12.5 px variants were folded into 12, and 13.5/14.5 into 14. **No `text-transform: uppercase`** is left (D10). Chart axes and labels are 12 px. KPI figures are tracked at −0.02em. A **colour cross-fade** (`--dur-2`, 200 ms) runs on body, rail, top bar, cards, qnav and tables. Motion tokens are `--ease` and `--dur-1/2/3` | `styles.css:30-35,55`; sizes throughout |
| **+ Library** | `.wave-row { content-visibility: auto; contain-intrinsic-size: auto 64px }` | `styles.css:392` |
| **+ Rail badge** | "Verified sample" uses rail grey, not green (D13). It still shows only when `wave.verified` | `styles.css:74` |

## Contrast (WCAG 2.x, computed from the shipped tokens)

Washes are composited onto the surface before measuring (dark red wash ≈ `#482423`, dark warn wash ≈ `#433720`).

| Pair | Need | Light | Dark |
|---|--:|--:|--:|
| ink on paper | 4.5 | 13.64 | 16.78 |
| ink on surface | 4.5 | 14.24 | 15.32 |
| ink-2 on surface | 4.5 | 6.63 | 9.33 |
| ink-2 on fill (chips, segments) | 4.5 | 5.88 | 7.73 |
| ink-3 on surface (axes, meta) | 4.5 | 4.82 | 6.09 |
| ink-3 on paper | 4.5 | 4.62 | 6.68 |
| red text on surface | 4.5 | 5.70 | 7.05 |
| sig text on red wash | 4.5 | 6.36 | 5.96 |
| blue link on surface | 4.5 | 6.92 | 8.37 |
| warn on warn wash | 4.5 | 5.41 | 6.88 |
| ok on surface | 4.5 | 6.38 | 8.54 |
| table header ink on head | 4.5 | 14.24 | 13.64 |
| rail ink on rail | 4.5 | 9.85 | 13.11 |
| white on red (primary button, code pill) | 4.5 | 4.89 | 4.89 |
| control border on surface | 3 | 3.61 | 3.37 |
| control border on paper | 3 | 3.45 | 3.69 |
| focus ring on paper | 3 | 4.69 | 7.72 |
| focus ring on surface | 3 | 4.89 | 7.05 |
| red fill (focus bar) on surface | 3 | 4.89 | 3.27 |
| focus line on surface | 3 | 4.89 | 4.08 |
| default bar on surface | 3 | 3.65 | 8.37 |
| series 1 / 2 / 3 | 3 | 6.92 / 5.05 / 3.51 | 8.37 / 6.21 / 4.44 |
| other series | 3 | 3.61 | 4.51 |
| cross-tab steps 1–6, text on fill | 4.5 | 13.08 / 10.74 / 7.45 / 4.82 / 5.05 / 6.92 | 12.61 / 9.52 / 6.43 / 5.19 / 7.87 / 11.86 |

Light control borders went from 2.12:1 (`#B2B2B2`) to 3.61:1. The dark heat cell went from 3.9:1 to 5.19:1 or better.

## Screenshots

All are in `screens/redesign/`. File names are `{before,after}-{d,m}-{library,overview,questions,crosstab,trends}-{light,dark}.png`: desktop 1440×900 and phone 390×844 @2x, for wave 415. Extra captures:
- `after-d-trends-switched-dark.png`: Trends after a live theme switch, scrolled to 400 px, with no remount;
- `after-m-question-sheet-light.png`: the phone question sheet.

## Performance

**Bundle (scratch builds, minified / gzip)**

| Chunk | Before (82) | After |
|---|--:|--:|
| entry `index-*.js` | 288.3 / 89.7 KB | 293.6 / 91.2 KB |
| shared `chunk-*.js` | 93.5 / 30.7 KB | unchanged |
| CSS | 36.9 / 8.4 KB | 41.6 / 9.6 KB |
| `charts-*.js` | 549.3 / 186.5 KB | unchanged |
| Overview route | 10.4 / 3.9 KB | 14.0 / 5.2 KB (`useQueries`) |
| `index.html` | 1.0 KB | 2.6 / 1.3 KB (inline shell) |

The entry grows by about 1.5 KB gzip: theme store, skeletons, menu. Every route is still code-split.

**Cold paint.** Measured on a local static server at slow-4G (150 ms RTT, 1.6 Mbps), cache disabled, 3 runs each, phone with 4× CPU throttling:

| Build | FP | **FCP** | DOMContentLoaded |
|---|--:|--:|--:|
| before (82) desktop | 0.92 s | **2.53 s** | 2.49 s |
| before (82) phone | 0.94 s | **2.59 s** | 2.52 s |
| after, with font preload | 1.21 s | 1.21 s | 2.74 s |
| **after, shipped (no font preload)** desktop | 1.02 s | **1.02 s** | 2.55 s |
| **after, shipped** phone | 1.04 s | **1.04 s** | 2.59 s |

- **FCP is 1.5 s earlier.** The shell paints as soon as the CSS arrives, instead of after the JS has run.
- **The font preload was measured worse.** It shares the slow link with the CSS and JS, so it cost about 0.2 s of first paint and app-ready. It was removed and the reason is noted in `index.html`.
- **The ~0.7 s tunnel target is not reached.** The ~42 KB stylesheet still blocks first paint. Two things would get there:
  - load the CSS without blocking (Vite `transformIndexHtml` or a `media="print" onload` swap in `vite.config.ts`, outside this pass's files);
  - S6, the long-cached HTML fallback in nginx.

**Other measurements:**
- Overview's dashboards now start with the book: in the live walk, three dashboard requests started 1–2 ms after `/book`.
- A theme switch makes 0 requests.

## Left for others / known limits

- **CSS is render-blocking** (see Performance). The next cold-paint gain needs `vite.config.ts` or nginx.
- **Keyboard chart reading** (§6.7: arrow keys through the points) is not done. Neither is **a focusable `<button>` in each cross-tab cell**; cells open their card on click or tap only.
- **Library `<details>` per past year and the KPI sparkline** (P2) are not done.
- **A shared `Empty` component with icon** (P2) is not done.
- **Phone wave select** shows "Oct 19, 2026 · n=…" truncated. A compact option label would need a separate list for narrow screens.
- **Reading order on phones:** the side list is now hidden on phones and the sheet is the only list, so the 82 note about DOM order no longer applies there.
- **Trends rings:** with the average on by default, rings sit on the raw dots, which makes weekly noise visible. That is intended (uncertainty display), but it is busier than a plain line. `avg=0` gives the old look.
