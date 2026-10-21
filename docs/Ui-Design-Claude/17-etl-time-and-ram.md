# 17 — ETL time and RAM per survey (measured 21 Oct 2026)

Question from the owner: *if surveys are posted every day or week, how long does the ETL take per survey and per day, how much RAM does it use, and how well optimised is it?*

**Short answer**
- **One weekly CSI-US wave takes about 2 minutes when the ETL runs on this Mac against Azure** (median 120 s across the load stages, range 61–532 s). Add about 30 s of post-load steps and about 50 s for the notification email, so **3–3.5 minutes from start to inbox**.
- **The same wave takes 12–17 s against a local MySQL.**
- **Time figures come from STG (Azure `cip_stg`) evidence:** the ETL's own stage log and read-only SELECTs. **RAM has never been measured on an STG run**; the RAM figures below come from local runs (see the note under "How it was measured").
- **Peak RAM is 180–210 MB for a weekly wave and 280–370 MB for the largest annual survey** (2,261–2,265 respondents, 468–675k answers). Loads run one at a time, so RAM does not grow with the number of surveys per day.
- **Most of the Azure time is network round trips and Azure server time. Python's own CPU work is small** (2–7 s of user CPU per load).

## How it was measured

| Source | What it gave |
|---|---|
| `logs/forsta-etl.log`: the `seconds {...}` dict that `load_survey`'s `lap()` writes (`etl/forsta_etl.py:212-268`) | Per-stage timings for 43 real Azure loads. 42 of them come from the 20–21 Oct run (23:00 → 00:59) and include the serving stage. |
| `cip_load_log` and `information_schema` on Azure `cip_stg` (read-only SELECTs and one EXPLAIN) | Load durations, answer, question and cell counts per wave, table sizes, server variables |
| *(Supplementary)* Local runs: `/usr/bin/time -l` around `load_survey`, against a new database `cip_etl_bench` in the `cip-mysql` container (port 3307), using the real Forsta API (GET only) | Wall time, per-stage time and max RSS. Cube cell counts matched Azure exactly (14,639 and 12,425 cells). |
| A pymysql hook that counts `_execute_command` calls per stage | Database round trips per stage, which gives the network cost at the measured 287 ms RTT |

> **Note on local runs.** These ran before the owner said not to test locally. No further local tests were run after that. They are kept only because they are the sole RAM measurement and the only per-stage round-trip count. The STG run proposed below would replace them. The local database `cip_etl_bench` is still in the `cip-mysql` container, waiting for the owner's decision on whether to drop it.

The local database holds the real schema plus copies of `cip_topic`, `cip_concept`, `cip_concept_option` and `cip_cohort_def`, taken read-only from Azure. Local MySQL has `local_infile=0`, so local runs used the batched-INSERT fallback. Azure has `local_infile=1` and uses `LOAD DATA`.

## Per-stage time: one weekly CSI-US wave

The wave is 261001 (19 Oct 2026): 693 respondents, 400 qualified, 128,665 answers, 70 questions and 348 fields.

| Stage | Azure from Mac, median of 42 loads (s) | Azure p90 / max (s) | Local MySQL, 3 runs (s) | DB round trips | Bytes sent |
|---|---:|---:|---:|---:|---:|
| fetch (Forsta API) | 2.7 | 3.4 / 6.5 | 3.0–3.9 | – | – |
| definitions | 9.3 | 9.8 / 20.1 | 0.1–0.2 | 19 | 0.06 MB |
| write (respondents + answers) | 21.5 | 36.8 / 165.9 | 3.0–5.6 | 35 | 8.7 MB |
| verify | 1.7 | 2.2 / 6.3 | 0.0–0.1 | 5 | – |
| profiles + question bases | 10.2 | 11.4 / 36.8 | 0.2–0.4 | 27 | 0.16 MB |
| harmonise | 6.7 | 9.1 / 24.1 | 0.1–2.3 | 10 | – |
| cube (`cip_agg_cell`) | **30.9** | 43.4 / 203.4 | 2.0–2.9 | 55 | – |
| search | 3.4 | 4.1 / 15.8 | 0.0 | 9 | – |
| tracker_line | 12.8 | 37.9 / **123.8** | 0.3–0.4 | 11 | 2.3 MB |
| serving (`srv_*`) | 16.0 | 20.1 / 49.0 | 1.4–1.7 | 18 | 2.0 MB |
| **Total of the stages** | **120** | – / 532 | **11.6–16.1 wall** | 242 (+36 setup) | 13 MB |
| post steps (calendar rebuild + dependants) | ~27 (gap between loads) | 7–102 | <1 | 17 | – |
| notify email with crosstabs | ~47–53 | – | not run | – | – |

