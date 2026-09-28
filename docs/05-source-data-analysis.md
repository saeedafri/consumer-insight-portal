# Source Data Analysis — Forsta Exports, 09/21/26

What the two files actually contain, measured rather than assumed. Every figure
below was produced by parsing the files; nothing here is estimated.

Survey: **"Shopping and Spending — inc Dept Stores + BNPL + Diamonds + GLP1s"**
Forsta project: `selfserve/58f/260908` on `se1.decipherinc.com`.

---

## 1. Raw Data 09_21_26.xlsx

Two sheets.

### Sheet `A1` — respondent-level data

| Property | Value |
|---|---|
| Rows | 405 (1 header + **404 respondents**) |
| Columns | **375** |
| Cell content | **Labels, not codes** |
| Unselected multi-punch | prefixed `NO TO: ` |

The label format matters. `q1r1` does not hold `0`/`1`; it holds
`NO TO: Met up with friends or family locally` or
`Met up with friends or family locally`. Any loader has to strip that prefix to
recover the code — `excel_parsers.normalise_label_cell()` does it in one place.

This is a **data-layout setting in Forsta**, not a fact of nature. A layout that
exports codes would be cleaner, and the API can request one (`?layout=<id>`).
Worth asking the Forsta admin for a codes layout; the loader handles both.

### Sheet `Datamap` — the survey definition

Three columns, blank-line-separated blocks:

```
q1: Which, if any, of these have you done in the past two weeks?
Values: 0-1
            0        Unchecked
            1        Checked
            [q1r1]   Met up with friends or family locally
            [q1r2]   Gone to a shopping mall (enclosed shopping center)
```

Parsed result: **93 question blocks**, expanding to exactly **375 variables** —
a perfect 1:1 match with the `A1` column headers, zero unmatched. That match is
the strongest evidence the model below is right.

Question types found:

| Type | Count | Example |
|---|---|---|
| Multi-punch list (`Values: 0-1` + rows) | 30 | `q1`, `q4`, `BN7`, `GP8` |
| Grid, ordered scale (`Values: 1-5` + rows) | 4 | `DP7` (9 retailers × 5-point), `GP6` (21 categories × 4-point) |
| Single-punch | 38 | `CS1`, `D5`, `BN3` |
| Open text (`…oe` verbatims) | 11 | `DP2r10oe`, `BN7r8oe` |
| Open numeric / paradata | 10 | `record`, `qtime` |

Content modules, which become `csi_topic`:

Shopping and Spending (`q1`–`q6`) · Department Stores (`DP1`–`DP8`) ·
Diamonds (`DJ1`–`DJ5`) · BNPL (`BN1`–`BN8`) · AI and GenAI (`D28`–`D35`) ·
GLP-1 (`GP1`–`GP10`) · Consumer Sentiment (`CS1`–`CS3`) ·
Macro and Gas Prices (`D12`–`D15`) · Demographics (`D1`–`D8`) ·
Paradata and quotas (`vos`, `vqtable*`, `qtime`, …)

Two structural details the schema has to respect:

- **`D2` is age in single years**, coded 1–54 (`1 = Under 18`, `2 = 18` … `54 = 70+`).
  The banner buckets it into generations. Storing the raw code and deriving the
  band at load time keeps both available.
- **`D8` is state, coded 1–51.** Census region is derived, not asked, so the
  derivation belongs in the load step (and is auditable there).

---

## 2. Cross Tabs 09_21_26.xlsx

Three sheets. `Percentages` and `Counts` have **identical geometry** — same
1,541 rows, same 81 columns — so they are read in lock-step and merged into one
row per cell.

### Sheet `Summary` — run settings

```
Respondents:       Qualified Only
Additional Filter: None
Table Set:         All
Percentage Base:   Total Answering
Stat Test Levels:  None / None (z-test)
Date Range:        09/21/26 – 09/21/26
```

These are not decoration. A percentage without its base definition is not a
number an analyst can defend, so they are stored on `csi_crosstab_run` and
surfaced with every figure in the portal.

Below them, **40 segment definitions** with their Forsta expressions and bases:

| Segment | Definition | Base |
|---|---|---|
| Total | `(ALL)` | 404 |
| Male | `(D1.r1)` | 200 |
| GenZ | `(D2.ch12 or D2.ch10 or …)` | 54 |
| Caucasian | `(D4.r2)` | 258 |
| $200,000 or greater | `(D5.r6)` | 18 |

