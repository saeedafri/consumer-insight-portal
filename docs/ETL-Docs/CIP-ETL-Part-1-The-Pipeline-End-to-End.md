# CIP ETL Series, Part 1: The Pipeline End to End

**Consumer Insight Portal (CIP), Coresight Research**
Series: How the CIP data pipeline works, explained for managers and the business team
This part: the whole pipeline in one pass, from the moment a survey closes in Forsta to the moment a number appears on a portal screen
Next parts: Part 2 Extraction, Part 3 Transformation (questionnaire and answers), Part 4 Transformation (business logic), Part 5 Loading and Verification, Part 6 Derived Data, Serving and Publishing

Everything in this document is taken from the project's code (folder `cip-stg`), not from older design notes.

---

## 1. What CIP is, in one paragraph

Coresight Research runs a weekly online survey of about 400 qualified US consumers, plus annual studies (Holiday Shopping, Online Grocery, Back-to-School, Apparel and others) and client projects. The surveys are built and fielded on **Forsta Surveys** (the platform formerly called Decipher). Before CIP, the data team downloaded each week's results from Forsta as Excel files, cleaned them by hand and pasted them into master workbooks. CIP replaces that manual work. A program, the **ETL pipeline**, reads every survey directly from Forsta, cleans and organises the data the same way the team did by hand, proves the stored data is identical to Forsta, and stores it in Coresight's MySQL database. The **portal** (the website) then shows charts, tables, trends, cross-tabs and reports from that database. Nobody downloads or pastes anything.

## 2. Why the pipeline exists, in business terms

There are four business reasons, and each one shaped how the pipeline is built.

**Reason 1: remove manual work and manual errors.** The data team's weekly line-by-line Excel file was rebuilt by the pipeline and compared week by week. The pipeline found errors in the manual file. Automation removes that class of error.

**Reason 2: Forsta does not keep data forever.** Forsta "hibernates" a survey after 90 days with no respondents and no one opening it. A hibernated survey cannot be read through the API until someone restores it in the Forsta portal. A hibernated survey can then be archived, and an archived survey is erased 12 months later. After that, Coresight's database is the only copy. This is why the pipeline loads every wave as soon as its fieldwork ends, and why it also keeps Forsta's fieldwork records (Part 6).

**Reason 3: speed for the reader.** All counting and percentage work is done in advance, once per wave, by the pipeline. When an analyst or a client opens a screen, the numbers are already calculated and saved as files. Screens open in about a millisecond instead of waiting for the database.

**Reason 4: trust.** A wave becomes visible only after the pipeline has proven, answer by answer, that what it stored matches what Forsta sent. If anything does not match, the wave stays hidden and the team is emailed.

## 3. Key words used in this series

These terms come up in every part. Each one is defined the way the code uses it.

| Term | Meaning |
|---|---|
| **ETL** | Extract, Transform, Load. Extract = read the data from the source. Transform = clean, reshape and apply business rules. Load = write it into the database. |
| **Forsta** | The survey platform. CIP only ever reads from it. It never changes anything in Forsta. |
| **Survey** | One questionnaire in Forsta, with its own address called a **path**, for example `selfserve/58f/260907`. |
| **Wave** | One fielding of a study. For the weekly tracker, each week is a new Forsta survey, so one Forsta survey = one wave. |
| **Wave label / wave date** | The Monday of the week the wave was fielded, for example `2026-09-28`. |
| **Family** | Waves of the same study that should be trended together. The weekly US tracker is family `CSI-US`. The China tracker is `CSI-CN`. An annual study's family is its title without the year, for example `HOLIDAY_SHOPPING`. |
| **Study type** | `tracker` (weekly), `annual` or `adhoc` (one-off or client study). Decided from Forsta tags and the title. |
| **Respondent** | One person's interview. |
| **Status** | Forsta's code for how an interview ended: 1 Terminated (screened out), 2 Overquota (their group was already full), 3 Qualified (completed and counts), 4 Partial (dropped out). |
| **Qualified** | Status 3. Every percentage on the portal is based on qualified respondents only. |
| **Datamap** | Forsta's description of the questionnaire: every question, its wording, its type, its rows and its answer codes and labels. |
| **Records** | Forsta's data export: one record per respondent, holding a value for each question variable. |
| **Register** | The table `cip_forsta_survey`: the pipeline's list of every Forsta survey it can see and what it has done with each. |
| **Load state** | A survey's state in the register: `due`, `loaded`, `failed`, `testing`, `hibernated`. |
| **Load status** | A wave's state in the main survey table `cip_survey`: `loading`, `verified`, `failed`. Only `verified` waves are shown on the portal. |
| **Concept** | A question tracked across waves under one stable identity, even if its code or exact wording changed. This is what makes trends possible. |
| **Cube** | Pre-counted results: for every answer, how many qualified people gave it, in total and by each standard demographic cut. |
| **Serving tables** | The final, ready-to-display results built from the cube: percentages, last week's figure, last year's figure, and warning flags. |
| **Publish** | Writing every standard screen's data as ready files that the web server sends directly. |