How to read the Azure numbers:
- **Round trips:** 242–297 per survey × 287 ms comes to about **70–85 s**.
- **The rest is Azure server time.** Cube runs 28 aggregate statements over temporary tables, and tracker_line runs a DELETE. Azure's `innodb_buffer_pool_size` is 2 GB, while the hot tables are about 8.5 GB (`cip_answer` alone is 5.3 GB and 23.8 M rows). A plain `COUNT(*)` of one survey's answers took 5.0 s on Azure.

## Peak RAM (max resident set size, `/usr/bin/time -l`)

| Load | Respondents | Answers | Wall (local) | Max RSS |
|---|---:|---:|---:|---:|
| CSI-US 261000 (first load) | 595 | 147,635 | 16.1 s | 194 MB |
| CSI-US 261001 | 693 | 128,665 | 11.6 s | 209 MB |
| CSI-US 261001 (reload, repeat) | 693 | 128,665 | 13.8 s | 191 MB |
| Holiday Shopping 260905 (annual) | 2,261 | 675,032 | 46.0 s | 367 MB |
| Amazon Apparel 260401 (annual) | 2,265 | 468,295 | 28.8 s | 292 MB |
| `app.data.cube` alone, wave 261001 (×2) | – | – | 1.4 / 1.5 s | 63 MB |
| `python -m etl.serving --wave` alone (×2) | – | – | 0.94 / 0.91 s | 102 MB |

RAM grows by roughly **0.25 KB per answer** on top of a base of about 150 MB. The cause is the full payload (`records`) and the list of answer-row dicts that `_write` builds (`etl/forsta_etl.py:316-322`). A 1 M-answer survey would need about 400 MB.

## Per-survey and per-day estimates

| Scenario | Size | ETL on Mac → Azure (today) | ETL inside Azure (≈1 ms RTT), estimated | Local DB (measured) | RAM |
|---|---|---:|---:|---:|---:|
| Weekly tracker wave | ~400 qualified / ~600 total, ~60–80 questions, ~130k answers | **~2 min** load; **~3.3 min** with post steps and email | **~45–60 s**: round trips fall from ~70 s to under 1 s, server time stays | 12–17 s | ~200 MB |
| Large annual survey | ~2,260 respondents, 470–675k answers | **3.5–9 min** (212 s for 511; 452–532 s for 262 and 494) | **~2–5 min**: server-bound (cube, write) | 29–46 s | 290–370 MB |
| "Daily", N surveys/day, sequential as today | N weekly-sized waves | **N × ~3.3 min** + ~35 s per run (connect, register, integrity). 10/day ≈ 35 min; 50/day ≈ 3 h | N × ~1–1.5 min. 50/day ≈ 1 h | N × ~15 s | flat ~200–370 MB (one at a time) |
| Real batch, 20–21 Oct | 42 waves loaded + 1 failed + 43 emails | **2 h 33 min**: loads 119 min (sum of stages 98 min), emails 34 min. About 3.6 min per survey | – | – | – |

