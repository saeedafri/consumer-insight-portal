# CIP API and MCP connector: how to use them

The portal's data can be read by your own programs (the **API**) and by Claude or any AI assistant that supports
MCP connectors (the **MCP connector**). Both act as **you**: they see exactly what your menus show in the portal, no
more, at the moment of each request. This guide is also in the portal at **Account → API keys and Claude → Read the
API guide** (`/app/api-guide`); `tests/test_docs.py` fails if the two differ or if a route is missing from either.

## 1. Make a key

1. Sign in to the portal and open **Account** (top right) → **API keys and Claude**.
2. Type a name for the key (the tool it is for, such as "My Claude") and press **Make a key**.
3. Copy the key now: it starts with `cip_` and is shown **once**. CIP keeps only its fingerprint (SHA-256).

You can keep up to 10 keys and revoke any of them on the same card; a revoked key stops working at once. A key cannot
make or revoke keys: that needs your signed-in portal session.

## 2. What a key may read: the same rules everywhere

| Rule | What it means for a key |
|---|---|
| Your role, client and menus | A key reads only what your left menu shows. The super admin chooses menus per role, per client and per person on the Access page; a person's choice beats their client's, which beats their role's |
| Changes apply within a minute | When a menu is taken away (a trial ends), your screens, your keys and the MCP connector lose it within a minute (most answers at once); no sign-out or refresh needed |
| Surveys | Only the surveys your organisation may see |
| Rate limit | The same per-minute limit as your sign-in; over it, the answer is `429` with `Retry-After: 60` |
| Admin pages | Never through a key while sign-in is the demo; otherwise only for admins, as in the portal |

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
| `GET /api/v1/waves/{survey_id}/report` | The weekly US Consumer Survey Insights report of a tracker wave | Weekly report |
| `GET /api/v1/waves/{survey_id}/logic` | When each question was shown, and the screen-out rules | Survey preview |
| `GET /api/v1/questions/{family}/{study_type}/{qcode}` | One question across every wave and cut | Trends, Compare waves or Audiences |
| `GET /api/v1/dashboards/{code}` | A topic dashboard for its latest wave | Topic dashboards |
| `GET /api/v1/dashboards/{code}/{survey_id}` | A topic dashboard for one wave | Topic dashboards |
| `GET /api/v1/search` | Questions by words, code, answer or survey, `?q=tariffs&limit=40` | Search questions |
| `GET /api/v1/sectors` | The sector databank: purchase rate, retailers, brands, categories | Sector databank |
| `GET /api/v1/expectations` | Retail events, expected vs actual | Expected vs actual |
| `GET /api/v1/reports` | The waves that have a weekly report | — |
| `GET /api/v1/schedule` | The launch plan against what Forsta fielded | Launch schedule |
| `GET /api/v1/fieldwork` | Each survey's funnel and why respondents dropped out | Fieldwork |
| `GET /api/v1/methodology` | How the figures are made | — |
| `GET /api/v1/public/facts` | The home page's counts and dates (no key needed) | — |
| `POST /api/v1/ask` | A question in plain words, answered from published figures with sources, `{"question": "…"}` | Ask CIP |
| `POST /api/v1/export/{kind}` | A screen's table as CSV, Excel or PowerPoint | Export |
| `GET /api/v1/keys` | Your keys (name, first characters, date) | — (portal sign-in) |
| `POST /api/v1/keys` | Make a key, `{"name": "…"}` | — (portal sign-in) |
| `DELETE /api/v1/keys/{shown}` | Revoke one of your keys | — (portal sign-in) |

**Your team's items.** The same boards, saved views, alerts and audiences as on the screens; you can remove only
what you made.

| Method and address | What it does | Needs on your menu |
|---|---|---|
| `GET /api/v1/team/summary` | Your boards, saved views, alerts and audiences in one answer | — |
| `GET /api/v1/team/views` | Saved views shared with your team | Saved views |
| `POST /api/v1/team/views` | Save a view for your team | Saved views |
| `DELETE /api/v1/team/views/{view_id}` | Remove a saved view you made | Saved views |
| `GET /api/v1/alerts` | Your team's alerts | Alerts |
| `POST /api/v1/alerts` | Watch an answer for a significant change | Alerts |
| `DELETE /api/v1/alerts/{alert_id}` | Remove an alert you made | Alerts |
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

**Answers.** JSON, gzip-compressed when you accept it. Errors are `{"detail": "…", "status": n}`: `401` no or revoked
key, `403` not on your menu ("Not included in your subscription") or a survey you may not see, `404` not found, `429`
too many requests, `503` busy (retry after the seconds in `Retry-After`).

## 4. The MCP connector (Claude and other AI assistants)

Address: `https://<portal>/mcp` (MCP streamable HTTP, protocol `2025-06-18`), with the same `Authorization` header.

```bash
claude mcp add --transport http cip https://<portal>/mcp --header "Authorization: Bearer cip_…"
```

In Claude Desktop or claude.ai: Settings → Connectors → Add custom connector, address `https://<portal>/mcp`, and the
header `Authorization: Bearer cip_…`.

| Tool | What it does | Needs on your menu |
|---|---|---|
| `search_questions` | Find questions by topic, words, brand or code; plain English works | Search questions |
| `list_waves` | Survey waves, newest first, optionally of one family (e.g. CSI-US) | — |
| `question_results` | One question in one wave: each answer's % for Total, gender and generation, the prior week and last year, and significance | Question explorer |
| `question_trend` | One question over the last waves of its family | Trends |
| `crosstab` | One question by two demographic cuts | Cross-tab matrix |

A tool your menus do not include answers with an error the assistant can read ("Not included in your subscription").
Figures are unweighted percentages of qualified respondents unless a tool says otherwise; cite the survey, wave date
and base (n).
