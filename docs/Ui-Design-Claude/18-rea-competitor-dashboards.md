# 18 · How public survey and polling sites show data in the browser (REA observation)

**Captured:** 21 Oct 2026, by Claude, using REA (reverse-engineer-anything) against a headless Chrome 155 on CDP `127.0.0.1:9333`. Public pages only. No sign-in, nothing submitted, non-essential cookies declined (YouGov "Don't Accept"). Every target opened was closed afterwards.

**What this adds to [15](15-competitor-patterns.md).** Doc 15 is desk research from vendor help pages. This doc covers what the live pages actually do: the stack, how data reaches the chart, payload sizes, controls, accessibility and theming. It does not repeat doc 15's feature matrix.

**Evidence rules.**
- **Observed (REA):** network, accessibility tree, screenshots and bundle analysis, cited by Evidence ID (`ev_…`).
- **Measured (curl):** byte sizes, fetched once with plain GETs of the same public URLs. REA was run without response bodies, so its captures don't record sizes.
- **Inferred:** our reading of the evidence. Marked **[inferred]**.

**Limits.**
- REA's scenario runner has no hover action, so tooltips were not triggered. Tooltip content below is inferred from each chart's accessibility labels and data shape.
- Connect-mode captures used the headless window, about 756 × 470 px. The screenshots therefore show near-phone layouts.

## 1. What loaded

| Site | URL captured | Result | Evidence |
|---|---|---|---|
| Our World in Data grapher | `ourworldindata.org/grapher/life-expectancy` | Loaded; Table tab exercised | `ev_183c1806…4ef4e4`, `ev_937cc33d…db0734`, passive `ev_0dd07cfa…d2ce3` |
| YouGov public tracker | `yougov.com/en-us/trackers/amy-klobuchar-favorability` | Loaded. Cookies declined, then 6m range and "What is this?" clicked | `ev_f31d32dd…a166f1`, `ev_cd50e95e…910d8d` |
| YouGov economy tracker | `today.yougov.com/topics/economy/trackers/state-of-the-economy` | **404** after redirect. The slug no longer exists | `ev_ce604415…68aee` |
| Civiqs | `civiqs.com/results/economy_us_now` | Loaded | `ev_8bfaa978…8c76f` |
| Datawrapper (YouGov BrandIndex chart) | `datawrapper.dwcdn.net/W3Lmi/1/` | Loaded | `ev_901461fd…bcd21` |
| Gallup topic trends | `news.gallup.com/poll/1609/consumer-views-economy.aspx` | Loaded (12 Datawrapper iframes) | `ev_c805859c…5b20f` (full ID in §6) |
| Statista free statistic | `statista.com/statistics/273018/…` | Loaded; bundle analysed | `ev_cc28cdbc…bd6ab9`, bundle `ev_08ea7ed2…a15` |
| Ipsos What Worries the World | `ipsos.com/en/what-worries-world` | Loaded (Flourish iframe) | `ev_6e66955b…dd09fdb260` |
| Morning Consult trackers | `intel.morningconsult.com/mc-content/trackers` | Index loaded. Each tracker (e.g. consumer confidence) **301-redirects to the marketing homepage**, so the data is gated | `ev_cf192790…abe373`, `ev_6116db0b…8be2f85` |
| Pew Research data tool | `pewresearch.org/religious-landscape-study/database/` | **Bot check ("Checking your browser…")**. Not bypassed | target list `ev_cf6fbf1e…122578` |
| Ipsos consumer tracker | `ipsos.com/en-us/ipsos-consumer-tracker` | 404 | target list `ev_cf6fbf1e…122578` |

Full Evidence IDs are listed in §6.

## 2. Per-site findings

### 2.1 Our World in Data grapher (the reference for chart interaction)

**Stack**
- One ES-module bundle, `owid.mjs`, about 1.06 MB, plus `owid.css`.
- React (`createRoot`) with MobX state (36 `mobx` references in the bundle).
- Charts are custom SVG, with no third-party chart library. **[inferred from the bundle strings and the SVG accessibility tree]**

