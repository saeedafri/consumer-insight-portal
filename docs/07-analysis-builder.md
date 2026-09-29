# The Analysis Builder

The cross-tab answers the questions Forsta was asked to tabulate. This page
answers the rest.

*"Among GenZ and Millennial BNPL users in the Midwest or South, which
department stores did they buy from?"* is three criteria and a question. It
appears nowhere in the 78 published tables, and it is four clicks here.

---

## How it works

A **cohort** is an intersection of criteria over the long fact table:

| Criterion | Built from | SQL |
|---|---|---|
| a demographic | `csi_profile` | `p.generation IN (…)` |
| an answer to a multi-punch | `csi_answer` + `csi_item` | `EXISTS (… item_id IN (…) AND value_code = 1)` |
| an answer to a single-punch | `csi_answer` + `csi_option` | `EXISTS (… question_id = ? AND value_code IN (…))` |

Criteria are ANDed; values inside one criterion are ORed — which is what an
analyst means by "GenZ or Millennial". The target question is then aggregated
over whoever survives, optionally broken by any demographic.

## The base still travels

The cohort is not the base. `DP2` is asked only of department-store buyers, so
filtering to Millennials gives a cohort of 159 but a DP2 base of 88. The page
says so above the chart, the table carries both numbers, and the Excel export
records them on its provenance sheet.

Below n=30 the page refuses to be quiet about it: Coresight's own cross-tabs
flag anything under ~50 and suppress under ~30, so a warning appears and says
to read the result as directional.

## Verified against the published tables

The engine is checked against numbers Forsta computed independently
(`tests/test_analysis.py`):

| Cohort | Engine | Published base |
|---|---|---|
| `BN1 = Yes` (BNPL users) | 133 | BN2 base = 133 |
| `DP1 = Yes` (department-store buyers) | 222 | DP2 base = 222 |
| `GP1` (GLP-1 users) | 71 | GP8 base = 71 |
| Generation = GenZ | 54 | Summary sheet = 54 |

and an unfiltered run reproduces the cross-tab exactly — q4 Walmart
`0.59653465`, n=241, base 404.

## One bug worth knowing about

The Forsta export is in **label** format: a single-punch cell holds `"Yes"`,
not `1`. Run through the multi-punch rule, every answered cell becomes code 1
— and "BNPL users" silently becomes all 404 respondents instead of 133. Every
filter built on a single-punch question would have been wrong, and wrong in
the direction that makes findings look stronger.

The loader now resolves the label back through the datamap dictionary
(`_code_lookup` in `etl/run_pipeline.py`). `test_single_punch_answers_keep_distinct_codes`
guards it.

## Excel

Every table on every page has a **Download to Excel** button. The workbook is
branded (Coresight red header, Inter, banded rows, percentages formatted as
percentages) and carries an **About this export** sheet with the wave, the
question, the cohort, the base, each filter applied, and a note on how to read
the percentages. A spreadsheet of bare percentages with no base attached is
how the wrong number ends up in a client deck.

The workbook is built only when someone clicks — `st.download_button` takes
the builder as a callable — so it costs nothing on pages where nobody exports.
