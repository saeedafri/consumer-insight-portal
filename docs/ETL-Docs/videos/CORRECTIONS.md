# Corrections to the six ETL videos (checked 15 November 2026)

The six videos in this folder were rendered on 15 November 2026 (10:21 to 10:38) from an earlier copy of the
Part 1 to 6 notes. Their narration and slides were transcribed and checked against the code and the corrected notes
(`../CIP-ETL-Part-*.md`). The statements below are wrong or out of date in the videos; the notes are correct.
Re-render the videos from the corrected notes to remove them. Times are minutes:seconds into each video; "slide"
means the text is on screen, otherwise it is spoken.

## Part 1, The Pipeline End to End (15:26)

| Time | The video says | Correct |
|---|---|---|
| 02:13 | A wave whose counts disagree with Forsta "stays hidden in loading status" | It is marked `failed` (hidden), and the failure list is emailed |
| 02:43 | A wave is labelled "by the Monday of its launch week" | By the Monday of the week of the earliest qualified complete |
| 03:12; slide 15:24 | The data export is "two megabytes" | About 5 MB with every status (5.1 MB for survey 261003); 2 MB would be qualified only |
| 04:57; slide 15:24 | "373 verified waves" | 523 on 15 Nov 2026: 374 US and other studies plus 149 China weeks |
| 05:06 | "The API and web portal only read" | Survey data is written only by the ETL; the API writes its own working tables (sign-in, alerts, boards, saved views, access, dashboards) |
| 08:00 | A tracker loads early when "any of three conditions" holds | Any of four: 400 qualified, every quota cell full, one whole quota sheet full, or 9 hours after launch |
| 09:28; slide 10:00 | Step 3 skips "any survey with three consecutive failures" ("<3 fails") | After 3 failures in a row a wave is retried every 6 hours, and once more when Forsta closes it; waves still open in Forsta load first, then closed ones oldest first |
| 09:47; slide 10:00 | "Monday through Thursday", an idle run exits; "1 API + 2 small DB" | Any idle run exits except the first idle check of a Friday; an idle run still reads the survey list, live quotas and Forsta's fieldwork records |
| 11:42 | Stage 1 streams "the data map and the full data array" to disk | The datamap is read into memory; only the respondent records are streamed to the disk snapshot |
| 13:31 | Stage 10 refreshes the search entries the portal's search box uses | `cip_search` is kept for the integrity check; the search box builds its own index in memory |
| 14:28; slide 15:24 | "Broken surveys stop retrying after three failures" ("3-strike cap"); "4 tries (2s-60s wait)" | Retried every 6 hours after 3 failures; Forsta requests wait 2, 4 and 8 seconds between the 4 tries |
| 14:48; slide 15:24 | Panel IDs are always HMAC-hashed with a secret salt | Keyed (HMAC) when `CIP_RESPONDENT_SALT` is set, otherwise a plain SHA-256 fingerprint |
| 14:57; slide 15:24 | The watchdog alerts "if any run stalls past three hours" | The run promises a sign of life within 3 hours; the alarm comes when that promise is 60 minutes late (checked hourly, so about 4 hours) |

## Part 2, Extraction (11:51)

| Time | The video says | Correct |
|---|---|---|
| 01:40 | A rejected key "emails the team" | Emails the private failure list |
| 01:53 | Retries wait "from 2 to 60 seconds" | 2, 4 and 8 seconds (60 is a cap never reached with 4 tries) |
| 02:38 | A quiet run is "one survey list call plus quick quota checks" | It also refreshes Forsta's fieldwork records (company records every run, loaded live surveys, up to 10 missing a record) |
| 04:14 | An annual study collecting 50 more responses "triggers an automatic refresh" | It stays loaded while live; it is reloaded when Forsta closes it again (new close date) |
| 06:06 to 06:52; slide 07:04 | "Three-strike circuit breaker": after 3 failures the wave "waits for an engineer" ("Removed from auto retry") | After 3 failures it is retried every 6 hours, and once when Forsta closes it; the failure email gives the time of the next try and the command to load it at once |
| 06:23 | "Waves run oldest close date first" | Waves still open in Forsta first, then closed ones, oldest first |

## Part 3, Transformation: Questionnaire and Answers (11:44)

