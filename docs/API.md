# CIP API and MCP connector: how to use them

The portal's data can be read by your own programs (the **API**) and by Claude or any AI assistant that supports
MCP connectors (the **MCP connector**). Both act as **you**: they see exactly what your menus show in the portal, no
more, at the moment of each request. This guide is also in the portal at **Account → API keys and MCP → Read the
API guide** (`/app/api-guide`); `tests/test_docs.py` fails if the two differ or if a route is missing from either.

## 1. Make a key

1. Sign in to the portal and open **Account** (top right) → **API keys and MCP**.
2. Type a name for the key (the tool it is for, such as "My Claude") and press **Make a key**.
3. Copy the key now: it starts with `cip_` and is shown **once**. CIP keeps only its fingerprint (SHA-256).

You can keep up to 10 keys and revoke any of them on the same card; a revoked key stops working at once. A key cannot
make or revoke keys: that needs your signed-in portal session.

## 2. What a key may read: the same rules everywhere

| Rule | What it means for a key |
|---|---|
| API keys and MCP | Only when "API keys and MCP" is on your menu: the super admin turns it on per role, client or person on the Access page. Without it the Account page has no keys card and every key you made is refused (403) until it is turned back on |
| Your role, client and menus | A key reads only what your left menu shows. The super admin chooses menus per role, per client and per person on the Access page; a person's choice beats their client's, which beats their role's |
| Changes apply within a minute | When a menu is taken away (a trial ends), your screens, your keys and the MCP connector lose it within a minute (most answers at once); no sign-out or refresh needed |
| Surveys | Only the surveys your organisation may see |
| Rate limit | The same per-minute limit as your sign-in; over it, the answer is `429` with `Retry-After: 60` |
| Admin pages | Never through a key: they need an admin signed in to the portal. Offboarding someone revokes their keys too |

## 3. The API

Send the key in the `Authorization` header to `https://<portal>/api/v1/…`:

```bash
curl -H "Authorization: Bearer cip_…" "https://<portal>/api/v1/waves"
curl -H "Authorization: Bearer cip_…" "https://<portal>/api/v1/search?q=holiday%20shopping"
curl -H "Authorization: Bearer cip_…" "https://<portal>/api/v1/waves/532/results?q=q4&dim=total,generation"
```

