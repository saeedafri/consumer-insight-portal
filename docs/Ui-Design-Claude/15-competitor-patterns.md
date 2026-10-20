# 15 — Competitor UI patterns for survey dashboards

Research date: 20 Oct 2026. Scope: how leading survey and market-research analytics products present results, and what the CIP portal should copy. The portal serves Coresight's weekly US consumer survey: about 400 respondents a week, about 60 questions per wave, hundreds of archived waves, tracker questions repeated weekly, and banners Total / gender / generation / income / region.

**Evidence rules.** Every factual claim cites a numbered source (list at the end). Most sources are vendor help centres and marketing pages, so treat feature claims as vendor-reported. Text marked **[inferred]** is our own reasoning or recommendation, not a sourced fact. "n/f" in the matrix means not found in public docs. It does not mean the product lacks the feature, because many products (Morning Consult, Numerator, YouGov Profiles, Harmoni) put their docs behind a login. Crosstab.io returned no public product documentation, so it is left out.

---

## 1. Feature matrix

Y = documented publicly. n/f = not found.

| Product | Archive search / browse | Auto highlights | Chart-type switch | Nets / Top-2-box | Base n + small-base rule | Sig display | Trend sig vs prior / YoY | Cell tooltip stats | Saved views / share | PPT export |
|---|---|---|---|---|---|---|---|---|---|---|
| Qualtrics XM | n/f | Y Stats iQ [6] | Y at page create [4] | Y Top/bottom box metric [2] | Y response thresholds [3] | Letters A/a [1]; arrows in dashboards [2] | Y previous period + 1 yr [2] | Y arrow hover: direction + CI [2] | Y saved filters, public dashboard [4] | Y editable [4] |
| Q / Displayr | n/f | Y rank by significance [11]; Research Agent [13] | n/f | Y NET / Top-K [10] | Y min n for testing [9] | Arrows + blue/red, letters [8] | Y wave-to-wave, sparklines [11] | n/f | Y | Y auto-refresh [11] |
| Crunch.io (powers YouGov Surveys [26]) | Y folders, sort, search across datasets/variables/categories, date filter [18][19][24] | n/f | n/f | n/f | Y warn/suppress below threshold [17] | Green→red shading; click-to-compare; letters in export [15][20] | Y appended waves [23] | Y MOE + unweighted base [16] | Y decks, dashboards [21] | Y [21] |
| YouGov public trackers | Y topic pages, related trackers [25] | n/f | n/f | n/f | Y n per wave shown [25] | n/f | 3m/6m/1yr/all ranges [25] | n/f | Y share, crosstab download [25] | n/f |
| YouGov BrandIndex | n/f | Y "Biggest movers" list [27] | n/f | Net score -100..+100 [27] | n/f | Green arrows [27] | Y month-on-month sig [27] | n/f | n/f | n/f |
| YouGov Profiles | n/f | Y Z-score auto-highlights [28] | n/f | n/f | n/f | Z score [28] | n/f | n/f | n/f | n/f |
| Morning Consult | n/f | AI chat, AI news summaries [29] | n/f | n/f | n/f | n/f | 5-day moving averages [29] | n/f | Y export, API, scheduled [29] | n/f |
| Infotools Harmoni | n/f | Y smart highlighting, alerts, ChatHarmoni [30] | n/f | n/f | n/f | n/f | Y time-series tools [30] | n/f | Y | n/f |
| Toluna Start | n/f | n/f | n/f | n/f | Y min base setting [31] | Y [31] | n/f | n/f | Y secure web page [31] | Y [31] |
| Pollfish | n/f | n/f | Table / column / pie [32] | n/f | Completes shown [32] | n/f | n/f | n/f | Y share link [32] | n/f (PDF/XLS/CSV/SPSS) [32] |
| SurveyMonkey | n/f | Y Insights (30–10k responses) [38] | Y 8 types + "apply to all" [38] | Combine choices [38] | Y n<30 → "More responses needed" [38] | Blue highlight, group letters [38] | Time-period compare rule [38] | Y sig message on hover [38] | Y shared data pages [38] | Y [38] |
| Statista | Y | n/f | n/f | n/f | n/f | n/f | n/f | n/f | n/f | Y + PNG/PDF/XLS [33] |
| Pew Research | n/f | n/f | Chart / table [34] | n/f | Y n on rollover; MOE shown [34] | MOE in graphics [34] | n/f | Y sample size [34] | n/f | n/f |
| Civiqs | n/f | n/f | Trend / Net toggle [35] | Net [35] | n/f | Uncertainty band [35] | Daily trend, date picker [35] | Y daily values [35] | n/f | n/f |
| Gallup Analytics | Y searchable trends [36] | n/f | n/f | n/f | MOE text [36] | n/f | Y trends [36] | n/f | n/f | Export [36] |
| Roper iPoll | Y question-level search across archive [39] | n/f | n/f | n/f | Sample description [39] | n/f | n/f | n/f | n/f | n/f |
| Numerator | n/f | "AI-Powered Insights" (G2) [37] | n/f | n/f | n/f | n/f | n/f | n/f | Y shared workspaces [37] | n/f |

