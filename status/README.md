# Status: what is done, what is pending, where we are stuck

The one place every agent (Claude, Gemini, Codex, others) and every person reads **before starting** and updates
**while working** on CIP. The rule is in CLAUDE.md, AGENTS.md and GEMINI.md.

## The standard

- **Read this file first.** Take the next pending item, or the one the user names; do not redo a done one.
- **Update it as you go**, in the same change as the code: when you start an item, finish it, or get stuck. One line
  per item in the table below; newest change at the top of its section.
- **Status**, exactly one of:
  - `Done`: built, tested, the docs updated (What's new, docs/CHANGELOG.md, docs/API.md when an API changed).
  - `Waiting for deploy`: done here, not yet on staging (the user commits and pushes; agents never do).
  - `In progress`: an agent is on it now; say which and since when.
  - `Pending`: agreed, not started.
  - `Stuck`: cannot move without someone; say exactly who or what is needed.
- **Where**: the files or screens it touches, so the next agent finds it. **Note**: one line; the detail lives in the
  code, the tests and docs/CHANGELOG.md, not here.
- Dates are written out (7 Nov 2026), times in IST. When an item has been `Done` on staging for a week, move it to
  "Done earlier" at the bottom as one line.

## In progress

| Item | Status | Where | Note |
|---|---|---|---|
| (nothing in progress) | | | |

## Waiting for deploy (done here, not on staging yet)

| Item | Status | Where | Note |
|---|---|---|---|
| Cache warm-up after a deploy | Waiting for deploy | etl/publish.py ask_nginx, tests/test_publish.py | Its 1 h cookie fell before nginx's access cut-off, so the 7 Nov 16:21 IST deploy warmed 0 of 1,740 cross-tabs; now a full-length cookie. After the deploy the Publish log must say "1740 of 1740" |

## Pending

| Item | Status | Where | Note |
|---|---|---|---|
| Keys survive a redeploy | Pending | staging, /home/cip/api_keys.yml | Check at the next deploy: `claude mcp list` must still show cip-stg Connected |
| Schema changes are applied by hand | Pending (known limit) | scripts/init_db.py, docs/technical/08-operations-runbook.md | No deploy step runs it: after a deploy that changes sql/ or schema_upgrade.py, run `python scripts/init_db.py` (role column 255 done by hand 7 Nov 17:15 IST) |
| More MCP tools: weekly report, sector databank, expected vs actual | Pending | api/mcp.py | Same rules as the screens; needs the published files' shapes |
| Disk alerts before the Azure worker disk fills | Pending | api/metrics.py, Teams webhook | The disk is Azure's (old deploy images fill it); CIP's own files are about 0.2 GB |
| Menus when the database is down at a server start | Pending (known limit) | shared/core/access.py managed_features | Until the first read succeeds, everyone gets their package: a removed trial menu can show for that time. Fix: keep the last choice in a file on /home |
| Two API workers saving keys at the same moment | Pending (known limit) | shared/core/api_keys.py save | Staging runs one worker, so no race today; add a file lock before running two |
| Split etl/fieldwork.py (collect, check, publish) | Pending (code review, judgement call) | etl/fieldwork.py | ~600 lines doing three jobs; works and is tested |

## Stuck

| Item | Status | Where | Note |
|---|---|---|---|
| Demo sign-in is on in staging: anyone can sign in as any email, no password | Stuck: the user / IT (urgent) | App Service setting CIP_DEMO_LOGIN | Checked 7 Nov 17:20 IST: a stranger's email reads every wave; your email gets the super admin's menus (admin pages still need the token). Company sign-in works, so set CIP_DEMO_LOGIN=0 |
| `cip-stg.coresight.com` does not resolve on the office network | Stuck: IT | office DNS 10.2.21.4 | Public DNS points it to the Azure app; until IT adds it, use the azurewebsites address |
| PDF export of very wide team reports | Stuck: Forsta | e.g. "Full cross" (41 columns) | Forsta's own PDF layout error; the Excel and PowerPoint of the same report work |
| Old Azure images filling the worker disk | Stuck: IT / Azure | App Service plan csr-awa-cip-portal-stg | Azure clears old images itself; IT can confirm the clean-up or move the app to a plan with more local disk |

## Done earlier

| Item | Status | Where | Note |
|---|---|---|---|
| Checked on staging after the 7 Nov deploy (443c3ef0) | Done | staging | 17 API routes and 5 MCP tools with a key; a key cannot make keys; a trial ended at 17:23:53 IST was refused 10 s later in the same session; no errors since the deploy |
| Hibernated surveys (8) | Done: decided not to wake them | etl/fieldwork.py | The user's decision, 7 Nov 2026: only their summary is kept |
| Review fixes: role column 255 characters, dropped menus seen by every worker, key file only where writable, blank answers paired by code, Survey preview logic gated, Logs fully in IST | Done (staging, 7 Nov) | sql/010, api/main.py, etl/fieldwork.py | |
| API guide, What's new = docs/CHANGELOG.md, docs/API.md | Done (staging, 7 Nov) | /app/api-guide, tests/test_docs.py | |
| Own API keys; menus per client and person; trials end without refresh | Done (staging, 7 Nov) | Account and Access pages, api/signin.py, deploy/cip_auth.js | |
| Forsta screens, read-only POSTs enforced, Forsta vs CIP check, Excel/PDF/PowerPoint | Done (staging, 7 Nov) | /app/forsta/…, etl/forsta_client.py | 43,396 of 43,396 cells match in 77 surveys |
| Fieldwork per survey, why respondents dropped out; Logs in IST | Done (staging, 7 Nov) | /app/fieldwork/…, Logs page | |
| CIP MCP connected to the super admin in Claude Code | Done | `claude mcp list` → cip (local), cip-stg (staging, your key "Claude Code (staging)") | |
| Company sign-in (SSO) on staging | Done | api/signin.py, csr-idp | |
| Ponytail at ultra level on every change | Done | CLAUDE.md, AGENTS.md, GEMINI.md | |
