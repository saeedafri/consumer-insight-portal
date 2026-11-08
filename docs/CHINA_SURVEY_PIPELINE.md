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

Waves are family `CSI-CN`, country `CN`, platform `baidu`, named by the Monday of the first submit. Weekly-tracker views
built for the US (the weekly report, sector databank, expected vs actual, the public home page's figures, the
library's "latest tracker wave") stay on `CSI-US`.

Measured on this Mac (SQLite): a week loads in ~0.9 s, the incremental publish in under a second, published China
files are served in 2-3 ms.

## The analysts' English converter ("Consumer Tracker English.xlsx")

Good as a source of wording, not usable as the mapping itself:

- **It has no Chinese in it.** Its rows line up with the topline by position only.
- **Q8 and Q9 are in a different order from the Chinese.** 积极 (positive) sits next to "Pessimistic" and 消极
  next to "Optimistic". Mapped by position, every optimist would load as a pessimist.
- Smaller errors: S2 says "58-76" where respondents read 57-76; Q7's 没有变化 is "No change", not "Same as now";
  S5's wording is half Chinese; Q1 says "discretionary retail and service things" for 日常消费品和餐饮 (everyday
  consumer goods and dining); Q2 adds "because of coronavirus concerns", which respondents never read; stray
  "+A29:C36" text, routing notes in answers ("(move to Q3)"), stale counts (804).

So the codebook keys every answer by its exact Chinese text, uses the converter's English, and fixes the errors above.
To change a wording, edit `config/china_codebook.yml`. A new answer goes at the end of its list, so the codes already
loaded keep their meaning.

## Option 1: pulling the files from SharePoint (needs IT)

Not built yet; the upload page works today. When IT grants the access below, a small job in `deploy/etl-loop.sh`
can watch one folder, pair each week's raw file with its topline and call the same `load()`. The checks, refusals and
Teams alerts would be the same as for an upload.

What to ask IT for (Microsoft Entra ID + Microsoft Graph, app-only, least privilege):

1. **An app registration** in the Coresight tenant, e.g. "CIP – China survey reader", single tenant.
2. **API permission: Microsoft Graph `Sites.Selected` (Application)**, with admin consent. On its own this grants
   nothing. Then a SharePoint/Global admin grants the app the **`read`** role on **the one site** that holds the folder
   (`POST https://graph.microsoft.com/v1.0/sites/{site-id}/permissions` with `"roles": ["read"]`). Grant **`write`**
   instead only if CIP should move processed files into a "Loaded" subfolder. If the tenant supports it, the narrower
   `Lists.SelectedOperations.Selected` limits the grant to the one document library.
3. **A credential**: a certificate (preferred) or a client secret with an expiry date and an owner for its renewal.
   It goes in the App Service settings or Key Vault, never in the repository.
4. **The details**: tenant ID, the app's client ID, the site URL, the library and folder path, and the file naming the
   analysts will follow (for example `YYYY-MM-DD raw.csv` and `YYYY-MM-DD topline.xls`).
5. **Network**: outbound HTTPS (443) from the App Service to `login.microsoftonline.com` and `graph.microsoft.com`.

Not needed, and best refused: `Sites.Read.All` or `Files.Read.All` (every site in the tenant), delegated permissions
or a person's account, and SharePoint's legacy app-only (Azure ACS) registrations, which Microsoft has retired for
SharePoint Online.
