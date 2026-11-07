# Forsta API review: what is read-only, where CIP uses it, and corrections to the Gemini research

Checked 7 November 2026 against the Decipher REST API 1.0 specification (175 paths: 117 GET and 57 POST operations, the
file Gemini read), our live Forsta account (company 86, read-only calls on survey `selfserve/58f/261003`, the
2 November wave) and the CIP code and database (`cip_stg`, read-only queries). Every number below was measured, not
taken from the research.

## 1. Nothing CIP does changes a survey

- **In the code.** CIP talks to Forsta through one client, `etl/forsta_client.py`, whose only HTTP call is
  `session.get`. Every Forsta call in CIP goes through it. A test fails if anyone adds a POST, PUT, PATCH or DELETE, or
  calls Forsta from anywhere else: `tests/test_fieldwork.py::test_cip_only_ever_reads_from_forsta`.
- **On the live account.** Two read-only POSTs were run on survey 261003 (`crosstabs/execute` and `POST /data`) and
  the survey checked before and after: last survey edit (2 Nov 19:07:58), last edit, last quota edit, total (1,044) and
  qualified (403) were all unchanged. Forsta's audit log gained only access records ("API: POST
  surveys/<path:survey>/data in 167 ms", "Crosstabs: viewed report"): Forsta logs every API call, GETs included, and
  none of them is an edit.
- **Respondents.** Since 7 November CIP downloads and keeps every respondent (qualified, terminated, over quota and
  partial): nothing Forsta holds is discarded.

## 2. The POST operations that are read-only

Of the 57 POST operations, these compute or read and change nothing in the survey:

| Endpoint | What it does | Checked | Use in CIP | Where its results go |
|---|---|---|---|---|
| `POST /surveys/{survey}/data` | The data export, with the conditions and field list in the body (for lists too long for a URL) | Live: 200, 1.1 s, survey unchanged | Not needed today: CIP's GET export has no long conditions | The load, as now (`cip_respondent`, `cip_answer`) |
| `POST /surveys/{survey}/crosstabs/execute` | Forsta's own cross-tab: any tables, segments, filters, significance letters, in memory | Live: 200, 1.5 s, survey unchanged; q4 matches CIP to the person (Walmart 272, Dollar General 134, Sam's Club 68) | An independent check of every loaded wave: Forsta's totals against CIP's cube, shown as "Forsta agrees" on the Fieldwork screen | A new kind (`crosstab_check`) in `cip_forsta_record` beside the survey's other Forsta answers, published with the Fieldwork file |
| `POST /surveys/{survey}/crosstabs/saved/{saved}/execute` | Runs a report the research team saved in Forsta (261003 has 5) | From the specification | The team's own saved tables, reproduced in CIP next to each wave | `cip_forsta_record`, kind `saved_report:<id>` |
| `POST /surveys/{survey}/crosstabs/saved/{saved}/export/{format}` | Converts a saved report to Excel, PowerPoint or PDF and returns the file | From the specification | "Forsta's report" download for admins | `cip_forsta_record`, kind `saved_export:<id>` (the file, gzip-compressed) |
| `POST /bulk/bounced` | Checks a list of emails against known bounce-backs | From the specification | None: CIP sends no survey invitations | — |
| `POST /surveys/{survey}/samplesources/{listId}/verify` | Verifies signed survey links | From the specification | None: CIP does not build survey links | — |
| `POST /globalsearch/emails` | Finds participants who were sent a bulk email | From the specification | None: personal data, no analytical use | — |
| `POST /globalsearch/evars` | Finds participants by extra-variable values | From the specification | None: personal data, no analytical use | — |

**Not to be treated as read-only:**

- `POST /surveys/{survey}/evaluate` runs code inside the survey's environment. An expression only reads, but the
  endpoint runs whatever it is sent, so it is not safe to class as read-only.
- These sound harmless but do change something: `reports/media` (starts a job), `summary/share_link` (creates or
  revokes a link), `datafeed/{feed}/ack` (moves the feed on), `sst` (writes simulated respondents),
  `samplesources/{listId}/sign` (creates signatures), `logic/{label}/trigger` (runs survey code) and
  `distribute/email|ftp|slack` (sends data out of Forsta).
- Everything else (launch, close, archive, unarchive, data edits, campaigns, users, keys, translations, sections)
  writes, as its name says.

