# CIP ETL Series, Part 5: Loading and Verification

**Consumer Insight Portal (CIP), Coresight Research**
Series: How the CIP data pipeline works, explained for managers and the business team
This part: the "L" of ETL, and the proof that comes with it. How data is written into the database, in what order and inside which transactions; how every wave is proven equal to its source before anyone can see it; what happens when something fails; and the checks that keep the whole database healthy over time
Previous part: Part 4, Transformation (Business Logic). Next part: Part 6, Derived Data, Serving and Publishing

Everything in this document is taken from the project's code (folder `cip-stg`), mainly `etl/forsta_etl.py` (`load_survey`, `_load_snapshot`, `_write`, `verify`, `reconcile_survey`), `etl/loaders.py`, `shared/core/database.py` (`bulk_insert`), `etl/integrity.py`, `etl/publications.py` and `scripts/weekly_forsta.py`.

---

## 1. What "loading" means in CIP

Loading is writing the transformed data into the MySQL database `cip_stg` so that it is stored permanently, can be found again, and can be trusted. In CIP, loading is never just "insert the rows". Every load follows six principles. Each one is a business promise.

| Principle | What it means | Business promise |
|---|---|---|
| **Invisible until proven** | A wave is hidden (`loading`) while it is written, and becomes visible (`verified`) only after every check passes | Nobody ever sees half-written or wrong data |
| **All or nothing for the facts** | A wave's respondents and answers are replaced in **one** database transaction | A failure never leaves a wave half old and half new |
| **Safe to repeat** | Every write is keyed on Forsta's own identifiers and updates in place | Re-running a load never creates duplicates |
| **One writer at a time** | Every job that writes takes one shared lock first | Two jobs never overwrite or deadlock each other |
| **Every load is recorded** | Each attempt gets a row in the audit table `cip_load_log` | Who loaded what, when, how many rows, and why it failed is always on record |
| **Fail loudly** | Any doubt (a count that differs, a database warning) fails the wave and emails the team | No number is ever changed or dropped silently |

## 2. The order of writes for one wave

This is the exact sequence in `_load_snapshot()`. "Own" means the step commits in its own transaction. "A" marks the single transaction that replaces the facts.

| # | Step | Tables written | Transaction |
|---|---|---|---|
| 1 | Create or update the wave's row, then set it to `loading` with sample source, total respondents, tags, fieldwork start and end | `cip_survey` | own (two short ones) |
| 2 | Open an audit row: source type `api`, object `data`, reference `forsta:{path}` | `cip_load_log` | own |
| 3 | Write the questionnaire: topics if new, questions, options, items, fields | `cip_topic`, `cip_question`, `cip_option`, `cip_item`, `cip_field` | own |
| 4 | Write respondents; remove respondents Forsta no longer has; delete the wave's old answers; write the new answers | `cip_respondent`, `cip_profile`, `cip_respondent_cohort`, `cip_answer` | **A** |
| 5 | **Verify** (reads only) | none | |
| 6 | Remove list rows the questionnaire no longer has and nobody chose | `cip_item` | own |
| 7 | Rebuild demographic profiles and record which question fed each | `cip_profile_map`, `cip_profile` | own |
| 8 | Count each question's base | `cip_question.base_n` | own |
| 9 | Harmonise: concepts, concept options, links | `cip_concept`, `cip_concept_option`, `cip_concept_map` | own |
| 10 | Cube: delete old cells (own commit), then re-derive cohorts and build new cells | `cip_agg_cell`, `cip_respondent_cohort` | own (two) |
| 11 | Search index | `cip_search` | own |
| 12 | Line-by-line rows (weekly tracker only) | `cip_tracker_line` | own |
| 13 | Serving rows | `srv_wave`, `srv_result`, `srv_answer` | own |
| 14 | Close the audit row: rows read, rows loaded, status `success` | `cip_load_log` | own |
| 15 | Set the wave to `verified` (now visible) | `cip_survey` | own |
| 16 | Mark the register `loaded`, with the wave's ID and time; record the event | `cip_forsta_survey`, `cip_forsta_event` | own |
| 17 | Rebuild the survey calendar | `cip_wave_module` | own |
| 18 | Rebuild the serving rows of waves that compare against this one | `srv_*` of other waves | own per wave |

