# CIP ETL Series, Part 2: Extraction

**Consumer Insight Portal (CIP), Coresight Research**
Series: How the CIP data pipeline works, explained for managers and the business team
This part: the "E" of ETL. How CIP finds every survey, decides which ones to read, and gets the questionnaire and every respondent's data out of the source, safely and completely
Previous part: Part 1, The Pipeline End to End. Next part: Part 3, Transformation (Questionnaire and Answers)

Everything in this document is taken from the project's code (folder `cip-stg`), mainly `etl/forsta_client.py`, `etl/forsta_etl.py`, `etl/record_stream.py`, `etl/fieldwork.py`, `etl/sharepoint_china.py`, `etl/baidu_qss_export.py` and `etl/legacy_dwh.py`.

---

## 1. What "extraction" means in CIP

Extraction is everything the pipeline does to get raw data out of the place where it was collected, before any cleaning or business rule is applied. In CIP, extraction has four jobs:

1. **Find** every survey that exists in the source (discovery).
2. **Decide** which surveys are ready to be read now, which must wait, and which cannot be read (the register and its load states).
3. **Fetch** the questionnaire and every respondent's answers for each ready survey.
4. **Hold** that data safely on the server so the next steps can read it several times without asking the source again (the snapshot).

Extraction ends when the pipeline has, for one wave, the questionnaire (the datamap) in memory and every respondent record saved in a private temporary file. Part 3 picks up from there.

A rule that runs through every part of extraction: **CIP only reads.** It never creates, edits, launches, closes or deletes anything in Forsta.

## 2. The sources, and which ones extraction runs on

| Source | What it holds | Extraction method | Scheduled? |
|---|---|---|---|
| **Forsta Surveys API** | Every survey from June 2025 onward: the weekly US tracker, annual studies, client studies | Web requests to Forsta's REST API (`https://se1.decipherinc.com/api/v1/...`) | Yes, the main pipeline |
| **Baidu QSS via SharePoint** | The weekly China Consumer Survey | Two files per week from the analysts' SharePoint folder, read through Microsoft Graph | Yes, every 10 minutes once IT access is set |
| **Portal upload page** | The same China files, uploaded by hand | The Upload Survey page in the portal | On demand |
| **Old warehouse tables `dwh_sm*`** | Qualtrics (Aug 2022 to May 2025) and SurveyMonkey (2018 to July 2022) | Read inside the same MySQL server | No, history loaded once |
| **One Qualtrics Excel export** | The May 2025 wave missing from the old warehouse | Excel file read once | No, loaded once |

Most of this document is about Forsta, because that is what runs every day. Sections 13 and 14 cover the China and history sources.

## 3. Connecting to Forsta

### 3.1 Settings

The connection needs four settings, kept as environment variables on the server (never in the code):

| Setting | Value | Meaning |
|---|---|---|
| `FORSTA_HOST` | `se1.decipherinc.com` | Forsta's server for Coresight's account |
| `FORSTA_API_KEY` | a 64-character key | Created in the Forsta portal under the user's avatar, then API Access |
| `FORSTA_TIMEOUT_SECONDS` | 120 | How long to wait for Forsta to answer one request |
| `FORSTA_MAX_RETRIES` | 4 | How many times in total to try one request |

The key is sent on every request in a header called `x-apikey`. Each request also says it comes from `coresight-cip/1.0` and asks for JSON. No survey path is configured anywhere: the pipeline discovers every survey the key can see.

### 3.2 The read-only guarantee

Every request to Forsta is a GET, which by definition only reads. Forsta also offers some actions as POST requests, which could change things (launch, close, edit data, share links). The code keeps a fixed list of exactly three POSTs that only compute and change nothing:

1. Running a cross-tab in memory (`surveys/{path}/crosstabs/execute`)
2. Running a report the team saved (`surveys/{path}/crosstabs/saved/{id}/execute`)
3. Exporting that saved report as Excel, PDF or PowerPoint (`surveys/{path}/crosstabs/saved/{id}/export/...`)

