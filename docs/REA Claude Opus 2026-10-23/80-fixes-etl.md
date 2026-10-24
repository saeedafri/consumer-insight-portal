# 80 · ETL fixes (23 Oct 2026)

Scope: code, tests and read-only checks only. Nothing was written to any database. Serving and cube were not rebuilt, `etl.publish` was not run, no DDL or view was applied, Forsta was not called, and nothing on :8000 was touched. Every live-data step is in the runbook (§3 runbook) and needs your approval first.

Tests: `.venv/bin/python -m pytest -q tests` gives **318 passed**. That includes 17 new tests in `tests/test_etl_fixes.py`, and two older tests updated where the intended behaviour changed (`test_launch_schedule.py`, `test_serving.py`).

## 1. Gap → change → test → evidence

| Gap | Change (file:line) | Test | Evidence |
|---|---|---|---|
| **ETL-01** A numeric answer with more than 4 decimals failed the whole wave | `etl/forsta_etl.py:227` `_number` rounds to 4 decimals, so `DECIMAL(18,4)` takes the value without a Note. `qtime` seconds use `_number` too. The strict warning gate in `database.bulk_insert` stays. The other bulk-loaded decimals (`srv_result.pct/prior_pct/ly_pct`) were already rounded to 3 decimals. | `test_a_numeric_answer_is_rounded_to_the_four_decimals_mysql_stores` checks the LOAD DATA text (`tsv()`) against the MySQL `DECIMAL(18,4)` shape. SQLite cannot show this, because it never warns. | 250701's `qtime` Note 1265 (`logs/forsta-etl.log:1220`) |
| **ETL-02** Serving keyed cells on item label | `etl/serving.py:141-185`: within a wave a cell is identified by `(question_id, item_id, option_id, dim, dim_value)`. The prior or last-year match (`counterpart`) uses the harmonised answer first, then `(qcode, normalised item label, option code)`, and only when that key is unique in both waves. `rows_for` (`:187`) now writes one row per cube cell. | `test_two_items_with_the_same_label_are_both_served_and_compared_only_when_unambiguous` | Read-only dry run of the new build on survey 97: both YouTube items are served (item 13115 n=0 and item 13120 n=612 = 47.3 %), where live serving has only the 0 % one. |
| ETL-02 integrity | `etl/integrity.py:82`: new derived check "served wave whose serving rows differ from its cube cells", healed by `serving.build_wave`. It covers waves built in the last 7 days, because the full check takes about 100 s. | `test_integrity_finds_a_wave_whose_serving_rows_lost_cube_cells` | Read-only, full form on live: under the old rule exactly waves **97, 201, 210, 214, 295, 361, 383 and 406** mismatch, matching the audit's 8. Under the new rule 329 waves mismatch until they are rebuilt, because their blank-segment rows go (DB-06). |
| ETL-02 source (survey 97 Q7 import) | **The legacy import is malformed.** `dwh_smanswer` lists `QID17A1–A12` (Facebook … LinkedIn), but the responses carry `A9–A20`. All 818 responses on `A9` have the text "Facebook" while the list calls `A9` "LinkedIn". Live `cip_answer` therefore holds Facebook's 818 under "LinkedIn", Instagram's 397 under "Reddit", and so on, and Facebook, Instagram, Pinterest, TikTok, Twitter and YouTube r9 are 0 %. Fix: `etl/legacy_dwh.py:156` `relabel()` gives each answer the one text its responses carry (HTML, spacing and entities ignored, since SurveyMonkey stores `In-store<em> only</em>`), and drops a listed answer nobody chose that only repeats another answer's label. | `test_a_legacy_answer_takes_the_label_its_respondents_saw` | Read-only scan of 145 legacy waves, see §1.1. A second malformed wave was found: **201** (`SV_3VmPUvYk4kj76PY`, tracker 15 Aug 2022), with 88 shifted answer ids covering 8,029 picks (grocery retailers). Both waves need a reload (runbook step 4). |
| **ETL-03** `concept_option_id` was never served | `etl/serving.py:116-139`: `cube_rows` joins the confirmed `cip_concept_map` row on the cell's `map_key`, so `srv_result.concept_option_id` is filled. `payloads.versions` and the prior/last-year match then use it. `app/data/cube.py:179`: `refresh_cohorts`, which runs after every Mappings decision, now rebuilds that wave's serving rows plus its dependants. | `test_a_confirmed_concept_fills_serving_and_links_a_reworded_question` | Dry run: concept filled on 11,727 of 12,425 rows (wave 415), 11,719 of 14,639 (412) and 6,817 of 6,817 (97). Live has 0. |
| DB-08 / ETL-20 auto-confirm | `app/data/harmonise.py:379` `confirm_same_wording(apply=False)`, with CLI `python -m app.data.harmonise --confirm-same-wording [--apply]`. It confirms a proposed unit only when the wording and type exactly match its concept (method `exact_text`) and no other question in the wave already uses that concept. Similar-wording proposals stay for a person. New loads are unchanged: "changed" stays proposed, which was a deliberate earlier design choice. | `test_same_wording_proposals_are_confirmed_only_when_asked_and_safe` | **Dry run (read-only engine): 1,322 units in 350 waves would be confirmed.** The queue holds 1,322 proposed exact-text and 2,449 proposed similar-text units. |
| **Significance (UI-01/02/04/09)** | `etl/serving.py:218-258`. Each wave's Total rows are tested with a two-sided pooled two-proportion z-test against prior and against last year (`p_value`, `math.erfc`). Benjamini–Hochberg runs at 5 % FDR (`survives`) **over the testable rows only**. Testable means: both percentages present, both bases ≥ `TEST_BASE` (30), no `base_changed_*`, and not a filler (regex identical to `web/src/api.ts isFiller`). Rows that pass get `sig_prior` / `sig_ly` in `srv_result.flags`, which is comma-separated and additive. The rule is written out in the module docstring (`:13-19`). `sql/009_serving_flags.sql` widens the SET. Until 009 is applied, `schema_has()` (`:64`) leaves the tokens out, so code deployed before the DDL never errors. | `test_the_z_test_and_benjamini_hochberg_match_the_textbook`, `test_significance_flags_follow_the_written_rule` (a filler and a base-20 row are not tested; only Total rows are flagged) | Dry run: wave 415 has 6 `sig_prior` and 7 `sig_ly`; 412 has 0 and 1. **Deviation from the brief:** it said base ≥ 5. I used 30, the same as `payloads.TEST_BASE` and `web/src/stats.ts TEST_BASE`, so the pipeline and the frontend fallback agree. To use 5, change `serving.TEST_BASE`. |
| **ETL-04** One exception ended the 54 h watch | `scripts/weekly_forsta.py:160-185`: each cycle's `run()` and schedule read is wrapped. A failure logs, alerts ("a watch cycle crashed"), sets `code = 1`, and the watch continues. | `test_the_watch_carries_on_past_a_crashed_cycle` | — |
| **ETL-06** Annual and ad hoc studies loaded at 9 h | `etl/forsta_etl.py:105-113`: `fielded()` is now for trackers only (9 h / 400 / quota). Other studies load when Forsta closes them. `srv_wave.in_field` is set in the build (`serving.py:113,279`), meaning a Forsta wave with no `field_end`. The column comes from 009 (and `schema_upgrade`, edited by the backend agent). | `test_fieldwork_ends_…` (updated), `test_a_wave_loaded_while_in_field_is_marked_in_field` | — |
| **ETL-10/11, DB-07** | `config/survey_map.yml:23-60`: a `family:` map, keyed by source reference: HOLIDAY_SHOPPING (2021, 2023, 2025, 2026), ONLINE_GROCERY (2019, 2023–2026), APPAREL_SHOPPING (2019–2023), BACK_TO_SCHOOL (2021, 2022, 2023, 2026) and SHOPPING_AND_SOCIAL_MEDIA (2019, 2021). There is also an `exclude:` list (394, 382, 261). Code changes: `etl/survey_map.py:71-87`; `forsta_etl.family` (`:68`) and `legacy_dwh.study_for` (`:53`) read the map. In serving, `served()` (`:73`) gives no serving rows to excluded waves or to non-tracker waves under `MIN_SAMPLE` (30), and `comparison()` never picks them. Non-tracker "last year" is the family's latest wave 300–430 days earlier (`YEAR_DAYS`), because annual studies are not fielded in the same week each year. `discover()` sets a closed non-tracker survey under 30 qualified to `too_small` (`:159`), or `testing` until 009 adds the ENUM member. Raw data is never deleted. | `test_an_annual_study_listed_in_the_config_…`, `test_a_closed_tiny_ad_hoc_survey_is_too_small_to_load` | Holiday 2026 (262) now compares with 2025 (239), 343 days apart. Left out pending your confirmation: Amazon Apparel Annual Tracker 2026 (494), and 391 / 97 for social media (different study type or title). |
| **ETL-07** A failed reload kept stale serving rows | `etl/forsta_etl.py:364-369`: when a load fails after its write, `serving.drop_wave` runs, so live and published screens agree. The weekly run also publishes after a failure (`weekly_forsta.py:139`). The legacy loader sets `loading`, `verified` or `failed` and drops serving rows on failure (`legacy_dwh.py:328`), which also covers **ETL-21** for legacy. | `test_a_reload_failing_after_its_write_takes_its_serving_rows_away` | — |
| **ETL-16** | `etl/publish.py:77-84`: if `build()` fails anywhere, `.build-*` is removed. | `test_a_publish_that_fails_midway_removes_its_folder` | — |
| **ETL-08** Run lock | `etl/loaders.py:22-50`: one `etl_lock()` (`GET_LOCK('cip_etl')`, `wait_timeout` 7 days on its session, yields the connection). It is used by `weekly_forsta.main` (and pinged every watch cycle), all `forsta_etl` write modes including `--reindex`, `serving`, `cube`, `legacy_dwh`, `publish`, `integrity` (heal mode), `harmonise --confirm-same-wording` and `rekey_respondents`. It is a no-op on SQLite. | covered through every CLI test path (SQLite) | Not covered: `api/dashboards.py --build` and the Streamlit Mappings page (not my files, see §4). |
| **ETL-09** | `scripts/weekly_forsta.py:118-125`: every newly loaded wave is reconciled value by value against Forsta (one GET), and differences or `checked == 0` count as integrity problems. `forsta_etl.reconcile_all` (`:572`) treats `checked == 0` as a failure. | `test_reconcile_fails_a_wave_nothing_could_be_checked_on` | — |
| **ETL-17** Schedule ended 11 Jan 2027 | `etl/launch_schedule.py:106-119` `plan_weeks()`: the workbook's Mondays come first. After them, every Monday counts as planned except `skip:` dates (in `config/launch_schedule.yml`, kept by `--import`), up to 8 weeks ahead. `write_launchd` now writes `Weekday 1 17:30` plus Friday 09:00, with no dates. The repo plist `scripts/launchd/com.coresight.cip-forsta-etl.plist` has been regenerated. The installed copy in `~/Library/LaunchAgents` is not touched (runbook step 9). | `test_past_the_workbook_every_monday_is_a_launch_except_the_skipped` | — |
| **ETL-19** | Alert subjects carry the count, for example "integrity check: 3 problems" or "published numbers moved in 2 publications" (`weekly_forsta.py:145,155`), so a new problem is not throttled for 6 h. `config/notify.yml` is unchanged: **the team distribution-list address is needed from you** for `failure:` and `tracker:`. | — | — |
| **ETL-22** | `forsta_etl.py:149`: a live wave that keeps failing stays `failed`, so `MAX_ATTEMPTS` applies. | existing `test_a_wave_that_keeps_failing_…` | — |
| **DB-06** 18,968 qualified respondents without a profile | Root cause, from read-only checks: **no code bug in profile building; the source has no demographics.** The 41 waves are 10 Forsta B2B client studies (no consumer demographics asked), 10 Qualtrics tracker waves from Aug–Oct 2022 (10–15 questions, none demographic; 14 and 16–19 have none at all), and 21 SurveyMonkey waves with no `dwh_smdemography` rows. Survey 261 (n=2) is excluded anyway. The defect was downstream: the cube's blank cut value (`''`) was served as a segment equal to Total. Fix: `serving.cube_rows` (`:139`) leaves out `dim_value = ''` for non-total cuts. | `test_a_real_load_stores_answers_…` (updated: no blank segment) | There is no profile backfill possible, because the source holds no data to backfill. The "backfill" is the serving rebuild (runbook step 5). |
| **DB-03 / ETL-14** | `etl/records.respondent_key` already writes HMAC(salt, sha256(id)) once `CIP_RESPONDENT_SALT` is set. `scripts/rekey_respondents.py` now: HMAC(salt, existing key), a `--dry-run` flag, the run lock, a SQLite path (no UPDATE…JOIN there), and a run-once marker. **Not run.** | `test_rekeying_turns_every_stored_key_into_the_salted_one_new_loads_write`: rekeyed keys equal what a salted load writes, and a second run is a no-op | — |
| **DB-02** IPs | Statement written, not run (runbook step 11). | — | Live: 161,734 non-null `dwh_smresponse.ip_address` (the audit counted 79,626 IPv4). |
| **DB-09** | `sql/002_views.sql`: `load_status = 'verified'` added to `v_cip_answers`, `v_cip_item_incidence`, `v_cip_single_distribution`, `v_cip_grid`, `v_cip_crosstab`, `v_cip_trend`, `v_cip_survey_health`, `v_cip_question_base` and `v_cip_mapping_queue`. **Not applied.** | the suite builds the views on SQLite | — |
| **ETL-23** (narrow form, added 23 Oct 19:25 during go-live) | Reloading 97 with `relabel()` left the old list's rows as empty duplicates ("YouTube 0 %" under "YouTube 47 %"), because `load_definitions` never removes a row and the loader writes "not chosen" zeros for every listed row. `etl/loaders.py drop_unlisted_items()` runs after the answers write in both loaders (`forsta_etl.load_survey`, `legacy_dwh._load`): a row the questionnaire no longer lists **and nobody chose** (no code ≠ 0, no number, no text) is deleted, with its zeros. Rows with real answers and the pipeline's virtual questions are never touched. | `test_a_reload_removes_the_empty_answers_the_old_list_left` (load with the old list, reload with the fix) | Live: 97 removed 16 rows, 201 removed 2; 97 still 181,818 answers; Q7 serves 12 unique answers, Facebook 818 (63.3 %), YouTube 612 (47.3 %). |
| Not done | ETL-13 (RIWI weeks), ETL-15 (time zones), ETL-23 in full (removing a dropped row that still holds answers), ETL-12 (tenancy). | | |

