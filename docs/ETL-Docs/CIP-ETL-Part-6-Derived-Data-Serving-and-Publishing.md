# CIP ETL Series, Part 6: Derived Data, Serving and Publishing

**Consumer Insight Portal (CIP), Coresight Research**
Series: How the CIP data pipeline works, explained for managers and the business team
This part: the last stage of the pipeline. What is built on top of verified data so that every screen, report and email is ready before anyone asks for it: the cube, the serving tables with their week-on-week and year-on-year comparisons and significance flags, the data team's line-by-line file, the search index, open-ended coding, dashboards, the published files, the reports built from them, and the emails
Previous part: Part 5, Loading and Verification. This is the final part of the series

Everything in this document is taken from the project's code (folder `cip-stg`), mainly `etl/cube.py`, `etl/serving.py`, `etl/tracker_line.py`, `etl/loaders.py` (`index_survey`), `etl/open_ends.py`, `etl/publish.py`, `shared/data/payloads.py`, `etl/weekly_report.py`, `etl/sectors.py`, `etl/retailers.py`, `etl/expectations.py`, `etl/notify.py`, `etl/fieldwork.py`, `api/dashboards.py` and `config/dashboards.yml`.

---

## 1. Why everything is calculated in advance

The survey data changes once a week. People open the portal many times a day. So CIP does all counting and percentage work **once per wave, in the pipeline**, and stores the finished results. When someone opens a screen:

- most requests are answered by the web server (nginx) sending a ready file from disk, in about a millisecond, with **no database query at all**;
- the rest (custom cross-tabs, search, admin pages) are answered by the API from small, pre-built tables.

The code calls this "the MDP lesson: the cost is rows fetched". A standard screen reads tens of pre-counted rows instead of scanning a wave's 150,000 answers.

There are three layers of pre-calculation, each built from the one before:

| Layer | What it holds | Built by | When |
|---|---|---|---|
| **Cube** (`cip_agg_cell`) | Counts and bases for every answer by every standard cut and cohort | `etl/cube.py` | During each wave's load |
| **Serving tables** (`srv_wave`, `srv_result`, `srv_answer`) | Finished percentages with last week's and last year's figures, flags and significance | `etl/serving.py` | During each wave's load |
| **Published files** (`data/published/current/…`) | Every standard screen's data as compressed JSON files | `etl/publish.py` | After each run that loaded something |

## 2. The cube

### 2.1 What a cube cell is

A cell in **`cip_agg_cell`** is one count for one wave:

> For **this answer** (question, row, option), among **this group of people** (everyone, or one cohort), in **this cut** (total, or one value of one demographic): how many qualified people gave it (`n`), and how many were asked (`base_n`).

Each cell also stores the sum and count of the age midpoints and income midpoints of the people in it, so average age and average income of any answer's group can be computed without going back to the answers.

### 2.2 The standard cuts

| Cut | Values |
|---|---|
| total | Total |
| gender | as answered (for example Male, Female) |
| age_band | 18-29, 30-44, 45-60, Over 60 |
| generation | GenZ, Millennial, GenX, Boomer |
| income_band | as answered |
| census_region | Northeast, Midwest, South, West |
| urbanicity | as answered (urban, suburban, rural; city tier in China) |

### 2.3 Who is counted, and the base rules

- Only **qualified** respondents.
- Only questions that are not technical and not virtual.
- Only **single-choice** questions, **grid rows**, and **multi-select items**. Numeric and text answers have no percentages.
- **Single choice and grid rows:** the base is everyone who answered that question or row. Each answer's count is how many chose it.
- **Multi-select items:** the base is everyone who answered the question at all ("Total Answering"). An item's count is how many ticked it (code 1). An item a person was not shown counts as not chosen.
- **Groups:** cells are built once for everyone, and once more for each current cohort (for example Beauty shoppers, Part 4).

### 2.4 How it is built quickly

The wave's qualified answers, with every cut attached, are read **once** into a temporary table inside MySQL. Each cut then becomes a row of a tiny derived list of the seven cuts, so every answer meets every cut in one statement. The code notes this replaced 78,000 lookups per cut, 14 times per cohort, and cut the cube to 4 round trips per wave instead of 28.

### 2.5 Two design choices

- **A cell stores its answer's own key, not its concept.** Concept links are joined when results are read. So confirming a mapping (Part 4) never requires rebuilding the cube. Cohort cells are the exception, because a cohort rule is written over concepts; those are re-derived after a mapping decision.
- **Old cells are deleted first, in their own commit.** If the rebuild then fails, readers find no cells and fall back to counting answers directly, instead of being shown the previous load's numbers.