Any other POST is refused inside CIP's own code before anything is sent. A path containing `..` is also refused, so no one can trick the rule with a crafted address. These three POSTs are used only to keep Forsta's fieldwork record (Section 12), and after them the pipeline re-reads the survey's "last edited" time to prove nothing changed. This was checked live on survey 261003 on 7 November 2026: the last edit and the audit log did not change.

### 3.3 How the connection handles errors

| What Forsta answers | What CIP does | Retried? |
|---|---|---|
| Success (2xx) | Continues. Logs Forsta's daily usage counter (`x-usage-today` header) when present | — |
| 401 Unauthorized | Stops with an authentication error: the key is missing, wrong, or not allowed for this survey | No |
| 403 Forbidden | Stops with an authentication error: the key is valid but has no access to this survey | No |
| 429 Too Many Requests | Treated as "Forsta is busy" | Yes |
| 500 and above (server errors) | Treated as "Forsta is busy" | Yes |
| Any other 4xx (for example 404, or 428 for a hibernated survey) | Stops with an error showing the first 400 characters of Forsta's message | No |
| Connection dropped, or no answer within 120 seconds | Network error | Yes |

Retries use waits that grow each time, from 2 seconds up to a maximum of 60 seconds, for up to 4 tries in total. A busy or briefly unavailable Forsta is absorbed this way without failing the run. Errors that will not fix themselves by waiting (a wrong key, a hibernated survey) are not retried, so the run does not waste time.

The very first call of every scheduled run is the cheapest possible one, "who am I" (`rh/users/self`). It proves the key works before anything else is attempted. If Forsta rejects it, the run stops with exit code 2 and the team is emailed.

## 4. The Forsta calls the pipeline makes

| Call | Endpoint | When | Size and purpose |
|---|---|---|---|
| Who am I | `GET rh/users/self` | Start of every run | Tiny. Proves the key works |
| List every survey | `GET rh/companies/all/surveys` | Once per run (discovery), and once more only if something is due | The register's input |
| Quota | `GET surveys/{path}/quota` | For each survey that is live, during discovery | How many completes each quota cell has and needs |
| Datamap | `GET surveys/{path}/datamap?format=json` | Once per wave loaded | About 0.5 MB. The questionnaire |
| Data | `GET surveys/{path}/data?format=json` | Once per wave loaded, and once more to re-check it | About 2 MB for 500 respondents. Every respondent's answers |
| Fieldwork reads | about 18 read-only endpoints per survey (Section 12) | After loads, and for surveys missing a record | Forsta's own record of the fieldwork |

A run that finds nothing new makes one Forsta call after the key check (the survey list) and reads quota only for surveys still live.

## 5. Discovery: finding every survey

Discovery is the function `discover()` in `etl/forsta_etl.py`. It runs at the start of every scheduled run.

### 5.1 What Forsta returns for each survey

One call returns a list with one entry per survey the key can see. The pipeline uses these fields from each entry:

| Forsta field | Example | Used for |
|---|---|---|
| `path` | `selfserve/58f/260907` | The survey's identity |
| `title` | `Shopping and Spending - inc Beauty + Tariffs` | Study type, family, calendar |
| `state` | `testing`, `live`, `closed` | Whether it can be loaded |
| `hibernated` | true or false | Whether it can be read |
| `tags` | `Weekly consumer tracker` | Study type |
| `createdOn`, `dateLaunched`, `closedDate` | dates | Fieldwork timing, reopen detection |
| `qualified`, `total` | 405, 712 | Progress to quota, reopen detection |
| `sampleSources` | panel source IDs | Stored on the wave |

### 5.2 Study type: what kind of study is it?

| Rule, checked in order | Study type |
|---|---|
| Tagged "Weekly consumer tracker", or the title starts with "Shopping and spending" | `tracker` |
| Tagged "annual tracker" | `annual` |
| Anything else | `adhoc` |

Study type matters a lot later. Only `tracker` waves can be loaded before Forsta closes them, and only trackers get a "prior week" comparison.