### 1.1 Legacy label scan (read-only, per wave, 23 Oct)

Method: for every answer id whose responses all carry one text, compare that text, with HTML tags stripped, against the `dwh_smanswer` title.

Result: see the appendix line **SCAN** at the end of this file.

`relabel()` changes labels only where that comparison differs. A reload is needed to take effect.

## 2. Notes for the other agents (files I do not own)

- **Backend (`app/core/schema_upgrade.py`)**: `srv_wave.in_field` and the `sig_prior` / `sig_ly` SET members are already added. Still missing: `('cip_forsta_survey','load_state', "ENUM('new','due','loaded','failed','hibernated','testing','too_small') …", 'too_small')` in `WIDEN`, plus `009` in `SQL_FILES` if wanted. Until then `discover` falls back to `testing` (via `schema_has`).
- **Backend (`app/data/payloads.py`)**: `TEST_BASE` could import `etl.serving.TEST_BASE` (one source). `srv_answer` still stores `''` cut values, so `question_cuts` and `people` should skip `''` the way `srv_result` now does (DB-06). Waves with no `srv_wave` row (excluded or too small) are absent from the picker automatically.
- **Backend (`api/dashboards.py --build`) and `app/pages/7_Mappings.py`**: wrap writers in `etl.loaders.etl_lock()`. Mappings decisions now rebuild serving through `cube.refresh_cohorts`, which takes about 15–40 s per decision from India.
- **Frontend**: tokens `sig_prior` / `sig_ly` on Total rows, `srv_wave.in_field`, and launch weeks past the workbook with `names: ["Weekly tracker"]`, with `cycle` repeating the last workbook cycle.

