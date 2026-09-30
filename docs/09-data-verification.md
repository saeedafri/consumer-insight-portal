# Data Verification — Is What the Portal Shows What Forsta Published?

Run on 29 September 2026 against both loaded waves (09/21/26 and 09/28/26),
first on the local SQLite copy, then on `dwh_stg`.

```bash
python scripts/reconcile.py              # every wave in the database
python scripts/reconcile.py --wave 2026-09-28
```

Exit code 1 on any unexplained mismatch, so it can gate a scheduled load.

---

## What it checks

1. **Every published Total cell.** For each question Forsta tabulated, the
   portal's own engine (`repository.analyse`, no filters) recomputes the
   percentage from the raw answers in `csi_answer` and compares it with the
   cell in `csi_crosstab`. Paradata tables (`qtime`, device, browser) are
   skipped — they are field statistics, not answers.
2. **Every banner column size.** Each demographic column (Male, GenZ,
   $50,000–$99,999, Northeast, "Much worse"…) must equal the cohort the
   portal's filters build. A column is matched through the question its Forsta
   definition names (`(CS1.r1)` → CS1), because CS1 and CS2 share labels.

## Result

| Wave | Published cells reproduced | Banner columns matching |
|---|---|---|
| 2026-09-21 — Dept Stores, BNPL, Diamonds, GLP-1 | **667 / 667** | 36 / 38, 2 known Forsta differences |
| 2026-09-28 — Beauty, Holiday, Inflation, Tariffs | **788 / 788** | 36 / 38, 2 known Forsta differences |

---

## Defects found and fixed on the way

The first run reproduced 767/771 and 858/894 cells. Each gap had one root cause:

| # | Symptom | Root cause | Fix |
|---|---|---|---|
| 1 | Loading 09/28 would merge into 09/21 | `csi_survey` unique on host + path; both weeks are the same Forsta project | key includes `wave_label`; `--wave` required |
| 2 | HX1: 333 of 403 answers (and most of HX2) had no code | datamap labels use non-breaking spaces (`Spent\xa0a lot…`), raw export uses normal ones | `excel_parsers.clean_text` folds whitespace on every sheet |
| 3 | BT8, GP4, GP10 percentages too high, by up to 3× | multi-select items divided by those *shown* the item, not everyone answering the question | base = distinct respondents answering the question (Forsta's "Total Answering") |
| 4 | Grids (BT14, DP7, GP6) pooled into one distribution | `analyse()` had no grid branch | each grid row is its own distribution, labelled "row — rating", drawn as 100% stacked bars |
| 5 | GenZ = 62, published 61 | one Qualified respondent answered "Under 18"; the parser read it as 18 | "Under N" parses as N−1, outside every age band |
| 6 | Grid filters silently wrong | a grid filter matched `value_code = 1` (the multi-select rule) — on BT14 that is "Very positive", not "rated it" | grid filters offer "row — rating" pairs and match both |

Also fixed: `D28r8oe` / `D32r15oe` fell outside the AI topic (`\b` does not
match between `28` and `r`), and with a break active the page compared the
largest segment's base against the whole cohort, so every question looked
routed.

## Known Forsta difference — the region banner

Forsta's region columns leave out two states:

| Column | Forsta | Portal (US Census) | Difference |
|---|---|---|---|
| South | 148 | 155 | + 7 Maryland respondents |
| Midwest | 70 (09/28), 73 (09/21) | 85 | + 15 / + 12 Missouri respondents |

The four region columns sum to 381 of 403 (09/28) and 385 of 404 (09/21), so
19–22 respondents per wave sit in no region in the published cross-tab. The
portal keeps the Census definition. **Ask the research team to add Maryland to
South and Missouri to Midwest in the Forsta banner**; once they do, this check
starts passing without a code change.

`D2 = Under 18` appearing among Qualified completes also suggests the age
screener is not terminating under-18s. Worth raising with whoever programs
the survey.
