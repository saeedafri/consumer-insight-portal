# CIP state machines: live state and verification (15 Nov 2026)

**What this is.** A re-check of the 32 state machines from the 15 Nov audit, after the fixes in `b831980` and the
commits that followed (cip-test HEAD `68de3f4`). For each machine: its current state on staging, whether each earlier
finding is really fixed (code, tests, live data), and what is still open, with proof. Written by Claude (Opus 5.5) on
15 Nov 2026, about 16:20-16:45 IST.

**Nothing was changed.** No code, no data: every database session was switched to read-only before it ran a query.
I also did not sign in to staging, because a sign-in writes a session row and an audit row on a system the team uses.

## Read this first

- **12 of the 13 earlier findings are fixed, tested and deployed.** The 13th, two "loaded" messages for each early-loaded
  wave, is waiting on your decision, as `status/README.md` already says. The Save view double-post that turned up
  while fixing is fixed too.
- **The fixed code has 4 open issues, each reproduced by a test** (Appendix B). Two are in the new Monday watch, which
  runs for real for the first time tomorrow, **Mon 16 Nov at 17:30 IST** (12:00 UTC).
- **Staging's live state is healthy.** All 523 waves are `verified`. No run is stuck `running`. No Forsta survey is
  `failed` or `due`. All 21 integrity checks pass. The one published publication still reproduces exactly.
- **Outside the state machines:** the staging env files are committed and pushed to GitHub `origin/master`. They hold
  the live database passwords, the session secret, the admin token and the Forsta key. Rotate those secrets (§7).

## Follow-up, same day (after this report)

- **N1 to N4 fixed**, each with a regression test that fails without its fix (the Appendix B reproductions, inverted):
  - N1: a watch check that finds the lock taken still reads the week (`scripts/weekly_forsta.py watch`);
    `tests/test_pipeline_hardening.py::test_a_watch_check_that_finds_the_lock_taken_still_sees_the_wave_in`.
  - N2: `main()` beats `finished` only while the heartbeat is still its own (`last_beat()["pid"]`);
    `::test_a_30_minute_check_never_writes_over_a_live_watchs_heartbeat`.
  - N3: a failed wave is `due` once when Forsta closes it (`etl/forsta_etl.py discover`);
    `tests/test_forsta_etl.py::test_a_failed_wave_is_tried_when_forsta_closes_it_not_six_hours_later`.
  - N4: the Upload survey page calls `notify.alerts` after the load (`api/ingest.py publish_survey`);
    `tests/test_ingest_api.py::test_publish_loads_the_week_and_starts_one_publish`.
- **The deploy waits for `/readyz`**, not `/healthz` (`bitbucket-pipelines.yml &wait_live`, `tests/test_deploy_files.py`).
- **Secrets:** the GitHub repository is **public**. Both env files are untracked and `*.env` is ignored in cip-test and
  cip-stg; rotating every value, making the repository private and purging its history are the user's steps.
- These are in cip-test and cip-stg, waiting for deploy; deploy before Monday 17:30 IST for N1 and N2.

---

## 1. What was checked, and how

| Source | What it gave |
|---|---|
| Code | `git diff 896ec7f..68de3f4`, read file by file for every state holder |
| What staging runs | `/healthz` and `/readyz` both answer build **`3be1b2c1`**, which is `cip-stg` HEAD (15 Nov 15:46 IST). The 21 files touched by the fixes are byte-identical in `cip-test` and `cip-stg`. |
| Test suite | `pytest`: **595 passed** in 69.9 s. The 27 tests added with the fixes, run by name: **27 passed** (§3). `tsc --noEmit` on the frontend: no errors. |
| Live state | A read-only probe of the staging database `cip_stg` at **10:52:47 UTC (16:22 IST)** (script in Appendix C, output in Appendix A). It counts every state column, lists stuck rows, and runs the production integrity checks (`etl/integrity.py` `CHECKS`) and `etl/launch_schedule.py` `weeks()` on live data. Every session ran `SET SESSION TRANSACTION READ ONLY` (`@@session.transaction_read_only = 1`). |
| Dry runs | `harmonise.confirm_same_wording(apply=False)` and `publications.drift_summary()`, both read-only (Appendix D) |
| Reproductions | 4 pytest tests run under the repo's own isolation (`tests/conftest.py`: throwaway SQLite, live settings blanked, network blocked). Each test **passes while its issue exists**, so a fix turns it red (Appendix B). |

**Not observable from outside the container**, so not reported as live state:
- the ETL heartbeat file and the failure-email throttle file
- Ask's monthly spend file and its 15-minute pause after OpenAI refuses the key
- the published version folders
- all in-memory state (caches, rate-limit buckets) and all browser state

A signed-in admin sees most of these on the Logs page and at `/api/v1/admin/health`.

**Caution.** The local `.env` has no `APP_DB_USER`, so `get_engine("app")` on this Mac connects to staging as the STG
owner account, with full write rights, not as the read-only `cip_app`. That is why the probe makes its own sessions
read-only. Any local script or local API run writes to staging with owner rights.

---

## 2. The 13 earlier findings

| # | Finding (15 Nov audit) | Now | Where the fix is | Proof |
|---|---|---|---|---|
| 1 | Monday watch held the ETL lock for up to 54 h: the Upload page answered 409, SharePoint stopped | **Fixed** | `scripts/weekly_forsta.py:182-216`: the watch takes the lock for each check (`:197`). `main()` (`:291-310`) takes it only to start. `watch_waiting()` (`:279-289`) keeps the 30-minute checks off a live watch. | `test_the_watch_holds_the_lock_only_while_it_checks`. Lock free at probe time. **New issues N1, N2.** |
| 2 | Ask kept stale answers (after `learn()`, and from the keyword-only window) | **Fixed** | `api/assistant.py:448`: `learn()` empties the cache. `:747`, `:754`: no answer is kept until the vectors are done (`settled` flag, `:93`, `:138-143`). | `test_the_same_person_asking_again_gets_the_learned_answer_not_the_kept_quick_one`, `test_an_answer_from_before_the_search_vectors_is_not_kept`. Small residual R4. |
| 3 | A Forsta wave that failed 3 times was never retried, and the email said it would be | **Fixed** | `etl/forsta_etl.py:527-541` (`RETRY_HOURS = 6`), `next_try()` `:564`. `scripts/weekly_forsta.py:115`. `etl/notify.py:298` (`next_step`). | `test_a_wave_that_failed_three_times_is_tried_again_later_and_its_email_says_when`. Live: 0 failed, 0 due, 0 failed attempts. **Residual N3.** |
| 4 | Loads left `running` runs and half-loaded `verified` waves | **Fixed** | Qualtrics `etl/qualtrics_export.py:139-179`. Legacy `etl/legacy_dwh.py:332-345`. China `etl/baidu_qss_export.py:388`. Forsta `etl/forsta_etl.py:372`. All now use `except BaseException`. SIGTERM becomes `SystemExit` while the lock is held (`etl/loaders.py:44-46`). `finish_run` fails a run with an empty error (`:350`). The upgrade ignores `running` rows when the lock is free (`shared/core/schema_upgrade.py:196-197`). | 7 tests (§3). Live: 0 runs `running`, 0 waves not `verified`, integrity "wave stuck loading" passes. |
| 5 | SharePoint published outside the ETL lock | **Fixed** (watcher not on yet) | `etl/sharepoint_china.py:225` | `test_the_pass_publishes_under_the_etl_lock_and_waits_its_turn` |
| 6 | SharePoint load crashes went unreported, were retried forever, and copies piled up | **Fixed** (watcher not on yet) | `etl/sharepoint_china.py:46` (`ATTEMPTS = 3`), `:117-127`, `:183`, `:193-196`, `:204-215`, `:243` | 3 tests (§3) |
| 7 | Double-clicks made duplicates (6 forms) | **Fixed** | `PinDialog.tsx:15,32,63`; `AlertMe.tsx:12,36`; `ApiKeys.tsx:15,45`; `Audience.tsx:51,127`; `Boards.tsx:23,48,117,141`; Save view: `Shell.tsx:406,420` plus `saved.ts:5,27-31` (`68de3f4`) | `tsc` passes (there is no frontend test runner). Live: no duplicate team views, boards, audiences, comments or pinned items on staging; no alerts exist. |
| 8 | Two "loaded and verified" messages for each early-loaded wave | **Open: your decision** (`status/README.md`, Pending) | `scripts/weekly_forsta.py:163`. `etl/notify.py` still has no early/final wording. | Live example: wave `261002` was loaded early on 26 Oct 18:35 UTC (live, 401 qualified) and again on 2 Nov 12:02 UTC (closed, 404): one message each time. |
| 9 | Alerts were checked before Forsta closed the wave, never on the final data; the Library's "last fired" went stale | **Fixed** | `api/team.py:268` (an in-field wave stays due), `:276` (fires at most once per wave), `:287-288` (`changed()`). `notify.alerts` is called from `scripts/weekly_forsta.py:148`, `etl/forsta_etl.py:617` and `etl/sharepoint_china.py:219`. | `test_a_wave_loaded_early_is_judged_again_on_its_final_reload_and_fires_once`. Live: no alerts set on staging. **Residual N4.** |
| 10 | A failed Logs download asked for the admin token | **Fixed** | `frontend/src/screens/Logs.tsx:101-103`, `:119`, `:134`, `:163`, `:178` | `tsc` passes |
| 11 | The watchdog gave a false alarm during 2-3 h runs | **Fixed** | `scripts/weekly_forsta.py:271` counts silence from the promised next beat | `test_a_long_run_inside_its_promise_is_not_a_stopped_scheduler` |
| 12 | A wave hibernated between its early load and its final reload went unwarned | **Fixed** | `etl/integrity.py:136-140` (a new watch check) | `test_a_wave_hibernated_before_its_final_reload_is_warned_about`. Live: the check passes. |
| 13 | Signing in from two tabs at once failed the first tab | **Fixed** | `api/signin.py:48`, `:271-274`, `:308`, `:382` (one handshake cookie per attempt) | `test_two_tabs_signing_in_at_once_both_get_in` |