The code times stages 3 to 13 and logs the seconds for each (`fetch`, `definitions`, `write`, `verify`, `profiles`, `harmonise`, `cube`, `search`, `tracker_line`, `serving`), together with respondents loaded, harmonisation counts and cube cells. So the cost of each stage is visible in the logs for every wave.

**Why step 4 alone is one big transaction, and the rest are separate.** The facts (respondents and answers) are the irreplaceable part: they must change together or not at all. Everything after step 5 is **derived** from the facts and can always be rebuilt from them. If a derived step fails, the facts are still correct, and the integrity check (Section 11) or the next run rebuilds what is missing.

## 3. Writing the survey row and the questionnaire

### 3.1 The survey row

The wave's row in `cip_survey` is written with "insert, or update if it exists", keyed on (platform, source reference, wave label). For a Forsta wave that is (`forsta`, the Forsta path, the Monday label). The same Forsta wave therefore always lands on the same row and keeps its `survey_id`. On update, the family, wave label, wave date and datamap fingerprint keep their stored values if the new ones are empty.

Immediately after, the wave is set to **`loading`**. Every portal screen and every derived step reads only `verified` waves, so from this moment the wave disappears from view until it is proven.

### 3.2 The questionnaire

The questions, options, items and fields (Part 3) are written in one transaction with a fixed, small number of statements: one batched statement per table, whatever the size of the questionnaire. Every row is "insert, or update if it exists", keyed on Forsta's own names. Fields use "insert if missing". Reloading an unchanged questionnaire therefore changes nothing; a changed questionnaire updates wordings, labels and flags in place.

## 4. Transaction A: replacing the facts

This is the core of loading (`_write()`). Everything below happens inside one database transaction.

### 4.1 Respondents

1. Each record from the snapshot becomes a respondent row (Part 3, Section 8).
2. Rows are sent 512 at a time with "insert, or update if it exists", keyed on (wave, record number). A reloaded respondent keeps their `respondent_id`.
3. The pipeline reads back every respondent of the wave and their IDs.
4. **Anyone no longer in Forsta is removed.** Any stored respondent whose `uuid` was not in this download is deleted, along with their cohort memberships and demographic profile. The database mirrors Forsta exactly.

### 4.2 Answers

1. All of the wave's existing answers are deleted.
2. New answer rows are generated one record at a time from the snapshot (Part 3, Section 9) and written to a temporary tab-separated file on the server.
3. The file is uploaded to MySQL in **one command**, `LOAD DATA LOCAL INFILE`, in UTF-8 (utf8mb4). Empty values are written as MySQL's NULL marker, and tabs, line breaks and backslashes inside values are escaped so they cannot break a row.
4. The temporary file is deleted.

**Why one bulk command.** The database is in Azure and the team is in India. The code measured that the network round trips, not the database, were the cost: 13,000 rows took 18 seconds as ordinary inserts. One bulk upload sends the whole wave as one compact stream.

**The fallback.** If the server refuses bulk upload from a client (MySQL errors 1148, 2068 or 3948, meaning "LOCAL INFILE is switched off"), the same file is read back and sent as batched inserts of 5,000 rows each. Any other error is raised.

### 4.3 The "zero warnings" rule

After the bulk upload, the pipeline asks MySQL for warnings. **If there is even one**, it raises an error: "LOAD DATA into cip_answer warned …: nothing is kept". The transaction rolls back, and the wave's previous answers stay exactly as they were.