---

## 2. Patterns by area

### 2.1 Home / survey library
- **Search at question level, not just survey level.** Roper splits iPOLL (question-level search) from RoperExpress (dataset-level search). Each iPOLL hit shows the full question wording and the share of respondents giving each answer, with filters for keyword, topic, organisation and date range [39]. Gallup's library tools retrieve similarly worded questions across years so users can build a trend [36]. *Why it matters:* with hundreds of waves × 60 questions, people look for a question ("tariff concern"), not for "Wave 2025-W31".
- **Typed search with date and scope filters.** Crunch lets users limit results to datasets, variables or categories, filter by dataset end date, and choose between the current project and a "Search all datasets" link. The panel always shows the current search scope [18]. Its newer search accepts natural language, and quoted text forces an exact match [19].
- **Folders plus sortable list or card views.** Crunch sorts by name, type, or created / modified / accessed date [24].
- **Topic hubs with related trackers.** YouGov groups trackers by topic and lists related trackers on each tracker page [25].

### 2.2 Overview / "what changed"
- **Rank questions by significance of change.** Q crosstabs every question by date in one action and orders the results by significance [11]. BrandIndex's "Biggest Movers" lists brands by how many of 13 metrics rose significantly month on month [27].
- **Auto-highlights that explain themselves.** Every SurveyMonkey Insight comes with a short note on how it was calculated. Insights only run with 30–10,000 responses and disappear once a filter is applied [38]. YouGov Profiles uses a Z score to flag the variables that most set a group apart [28].
- **LLM summaries on top of a stats engine.** Displayr Research Agent adds audit trails so each summary traces back to raw data [13]. ChatHarmoni drafts summaries of individual charts [30]. Morning Consult has AI news summaries and chat [29].
- **[inferred]** For CIP, the "what changed" page should be deterministic: it lists the tracker questions with a significant week-on-week change, ranked by effect size and labelled with base and p. Any LLM text should sit on top as an optional, cited layer.

### 2.3 Single-question view
- **Chart switching limited to valid types.** SurveyMonkey offers horizontal/vertical bar, stacked bar, pie, donut, line, area and gauge. It hides pie and donut for multi-answer questions and whenever a compare rule is on, and has an "Apply to all" option [38]. Pollfish offers table, column and pie [32]. Qualtrics builds a default chart for every question, with the compatible widgets set by question type [4].
- **Chart and table together.** SurveyMonkey has separate checkboxes for chart, data table and on-chart values, plus a toggle between percentages and counts [38]. Pew lets users switch between chart and table [34].
- **Nets / Top-2-box.** Q and Displayr offer "Create NET", which keeps the original categories and adds a combined one, alongside "Merge", which replaces them. Q warns that either change applies everywhere in the project [10]. Qualtrics dashboards support Top/Bottom box metrics, including significance tests on them [2].
- **Base and wording on every view.** YouGov tracker pages print the exact question wording, the population ("US Registered Voters"), the n per wave ("1061 - 1322 ... per wave") and a methodology link [25]. Pollfish puts the number of completes at the top of each results page [32].
- **Small-base handling.**
  - Crunch shows values from bases below a configurable threshold in light grey with a footer naming the threshold, or can suppress them [17].
  - SurveyMonkey shows "More responses needed" when a group has fewer than 30 [38].
  - Qualtrics hides answer choices below a response-count threshold. Users report that it works per widget, not per bar [3][7].
  - Alida sets a default minimum of 30 for significance testing [48].
  - One public dashboard flags n<50 in yellow and hides n<30 [47].
  - Q's default minimum for testing is only 2 [9].