### 5.3 The register

Every survey from the list is written into the table **`cip_forsta_survey`**, one row per Forsta path. This table is the pipeline's memory of what exists and what it did. Its main columns:

| Column | Meaning |
|---|---|
| `forsta_path` | The survey's path (the key of the table) |
| `title`, `state`, `hibernated`, `tags`, `study_type` | As Forsta reports them |
| `created_on`, `launched_at`, `closed_at` | Dates from Forsta |
| `qualified_n`, `total_n` | Qualified and total respondents |
| `last_seen` | When discovery last saw this survey in Forsta's list (UTC) |
| `load_state` | The pipeline's decision: `due`, `loaded`, `testing`, `hibernated`, `failed` |
| `survey_id` | The wave's ID in CIP once loaded |
| `loaded_at`, `last_error`, `attempts` | Load history |
| `quota_json`, `quota_at` | The last quota reading while the survey was live |

### 5.4 Deciding the load state

For each survey, the pipeline decides one load state. The rules are checked in this exact order, and the first one that matches wins.

First, it works out whether the survey was **reopened**: either Forsta's close date is now different from the one stored, or the total number of respondents changed.

| # | Condition | Load state | What it means for the business |
|---|---|---|---|
| 1 | Already `loaded`, and (still live in Forsta, or not reopened) | `loaded` | Nothing to do. A wave loaded early while still live stays loaded until Forsta closes it |
| 2 | Live in Forsta, and its fieldwork is effectively over (the "fielded" rule, Section 6) | `due` (or stays `failed` if it was failing) | Load it now, even though Forsta has not closed it yet |
| 3 | Forsta state is not `closed` (testing, or live and still fielding) | `testing` | Wait |
| 4 | Closed but hibernated | `hibernated` | Cannot be read until someone restores it in the Forsta portal. Left alone |
| 5 | Closed, readable, and anything else (new, or reopened) | `due` (or stays `failed` if it was failing) | Load it |

Two examples:

- A weekly wave was loaded early on Tuesday morning while still live. Rule 1 keeps it `loaded`. On Wednesday Forsta closes it, so its close date changes from empty to a date. Now it counts as reopened, rule 1 no longer applies, and rule 5 makes it `due`. The next run reloads it, and that reload is final.
- An annual study was loaded last month. Someone reopened it in Forsta and collected 50 more respondents. Its total changed, so it counts as reopened, becomes `due` and is reloaded with the new respondents.

The code's comment states the principle: every closed, readable survey is loaded, however few people answered it.

### 5.5 Saving the decisions efficiently

The database is in Azure and the team works from India, where each round trip to the database costs about 250 milliseconds. So discovery writes as little as possible:

- **Every run:** one UPDATE sets `last_seen` for every survey in the list. Live surveys also get their latest quota reading.
- **Only if something changed** (a new survey, or any of title, state, hibernated, tags, study type, dates, counts or load state differs): one batched "insert or update" for the changed rows.
- **Only if a survey's Forsta state or load state changed:** one row per change in **`cip_forsta_event`**, the status history. The register keeps only the current state; this table keeps the story (for example: launched 18:02, quota full 03:10, closed 06:40, loaded 06:44).
- **When anything changed:** the survey calendar (`cip_wave_module`) is rebuilt, so it also covers surveys that were never loaded, such as hibernated ones.

An idle run is therefore one UPDATE and nothing else.

## 6. The "fielded" rule: loading a live wave early

Forsta often keeps a weekly wave open after enough people have answered. Waiting for Forsta to close it would delay the data. So for weekly tracker waves only, the pipeline decides for itself that fieldwork is over. This is the function `fielded()`.

A live wave counts as fielded when **any one** of these is true:

| Test | Rule | Why |
|---|---|---|
| Time | 9 hours or more since Forsta's launch time | The data team's window: launch about 18:00 IST, fieldwork over by about 03:00 IST |
| Quota target | 400 or more qualified respondents | The plan's target per weekly wave (400 to 414 in every Forsta wave so far) |
| All cells full | Every unconditional quota cell has reached its limit | No group needs more people |
| A whole sheet full | Qualified respondents reach the smallest total target of any quota sheet | One complete quota dimension is satisfied |