The code states that the cube's counts and bases are exactly what counting the raw responses gives, and the project's tests prove it for every question and cut.

## 3. The serving tables

The serving step turns cube cells into finished rows that a screen can show as they are. Nothing on the screen does arithmetic. Three tables:

| Table | One row per | Main contents |
|---|---|---|
| `srv_wave` | Verified wave | Family, study type, wave date, qualified respondents, which wave is "prior week", which is "last year", why there is no last year, rows built, whether still in field, when built |
| `srv_result` | Cube cell for everyone (each answer × each cut) | Question, answer labels and code, sort order, harmonised answer, `n`, base, **percentage**, prior week's percentage and base, last year's percentage and base, **flags** |
| `srv_answer` | Each qualified answer, with all six cuts | Used for any two-cut cross-tab (for example generation × gender) as one small grouping. Multi-select items appear only when chosen, plus one "base" row per person per multi question answered |

**Every verified wave is served, however few people answered it.** The code records this as the user's rule of 23 October 2026.

### 3.1 The percentage

`pct = 100 × n ÷ base`, rounded to 3 decimals.

### 3.2 Which wave is "prior week"

Only for weekly trackers: the latest verified wave of the **same family** dated 1 to **14 days** earlier. Annual and ad hoc studies have no prior week.

### 3.3 Which wave is "last year"

| Study type | Rule |
|---|---|
| Tracker | The verified wave of the same family whose date is within **3 days** of exactly **364 days** earlier (the same weekday a year ago) |
| Annual or ad hoc | The family's latest verified wave **300 to 430 days** earlier, because annual studies do not field in the same week each year |

If there is no last-year wave, `srv_wave` says why: `not_loaded` when Forsta shows a tracker launched that week that was never loaded (for example hibernated), so the portal says so instead of substituting another week; otherwise `none`.

### 3.4 Finding "the same answer" in the other wave

For each cell, its counterpart in the prior or last-year wave is found:

1. by **harmonised answer** (concept option), when both waves have one;
2. otherwise by the same **question code, answer label and answer code, in the same cut**, but only if that combination is unique in both waves.

Then the two cells must be **the same question**: either they share a harmonised answer, or the question wording is identical after normalisation. If the code matches but the wording does not, the comparison is dropped and the cell is flagged `wording_changed_prior` or `wording_changed_ly`. The code gives the reason: question codes are reused for new topics (Q13 was footwear one week and Cyber Monday the next), so a matching code and label alone prove nothing.

### 3.5 The flags

| Flag | Rule | Why |
|---|---|---|
| `small_base` | Base under **50** respondents | The percentage is shown but marked as less reliable (faded on screen) |
| `wording_changed_prior` / `_ly` | Same code, different question | Do not compare unlike questions |
| `base_changed_prior` / `_ly` | The share of qualified respondents asked this question moved by more than **10 percentage points** between the two waves (judged on Total) | The survey's routing changed, so the two percentages describe different populations |
| `sig_prior` / `sig_ly` | A statistically significant change (Section 3.6) | Highlights real movement |

### 3.6 Significance: which changes are real

Significance is decided **once, here**, and every screen, the weekly report, the dashboards and the emails use the same result.

**The test.** A two-sided, pooled **two-proportion z-test** at 95 %, comparing this wave's percentage with the prior (or last-year) wave's percentage for the same answer.

**Which rows are tested.** Only rows that meet every condition:

- Total cut (not demographic cuts);
- both percentages exist;
- both bases are at least **30**;
- no `base_changed` flag (routing did not change);
- the answer is not a filler answer: "None of these", "None of the above", "Other -…" or "Other (…", "Prefer not…".

**The correction for testing many rows at once.** A wave has hundreds of answers. At 95 %, about 1 in 20 unchanged answers would look "significant" by chance. So the pipeline applies the **Benjamini–Hochberg** procedure at a 5 % false-discovery rate, separately for prior-week and last-year tests, over that wave's tested rows only. In plain words: the p-values are sorted from smallest to largest; the k-th smallest must be no larger than k ÷ (number tested) × 5 %; the largest k that passes, and every row before it, are significant. Rows that were not tested are left out of the correction rather than counted as "no change".

A row that survives gets `sig_prior` and/or `sig_ly`.

### 3.7 Keeping comparisons current

