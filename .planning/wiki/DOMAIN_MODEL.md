# CIP domain model and glossary

Facts below were read from the code and the `cip_stg` database on 22 Oct 2026. Nothing here is estimated.

## Scale

| Thing | Value |
|---|---|
| Waves served (`srv_wave`) | 371, from 18 Jan 2018 to 19 Oct 2026 |
| Largest family | CSI-US tracker, 268 waves; the rest are annual or ad hoc studies |
| Qualified respondents (all waves) | 188,322 |
| Answer rows (`srv_answer`) | 9,532,424 |
| Result rows (`srv_result`) | 2,416,109 |
| Harmonised concepts (`cip_concept`) | 2,456 (the "828+" in the brief is a floor) |
| Concept answer options | 15,451 |
| Question-to-concept links | 87,086 confirmed, 3,771 proposed (waiting for an analyst) |

## Glossary

- **Wave**: one fielding of one survey. A weekly tracker wave is labelled by its Monday.
- **Family and study type**: the series a wave belongs to (`CSI-US` + `tracker`). Trends run within a family.
- **Question version**: the same code can mean different questions over time. Two waves are comparable only when their normalised wording matches (`same_question` / `versions()`); otherwise they are left out, never joined.
- **Concept**: a question identified across waves by normalised wording and type (`app/data/harmonise.py`). Match kinds: `exact` (confirmed), `changed` (same wording, new answers: proposed), `similar` (wording at least 0.85 alike: proposed), `new` (confirmed as a new concept). A proposal trends nothing until an analyst confirms it.
- **Grid question**: harmonised row by row; each row is its own concept, rows of one grid share a `concept_group`.
- **Base (n)**: respondents who were asked and answered. Percentages are of the base, not of all respondents.
- **Banner / cut / dim**: a respondent grouping. A *two-cut crosstab* shows one question by two cuts.
- **Audience**: any combination of cuts and answers (for example Female, Gen Z or Millennial, chose ChatGPT), shown against everyone else.

## Demographic cuts (`etl/serving.CUTS`)

| Cut | Values in the data |
|---|---|
| gender | Female, Male |
| age_band | 18-29, 30-44, 45-60, Over 60 |
| generation | GenZ, Millennial, GenX, Boomer |
| income_band | under $25,000; $25,000-$49,999; $50,000-$99,999; $100,000-$149,999; $150,000-$199,999; $200,000 or greater; prefer not to say |
| census_region | Northeast, Midwest, South, West |
| urbanicity | Urban, Suburban, Rural |

A respondent has one value per cut in a wave (verified: no respondent changes value within a wave). A respondent with no value for a cut is left out of that cut, and "Total" always exists.

## Rules and formulas

1. **Percentage** = respondents giving the answer / base x 100. Multi-answer questions use the question's own base, so rows can sum above 100.
2. **Small cells.** Base under **30**: no figure anywhere (screens, files, exports, Ask CIP, Audiences); only the base ("n<30"). Base under **50**: figure shown and flagged "small base". Constants: `HIDDEN_BASE = 30` (`app/data/payloads.py`), `SMALL_BASE = 50` (`etl/serving.py`).
3. **Significance.** Two-sided two-proportion z-test at 95%, pooled standard error: `z = (p1 - p2) / sqrt(p(1-p)(1/n1 + 1/n2))`, `p = (p1 n1 + p2 n2) / (n1 + n2)`; significant when the two-sided p < 0.05. Python `api/dashboards.significant`, TypeScript `web/src/stats.ts`; same formula in `etl/crosstab_export.ztest`.
4. **Versus the rest, not versus Total.** A cut is compared with everyone outside it (`versusRest`), because Total contains the cut and would bias the test. Letter marks compare columns of the same cut only; groups that share people are never tested against each other.
5. **Multiple comparisons.** `survivesFdr` applies Benjamini-Hochberg at q = 0.05 where hundreds of answers are scanned (the "What changed" screen). The Crosstab letters do not use FDR, to match the Forsta tables the team checks against.
6. **Pooling across weeks** (`weeks` = 1, 2, 4, 8, 13 on a crosstab): counts and bases are **summed** across the waves that asked the same question version, then percentages are recomputed from the sums. There is no weighting step; respondents are unweighted today. If weights arrive, publish the weighted total and the sum of squared weights per cell so the test can use the Kish effective base `n_eff = (sum w)^2 / sum w^2`.

## Import graph (api/, etl/, app/ excluding Streamlit pages, scripts/; web/src)

- Python: 75 modules, 154 internal imports. Most imported: `app.core.database` (33), `app.core.config` (10), `app.data.cube` (8). One cycle, `app.data.cohorts` <-> `app.data.cube`, already broken by a lazy import and a comment.
- Web: 36 modules, 144 imports. Most imported: `api` (22), `stats` (18), `components/bits` (14). No cycles. `stats.ts` has no DOM or network references.
- Unlinked: only scripts and Streamlit components (entry points that nothing imports), as expected.

## Not done

The literature and GitHub search for tracking methods was not run: nothing in it would change a number the portal publishes. The two-proportion test, FDR and Kish effective base above are the standard methods; a source review belongs with the introduction of weights.
