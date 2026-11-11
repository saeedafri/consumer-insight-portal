# China Consumer Survey: how a week gets into CIP

The China survey is fielded on Baidu QSS (百度智能云问卷), which has no API reachable from outside China. Each week an
analyst downloads two files from Baidu and an admin loads them on the **Upload survey** page (`/app/ingest`).
The questions never change between weeks; only the respondents do.

## The two files

| File | What it is | Format |
|---|---|---|
| Raw export ("Original 7.csv") | one row per respondent: masked user id, time taken ("159秒"), submit time ("10/21/26 22:19"), five blank panel fields, then one column per question, or per answer for a multiple choice | CSV in GB18030 (Simplified Chinese), or the same table saved as .xlsx |
| Topline ("Consumer Tracker_ 2026-11-05.xls") | per question, each answer's count and "答题人数：n" (who answered) | Excel 97 .xls |

Files downloaded from SharePoint may end in `.aspx` ("Original 7.csv.aspx"); the page and the API accept them.

## What happens on Check and Publish

1. **Check** (`POST /api/v1/admin/survey/preview`, writes nothing): the raw rows are translated through
   `config/china_codebook.yml` and counted; every base and every answer count is compared with Baidu's topline
   (123 figures a week). Any wording the codebook lacks, a missing question, or one count off is listed, and Publish
   stays off. A raw file paired with another week's topline fails here.
2. **Publish** (`POST /api/v1/admin/survey/publish`): the same check, then the load in the Forsta pipeline's order
   (`etl/baidu_qss_export.py load`): definitions → respondents and answers → profiles (gender, age, income, city tier)
   → question bases → harmonised concepts → cube → search → serving rows → Baidu's topline into `cip_crosstab`
   (as printed, one Total column, beside CIP's figures) → the following week's comparisons. A failure
   leaves the previous version of that week in place. Then `python -m etl.publish` runs in the background; it rebuilds
   only the new wave and the CSI-CN trends and links everything else from the live version. If a scheduled run holds
   the ETL lock, it is tried again every 5 minutes for half an hour; meanwhile the API builds the new wave's pages.
3. Uploading the same week again replaces it. The two source files are kept in `CIP_UPLOAD_DIR` (default `data/uploads`).

Waves are family `CSI-CN`, country `CN`, platform `baidu`, named as the analysts name them: "Survey of Oct 26" was answered on 3 Nov, so a wave is the Monday of the week before
its first answer (true for all four October 2026 folders); from SharePoint the folder's own name decides. Weekly-tracker views
built for the US (the weekly report, sector databank, expected vs actual, the public home page's figures, the
library's "latest tracker wave") stay on `CSI-US`.

Measured on this Mac (SQLite): a week loads in ~0.9 s, the incremental publish in under a second, published China
files are served in 2-3 ms.

## Translation

Since 11 Nov 2026 the English is the analysts' own dictionary (`zh_en_dictionary.json`, keyed by the Chinese like
the codebook), except the age and city-tier labels the cuts need (see the codebook's header). The older positional
converter, "Consumer Tracker English.xlsx", is not used:

- **It has no Chinese in it.** Its rows line up with the topline by position only.
- **Q8 and Q9 are in a different order from the Chinese.** 积极 (positive) sits next to "Pessimistic" and 消极
  next to "Optimistic". Mapped by position, every optimist would load as a pessimist.
- Smaller errors: S2 says "58-76" where respondents read 57-76; Q7's 没有变化 is "No change", not "Same as now";
  S5's wording is half Chinese; Q1 says "discretionary retail and service things" for 日常消费品和餐饮 (everyday
  consumer goods and dining); Q2 adds "because of coronavirus concerns", which respondents never read; stray
  "+A29:C36" text, routing notes in answers ("(move to Q3)"), stale counts (804).

So the codebook keys every answer by its exact Chinese text.
To change a wording, edit `config/china_codebook.yml`. A new answer goes at the end of its list, so the codes already
loaded keep their meaning.

## The weekly report: the analysts' calculations

Every China week gets a report (`/app/w/<id>/report`, "China weekly report" in the menu), built by the same engine as
the US one (`etl/weekly_report.py`) from `config/china_weekly_report.yml` when the week is published. It reproduces the
analysts' monthly China CSI deck (2025-2026: Figures 1-13 and the appendix) and their aggregation workbook
("Aggregated data", tabs Consumer Sentiment, Activities, Offline store, Online store, Spending, Avoidance):

| Workbook / deck | Formula | In CIP |
|---|---|---|
| weekly % | count / who answered | every week checked against Baidu's own topline first |
| 4WRA | `=AVERAGE(4 weekly %)` | `rolling()`: the mean of four weekly %s, a week missing gives none |
| Weekly PPT change | `=100*(this week - last week)` | `week_change` (four-week averages), `weekly_week_change` (single weeks) |
| Four-Week PPT change | `=100*(this week - 4 weeks before)` | `quarter_change` / `weekly_change`, `change_weeks: 4` |
| Net optimism | `=positive - negative` | Q8 (personal finances), Q9 (economy), Q7 (against a year ago) |
| CI | `=CONFIDENCE.NORM(0.05, SQRT(p(1-p)), n)` | the methodology's margin of error at 95 % |

Checked on the Sep 2026 deck (`tests/test_weekly_report.py`): net economic optimism 43.7 % on Aug 31 and 38.6 % on
Sep 28, 31.1 % that week; personal finances 40.4 % to 35.2 %, 30.9 %. Two faults of the workbook are not repeated: from
Jun 2024 to Jul 2026 most rows of Activities and Offline store carry another answer's figures (rows re-sorted after the
formulas were written; 7,646 of 9,214 weekly figures agree once rows are matched by their values, the rest are the
2023-24 weeks the analysts weighted), and the Four-Week Change columns still read January or July 2026.