### 2.4 Crosstabs
- **Banner layout.** Qualtrics puts drag-in Columns (Banner) against Rows (Stub). Columns can be nested; rows cannot [5].
- **Three sig-display conventions.** Pick one and explain it.
  1. **Letters.** Each column gets a letter, and a cell lists the letters of columns it is significantly higher than. Qualtrics uses uppercase for the primary confidence level and lowercase for an optional secondary one [1]. Q uses lowercase by default and uppercase at p ≤ 0.001 [9]. SurveyMonkey and Crunch exports also use letters [38][20].
  2. **Arrows + colour vs complement.** This is Q/Displayr's default: up or down arrows with blue for higher and red for lower. Arrow length scales with significance [8][9].
  3. **Shading.** Crunch shades cells from dark green to dark red using standardized residuals [15]. SurveyMonkey crosstabs highlight significant cells in blue [38].
- **Click-to-compare.** In Crunch, hovering a column shows "Set comparison". The reference column turns grey and the other columns are shaded by a two-tailed t-test against it [15]. *Why it matters:* "Gen Z vs Total" and "Gen Z vs Boomers" answer different questions, and this lets the user choose which one.
- **Weighting transparency.** Q handles effective sample size for weights through Kish or Taylor-series methods [9]. Crunch can show unweighted N, weighted N or both [22]. Pollfish lets users switch between "Actual results" and "Post stratified" [32].
- **Index vs Total.** YouGov Profiles uses an over-indexing Z score [28]. **[inferred]** An index (subgroup % ÷ Total % × 100) is a natural extra cell metric for CIP banners.
- **Export.** Qualtrics exports xlsx of the current table or all crosstabs [1]. Pollfish crosstab exports have count, overall %, row % and column % sheets [32].

### 2.5 Trends over time
- **Period comparison offsets.** Qualtrics tests each period against the previous one or against the same period a year earlier [2]. Q tests wave to wave and colours what changed since the last wave [11].
- **Smoothing.** Morning Consult uses 5-day moving averages [29], BrandIndex 4- and 12-week moving averages [27], and Q offers moving averages and splines [11].
- **Uncertainty band.** Civiqs has a toggle for the uncertainty range, labelled events, a Net view, and a date-range picker [35]. Pew has moved to showing margins of error in some graphics because subgroups of about 100 interviews can carry an MOE of 10 points or more [34].
- **Time-range presets.** YouGov offers 3m / 6m / 1yr / all [25].
- **Missing waves.** Datawrapper leaves gaps by default and asks before connecting points. It recommends point markers so readers can see which values were actually measured [40]. *Why it matters:* the 51 hibernated surveys mean CIP *will* have holes. Drawing a line across them invents data.

### 2.6 Micro-interactions
- **Hover on charts.** Crunch highlights the hovered bar, segment or line [22]. Civiqs shows each day's results on hover [35].
- **Cross-filter by clicking a group.** In Civiqs, picking a group in "Refine By" redraws the trendline. Groups can be combined (e.g. Independent women with a degree), and the tables update to match [35].
- **Save and present.** Each slide in a Crunch deck remembers the filter and weight that were active when it was saved. Dashboards are decks shown in presentation mode by default and shared by URL [21].
- **Export.** Qualtrics: PDF, JPG, PPTX (editable), DOCX, CSV/TSV/XLSX [4]. Statista: PNG, PDF, XLS (source and release details on sheet 2), and PPT with several visualisations [33]. Q links PowerPoint, Excel and dashboards so they refresh with each wave [11].