## 3. Apply to live data (needs user approval)

Run these in order, from the repo, with `.venv/bin/python`. **Do not start any step while an ETL run holds the lock** (check `logs/etl-heartbeat.json` state = `finished`). Every step takes the lock itself. Nothing here touches :8000 or cloudflared. Timings are from India over the Azure link, about 250 ms per round trip.

1. **DDL 009 + views (2 min).**
   ```
   mysqldump --no-data <conn> cip_stg srv_result srv_wave cip_forsta_survey > backups/pre-009-schema.sql
   mysql <conn> cip_stg < sql/009_serving_flags.sql
   mysql <conn> cip_stg < sql/002_views.sql
   ```
   Rollback: `ALTER TABLE srv_wave DROP COLUMN in_field;`. Re-`MODIFY` `flags` and `load_state` to the definitions in `sql/005_serving.sql` / `sql/001_schema.sql`, but only once no row holds `sig_*` or `too_small`: `UPDATE srv_result SET flags = REPLACE(REPLACE(flags,',sig_prior',''),',sig_ly','')` first. Restore the views with `git show HEAD:sql/002_views.sql | mysql …`.
2. **Family remap of loaded annual waves (seconds).** This is `config/survey_map.yml family:` applied to rows already loaded:
   ```sql
   UPDATE cip_survey SET survey_family='HOLIDAY_SHOPPING' WHERE source_ref IN ('311513587','SV_5iEwVt7DCv68iMK','selfserve/58f/holiday','selfserve/58f/260905');
   UPDATE cip_survey SET survey_family='ONLINE_GROCERY' WHERE source_ref IN ('131312996','SV_eLIemMjZOqoobj0','SV_b2b9j6XNAtY0F4G','SV_6uot1ZQiKKsjdqe','selfserve/58f/260503');
   UPDATE cip_survey SET survey_family='APPAREL_SHOPPING' WHERE source_ref IN ('165769350','277793435','302343805','318304837','SV_0eweRRhLaBQ1kq2');
   UPDATE cip_survey SET survey_family='BACK_TO_SCHOOL' WHERE source_ref IN ('309290717','506778513','SV_8GuBh4A7c34vOBw','selfserve/58f/bts25');
   UPDATE cip_survey SET survey_family='SHOPPING_AND_SOCIAL_MEDIA' WHERE source_ref IN ('272687358','302456615');
   ```
   Rollback: first save `SELECT survey_id, survey_family FROM cip_survey WHERE source_ref IN (…)` to `backups/families-20261023.csv`, then write the old values back.