Why so strict? When MySQL bulk-loads a value that does not fit its column, it often adjusts it (truncates text, rounds a number, turns a bad value into zero) and only reports a warning. Without this rule, an answer could be stored with a changed value and no one would know. This is also why the pipeline rounds numbers to 4 decimals itself before upload (Part 3): MySQL's own rounding would raise a warning.

### 4.4 Commit

If every statement succeeds and there is no warning, transaction A commits. The wave's new facts are now stored, but the wave is still `loading`, so still invisible.

## 5. Verification: proving the stored data equals Forsta

`verify(survey_id, datamap, records)` runs right after transaction A. It only reads. It must return **no problems**, or the wave fails.

### 5.1 The three checks

| # | Check | How it is counted | Example of a failure message |
|---|---|---|---|
| 1 | **Every respondent stored** | Respondents stored for the wave = records in the snapshot | `respondents: 498 stored, 500 sent` |
| 2 | **Every question variable has a field** | Every variable in the datamap (except the personal ones: `userAgent`, `url`, `session`, `dcua`, `ipAddress`, `RID`) has a row in `cip_field` | `datamap variable q14r3 has no field` |
| 3 | **Every value stored** | For every field: the number of records with a non-empty value for it = the number of answer rows stored for it | `D5: 400 sent, 399 stored` |

If any check fails, the load raises "`<path>` does not match its payload" with the first five problems, and the failure handling in Section 7 takes over.

### 5.2 What the checks catch

- A record that was not written (check 1).
- A question Forsta added that the transformation did not understand, so it never became a field (check 2).
- A value that could not be stored under its field's rule, for example text in a numeric field or an impossibly large number. Transformation stores no row for it, so the counts differ (check 3). The wave fails instead of loading with a hole in it.
- Any bug that loses, duplicates or misroutes answers (check 3).

### 5.3 What the counts do not prove, and the second check that does

Counts prove that every value arrived, not that every value is right. A wrong code would pass a count check. That is why, after each run that loaded a wave, the pipeline also compares every **value** with Forsta (Section 10). The two checks together cover "everything arrived" and "everything is correct".

## 6. After verification: making the wave visible

Once verification passes:

1. List rows the questionnaire no longer lists and that nobody chose are removed (Part 3, Section 6.5).
2. The derived steps run (profiles, bases, harmonisation, cube, search, line-by-line, serving; Parts 4 and 6).
3. The audit row is closed with status `success`, rows read and rows loaded.
4. The wave is set to **`verified`**. From this moment it is visible on the portal.
5. The register marks the survey `loaded`, records its `survey_id` and load time, resets its failure counter, and writes an event row.
6. The survey calendar is rebuilt, because the wave's questions may now reveal a seasonal tracker.
7. Waves that compare against this one (the next week, and the same week next year) get their serving rows rebuilt, so their "vs last week" and "vs last year" figures now include it. A failure there is logged and never fails this wave.

## 7. Failure handling

### 7.1 What happens when a load step fails

Any error from step 3 onward is caught, handled, and then raised again so the run records it:

1. The audit row is closed with status `failed`, the rows read and written so far, and the error text (up to 2,000 characters).
2. **The "intact" rule decides the wave's status:**
   - If transaction A never committed (`written` is still empty) **and** the wave was already `verified` from an earlier load, its old facts were never touched. It goes back to **`verified`**, and people keep seeing last load's data.
   - Otherwise the wave becomes **`failed`**, and its serving rows are deleted, so no screen or published file keeps numbers for answers that are no longer there.
3. The register marks the survey `failed`, stores the error (up to 1,000 characters), adds 1 to its consecutive-failure counter, and records an event.
4. The run moves on to the next due wave.

### 7.2 Retries

| Rule | Value |
|---|---|
| Retry a failed wave automatically | Yes, in each following run |
| Maximum consecutive failures before automatic retries stop | 3 |
| After that | It waits for a person to run `python -m etl.forsta_etl --survey <path>` |
| Counter reset | On the next successful load |

