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
| Review fixes: role column 40 → 255 characters (long emails), dropped menus seen by every worker, key file only where writable, check pairs blank answers by code, Survey preview logic gated, Logs fully in IST | Waiting for deploy | sql/010, shared/core/schema_upgrade.py LENGTHEN, api/main.py, etl/fieldwork.py check | The schema step at the deploy runs `ALTER TABLE cip_role_access MODIFY COLUMN role VARCHAR(255)` (dry-run checked on staging) |
| Forsta collection for every survey: cross-tab check, Excel/PDF/PowerPoint | Done (in the staging database) | cip_forsta_record | 86 surveys, 194 reports; 43,396 of 43,396 cells match Forsta in 77 surveys (the 8 hibernated and 261003 locally not checked; 261003 checked directly, 867 of 867) |
| Documentation standard: What's new = docs/CHANGELOG.md, API guide page = docs/API.md | Waiting for deploy | tests/test_docs.py, WhatsNew.tsx, ApiGuide.tsx | The test fails if they differ or a route is undocumented |
| API guide in the portal | Waiting for deploy | /app/api-guide, docs/API.md | Every route (44) and MCP tool, with the menu each needs |
| API and menus agree everywhere | Waiting for deploy | api/main.py require_feature, api/mcp.py | Fixed: Launch schedule, a wave's results (Question explorer), question history (Trends, Compare or Audiences) |
| Each person makes their own API keys | Waiting for deploy | Account page, /api/v1/keys, shared/core/api_keys.py | Keys kept in /home/cip/api_keys.yml on Azure (survives deploys): check after the deploy |
| Menus for one client or one person (drag and drop) | Waiting for deploy | Access page, shared/core/access.py menus | A person's choice beats their client's, which beats their role's |
| A trial that ends closes at once, no refresh | Waiting for deploy | api/signin.py stale_before, deploy/cip_auth.js | nginx stops trusting older "sees everything" cookies; tested with the real nginx script |
| Logs in IST; old error no longer in every range; disk shows CIP's own share | Waiting for deploy | Logs page, api/metrics.py | |
| Forsta screens for admins (team reports, cross-tab setup, sample and devices, warnings, files, deletion, account, Forsta vs CIP) | Waiting for deploy | /app/forsta/…, etl/fieldwork.py | 261003: 867 of 867 cells match Forsta |
| Read-only Forsta POSTs, enforced | Waiting for deploy | etl/forsta_client.py READ_ONLY_POSTS | Three allowed; any other refused before sending |
| Fieldwork page per survey, why respondents dropped out, scrolling tables, terms in Methodology | Waiting for deploy | /app/fieldwork/…, Methodology | |

## Pending

| Item | Status | Where | Note |
|---|---|---|---|
| After the deploy: test on staging with a key (API and MCP), keys survive a redeploy, a trial ending | Pending | staging | Needs the deploy first |
| More MCP tools: weekly report, sector databank, expected vs actual | Pending | api/mcp.py | Same rules as the screens; needs the published files' shapes |
| Disk alerts before the Azure worker disk fills | Pending | api/metrics.py, Teams webhook | The disk is Azure's (old deploy images fill it); CIP's own files are about 0.3 GB |
| Menus when the database is down at a server start | Pending (known limit) | shared/core/access.py managed_features | Until the first read succeeds, everyone gets their package: a removed trial menu can show for that time. Fix: keep the last choice in a file on /home |
| Two API workers saving keys at the same moment | Pending (known limit) | shared/core/api_keys.py save | Staging runs one worker, so no race today; add a file lock before running two |
| Split etl/fieldwork.py (collect, check, publish) | Pending (code review, judgement call) | etl/fieldwork.py | ~600 lines doing three jobs; works and is tested |

## Stuck

| Item | Status | Where | Note |
|---|---|---|---|
| `cip-stg.coresight.com` does not resolve on the office network | Stuck: IT | office DNS 10.2.21.4 | Public DNS points it to the Azure app; until IT adds it, use the azurewebsites address |
| 8 hibernated surveys: only their summary is kept | Stuck: the user decides | 251004, 260101, 260202, 260402, 260700, 260701, 260703, beauty | Reading them means waking them in Forsta, which changes the survey and may cost |
| PDF export of very wide team reports | Stuck: Forsta | e.g. "Full cross" (41 columns) | Forsta's own PDF layout error; the Excel and PowerPoint of the same report work |
| Old Azure images filling the worker disk | Stuck: IT / Azure | App Service plan csr-awa-cip-portal-stg | Azure clears old images itself; IT can confirm the clean-up or move the app to a plan with more local disk |

## Done earlier

| Item | Status | Where | Note |
|---|---|---|---|
| Company sign-in (SSO) on staging | Done | api/signin.py, csr-idp | The 6 Nov 19:21 UTC discovery error no longer applies: authorize and token addresses are set |
| CIP MCP connected to the super admin in Claude Code | Done | `claude mcp list` → cip | Local API on this Mac (:8000); a staging connection after the deploy |
| Ponytail at ultra level on every change | Done | CLAUDE.md, AGENTS.md, GEMINI.md | |