Since 7 Nov 2026 CIP sends three of these POSTs, and no other: `crosstabs/execute`, `crosstabs/saved/{saved}/execute`
and `crosstabs/saved/{saved}/export/{excel|pdf|pptx}` (`READ_ONLY_POSTS` in `etl/forsta_client.py`). `read_post()`
refuses any other endpoint before anything is sent, `tests/test_fieldwork.py` fails if a PUT, PATCH, DELETE or another
POST is added, and after a survey's saved reports are run `etl/fieldwork.py` re-reads the survey and logs an error if
its last edit or state moved. Checked live on 261003: last edit and audit log unchanged. The saved reports' tables and
Excel files are on the admin screen Forsta → Team reports. The other read-only POSTs need emails or links CIP does not
have, and `POST /surveys/{survey}/data` returns what CIP already reads with GET.

## 3. Every GET operation, and where CIP uses it

Status: **Added 7 Nov**: read every run by `etl/fieldwork.py` and kept verbatim, gzip-compressed, in the database
(`cip_forsta_record`, one row per survey and kind), shown where it says. **In CIP**: used by the load.
**Needs an id or a Forsta feature we do not use**: nothing to collect until one exists. **Not for CIP**: with the reason
(API keys, translations, campaigns, MaxDiff/conjoint and video are left out on purpose).

117 GET endpoints: 31 added 7 nov, 5 in cip, 0 recommended next, 16 needs an id or a forsta feature we do not use, 65 not for cip.

| Endpoint | What Forsta returns | Status | Where CIP uses it, or why not |
|---|---|---|---|
| `GET /archives/planned` | Get planned activities | Added 7 Nov | Same |
| `GET /archives/{company}/deleted` | Get archives deleted report | Added 7 Nov | Same |
| `GET /archives/{company}/deletion` | Get archives deletion report | Added 7 Nov | Kept: Forsta's deletion report |
| `GET /archives/{company}/deletion/data` | Get participant data deletion report | Added 7 Nov | Kept: participant data deletion report |
| `GET /archives/{company}/scheduled` | Get surveys scheduled to be archived | Added 7 Nov | Same |
| `GET /autoclose/planned` | Get a list of surveys visible to you that are scheduled to be automatically closed
within the specified number of days.
 | Added 7 Nov | Fieldwork deletion schedule: 'Planned by Forsta' (none today) |