### 2.7 Questionnaire view
- Roper and YouGov treat exact question wording as primary content. Each result carries the full wording and sample description [39][25].
- Qualtrics lets users preview a single question as the respondent sees it (https://www.qualtrics.com/support/survey-platform/survey-module/editing-questions/formatting-questions/).
- **[inferred]** No product we found offers a public "questionnaire as navigation" view: a wave's question list, in order, with routing and bases, that you click into results. That is a gap CIP can fill cheaply from Forsta metadata.

### 2.8 Performance and accessibility
- **Response-time targets.** Under 0.1 s feels like direct manipulation. Up to 1 s keeps the user's train of thought. Past 10 s, show progress and offer cancel [42]. Google's INP threshold for "good" is 200 ms or less at p75 [43]. Crunch markets sub-second queries (vendor claim) [46].
- **Accessibility.** Datawrapper provides:
  - alt text
  - a "Get the data" CSV link
  - a colour-blind check
  - a keyboard "chart explorer" that exposes tooltip content through the arrow keys [40]

  Highcharts provides keyboard point navigation, ARIA regions per series, a data-table view and sonification [41]. **[inferred]** Q's default blue/red sig colours need a non-colour cue such as arrows or letters for colour-blind users. Q already pairs them with arrows [8].

### 2.9 What competitors do badly
- **Slow dashboards.** Some G2 reviewers say Qualtrics data panes and dashboards load slowly, and a QuestionPro critique calls branding customisation frustrating [44]. Displayr reviewers report slow processing on large datasets and a steep learning curve [14].
- **Sorting that contradicts its label.** A Qualtrics community user found Stats iQ Relate's "significance and effect size" sort was in fact ordered by effect size [45].
- **Thresholds that are too coarse.** Qualtrics thresholds work per widget rather than per bar [7], and custom metrics can still show when the threshold hides the underlying results [3].
- **Insights that vanish under filters.** SurveyMonkey drops Insights once a filter is applied and leaves them out of exports [38].
- **Hidden methodology.** Statista keeps full source and release details in the XLS second sheet [33]. **[inferred]** Users who only see the PNG lose that context.
- **Nets that change globally.** In Q, a NET changes the question everywhere in the project [10]. **[inferred]** CIP nets should be view-level.
- **Thresholds set too low.** Q's default minimum for testing is n=2 [9]. **[inferred]** That is far too permissive for weekly n≈400 subgroups.

---

## 3. Top 15 patterns to adopt (ranked by value for CIP)

1. **Base n and exact wording on every chart, table and export** [25][32]. This costs little and builds the most trust.
2. **Small-base rule: grey plus footnote below a warning threshold, suppress below a floor** [17][38][47]. **[inferred]** Defaults: warn when n<100, suppress when n<50. At n≈400, a gen/region cell is often 60–120.
3. **Tracker line with week-on-week and year-on-year significance markers** [2][11]. Hollow or filled point markers on significant waves.
4. **"What changed this week" page: tracker questions ranked by significant change** [11][27]. Deterministic, with p and base shown.
5. **Column-letter sig in crosstabs, plus an optional arrow-and-colour mode** [1][8][9]. Letters survive greyscale print and colour blindness.
6. **Click-to-compare reference column (default Total)** [15].
7. **Question-level search across all waves, with date-range and topic filters** [39][18][19].
8. **Gaps for missing waves, never interpolated, with markers on measured points** [40].
9. **Uncertainty band toggle on trend lines** [35][34]. MOE at n=400 is about ±4.9 pts. **[computed]** At n=100 it is about ±9.8 pts.
10. **Cell tooltip with MOE and unweighted base by default; weighted base and count optional** [16].
11. **Nets / Top-2-box as a view toggle that never alters the stored question** [10][2].
12. **Chart-type switch restricted to valid types for the question, with chart and table always available** [38][34].
13. **Time-range presets (3m / 6m / 1y / all) plus moving-average toggle (4-week)** [25][27].
14. **Saved views as shareable URLs that keep filters and banner, and slides that remember their filter** [21].
15. **Exports: PNG with wording, base and source baked in; CSV; editable PPTX; source and methodology carried in every format** [4][33].

---

## 4. Tooltip specs

Assembled from Qualtrics [2], Crunch [16], SurveyMonkey [38], Pew [34] and Civiqs [35]. Field order is our recommendation **[inferred]**.

**4.1 Bar / single-question chart (one answer, one group)**
```
Very concerned · Gen Z
42%  (±9.1 pts, 95%)
n = 112 unweighted · 118 weighted
Wave 2026-W41 · 6–12 Oct 2026
▲ Significantly higher than Total (31%), p < .05
```
Small base: replace the sig line with "Low base (n<100), interpret with caution". Below the floor, show "Not shown: n<50" and no value [17][38].

**4.2 Trend point (tracker line)**
```
Wave 2026-W41 · 6–12 Oct 2026
Very/somewhat concerned (Top-2): 58%  ±4.9
n = 402
vs prior wave (W40): +6 pts ▲ significant
vs same week last year (2025-W41): +3 pts, n.s.
```
Hovering a gap wave shows "No data: wave not fielded/loaded" [40]. With 4-week MA on, add "4-wk avg: 55%" [27].

**4.3 Crosstab cell**
```
Female × Very concerned
37% of column  (count 74)
Base: 201 unweighted / 206 weighted
MOE ±6.7 pts
Higher than: Male (B)    Index vs Total: 112
```
Default fields are MOE and unweighted base. The rest are user options, remembered per user [16].

**4.4 Significance marker (arrow / letter)**
"Higher than Total at 95% confidence (two-tailed z-test of proportions)". Qualtrics shows the reason and confidence level on hover [2]. SurveyMonkey shows "Significantly higher than / lower than / No significant difference" [38].

**4.5 Behaviour**
- Keyboard focus opens the same tooltip [40][41].
- Content is plain text, so a screen reader can read it.
- The tooltip never covers the hovered mark.
- Values in the tooltip match the export.

---

## 5. Sources

1. Qualtrics, Crosstabs Options. https://www.qualtrics.com/support/survey-platform/data-and-analysis-module/cross-tabulation/cross-tabulation-options/
2. Qualtrics, Significance Testing in Dashboard Widgets. https://www.qualtrics.com/support/vocalize/widgets/significance-testing-in-simple-charts-simple-tables-cx/
3. Qualtrics, Response Count Thresholds. https://www.qualtrics.com/support/vocalize/filtering-dashboards/response-count-thresholds/
4. Qualtrics, Results Dashboards Basic Overview. https://www.qualtrics.com/support/survey-platform/reports-module/results-dashboards/results-dashboard-overview/
5. Qualtrics, Cross Tabulation Overview. https://www.qualtrics.com/support/survey-platform/data-and-analysis-module/cross-tabulation/cross-tabulation-overview/
6. Qualtrics, Stats iQ. https://qualtrics.com/iq/stats-iq/
7. Qualtrics community, per-bar threshold thread. https://community.qualtrics.com/cx-dashboards-8/hide-bars-on-vertical-and-horizontal-widgets-for-below-a-certain-number-of-respondents-26224
8. Q wiki, Ways of Showing Statistical Significance. https://wiki2.q-researchsoftware.com/wiki/Arrows
9. Q wiki, Statistical Assumptions. https://wiki.q-researchsoftware.com/wiki/Statistical_Assumptions
10. Q wiki, How to Compute Top 2 Box Scores. https://wiki2.q-researchsoftware.com/wiki/Top_2_Box
11. Q, Tracking Analysis. https://www.qresearchsoftware.com/tracking-analysis
12. Displayr/Q help, custom significance colours. https://help.qresearchsoftware.com/hc/en-us/articles/4588401345807
13. Research Live, Displayr launches AI report tool. https://www.research-live.com/article/news/displayr-launches-ai-report-tool/id/5141403
14. Capterra, Displayr reviews. https://www.capterra.com/p/209889/Displayr/reviews/
15. Crunch, Click to set the comparison column. https://crunch.io/dev/features/click-to-compare/
16. Crunch, See the margin of error in tables. https://crunch.io/dev/features/margin-of-error/
17. Crunch help, low-base warnings/suppression. https://help.crunch.io/hc/en-us/articles/4665402502029
18. Crunch, Refine your searches. https://crunch.io/dev/features/search-filters/
19. Crunch help, Search in Crunch. https://help.crunch.io/hc/en-us/articles/40867072211469-Search-in-Crunch
20. Crunch help, tab book export. https://help.crunch.io/hc/en-us/articles/360039306952
21. Crunch help, tray/decks and Viewing a dashboard. https://help.crunch.io/hc/en-us/articles/10238198311437-Using-the-tray-to-save-analyses ; https://help.crunch.io/hc/en-us/articles/34267419053197-Viewing-a-dashboard
22. Crunch release notes (hover highlight; weighted/unweighted N). https://crunch.io/release-notes/2024-05-20/ ; https://crunch.io/release-notes/2023-04-03
23. Crunch help, tracking studies. https://help.crunch.io/hc/en-us/articles/360052195131
24. Crunch help, Navigating datasets / folders. https://help.crunch.io/hc/en-us/articles/360039980712 ; https://help.crunch.io/hc/en-us/articles/36874774287885-Folders-in-Crunch
25. YouGov tracker page example. https://yougov.com/en-us/trackers/amy-klobuchar-favorability
26. YouGov Self-serve Surveys (results in YouGov Crunch). https://yougov.com/en-us/business/products/self-serve-surveys
27. YouGov BrandIndex movers + sig arrows + moving averages. https://business.yougov.com/content/51722-us-biggest-brand-movers-march-2025 ; https://yougov.com/fr-fr/articles/21404-les-marques-qui-progressent-le-plus-en-juillet-201-1 ; https://datawrapper.dwcdn.net/W3Lmi/1 ; https://datawrapper.dwcdn.net/d4TNJ/1
28. YouGov Profiles / Profiler FAQ (Z score). https://yougov.com/business/products/global-profiles ; https://yougov.com/en-gb/articles/10980-yougov-profiler-faqs
29. Morning Consult: Consumer Confidence Dashboard, MCI, AI news summaries. https://pro.morningconsult.com/trackers/consumer-confidence-dashboard ; https://pro.morningconsult.com/morning-consult-intelligence ; https://pro.morningconsult.com/articles/ai-news-summaries
30. Infotools Harmoni. https://www.infotools.com/discover-harmoni ; https://infotools.com/harmoni
31. Toluna Start Analytics & Insights. https://tolunacorporate.com/toluna-start-platform/analytics-and-insights/
32. Pollfish results dashboard and crosstabs guide. https://www.pollfish.com/resources/blog/pollfish-school/the-pollfish-survey-results-dashboard-understanding-its-functionality-and-how-to-use-it/ ; https://resources.pollfish.com/?p=83773
33. Statista download formats; library guide. https://www.statista.com/getting-started/working-with-statista-statistic-download-formats ; https://library.purdueglobal.edu/statistaguide/downloading
34. Pew: displaying margins of error; RLS rollover sample sizes. https://www.pewresearch.org/decoded/2021/10/25/why-pew-research-center-will-display-margins-of-error-in-some-graphics/ ; https://www.pewforum.org/religious-landscape-study/belief-in-absolute-standards-for-right-and-wrong/right-or-wrong-depends-on-the-situation/party-affiliation/
35. Civiqs FAQ. https://civiqs.com/faq
36. Gallup Analytics (library descriptions). https://edesiderata.crl.edu/resources/gallup-analytics ; https://blog.lib.uiowa.edu/trials/?p=1510 ; https://guides.lib.virginia.edu/gallup ; https://www.gallup.com/analytics/390536/sleep-in-america-2022.aspx
37. Numerator. https://help.insights.numerator.com/en/articles/11878350-all-about-insights ; https://www.g2.com/products/numerator-verified-voices/features
38. SurveyMonkey help: compare rules, significant differences, chart types, custom charts, Insights; crosstab explainer. https://help.surveymonkey.com/en/analyze/compare-rules ; https://help.surveymonkey.com/surveymonkey/analyze/significant-differences/ ; https://help.surveymonkey.com/en/surveymonkey/analyze/chart-types/ ; https://help.surveymonkey.com/en/analyze/custom-charts ; https://help.surveymonkey.com/en/surveymonkey/analyze/analyze-with-ai/ ; https://help.surveymonkey.com/ko/surveymonkey/analyze/insights ; https://www.surveymonkey.com/learn/research-and-analysis/what-is-a-crosstab-and-when-to-use/
39. Roper iPOLL. https://ssric.calstate.edu/node/240 ; https://ropercenter.cornell.edu/sites/default/files/pdf/Roper%20iPoll%20and%20Health%20Poll%20Database%20Library%20Guide.pdf
40. Datawrapper: accessibility, keyboard navigation, patchy data. https://www.datawrapper.de/blog/better-accessibility-for-datawrapper-visualizations ; https://www.datawrapper.de/blog/keyboard-navigation-dynamic-font-scaling ; https://www.datawrapper.de/academy/patchy-data
41. Highcharts accessibility module. https://highcharts.com/docs/accessibility/accessibility-module-feature-overview
42. NN/g, 3 response-time limits. https://www.nngroup.com/videos/3-response-time-limits-interaction-design/
43. web.dev, INP. https://web.dev/articles/inp
44. Qualtrics reviews / critique. https://www.g2.com/products/qualtrics-corexm/reviews ; https://www.questionpro.com/blog/cons-and-disadvantages-of-using-qualtrics/
45. Qualtrics community, Relate sort order. https://community.qualtrics.com/questions/14894
46. Crunch marketing (sub-second claim, vendor). https://info.crunch.io/displayr ; https://greenbook.org/tech-showcase/on-demand/crunchio-online-survey-data-analysis-platform-for-tracking-studies
47. Australian Digital Inclusion Index dashboard guide (n<50 flag, n<30 hidden). https://digitalinclusionindex.org.au/?p=192
48. Alida, apply significance tests (default min 30). https://insightcommunity.help.alida.com/enus/adhoc/reports_modern/significance_testing/significance_testing_apply_modern.html

Not directly verified: several Crunch, Pew and Q help pages returned HTTP 403 to the fetcher. Claims citing [12], [17], [21], [24] and [34] rest on search-engine extracts of those pages, not on a full read.