When a wave is loaded, waves that compare **against it** are rebuilt too: the next fortnight's waves (their "prior week") and the waves 300 to 430 days later (their "last year"). Only those whose prior or last-year wave is actually this one are rebuilt. A failure there is logged and leaves them as they were.

### 3.8 Reliability

The build runs at the "read committed" isolation level so parallel builds do not block each other, retries up to 3 times on MySQL lock errors, and replaces the wave's three tables in one transaction. Many waves can be rebuilt in parallel (up to 4 workers): `python -m etl.serving --all --jobs 4`.

## 4. The data team's line-by-line file

Every week, the data team used to paste each wave's raw export under one header row in "Weekly Line-By-Line Survey Data.xlsx" (36 waves, February to September 2026). The pipeline now builds the same rows for every weekly tracker wave it loads, in **`cip_tracker_line`**, from `config/tracker_line.yml`.

| Rule | Detail |
|---|---|
| Rows | One per **qualified** respondent, in order of completion |
| Waves | US weekly tracker (family CSI-US) only |
| Columns, in the team's order | Month, date, then the multi-select lists q1 (Activities), q2 (Purchased In-store), q3 (Purchased Online), q4 (Food), q5 (Non-food), then Household Situation (CS1), Economic Situation (CS2), Gender (D1), Age (D2), Relationship Status (D3), Ethnicity (D4), Household Income (D5), Primary Residence (D6), State (D8), start_date, Age Range, Generation |
| Multi-select | One column per item, named "<prefix><item label>" (for example "Food: Walmart"); holds the item label when chosen, blank when not |
| Single choice | The answer label; Age becomes a number when it is one (34), but stays "70 or more" |
| Month | The 1st of the wave's month |
| date | Completion time as "MM/DD/YYYY HH:MM" |
| Age Range, Generation | From the profile, with the team's spellings ("over 60", "Millenial") |
| Not carried | D7 (the team leaves it out) and the panel session ID (personal data) |

`python -m etl.tracker_line --compare <the team's workbook>` rebuilds the rows and compares every column's value counts with the team's file, wave by wave. The project's business documentation records 16 weeks identical, with 3 errors found in the manual file.

## 5. The search index

After each load, the wave's rows in **`cip_search`** are rebuilt: one row for the wave (title, family, tags, Forsta path), one per reportable question (wording and code), and one per concept (name, code, and how many waves asked it). The portal's search box is one full-text read of this table.

## 6. Open-ended answers coded into themes

Free-text questions ("Other, please specify" and open questions) cannot be charted as typed. After each load, `etl/open_ends.py` codes each wave's open-ended questions into themes:

- **With Claude credentials:** Claude reads the answers and names up to 8 themes.
- **Otherwise, by frequency:** answers are tidied (spelling, case, near misses at 85 % similarity merged); an answer given by two or more people becomes a theme; "n/a", "nothing" and similar become one theme; the rest are "Other answers".

The result is kept in `data/coded/<survey_id>.json` (on storage that survives redeployment). A question is not coded again unless its answers change. The portal then shows the question as one more chart: the share of those who wrote something, by theme, for Total, gender and generation. **The verbatims themselves never leave that file.**

## 7. Topic dashboards and metric alerts

- **Topic dashboards** (`config/dashboards.yml`, built by `api/dashboards.py`) are the business team's databank tiles: single percentages, ranked lists (for example top retailers) and segments, each with its prior and last-year comparison and a small-base flag at 50. "Prior" is the previous wave of the same module and season; "last year" follows a rule set per dashboard (the same wave number last season, the same calendar week, or the nearest wave a year earlier). After a load, only the dashboards of modules the new wave carries are rebuilt. Every number comes from the serving rows.
- **Metric alerts** set by team members in the portal are checked once per new wave; one that fires sends a Teams message and an email to the person who set it.

## 8. Publishing: the ready files

### 8.1 What is written

`etl/publish.py` writes every standard screen's data as gzip-compressed JSON files. The paths mirror the API's own web addresses, and the bytes come from the same functions the API uses, so nginx and the API answer identically.