| Method and address | What it returns | Needs on your menu |
|---|---|---|
| `GET /api/v1/me` | You: email, role, client, features, permissions | — |
| `GET /api/v1/waves` | Every wave you may open, newest first | — |
| `GET /api/v1/waves/{survey_id}/book` | A whole wave: questions, answers and topic dashboards (the always-on Overview's data) | — |
| `GET /api/v1/waves/{survey_id}/results` | Finished rows for questions × cuts, `?q=XM3,XM1&dim=total,generation` | Question explorer |
| `GET /api/v1/waves/{survey_id}/crosstab` | One question by two cuts, `?q=XM3&by=generation,gender&weeks=4` | Cross-tab matrix |
| `GET /api/v1/waves/{survey_id}/report` | The weekly report of a tracker wave: US Consumer Survey Insights or China Consumer Survey Insights | Weekly report |
| `GET /api/v1/waves/{survey_id}/logic` | When each question was shown, and the screen-out rules | Survey preview |
| `GET /api/v1/questions/{family}/{study_type}/{qcode}` | One question across every wave and cut | Trends, Compare waves or Audiences (US weekly questions: or In store vs online) |
| `GET /api/v1/dashboards/{code}` | A topic dashboard for its latest wave | Topic dashboards |
| `GET /api/v1/dashboards/{code}/{survey_id}` | A topic dashboard for one wave | Topic dashboards |
| `GET /api/v1/search` | Questions by words, code, answer or survey, `?q=tariffs&limit=40` | Search questions |
| `GET /api/v1/glance` | This week at a glance: six cards from the newest wave of each weekly survey, US and China (US: the week's sector's leading retailer and top product; what is new this week, or the sector's median spend; China: the top activity, the top category bought online and the spending plans; both: the biggest change, the widest in-store vs online gap and the personal-finances outlook), leaving out a survey whose waves you may not open | Home |
| `GET /api/v1/sectors` | The sector databank: purchase rate, retailers, brands, categories, and the median spend band of each survey | Sector databank |
| `GET /api/v1/retailers` | Retailer databank: every weekly retailer and every sector's retailers, week by week since Jul 2025, as counts (shoppers, food, nonfood, gender, generation, income, region, area) plus sentiment (every sector module's retailer grid, named with its module), for any weeks chosen; each sector names its shoppers as titles say them (shoppers: "department store shoppers") | Retailer databank |
| `GET /api/v1/expectations` | Retail events, expected vs actual | Expected vs actual |
| `GET /api/v1/reports` | The waves that have a weekly report | — |
| `GET /api/v1/schedule` | The launch plan against what Forsta fielded | Launch schedule |
| `GET /api/v1/fieldwork` | Each survey's funnel and why respondents dropped out | Fieldwork |
| `GET /api/v1/methodology` | How the figures are made | — |
| `GET /api/v1/public/facts` | The home page's counts and dates (no key needed) | — |
| `POST /api/v1/ask` | A question in plain words, `{"question": "…"}` (add `"quick": true` for the answer by meaning and Ask's own reader, about 100 ms, no AI; its `check` says to ask again with `"check": true` for the AI model's reading, sent only when the reader is unsure and a key is set; `understood` says how it was read: `reader`, `model` (the AI), `meaning`, `name`, `named`, `verified`, `learned` or `rules`): the answer in sentences, a chart, every figure and its base, the source and other matching questions, with it `tiles` (up to three headline figures, each with its note), `takeaway` (what the figures tell, in one sentence) and `next` (up to three follow-up questions, each with its survey question `key`: send it back as `"key"` to answer from that same question); `chart.type` is the form that fits: `line`, `bar`, `grouped`, `split` (one whole in up to six parts), `stacked` (100% by group), `heatmap` or `dumbbell` (first against latest wave), and a chart by a cut carries each group's base in `bases` when the displayed figures use a common base; shares, counts, top answers, trends by wave, 2 weeks, 4 weeks, month, quarter or year, comparisons and cuts, from the surveys only; when two survey questions are too close to call it answers `"mode": "choose"` with them as `suggestions` instead of guessing; `corrected` is the question as answered when a misspelt word was put right ("subcription" is "subscription"). Table `cell_bases` aligns with the numeric cells of `rows` and uses null for unavailable figures. The older `bases` array gives the common column base, or zero when the column has no common base. The `scope` object gives the country, dates and number of survey waves used, and `base`: the people who answered the main figure (0 when the answer is by a group). Each source has `name`, the survey question's short name. A best match that misses the question's subject (every one of two or more of its words, three or more, or two with one that no survey uses) returns mode none with the closest questions as `suggestions`. A `headline` from a question last asked more than a year before the newest wave ends with “Last asked” and that date. Explicit requests for weighted figures or a count of people who selected both answers can return mode none with an explanation and no figures. A comparison also returns mode none when a named group has no reportable figures in a requested period. Send `"previous"` (the question the latest answer was for) and `"previous_key"` (its source key) with a typed question, and a follow-up such as "What about Gen Z?", "and by income?" or "what about Target?" is read with it: the answer's `asked_as` is the question as read. A summary question ("Summarize this week", "How do consumers feel?") returns `overview`: one line per weekly tracker question in config/weekly_report.yml `ask_overview` (`name`, `text`, `qcode`, `link`), the sentiment ones as net better, with every question in `sources`. Send `"weighted": true` (the page does when its Weighted switch is on), or ask for "Census-weighted" figures, for shares Census-weighted by gender, age and region for any group, two groups at once included, from each wave's respondents and their weights (the published respondent file); `weighting` says `weighted` or `unweighted`, and a note says why when a wave has no respondent file to weight. An answer from one wave adds the change since the wave before, tested, to `takeaway` and `tiles`. A question naming two kinds of group ("Gen Z women", "Amazon by generation and gender") is answered from the cross-tab figures of the latest 4 waves pooled, its `sources` link opening Cross-tabs; three or more kinds return mode none. A question asking how a tracked topic is doing ("How good is GLP-1 performing?", "How are tariffs and inflation trending?") is answered from that topic's dashboard (config/dashboards.yml `ask` words): `understood` is `topic`, the `headline` gives the verdict (rising, falling or holding steady: the headline figure's change since the dashboard's first wave, tested at 95%), `overview` lists its other figures, and the chart is the headline figure's trend. Every other answer also leads with its verdict: a clear lead or a close race, the group highest and by how much, rising, falling or steady over time, and a better/worse scale as its net. A question that joins survey questions for the same people ("among recent AI users, what share used GenAI to shop"), compares groups defined by another question's answers or by ages the survey does not cut by, asks for both / either / not, a funnel, a group across several weeks or a change tested between two weeks is answered from its plan, run on each week's respondents: `understood` is `plan`, and `read_as` lists how it was read (`label` and `value`: Counted, Among, Split by, Steps, Weeks). | Ask CIP |
| `GET /api/v1/ask/suggest` | What the Ask box offers while someone types, `?q=ama prim`: `corrected` (the words put right, or null) and `suggestions` (up to six survey questions whose analyst name holds the words typed, each with its `key`: send it with `POST /api/v1/ask` to answer from that question). From the index in memory, no AI, no cost | Ask CIP |
| `GET /api/v1/ask/history` | This person's own recent Ask CIP questions, newest first, each once and as read (a follow-up as its full question): `{"questions": [{"question", "asked_at"}]}`, up to 30, from the access log every ask writes. Never anyone else's. The Ask page lists them under "Your recent questions" to ask again | Ask CIP |
| `GET /api/v1/datasets/consumer-health` | The Consumer Health workbook (etl/consumer_health.py): the data science team's 73 columns, one row per US weekly respondent, their workbook (4 Sep 2023 to 10 Aug 2026), every older US weekly survey CIP holds from 28 Dec 2020 and every newer one, rebuilt by each publish; an .xlsx file | Consumer Health dataset |
| `POST /api/v1/export/{kind}` | A screen's table as CSV, Excel or PowerPoint (a table of weeks is drawn as a line chart of every week, with gridlines; % columns get a % axis and labels); or a book, `sheets` (up to 40 tables, 10,000 rows in all, 200 columns each, each with a `title`), as one Excel workbook with a tab per table (Excel only; a bigger book is refused, never cut). Excel is in the house style: header in Coresight red, a % column (header with %, or every number of a table with `unit` "%") shown as 61.0%, `plain` rows (indexes: people asked 1,234, a net score 12.3) as plain numbers, 2026-11-23 as a date; one is built at a time, so a second may get 503 busy (retry after 5 s) | Export |
| `GET /api/v1/keys` | Your keys (name, first characters, date) | — (portal sign-in) |
| `POST /api/v1/keys` | Make a key, `{"name": "…"}` | — (portal sign-in) |
| `DELETE /api/v1/keys/{shown}` | Revoke one of your keys | — (portal sign-in) |

**Your team's items.** The same boards, saved views, alerts and audiences as on the screens; you can remove only
what you made. Saving a view, an alert or an audience also needs `"by"`: your name, shown to the team as whose it is (a 422 says so when it is missing). An audience's groups are matched without spaces or case ("Gen Z" is the data's GenZ); a group a wave lacks is listed in `skipped`.