3. **Auto-confirm same-wording proposals (≈10–20 min, 350 waves).**
   ```
   python -m app.data.harmonise --confirm-same-wording           # expect 1322 units in 350 waves
   python -m app.data.harmonise --confirm-same-wording --apply
   ```
   Rollback: `UPDATE cip_concept_map SET status='proposed', reviewed_by=NULL, reviewed_at=NULL WHERE reviewed_by='auto:same_wording' AND concept_option_id IS NULL; DELETE FROM cip_concept_map WHERE reviewed_by='auto:same_wording' AND concept_option_id IS NOT NULL;`. The concept options it added stay, which is harmless.
4. **Reload the two malformed legacy waves (≈3–5 min each).**
   ```
   python -m etl.legacy_dwh --id SV_414ROr6xamluGNg     # survey 97
   python -m etl.legacy_dwh --id SV_3VmPUvYk4kj76PY     # survey 201
   ```
   Rollback: `git stash` the `relabel` change and reload the same ids. That reproduces today's rows.
5. **Serving rebuild of every wave (≈25–45 min at `--jobs 4`; 371 waves at 12–20 s each).**
   ```
   python -m etl.serving --all --jobs 4
   ```
   Rollback: check out the previous `etl/serving.py` and run the same command again. The published files are untouched until step 7.