Keeping `seg_definition` verbatim is what lets an analyst audit how "GenZ" was
defined in a given wave rather than trusting that it never changed.

### Sheets `Percentages` / `Counts` — 78 stacked tables

Each table repeats a three-row header: banner group name, segment label with
its stat-test letter, and `N=`. Data sits in every second column; the odd column
to its right carries the significance letters and the `*` / `**` low-base flags.

Parsed totals: **78 question tables**, **40 segments**, **33,240 cells**.

Bases worth flagging in the UI: 13 of the 40 segments carry `*` and 4 carry
`**`. Non-binary (n=4), $200,000+ (n=18) and $150,000–$199,999 (n=24) are too
small to report on their own. `csi_segment.low_base` carries this through
so the portal can warn rather than silently draw a bar on n=4.

---

## 3. Routing — the thing that most affects the numbers

Every one of the 404 records is `Qualified`; there are no terminates,
overquotas or partials in this export. But **most questions were not asked of
all 404.** Counting non-empty cells per question recovers the routing exactly,
and the cross-tab confirms it independently (`count / pct` returns the same
base to the unit):

| Module | Gate | Asked of | Share of wave |
|---|---|---|---|
| Shopping q1–q6 | none | 404 | 100% |
| Department stores DP2–DP6, DP8 | DP1 = bought in past 3 months | **222** | 55% |
| Department stores DP7 (retailer ratings) | per-retailer | **16–107** | varies by row |
| Diamonds DJ2, DJ4 | DJ1 = would consider diamond jewelry | **251** | 62% |
| Diamonds DJ3 | DJ2 = would consider lab-grown | **186** | 46% |
| BNPL BN2, BN4–BN8 | BN1 = used BNPL in 12 months | **133** | 33% |
| BNPL BN3 (most used) | BN2 = uses more than one | **74** | 18% |
| AI D29–D31 | D28 = used an AI tool | **283** | 70% |
| AI D32–D34 | D31 = uses GenAI for shopping | **70** | 17% |
| AI D35 | D33 = completed a purchase in-platform | **44** | 11% |
| GLP-1 GP2–GP10 | GP1 = currently using a GLP-1 | **71** | 18% |
| Gas prices D15 | D14 = cut spending | **260** | 64% |
| Sentiment, macro, demographics | none | 404 | 100% |

Two consequences, and they are the reason the schema looks the way it does.

**The cross-tab header lies about the denominator.** Every table prints
`N=404` above the Total column, because that is the *segment size*. The
percentages are computed on *Total Answering*. For DP2 "Bergdorf Goodman" the
cell reads 7.2% with a count of 16 — and 16/404 is 4.0%, not 7.2%. The real
denominator is 222. Anyone recomputing from the header will be wrong on 43 of
the 78 tables.

`count / pct` recovers the true base exactly every time, so
`csi_crosstab.answer_base_n` stores it, `csi_segment.seg_base_n` keeps the
segment size separately, and the two are never mixed.

**Several of these bases are too small to report.** GP2–GP10 sit on n=71 for
the whole wave; cut by generation or income they fall into single figures.
D35 is n=44. `csi_question.base_n` is populated at load and the portal warns
above any chart whose base is below the wave base.

---

## 4. What this implies for the design

1. **The datamap is the contract.** Load it first, every time. `datamap_hash` on
   `csi_survey` detects a questionnaire change between waves before bad data
   lands.
2. **Long, not wide.** 375 variables this wave; next wave will differ. A wide
   table means a schema migration per wave. `csi_answer` (one row per
   respondent × variable) absorbs questionnaire change with no DDL at all.
   Volume is modest: 404 × 375 ≈ 151k rows per wave, so a year of monthly waves
   is under 2 million rows — nothing for MySQL.
3. **Store both the raw fact and the cross-tab.** They answer different
   questions. The raw fact supports any cut an analyst invents; the cross-tab is
   the published, base-defined, significance-tested number that must match what
   went into the report. Recomputing percentages from raw data and getting 52.8%
   where the report said 52.7% is a credibility problem, not a rounding one.
4. **Flatten the demographics.** Filtering by generation shouldn't mean joining
   eight EAV rows per respondent. `csi_profile` pays for itself on
   every page load.