**Data**
- Two JSON files per indicator, from a separate API host:
  - `api.ourworldindata.org/v1/indicators/1118466.data.json`: about 75 KB;
  - `…metadata.json`: about 10 KB.
- Page HTML is about 25 KB.
- Requests: 49 cold (Evidence `ev_183c…`) and 28 warm (`ev_937c…`). Most of the remainder are fonts (17) and analytics.

**Controls** (accessibility tree)
- Tabs: `Table / Map / Line / Bar`.
- Buttons: "Edit countries and regions", "Play time-lapse".
- Time range slider with two thumbs labelled "Start time: 1770" and "End time: 2023".
- Download, Share, Enter full-screen.
- Switching to Table changes the URL to `?tab=table` and fetches no new data.

**Table view**
- A real `<table>` with columns *Country or region / 1543 / 2023 / 1543 to 2023 (sparkline cell) / Absolute Change / Relative Change*.
- "Filter by: All (265)" and a country search box.

**Provenance next to the chart**
- Data source line and licence (CC BY).
- A definition list: *Description, Data source, Unit, Date range, Last updated 2025-10-22, Next expected update 2026-10-22, Managed by*.
- Downloads: **"Download full data"** and **"Download displayed data"** (ZIP of CSV + metadata JSON + README).
- Copyable CSV and metadata URLs, with code examples.

**Accessibility**
- The chart SVG exposes its axis ticks and series names as image text.
- Every control is a labelled tab, slider or button.

**Dark mode:** none. `owid.css` contains no `prefers-color-scheme` rule.

**Responsive:** at about 756 px wide, the series labels sit at the end of each line, not in a legend.

### 2.2 YouGov public tracker

**Stack**
- Angular 21.2.7 (`ng-version`), server-rendered, served from CloudFront `ashes/…/main.js`.
- Highcharts 12.6.0, found in `main.js` together with its accessibility module.

**Data**
- One JSON fetch per tracker: `api-test.yougov.com/public-data/v5/us/trackers/<slug>/overall/`.
  - Size: **4.96 KB raw, 775 B on the wire**.
  - Shape: `{raw_values: [[…164 per series]×3], values: [[…]×3]}`. These are the weekly values and the smoothed trend, one array per answer, with **`null` for missing waves**.
- The page HTML is about 737 KB raw (121 KB gzipped). Most of it is the Angular transfer state (`yg-app-state`, 238 KB): menu, i18n and related content. Only about 3 KB is the tracker's own details.
- Requests: 99–106 in total, 47–51 of them images. Most of the 28 scripts are third-party (VWO, OneTrust, New Relic, Trustpilot).