**Also fixed along the way:**
- Monday's 03:30 UTC slot started the watch 8.5 hours early (`deploy/etl-loop.sh:18`).
- Friday's full check ran on every idle check (`scripts/weekly_forsta.py:47`, `:125-131`).
- A rollback could land on a half-written version (`etl/publish.py:503`).
- The quick-then-check step of Ask now has its own rate limit, `ask_check` (`api/main.py:696`).
- Revoked sessions stay out after a restart (`api/signin.py:140`, `:201-211`).
- API keys are refused on admin pages, and offboarding someone revokes their keys.

**`status/README.md` is out of date on deploys.** It lists these fixes as "Waiting for deploy", but staging already runs
them: build `3be1b2c1` is `cip-stg` HEAD, and the files match `cip-test` byte for byte.

---

## 3. Tests run

Full suite: `595 passed in 69.86s` (exit 0). The tests added with the fixes, run by name (`27 passed in 19.79s`):

| Finding | Test |
|---|---|
| 1 | `test_pipeline_hardening.py::test_the_watch_holds_the_lock_only_while_it_checks` |
| 1 | `test_pipeline_hardening.py::test_the_30_minute_check_never_starts_a_watch` |
| 1 | `test_pipeline_hardening.py::test_only_the_launch_run_watches_on_a_monday` |
| 1 | `test_pipeline_hardening.py::test_the_full_check_runs_once_a_friday_on_the_first_idle_check_that_gets_the_lock` |
| 2 | `test_assistant.py::test_the_same_person_asking_again_gets_the_learned_answer_not_the_kept_quick_one` |
| 2 | `test_assistant.py::test_an_answer_from_before_the_search_vectors_is_not_kept` |
| 2 | `test_assistant.py::test_a_refused_key_sends_no_call_for_a_while_and_health_says_why` |
| 3 | `test_forsta_etl.py::test_a_wave_that_failed_three_times_is_tried_again_later_and_its_email_says_when` |
| 4 | `test_etl_fixes.py::test_a_run_closed_with_a_wordless_error_is_failed` |
| 4 | `test_etl_fixes.py::test_a_sigterm_while_the_etl_lock_is_held_unwinds_the_run` |
| 4 | `test_legacy_history.py::test_a_legacy_load_that_is_killed_closes_its_run_and_hides_its_wave` |
| 4 | `test_legacy_history.py::test_a_qualtrics_reload_is_hidden_while_it_loads_and_closed_when_killed` |
| 4 | `test_baidu_qss_export.py::test_a_china_load_stopped_half_way_closes_its_run_and_hides_its_week` |
| 4 | `test_schema_v2.py::test_a_run_killed_outright_does_not_block_the_upgrade_for_good` |
| 4 | `test_publish.py::test_a_rollback_never_lands_on_a_version_a_killed_publish_left_half_written` |
| 5 | `test_sharepoint_china.py::test_the_pass_publishes_under_the_etl_lock_and_waits_its_turn` |
| 6 | `test_sharepoint_china.py::test_a_crashing_load_is_told_once_spares_the_other_weeks_and_is_not_loaded_every_pass` |
| 6 | `test_sharepoint_china.py::test_a_folder_graph_cannot_reach_is_told_too` |
| 6, 9 | `test_sharepoint_china.py::test_a_loaded_week_is_judged_for_alerts_and_a_pass_that_meets_the_lock_keeps_no_copies` |
| 9 | `test_team.py::test_a_wave_loaded_early_is_judged_again_on_its_final_reload_and_fires_once` |
| 9 | `test_team.py::test_an_alert_stays_quiet_once_whoever_set_it_lost_access` |
| 9 | `test_forsta_etl.py::test_alerts_go_to_teams_and_their_owner_and_never_fail_a_load` |
| 11 | `test_pipeline_hardening.py::test_a_long_run_inside_its_promise_is_not_a_stopped_scheduler` |
| 12 | `test_pipeline_hardening.py::test_a_wave_hibernated_before_its_final_reload_is_warned_about` |
| 13 | `test_access.py::test_two_tabs_signing_in_at_once_both_get_in` |
| sessions | `test_access.py::test_a_revoked_session_stays_out_after_a_restart` |
| quick → check | `test_access.py::test_the_ai_check_and_search_have_their_own_limits` |

The reproductions of the open issues (Appendix B) ran with the same isolation: `4 passed in 0.72s`.

---

## 4. Issues still open, with proof

### N1. A watch check that finds the lock taken can't end the watch, and at the deadline sends a false alarm (medium)

**Where.**
- `scripts/weekly_forsta.py:200-202`: when `etl_lock()` raises `Locked`, the watch sets `now = {}`.
- `:207`: the watch ends only when `now["status"] == "loaded"` and the wave is closed, so that cycle can't end it.
- `:210-212`: if that cycle is past the deadline, the watch posts `⚠️ {name}: not in after 54 h (status: unknown)` to
  the Teams channel.

**When it happens.** Whenever another writer holds the lock at the moment the watch wakes for a check. Since fix #1 the
lock is free while the watch sleeps, so other writers now run during the watch and this is more likely than before:
- an Upload survey load, and the background `python -m etl.publish` it starts, which holds the lock for minutes
- a hand-run `python -m etl.forsta_etl --survey ...`
- the SharePoint watcher, once IT turns it on
- a 30-minute check that won the race (N2)

Most such cycles only skip one check, which runs again 30 minutes later. The harm comes when that cycle is the last
one: the team gets a false "not in after 54 h" with `status: unknown`, though the wave is loaded.

**Proof.** `test_a_watch_check_that_finds_the_lock_taken_cannot_end_and_alarms_at_its_deadline` (Appendix B) passes.
With `launch_schedule.weeks()` reporting the week loaded and closed, and the lock taken, `watch()` posts
`not in after 0 h (status: unknown)`. With the lock free, the same cycle ends quietly.

**Suggested change (not applied).** In the `Locked` branch, still read the week:
`now = next((w for w in launch_schedule.weeks()["weeks"] if w["date"] == str(week["date"])), {})`.
The end condition and the deadline message then use the real status. It is a read-only query.

### N2. A 30-minute check overwrites a live watch's heartbeat (low to medium)

**Where.** `scripts/weekly_forsta.py:309`: `main()` beats `finished` at the end of every run. That includes a
30-minute check (`--once`) that took the lock while a watch was alive. `watch_waiting()` (`:279-289`) only protects a
watch whose latest beat says `watching: waiting`.

**Sequence.**
1. The watch wakes at the moment a 30-minute check starts.
2. The check reads the heartbeat `watching: running` (not `waiting`), takes the lock and runs.
3. The watch finds the lock taken (N1), beats `watching: waiting` and sleeps for 30 minutes.
4. The check finishes and beats `finished`, over the watch's beat.
5. At the next half hour, `watch_waiting()` is False, so the check takes the lock ahead of the watch again, and the
   watch loses again.

This repeats until the watch's wake time drifts past the end of the check's run. Waves still load, because the checks
run the same `run()`. What breaks is the watch itself: its end condition and its deadline message (N1).

**Proof.** `test_a_30_minute_check_overwrites_a_live_watch_heartbeat_so_the_next_check_contends_again` passes. After
`main(once=True)`, the heartbeat says `finished` and `watch_waiting()` is False, while the watch's process is alive.

**Suggested change (not applied).** In `main()`, beat `finished` only if the heartbeat still carries this process's
`RUN` id (the `run` field `beat()` writes), so a check never writes over a live watch's beat.

### N3. Forsta closing a failed wave restarts its 6-hour retry clock (low)

**Where.**
- `run_due()` (`etl/forsta_etl.py:531-541`) counts the 6-hour pause from the newest `failed` row in `cip_forsta_event`.
- `discover()` writes a row whenever the pair (Forsta state, load_state) changes (`:183`, `:198`).
- A failed wave stays `failed` through the close (`:156`, `:162`).

So the close itself writes a `failed` event, though no load was tried.

**Effect.** Take the case fix #3 was about: a wave fails 3 times while in field, then Forsta closes it. It is now
retried 6 hours after the close, rather than at the close, when the final data first becomes readable. Before the fix
it was never retried, so this is a smaller residual of the same problem.

**Proof.** `test_forsta_closing_a_failed_wave_restarts_its_six_hour_retry_clock` passes.
- Control: a failed wave whose last failure is 7 hours old is picked by `run_due()`.
- After Forsta closes it, the newest event is `('closed', 'failed')`, and `run_due()` skips it.

**Suggested change (not applied).** Base the pause on load attempts only. One way: retry a failed wave on the first run
after its Forsta state changes, since closed is when the final data becomes readable. Another: keep `discover()` from
counting a pure Forsta state change as a failure.

### N4. China weeks loaded on the Upload survey page never trigger the alerts (low today)

**Where.** `api/ingest.py:76-99` (`publish_survey`) loads the week (`:89`) and starts the publish (`:98`), but never
calls `notify.alerts`. Every other load path does:
- the weekly run (`scripts/weekly_forsta.py:148`)
- a hand-run Forsta load (`etl/forsta_etl.py:617`)
- a SharePoint load (`etl/sharepoint_china.py:219`)

`status/README.md` says alerts now run "after China and hand-run loads". That holds for SharePoint, which isn't on yet,
but not for the Upload page, which is the China path in use today.

**Today.** No alerts are set on staging (`cip_metric_alert` is empty), so nothing has been missed yet. Once someone
sets an alert on a China question, weeks loaded on the Upload page are never checked against it. A later SharePoint
load checks only its own week.