6. **Integrity confirmation (read-only, ≈3–5 min).**
   ```
   python -m etl.integrity --check
   ```
   Then these SELECTs:
   ```sql
   -- every served wave: rows = reportable cube cells (expect 0 rows)
   SELECT w.survey_id FROM srv_wave w WHERE w.rows_built <> (SELECT COUNT(*) FROM cip_agg_cell c JOIN cip_question q ON q.question_id=c.question_id AND q.is_technical=0 AND q.is_virtual=0 WHERE c.survey_id=w.survey_id AND c.cohort_id IS NULL AND c.base_n>0 AND (c.dim='total' OR c.dim_value<>''));
   -- survey 97 Q7: expect Facebook 818 (63.3 %), YouTube 612 (47.3 %), Instagram 397, TikTok 394, Pinterest 275, Twitter 265; no duplicate labels
   SELECT item_label, n, base_n, pct FROM srv_result WHERE survey_id=97 AND qcode='Q7' AND dim='total' ORDER BY sort_order;
   -- harmonisation reached serving (expect >0 on 415/412) and sig flags exist
   SELECT survey_id, SUM(concept_option_id IS NOT NULL), SUM(FIND_IN_SET('sig_prior',flags)>0), SUM(FIND_IN_SET('sig_ly',flags)>0) FROM srv_result WHERE survey_id IN (415,412) GROUP BY survey_id;
   -- excluded / tiny waves are gone from serving (expect 0)
   SELECT COUNT(*) FROM srv_wave WHERE survey_id IN (394,382,261);
   ```
   Expected from today's dry run: 415 → 11,727 concept rows, 6 `sig_prior`, 7 `sig_ly`.