What changes in production:
- **Round trips** (about 60% of today's time) drop to almost nothing once the ETL runs inside Azure.
- **Server-side time** (cube, write, tracker_line, serving) stays, and it grows as `cip_answer` grows (about 45 MB per weekly wave across all tables) unless the buffer pool grows with it.
- **Network-sensitive stages:** definitions, profiles and search each cost about 9–10 s from the Mac but under 0.5 s locally. They are round-trip bound and will almost disappear.

## Biggest optimisation opportunities

| # | What | Where | Evidence | Expected gain |
|---|---|---|---|---|
| 1 | **Run the ETL next to the database.** Use an Azure VM, container or job in the same region instead of the Mac over VPN. | ops, no code | 242–297 round trips × 287 ms ≈ 70–85 s per survey | **About −60% per survey: ~120 s → ~45–60 s for a weekly wave** |
| 2 | **Stop the tracker_line full scan.** `DELETE FROM cip_tracker_line WHERE survey_id = :s` has no index starting with `survey_id`; the only one is `KEY ix_line_wave (wave_date, survey_id)`. The DELETE also runs for non-tracker waves, which then write nothing. Fix: check the family before the DELETE, and delete by `(wave_date, survey_id)` or add `KEY (survey_id)`. | `etl/tracker_line.py:54-55`, `sql/001_schema.sql:757` | 67.8 s on Azure for annual wave 494, which writes 0 lines. Weekly median 12.8 s, max 123.8 s. Locally 0.0–0.4 s. | **−10 to −120 s per survey** |
| 3 | **Cube in 2 statements per cohort instead of 14.** Today there is one INSERT…SELECT per cut × {single, multi} (`CUBE_DIMS` has 7 cuts), and each one rescans `cip_tmp_cube`. Unpivoting the 7 cuts with a small derived table gives one pass each for single and multi. Also, serving's `store_answers` runs the 6-table `ANSWER_ROWS` join twice more; it could read the cube's temporary table instead. | `app/data/cube.py:149-153`, `app/data/cube.py:112-118`, `etl/serving.py:178-189` | Cube is the largest Azure stage (median 30.9 s, max 203 s; 55 round trips) | **Likely cube ~31 s → ~8–12 s; serving ~16 s → ~8 s** |
| 4 | **Do the per-run work once per run, not once per survey.** `survey_calendar.rebuild()` rereads every question of every wave after each load, and `rebuild_dependants` rebuilds neighbouring serving rows. In a backfill or a daily batch, run both once at the end; `serving.build_all(jobs=4)` already exists. Notify takes ~47–53 s per survey (stats queries and crosstab attachments) and could run in parallel or as one digest. | `etl/forsta_etl.py:280-281`, `etl/notify.py:100-140` | ~27 s gap between loads; 43 emails took 34 min | **−25 s per survey in batches; −30 min for a 40-survey batch** |
| 5 | **Parallel loads and a bigger buffer pool.** Loads are sequential, and on the Mac they are mostly waiting on the network. 3–4 workers would cut a batch about 3×, at about 200–370 MB RAM each (watch for 1213 deadlocks, which `serving.build_wave` already retries). Separately, a 2 GB buffer pool against about 8.5 GB of hot tables explains the write outliers (138–166 s) and the slow cube. | `scripts/weekly_forsta.py`; Azure server tier | Write median 21.5 s vs 166 s max; one COUNT took 5 s cold | **Batch ≈ 3× faster; fewer outliers** |

Smaller items:
- **Memory:** `_write` could stream answer rows straight into the `LOAD DATA` TSV file instead of building a list of dicts (`etl/forsta_etl.py:316-323`, `355-357`). That saves about 100–150 MB on the largest surveys. RAM is not a constraint today.
- **Fresh-install bug, found while measuring:** `sql/001_schema.sql:759` has an unescaped apostrophe (`'The data team's line-by-line …'`), so `schema_upgrade.install()` fails on an empty database. The benchmark used a patched copy in scratch; the repository file was not changed.

## Proposed STG measurement run (needs owner approval, not run)

To get time and RAM measured on STG itself, reload one recent weekly wave with the RSS meter on:

```bash
cd /Users/mohdsaeedafri/All-Code-Base/consumer-insight-portal
/usr/bin/time -l .venv/bin/python -m etl.forsta_etl --survey selfserve/58f/261001   # survey_id 415, wave 2026-10-19
```

- **What it measures:** the `seconds {...}` stage line in `logs/forsta-etl.log`, the `cip_load_log` duration, and "maximum resident set size" from `time -l`. Run it twice to see the variance.
- **What it writes:** it is a write to `cip_stg`. It reloads wave 415 in place: the wave is marked `loading`, its answers, cube, tracker lines and serving rows are deleted and reinserted, and the wave is marked `verified` again. While it runs (about 2 min), readers see the wave as loading.
- **Forsta:** GET only.
- **Notify:** the command does not send the email. That step belongs to `scripts/weekly_forsta.py`.
- **For an upper bound, also run:** `selfserve/58f/260905` (survey_id 262, 2,261 respondents, 675k answers), with the same command.

## Limits of these numbers

- RAM comes from local runs only. No STG run has measured RAM yet; see the proposed run above. Python's memory does not depend on the database's location, apart from the result sets it reads back, so the local RSS should be close to what an STG run shows.
- Local runs used MySQL 8.0.46 in Docker on an Apple-silicon Mac with a 2 GB buffer pool and only 2–5 waves loaded. Azure holds about 370 waves, so local server time is a lower bound.
- Local runs used batched INSERTs, not `LOAD DATA`. Locally that makes little difference; on Azure `LOAD DATA` was measured at 14 s vs 36 s for wave 412.
- Harmonise ran against copied concepts but not against `cip_concept_map` (about 90k rows), so its local timing is optimistic.
- "Inside Azure" figures are estimates: Azure stage time minus round trips × RTT. They were not measured on an Azure host.
- Notify and crosstab emails were not run locally. Their cost comes from log timestamps only.
- Azure stage timings come from a single batch on one night (20–21 Oct), when the server was busy with back-to-back loads. A lone weekly load, such as 261001 on 20 Oct, took 87.5 s for its stages (before the serving stage existed). The `cip_load_log` duration for the same wave was 81 s.
- Nothing was written to Azure `cip_stg` or `dwh_stg`, and Forsta was read with GET only. The benchmark database `cip_etl_bench` is left in the local `cip-mysql` container.

## Addendum: measured run on STG, approved 21 Oct 2026

Wave 415 (`selfserve/58f/261001`, 19 Oct 2026, 693 respondents, 12,425 cube cells) was reloaded twice into Azure `cip_stg` with `/usr/bin/time -l`. Forsta was read with GET only, and no email was sent.

| | Run 1 | Run 2 |
|---|--:|--:|
| Wall time | **150.0 s** | **136.7 s** |
| CPU time (user + sys) | 2.4 s | 2.4 s |
| Peak RAM (max resident set) | **179 MB** | **184 MB** |

Seconds per stage, from the ETL's own log:

| Stage | fetch | definitions | write | verify | profiles | harmonise | cube | search | tracker_line | serving |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| Run 1 | 3.9 | 13.4 | 23.6 | 1.4 | 9.3 | 5.8 | 28.4 | 3.4 | **35.7** | 13.5 |
| Run 2 | 3.0 | 12.9 | 15.3 | 1.4 | 10.8 | 4.8 | 27.9 | 3.4 | **33.8** | 12.1 |

**What this confirms:**
- **Over 98 % of the time is waiting on Azure.** Python's own CPU is 2.4 s, so the network and the database decide the speed.
- **tracker_line is the slowest stage, at about 35 s.** It is the missing `survey_id` index on the delete (fix 2 above).
- **RAM is about 180 MB per load.** A daily load of N surveys, run one at a time, still peaks at about 180 MB.
- **Per day, measured on STG:** about 2.4 min per weekly survey, so 10 a day is about 25 min and 50 a day is about 2 h. Running the ETL inside Azure and the fixes above would bring a weekly survey to about 1 min.