| Method and address | What it does | Needs on your menu |
|---|---|---|
| `GET /api/v1/team/summary` | Your boards, saved views, alerts and audiences in one answer | — |
| `GET /api/v1/team/views` | Saved views shared with your team | Saved views |
| `POST /api/v1/team/views` | Save a view for your team | Saved views |
| `DELETE /api/v1/team/views/{view_id}` | Remove a saved view you made | Saved views |
| `GET /api/v1/alerts` | Your team's alerts | Alerts |
| `POST /api/v1/alerts` | Watch an answer for a significant change | Alerts |
| `DELETE /api/v1/alerts/{alert_id}` | Remove an alert you made | Alerts |
| `GET /api/v1/alerts/new-surveys` | Whether you are emailed each new survey (My account) | Alerts |
| `PUT /api/v1/alerts/new-surveys` | Turn the new-survey email on or off (subscribed: true or false) | Alerts |
| `GET /api/v1/audiences` | Your team's saved audiences | Audiences |
| `POST /api/v1/audiences` | Save an audience (who answered what) | Audiences |
| `DELETE /api/v1/audiences/{audience_id}` | Remove an audience you made | Audiences |
| `POST /api/v1/waves/{survey_id}/audience` | One question for an audience against everyone | Audiences |
| `POST /api/v1/waves/{survey_id}/audience/profile` | What sets an audience apart in a wave | Audiences |
| `GET /api/v1/boards` | Your team's boards | Boards |
| `POST /api/v1/boards` | Make a board | Boards |
| `GET /api/v1/boards/{board_id}` | A board with its pinned tables and comments | Boards |
| `DELETE /api/v1/boards/{board_id}` | Remove a board you made | Boards |
| `GET /api/v1/boards/{board_id}/deck` | The board as one branded PowerPoint | Boards |
| `POST /api/v1/boards/{board_id}/items` | Pin a screen's table to a board | Boards |
| `DELETE /api/v1/boards/items/{item_id}` | Unpin a table | Boards |
| `POST /api/v1/boards/items/{item_id}/comments` | Comment on a pinned table | Boards |
| `DELETE /api/v1/boards/comments/{comment_id}` | Remove a comment you made | Boards |

