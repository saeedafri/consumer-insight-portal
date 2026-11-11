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

## Option 1: picked up from SharePoint by itself (built; waits for IT's access)

`etl/sharepoint_china.py`, run by `deploy/etl-loop.sh` every 10 minutes (minutes 02, 12, … 52) once the settings below
exist. Each pass:

1. signs in as the app (client credentials) and walks the China folder: year → month → week folders, one Graph call
   per folder (~60 a year, a few seconds from Azure);
2. in each week folder takes the one `.csv` (raw) and the one `.xls` (crosstab); `_EN.xlsx` translations are ignored;
3. skips the pair if this exact version was already loaded or refused (its file ids and eTags are the `source_ref` of
   its row in `cip_load_log`): a replaced file has a new eTag, so a corrected week reloads by itself;
4. loads it with the same `load()` and checks as the upload page, named by the folder ("2026 / Survey of Oct 26" is
   2026-10-26). A pair whose figures differ from the crosstab is not loaded and emailed once to the failure list;
   a load posts one line to Teams;
5. after any load rebuilds the published files, so the week is in the survey list within minutes.

"Immediately" is at most 10 minutes. Graph change notifications (webhooks) could cut that to seconds, but need a
public endpoint and a subscription renewed every few weeks; not worth it for a weekly file.

What to ask IT for (Microsoft Entra ID + Microsoft Graph, app-only, least privilege):

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

Not needed, and best refused: `Sites.Read.All` or `Files.Read.All` (every site in the tenant), delegated permissions
or a person's account, and SharePoint's legacy app-only (Azure ACS) registrations, which Microsoft has retired.

To try it once the settings are in: `python -m etl.sharepoint_china --list` shows each week folder it sees and what it
would load, writing nothing.