| `GET /hibernation/status` | Get hibernation status | Added 7 Nov | Checked before each Fieldwork read: a hibernated survey is skipped, never woken |
| `GET /meta` | Get API metadata | Added 7 Nov | Kept each run: Forsta's own list of its endpoints, to spot new ones |
| `GET /rh/companies` | List companies | Added 7 Nov | Finds the company id (86) for the retention rule |
| `GET /rh/companies/{company}/crosstab-report-defaults` | Get crosstab preferences | Added 7 Nov | Kept: the company's cross-tab defaults |
| `GET /rh/companies/{company}/retention` | Get company data retention settings. | Added 7 Nov | Fieldwork screen: the company's deletion rule (365 days after archiving) |
| `GET /rh/surveys/archived` | Get a list of archived surveys | Added 7 Nov | Fieldwork screen: Forsta's deletion schedule, and which archived surveys CIP holds |
| `GET /rh/surveys/categories` | Get categories | Added 7 Nov | Kept; the survey's category on the 'In Forsta' card |
| `GET /rh/surveys/historical` | Get historical list | Added 7 Nov | Fieldwork screen: 'In Forsta, not in CIP' (12 surveys, mostly test copies) |
| `GET /rh/surveys/{survey}` | Get survey information | Added 7 Nov | Fieldwork screen: state, launch and close times, questions, last edit, retention |
| `GET /rh/surveys/{survey}/audit-log` | Retrieve a survey's audit log | Added 7 Nov | Fieldwork timeline: duplicated, launched, closed, edited, permissions (reads left out) |
| `GET /rh/warnings/summary` | Get warnings summary | Added 7 Nov | Kept each run: every survey's warning counts in one call |
| `GET /surveys/{survey}/can-archive` | Check if survey can be archived | Added 7 Nov | Fieldwork 'In Forsta' card: whether and why not it can be archived |
| `GET /surveys/{survey}/crosstabs/configuration` | Get crosstabs configuration | Added 7 Nov | Kept: the research team's own banners and weight; next: offer them as Cross-tab banners |
| `GET /surveys/{survey}/crosstabs/saved` | List saved reports | Added 7 Nov | Fieldwork 'In Forsta' card: the research team's saved reports (5 for 261003) |
| `GET /surveys/{survey}/datasources` | List datasources | Added 7 Nov | Kept; count on the 'In Forsta' card |
| `GET /surveys/{survey}/files` | List files | Added 7 Nov | Kept: survey.xml and assets, size and last change |
| `GET /surveys/{survey}/files/{filename}` | Download file | Added 7 Nov | survey.xml kept; each question's display condition and the screen-out rules on the Survey preview |
| `GET /surveys/{survey}/layouts` | Retrieve all data layouts | Added 7 Nov | Kept; count on the 'In Forsta' card |
| `GET /surveys/{survey}/state/live/warnings` | Get launch warnings | Added 7 Nov | Kept: Forsta's launch checks; next: show on the Launch schedule for a wave about to launch |
| `GET /surveys/{survey}/summary/completions` | List completions | Added 7 Nov | Fieldwork screen: opened, partial, terminated, over quota, qualified, incidence, interview length |
| `GET /surveys/{survey}/summary/dropouts` | List drop-outs | Added 7 Nov | Fieldwork screen: where respondents dropped out, page by page, with seconds per page |
| `GET /surveys/{survey}/summary/splits` | List splits | Added 7 Nov | Kept in the Fieldwork record (fieldwork by split); to show next to the funnel |
| `GET /surveys/{survey}/tasks` | Get survey tasks | Added 7 Nov | Kept; open tasks on the 'In Forsta' card |
| `GET /surveys/{survey}/terms` | Get survey term elements | Added 7 Nov | Fieldwork screen: the screen-out rules behind 'terminated' (261003: two speeder checks) |
| `GET /surveys/{survey}/warnings` | Get warnings | Added 7 Nov | Fieldwork screen: blocked sessions, server errors, exceptions, quota misses |
| `GET /rh/companies/{company}/surveys` | Get surveys | In CIP | The survey register, every run (etl/forsta_etl.py discover) |
| `GET /rh/users/{user}` | Get user | In CIP | rh/users/self: the key check before each run (scripts/weekly_forsta.py) |
| `GET /surveys/{survey}/data` | Download data | In CIP | Every load: all respondents, all statuses (etl/forsta_etl.py), and the re-check against Forsta (_reconcile) |
| `GET /surveys/{survey}/datamap` | Retrieve datamap | In CIP | Every load: questions, answers, codes, grid labels (etl/forsta_etl.py); the Survey preview screen |
| `GET /surveys/{survey}/quota` | Get quota | In CIP | Fieldwork end detection and the launch watcher (cip_forsta_survey.quota_json); kept in the Fieldwork record |
| `GET /datafeed/{feed}` | Get new data | Needs an id or a Forsta feature we do not use | Needs a data feed set up in Forsta (a write): none exists |
| `GET /datafeed/{feed}/state` | Get feed state | Needs an id or a Forsta feature we do not use | Same |
| `GET /exceptions/search` | Find error | Needs an id or a Forsta feature we do not use | Needs an exception id: none logged (0 exceptions) |
| `GET /hello` | Hello there! | Needs an id or a Forsta feature we do not use | Liveness only: rh/users/self already checks the key |
| `GET /status` | Get task | Needs an id or a Forsta feature we do not use | Needs an async task id |
| `GET /status/content` | Get task content | Needs an id or a Forsta feature we do not use | Same |
| `GET /surveys/{survey}/coverage` | Execute coverage report | Needs an id or a Forsta feature we do not use | Needs segments chosen per run: a report to run on request, not to keep |
| `GET /surveys/{survey}/crosstabs/targets/{target}/settings` | Get crosstabs settings for a target | Needs an id or a Forsta feature we do not use | Needs a target id |
| `GET /surveys/{survey}/crosstabs/validate` | Validate logic | Needs an id or a Forsta feature we do not use | Checks a condition typed in: on request only |
| `GET /surveys/{survey}/datasources/{datasource}` | Get datasource | Needs an id or a Forsta feature we do not use | Needs a data source: none exist |
| `GET /surveys/{survey}/datasources/{datasource}/data` | List datasource data | Needs an id or a Forsta feature we do not use | Same |
| `GET /surveys/{survey}/edits/{edit}` | Get survey response edits | Needs an id or a Forsta feature we do not use | Needs an edit id; the audit log already records each data edit (wave 530: 2 rows deleted) |
| `GET /surveys/{survey}/files/headers` | Get file headers | Needs an id or a Forsta feature we do not use | Headers of uploaded files: none used |
| `GET /surveys/{survey}/layouts/{layout_id}` | Retrieve a single data layout | Needs an id or a Forsta feature we do not use | Needs a layout id: none exist for our surveys |
| `GET /surveys/{survey}/sample/{listId}/links` | Get participant sources | Needs an id or a Forsta feature we do not use | 404 for our sample source (114) |
| `GET /surveys/{survey}/tasks/{task_id}` | Get survey task | Needs an id or a Forsta feature we do not use | Needs a task id: no tasks |
| `GET /libraries/{company}/elements` | Get elements | Not for CIP | Same |
| `GET /libraries/{company}/elements/{eid}` | Get element | Not for CIP | Forsta's question library: programming, not data |
| `GET /libraries/{company}/surveys/{survey}/elements` | Get survey elements | Not for CIP | Same |
| `GET /misc/scoreboard` | Get light scoreboard | Not for CIP | 403 for our key |
| `GET /panels/{panel_id}/datapoints` | List panel datapoints | Not for CIP | Same |
| `GET /panels/{panel_id}/link` | Get link | Not for CIP | Same |
| `GET /panels/{panel_id}/registration` | Get registration survey | Not for CIP | Kinesis panels: Coresight does not use one (no panels on the company) |
| `GET /parameters/list/{survey}` | Get available project parameters | Not for CIP | Project parameters: programming settings |
| `GET /parameters/validate/{survey}` | Validate saved project parameters | Not for CIP | Same |
| `GET /parameters/{survey}` | Get saved project parameters | Not for CIP | Same |
| `GET /rh/apikeys` | List API Keys | Not for CIP | Returns API keys themselves: never stored or shown. Only an expiry warning would be safe |
| `GET /rh/apikeys/{apikey}` | Get | Not for CIP | Same |
| `GET /rh/companies/{company}/groups` | List groups within a company | Not for CIP | Forsta user groups |
| `GET /rh/companies/{company}/panels` | List company panels | Not for CIP | No panels on the company |
| `GET /rh/companies/{company}/preferences` | List company preferences | Not for CIP | Forsta account settings |
| `GET /rh/companies/{company}/preferences/{key}/history` | Get preference history | Not for CIP | Same |
| `GET /rh/surveys/current` | Get current surveys | Not for CIP | Empty for our key; the register uses rh/companies/{company}/surveys |
| `GET /rh/usage` | Calculate usage | Not for CIP | 403 for our key (and needs start and end) |
| `GET /rh/users` | List users | Not for CIP | Forsta's user directory: personal data of Forsta users, no use in CIP |
| `GET /rh/users/{user}/audit-log` | Retrieve a user's audit log | Not for CIP | A Forsta user's own activity: the survey audit log covers what CIP needs |
| `GET /rh/users/{user}/status` | Retrieve a user's status | Not for CIP | Same |
| `GET /rh/users/{user}/whiteboard` | Get whiteboard | Not for CIP | Same |
| `GET /schedule` | Get logic events | Not for CIP | Logic events: programming |
| `GET /surveys/{survey}/campaigns` | Get campaigns | Not for CIP | Email campaigns: the tracker's sample comes from a panel, not email invitations (none for 261003) |
| `GET /surveys/{survey}/campaigns/suppressions` | Get suppression lists | Not for CIP | Email campaigns: the tracker's sample comes from a panel, not email invitations (none for 261003) |
| `GET /surveys/{survey}/campaigns/suppressions/{suppression}` | Get suppression list | Not for CIP | Email campaigns: the tracker's sample comes from a panel, not email invitations (none for 261003) |
| `GET /surveys/{survey}/campaigns/{campaign}` | Get campaign | Not for CIP | Email campaigns: the tracker's sample comes from a panel, not email invitations (none for 261003) |
| `GET /surveys/{survey}/campaigns/{campaign}/invite` | Get Invite | Not for CIP | Email campaigns: the tracker's sample comes from a panel, not email invitations (none for 261003) |
| `GET /surveys/{survey}/campaigns/{campaign}/list` | Get list | Not for CIP | Email campaigns: the tracker's sample comes from a panel, not email invitations (none for 261003) |
| `GET /surveys/{survey}/campaigns/{campaign}/list/{send}` | Get email status list | Not for CIP | Email campaigns: the tracker's sample comes from a panel, not email invitations (none for 261003) |
| `GET /surveys/{survey}/campaigns/{campaign}/sends` | Get sends | Not for CIP | Email campaigns: the tracker's sample comes from a panel, not email invitations (none for 261003) |
| `GET /surveys/{survey}/campaigns/{campaign}/sends/{send}` | Get a send | Not for CIP | Email campaigns: the tracker's sample comes from a panel, not email invitations (none for 261003) |
| `GET /surveys/{survey}/campaigns/{listfile}/blocks` | Get campaign blocks | Not for CIP | Email campaigns: the tracker's sample comes from a panel, not email invitations (none for 261003) |
| `GET /surveys/{survey}/campaigns/{listfile}/bounces` | Get campaign bounce-backs | Not for CIP | Email campaigns: the tracker's sample comes from a panel, not email invitations (none for 261003) |
| `GET /surveys/{survey}/campaigns/{listfile}/optouts` | Get campaign optouts | Not for CIP | Email campaigns: the tracker's sample comes from a panel, not email invitations (none for 261003) |
| `GET /surveys/{survey}/campaigns/{listfile}/spam` | Get campaign spam reports | Not for CIP | Email campaigns: the tracker's sample comes from a panel, not email invitations (none for 261003) |
| `GET /surveys/{survey}/conjoint/report/{question_label}` | Get survey conjoint utilities | Not for CIP | Same |
| `GET /surveys/{survey}/conjoint/status` | Get survey conjoint statuses | Not for CIP | No conjoint questions (empty for 261003) |
| `GET /surveys/{survey}/dashboards` | List dashboards | Not for CIP | Forsta dashboards (none): CIP is the dashboard |
| `GET /surveys/{survey}/dashboards/{id}` | Get dashboard | Not for CIP | Same |
| `GET /surveys/{survey}/dqapi/{label}/hitrate` | Calculates the coefficients | Not for CIP | Same |
| `GET /surveys/{survey}/dqapi/{label}/mxd` | Output data in a format suitable for Sawtooth | Not for CIP | Same |
| `GET /surveys/{survey}/dqapi/{label}/tricked` | Output respondent data in so-called “tricked” format | Not for CIP | Same |
| `GET /surveys/{survey}/dqapi/{label}/{name}` | Call an DQ-specific API function | Not for CIP | MaxDiff/DQ functions: the tracker has no MaxDiff questions |
| `GET /surveys/{survey}/logic/{label}/debug` | Debug logic node | Not for CIP | Programming |
| `GET /surveys/{survey}/mls/application/data` | Get Language Manager application data | Not for CIP | Translations: the tracker is English only |
| `GET /surveys/{survey}/panels` | List kinesis panels | Not for CIP | Same (none linked) |
| `GET /surveys/{survey}/sections` | Get survey sections | Not for CIP | 400 for our surveys (no sections set up) |
| `GET /surveys/{survey}/sections/{section}/editor` | Get section's editor | Not for CIP | Programming |
| `GET /surveys/{survey}/sections/{section}/validate` | Validate survey section | Not for CIP | Programming |
| `GET /surveys/{survey}/state/warnings` | Get warnings | Not for CIP | 404 for our surveys; the launch checks come from state/live/warnings |
| `GET /surveys/{survey}/subscribers` | Get Survey Subscribers | Not for CIP | Who is subscribed to the project in Forsta: Forsta's own users, not CIP's |
| `GET /surveys/{survey}/summary/campaigns` | List campaigns | Not for CIP | Email campaign summary: the tracker uses panel sample, not email invitations |
| `GET /surveys/{survey}/summary/share_link` | Get share link | Not for CIP | The response summary's share link: a link into Forsta, not data |
| `GET /surveys/{survey}/test/token` | Get survey test URL token | Not for CIP | A test link into the survey |
| `GET /surveys/{survey}/users` | Get Survey Users | Not for CIP | Forsta users on the project: same |
| `GET /surveys/{survey}/users/{user}` | Get a Specific Survey User | Not for CIP | Same |
| `GET /surveys/{survey}/videos` | Get videos | Not for CIP | No video questions |
| `GET /surveys/{survey}/videos/{video_id}` | Get video | Not for CIP | Same |
| `GET /surveys/{survey}/videos/{video_id}/watermark_videos` | List watermarked videos | Not for CIP | Same |
| `GET /sysinfo` | Get system information | Not for CIP | 403 for our key |
| `GET /sysinfo/config` | Get system configuration | Not for CIP | 403 for our key |
| `GET /translation` | Get translations | Not for CIP | Same |
| `GET /translation/delta` | Get translation delta | Not for CIP | Same |
| `GET /translation/delta/reservation` | Get translation reservations | Not for CIP | Same |