**Proof.** `test_a_china_week_loaded_on_the_upload_page_never_judges_the_alerts` passes: `publish_survey()` returns the
loaded week, and `notify.alerts` is never called.

**Suggested change (not applied).** Call `notify.alerts([result["survey_id"]])` after the load. It never raises
(`etl/notify.py:293` catches everything). It could also run in the background publish process, so the request
doesn't wait on Teams and email.

### Still open by decision

- **#8, the two loaded messages.** See §2. Listed under Pending in `status/README.md`.
- **A load that crashes after writing its answers hides that week until a good load.** Already acknowledged in
  `status/README.md` ("needs staged reloads"). It comes from the `intact` rule in `etl/forsta_etl.py` and
  `etl/baidu_qss_export.py`.

### Minor residuals (low; no action needed now)

- **R1.** `FULL_CHECKED` is written before `integrity.run()` (`scripts/weekly_forsta.py:131`). If that run crashes, the
  Friday full check is not tried again that Friday.
- **R2.** A container stop sends SIGKILL to the loaders: bash is PID 1 (`deploy/Dockerfile:69` runs
  `bash deploy/start.sh`, with no init process) and doesn't pass SIGTERM on. So a run killed by a deploy still stays `running`, and its wave `loading`, until the next run. This is harmless
  now: the upgrade ignores such rows when the lock is free, and the register retries the wave. Live: 0 such rows.
- **R3.** The fieldwork collector marks a record complete when a row of the newest kind, `crosstab_check`, exists
  (`etl/fieldwork.py:346-356`, `:274`). Adding a newer kind means moving that marker by hand. Live: 0 records missing.
- **R4.** Two short windows in Ask's answer cache:
  - `add_vectors()` sets `self.vectors` before `load_verified()` (`api/ask_index.py:336-337`), so an answer worked out
    in between is kept without the verified and learned matches.
  - A quick answer worked out while `learn()` runs can be stored just after the cache is emptied
    (`api/assistant.py:740-757`).

  Both windows last a fraction of a second.
- **R5.** `load_state = 'testing'` covers both a survey in Forsta testing and a live study that can't be loaded yet.
  Live example: `selfserve/58f/261101`, an ad hoc study live since 12 Nov with 52 qualified. The `state` column tells
  them apart; only the name misleads.
- **R6.** `renew()` lets the session through if the database is out of reach (`api/signin.py:201-211`). This is a
  documented choice.

---

## 5. Current state of every machine

### 5.1 Stored in the database (staging `cip_stg`, 10:52 UTC)

**D1 Wave load (`cip_survey.load_status`: loading → verified / failed).** All 523 waves are `verified`. None are
`loading` or `failed`. Every verified wave has a serving row, and no serving row belongs to an unverified wave.

| platform | tracker | annual | ad hoc | total |
|---|---|---|---|---|
| forsta | 71 | 5 | 11 | 87 |
| qualtrics | 131 | 7 | 4 | 142 |
| surveymonkey | 69 | 12 | 64 | 145 |
| baidu | 149 | | | 149 |

**D2 Forsta register (`cip_forsta_survey`).**
- 98 rows: 87 `loaded` and 11 `testing` (10 in Forsta testing, 1 live ad hoc study). 8 of the loaded ones were
  hibernated by Forsta after their final load, which is fine.
- `due`, `failed`, `hibernated` and `new`: 0 each. No row has a failed attempt.
- `discover()` last ran at **10:30 UTC** (the 16:00 IST check), so staging's ETL loop is running.
- 2 rows have not been listed by Forsta for 7 days. The "no longer listed and never loaded" check passes, so neither is
  a missing wave.
- No wave is waiting for a final reload.
- Last 14 days: 3 `due` → `loaded` (waves `261002`, `261003`, `261100`), 3 launches, and 5 events for surveys in
  Forsta testing.

The two-phase load is real history. `261002` was loaded early on 26 Oct at 18:35 UTC (live, 401 qualified) and
reloaded at close on 2 Nov at 12:02 UTC (404). `261100` (launched 9 Nov) was not loaded early, because that day's
deploy killed the watch, as `status/README.md` records. It loaded on 10 Nov at 03:30 UTC.

**D3 Load runs (`cip_load_log`).**
- `success`: 673 (155 in the last 7 days, newest 11 Nov 18:30 UTC).
- `failed`: 9, newest 20 Oct. Four are lock-wait and deadlock errors from before the single ETL lock existed; five
  are legacy reloads interrupted on 30 Sep, each annotated by hand.
- `running`: **0**.
- No `sharepoint:` keys, so the SharePoint watcher has never run (it is waiting for IT).

**D4 Concept review (`cip_concept_map`: proposed → confirmed).**
- Confirmed: 122,785 (12,365 at question level, 110,420 at answer level).
- Proposed: 2,663 at question level (150 exact wording, 2,513 similar wording).
- Rejected: 0.

The dry run of `confirm_same_wording` would settle all 150 exact-wording proposals. 149 of them are China's `S2`
"What is your age?", one per China wave, against concept `D2_C85447`; the other is the US `NY2` in wave 530.
Confirming them puts China's age answers on the same concept as the US age question. That is a research decision, not
a technical one.
- To count: `python -m etl.harmonise --confirm-same-wording`
- To confirm: add `--apply`, then rebuild with `python -m etl.serving --all --jobs 4`

The 2,513 similar-wording proposals are mostly in US tracker waves: Forsta 1,455 (71 waves), Qualtrics 561 (118),
SurveyMonkey 168 (66).

**D5 Publications.**
- 1 `published`: `BEAUTY_RETAILERS_SHOPPERS_2024_25` v3.
- 2 `withdrawn`, set on 30 Sep by hand (no code writes `withdrawn`).
- 0 `draft`.

`drift_summary()` shows the published one still reproduces exactly: 66 cells, 0 moved, 0 missing, 0 new, 0 errors.

**D6 Sign-in sessions (`cip_access_session`, UTC).**

| provider | active | revoked | expired | total | newest sign-in |
|---|---|---|---|---|---|
| identity provider (oidc) | 1 | 29 | 187 | 188 | 14 Nov 03:42 |
| demo sign-in | 15 | 9 | 704 | 719 | 15 Nov 10:05 |

No revoked session is still unexpired, so the API's revocation list is empty. The demo sign-in is still used on
staging, which bears on your open decision to refuse unknown emails.

**D7 Metric alerts.** None are set on staging, so there is nothing to check. Alerts can be set on 101 families in the
serving layer: CSI-US (271 waves, newest 533 on 9 Nov), CSI-CN (149 waves, newest 682 on 26 Oct), and 99 families of
1-3 waves each. No wave is flagged in field.

**D8 SharePoint file versions.** No rows: the watcher is not on.

**D9 Fieldwork records (`cip_forsta_record`).** 88 surveys, 2,291 records, newest at 10:42 UTC today. Loaded Forsta
waves still missing a complete record: 0.

**Worked out at read time: the launch schedule.** This is `launch_schedule.weeks()` run on live data;
`planned_weeks_missing()` returns none.

| week | status | qualified / quota | Forsta closed (UTC) |
|---|---|---|---|
| 2026-09-28 | loaded | 403 / 400 | 29 Sep 06:16 |
| 2026-10-05 | loaded | 401 / 400 | 6 Oct 14:19 |
| 2026-10-12 | loaded | 404 / 400 | 13 Oct 14:00 |
| 2026-10-19 | loaded | 400 / 400 | 19 Oct 18:35 |
| 2026-10-26 | loaded | 404 / 400 | 26 Oct 19:52 |
| 2026-11-02 | loaded | 403 / 400 | 2 Nov 19:07 |
| 2026-11-09 | loaded | 404 / 400 | 9 Nov 19:49 |
| **2026-11-16** | **setting_up** | 110 / 400 | |
| 2026-11-23 | planned | | |
| 2026-11-30 | planned | | |

**Integrity: all 21 checks pass.** The list is in Appendix A.

### 5.2 Files and background processes