**Controls**
- One button per answer (Favorable / Unfavorable / Don't know) to show or hide it.
- A population combobox ("US Registered Voters").
- `3m / 6m / 1yr / all`. Clicking 6m sets `?period=6m` and re-renders **without a new fetch** (`ev_cd50…`: only the first two API calls appear).
- "Hide trend line", plus "What is this?". The latter opens: *"Trend lines are linear regressions computed using a LOESS smoother…"*.
- A floating share button.

**Methodology block**
- "Weekly tracker / 1061 - 1322 US Registered Voters per wave / Methodology / **Download crosstabs**".
- The download is an XLSX file, `content-disposition: attachment; filename=amy-klobuchar-favorability.xlsx`, 56 KB. Its headers were checked with a HEAD request; it was not downloaded.

**Latest values**
- Printed as text at the end of the lines ("29TH MAR 2022 35.5 % 31.1 %").
- A dashed vertical cursor marks the latest wave.

**Accessibility:** Highcharts' generated region reads *"Combination chart with 6 data series… Data ranges from 14.7 to 46.6"*, with one region per series, e.g. *"Line with 164 data points"*. After the 6m click it updated to *"24 data points… 31.1 to 35.5"*.

**Weaknesses seen:** x-axis dates are **rotated about 40°**. The chart shows no margin of error or band.

**Dark mode:** none observed.

### 2.3 Civiqs

**Stack**
- Remix / React Router, with route chunks such as `_app.results_._question-….js` and `entry.client`.
- Headless UI components; d3, referenced in `ActiveDemographics`.
- Tailwind `dark:` classes appear in `_app`, but no dark toggle is visible.

**Data**
- Server-rendered into `window.__remixContext`. **There is no data XHR.**
- Page HTML is **10.2 MB raw, 1.76 MB gzipped**.
- Inside `routes/_app.results_.$question` (6.48 MB):
  - `topline`, 4.8 MB: daily series for 4,297 days, each point with `value`, `low` and `high`. It also carries `ci_high`, `ci_low` and `trendline`, all duplicated as `filtered_topline` and `unfiltered_topline`;
  - `net_data`, 215 KB;
  - `crosstabs`, 3 KB: every subgroup's latest split, plus `population_warning: false`;
  - `related`, **1.68 MB**: the full data of four related polls, used only for their thumbnails.

**Header:** *"National Economy: Current Condition · Registered Voters · January 15, 2015—October 19, 2026: 1,211,977 Responses"*.

**Controls**
- "Refine By" (subgroup filter).
- Legend buttons that also act as answer toggles ("41% - Very bad").
- Trendline / Net Good views.
- Switches: **Uncertainty Range** (on), **News & Events** (on), Zoom In (on), Sum Totals. The URL keeps `?uncertainty=true&zoomIn=true&annotations=true`.

**News & Events:** about 20 labelled events on the time axis ("Coronavirus stock crash", "Tariff announcement", …). The labels are rotated about 45°.

**Subgroups:** under the chart, every demographic (age, education, gender, party, race) is listed with its full answer split for the selected date. Each is a link that refines the chart.

**Accessibility:** weak. The chart is an unlabelled `img`, and there is no table fallback for the trend.

### 2.4 Datawrapper (YouGov BrandIndex chart, and Gallup's embeds)

**Stack**
- `dw-2.0.min.js` and `d3-lines.js` vis, with Svelte markup.

**Data**
- One `dataset.csv` fetch per chart: **1.6 KB** (TSV: date, Buzz, Ad Awareness, Current Customer).
- HTML about 56 KB (10 KB gzipped), with the chart config inline.
- 22 requests per chart, 11 of them fonts.

**Theming**
- `<meta name="color-scheme" content="light dark">`.
- Two stylesheets switched by media query, `css-light` with `media="(prefers-color-scheme: light)"` and a dark one. The embed follows the reader's system theme.

**Annotation:** "Moving average: 4 weeks" is printed under the chart. The source line reads "YouGov BrandIndex | 1 November 2023 to 3 January 2024". Share links appear in the footer.

**Accessibility:** only `img "Line chart with 2 lines"` plus the title and description.

**Gallup** (`ev_c805…`)
- The topic page is a share bar plus **12 Datawrapper iframes**, mostly `d3-lines`.
- Iframes load lazily. Only 3 `dataset.csv` fetches happened in the 7-second window. 33 of the 85 requests went to dwcdn.
- Chart notes carry the methodology caveats, e.g. "Gallup also asked the Economic Confidence Index questions in four 1992 polls…".

### 2.5 Statista

**Stack** (bundle `ev_08ea…`)
- React + React Router, built with Vite / rolldown (`rolldown-runtime`).
- Highcharts 12.6.0 with the export-data module (`export-data.src`, 682 KB raw).
- 14 scripts, about 2.8 MB raw in total.

**Data:** inlined in the server-rendered HTML (387 KB raw, 77 KB gzipped). There is no data fetch.

**Controls**
- "Switch chart type": zoomable line, zoomable column, or table.
- "Category filter: 21/21 categories" and Download.
- "Click here to show source details", "Open citations", Share, **"Copy data"**, **"Copy data for AI"**, **"Ask AI"**.

**Context shown:** *Region: Worldwide*, *Survey time period: 2005 to 2025*, a source link, and "figures are estimates".

**Accessibility:** the best observed.
- *"Line chart with 21 data points"* and a **"View as data table, Chart"** button.
- An axis description and data range.
- **One labelled image per point** ("2019, 4,200.00. Number of users in millions."), so the points are keyboard reachable.

### 2.6 Ipsos What Worries the World

**Stack:** a Drupal page with one **Flourish** iframe (`flo.uri.sh/visualisation/25891557/embed`). The Flourish HTML is 418 KB raw (124 KB gzipped), with the template code and data inline (`_Flourish_data`, `_Flourish_data_column_names`).

**Page content:** KPI headings ("28%", "61%"…) as "key findings at a glance", followed by a downloadable PDF report.

### 2.7 Morning Consult

- The tracker index is a Next.js pages-router site under `/mc-content`.
- The consumer-confidence tracker 301-redirects to the marketing homepage. The public tracker pages that doc 15 cited [29] are no longer public.
- Nothing to compare at chart level.

## 3. Cross-site patterns REA adds to doc 15

| Pattern | Who | Notes |
|---|---|---|
| **Small JSON or CSV per chart, fetched once; all view changes client-side** | OWID (75 KB), YouGov (775 B wire), Datawrapper (1.6 KB) | Range, tab and series toggles never refetch. View state lives in the URL (`?tab=table`, `?period=6m`, `?uncertainty=true`) |
| **Inline everything** (the anti-pattern) | Civiqs (1.76 MB gzipped per page), Statista, Flourish | Civiqs ships CI arrays twice and full data for related-poll thumbnails |
| **Missing waves as `null`** | YouGov `raw_values` | The same rule CIP already follows |
| **Raw and smoothed series sent together, with smoothing explained on demand** | YouGov ("What is this?" → LOESS), Datawrapper ("Moving average: 4 weeks") | |
| **Latest value labelled at the end of each line** | OWID, YouGov | Replaces the need for a legend on phones |
| **Event annotations on the time axis, toggleable** | Civiqs "News & Events" | |
| **All subgroups for the selected date listed under the trend; click to refine** | Civiqs | |
| **Provenance as structured data beside the chart** | OWID (last/next update, unit, source), YouGov (n range per wave, methodology, crosstab XLSX), Civiqs (population, dates, total responses), Statista (region, period, citations) | |
| **Two download scopes** | OWID "full" vs "displayed" | Plus copyable data and metadata URLs |
| **Generated chart descriptions for screen readers** | Highcharts sites (YouGov, Statista): series count, points, data range, per-point labels, "View as data table" | Datawrapper and Civiqs only give a one-line alt text or nothing |
| **Embed follows the system theme** | Datawrapper | OWID, YouGov and Statista showed no dark mode |
| **Rotated axis or event labels** (avoid) | YouGov dates, Civiqs events | CIP's style guide forbids this |

## 4. Where the CIP portal already leads

- **Payload:** one `/book` per wave is 23 KB gzipped and feeds five screens ([16](16-portal-and-staging-test.md) §4). That is smaller than YouGov's HTML around a 775-byte series, and about 75× smaller than one Civiqs page.
- **Uncertainty:**
  - CIP: an MoE band toggle, white rings on significant week-on-week moves, sig letters in cross-tabs, and small-base fading and suppression;
  - Civiqs: an uncertainty band but no significance markers;
  - YouGov and Statista: neither.
- **Gaps:** CIP leaves missing weeks as gaps, the same as YouGov's nulls.
- **Dark mode:** CIP follows the system setting before first paint, with a manual toggle (`web/index.html`, `src/theme.ts`). Only Datawrapper matches this.
- **Axis labels:** CIP never rotates them; YouGov and Civiqs do.
- **URL state:** CIP keeps the view, cut, reference column, pooled weeks, range and answers in the URL. This is equal to or better than OWID and YouGov.

## 5. Gap list: where CIP lags, ranked by value

Ranked by trust and everyday use for Coresight analysts and clients, then by cost. "Code" names the file that would change.

| # | Gap | Who does it | CIP today | Concrete fix |
|--:|---|---|---|---|
| 1 | **Provenance block per chart and trend** | YouGov "Weekly tracker / 1061–1322 … per wave / Methodology / Download crosstabs". OWID "Last updated / Next expected update / Unit / Source". Civiqs population, date span, total responses | Wave n in the top bar and base per chart. No population label, no n range across a trend, no "unweighted" disclosure, no methodology link, no next-wave date | Add a footer under every chart card: *Population · fieldwork dates · n (or n min–max across the trend) · Unweighted · Methodology link · Next wave expected*. `bits.tsx` gets one `Provenance` component used by Explorer, Crosstab, Trends and Overview. The data is already in `/book` and the trend payload |
| 2 | **Shareable chart artefact: PNG with title, wording, base and source; Copy link; Share** | OWID Download / Share / full-screen; Statista Download, Share, citations; YouGov share; Datawrapper share footer | CSV only. URL state exists but there is no button for it | `EChart.tsx`: expose `getDataURL()`, then draw the header (code, wording) and footer (provenance from gap 1) onto one canvas → PNG. Add a "Copy link" button using `navigator.clipboard.writeText(location.href)`. Overlaps doc 15 pattern 15, but REA shows the minimum bar is *PNG + link*, not PPTX |
| 3 | **Screen-reader chart description and keyboard points** | Highcharts on YouGov and Statista: "Line with 164 data points… ranges from 14.7 to 46.6", one label per point, "View as data table" | `<div role="img" aria-label={label}>` around a canvas: one static label, no data, no keyboard reach | Register ECharts `AriaComponent` (`aria: { enabled: true }`) in `EChart.tsx` for auto descriptions. Build `label` from the data (series count, range, latest value, significant moves). Add a visually hidden "View as table" link to the table each screen already renders. Decal patterns (`aria.decal`) for colour-blind users on stacked and donut charts |
| 4 | **Direct end-of-line labels with the latest value** | OWID, YouGov | Legend checkboxes under the chart with the latest % | `Trends.tsx`: `endLabel: { show: true, formatter: "{a} {c}%" }` on shown series. Keep the checkbox legend for choosing series. Fixes phone reading, where the legend wraps under the fold |
| 5 | **Explain smoothing and the band in place** | YouGov "What is this?" → LOESS text; Datawrapper "Moving average: 4 weeks" note | "4-week average" and "Margin of error" checkboxes with no explanation | One "?" popover per toggle with one sentence each (*"Average of this and the previous 3 waves; gaps are skipped"*, *"95% margin of error at this wave's base"*). When the average is on, print "4-week moving average" in the chart subtitle and in the PNG |
| 6 | **Event annotations on trends** | Civiqs "News & Events" toggle with about 20 labelled events | None | A small `cip_event` table (date, label). Draw it as ECharts `markLine` with **horizontal** labels or numbered flags (not rotated), behind a "Events" toggle stored in the URL. Retail use: Prime Day, Thanksgiving / BFCM, tariff announcements, CPI releases |
| 7 | **All subgroups for the selected wave under the trend; click to refine** | Civiqs "Subgroups" list; each link refines the chart | One banner column at a time via a select | Under the trend, a compact table: rows are banner columns (gender, generation, income, region), cells are the focus answer % with sig vs Total. Clicking a row sets `?col=`. The data is already in the wave's `/book` |
| 8 | **Net / Top-2 as a view** | Civiqs "Net Good" (server-computed `net_data` series) | Open item in doc 16 §7 | Compute net (top-2 minus bottom-2) client-side from the existing series for scale questions detected in `QuestionChart.tsx`. View-level only, never stored (doc 15 §2.9) |
| 9 | **Two download scopes and a stable data URL** | OWID "Download full data" vs "displayed data" ZIP (CSV + metadata + README); copyable CSV and metadata URLs; YouGov crosstab XLSX | CSV of the current view only | Add "Full question (all waves, all columns)" next to the existing CSV, served by the API as CSV with a metadata header (wording, base, fieldwork, unweighted). Show the API URL with a copy button for analysts. XLSX only if clients ask; CSV covers Excel |
| 10 | **Table view with sparkline and change columns** | OWID table: sparkline cell, absolute and relative change between two chosen periods, search | Tables in Explorer and Trends; What changed lists Δ vs last week or last year | Add a sparkline column (last 12 waves, inline SVG, no library) and an "absolute / relative" change toggle to `Changes.tsx` |
| 11 | **Embeddable chart that follows the reader's theme** | Datawrapper `color-scheme: light dark` with media-switched CSS; Flourish iframes in Ipsos and Gallup articles | None | Defer until reports need live embeds. A `/embed/...` route that renders only the chart card, plus provenance, reading `prefers-color-scheme` |
| 12 | **"Copy data for AI" / "Ask AI"** | Statista | None | Defer. If wanted, a "Copy as Markdown table" button with wording and base covers most of it without an LLM |

Not gaps (seen but not worth copying): the OWID time-lapse "Play" button, Civiqs inlining megabytes of data per page, Statista's 2.8 MB of JavaScript, YouGov's rotated date labels, and YouGov showing no margin of error.

## 6. Evidence index

| Evidence ID | What |
|---|---|
| `ev_cf6fbf1e83bbb8a481ee9b4f890fd7dfa4d66bdbfc4f093d4a660c38f3122578` | Target list (Pew bot check, Ipsos 404, Morning Consult redirect) |
| `ev_0dd07cfae3e38753d42bec1badd7625b07f3ed4ecba25275b77307e9786d2ce3` | OWID passive page inspection (accessibility tree, 1,214 DOM nodes) |
| `ev_183c1806c4e513a66803d1b938288f5a698a058d63c8d4963de7d85b7f1ef4e4` | OWID cold load: network (indicator data and metadata JSON), accessibility tree, screenshot |
| `ev_937cc33d84c33a92b0e91ed197ff063cd275835299557dcb7616db6f86db0734` | OWID Table tab: `?tab=table`, no refetch, table structure |
| `ev_ce604415f368def3565849722733b33ae697e8c4858a42cc537ec2684ed68aee` | YouGov economy tracker 404 |
| `ev_f31d32dd25d87b442d4caf48adc0be3c64e8b6010a20826a579a8160a46166f1` | YouGov tracker load: `overall/` JSON fetch, Highcharts accessibility regions, methodology block |
| `ev_cd50e95e0d474c745a72735aed577c892b45c0408f09b870a23e4436e3910d8d` | YouGov: decline cookies, 6m (`?period=6m`, no refetch), "What is this?" LOESS text |
| `ev_8bfaa978394456bf3896207cc403ec26b1029cad0c600e648c3f627fdbf8c76f` | Civiqs: Remix chunks, no data XHR, toggles, subgroup list |
| `ev_901461fd066f62c9a7869c2639232685a8d4266a5198c2ae13a04a34097bcd21` | Datawrapper chart: `dataset.csv`, d3-lines, accessibility tree |
| `ev_c805859c6be41982546a65e55caacbfe088804e1699bf3157c55a2059e55b20f` | Gallup: 12 Datawrapper iframes, lazy `dataset.csv` |
| `ev_cc28cdbc884d186830c83dd9ea2a2c638661d4084e27d4d31971211529bd6ab9` | Statista: controls, Highcharts accessibility, source block |
| `ev_08ea7ed28af1cc0e42242addaa2d4abe21be83e83c99b32d9274216b8b303a15` | Statista bundle: React + Vite / rolldown, Highcharts export-data, 14 scripts |
| `ev_6e66955bd356ec197ecf7e6962f08f15ed833a4da71f36878dc788dd09fdb260` | Ipsos: Drupal + Flourish embed |
| `ev_cf192790e89f342c10a8b89e7162f69565af43f50425033b72d17cfa79abe373` | Morning Consult tracker index (Next.js) |
| `ev_6116db0bed87a92088507cac6aa541210efbca6d91f862822a2feea588be2f85` | Morning Consult tracker → 301 to homepage |

**Measured with curl:**
- byte sizes;
- YouGov `overall/` JSON shape;
- Civiqs `__remixContext` breakdown;
- Highcharts version strings;
- the `prefers-color-scheme` checks.

These are not REA evidence. Re-run them with the same public URLs.