The full machine-readable description is at `GET /api/v1/openapi.json`.

**Question codes** may be written in any case (`XM3` or `xm3`). **Answers.** JSON, gzip-compressed when you accept it. Errors are `{"detail": "…", "status": n}`: `401` no or revoked
key, `403` not on your menu ("Not included in your subscription") or a survey you may not see, `404` not found, `429`
too many requests, `503` busy or, for a few seconds after a restart, being published (retry after the seconds in `Retry-After`).

## 4. The MCP connector (Claude and other AI assistants)

Address: `https://<portal>/mcp` (MCP streamable HTTP, protocol `2025-06-18`), with the same `Authorization` header.

```bash
claude mcp add --transport http cip https://<portal>/mcp --header "Authorization: Bearer cip_…"
```

In Claude Desktop or claude.ai: Settings → Connectors → Add custom connector, address `https://<portal>/mcp`, and the
header `Authorization: Bearer cip_…`.

| Tool | What it does | Needs on your menu |
|---|---|---|
| `ask` | Any question in plain words, answered as on the Ask CIP page: the answer, every figure with its sample size in table.cell_bases, the chart that fits, the source, the closest questions when none matches, or which survey question was meant when two are too close to call | Ask CIP |
| `search_questions` | Find questions by topic, words, brand or code; plain English works; one entry per question over every code it was asked under | Search questions |
| `list_waves` | Survey waves, newest first, optionally of one family (e.g. CSI-US) | — |
| `question_results` | One question in one wave: each answer's % for Total, gender and generation, the prior week and last year with their bases, and significance (none for weighted figures: the tests are on the unweighted ones) | Question explorer |
| `question_trend` | One question over the last waves of its family | Trends |
| `crosstab` | One question by two demographic cuts | Cross-tab matrix |

A tool your menus do not include answers with an error the assistant can read ("Not included in your subscription").
Figures are unweighted percentages of qualified respondents unless a tool says otherwise; cite the survey, wave date
and base (n).

## 5. Upload survey (admins only)

The China Consumer Survey's weekly load (api/ingest.py, etl/baidu_qss_export.py). Both take two multipart files:
`raw` (Baidu's raw export, .csv or .xlsx) and `topline` (Baidu's topline, .xls or .xlsx); a trailing `.aspx` from a
SharePoint download is ignored. Each is at most 10 MB.

- `POST /api/v1/admin/survey/preview`: the wave date, respondents, every question's counts, how many figures equal the
  topline (`matched`) and every `problems` line (a wording missing from config/china_codebook.yml, a count that differs).
  Writes nothing.
- `POST /api/v1/admin/survey/publish` (optional form field `wave`, YYYY-MM-DD): the same check; with no problem the week
  is loaded (the same week again replaces it) and the published files are rebuilt in the background. 422 with the
  problems when the check fails (nothing written), 409 while another CIP run holds the ETL lock.
- `POST /api/v1/admin/sharepoint/notify`: "the China folder changed", from Microsoft Graph's webhook (the
  subscription's `clientState`) or a Power Automate flow (header `X-CIP-Secret`); no sign-in, the secret
  `CIP_SP_WEBHOOK_SECRET` instead. Answers Graph's `?validationToken=` check in plain text; 202 for a right secret,
  and a SharePoint pass (etl/sharepoint_china.py) runs within a minute; 403 for a wrong one; 404 while not set up.
  docs/CHINA_SURVEY_PIPELINE.md lists every way a week gets in.