The code notes a real case: on 19 October 2026 Forsta stopped a wave at 400 with Midwest at 80 of 85. The cells were not all full, but the 400 rule fired, which is why it exists.

**What the quota reading contains.** For each live survey, the pipeline reads Forsta's quota and turns it into a simple list: for each quota cell, its sheet (for example Gender or Region), the cell's name built from Forsta's own descriptions (for example `Male`, `South`, or a combined cell), whether the sheet is conditional, the limit and the number complete. Conditional cells are ignored for the "all cells full" test. This list is also saved on the register so the portal's Launch Schedule page can show progress.

**Annual and ad hoc studies are never loaded early.** They field for days (the Holiday 2025 study fielded for 8 days), and the rule is that a study is never published half-fielded. They load only once Forsta closes them.

**Loading early does not change anything in Forsta.** The survey stays open there. When Forsta later closes it, the pipeline reloads it (Section 5.4, first example). Until then, the serving tables mark the wave "in field", so the portal knows its numbers are not final.

## 7. Choosing what to load in this run

The function `run_due()` selects the surveys to load:

- every survey whose load state is `due`, plus
- every survey whose load state is `failed` and that has failed **fewer than 3 times in a row**,
- ordered by close date, then path, so the **oldest is loaded first**.

The survey list from Forsta is fetched only once and reused for every wave in the run, so loading five waves still costs one list call.

Each wave is loaded on its own. If one fails, its error is written to the register (`load_state = failed`, `last_error`, `attempts` plus one) and to the audit log, and the run moves on to the next wave. A survey that has failed 3 runs in a row is no longer retried automatically. It waits for someone to run it by hand (`python -m etl.forsta_etl --survey <path>`), because fetching a broken survey in full on every run would only waste time.

## 8. Fetching one wave

### 8.1 The questionnaire: the datamap

The first download is the datamap, about 0.5 MB. It describes the whole questionnaire:

- every **question**: its label (code, for example `q2`, `D5`, `HX6`), its wording, its type (single, multiple, number, float, text, textarea, date) and Forsta's flags (`t` for technical, `v` for virtual/derived);
- every **variable** of the question: one per export column, for example `q2r1`, `q2r2` for the rows of a list, each with its row and column titles;
- every **value**: the answer codes and their labels, for example 1 = "Much better", 2 = "Somewhat better".

The datamap is read in full into memory. Part 3 explains how it becomes questions, rows, options and fields.

### 8.2 The respondents: the data export

The second download is every respondent's record, about 2 MB for 500 respondents.

**All statuses are downloaded, on purpose.** The request has no filter, so it returns terminated, over-quota, qualified and partial respondents. The portal's numbers use qualified respondents only, but the others are the record of how fieldwork went, and Forsta will delete archived surveys a year after archiving. The code notes that asking for qualified only would cut the download by 60 % (5.1 MB to 2.0 MB for survey 261003), but the load runs in the background and nobody waits on it, so completeness wins.

### 8.3 Streaming: reading the download piece by piece

The data export is one large JSON list. Instead of waiting for the whole body and holding it all in memory, the pipeline reads it in 64 KB pieces and pulls out one respondent at a time as soon as that respondent's record is complete. Memory use stays the size of one piece plus the largest single record, however big the survey.

While streaming, the reader checks that the export is well formed, and fails clearly if it is not:

| Problem in the download | Error raised |
|---|---|
| Does not start with a list | "Forsta data export must be a JSON array" |
| Ends before the list closes (cut off) | "ended before its array was complete" |
| A record is broken or truncated | "contains invalid or truncated JSON" |
| An entry is not a respondent object | "contains a non-object respondent" |
| A comma is missing or doubled between respondents | "missing a respondent separator" or "has a trailing comma" |
| Anything after the list | "has content after its array" |
| Characters that are not valid UTF-8 | "contains invalid UTF-8" |