| Machine | Current state |
|---|---|
| Scheduler minute loop (`deploy/etl-loop.sh`) | Slots are `Mon@12:00` and `Tue-Sun@03:30` (`:18`). It is alive: `discover()` ran at 10:30 UTC and the fieldwork collector at 10:42 UTC. The next launch run is Mon 16 Nov at 12:00 UTC, for the week now in `setting_up`. |
| ETL lock and Monday watch | The lock was free at 10:52 UTC, so no run was in progress. The per-check locking (fix #1) runs for the first time tomorrow; see N1 and N2. |
| Heartbeat and watchdog | Not observable (the file is on the container). The code is fixed (#11). |
| Failure-email throttle (`logs/notify-state.json`) | Not observable. Unchanged: it is read and rewritten with no lock, so two processes can each send once in the same window. Low. |
| Published versions | `/readyz` answers `ready: true` (the published wave list is in place). The version folders are not observable. Rollback is fixed (`etl/publish.py:503`). |
| Ask AI on/off (spend file and 15-minute refusal pause) | Not observable without an admin session. `status/README.md` notes staging's OpenAI account had no credit on 14 Nov. |
| Ask learned and verified answer files | Not observable. The code is fixed (#2). |
| Open-ended coding (`/home/cip/coded`) | Not observable. Unchanged. |
| Request-log reader | Not observable. Unchanged. |
| API keys file | Not observable. Offboarding now revokes a person's keys (`api/signin.py` `revoke_person`, `shared/core/api_keys.py` `revoke`). |

### 5.3 API memory (per process)

| Machine | Current state |
|---|---|
| Published-data cache versions | The design is unchanged. The minute loop now also rebuilds Ask's index after a publish. |
| Ask index phases and answer cache | Fixed (#2); small residual R4. |
| Team lists cached by a stamp file | `due_alerts` now moves the stamp when an alert fires (`api/team.py:287-288`). |
| Access menus cache (30 s) | Saved choices are now stored as `{"on", "offered"}` (`shared/core/access.py` `choice()`, `grown()`). Live, 4 rows: 2 in the new format (service and analyst, written today at 09:22 and 10:42 UTC by the deployed code), 1 old list (a client, 7 Nov) and 1 `null` (a person's dropped choice, 7 Nov). The old format is still read correctly (`test_a_choice_saved_before_the_menus_grew_loses_nothing_and_a_new_one_is_kept_as_saved`). |
| Ask quick → check | Closed: a check now spends from its own `ask_check` limit (`api/main.py:696`). |

### 5.4 Screens and other code

| Machine | Current state |
|---|---|
| Ask reply (pending check / confirmed / failed / replaced) | Unchanged |
| Upload stages | Unchanged; fine (computed, never stored) |
| Logs page | Fixed (#10) |
| Undo bar (delete later) | Unchanged; fine |
| Save buttons | Fixed (#7), Save view included |
| Access screen | Redrawn as the complete left menu; unsaved choices per role work as before |
| Forsta export streaming parser | Unchanged; well tested (`tests/test_forsta_streaming.py`: chunk sizes 1 to 65,536 and 15 malformed exports) |
| Weekly report `ACTIVE` switch | Unchanged; fine while only one thread uses it |

---

## 6. Unused states and tables, checked against the data

| State or table | Written by code | Rows on staging | Verdict |
|---|---|---|---|
| `cip_survey.status` | never | 523, all `closed` (the default) | unused column |
| `load_status` value `superseded` | never | 0 | unused value |
| `load_state` value `new` | never (database default only) | 0 | unused value |
| concept map value `rejected` | never | 0 | unused value, though still read at `etl/harmonise.py:349` and `sql/002_views.sql:233` |
| publication value `draft` | never | 0 | unused value |
| publication value `withdrawn` | never | **2** (set by hand, 30 Sep) | **Used, by hand.** The filter in `drift_summary()` (`etl/publications.py:295`) is needed. Calling it dead code in the 15 Nov audit was wrong. |
| `cip_auth_session` table | never | 2 | unused table (replaced by `cip_access_session`) |
| `cip_load_state` table | only `scripts/rekey_respondents.py` (a run-once marker) | 0 | watermark columns unused |

---

## 7. Outside the state machines

1. **Secrets in git (high).** `cip-staging.env` and `cip_staging.env` have been tracked since `c23decd` (8 Nov) and are
   on GitHub `origin/master` (`saeedafri/consumer-insight-portal`). The Bitbucket deploy repo (`cip-stg`) does not
   track them. They hold:
   - the staging database passwords
   - `CIP_SESSION_SECRET`: anyone who has it can forge a sign-in cookie
   - `CIP_ADMIN_TOKEN`
   - the Forsta API key, the email password and the Teams webhook

   `.gitignore` covers `.env` and `.env.*`, but not `*.env`. Rotate every one of these, remove both files from the
   repo and its history, and add `*.env` to `.gitignore`.
2. **The local `.env` connects as the database owner** (see §1).
3. **Some lines of the local `.env` don't load.** python-dotenv cannot parse them (it warned about lines 67, 82, 84-86,
   89, 90 and 92), so those settings are silently missing.
4. **`status/README.md` shows deployed fixes as "Waiting for deploy"** (see §2).

---

## 8. Suggested order

1. Rotate the secrets (§7.1).
2. Before tomorrow's launch at 17:30 IST, if possible: N1 (one line) and N2.
3. N4 (one line).
4. Decide on the two loaded messages (#8) and on mapping China's age question (D4).
5. N3, when convenient.
6. Update `status/README.md`.

---

## Appendix A. Probe output

This is the probe's output as it ran at 10:52:47 UTC. It is verbatim except for three edits: the per-family list is
summarised, survey titles are dropped, and the one query that failed is explained.

```text
## Probe context
- read-only session: 1
- server time (UTC): 2026-11-15 10:52:47
- ETL lock `cip_etl` free: 1 (held by connection: None )
- srv_wave.in_field column present: True
- cip_forsta_survey.attempts column present: True

## D1 Wave load (cip_survey.load_status)
Waves by load_status, platform, study type
| load_status | platform | study_type | waves |
| verified | forsta | tracker | 71 |
| verified | forsta | annual | 5 |
| verified | forsta | adhoc | 11 |
| verified | qualtrics | tracker | 131 |
| verified | qualtrics | annual | 7 |
| verified | qualtrics | adhoc | 4 |
| verified | surveymonkey | tracker | 69 |
| verified | surveymonkey | annual | 12 |
| verified | surveymonkey | adhoc | 64 |
| verified | baidu | tracker | 149 |
The unused cip_survey.status column
| closed | 523 |
Every wave not 'verified': none
Verified waves with no serving row (not on any screen): none
Serving rows whose wave is not verified: none

## D2 Forsta register (cip_forsta_survey)
Register by load_state and Forsta state
| load_state | state | hibernated | surveys | last_seen |
| loaded | closed | 0 | 79 | 2026-11-15 10:30 |
| loaded | closed | 1 | 8 | 2026-11-15 10:30 |
| testing | live | 0 | 1 | 2026-11-15 10:30 |
| testing | testing | 0 | 5 | 2026-11-15 10:30 |
| testing | testing | 1 | 5 | 2026-11-15 10:30 |
When discover() last ran and rows not seen for 7 days
| newest_seen 2026-11-15 10:30 | unseen_7d 2 | total 98 |
Rows with failed attempts, and whether run_due picks them on the next run: none
Hibernated rows (survey_id set = loaded before hibernation)
| forsta_path | state | load_state | survey_id | closed_at | loaded_at |
| selfserve/58f/260703 | closed | loaded | 254 | 2026-08-03 20:06 | 2026-10-07 15:18 |
| selfserve/58f/260701 | closed | loaded | 252 | 2026-07-22 17:59 | 2026-10-07 15:15 |
| selfserve/58f/260700 | closed | loaded | 250 | 2026-07-14 17:04 | 2026-10-07 15:12 |
| selfserve/58f/260402 | closed | loaded | 244 | 2026-04-14 13:59 | 2026-10-07 14:59 |
| selfserve/58f/260202 | closed | loaded | 242 | 2026-02-24 14:45 | 2026-10-07 14:56 |
| selfserve/58f/260101 | closed | loaded | 241 | 2026-01-19 20:09 | 2026-10-07 14:54 |
| selfserve/58f/251004 | closed | loaded | 240 | 2025-10-27 22:31 | 2026-10-07 14:52 |
| selfserve/58f/beauty | closed | loaded | 237 | 2025-08-04 18:48 | 2026-10-07 14:45 |
| selfserve/58f/251201 | testing | testing | — | — | — |
| selfserve/58f/260504 | testing | testing | — | — | — |
| selfserve/58f/weekly_consumer | testing | testing | — | — | — |
| selfserve/58f/weekly_mass | testing | testing | — | — | — |
| selfserve/58f/weeklyconsumer_apparel | testing | testing | — | — | — |
Live surveys now (Forsta state 'live')
| forsta_path | study_type | launched_at | qualified_n | total_n | load_state | survey_id |
| selfserve/58f/261101 | adhoc | 2026-11-12 15:59 | 52 | 472 | testing | — |
Loaded early, waiting for the reload at close: none
Last 15 observed transitions (cip_forsta_event)
| forsta_path | seen_at | state | load_state | qualified_n |
| selfserve/58f/261101 | 2026-11-12 16:00 | live | testing | 0 |
| selfserve/58f/261102 | 2026-11-11 14:30 | testing | testing | 0 |
| selfserve/58f/261100 | 2026-11-10 03:30 | closed | loaded | 404 |
| selfserve/58f/261100 | 2026-11-10 03:30 | closed | due | 404 |
| selfserve/58f/261100 | 2026-11-09 14:00 | live | testing | 0 |
| selfserve/58f/261101 | 2026-11-06 03:30 | testing | testing | 1804 |
| selfserve/58f/261003 | 2026-11-05 12:25 | closed | loaded | 403 |
| selfserve/58f/261003 | 2026-11-05 12:23 | closed | due | 403 |
| selfserve/58f/261100 | 2026-11-05 12:23 | testing | testing | 110 |
| selfserve/58f/261003 | 2026-11-02 13:35 | live | testing | 0 |
| selfserve/58f/261002 | 2026-11-02 12:02 | closed | loaded | 404 |
| selfserve/58f/261002 | 2026-11-02 12:00 | closed | due | 404 |
| selfserve/58f/261003 | 2026-11-02 12:00 | testing | testing | 125 |
| selfserve/58f/261004 | 2026-11-02 12:00 | testing | testing | 0 |
| selfserve/58f/261002 | 2026-10-26 18:35 | live | loaded | 401 |
Transitions in the last 14 days by load_state
| due | closed | 3 | 2026-11-10 03:30 |
| loaded | closed | 3 | 2026-11-10 03:30 |
| testing | live | 3 | 2026-11-12 16:00 |
| testing | testing | 5 | 2026-11-11 14:30 |

## D3 Load runs (cip_load_log.status)
Runs by status (all time, last 7 days, newest)
| success | 673 | 155 | 2026-11-11 18:30 |
| failed | 9 | 0 | 2026-10-20 19:16 |
Runs still 'running': none
Last 10 failed runs
| 510 | 503 | api | forsta:selfserve/58f/260502 | 2026-10-20 19:16 | (1205, 'Lock wait timeout exceeded; try restarting transaction') INSERT INTO cip_quest... |
| 507 | 503 | api | forsta:selfserve/58f/260502 | 2026-10-20 19:13 | (1205, 'Lock wait timeout exceeded; try restarting transaction') INSERT INTO cip_quest... |
| 505 | 497 | api | forsta:selfserve/58f/260500 | 2026-10-20 19:08 | (1213, 'Deadlock found when trying to get lock; try restarting transaction') INSERT INTO cip_a... |
| 431 | 425 | api | forsta:selfserve/58f/250702 | 2026-10-20 17:38 | (1213, 'Deadlock found when trying to get lock; try restarting transaction') INSERT INTO cip_a... |
| 239 | 218 | manual | dwh_stg.dwh_sm*:281427446 | 2026-09-30 19:35 | interrupted: SurveyMonkey reload stopped with its session (2026-09-30/10-01); reload pending |
| 227 | 222 | manual | dwh_stg.dwh_sm*:283472319 | 2026-09-30 19:12 | interrupted: SurveyMonkey reload stopped with its session (2026-09-30/10-01); reload pending |
| 209 | 204 | manual | dwh_stg.dwh_sm*:164668935 | 2026-09-30 18:46 | interrupted: SurveyMonkey reload stopped with its session (2026-09-30/10-01); reload pending |
| 117 | 112 | manual | dwh_stg.dwh_sm*:SV_bQQ2shFHXxOxWWq | 2026-09-30 08:44 | interrupted (income overflow / VPN drop, 2026-09-30); wave reloaded successfully later |
| 35 | 30 | manual | dwh_stg.dwh_sm*:SV_8Cwf7gfYMnYlqvk | 2026-09-30 06:45 | interrupted (income overflow / VPN drop, 2026-09-30); wave reloaded successfully later |
Last 10 runs of any status: load_id 682-691, all success, 11 Nov 18:19-18:31 UTC, China weeks
  (source_ref "SharePoint <year>/<month>/Survey of <date>", survey_ids 653, 537, 536, 535, 534, 682, 681, 680, 679, 678)
SharePoint pair ledger (source_ref sharepoint:...): none

## D4 Concept review (cip_concept_map.status)
| status | method | question_level | mappings |
| proposed | exact_text | 1 | 150 |
| proposed | similar_text | 1 | 2513 |
| confirmed | exact_text | 0 | 110420 |
| confirmed | exact_text | 1 | 12365 |

## D5 Publications (cip_publication.status)
| withdrawn | 2 | 2026-09-30 18:31 |
| published | 1 | 2026-09-30 18:58 |

## D6 Sign-in sessions
| provider | active | revoked_unexpired | revoked_total | expired | total | newest_sign_in |
| oidc | 1 | 0 | 29 | 187 | 188 | 2026-11-14 03:42 |
| demo | 15 | 0 | 9 | 704 | 719 | 2026-11-15 10:05 |
The unused cip_auth_session table: 2 rows

## D7 Metric alerts (cip_metric_alert)
Each alert's watermark against the newest wave of its family: none (no alerts set)
Families in the serving layer: 101 (summarised)
  CSI-US tracker: 271 waves, newest survey_id 533 (2026-11-09), in_field 0
  CSI-CN tracker: 149 waves, newest survey_id 682 (2026-10-26), in_field 0
  99 other families (annual and ad hoc): 1-3 waves each, in_field 0

## D8 Fieldwork records (cip_forsta_record)
Loaded Forsta waves still missing a complete record: 0
Records kept: 88 surveys, 2291 records, newest 2026-11-15 10:42

## Serving layer flags
Waves served as 'in field': none
| ly_status | study_type | waves |
| loaded | annual | 1 |
| loaded | tracker | 287 |
| none | adhoc | 79 |
| none | annual | 23 |
| none | tracker | 133 |

## Other stored state
Dashboard pointers (cip_dash_published): 184, newest 2026-11-10 03:31
cip_load_state rows: none
Access screen choices (cip_role_access) by saved format
| OBJECT | 2 | 2026-11-15 10:42 |
| ARRAY | 1 | 2026-11-07 09:48 |
| NULL | 1 | 2026-11-07 11:55 |

## Duplicates left by double submits (before the 15 Nov guards)
Team views saved twice: none
Alerts set twice: query failed (MySQL ONLY_FULL_GROUP_BY on answer_label); the table is empty, so there are none
Boards with the same name by the same person: none
Audiences with the same name by the same person: none
Comments posted twice: none
Board items pinned twice: none

## Integrity checks (etl/integrity.py CHECKS, run read-only)
| verified wave without cube cells | derived | pass |
| verified wave missing from search | derived | pass |
| Forsta tracker wave without line-by-line rows | derived | pass |
| served wave whose serving rows differ from its cube cells | derived | pass |
| tracker line without its respondent | orphan | pass |
| search row of a deleted wave | orphan | pass |
| search row of a deleted question | orphan | pass |
| search row of a deleted concept | orphan | pass |
| calendar row of a survey not in the register | orphan | pass |
| tracker line of an unqualified or other wave's respondent | base | pass |
| register row pointing at a missing wave | base | pass |
| register says loaded, wave not verified | base | pass |
| wave stuck loading | base | pass |
| verified wave without qualified respondents | base | pass |
| duplicate Forsta respondent (uuid) in a wave | base | pass |
| same panelist qualified twice in a wave | base | pass |
| closed Forsta survey still not loaded after 3 days | base | pass |
| closed Forsta survey hibernated before it was loaded | watch | pass |
| Forsta wave hibernated before its final reload | watch | pass |
| Forsta survey no longer listed by Forsta and never loaded | watch | pass |
| profile filed under another wave | base | pass |

## Launch schedule status (etl/launch_schedule.py weeks(), on live data)
| date | cycle | status | qualified | quota | closed |
| 2026-09-28 | 21 | loaded | 403 | 400 | 2026-09-29T06:16:18Z |
| 2026-10-05 | 21 | loaded | 401 | 400 | 2026-10-06T14:19:55Z |
| 2026-10-12 | 21 | loaded | 404 | 400 | 2026-10-13T14:00:41Z |
| 2026-10-19 | 21 | loaded | 400 | 400 | 2026-10-19T18:35:13Z |
| 2026-10-26 | 22 | loaded | 404 | 400 | 2026-10-26T19:52:31Z |
| 2026-11-02 | 22 | loaded | 403 | 400 | 2026-11-02T19:07:58Z |
| 2026-11-09 | 22 | loaded | 404 | 400 | 2026-11-09T19:49:01Z |
| 2026-11-16 | 22 | setting_up | 110 | 400 | — |
| 2026-11-23 | 22 | planned | — | 400 | — |
| 2026-11-30 | 22 | planned | — | 400 | — |
planned_weeks_missing(): none

## Staging web app (public endpoints)
/healthz -> 200 {"ok":true,"build":"3be1b2c1"}
/readyz  -> 200 {"ready":true,"build":"3be1b2c1"}
```

---

## Appendix B. Reproduction tests for the open issues

Save the file anywhere and run it from the cip-test root:
`.venv/bin/python -m pytest -p tests.conftest <file> -q --rootdir=.`
(`-p tests.conftest` loads the repo's isolation: throwaway SQLite, live settings blanked, network blocked.) Each test
passes while its issue exists. Result on 15 Nov: `4 passed in 0.72s`.

<details>
<summary>test_state_machine_repro.py</summary>

```python
"""Reproductions for the state-machine issues still open after the 15 Nov fixes. Each test PASSES when the issue is
present (it asserts today's behaviour), so a fix makes it fail. Run from the cip-test root with the repo's isolation
(tests/conftest.py: throwaway SQLite, live settings blanked, network blocked):

    .venv/bin/python -m pytest -p tests.conftest <this file> -q
"""
from __future__ import annotations

import importlib
import io
import json
import os
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone

import sqlalchemy as sa

from etl import forsta_etl

PATH = "selfserve/58f/261200"


def survey(state: str, launched_hours_ago: float, closed: bool) -> dict:
    now = datetime.now(timezone.utc)
    return {"path": PATH, "title": "Shopping and Spending - inc Apparel", "state": state, "hibernated": False,
            "tags": ["Weekly consumer tracker"], "createdOn": (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "dateLaunched": (now - timedelta(hours=launched_hours_ago)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "closedDate": now.strftime("%Y-%m-%dT%H:%M:%SZ") if closed else None, "qualified": 404, "total": 470}


class Forsta:
    host = "se1.decipherinc.com"

    def __init__(self, meta):
        self.meta = meta

    def surveys(self):
        return [self.meta]

    def survey_quota(self, path):
        return {}


def test_forsta_closing_a_failed_wave_restarts_its_six_hour_retry_clock(csi_db, monkeypatch):
    """etl/forsta_etl.py discover records an event whenever (Forsta state, load_state) changes, and run_due counts the
    6-hour pause from the newest 'failed' event. So the close of a wave that failed 3 times while live writes a fresh
    'failed' event and pushes its retry 6 hours past the close, though no load was tried."""
    picked = []
    monkeypatch.setattr(forsta_etl, "load_survey", lambda client, path, meta=None: picked.append(path) or 1)
    live = Forsta(survey("live", launched_hours_ago=10, closed=False))       # fieldwork over (FIELD_HOURS 9): due
    assert forsta_etl.discover(live) == {"due": 1}
    for _ in range(forsta_etl.MAX_ATTEMPTS):                                 # three failed checks while live
        forsta_etl._mark(PATH, "failed", error="Forsta 503")
    seven_hours_ago = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=7)
    with csi_db.begin() as conn:                                             # the last failure is 7 hours old
        conn.execute(sa.text("UPDATE cip_forsta_event SET seen_at = :t WHERE forsta_path = :p"), {"t": seven_hours_ago, "p": PATH})
    assert forsta_etl.run_due(live)["loaded"] == [PATH]                      # control: due for its 6-hour retry now
    picked.clear()
    forsta_etl._mark(PATH, "failed", error="Forsta 503")                     # (that retry failed too: attempts 4)
    with csi_db.begin() as conn:
        conn.execute(sa.text("UPDATE cip_forsta_event SET seen_at = :t WHERE forsta_path = :p"), {"t": seven_hours_ago, "p": PATH})
    closed = Forsta(survey("closed", launched_hours_ago=20, closed=True))    # Forsta closes it: final data now readable
    forsta_etl.discover(closed)
    with csi_db.connect() as conn:
        newest = conn.execute(sa.text("SELECT state, load_state FROM cip_forsta_event WHERE forsta_path = :p"
                                      " ORDER BY event_id DESC LIMIT 1"), {"p": PATH}).one()
    assert tuple(newest) == ("closed", "failed")                            # the close itself is recorded as 'failed'
    assert forsta_etl.run_due(closed)["loaded"] == []                       # so the closed wave waits 6 more hours
    assert picked == []


def week():
    return {"date": date(2026, 11, 16), "names": ["Apparel"], "topics": [], "cycle": 22}


def test_a_watch_check_that_finds_the_lock_taken_cannot_end_and_alarms_at_its_deadline(tmp_path, monkeypatch):
    """scripts/weekly_forsta.py watch: when a 30-minute check holds the lock, the watch's cycle sets now = {} (no status
    read), so it cannot see 'loaded and closed', and if that cycle is past the deadline it posts '⚠️ … not in after
    54 h (status: unknown)' to Teams although the wave is in."""
    weekly = importlib.import_module("scripts.weekly_forsta")
    told = []
    monkeypatch.setattr(weekly, "HEARTBEAT", tmp_path / "beat.json")
    monkeypatch.setattr(weekly, "tell", lambda action, *args: told.append(args[0]))
    monkeypatch.setattr(weekly.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(weekly, "WATCH_HOURS", 0)                            # this cycle is past the deadline
    monkeypatch.setattr(weekly.launch_schedule, "weeks",                    # the wave IS loaded and closed
                        lambda today=None: {"weeks": [{"date": "2026-11-16", "status": "loaded", "closed": "2026-11-17T01:00:00Z"}]})

    def taken(wait=0):
        raise weekly.Locked("a 30-minute check holds the lock")
    monkeypatch.setattr(weekly, "etl_lock", taken)
    weekly.watch(week())
    assert any("not in after 0 h (status: unknown)" in m for m in told), told

    told.clear()                                                             # control: the same cycle with the lock free

    @contextmanager
    def free(wait=0):
        yield None
    monkeypatch.setattr(weekly, "etl_lock", free)
    monkeypatch.setattr(weekly, "run", lambda: 0)
    weekly.watch(week())
    assert not any("not in after" in m for m in told), told


def test_a_30_minute_check_overwrites_a_live_watch_heartbeat_so_the_next_check_contends_again(tmp_path, monkeypatch):
    """main(once=True) beats 'finished' when its run ends, over a live watch's 'watching: waiting' written meanwhile:
    watch_waiting() then answers False for the watch's whole 30-minute sleep, so the next check takes the lock instead
    of leaving it to the watch (and the watch's own check finds it taken: the test above)."""
    weekly = importlib.import_module("scripts.weekly_forsta")
    monkeypatch.setattr(weekly, "HEARTBEAT", tmp_path / "beat.json")
    monkeypatch.setattr(weekly, "tell", lambda *a: None)

    @contextmanager
    def free(wait=0):
        yield None
    monkeypatch.setattr(weekly, "etl_lock", free)
    weekly.beat("watching: running", weekly.RUN_HOURS)                      # the watch (pid alive) just woke for its check

    def check_while_the_watch_lost_the_lock():                               # meanwhile the watch found the lock taken
        weekly.beat("watching: waiting", weekly.WATCH_EVERY_SECONDS / 3600)  # and went back to sleep for 30 minutes
        assert weekly.watch_waiting() is True
        return 0
    monkeypatch.setattr(weekly, "run", check_while_the_watch_lost_the_lock)
    assert weekly.main(once=True) == 0
    beat = json.loads((tmp_path / "beat.json").read_text())
    assert beat["state"] == "finished" and beat["pid"] == os.getpid()        # the live watch's heartbeat is gone
    assert weekly.watch_waiting() is False                                   # the next check will not leave it to the watch


def test_a_china_week_loaded_on_the_upload_page_never_judges_the_alerts(tmp_path, monkeypatch):
    """api/ingest.py publish_survey loads a China week (the only China path live until IT enables SharePoint) but never
    calls etl/notify.py alerts, which etl/sharepoint_china.py, a hand-run Forsta load and the weekly run all call."""
    from fastapi import UploadFile
    from api import ingest
    from etl import baidu_qss_export, notify
    judged = []
    monkeypatch.setattr(ingest, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(ingest, "start_publish", lambda: None)
    monkeypatch.setattr(baidu_qss_export, "load", lambda raw, topline, wave=None, source=None:
                        {"wave": "2026-11-16", "survey_id": 999, "respondents": 400, "matched": 123})
    monkeypatch.setattr(notify, "alerts", lambda survey_ids: judged.append(survey_ids))
    raw = UploadFile(file=io.BytesIO(b"id,q1\n1,2\n"), filename="raw.csv")
    topline = UploadFile(file=io.BytesIO(b"topline"), filename="topline.xls")
    assert ingest.publish_survey(raw=raw, topline=topline, wave=None, who={"email": "admin@example.com"})["survey_id"] == 999
    assert judged == []                                                      # the SharePoint path would call alerts([999])
```

</details>

---

## Appendix C. The live-state probe

Run from the cip-test root: `.venv/bin/python <file> > state.md`. Every connection it opens is made read-only first,
and it never prints email addresses.

<details>
<summary>state_probe.py</summary>

```python
"""Read the current state of every database-backed CIP state machine on staging (cip_stg), and run the production
integrity checks and launch-schedule status function against it. Read-only: every connection the probe's engine opens
is put in READ ONLY mode before use, so any write would fail. Prints Markdown. Never prints email addresses.

    cd cip-test && .venv/bin/python <this file> > state.md
"""
import sys
from datetime import date, datetime, timedelta

sys.path.insert(0, ".")
from sqlalchemy import event, text  # noqa: E402

from shared.core.database import get_engine  # noqa: E402

ENGINE = get_engine("app")


@event.listens_for(ENGINE, "connect")
def read_only(dbapi_connection, record):
    cursor = dbapi_connection.cursor()
    cursor.execute("SET SESSION TRANSACTION READ ONLY")
    cursor.close()


def cell(value) -> str:
    if value is None:
        return "—"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    return str(value).replace("|", "/").replace("\n", " ")


def table(conn, title: str, sql: str, **params) -> list:
    print(f"\n#### {title}\n")
    try:
        result = conn.execute(text(sql), params)
        cols = list(result.keys())
        rows = result.all()
    except Exception as exc:  # a missing table or column on this server: say so, carry on
        print(f"_query failed: {type(exc).__name__}: {str(exc)[:200]}_")
        return []
    if not rows:
        print("_none_")
        return rows
    print("| " + " | ".join(cols) + " |")
    print("|" + "---|" * len(cols))
    for r in rows:
        print("| " + " | ".join(cell(v) for v in r) + " |")
    return rows


def has_column(conn, table_name: str, column: str) -> bool:
    return bool(conn.execute(text(
        "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = :t AND column_name = :c"),
        {"t": table_name, "c": column}).scalar())


with ENGINE.connect() as conn:
    print("## Probe context\n")
    print("- read-only session:", conn.execute(text("SELECT @@session.transaction_read_only")).scalar())
    print("- server time (UTC):", conn.execute(text("SELECT UTC_TIMESTAMP()")).scalar())
    print("- ETL lock `cip_etl` free:", conn.execute(text("SELECT IS_FREE_LOCK('cip_etl')")).scalar(),
          "(held by connection:", conn.execute(text("SELECT IS_USED_LOCK('cip_etl')")).scalar(), ")")
    print("- srv_wave.in_field column present:", has_column(conn, "srv_wave", "in_field"))
    print("- cip_forsta_survey.attempts column present:", has_column(conn, "cip_forsta_survey", "attempts"))
    in_field = has_column(conn, "srv_wave", "in_field")

    print("\n## D1 Wave load (cip_survey.load_status)")
    table(conn, "Waves by load_status, platform, study type",
          "SELECT load_status, platform, study_type, COUNT(*) AS waves FROM cip_survey GROUP BY 1, 2, 3 ORDER BY 1, 2, 3")
    table(conn, "The unused cip_survey.status column", "SELECT status, COUNT(*) AS waves FROM cip_survey GROUP BY 1")
    table(conn, "Every wave not 'verified'",
          "SELECT survey_id, platform, study_type, wave_label, LEFT(title, 60) AS title, load_status, updated_at"
          " FROM cip_survey WHERE load_status <> 'verified' ORDER BY updated_at DESC LIMIT 40")
    table(conn, "Verified waves with no serving row (not on any screen)",
          "SELECT s.survey_id, s.platform, s.study_type, s.wave_label, LEFT(s.title, 50) AS title FROM cip_survey s"
          " LEFT JOIN srv_wave w ON w.survey_id = s.survey_id WHERE s.load_status = 'verified' AND w.survey_id IS NULL"
          " ORDER BY s.survey_id")
    table(conn, "Serving rows whose wave is not verified",
          "SELECT w.survey_id, s.load_status, w.wave_date FROM srv_wave w JOIN cip_survey s ON s.survey_id = w.survey_id"
          " WHERE s.load_status <> 'verified'")

    print("\n## D2 Forsta register (cip_forsta_survey)")
    table(conn, "Register by load_state and Forsta state",
          "SELECT load_state, state, hibernated, COUNT(*) AS surveys, MAX(last_seen) AS last_seen"
          " FROM cip_forsta_survey GROUP BY 1, 2, 3 ORDER BY 1, 2, 3")
    table(conn, "When discover() last ran (newest last_seen) and rows not seen for 7 days",
          "SELECT MAX(last_seen) AS newest_seen, SUM(last_seen < UTC_TIMESTAMP() - INTERVAL 7 DAY) AS unseen_7d,"
          " COUNT(*) AS total FROM cip_forsta_survey")
    table(conn, "Rows with failed attempts, and whether run_due picks them on the next run (MAX_ATTEMPTS 3, RETRY_HOURS 6)",
          "SELECT f.forsta_path, f.state, f.load_state, f.attempts, f.closed_at, f.loaded_at,"
          " (SELECT MAX(e.seen_at) FROM cip_forsta_event e WHERE e.forsta_path = f.forsta_path AND e.load_state = 'failed') AS last_failed_event,"
          " CASE WHEN f.load_state = 'due' THEN 'yes (due)'"
          "      WHEN f.load_state = 'failed' AND (f.attempts < 3 OR NOT EXISTS (SELECT 1 FROM cip_forsta_event e"
          "           WHERE e.forsta_path = f.forsta_path AND e.load_state = 'failed' AND e.seen_at > UTC_TIMESTAMP() - INTERVAL 6 HOUR))"
          "      THEN 'yes' ELSE 'no' END AS picked_next_run,"
          " LEFT(f.last_error, 120) AS last_error"
          " FROM cip_forsta_survey f WHERE f.attempts > 0 OR f.load_state IN ('failed', 'due') ORDER BY f.closed_at DESC")
    table(conn, "Hibernated rows (with survey_id = loaded before hibernation)",
          "SELECT forsta_path, state, load_state, survey_id, closed_at, loaded_at, LEFT(title, 50) AS title"
          " FROM cip_forsta_survey WHERE load_state = 'hibernated' OR hibernated = 1 ORDER BY closed_at DESC LIMIT 30")
    table(conn, "Live surveys now (Forsta state 'live')",
          "SELECT forsta_path, LEFT(title, 50) AS title, study_type, launched_at, qualified_n, total_n, load_state, survey_id, quota_at"
          " FROM cip_forsta_survey WHERE state = 'live' ORDER BY launched_at DESC")
    table(conn, "Loaded early, waiting for the reload at close (load_state loaded, Forsta not closed)",
          "SELECT forsta_path, state, survey_id, loaded_at, qualified_n FROM cip_forsta_survey"
          " WHERE load_state = 'loaded' AND state <> 'closed'")
    table(conn, "Last 15 observed transitions (cip_forsta_event)",
          "SELECT forsta_path, seen_at, state, load_state, qualified_n FROM cip_forsta_event ORDER BY event_id DESC LIMIT 15")
    table(conn, "Transitions in the last 14 days by load_state",
          "SELECT load_state, state, COUNT(*) AS events, MAX(seen_at) AS newest FROM cip_forsta_event"
          " WHERE seen_at > UTC_TIMESTAMP() - INTERVAL 14 DAY GROUP BY 1, 2 ORDER BY 1, 2")

    print("\n## D3 Load runs (cip_load_log.status)")
    table(conn, "Runs by status (all time, and last 7 days)",
          "SELECT status, COUNT(*) AS runs, SUM(started_at > UTC_TIMESTAMP() - INTERVAL 7 DAY) AS last_7_days,"
          " MAX(started_at) AS newest FROM cip_load_log GROUP BY 1 ORDER BY 1")
    table(conn, "Runs still 'running' (never closed)",
          "SELECT load_id, survey_id, source_type, object_type, LEFT(source_ref, 60) AS source_ref, started_at,"
          " TIMESTAMPDIFF(HOUR, started_at, UTC_TIMESTAMP()) AS hours_old FROM cip_load_log WHERE status = 'running' ORDER BY load_id")
    table(conn, "Last 10 failed runs",
          "SELECT load_id, survey_id, source_type, LEFT(source_ref, 50) AS source_ref, started_at, LEFT(error_text, 140) AS error"
          " FROM cip_load_log WHERE status = 'failed' ORDER BY load_id DESC LIMIT 10")
    table(conn, "Last 10 runs of any status",
          "SELECT load_id, survey_id, source_type, object_type, LEFT(source_ref, 50) AS source_ref, status, started_at, finished_at"
          " FROM cip_load_log ORDER BY load_id DESC LIMIT 10")
    table(conn, "SharePoint pair ledger (source_ref sharepoint:...)",
          "SELECT status, source_type, (survey_id IS NULL) AS no_survey, COUNT(*) AS runs, MAX(started_at) AS newest"
          " FROM cip_load_log WHERE source_ref LIKE 'sharepoint:%' GROUP BY 1, 2, 3")

    print("\n## D4 Concept review (cip_concept_map.status)")
    table(conn, "Mappings by status and method",
          "SELECT status, method, (concept_option_id IS NULL) AS question_level, COUNT(*) AS mappings"
          " FROM cip_concept_map GROUP BY 1, 2, 3 ORDER BY 1, 2, 3")

    print("\n## D5 Publications (cip_publication.status)")
    table(conn, "Publications by status", "SELECT status, COUNT(*) AS publications, MAX(published_at) AS newest FROM cip_publication GROUP BY 1")

    print("\n## D6 Sign-in sessions")
    table(conn, "cip_access_session by state (UTC)",
          "SELECT provider,"
          " SUM(revoked_at IS NULL AND expires_at > UTC_TIMESTAMP()) AS active,"
          " SUM(revoked_at IS NOT NULL AND expires_at > UTC_TIMESTAMP()) AS revoked_unexpired,"
          " SUM(revoked_at IS NOT NULL) AS revoked_total, SUM(expires_at <= UTC_TIMESTAMP()) AS expired,"
          " COUNT(*) AS total, MAX(created_at) AS newest_sign_in FROM cip_access_session GROUP BY provider")
    table(conn, "The unused cip_auth_session table", "SELECT COUNT(*) AS rows_ FROM cip_auth_session")

    print("\n## D7 Metric alerts (cip_metric_alert)")
    newest = "MAX(w.survey_id)"
    closed = "MAX(CASE WHEN COALESCE(w.in_field, 0) = 0 THEN w.survey_id END)" if in_field else newest
    table(conn, "Each alert's watermark against the newest wave of its family",
          "SELECT a.alert_id, a.survey_family, a.study_type, a.qcode, a.against, a.last_checked, a.last_fired,"
          " (a.owner_email IS NOT NULL) AS has_owner, a.created_at,"
          f" {newest} AS newest_wave, {closed} AS newest_closed_wave,"
          f" CASE WHEN COALESCE(a.last_checked, 0) >= COALESCE({closed}, 0) THEN 'up to date' ELSE 'behind' END AS judged"
          " FROM cip_metric_alert a LEFT JOIN srv_wave w ON w.survey_family = a.survey_family AND w.study_type = a.study_type"
          " GROUP BY a.alert_id, a.survey_family, a.study_type, a.qcode, a.against, a.last_checked, a.last_fired, a.owner_email, a.created_at"
          " ORDER BY a.alert_id")
    table(conn, "Families in the serving layer (what alerts can be set on)",
          "SELECT w.survey_family, w.study_type, COUNT(*) AS waves, MAX(w.survey_id) AS newest_id, MAX(w.wave_date) AS newest_date"
          + (", SUM(w.in_field) AS in_field" if in_field else "") +
          " FROM srv_wave w GROUP BY 1, 2 ORDER BY 1, 2")

    print("\n## D8 Fieldwork records (cip_forsta_record)")
    table(conn, "Loaded Forsta waves still missing a complete record (no crosstab_check row): the collect() queue",
          "SELECT COUNT(*) AS missing FROM cip_forsta_survey f JOIN cip_survey s ON s.source_ref = f.forsta_path AND s.platform = 'forsta'"
          " WHERE f.forsta_path NOT IN (SELECT forsta_path FROM cip_forsta_record WHERE kind = 'crosstab_check')")
    table(conn, "Records kept", "SELECT COUNT(DISTINCT forsta_path) AS surveys, COUNT(*) AS records, MAX(fetched_at) AS newest FROM cip_forsta_record")

    print("\n## Serving layer flags")
    if in_field:
        table(conn, "Waves served as 'in field' and their register state",
              "SELECT w.survey_id, w.wave_date, w.survey_family, f.state, f.load_state, f.closed_at FROM srv_wave w"
              " LEFT JOIN cip_survey s ON s.survey_id = w.survey_id LEFT JOIN cip_forsta_survey f ON f.forsta_path = s.source_ref"
              " WHERE w.in_field = 1 ORDER BY w.survey_id")
    table(conn, "ly_status across served waves", "SELECT ly_status, study_type, COUNT(*) AS waves FROM srv_wave GROUP BY 1, 2 ORDER BY 1, 2")

    print("\n## Other stored state")
    table(conn, "Dashboard pointers (cip_dash_published)", "SELECT COUNT(*) AS published, MAX(published_at) AS newest FROM cip_dash_published")
    table(conn, "cip_load_state rows (designed as watermarks)", "SELECT feed_name, last_status, updated_at FROM cip_load_state")
    table(conn, "Access screen choices (cip_role_access) by saved format",
          "SELECT JSON_TYPE(features) AS format, COUNT(*) AS roles, MAX(updated_at) AS newest FROM cip_role_access GROUP BY 1")

    print("\n## Duplicates left by double submits (before the 15 Nov guards)")
    table(conn, "Team views saved twice (same url and owner)",
          "SELECT url, COUNT(*) AS copies, GROUP_CONCAT(view_id ORDER BY view_id) AS view_ids, MIN(created_at) AS first, MAX(created_at) AS last"
          " FROM cip_team_view GROUP BY url, owner_email HAVING COUNT(*) > 1 ORDER BY copies DESC LIMIT 20")
    table(conn, "Alerts set twice (same owner, question, answer, cut, baseline)",
          "SELECT qcode, answer_label, COUNT(*) AS copies, GROUP_CONCAT(alert_id ORDER BY alert_id) AS alert_ids FROM cip_metric_alert"
          " GROUP BY owner_email, survey_family, study_type, qcode, item_label, option_code, dim, dim_value, against HAVING COUNT(*) > 1")
    table(conn, "Boards with the same name by the same person",
          "SELECT name, COUNT(*) AS copies, GROUP_CONCAT(board_id ORDER BY board_id) AS board_ids, TIMESTAMPDIFF(SECOND, MIN(created_at), MAX(created_at)) AS seconds_apart"
          " FROM cip_board GROUP BY name, created_by HAVING COUNT(*) > 1")
    table(conn, "Audiences with the same name by the same person",
          "SELECT name, COUNT(*) AS copies, GROUP_CONCAT(audience_id ORDER BY audience_id) AS audience_ids FROM cip_audience"
          " GROUP BY name, owner_email HAVING COUNT(*) > 1")
    table(conn, "Comments posted twice (same item, author, text)",
          "SELECT item_id, COUNT(*) AS copies, GROUP_CONCAT(comment_id ORDER BY comment_id) AS comment_ids FROM cip_board_comment"
          " GROUP BY item_id, author, body HAVING COUNT(*) > 1")
    table(conn, "Board items pinned twice (same board, title, url, spec)",
          "SELECT board_id, LEFT(title, 50) AS title, COUNT(*) AS copies, GROUP_CONCAT(item_id ORDER BY item_id) AS item_ids FROM cip_board_item"
          " GROUP BY board_id, title, url, MD5(spec) HAVING COUNT(*) > 1")

    print("\n## Integrity checks (etl/integrity.py CHECKS, run read-only)\n")
    from etl import integrity
    print("| check | kind | result |")
    print("|---|---|---|")
    for check in integrity.CHECKS:
        try:
            hits = integrity.found(conn, check)
            result = "pass" if not hits else (f"survey_id {hits[:10]}" if check.kind == "derived" else f"{hits[0]}")
        except Exception as exc:
            result = f"query failed: {type(exc).__name__}"
        print(f"| {check.name} | {check.kind} | {result} |")

print("\n## Launch schedule status (etl/launch_schedule.py weeks(), run on live data)\n")
from etl import launch_schedule  # noqa: E402

today = date.today()
weeks = launch_schedule.weeks(today)["weeks"]
recent = [w for w in weeks if today - timedelta(days=50) <= date.fromisoformat(str(w["date"])) <= today + timedelta(days=15)]
keys = [k for k in ("date", "cycle", "status", "qualified", "quota", "closed", "path", "names") if any(k in w for w in recent)]
print("| " + " | ".join(keys) + " |")
print("|" + "---|" * len(keys))
for w in recent:
    print("| " + " | ".join(cell(w.get(k)) for k in keys) + " |")
missing = integrity.planned_weeks_missing(today)
print("\nplanned_weeks_missing():", missing or "none")
```

</details>

---

## Appendix D. Dry runs on live data

<details>
<summary>dry_runs.py, review_queue.py and their output</summary>

```python
"""Dry runs of two state machines' own functions against staging, read-only (every connection READ ONLY):
  - etl/harmonise.py confirm_same_wording(apply=False): which 'proposed' concept mappings the safe auto-confirm would settle
  - etl/publications.py drift_summary(): whether each published publication still reproduces its frozen numbers
"""
import sys

sys.path.insert(0, ".")
from sqlalchemy import event  # noqa: E402

from shared.core.database import get_engine  # noqa: E402

for role in ("app", "etl"):
    @event.listens_for(get_engine(role), "connect")
    def read_only(dbapi_connection, record):
        cursor = dbapi_connection.cursor()
        cursor.execute("SET SESSION TRANSACTION READ ONLY")
        cursor.close()

from etl import harmonise, publications  # noqa: E402

plan = harmonise.confirm_same_wording(apply=False)
print("confirm_same_wording(apply=False):", sum(plan.values()), "units in", len(plan), "waves")
print("  per wave (survey_id: units):", dict(sorted(plan.items())))

drift = publications.drift_summary()
print("drift_summary():")
print(drift.to_string(index=False) if not drift.empty else "  (no published publication)")
```

```python
"""The concept-review queue on staging, read-only: what the 150 safe proposals are, and where the similar-text ones sit."""
import sys

sys.path.insert(0, ".")
from sqlalchemy import event, text  # noqa: E402

from shared.core.database import get_engine  # noqa: E402

engine = get_engine("app")


@event.listens_for(engine, "connect")
def read_only(dbapi_connection, record):
    cursor = dbapi_connection.cursor()
    cursor.execute("SET SESSION TRANSACTION READ ONLY")
    cursor.close()


with engine.connect() as conn:
    print("exact_text proposals by question and concept:")
    for row in conn.execute(text(
            "SELECT q.qcode, c.concept_code, LEFT(q.qtext, 70) AS qtext, s.survey_family, COUNT(*) AS waves,"
            " MIN(s.wave_label) AS first_wave, MAX(s.wave_label) AS last_wave FROM cip_concept_map m"
            " JOIN cip_question q ON q.question_id = m.question_id JOIN cip_concept c ON c.concept_id = m.concept_id"
            " JOIN cip_survey s ON s.survey_id = m.survey_id"
            " WHERE m.status = 'proposed' AND m.method = 'exact_text' AND m.concept_option_id IS NULL"
            " GROUP BY q.qcode, c.concept_code, LEFT(q.qtext, 70), s.survey_family ORDER BY waves DESC LIMIT 10")):
        print("  ", tuple(row))
    print("similar_text proposals by family:")
    for row in conn.execute(text(
            "SELECT s.survey_family, s.platform, COUNT(*) AS proposals, COUNT(DISTINCT m.survey_id) AS waves, MIN(m.created_at), MAX(m.created_at)"
            " FROM cip_concept_map m JOIN cip_survey s ON s.survey_id = m.survey_id"
            " WHERE m.status = 'proposed' AND m.method = 'similar_text' GROUP BY 1, 2 ORDER BY proposals DESC LIMIT 8")):
        print("  ", tuple(row))
    print("role access rows (kind only):")
    for row in conn.execute(text("SELECT CASE WHEN role LIKE 'person:%' THEN 'person' WHEN role LIKE 'client:%' THEN 'client'"
                                 " ELSE role END AS who, JSON_TYPE(features), updated_at FROM cip_role_access ORDER BY updated_at")):
        print("  ", tuple(row))
```

```text
confirm_same_wording(apply=False): 150 units in 150 waves
  per wave (survey_id: units): {530: 1, 534: 1, 535: 1, ... 682: 1}   (one unit in each of waves 530 and 534-682)
drift_summary():
 publication_id                          pub_code  version  pub_name                                                published_at         cells  moved  missing  new  error
              3 BEAUTY_RETAILERS_SHOPPERS_2024_25        3  Beauty retailers — beauty shoppers, Jun 2024 – May 2025  2026-09-30 18:58:37     66      0        0    0      0

exact_text proposals by question and concept:
   ('S2', 'D2_C85447', 'What is your age? (Select one)', 'CSI-CN', 149, '2023-10-23', '2026-10-26')
   ('NY2', 'Q9_642773', "How do you expect your New Year's holiday spending this year to compar", 'CSI-US', 1, '2026-10-26', '2026-10-26')
similar_text proposals by family:
   ('CSI-US', 'forsta', 1455, 71, 2026-10-07 14:41:48, 2026-11-10 03:30:12)
   ('CSI-US', 'qualtrics', 561, 118, 2026-09-30 06:31:06, 2026-09-30 12:32:29)
   ('CSI-US', 'surveymonkey', 168, 66, 2026-10-08 12:05:46, 2026-10-08 13:45:00)
   ('HOLIDAY_SHOPPING_AND_SPENDING', 'forsta', 23, 2, ...)
   ('HOLIDAY_SHOPPING', 'forsta', 16, 1, ...)
   ('AMAZON_APPAREL_ANNUAL_TRACKER', 'forsta', 10, 1, ...)
   ('ONLINE_GROCERY', 'forsta', 9, 1, ...)
   ('BACK_TO_SCHOOL', 'forsta', 8, 1, ...)
role access rows (kind only):
   ('client', 'ARRAY', 2026-11-07 09:48:20)
   ('person', 'NULL', 2026-11-07 11:55:25)
   ('service', 'OBJECT', 2026-11-15 09:22:11)
   ('analyst', 'OBJECT', 2026-11-15 10:42:04)
```

</details>

---

## Appendix E. Re-running everything

From the cip-test root:

| Check | Command |
|---|---|
| Test suite | `.venv/bin/python -m pytest -q` (595 tests, about 70 s) |
| Frontend types | `cd frontend && node_modules/.bin/tsc --noEmit -p .` |
| Open-issue reproductions | save Appendix B, then `.venv/bin/python -m pytest -p tests.conftest <file> -q --rootdir=.` |
| Live state | save Appendix C, then `.venv/bin/python <file> > state.md` (read-only sessions; needs the VPN route to the staging database) |
| Dry runs | save Appendix D, then `.venv/bin/python <file>` |
| What staging runs | `curl -s https://csr-awa-cip-portal-stg-gyhvanh7gmbmdda0.centralus-01.azurewebsites.net/healthz` (compare `build` with `git -C ../cip-stg log -1 --format=%h`) |