| File | What it feeds |
|---|---|
| `api/v1/waves.json.gz` | The survey picker: every served wave |
| `api/v1/waves/<id>/book.json.gz` | A wave's full "book": every reportable question with Total, Male, Female, Gen Z, Millennial, Gen X and Boomer columns, bases, prior-week and last-year figures, flags, and Census-weighted figures alongside |
| `api/v1/waves/<id>/cuts/<qcode>.json.gz` | A question's answers counted by every cut, enough for any two-cut cross-tab |
| `api/v1/waves/<id>/people.json.gz` | Who gave which answer, as bitsets, for building audiences (read by the API only, never served to browsers) |
| `api/v1/questions/<family>/<study>/<qcode>.json.gz` | One question across every wave of its family and every cut, for Compare and Trends |
| `api/v1/dashboards/<code>/<id>.json.gz` | The topic dashboards |
| Weekly report, sector tables, retailer databank, expected vs actual, fieldwork, public home page facts | Section 9 |
| `manifest.json` | Version, counts, each wave's build time, and the rules used |

**Display rules in the book.** Every figure is shown however few people answered; only a group of zero has no figure (the user's rule, 23 October 2026). A group that was asked a question but where nobody chose an answer shows **0 %**, not a blank. Small bases are flagged, not hidden.

**A reused question code becomes a new version.** Question files and cross-tabs pool or trend only the waves that asked the same question (same wording or shared harmonised answers). A code reused for a new topic starts a new series.

### 8.2 Building only what changed

A full rebuild of every wave takes about 16 minutes, so each publish rebuilds only what changed:

- A wave whose serving rows were not rebuilt since the live version (same build time) is **hard-linked** from the live version: no database work and no extra disk.
- Only question files of questions a new or reloaded wave asked are rewritten; the rest of the family's files are linked. Any linked file that lists a reloaded wave is rewritten too, so no file keeps old answers.
- If a wave was removed, or a display rule changed (the manifest records a rules version), every affected file is rebuilt.
- Up to 4 parallel workers read from the database.

### 8.3 Quality gates before going live

The new version is written into its own folder, `.build-<timestamp>`. Before it goes live, it must pass these gates:

1. The picker lists exactly as many waves as the serving tables hold.
2. Every wave has a readable book for the right wave, with a question list.
3. Every wave has readable respondent bitsets.
4. No wave lost more than a tenth of its questions compared with the live version (for waves with 10 or more questions). A big drop means a broken load or harmonisation, not a real change.
5. No file is missing, empty, unreadable or truncated.

If any gate fails, the new folder is deleted, the **previous version stays live**, and the team is emailed.

### 8.4 Going live in one step

The live pointer, `current`, is a link to one version folder. Publishing creates a new link and renames it over `current` in **one atomic step**, so a reader sees either the old version or the new one, never a mix. The last **3 versions** are kept; `python -m etl.publish --rollback` points `current` back to the one before.

nginx keeps a cache of answers keyed by the published version, so a new version starts fresh keys at once and nothing needs emptying; old entries expire by themselves.

### 8.5 After going live

1. **Warm the cache.** For each weekly tracker's newest wave (US and China), every one-week cross-tab of every question by every pair of cuts is requested once from nginx, so the first readers find them ready. Requests go one at a time, resting as long as each took, so warming uses at most half of the server's one CPU and people's requests always come first.
2. **Back up.** The version is saved as one tar file, either in a folder on `/home` (which survives redeployment) or in Azure Blob storage, with a `latest` pointer.
3. **Ask Coresight checks.** New survey questions are given business names and checked by Ask Coresight's quality step. A failure never affects the portal.

### 8.6 After a deployment or restart

A new container has no published files on its own disk. At start, it **restores** the latest backup in seconds (a full rebuild took 6 minutes at full CPU on 5 November 2026), rebuilds the views with the new code, swaps it live, and then re-warms nginx with this week's cross-tabs and the 300 answers people asked for most (from the request log). If the restored version is **behind** the database (a wave loaded since the backup, detected by comparing the serving tables' count and latest build time with the manifest), the next run publishes within 30 minutes. If there are no published files at all, the scheduler retries the restore every hour so screens are never left empty.

## 9. Reports and databanks built at publish time

These are computed from the published files (mostly without the database), written as files, and shown by their screens as they are.