**No retry after data starts arriving.** Retries happen only before the first byte of data. If the connection breaks halfway through, the error goes up and the wave fails for this run. Retrying a half-read body could add some respondents twice. The next run fetches the wave again from the beginning.

### 8.4 The snapshot: a private copy on disk

As respondents stream in, each one is written as one line to a **private temporary file** on the server's disk. Respondents without a `uuid` are skipped; these are Forsta system rows, not people. The file is deleted automatically when the wave's load finishes, whether it succeeded or failed.

Why a snapshot? The same records are read several times during one load:

1. to find the wave's date (the earliest qualified completion),
2. to write respondents and answers,
3. to verify that what was stored equals what was sent.

Reading from the disk copy guarantees all three use exactly the same data, without asking Forsta three times and without holding everything in memory. The snapshot also knows its own count of respondents, which verification uses.

### 8.5 What one raw record looks like

Each record is one respondent. Values arrive as codes and strings, not labels. An illustrative record, using the shapes the code documents:

| Key | Example value | Meaning |
|---|---|---|
| `record` | `412` | Forsta's record number in this survey |
| `uuid` | a long unique string | Forsta's unique ID for this interview |
| `status` | `3` | 1 Terminated, 2 Overquota, 3 Qualified, 4 Partial |
| `date` | `09/29/2026 01:10` | Completion date and time |
| `qtime` | `612` | Seconds the interview took |
| `markers` | quota bucket names | Which quota cells this person counted in |
| `vlist` or `list` | `114` | Panel source |
| `vos`, `vbrowser`, `vmobiledevice` | `Windows`, `Chrome`, `Desktop` | Device information Forsta derives |
| `vdropout` | a question code | Where a partial respondent stopped |
| `RID` | the panel's ID for the person | Personal: never stored as is (Part 3) |
| `userAgent`, `url`, `session`, `dcua`, `ipAddress` | | Personal: never stored |
| `q2r1`, `q2r2`, … | `1` or `0` | A multi-select item: chosen or shown but not chosen |
| `CS1` | `2` | A single-choice answer code |
| `q9oe` | free text | An "Other, please specify" box |

Nothing is cleaned or relabelled at this stage. That is transformation, in Part 3.

## 9. Wave identity: which wave is this?

Before writing anything, the pipeline decides where this survey belongs in CIP.

### 9.1 The wave label (the wave date)

**Rule:** the wave is labelled with the **Monday of the week of the earliest completion date among qualified respondents**. If the survey has no qualified respondent at all, all respondents' dates are used instead.

Example: the first qualified respondent completed on Tuesday 29 September 2026 at 01:10. The Monday of that week is 28 September 2026, so the wave label and wave date are `2026-09-28`. This matches how the data team always named weekly waves in their Excel files.

**A reload keeps its label.** If this pipeline loaded the same Forsta path before (found through the audit log entry `forsta:{path}`), the wave keeps its original label and its original `survey_id`, even if the earliest date has moved. Otherwise a reload could create a second copy of the same wave. This protection applies only to waves this pipeline loaded from the API; a wave loaded another way on the same path is never overwritten.

### 9.2 The family: which waves trend together

| Rule, in order | Family |
|---|---|
| Study type is `tracker` | `CSI-US` |
| The path is listed under a family in `config/survey_map.yml` | That family (for example `HOLIDAY_SHOPPING`, `ONLINE_GROCERY`, `APPAREL_SHOPPING`, `BACK_TO_SCHOOL`) |
| Otherwise | The title with any year removed, upper-cased, with spaces and symbols turned into `_` (for example "Holiday Shopping 2026" becomes `HOLIDAY_SHOPPING`) |

The config list exists because studies get renamed between years ("Holiday 2021 Shopping and Spending", "Holiday Shopping and Spending 2025", "Holiday Shopping 2026"). Without it, each renamed year would become its own family and lose its year-on-year comparison. The list ties together Forsta paths, Qualtrics IDs and SurveyMonkey IDs of the same study.