### 7.3 Who is told

- A **failure email** for each wave that did not load, with its stored error. Failure emails go only to the private failure list in `config/notify.yml` (internal error details), never to the team list or the CC address.
- The same failure subject is emailed **at most once every 6 hours**, because runs happen every 30 minutes. A different problem (a different subject) is emailed at once. The repeat window starts only once an email really went out, so a failed send never silences an alert.
- The run exits with code **1**.

### 7.4 Failure cases at a glance

| Where it fails | Wave status afterwards | Visible data |
|---|---|---|
| Download from Forsta fails (before the wave row is touched), wave verified before | `verified` | Last load's data, unchanged |
| Download from Forsta fails on a first load | No wave row yet; the register shows `failed` | None |
| Questionnaire step fails, wave verified before | `verified` | Last load's data, unchanged |
| Questionnaire step fails on a first load | `failed` | None |
| Transaction A rolls back (for example a MySQL warning) on a wave verified before | `verified` | Last load's data, unchanged |
| Verification finds a difference | `failed`, serving rows removed | None until the next successful load |
| A derived step fails after verification | `failed`, serving rows removed | None until the next successful load or heal |

## 8. Reloads and idempotency

A wave is reloaded when Forsta closes a wave that was loaded early, when a survey is reopened, when a failed wave is retried, or by hand. A reload is safe because:

| Layer | What a reload does |
|---|---|
| Wave row | Same row, same `survey_id`, same wave label (protected by the audit log's `forsta:{path}` entry, Part 2) |
| Questionnaire | Updated in place; nothing duplicated; unlisted, unchosen rows removed after verification |
| Respondents | Updated in place by record number; anyone no longer in Forsta removed |
| Answers | Fully replaced inside transaction A |
| Demographic profiles | Rebuilt |
| Concepts | Units already linked (confirmed, proposed or rejected) are left alone; only new units are decided |
| Cube, search, line-by-line, serving | Deleted and rebuilt for the wave |
| Waves that compare with it | Their serving rows rebuilt |

The code's own description of the loaders: everything is idempotent; re-running a load for the same wave updates in place rather than duplicating, so a failed run can simply be re-run.

## 9. Concurrency: one writer at a time

### 9.1 The run lock

Every job that writes (the scheduled run, a hand-run load, a rebuild, a publish, the China loader, the respondent rekey) first asks MySQL for a named lock, **`cip_etl`** (`GET_LOCK`).

- If the lock is free, the job holds it for its whole run.
- If another job holds it, the new job stops at once ("Another CIP run holds the lock"). A scheduled check every 30 minutes simply finds the lock taken while Monday's watch runs, and stops.
- A container restart's publish restore may queue for the lock (up to 6 hours) instead of stopping.
- The lock belongs to the database connection. If a job is killed, its connection closes and the lock is released automatically. No stuck lock needs clearing by hand.
- The lock's connection is told not to time out for 7 days (the server normally drops idle connections after 8 hours), and Monday's 54-hour watch pings it every cycle.

The code records why the lock exists: two writers at once deadlocked on 20 October 2026.

### 9.2 Other protections

- **Serving builds** run at the "read committed" isolation level, so building one wave does not block building another, and are retried up to 3 times with a short growing wait on MySQL's lock-timeout and deadlock errors (1205, 1213).
- **Mapping decisions** use a conditional update ("only if still proposed"), so two analysts deciding the same proposal at once cannot both win.

### 9.3 Database roles

The code connects with two roles: `etl`, which writes, and `app`, which the portal and API use to read. Only the ETL role uses bulk upload. The README states the rule: the portal reads; only the ETL writes.

## 10. Reconciliation: comparing every value with Forsta

### 10.1 When it runs

- **After every run that loaded something:** for each wave loaded in that run.
- **On demand, for every Forsta wave:** `python -m etl.forsta_etl --reconcile`.
- **On demand, for every wave of every platform:** `python scripts/reconcile.py` (or `--wave <label>` for one). Qualtrics and SurveyMonkey waves are compared with the old warehouse tables they came from. A wave loaded from a one-off export has no source left to compare against.

### 10.2 How it works

1. Every stored answer of the wave (respondent `uuid`, field, code, label, number, text) is copied into a small temporary SQLite file on the server, indexed by respondent. This keeps memory low even for wide annual surveys, and the file is deleted afterwards.
2. The wave's data is downloaded from Forsta again, streamed record by record.
3. For each value in each record, the pipeline works out what **should** be stored, using exactly the same rule as the load (Part 3, Section 9), and compares it with what **is** stored for that respondent and field:
   - codes must be equal; or
   - labels must be equal (for values that are not whole numbers); or
   - numbers must be equal at 4 decimals; or
   - texts must be equal, character for character.
4. Every comparison is counted. Up to 200 differences are listed, each with the respondent, field, Forsta's value and the stored value.

### 10.3 Results and what counts as a pass

| Result | Meaning | What the run does |
|---|---|---|
| Values checked, 0 differences | Pass | Nothing |
| Differences found | Fail | Reported in the integrity email: "survey X: n of m answers differ from Forsta", with the first three |
| Nothing could be compared (for example the survey has since hibernated and Forsta answers 428) | **Not a pass** | Reported: "no answer could be compared with Forsta" |

The project's documentation records a full reconciliation on 8 October 2026: 31 Forsta waves, 4,476,153 answers, 0 differences.

## 11. The integrity check: is the whole database healthy?

`etl/integrity.py` runs after every scheduled run that loaded or failed something, and in Friday's run even when nothing changed. Each check is cheap (the code notes 4 seconds or less on a database of 23 million answers). Checks come in four kinds:

| Kind | Meaning | What happens |
|---|---|---|
| **derived** | A verified wave is missing rows the ETL derives | **Healed automatically** by rebuilding them |
| **orphan** | A derived or index row points at something deleted | **Healed automatically** by deleting it |
| **base** | Something in the loaded data itself is wrong | **Never touched automatically.** Reported, so a person decides |
| **watch** | A survey the database does not hold and the pipeline cannot fetch by itself | Logged as a warning every run; never fails the run |

### 11.1 Every check

| # | Kind | Check | Fix |
|---|---|---|---|
| 1 | derived | A verified wave with reportable questions but no cube cells | Rebuild the cube |
| 2 | derived | A verified wave missing from search | Rebuild its search rows |
| 3 | derived | A verified Forsta tracker wave without line-by-line rows | Rebuild its lines |
| 4 | derived | A recently served wave whose serving row count differs from its reportable cube cells (newest 20 checked) | Rebuild its serving rows |
| 5 | orphan | Line-by-line row whose respondent is gone | Delete |
| 6 | orphan | Search row of a deleted wave | Delete |
| 7 | orphan | Search row of a deleted question | Delete |
| 8 | orphan | Search row of a deleted concept | Delete |
| 9 | orphan | Calendar row of a survey not in the register | Delete |
| 10 | base | Line-by-line row of an unqualified respondent or another wave's respondent | Report |
| 11 | base | Register row pointing at a wave that does not exist | Report |
| 12 | base | Register says `loaded` but the wave is not `verified` | Report |
| 13 | base | A wave stuck in `loading` | Report |
| 14 | base | A verified wave with no qualified respondents | Report |
| 15 | base | The same Forsta `uuid` twice in one wave | Report |
| 16 | base | The same panelist (same respondent key) qualified twice in one wave | Report |
| 17 | base | A closed Forsta survey still not loaded after 3 days | Report |
| 18 | base | A demographic profile filed under a different wave than its respondent | Report |
| 19 | watch | A closed survey hibernated before it was loaded: reactivate it in Forsta, the next run loads it | Warn |
| 20 | watch | A survey no longer listed by Forsta, never loaded, and not only ever in testing: ask Forsta to restore it | Warn |
| 21 | plan | A tracker week the data team planned (`config/launch_schedule.yml`) still not in the portal 4 days after its Monday (looking back 8 weeks) | Report |

Check 21 compares against the team's plan, not every Monday, because the tracker ran fortnightly in parts of 2024 and 2025.

### 11.2 How healing is limited and confirmed

- At most 20 waves are rebuilt per check per run, so a large gap heals over several runs instead of making one run very long.
- After healing, the check runs again. If the problem is still there, it is reported as "still wrong after healing".
- If a heal itself fails, the error is reported with the check.

### 11.3 Result

Whatever is still wrong is listed in one integrity email, with the number of problems in the subject, so a new kind of problem is not hidden by the 6-hour repeat window. If nothing failed to load but integrity problems remain, the run exits with code **5**.

The check can also be run by hand: `python -m etl.integrity` (check and heal) or `python -m etl.integrity --check` (report only, change nothing).

## 12. Publication drift: have numbers we already published moved?

Coresight's reports quote numbers. A **publication** in CIP is a frozen record of such numbers: its definition (which concept, which waves, which cohort, which cut, pooled or wave by wave, minimum base) and the cells it gave on the day it was published (`cip_publication`, `cip_publication_cell`).

At the end of every run in which no wave failed, the pipeline recomputes every publication from today's data using the same single function that produced it, and compares cell by cell:

| Status | Meaning |
|---|---|
| same | Within a tolerance of 0.0005 for proportions and averages; counts must be exact |
| moved | The value changed, or crossed the minimum base either way |
| missing | A published cell can no longer be computed |
| new | A cell exists today that was not published |
| error | The definition no longer resolves |

If any publication has a moved, missing, new or error cell, the team is emailed the summary and the run exits with code **3**. This replaces the analysts' manual "Cross-Check" tab. `python -m etl.publications --drift` runs it by hand.

## 13. Where to look: the load's records

| Record | Contents |
|---|---|
| `cip_survey.load_status` | `loading`, `verified` or `failed` for each wave. Only `verified` is shown |
| `cip_forsta_survey` | Each Forsta survey's load state, `survey_id`, load time, last error and consecutive failures |
| `cip_forsta_event` | Every observed change of state over time |
| `cip_load_log` | One row per load attempt: source, reference, rows read, rows loaded, rows rejected, status (`success`, `partial`, `failed`), error text, start and finish time |
| `logs/forsta-etl-errors.jsonl` | Every warning and error, one JSON line each: run, step, error type, traceback; secrets masked |
| `logs/etl-heartbeat.json` | The last sign of life and the promised next one, read by the hourly watchdog |
| Exit code of each run | 0 fine, 1 a wave failed, 2 key or schema problem, 3 a published number moved, 4 database unreachable, 5 integrity problem not healed |

## 14. Summary

Loading in CIP writes a wave in a strict order. The wave is first hidden. Its questionnaire is written in place. Then its respondents and answers are replaced together in one transaction, using a bulk upload that fails on any database warning so no value can be changed silently. Before anyone can see the wave, verification proves that every respondent, every question variable and every value Forsta sent is stored. Only then are the derived tables built and the wave made visible. If anything fails, a wave that was fine before keeps its old data, a new or broken wave stays hidden, the error is recorded and emailed, and the next runs retry it up to three times. Reloads are always safe because every write is keyed on Forsta's own identifiers. One lock ensures a single writer. After each run, every loaded value is compared with Forsta a second time, an integrity check heals what can be rebuilt and reports the rest, and every number Coresight has already published is recomputed to confirm it has not moved.

**Part 6** explains what is built on top of verified data: the cube, the serving tables with their week-on-week and year-on-year comparisons and significance flags, the line-by-line file, the search index, the published files, the reports, and the emails.