## 4. Where the Gemini research is inaccurate

The research is a good map of the API, and several findings hold: the count of 117 GET operations, the
Forsta-versus-CIP cross-tab match, the drop-out figures (q1: 1,193 started, 69 dropped, 33.9 s), the 33.8 % incidence,
the 73 archived surveys, hibernated surveys answering 428 (260402 confirmed; the count of 12 not rechecked), and that rim weighting writes to Forsta. These do not hold:

| # | The research says | What is true | Evidence |
|---|---|---|---|
| 1 | The database is `dwh_stg` | It is `cip_stg` | `SELECT DATABASE()` on the connection CIP uses |
| 2 | `cip_answer.value_label` wastes 1.2 GB | It is empty: 0 of 320,045 rows in wave 532, 0 in seven of eight waves sampled, 52 of 92,351 in the eighth | Read-only count by wave |
| 3 | The `value_text` TEXT column bloats every row with off-page pointers | An empty TEXT column costs nothing in InnoDB's DYNAMIC rows (the table's format); about 1,300 of 320,045 rows hold text | `SHOW CREATE TABLE`; count of non-empty values |
| 4 | Hashing `cell_key varchar(200)` saves 417 MB | Keys average 38.5 characters (54 at most), so the saving is about 90 MB | Average key length, wave 532 |
| 5 | A natural primary key saves 1.1 GB | Only the `uq_answer` index goes; the other secondary indexes then carry a 12-byte key instead of 8 | InnoDB stores the primary key in every secondary index |
| 6 | Partition `cip_answer` by `survey_id` with the DDL given | The DDL fails: MySQL cannot partition a table with foreign keys (it has two), and every unique key must include `survey_id` (`uq_answer` does not). Its `TRUNCATE PARTITION` to reload one wave would delete about 20 | `SHOW CREATE TABLE cip_answer` |
| 7 | Cache `book.json.gz` for a year, public and immutable | A book changes when its wave is reloaded and its address does not change, so people would see stale numbers; "public" lets shared caches keep private data; the location pattern does not match the real address (`/api/v1/waves/<id>/book`) | `deploy/cip_locations.conf` |
| 8 | Phase 1 (`cond=qualified`) is done | It was not in the code when the research was written | `etl/record_stream.py` history |
| 9 | 60 % of rows are discarded during loading | They were stored, not discarded: 193,105 of 320,045 answer rows of wave 532 belong to non-qualified respondents | Read-only count by status |
| 10 | Survey 261003: 641 terminated and 149 drop-outs | 32 terminated (two speeder checks), 609 over quota, 149 partial, 403 qualified, 1,193 opened | `summary/completions` and `terms` |
| 11 | Median interview length 8.4 minutes | 6.0 minutes (361 s); the average is 7.3 (435 s) | `summary/completions` |
| 12 | The qualified-only export cuts 3.5 MB to 850 KB | 5.1 MB to 2.0 MB, 3.9 s to 0.7 s. Not adopted: nothing Forsta holds is discarded | Two GETs on 261003 |
| 13 | A field list can strip the unused columns | The load checks every datamap variable arrived (`verify`): a field list would have to name all of them, for little saving | `etl/forsta_etl.py` verify |
| 14 | API usage metering via `rh/usage` | 403 for our key (it also needs `start` and `end`) | Live GET |
| 15 | An audit and security centre from `sysinfo` | 403 for our key; `misc/scoreboard` too | Live GET |
| 16 | `hibernation/status` lists hibernation | It needs `survey=`: one survey at a time ("restored" or "hibernated") | Live GET |
| 17 | 7 read-only POST operations | 8 by the specification: `/bulk/bounced` and `samplesources/{listId}/verify` were missed; `evaluate` runs code and should not be counted | Section 2 |
| 18 | API keys can be shown and rotated from an admin panel | `rh/apikeys` returns the keys themselves; showing them in CIP would leak them, and rotating writes | Live GET (response not stored) |
| 19 | Unarchiving the hibernated surveys resolves the ticket | It does wake them, but it changes Forsta and is a paid action: excluded by the read-only decision | Specification |

Not checked here: the research's timings for a full 109-table cross-tab (2.01 s) and for the ETL phases (17.5 s).