### 9.3 The wave's row

The wave is then created or updated in **`cip_survey`**. Its identity is the combination of platform, source reference (the Forsta path) and wave label, so the same wave always lands on the same row. Stored with it:

| Column | Source |
|---|---|
| `title`, `survey_family`, `study_type`, `platform = forsta`, `source_ref` | As decided above |
| `wave_label`, `wave_date` | Section 9.1 |
| `datamap_hash` | A SHA-256 fingerprint of the datamap. If the questionnaire changes between loads, the fingerprint changes |
| `sample_source` | Forsta's sample sources |
| `total_n` | Forsta's total, or the number of records |
| `tags` | Forsta's tags |
| `field_start`, `field_end` | Forsta's launch and close dates. An empty `field_end` means the wave is still open in Forsta |
| `load_status` | Set to `loading` immediately, so the wave is invisible until verified |

From here on, the work is transformation and loading (Parts 3 to 5).

## 10. The second extraction: re-reading Forsta to check

After a run loads a wave, it downloads that wave's data from Forsta a **second time** and compares every stored answer value with Forsta's value (`reconcile_survey`). This is extraction used as an audit. The comparison itself is explained in Part 5. Two extraction details matter here:

- The stored answers are first copied into a small temporary SQLite file, indexed by respondent, so the comparison stays fast and uses little memory even for wide annual surveys.
- If Forsta cannot be read (for example the survey has since hibernated and answers 428), the check is skipped with a warning and reported as "no answer could be compared". It never passes silently.

The same re-read can be run for every Forsta wave: `python -m etl.forsta_etl --reconcile` or `python scripts/reconcile.py`.

## 11. Extraction state at a glance

| Where | What it tells you |
|---|---|
| `cip_forsta_survey` (register) | Every Forsta survey, its Forsta state and its load state now |
| `cip_forsta_event` | Every observed change of state over time |
| `cip_load_log` | Every load attempt: source `forsta:{path}`, rows read, rows loaded, status, error |
| `logs/forsta-etl-errors.jsonl` | Every warning and error, one JSON line each, with secrets masked |
| Portal, Launch Schedule page | Planned weeks against what Forsta fielded, with quota progress |

## 12. Extracting Forsta's fieldwork record

Respondent data is only part of what Forsta holds. Forsta also knows how the fieldwork went, how the questionnaire was built, and when it will delete each survey. All of that disappears when Forsta erases an archived survey. So the pipeline extracts it too (`etl/fieldwork.py`) and keeps it in the table **`cip_forsta_record`**: one row per survey and kind of record, Forsta's answer stored exactly as sent, compressed.

**Per survey** (16 read-only endpoints plus the questionnaire file):

| Kind | What it is |
|---|---|
| survey | The survey's own record |
| completions, dropouts, splits | The respondent funnel, drop-outs by page, and the funnel by sample source, operating system, browser and device |
| warnings, launch warnings | Forsta's warnings about the survey |
| quota, terms | Quota cells and screen-out rules |
| banners, saved reports | Cross-tab banners and the team's saved reports (run and exported through the three read-only POSTs) |
| files, `survey.xml` | The survey's files, including the questionnaire's source and logic |
| audit log, tasks, layouts, data sources, can-archive | Change history and setup |