## 4. Where the data comes from

CIP has one live source and three history sources.

| Source | Years | How CIP gets it | Runs automatically? |
|---|---|---|---|
| **Forsta Surveys API** | June 2025 onward | Read through Forsta's REST API (web requests that only read) | Yes. This is the main pipeline and the focus of this series. |
| **Baidu QSS (China Consumer Survey)** | Weekly China waves | Analysts put Baidu's raw export (.csv) and its topline (.xls) in a SharePoint folder; CIP picks them up, or they are uploaded on the portal's Upload Survey page | Yes, once IT access to SharePoint is set |
| **Qualtrics** | Aug 2022 to May 2025 | From the old warehouse tables `dwh_sm*` (and one Excel export for May 2025) | No. Loaded once, as history. |
| **SurveyMonkey** | 2018 to July 2022 | From the same old `dwh_sm*` tables | No. Loaded once, as history. |

The scheduled pipeline never reads the old warehouse again. History was loaded one time. The README states the database holds **373 verified waves, from 18 January 2018 to 2 November 2026**.

## 5. Where the data goes

All data goes into one MySQL 8 database called **`cip_stg`**, hosted on Azure (server `csr-mysql8-flex-stg`). Every CIP table starts with `cip_` or `srv_`. Only the ETL writes to it. The portal and its API only read.

Think of the database in six layers. Data flows down through them.

| Layer | What it holds | Main tables |
|---|---|---|
| 1. Register | Every Forsta survey seen, its Forsta state, and the pipeline's decision about it | `cip_forsta_survey`, `cip_forsta_event` |
| 2. Questionnaire (definitions) | Waves, questions, grid rows and list items, answer options, and one "field" per export column | `cip_survey`, `cip_question`, `cip_item`, `cip_option`, `cip_field`, `cip_topic` |
| 3. Facts | One row per respondent, and one row per answer (the biggest table, about 23 million rows) | `cip_respondent`, `cip_answer` |
| 4. Derived | Demographic profile per person, concepts across waves, cohorts, the cube, search index, the team's line-by-line rows, the survey calendar | `cip_profile`, `cip_concept*`, `cip_respondent_cohort`, `cip_agg_cell`, `cip_search`, `cip_tracker_line`, `cip_wave_module` |
| 5. Serving | Finished percentages with comparisons and flags, ready for any screen | `srv_wave`, `srv_result`, `srv_answer` |
| 6. Published files | Every standard screen's data as compressed JSON files on disk | folder `data/published/current/…` |

Every load is also written to an audit table, `cip_load_log`. Nothing enters CIP without a row there.

## 6. Where the pipeline runs

The whole portal runs as **one container** on **Azure App Service**. Inside that one container, three things run side by side:

1. **nginx**, the web server. It sends the website and the published files to browsers.
2. **The API**, a Python FastAPI program. It answers requests that cannot be prepared in advance: custom cross-tabs, search, sign-in, admin pages.
3. **The ETL scheduler**, a small shell loop in `deploy/etl-loop.sh`. It starts the pipeline jobs at their times, at a lower CPU priority so the website stays fast.

The container is started by `deploy/start.sh`. If nginx, the API or the scheduler stops, the container stops and Azure starts a fresh one. Logs and some working files live in `/home/cip`, which survives restarts and new deployments.

## 7. When the pipeline runs: the schedule

The scheduler wakes every minute and checks the clock (UTC). These are its jobs, from the code in `deploy/etl-loop.sh`:

