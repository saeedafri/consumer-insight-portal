# CIP Feature Roadmap (27 Nov 2026) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close every gap between the manager's "CIP Feature Roadmap.xlsx" (sheets Plan and Resource, 27 Nov 2026) and the
portal, and make In store vs online show a kind's groups side by side, each item tested and copied to cip-stg.

**Architecture:** New weekly screens follow In store vs online: the published question files (every group, exact counts)
are fetched once and every pick is computed in the browser, so nothing new runs on the server. One screen file
(`frontend/src/screens/Weekly.tsx`) serves the three new menus from a topic table; the question-file lookup moves out of
Channels.tsx into `frontend/src/weekly.ts` so both use one copy. Sector spend adds one figure per survey in the ETL.

**Tech Stack:** React 19 + react-router, ECharts, TanStack Query; FastAPI; Python ETL; pytest; Playwright for the screens.

**Spec:** the manager's workbook (copy: scratchpad roadmap.xlsx) and the user's message of 27 Nov 2026 (item 1 below).

## Global Constraints

- Never `git commit`, `git push` or any history write, in cip-test or cip-stg: the user commits (CLAUDE.md).
- Never stop or restart the live API on :8000; test on the :8002 preview.
- Change only what an item asks; keep existing controls, wording and look (memory: change-only-what-was-asked).
- Every feature goes in the same words to What's new (WhatsNew.tsx) and docs/CHANGELOG.md, and a status/README.md row.
- After each item: full pytest, `npx tsc --noEmit`, a browser check on :8002, then copy only this item's hunks to cip-stg.
- Files other sessions changed (api/main.py, api.ts, WhatsNew.tsx, CHANGELOG.md, status/README.md): edit by hunk, never overwrite.

## Roadmap audit (what exists, what is left)