**For the company** (Coresight's account): the archive and deletion schedule, warnings for every survey, the full survey history, planned auto-closes and archives, deletion reports, retention settings, categories, cross-tab defaults, and Forsta's own list of endpoints (to notice new ones).

**Not kept, on purpose:** API keys, translations, campaigns, MaxDiff/conjoint and video.

**When it runs:** in every scheduled run, for the surveys just loaded, the surveys still in the field, and up to 10 older surveys still missing a record (about 70 seconds of Forsta calls, so a daily run stays short). About 18 calls per survey, 6 to 8 seconds. Also once at every server start, two minutes after the container starts. A failure here is logged and never stops a load. A hibernated survey is **not** woken, because waking it changes Forsta and is a paid action; it is marked hibernated and skipped.

These records feed the portal's Fieldwork and Forsta admin screens and each wave's question logic preview.

## 13. The China source: Baidu QSS through SharePoint

The China Consumer Survey is fielded on Baidu QSS. Baidu has no API that can be reached from outside China, so each week an analyst downloads two files from Baidu and puts them in a SharePoint folder.

### 13.1 Where the files are

The folder is organised as year, then month, then one folder per survey week, for example `2026/October/Survey of Oct 26`. Each week folder holds:

- **the raw export**: one row per respondent, as a `.csv` in the GB18030 encoding (Simplified Chinese Windows), as Baidu writes it, or the same table saved as `.xlsx`;
- **the topline**: Baidu's own summary, `Consumer Tracker_ <date>.xls`, with each question's answer counts and the number of people who answered it.

### 13.2 How CIP reaches SharePoint

Through Microsoft Graph, signed in as an Entra (Azure AD) app that IT sets up with read access to that one site (`Sites.Selected`). Settings: `CIP_SP_TENANT_ID`, `CIP_SP_CLIENT_ID`, `CIP_SP_CLIENT_SECRET`, `CIP_CHINA_SITE`, `CIP_CHINA_FOLDER`. Without them the watcher does nothing.

### 13.3 When it looks

Every 10 minutes from the scheduler. Optionally, SharePoint (through a Graph webhook) or a Power Automate flow can call the portal when a file changes; the portal leaves a marker file and the scheduler starts a pass within a minute. When that is set up, the 10-minute timer drops to hourly as a safety net. The webhook subscription is renewed daily.

### 13.4 What one pass does

1. Walk the folder tree and list every week folder with its files.
2. In each week folder, pick exactly **one raw file** (the one `.csv`, or the one `.xlsx` that is not an `_EN` translation) and **one topline** (the one `.xls`). If there are not exactly one of each, the folder is skipped and named, so a person can sort it out.
3. Build a version key from both files' SharePoint IDs and **eTags** (SharePoint's version stamp). If this exact pair was already loaded, or already refused, skip it. A replaced file gets a new eTag, so a corrected file is picked up automatically.
4. Work out the week from the folder names (for example "Oct 26" in year folder "2026" gives `2026-10-26`).
5. Download both files and pass them to the Baidu loader.
6. If anything loaded, rebuild the published files and post a Teams message.

### 13.5 Reading and checking the Baidu files

The Baidu loader (`etl/baidu_qss_export.py`) does a strict check **before writing anything**:

- The raw file's first three columns must be Baidu's user ID, time taken and submit time (in Chinese). Then each question is one column (single choice, marked 【单选】) or, for multiple choice, one column per answer (marked 【多选】).
- Every Chinese question and answer wording is translated through **`config/china_codebook.yml`**, which holds the analysts' own English. A wording the codebook does not know **stops the load and is named**, so nothing untranslated reaches the screens.
- Every count CIP calculates from the raw rows (each question's base and each answer's count) must **equal Baidu's topline**. A missing question or a single count off stops the load.
- Typed "other" answers are not loaded (Chinese free text), but their "Other" ticks are.

If any problem is found, nothing is written, the refusal is recorded once in the audit log, and the team is emailed.

### 13.6 Which week it is

The analysts name a survey by the week **before** the one it was answered in ("Survey of Oct 26" was fielded on 3 November). So without a folder name, the rule is: the Monday of the week of the first answer, minus 7 days. When the files come from SharePoint, the folder name wins. If the folder name is more than 21 days away from the week the answers show (for example a folder "2026/July/Survey of June 27" answered from 28 July), the answers' week is used and a warning is logged.

The China wave is stored as platform `baidu`, family `CSI-CN`, country `CN`, study type `tracker`. Uploading the same week again replaces it.

## 14. The history sources

These are not part of the scheduled pipeline. They were run once to bring the old years into CIP, and can be rerun if history must be rebuilt.

### 14.1 Qualtrics and SurveyMonkey from the old warehouse