| When (UTC) | When (IST) | Job | Purpose |
|---|---|---|---|
| Monday 12:00 | Monday 17:30 | `scripts/weekly_forsta.py` (the **launch run**) | On a Monday the data team planned a launch, it "watches" the new wave for up to 54 hours, checking every 30 minutes, and loads it when fieldwork ends |
| Every day 03:30 | Every day 09:00 | `scripts/weekly_forsta.py` | A short run that loads any other survey that closed, such as an annual or ad hoc study. Friday's run also runs the full integrity check |
| Every 30 minutes (:00 and :30) | | `scripts/weekly_forsta.py --once` | One single check. Safety net: if a deployment killed Monday's watch, a closed wave still loads within 30 minutes |
| Every hour at :05 | | `scripts/weekly_forsta.py --watchdog` | Raises an alarm if a run stopped without finishing, or if no run happened for over 2 hours |
| 2 minutes after each container start | | `python -m etl.fieldwork` | Saves Forsta's fieldwork records for any survey still missing them |
| Every 10 minutes (or within a minute of a SharePoint notification) | | `python -m etl.sharepoint_china` | Loads new China survey weeks from SharePoint, once IT access is set |
| Every hour at :10, only if no published files exist | | `python -m etl.publish --restore` | Makes sure the screens are never left empty |
| Every minute | | log archiving | Any log file over 20 MB is zipped into `logs/archive/` |

**The run lock.** Every job that writes to the database first takes one shared lock in MySQL, named `cip_etl` (`GET_LOCK`). If another job already holds it, the new job stops at once. So two writers never run at the same time. This matters because two writers once deadlocked each other (20 October 2026). The lock belongs to the database connection, so if a job is killed, the lock is released automatically.

## 8. One scheduled run, step by step

This is what `scripts/weekly_forsta.py` does each time it runs. Each step is shown with the business reason for it.

### Step 1: Pre-checks (stop early if something basic is wrong)

1. **Is Forsta configured?** The Forsta host and API key must be set. If not: email the failure and stop with exit code 2.
2. **Is the database reachable?** It tries up to 4 times, 5 minutes apart (15 minutes of patience for a network or VPN blip). If still unreachable: email and stop with exit code 4. The next scheduled run tries again.
3. **Does Forsta accept the API key?** It calls the cheapest Forsta endpoint, "who am I" (`rh/users/self`). If Forsta rejects the key: email and stop with exit code 2.
4. **Is the database schema up to date?** Three tables must exist (`cip_forsta_survey`, `cip_search`, `cip_tracker_line`). If any is missing, the database is older than the code, so the run refuses to load anything (exit code 2) and says to run `scripts/init_db.py` first.

### Step 2: Discover (Extraction begins)

One call to Forsta lists every survey the API key can see. Each survey is written into the register with its title, Forsta state, tags, launch and close dates, and counts. The pipeline then decides each survey's **load state**: due, loaded, testing, hibernated or failed. Part 2 explains these rules in full. In short: a closed, readable survey that is not loaded yet is **due**. A weekly tracker wave still live in Forsta also becomes due once its fieldwork is effectively over (9 hours after launch, or 400 qualified, or quota full).

### Step 3: Load every due wave (Extract, Transform, Load)

Every due wave, and every failed wave that has failed fewer than 3 times in a row, is loaded one at a time, oldest first. For each one, the pipeline downloads the questionnaire and all respondent records, transforms them, writes them, verifies them, and builds everything derived from them. Section 9 below walks through one wave. If a wave fails, the failure is recorded and the run moves on to the next wave.

### Step 4: Keep Forsta's fieldwork records

For the waves just loaded, plus surveys still in the field and a few older ones still missing it, the pipeline saves Forsta's own fieldwork record: the respondent funnel, drop-outs by page, quota, warnings, the questionnaire source file, and Forsta's archive and deletion schedule. These are read-only calls. A failure here is logged and never stops the run.

### Step 5: If nothing was loaded, finish quickly

If nothing was loaded and nothing failed, the run is "idle". On any day except Friday, and if the published files are not behind the database, it stops here with exit code 0. An idle run costs one Forsta call and two small database queries. Friday's run continues to the full checks below.

### Step 6: Integrity check (heal what can be rebuilt, report the rest)

`etl/integrity.py` checks that the database is whole. Missing derived rows (for example a verified wave with no cube cells) are rebuilt automatically. Rows pointing at something deleted are removed. Problems in the loaded data itself (duplicate respondents, a wave stuck in "loading", a closed survey still not loaded after 3 days) are never changed automatically. They are reported so a person decides. Part 5 lists every check.