Checked against every number of the 22 monthly decks from Dec 2024 to Sep 2026 (34,198 chart points and table cells):
95.0 % equal to CIP's to the deck's printed decimal; six decks equal in every number (Apr, May, Jun, Jul, Aug, Oct
2025). The rest, each traced: 2.1 % sit on another answer's row label and 0.6 % under a title of the other averaging
(Feb 2026's "four-week" in-store table prints the single weeks); 0.7 % are Nov 18 2024, which numbers its questions
differently, or four-week averages over it; 1.6 % match nothing in the SharePoint files, and where checked Baidu's own
crosstab agrees with CIP, not the deck (Apr 6 2026: Watched TV 42.0 % in Baidu's crosstab and CIP, 40.8 % in the deck;
Mar 2 2026: Better 48.8 %, the deck 44.2 %). Jul 27 2026, missing at first, is filed as "2026/July/Survey of June 27".

Not in CIP: Figure 1's macro timeline (NBS PMI, outside the survey) and the month's extra questions (luxury, 618,
Singles' Day, AI), which the crosstab carries but the raw export does not keep in a fixed form; the loader skips them.

## The history (2023-2026)

The SharePoint folder holds 174 week folders from Dec 2022. 152 pass the check against Baidu's crosstab; loaded by
folder name (`etl/sharepoint_china.py folder_week`), that is 149 weeks from Oct 2023 to Oct 2026 with Nov 17 2025. Not loadable, and
left for a person: Dec 2022 to Jul 2023 month folders (several raw files, only weighted crosstabs), three corrupt or
mis-named files (Mar 19 and Apr 1 2024, Nov 27 2023), and Nov 18 2024, whose Singles' Day file numbers the tracker's
questions differently. Nov 17 2025 loads: its Singles' Day questions come first as Q1-Q17 and the tracker's follow, so
for each code the loader reads the block whose answers are the codebook's (`tracker_columns`). A folder named more
than three weeks away from its own answers is misnamed and the answers decide (`MISNAMED_DAYS`): "2026/July/Survey of
June 27" was answered from 28 Jul and loads as the week of Jul 27. Other names sit 7 or 14 days from the answers: the
analysts named a week by its fielding Monday until 2025 and by the week before since. The loader reads files re-saved in a UK-set Excel (day-first, zero-padded dates) and the
2023-24 wordings (`older_wordings` in the codebook).

## Every way a week gets in

All four end in the same `load()` and the same check against Baidu's crosstab; they differ only in what starts it.

| Way | What starts it | Delay | What IT grants | CPU / RAM |
|---|---|---|---|---|
| A. Upload survey page | an admin, by hand | at once | nothing | the load only |
| B. Timed check | `deploy/etl-loop.sh`, every 10 minutes | at most 10 min | `Sites.Selected`, read, one site | a pass with nothing new: ~60 small Graph reads, under 1 s of CPU, a few seconds of ~80 MB |
| C. Power Automate calls CIP | a flow "When a file is created in a folder" on the China folder | under a minute | `Sites.Selected` for the pull (as B), and a Power Automate HTTP action (premium licence) | nothing while no file arrives |
| D. Microsoft Graph webhook | Microsoft, on any change in the site's Documents library | usually under a minute (Microsoft's stated maximum: 6 hours) | `Files.Read.All` (every file in the tenant), a public address | nothing while no file arrives; one pass per minute at most |
| E. Power Automate uploads the files | a flow that sends both files to `POST /api/v1/admin/survey/publish` | under a minute | no Graph permission at all; a CIP API key of an admin, and the HTTP action | the load only |

C and D call `POST /api/v1/admin/sharepoint/notify` (api/ingest.py). It needs no sign-in: it checks a shared secret
(`CIP_SP_WEBHOOK_SECRET`, 32+ characters) and only leaves a note, `data/sharepoint.wanted`, which the scheduler turns
into one pass of B within a minute, however many calls came. Once the secret is set the timed check runs hourly only,
as a safety net for a missed call. Without the secret the address answers 404.

**Recommended: B and C together.** Least privilege (one site, read only), a new week within a minute, and the hourly
check catches anything the flow misses. D works too, but Microsoft does not allow `Sites.Selected` for SharePoint
subscriptions, and only on a whole library (every change on the site calls CIP), so it needs tenant-wide read.

### What every SharePoint way does on a pass (B, C, D)

1. signs in as the app (client credentials) and walks the China folder: year → month → week folders, one Graph call
   per folder (~60 a year, a few seconds from Azure);
2. in each week folder takes the one `.csv` (raw) and the one `.xls` (crosstab); `_EN.xlsx` translations are ignored;
3. skips the pair if this exact version was already loaded or refused (its file ids and eTags are the `source_ref` of
   its row in `cip_load_log`): a replaced file has a new eTag, so a corrected week reloads by itself;
4. loads it with the same `load()` and checks as the upload page, named by the folder ("2026 / Survey of Oct 26" is
   2026-10-26). A pair whose figures differ from the crosstab is not loaded and emailed once to the failure list;
   a load posts one line to Teams;
5. after any load rebuilds the published files, so the week is in the survey list within minutes.

### What to ask IT for

For B (and C, D), Microsoft Entra ID + Microsoft Graph, app-only:

1. **An app registration** in the Coresight tenant, e.g. "CIP – China survey reader", single tenant.
2. **API permission: Microsoft Graph `Sites.Selected` (Application)**, with admin consent. On its own it grants nothing;
   a SharePoint or Global admin then grants the app **`read`** on the **CoreSightResearch** site only
   (`POST https://graph.microsoft.com/v1.0/sites/{site-id}/permissions`, `"roles": ["read"]`). Read is enough: CIP
   never changes the analysts' files.
3. **A client secret** (24 months, with a named owner for renewal), stored as an App Service setting, never in the
   repository. A certificate works too if IT prefers; tell us and the sign-in changes to it.
4. **The settings** on csr-awa-cip-portal-stg (and later production): `CIP_SP_TENANT_ID`, `CIP_SP_CLIENT_ID`,
   `CIP_SP_CLIENT_SECRET`, `CIP_CHINA_SITE=coresightresearch.sharepoint.com:/sites/CoreSightResearch` and
   `CIP_CHINA_FOLDER` = the folder's path inside the site's Documents library (e.g. `China CSI`; IT or the analysts can
   read it from the folder's Details pane).
5. **Network**: outbound HTTPS (443) from the App Service to `login.microsoftonline.com` and `graph.microsoft.com`.

For C, also:

6. `CIP_SP_WEBHOOK_SECRET` = a random value of 32+ characters (e.g. `openssl rand -hex 32`), in the App Service and,
   as a secure input, in the flow.
7. A flow owned by a service account with read on the China folder: trigger **SharePoint, "When a file is created in a
   folder"** (site CoreSightResearch, the China folder, "Include subfolders" on), action **HTTP**: `POST
   https://<portal>/api/v1/admin/sharepoint/notify`, header `X-CIP-Secret: <the secret>`, no body. The HTTP action is a
   premium connector: the flow's owner needs a Power Automate Premium (or per-flow) licence.

For D, instead of 2 (or beside it):

6. **Microsoft Graph `Files.Read.All` (Application)**, with admin consent: read on every file in the tenant.
7. `CIP_SP_WEBHOOK_SECRET` as in C, and `CIP_SP_WEBHOOK_URL=https://<portal>/api/v1/admin/sharepoint/notify`.
   The scheduler creates the subscription after each start (Microsoft first calls the address with a
   validationToken, answered by api/ingest.py) and renews it daily; Microsoft ends one after under 30 days.
8. **Network**: inbound HTTPS from Microsoft Graph to that address (it is outside the portal's sign-in).

For E: no IT grant. An admin creates a CIP API key (Account page) and the flow lists the week folder's files once both
are there, then sends `raw` and `topline` as multipart files to `POST /api/v1/admin/survey/publish` with
`Authorization: Bearer cip_…` (while staging's sign-in is the demo one, also `X-CIP-Admin-Token`). The flow, not CIP,
then decides when a week is complete; B or C is simpler to keep right.

Not needed for B or C, and best refused: `Sites.Read.All` or `Files.Read.All`, delegated permissions or a person's
account, and SharePoint's legacy app-only (Azure ACS) registrations, which Microsoft has retired.

To try it once the settings are in: `python -m etl.sharepoint_china --list` shows each week folder it sees and what it
would load, writing nothing; `python -m etl.sharepoint_china --subscribe` creates or renews D's subscription.