`python -m etl.legacy_dwh --all` (Qualtrics era) and `--all --era surveymonkey`.

- The old tables (`dwh_smsurveydetail`, `dwh_smresponse`, `dwh_smresponseqa` and others) sit on the same MySQL server as CIP. So answers are moved **inside MySQL** with INSERT … SELECT; only the small question definitions travel to the pipeline. That is what made 142 Qualtrics waves loadable over the India–Azure link.
- Only **completed** responses are taken. Hand-entered summary rows in the old tables are excluded.
- Qualtrics IDs start with `SV_`; SurveyMonkey IDs are numbers.
- The old tables' question type cannot be trusted (yes/no questions were stored as "multiple choice"), so the type is inferred from the data: a matrix is a grid; no answer rows means text; more than one answer from any respondent, or "select all" wording, means multi-select; otherwise single choice. Questions with no answer rows at all are skipped and counted.
- Family: titles matching the weekly tracker become `CSI-US`; otherwise the config family list or the title. Study type `annual` if 1,500 or more completes, else `adhoc`.
- For SurveyMonkey, the panel (SurveyMonkey Audience) supplied age, gender, income and Census division per response, outside the questions. These fill the demographic profile where no question did. A respondent's own answer is never overwritten.

### 14.2 The one Qualtrics Excel export

`python -m etl.qualtrics_export --file … --wave 2025-05-12` loaded the May 2025 wave that is missing from the old warehouse. Row 1 holds column codes, row 2 the question text, then one row per respondent. With no datamap, question types and answer lists are recovered from the columns: `_TEXT` columns are open text, a group where every cell holds its own column's answer is a multi-select, any other multi-column group is a grid, a single column is single choice. Personal and system columns (IP, location, recipient, panel ID, fraud scores) are never read.

## 15. What can go wrong in extraction, and what happens

| Situation | What the pipeline does | Who finds out |
|---|---|---|
| Forsta not configured (no host or key) | Run stops, exit code 2 | Failure email |
| Forsta rejects the key | Run stops after the first call, exit code 2 | Failure email |
| Forsta busy or briefly down | Up to 4 tries per request, waits 2 to 60 seconds | Only if all tries fail |
| A survey is hibernated before it was loaded | Marked `hibernated`, left alone | Integrity "watch" warning every run: reactivate it in Forsta, the next run loads it |
| A survey disappears from Forsta's list before it was loaded | Stays in the register with an old `last_seen` | Integrity "watch" warning after a week: ask Forsta to restore it |
| The download breaks halfway | That wave fails for this run; no retry mid-stream | Failure email; next run retries (up to 3 runs in a row) |
| The download is malformed | Clear error naming the problem; wave fails | Failure email |
| A closed survey still not loaded after 3 days | Reported by the integrity check | Integrity email |
| A planned tracker week not in the portal 4 days after its Monday | Reported by the integrity check | Integrity email |
| China files incomplete in a folder | Folder skipped and named | Shown in the pass's log |
| China files fail the topline check | Nothing written; refused once | Failure email |

## 16. Summary

Extraction in CIP starts by asking Forsta for its full list of surveys and recording every one in a register, with a clear decision for each: due, loaded, waiting, hibernated or failed. Closed surveys are loaded as soon as they close. Weekly tracker waves are loaded even earlier, as soon as 400 people qualify, quotas are full or 9 hours have passed, and are reloaded when Forsta closes them. For each wave, the pipeline downloads the questionnaire and every respondent of every status, streams the data piece by piece with strict checks, keeps a private snapshot on disk, and fixes the wave's identity (its Monday, its family, its study type) so a reload always lands in the same place. All of this is read-only: Forsta is never changed. The same careful approach covers the China survey from SharePoint, where nothing loads unless every count equals Baidu's own topline, and the history from Qualtrics and SurveyMonkey, which was loaded once.

**Part 3** takes the datamap and the snapshot and explains how they are transformed into clean questions, rows, answer options, fields, respondents and answers.
