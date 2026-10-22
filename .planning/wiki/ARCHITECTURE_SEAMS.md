# Architecture seams

How the pieces connect, where the boundaries are, and the three architecture decisions with the evidence behind each.

## The seams

```
Forsta (read-only GET)
   |  etl/forsta_etl.py          load a wave into cip_* tables      (writes cip_stg only)
   v
cip_* source tables
   |  etl/serving.py             build the serving cube: srv_wave, srv_result, srv_answer
   v
srv_* serving tables (MySQL)
   |  etl/publish.py             write gzip JSON + respondent bitsets per wave   (atomic swap, last 3 kept)
   v
data/published/current/api/v1/...
   |  nginx (static, auth_request)  or  api/main.py (same bytes, parsed once per version)
   v
React app (web/src)   -- pure maths in web/src/stats.ts
```

| Seam | Owner | Contract |
|---|---|---|
| Source to cube | `etl/serving.py` | `srv_*` tables; cuts are `CUTS`; small-cell constants `SMALL_BASE`, `HIDDEN_BASE` |
| Cube to files | `etl/publish.py` | one file per wave book, per wave and question cut counts, per family question, per wave `people` bitsets; gates run before the swap |
| Files to HTTP | nginx and `api/main.py` | the API's URLs are the files' paths; the API answers anything not yet published from the database |
| Live database reads | `api/team.py`, `app/data/payloads.py` | team views, alerts, saved audiences, `/results`; the only paths that pay the 270 ms Azure round trip |
| Statistics | `web/src/stats.ts`, `api/dashboards.significant`, `etl/crosstab_export.ztest` | the same two-proportion z-test written three times (TypeScript, API, export); no DOM or network in `stats.ts` |
| Respondent-level data | `payloads.people` to `api/team.audience` | bitsets stay on the server; no route returns the file |

Import health: no cycles in `web/src`; one in Python (`app.data.cohorts` and `cube`), already broken by a lazy import. No tool was added to enforce import boundaries: with 36 web modules and zero cycles, a linter is a dependency guarding nothing yet. Revisit if a cycle appears.

## Changes not made, and why

- **`query_cube(survey_id, qcode, cuts, pool_weeks)` wrapper.** `payloads.crosstab` and `payloads.question_cuts` already are that narrow interface (survey, question, two cuts, weeks) and hide the storage from the screens. A wrapper above them adds a layer with one caller. CIP runs MySQL; SQLite exists only for tests (`sqlite_compat`), and PostgreSQL and Parquet are not in the plan.
- **Moving `stats.ts` to a separate library.** It is already pure and has no DOM or network references. Publishing a package would add release work for one consumer.
- **Tailwind v4 and shadcn.** A Tailwind restyle was tried and reverted; the portal's own CSS and four small shims (`components/ui/`) render its markup. Tailwind would add a build step and a second styling system.
- **Request-level LRU on `/api/v1/search`.** Search takes about 1 ms (index in memory); a cache would save nothing.

## Dilemma 1: serving engine. Verdict: keep the precomputed published files on the relational cube (Option A)

Evidence measured on CIP's own 9.5 M answer rows:

| | Published files (today) | DuckDB in-process |
|---|---|---|
| Standard cross-tab | about 1 ms | 0.4 to 5 ms |
| Audience (arbitrary filters) | 0.008 ms (bitsets, 6.9 MB for all waves) | 0.8 ms (67 MB file, 115 MB RAM per process) |
| Storage for all waves | 6.9 MB bitsets + about 40 MB payloads | 67 MB (22 MB as Parquet) |
| New dependency | none | DuckDB (2.0.0 was one day old) |

A faster engine would not help the places that are slow: the ETL is dominated by the 270 ms round trip to Azure. Revisit only for ad hoc queries that pool many waves with arbitrary filters.

## Dilemma 2: where cross-tabs are computed. Verdict: server side over published rows (Option A)

- The largest wave has 2,336 respondents and the server answers in about 1 ms, so there is nothing for the browser to speed up.
- Computing in the browser requires sending respondent-level rows to every visitor. That lets anyone rebuild cells under 30 respondents, breaking the small-cell rule, and it would be a data-exposure change the business has not approved.
- Web Workers plus WebAssembly would add cross-origin isolation headers that can break the sign-in on the shared link.

## Dilemma 3: bundle delivery. Verdict: one bundle with lazy routes and a shared ECharts core (Option A)

- Page screens are separate lazy chunks of 1 to 18 KB each; the shell is 363 KB (116 KB gzipped); ECharts loads once, after the first screen, and is cached long term (555 KB, 188 KB gzipped).
- ECharts is already tree-shaken to Bar, Line and Pie plus Grid, Legend, Tooltip, Aria and the Canvas renderer. Removing Pie and Aria saves only tens of KB, so the 450 KB target for the charts chunk is not reachable without dropping a chart type or the library.
- Micro-bundles per route would duplicate the shared chart core or lose its caching, for no gain in first paint (52 to 88 ms measured).

The five-advisor council was not convened: each dilemma above has measured numbers and a rule behind it, and a council would restate them at the cost of about a dozen model calls.