### Step 7: Compare every loaded answer with Forsta again

For each wave loaded in this run, the pipeline downloads the data from Forsta a second time and compares **every stored answer value** with it. This is a second, independent proof on top of the count check done during the load.

### Step 8: Business outputs for the new waves

For each newly loaded wave:

- **Topic dashboards** (`config/dashboards.yml`) for the modules the wave carries are rebuilt.
- **Metric alerts** that team members set on the portal are evaluated, and a Teams message and an email go out if one fires.
- **Open-ended answers** ("Other, please specify" and free-text questions) are coded into themes so they can be charted (by Claude if credentials are set, otherwise by frequency).

### Step 9: Publish

If anything was loaded or failed, or the published files are behind the database, the pipeline rebuilds the published files (`etl/publish.py`). It writes a full new version in a new folder, runs quality gates on it, and only then switches the live pointer to it in one atomic step. If a gate fails, the previous version stays live. Part 6 explains this.

### Step 10: Tell people

- One email per loaded survey to the team list in `config/notify.yml`: who answered, the three biggest significant changes, and attached files in the team's own formats (cross-tab workbooks and the weekly line-by-line file).
- Failure emails go only to the failure list (internal error details).
- If the integrity check found problems, one email lists them.

### Step 11: Check that published numbers did not move

Only when no wave failed in this run: `etl/publications.py` re-computes every number Coresight has already published (frozen "publications") and compares them with today's data. If any published number would now come out different, the team is told.

### Step 12: Exit code

The run ends with a number that tells the scheduler what happened:

| Exit code | Meaning |
|---|---|
| 0 | Everything due was loaded and verified, or there was nothing to do |
| 1 | A wave failed to load or verify |
| 2 | Forsta rejected the key, Forsta is not configured, or the schema is behind the code |
| 3 | Loaded, but a previously published number moved |
| 4 | The database stayed unreachable (4 tries, 5 minutes apart) |
| 5 | The integrity check found something it could not heal |

## 9. Inside one wave: the full journey

This is `load_survey()` and `_load_snapshot()` in `etl/forsta_etl.py`. It is the heart of the pipeline. The code times each stage separately and logs the seconds, so each stage below is a real, measured step.

| # | Stage | E, T or L | What happens | Business reason |
|---|---|---|---|---|
| 1 | **Fetch** | Extract | Download the datamap (the questionnaire, about 0.5 MB) and every respondent record (about 2 MB for 500 people). Records are streamed and saved to a private temporary file on disk as they arrive. Records without a `uuid` (Forsta system rows) are dropped. | All respondents are kept, not only qualified ones: the others are the record of the fieldwork, and Forsta will delete the survey one day. |
| 2 | **Wave identity** | Transform | Decide the wave label: the Monday of the earliest completion date among qualified respondents. A wave this pipeline loaded before keeps its old label and ID. Decide study type and family. | The same wave must always land in the same place, even when reloaded. |
| 3 | **Survey row** | Load | Create or update the wave's row in `cip_survey` and set its status to `loading`. A loading wave is invisible to the portal. Start an audit row in `cip_load_log`. | Nobody sees half-written data. |
| 4 | **Definitions** | Transform + Load | Turn the datamap into questions, grid rows and list items, answer options and fields. Assign each question a topic. Drop personal fields. Write them. | Gives every answer a meaning: which question, which row, what the code stands for. |
| 5 | **Write** | Transform + Load | Turn each record into one respondent row and many answer rows (one per question variable that has a value). Replace the wave's answers in one database transaction. | One transaction: either every answer is replaced, or none is. |
| 6 | **Verify** | Check | Count check: stored respondents equal records sent; every datamap variable has a field; every field has exactly as many stored answers as the payload had values. Any difference fails the wave. Then remove list rows the questionnaire no longer has and nobody chose. | The proof that stored data equals Forsta's data. |
| 7 | **Profiles and bases** | Transform | Build one demographic profile per respondent (gender, age, age band, generation, income band, region and more). Count each question's base: qualified people who actually answered it. | Every demographic filter and every correct percentage depends on these. |
| 8 | **Harmonise** | Transform | Link each question to a concept so it can be trended with earlier waves. Exact matches are confirmed automatically. Similar wording is proposed for an analyst to review. | Makes "this week vs last week vs last year" possible even when wording or codes change. |
| 9 | **Cube** | Derive | Re-derive cohort membership (for example "Beauty shoppers") and pre-count every answer by every standard cut. | Fast, exact counts for every screen. |
| 10 | **Search** | Derive | Index the wave and its questions for the portal's search box. | People find questions by typing. |
| 11 | **Line-by-line** | Derive | For weekly tracker waves only: build the data team's line-by-line rows (one per qualified respondent, their column headers and order). | Reproduces the team's own weekly Excel file. |
| 12 | **Serving** | Derive | Build finished results: percentage, last week's and last year's figures, warning flags and significance flags. | Screens show results without doing any arithmetic. |
| 13 | **Mark verified** | Load | Close the audit row, set the wave to `verified` (now visible) and the register entry to `loaded`. Rebuild the survey calendar. Rebuild the serving rows of later waves that compare against this one. | The wave goes live only after every step succeeded. |