| Roadmap item (Excel status) | In CIP today | Task |
|---|---|---|
| In-store vs Online (Done) | /channels | T1: a kind's groups side by side |
| Retailer Databank; Retailer Shopper Scorecard (Done) | /retailers | T6 verify |
| Activities & Retailer Shopping, Food / Non-food (Next) | only per wave, in the Weekly report's tables | T2 new screen |
| Spending Pressure; Consumer Spending Cutback Monitor (To do) | Q6 only in the Question explorer; D15 inside the Gas tracker | T3 new screen |
| Consumer Sentiment Outlook; Confidence by Demographic (To do) | Weekly report's net better; Home's outlook card | T4 new screen |
| Sector Spend Insights (To do) | each sector's median spend band (card, Excel tab) | T5 average spend, every sector together |
| GenAI & AI Shopping Adoption; GenAI Survey; AI Shopping Adoption Tracker (To do) | GenAI tracker: heard of AI, shopped with GenAI, plan to, tools, worries | T6 verify |
| Retail Sector Databank; Retail Sector Surveys (To do) | /sectors, 13 sectors | T6 verify |
| Inflation, Tariffs, Financial Health, GLP-1, Gas, Social Commerce, Holiday trackers (To do) | /trackers/* (8 trackers) | T6 verify |
| Events, seasonal (To do) | Holiday shopping and Holiday outlook trackers, Expected vs actual | T6 verify |
| Annual Survey (To do) | Survey library: 24 annual studies | T6 verify |
| Shopping & Spending Survey (To do) | US weekly tracker | T6 verify |
| Smart Search by topic, survey or question (In progress) | /search: words, code, answer, survey title, topic chips, by measure | T6 verify |
| Key Highlights at a Glance (In progress) | Home's This week at a glance; Weekly report's three data points | T6 verify |
| Year-over-Year Change Tracker (In progress) | What changed (vs the same week last year), Trends | T6 verify |
| Cross-Tab Explorer (In progress) | Cross-tab matrix | T6 verify |
| Consumer Profile Snapshot (to add to Retailer Databank) | Retailer databank's Shopper profile | T6 verify |
| Five-Year Trend Archive (Done) | Trends, weekly tracker since Dec 2020 | T6 verify |
| Consumer Health Score (TBD) | not defined | Stuck: needs the manager's definition |

## Review Focus

- A group with no answers in the chosen week (Non-binary, old income bands): left out of the side-by-side bars, never a 0 bar.
- A code reused for another question (Q6 was food retailers until Jun 2026, expenses from Jul 2026): only weeks whose wording matches count.
- A net figure below zero (sentiment's net better): the bar runs left of zero and reads "−5.2", never "-5.2%".
- A week the question was not asked (expenses before 13 Jul 2026): the Week list offers only asked weeks.
- A sector whose spend bands are open at the top ("More than $200"): the average counts it at its floor, as Ask does.

---

### Task 1: In store vs online, a kind's groups side by side

**Files:** Modify `frontend/src/screens/Channels.tsx`

- [ ] When the Respondent group is a kind (not Everyone), the bar chart shows the chosen category for every group of that
  kind this week has answers from (Male, Female, Non-binary; Gen Z … Boomer), the chosen group highlighted with its % and
  Everyone's grey tick; a click on a group picks it (top filter, line chart buttons follow). Everyone: every category, as now.
- [ ] Title `${category} by ${kind name}`; export rows per group with Everyone's figures and bases.
- [ ] Verify on :8002: Gender → Male chosen, bars Male/Female/Non-binary for Food or beverages match `question_results` (725, q2).
- [ ] Docs, status row; copy to cip-stg.

### Task 2: Activities & retailers screen (/activities)

**Files:** Create `frontend/src/weekly.ts`, `frontend/src/screens/Weekly.tsx`; modify `Channels.tsx` (import `shares`),
`main.tsx`, `components/Shell.tsx`, `config/access.yml`, `api/main.py` (question route features), `tests/test_access.py`.

**Interfaces:** Produces `shares(files: QuestionFile[], wording: RegExp)` → `{ share(survey, cut, key), base(survey, cut), weeks: Map<number,string>, labels: Set<string> }`,
key = item label, or `item: label` for a grid row's scale point (as api/ask_figures.py names them).
`Weekly.tsx` default export reads its topic from the path: `TOPICS[path]` = `{ title, lede, feature, tabs: Tab[] }`,
`Tab = { name, codes: string[], wording: RegExp, items?: [name, plus: RegExp, minus?: RegExp][], rows?: true, source }`.

- [ ] Tabs: Activities (Q1, Q3; "have you done in the past two weeks"), Food retailers (Q4, Q6; "FOOD products from"),
  Nonfood retailers (Q5, Q7; "NONFOOD products from"). Layout as In store vs online: Week, Respondent group, answer;
  cards (this week with change, a year earlier); bars (all answers, or the answer by group); line over the year.
- [ ] Feature `activities` (menu Core research, grown from `channels`); test_access lists it.
- [ ] Verify: Walmart food, Total, 23 Nov 2026 equals `question_results(725, Q4)`; Gender split equals it too.

### Task 3: Spending pressure screen (/spending)

- [ ] Tabs from Q6 grid rows (Utilities, Insurance, Rent / mortgage): Expenses up (notable + significant increase),
  Expenses down (the cutback side), Net change (up − down); Where people cut back (D15, gas prices). Feature `spending`.
- [ ] Verify: Utilities up, Total, 23 Nov 2026 = 36.9 + 19.6 = 56.5%.

### Task 4: Consumer sentiment & outlook screen (/sentiment)

- [ ] Tabs Personal finances (CS1, q009) and Economy (CS2); answers Net better (better − worse), Better, About the same,
  Worse, Don't know; the kind's groups side by side is the demographic breakdown. Feature `sentiment`.
- [ ] Verify: net better, Total, 23 Nov 2026 equals the Weekly report's sentiment for wave 725.

### Task 5: Sector spend insights

**Files:** `etl/sectors.py` (`average_spend(rows) -> int | None`, whole dollars, None under three bands as `median_band`),
`tests/test_sectors.py`, `frontend/src/api.ts` (`Sector.spend.average`, `Sector.spend.changes`), `frontend/src/screens/Sectors.tsx`.

- [ ] Test: `average_spend` of M4 on 9 Nov 2026 (the median test's rows) is $291; "More than $500" counts at $500,
  "Cannot remember" nowhere; hidden figures or a non-spend question give None.
- [ ] A card "Spend across sectors": each sector's newest median band, average estimate and change vs its survey before
  and a year earlier; a click opens the sector. The chosen sector's average spend over its surveys as a line.

### Task 6: Verify every existing roadmap item and report

- [ ] Open each screen of the audit table on :8002 as the super admin, check data loads and Export works; note gaps.
- [ ] status/README.md: one row for the roadmap with each item's status; a copy of the workbook with a "CIP status" column.