| View | What it reproduces | Notes from the code |
|---|---|---|
| **Weekly "US Consumer Survey Insights" report** (one per recent tracker wave) | The PDF report: three biggest significant moves ("Three Data Points To Watch"); net better (better minus worse) for personal finances and the economy, weekly, four-week average and by income group, with the change over a year; 13-week tables (four-week averages) for food and nonfood retailers, categories in store and online, and activities, with one-week and three-month changes; the appendix; shopper profiles (average age and income by retailer over 13 weeks); respondents per week and margin of error; news events for the sentiment chart | Checked against the 3 November 2026 report: every number matched to 0.1 point. The same engine builds the China report. A week whose question wording differs from today's is treated as not asked, so a report never mixes two questions |
| **Databank sector tables** | One column per survey the sector ran (back to 2022), the purchase rate, and one table per tab (retailers, brands, categories) | Checked against the Databank page of 6 November 2026 (Department stores). Handles reused codes by wording (DS1 to DS3 for drugstores vs dollar stores) |
| **Retailer databank** | Every retailer and sector week by week, as counts so any choice of weeks can be added up in the browser; shoppers' split by gender, generation, income, region and area | Built from the respondent bitsets |
| **Expected vs actual** | For each retail event (Halloween, Black Friday …): what people expected before vs what they did after, the same year and the year before; differences and significance; median spend and market size where a spend question exists | Checked against the 7 October 2026 seasonal report |
| **Fieldwork** | Forsta's kept fieldwork records (funnel, drop-outs, warnings, archive schedule) for the admin screens, and each wave's question logic | From `cip_forsta_record` (Part 2), no Forsta call |
| **Public home page facts** | Counts and dates only (number of waves, responses, the latest weekly wave's date and topics) | No survey answer is public |

## 10. Emails and Teams messages

### 10.1 For each loaded survey

Sent last, after dashboards and published files are live, to the team list in `config/notify.yml` (with a copy to the data-automation mailbox), plus a Teams headline:

- who answered;
- the **three biggest significant changes** against the prior wave, by the portal's own rule (the `sig_prior` flag), one per question, leaving out the demographic questions D1 to D9;
- attachments in the team's own formats:
  - **Cross Tabs** and **Holiday Inflation Cross Tabs**, rebuilt from the database in the layout of the team's Forsta exports (Summary, Percentages, Counts; banner columns; bases; `*` under 100 respondents and `**` under 30), each only when that week's questionnaire can fill it; a set that cannot be filled is named in the email with the reason;
  - **Raw Data**, Forsta's labelled export;
  - **Weekly Line-By-Line**, for tracker waves.

Every workbook carries an "About this export" sheet stating the wave, filters and the base of each percentage.

### 10.2 For problems

Failure emails go only to the private failure list, at most once every 6 hours per subject (Part 5). Nothing about notifications can fail a run: a broken mail server never stops a load.

## 11. From Forsta closing to a number on screen

| Moment | What happens |
|---|---|
| Fieldwork effectively over (400 qualified, quota full or 9 hours) | Within 30 minutes, a run loads the wave (Part 2) |
| Load | Extract, transform, load, verify, profiles, bases, concepts, cube, search, line-by-line, serving (Parts 2 to 5) |
| Same run | Fieldwork record kept; integrity check; every value compared with Forsta; dashboards, alerts and open-ended coding |
| Same run | Publish: build, gates, atomic swap, warm cache, back up |
| Same run | Team email with the three biggest changes and the workbooks |
| Forsta closes the wave | The next run reloads it; the reload is final and replaces the early version the same way |

## 12. Summary

Once a wave is verified, CIP builds everything people will ask for. The cube counts every answer by every standard cut and cohort, with the right base for each kind of question. The serving tables turn those counts into finished percentages, find the same answer last week and last year (by concept, or by code and label only when the wording is the same), flag small bases, routing changes and reworded questions, and mark significant changes with a z-test corrected by Benjamini–Hochberg. The pipeline rebuilds the data team's line-by-line file exactly, indexes the wave for search, codes open-ended answers into themes, and refreshes the topic dashboards. Publishing writes every standard screen as a ready file, rebuilds only what changed, passes quality gates, and goes live in one atomic step with the last three versions kept for rollback. Reports, databanks and expected-versus-actual views are built from those files, and the team gets one short email per wave with the biggest changes and their usual workbooks.

## 13. The series in one paragraph

CIP's pipeline runs by itself inside the portal's container. **Extraction** finds every Forsta survey, loads each one as soon as its fieldwork is over, and never changes anything in Forsta. **Transformation** turns the questionnaire into clean questions, rows, options and fields, turns each record into respondents and answers, and applies Coresight's rules: qualified only, demographic bands and generations, income midpoints, regions, true question bases, concepts across waves, and cohorts. **Loading** writes each wave hidden, replaces its facts in one transaction, proves every value against Forsta, and only then makes it visible. **Serving and publishing** pre-compute every result with its comparisons and significance, so every screen opens instantly and every number can be traced back to the respondents who gave it.