**If any stage fails:** the audit row records the error. If the failure happened before the answers transaction committed, and the wave was already verified from an earlier load, it stays verified (its old data was not touched). Otherwise the wave is marked `failed` and its serving rows are removed so no screen shows numbers for answers that are no longer there. The register marks the survey `failed` with the error message, and the next run retries it, up to 3 times in a row. After that, it waits for someone to run it by hand.

## 10. How E, T and L map to the code

| ETL stage | Main files | What each file does |
|---|---|---|
| Orchestration | `deploy/etl-loop.sh`, `scripts/weekly_forsta.py` | The scheduler and the scheduled run |
| **Extract** | `etl/forsta_client.py` | Talks to the Forsta API: authentication, retries, streaming |
| | `etl/forsta_etl.py` (`discover`, `fielded`, `run_due`, `load_survey`) | Decides what to load and fetches it |
| | `etl/record_stream.py` | Saves the streamed records to a temporary file so they can be read several times |
| | `etl/sharepoint_china.py`, `etl/baidu_qss_export.py` | The China source |
| | `etl/legacy_dwh.py`, `etl/qualtrics_export.py` | History (one-time) |
| **Transform** | `etl/forsta_api.py` | Datamap to questions; personal-field denylist |
| | `etl/records.py` | Shared shapes, text cleaning, the respondent key (hash) |
| | `etl/forsta_etl.py` (`_respondent`, `_answer_values`) | Records to respondent and answer rows |
| | `etl/survey_map.py` + `config/survey_map.yml` | Topics, demographic mapping, age bands, generations, income midpoints, regions |
| | `etl/wave_loader.py` | Profiles, question bases, wave label |
| | `etl/harmonise.py` | Concepts across waves |
| | `etl/cohorts.py` + `config/cohorts.yml` | Named respondent groups |
| **Load** | `etl/loaders.py` | Survey and definition upserts, audit log, lock, search index |
| | `shared/core/database.py` (`bulk_insert`) | Fast bulk upload with MySQL `LOAD DATA LOCAL INFILE` |
| | `etl/forsta_etl.py` (`_write`, `verify`, `reconcile_survey`) | Writing answers and proving them |
| **Derive and serve** | `etl/cube.py`, `etl/serving.py`, `etl/tracker_line.py`, `etl/survey_calendar.py` | Pre-computed results |
| | `etl/publish.py` | Published files |
| **Checks and notices** | `etl/integrity.py`, `etl/publications.py`, `etl/notify.py`, `etl/fieldwork.py` | Health, drift, emails, Forsta's records |

## 11. A Monday, as it actually happens

This is how a normal week of the US weekly tracker plays out, from the code's own timings.

