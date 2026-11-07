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
| Demo sign-in off wherever company sign-in is set up | Waiting for deploy | api/signin.py demo, tests/test_access.py | Staging's CIP_DEMO_LOGIN=1 is then ignored; IT can remove the setting on Monday. Check: /auth/dev-login answers 404 |
| Question codes in any case on cross-tabs (API, MCP) | Waiting for deploy | api/main.py crosstab_payload, tests/test_api_speed.py | `q=Q1` was 404 where /results answered (Azure's disk is case-sensitive); found by Gemini's 7 Nov probe, its `lower()` fix would have broken XM3 |
| Cache warm-up sees every answer | Waiting for deploy | config/access.yml (role `service`: publish@cip) | The 1 h cookie fix was not enough: the warmer was an analyst, and analysts' menus on staging have no cross-tab, so 885d7fa6 still warmed 0 of 1,740. Check: Publish log "1740 of 1740" |

## Pending

| Item | Status | Where | Note |
|---|---|---|---|
| Schema changes are applied by hand | Pending (known limit) | scripts/init_db.py, docs/technical/08-operations-runbook.md | No deploy step runs it: after a deploy that changes sql/ or schema_upgrade.py, run `python scripts/init_db.py` (role column 255 done by hand 7 Nov 17:15 IST) |
| More MCP tools: weekly report, sector databank, expected vs actual | Pending | api/mcp.py | Same rules as the screens; needs the published files' shapes |
| Disk alerts before the Azure worker disk fills | Pending | api/metrics.py, Teams webhook | The disk is Azure's (old deploy images fill it); CIP's own files are about 0.2 GB |
| Menus when the database is down at a server start | Pending (known limit) | shared/core/access.py managed_features | Until the first read succeeds, everyone gets their package: a removed trial menu can show for that time. Fix: keep the last choice in a file on /home |
| Two API workers saving keys at the same moment | Pending (known limit) | shared/core/api_keys.py save | Staging runs one worker, so no race today; add a file lock before running two |
| Split etl/fieldwork.py (collect, check, publish) | Pending (code review, judgement call) | etl/fieldwork.py | ~600 lines doing three jobs; works and is tested |

## Stuck

| Item | Status | Where | Note |
|---|---|---|---|
| Remove CIP_DEMO_LOGIN from the staging App Service settings | Stuck: IT (Monday) | Azure, csr-awa-cip-portal-stg | The code ignores it once the deploy above is out; removing it keeps the settings honest |
| `cip-stg.coresight.com` does not resolve on the office network | Stuck: IT | office DNS 10.2.21.4 | Public DNS points it to the Azure app; until IT adds it, use the azurewebsites address |
| PDF export of very wide team reports | Stuck: Forsta | e.g. "Full cross" (41 columns) | Forsta's own PDF layout error; the Excel and PowerPoint of the same report work |
| Old Azure images filling the worker disk | Stuck: IT / Azure | App Service plan csr-awa-cip-portal-stg | Azure clears old images itself; IT can confirm the clean-up or move the app to a plan with more local disk |

## Done earlier

| Item | Status | Where | Note |
|---|---|---|---|
| Keys survive a redeploy | Done | /home/cip/api_keys.yml | The staging MCP key still worked after the 885d7fa6 deploy (7 Nov 18:15 IST) |
| Gemini's staging investigation (7 Nov) reviewed | Done | this board | Right: case bug, HEAD /healthz, team LIMIT 500, logout URL join, demo sign-in. Wrong or not a bug: its case fix, analyst menus (your Access choice, 15:18 IST), admin token under demo (by design), 228 RPS "brick wall" (a model, not measured) |
| Second Gemini Forsta research reviewed | Done | docs/FORSTA_API_REVIEW.md section 5 | 7 endpoints do not exist, statuses unmeasured, all six proposed menus would be empty or not apply: none built |
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