| Time | The video says | Correct |
|---|---|---|
| 00:35 | "500 interviews" become about 151,000 rows | A weekly wave of about 400 qualified respondents and 375 columns |
| 07:30 | The panel ID is always hashed again with HMAC and a server secret | Only when `CIP_RESPONDENT_SALT` is set; otherwise the plain SHA-256 fingerprint |
| 10:28 | "13,000 rows" took 18 seconds | 13,000 serving-table rows (the code's measurement) |
| 10:57 | China files "and historical Excel exports" deliver text labels | China and the one Qualtrics Excel export do; the Qualtrics and SurveyMonkey history from the old warehouse is copied with its codes |

## Part 4, Transformation: Business Logic (11:04)

| Time | The video says | Correct |
|---|---|---|
| 01:14 and 07:58 | "Across 20 years" of questionnaires; Q13 meant footwear "one month" and Cyber Monday the next | CIP's data starts on 18 January 2018; Q13 changed from one week to the next |
| 01:41 | China's config entries are "S1 through S4" | S1 to S4, plus Q8 and Q9 for the two outlooks |
| 09:19 | The 21 and 28 September test "yielded 1,769 clean concepts" | 0.796 was the highest score between unrelated questions in that test; 1,769 is the number of concepts in the database on 21 Oct 2026, a separate figure |
| 10:10 | Editing a cohort rule "automatically" recomputes members and cube cells | A new version is created and the old one's members and cells are deleted; members are re-derived at each wave's load, and for past waves by `python -m etl.cohorts --sync` (which fails today: it looks for its settings file one folder too high) |

## Part 5, Loading and Verification (10:17)

| Time | The video says | Correct |
|---|---|---|
| 00:44 and 02:28 | Stage timings are saved in `cip_load_log` | The seconds per stage go to the run's log; `cip_load_log` holds rows read, rows loaded, status, error and times |
| 03:14 | The answer file sizes "the searchable text prefix to 1500 characters" | No such limit exists; typed answers are stored in full |
| 05:55; slide 06:16 | "Three straight errors pause auto-retries" ("3-fail cap") | After 3 failures in a row, retried every 6 hours, and once when Forsta closes the wave |
| 06:39; slide 07:32 | "app user: strict READ ONLY"; the portal API runs with read-only credentials | Three roles: `etl` (survey data), `api_write` (the API's own boards, saved views, alerts, access log) and `app` (reads and publishing) |
| 07:14; slide 07:32 | `--survey` "overrides the three-strike pause" | There is no permanent pause any more; `--survey` loads a wave at once |
| 07:48 to 08:16; slide 08:48 | Reconciliation writes Forsta's fresh answers into SQLite, then streams the stored rows from MySQL | The other way round: the stored answers are copied into a temporary SQLite file, then Forsta's data is streamed and each value compared |
| 09:00 | The integrity engine inspects 23 million rows "in under 4 seconds" | Each check takes 4 seconds or less |
| 09:41; slides 08:52 and 10:12 | "21 integrity checks"; checks 19 to 21 include schedule delays | 22 checks since 15 Nov 2026: 19 to 21 are watch checks (including the new "hibernated before its final reload"), 22 is the plan check (a planned week not in the portal 4 days after its Monday) |
| slide 10:12 | Exit code 5 = "unhealed integrity defect" | Also when the second comparison finds answers that differ from Forsta, or could compare none |

## Part 6, Derived Data, Serving and Publishing (9:21)

| Time | The video says | Correct |
|---|---|---|
| 00:32 | "Every heavy calculation runs at publish time" | The cube and serving tables are built during each wave's load; publishing writes them out as files |
| 03:24 | `srv_answer` saves "respondent bit sets" | The bitsets are in the published `people` files; `srv_answer` holds each qualified answer with its cuts |
| 04:22 | A "95 % ... z-test" decides significance | The z-test gives each row a p-value; the Benjamini–Hochberg correction at 5 % decides which rows are significant |
| 05:34 | `cip_search` makes "typing a keyword anywhere in the portal" return matches | The portal's search box uses an index the API builds in memory; `cip_search` is kept for the integrity check |
| 06:51 | Rebuilding the whole history "takes 16 minutes" | 6 minutes at full CPU, measured on 5 Nov 2026 (16 is an older note) |
| 07:14 | The gates check that "zero files are empty or truncated" | The gates open the picker, every book and every bitset file; other files are not opened |
| 07:20 | If a gate fails "the team receives an alert" | The private failure list is emailed |
| 08:18; slide 09:16 | "US & China" weekly reports matched the 3 Nov 2026 PDF | The US report was checked against the 3 Nov 2026 report; the same engine builds the China report |
| 08:50; slide 09:16 | A "30-minute watchdog" alerts if a closed wave waits over 30 minutes | The 30-minute check loads closed waves; the watchdog runs hourly and alerts when a run stopped (about 4 hours after its last sign of life) or no check ran for 2 hours past the promised time |