1. **Monday 17:30 IST (12:00 UTC).** The launch run starts. If the data team's plan (`config/launch_schedule.yml`) has a launch today, it posts a Teams message: which sector and topics launch today, and that CIP will check every 30 minutes.
2. **About 18:00 IST.** The wave launches in Forsta. In the register it shows as `testing` (live, not yet done). While it is live, the pipeline also reads its quota cells (how many completes each group still needs) for the portal's Launch Schedule page.
3. **Every 30 minutes,** the watch runs one full cycle: discover, load what is due, and so on.
4. **When fieldwork is effectively over** (whichever comes first): 400 qualified respondents; or every quota cell full; or 9 hours after launch, which is about 03:00 IST. The wave becomes `due`, even though Forsta still shows it as live, and is loaded. The serving tables mark it "in field" because it is not final yet. The code notes that Forsta often stops a wave at 400 with one or two cells still short (for example Midwest 80 of 85 on 19 October 2026), so the 400 rule is usually the one that fires.
5. **When Forsta closes the wave,** its close date changes. The pipeline sees that, marks it `due` again and reloads it. That reload is the final version.
6. **The watch ends** when this week's wave is both loaded and closed, or after 54 hours (Monday 17:30 to Wednesday 23:30 IST). If 54 hours pass first, the team gets a Teams warning and the next runs keep checking.
7. **Annual and ad hoc studies** field for days. They are never loaded early. They load only after Forsta closes them, usually picked up by the 09:00 IST daily run.

## 12. Safety mechanisms, in one place

| Risk | What the pipeline does |
|---|---|
| Changing data in Forsta by accident | Every call is a read (GET). The only POSTs allowed are three Forsta computations that only read (running a cross-tab or a saved report, exporting a saved report). Any other POST is refused in code before it leaves the machine. |
| Forsta slow or briefly down | Each request is tried up to 4 times in total, with waits that grow from 2 up to 60 seconds, for connection errors, timeouts, "too many requests" (429) and server errors (5xx). |
| A bad wave keeps failing | It is retried at most 3 runs in a row, then waits for a manual run. |
| Two jobs writing at once | One database lock (`cip_etl`). The second job stops. |
| Half-written data on screen | A wave is `loading` (hidden) until fully verified. Answers are replaced in one transaction. |
| A silently changed value | The bulk upload fails the whole wave if MySQL reports even one warning. Numbers are rounded to 4 decimals before upload so MySQL never rounds them itself. |
| Personal data | Browser string, link, session, device fingerprint and IP address are never stored. The panel ID is stored only as a keyed hash (HMAC-SHA256 with a secret salt), so it cannot be turned back into the ID. |
| A run killed silently | Each run writes a heartbeat file promising its next sign of life. The hourly watchdog emails if the promise is broken. |
| Secrets in logs | Any environment value that looks like a key, password, token or webhook is masked as `***` in every log line. |
| A broken publish | Quality gates check the new version; if one fails, the old version stays live. The last 3 versions are kept for rollback. |

## 13. Size and scale (from the code and its documentation)

| Measure | Value |
|---|---|
| Verified waves | 373 (18 Jan 2018 to 2 Nov 2026) |
| Answers stored | about 23 million rows in `cip_answer` |
| Answer rows per weekly wave | about 151,000 |
| Qualified respondents per weekly wave | about 400 (400 to 414 in all Forsta waves so far) |
| People who start a weekly wave | about 500 to 800 |
| Datamap size | about 0.5 MB |
| Data export size | about 2 MB for 500 respondents |
| Longest a run may take before the watchdog calls it stuck | 3 hours |

## 14. Summary

The CIP pipeline runs by itself inside the portal's container. Every Monday it watches the new weekly wave and loads it as soon as fieldwork is effectively over, then reloads it when Forsta closes it. Every day it loads any other survey that closed. For each wave it extracts the questionnaire and every respondent from Forsta, transforms them into clean questions, respondents and answers with Coresight's business rules (qualified only, demographic bands, generations, regions, concepts across waves), loads them in one transaction, proves they match Forsta exactly, and only then makes them visible. It then pre-computes every result, publishes ready files for the screens, checks the database's health, and emails the team.

The next five parts go deeper:

- **Part 2, Extraction:** the Forsta API, discovery rules, the register's states, early loading of live waves, how data is downloaded and streamed, wave identity, and the China and history sources.
- **Part 3, Transformation (questionnaire and answers):** how the datamap becomes questions, rows, options and fields; question types; grids, bipolar grids and "Other (specify)"; personal-data removal; how each record becomes respondent and answer rows.
- **Part 4, Transformation (business logic):** demographic profiles, age bands, generations, income midpoints, census regions, question bases, topics, harmonisation into concepts, and cohorts.
- **Part 5, Loading and Verification:** write order, transactions, bulk upload, the verification rules, failure handling, reloads, reconciliation and the integrity checks.
- **Part 6, Derived Data, Serving and Publishing:** the cube, serving tables, prior-week and last-year comparisons, significance testing, the line-by-line file, publishing, emails and Forsta's fieldwork records.