7. **Publish (≈15 min: a full rebuild, since every wave's `built_at` changes).**
   ```
   python -m etl.publish
   ```
   Rollback: `python -m etl.publish --rollback`, which points `current` at the previous version.
8. **Dashboards build.** `python -m api.dashboards --build <DASHBOARD>` for each code in `config/dashboards.yml` (api/dashboards.py, backend-owned), then step 7 again (≈1 min incremental) so the files carry them. Rollback: the previous `cip_dash_published` rows stay until replaced. Rebuild from the old commit.
9. **launchd plist (ETL-17).** Do this before 11 Jan 2027; it is harmless now.
   ```
   cp scripts/launchd/com.coresight.cip-forsta-etl.plist ~/Library/LaunchAgents/
   launchctl unload ~/Library/LaunchAgents/com.coresight.cip-forsta-etl.plist
   launchctl load ~/Library/LaunchAgents/com.coresight.cip-forsta-etl.plist
   ```
   This affects the ETL job only, not `cip-api`. Rollback: copy back `git show HEAD:scripts/launchd/com.coresight.cip-forsta-etl.plist` and reload.
10. **Salt migration (DB-03, about 1 min).**
    - Set `CIP_RESPONDENT_SALT` (32+ random bytes, `python -c "import secrets;print(secrets.token_hex(32))"`) in `.env` **and** `~/.config/cip/api.env`.
    - Keep a copy of the salt in a password manager: it cannot be recovered.
    - **Immediately**, with no ETL run in between:
      ```
      python scripts/rekey_respondents.py --dry-run
      python scripts/rekey_respondents.py
      ```
    - The API reads the env only at restart. It does not use the salt, so no restart is needed.
    - Rollback: before running, `mysqldump <conn> cip_stg cip_respondent --where="respondent_key IS NOT NULL" --no-create-info > backups/respondent_keys_pre_salt.sql` (columns `respondent_id, respondent_key`). Restore with an UPDATE from it, then `DELETE FROM cip_load_state WHERE feed_name='respondent_key_salted'` and unset the salt.
11. **Null plaintext IPs (DB-02, irreversible).**
    ```sql
    UPDATE cip_stg.dwh_smresponse SET ip_address = NULL WHERE ip_address IS NOT NULL;   -- 161,734 rows
    ```
    Rollback: none by design. If you want one, export `id, ip_address` to an encrypted off-database file first. Keeping them in the database defeats the purpose.
12. **Check the public link** returns 200 on `/healthz` (no step above restarts anything).

**Important: what the scheduled run does if steps 1–5 are not applied before Monday 26 Oct 17:30 IST.**
- The new code runs safely without 009: no `sig_*`, no `in_field`, and `testing` instead of `too_small`.
- The integrity check heals up to 20 recently built waves per run by rebuilding their serving rows with the new code (about 15 s each). That is a gradual form of step 5.
- Annual and ad hoc studies no longer load while fielding.

## Appendix

SCAN (23 Oct, read-only, per wave over all 287 Qualtrics and SurveyMonkey waves): answer ids whose one response text differs from the listed title once HTML, spacing and entities are ignored: **SV_414ROr6xamluGNg (97): 8 answers, 3,206 picks · SV_3VmPUvYk4kj76PY (201): 88 answers, 8,029 picks · nothing else.** A first pass without the HTML rule flagged 49 SurveyMonkey waves (368 answers), which are all markup only, such as `In-store<em> only</em>`. That is why `relabel()` compares letters and digits only and leaves those waves' labels unchanged.
