# Verification and evidence limits

Date: 21 October 2026, Asia/Kolkata.

## Results

| Check | Observed result | Scope |
|---|---|---|
| REA connection | rea-agents 6.5.0, live MCP session | JavaScript/browser functions available; native disassemblers were not needed |
| Static source analysis | 26 parsed JavaScript/TypeScript files, 197,829 text bytes, 38,415 AST nodes,623 findings, zero parse failures | Artifact SHA256 82742c8ad7335a1d82eb813b1e40af72f1f5925dc662905ec43d0b27681327a2; application partial, semantic unknown |
| Semantic limits | 5,616 unknowns, including imports/calls/value flow | Extensionless TS references can be unresolved; this is tool coverage, not proof of broken code |
| Local library | Rendered371 waves and latest wave415 n400 | Existing port8000 process through documented LOCAL bypass; UI values only |
| Local wave journeys | Overview, question explorer, crosstab and Changes content rendered | Read navigations; filters, downloads and every question were not exhaustively exercised |
| Local Trends | Generic Portal Notice error state | Observed failure; cause unconfirmed |
| Local Compare | compare API returned404 twice | Source route exists; running backend/rebuilt frontend alignment unverified |
| Circana public product page | REA accessibility capture rendered Unify+ features | Marketing page, no authenticated product tenant |
| Frontend build | Passed TypeScript/Vite build | Rebuilt ignored dist files; existing backend remained running |
| Frontend stats check | Passed | Arithmetic example suite, not survey-method validation |
| First guarded full pytest attempt |253 passed,4 failed,9 errors,1150 warnings | Legacy test_analysis expected populated local data; guard redirected configured DB to empty temporary SQLite |
| Isolated fixture suite |253 passed,1150 warnings | `tests/test_analysis.py` excluded explicitly; no full-suite pass claimed |

The first run's legacy failures report `no such table: cip_question`. This is unavailable integration fixture coverage under the audit's isolation, not evidence that the live database lacks tables. The 13 legacy cases were not certified. Tests elsewhere used their SQLite fixtures. No live ETL, mail or Teams delivery was executed: dotenv loading was disabled in the test subprocess, relevant external settings cleared, database path redirected to temporary SQLite, and socket connect blocked.

The isolated test command and scope are documented in the [test log](evidence/pytest-isolated.txt). This log records only the second, explicitly bounded pass. The first result is retained here as the limitation; it was not erased by the narrower pass.

## REA evidence references

| Record | Evidence identifier |
|---|---|
| Complete retained static analysis | ev_681d67fc8f48ec7c6a5a2f65aee4b507aa3d4d1061475be84d917f3c1324b68f |
| Static summary projection | ev_b090f6302a72bb303862857110651bbdbc0aee70ec80ecf215dad796c4d7e7c1 |
| Module page | ev_b831cd4b06270232107b617ce726813a3433b319e0ffe9bd3dc4e8f4b7199f76 |
| Selected api.ts semantic reference | ev_1d6f9ecaf78405f29745d8b48fcff7194f2594a9c4fdfb5fc89b777f2ec9945e |
| Local library scenario | ev_9572672fac41849d88a405ff95d34a6dda01fed3050a1bf45c7aa2972bf45ac1 |
| Local wave journey scenario | ev_61f8c3a5d16688522572d471889ec4cab23da6b776b7608ab88a02c2cfa05874 |
| Circana Unify+ public page | ev_b056c9b0a851c27af952d6992af763b720af4005bd392bbe8bcf26f901beb061 |

The api.ts item selected by node ID is an unresolved import-reference role, not the entire file's endpoint inventory. Source review supplies the latter. No claim of graph completeness is made.

An additional authenticated GET-only contract check is stored in [runtime-contract-summary.json](evidence/runtime-contract-summary.json). Wave415 book returned200. Its default q1 trend returned200 with193 waves and included wave415, but its response lacked the top-level `versions` and per-wave `version` fields required by current `web/src/api.ts:46-49`; `Trends.tsx:212` dereferences `t.versions.length`. Compare again returned404. This establishes an actual running-response/current-client schema incompatibility. The exact backend build or stale-publication origin still requires release diagnosis; no restart or repair was performed. This companion check used ordinary HTTP tools, not a new REA record, and retained no cookie values or respondent data.

Browser scenarios launched owned headless Chrome155 and terminated those owned processes. Initial schema-rejected attempts (empty actions, then missing step_id) did not launch or capture the target; corrected calls produced the records above. Competitor public navigation used no login, form submissions or extraction of protected content.

## Source and runtime identity

HEAD identifies the baseline commit, while source manifest hashes identify the investigated files. The initial worktree already contained29 modified tracked paths and two untracked application paths. The running API PID29617 started before the later source modifications; its build commit and loaded Python module revisions were not exposed or established. Frontend build verification updated dist. Therefore local failures require a coordinated version-matched reproduction; neither deployment readiness nor source-defect root cause is certified.

## Unresolved evidence

No new staging SQL inventory, provider-value reconciliation, service account effective grants, customer tenancy contract, IdP deployment, backup restore, production uptime/load/soak test, panel repeat-overlap, weighting target or external data licence was verified. Existing documents about those topics are historical references. Competitor pricing, private functionality and outcome claims remain unverified beyond official advertised material.

## Task checklist

| Requested question | Outcome |
|---|---|
| Understand product architecture/data/workflows | Answered at code and selected runtime level |
| Identify current gaps | Source/observed gaps catalogued; deployment-specific impact scoped |
| Identify competitors and extra capabilities |23 bounded vendor/product entries and official sources |
| Reverse engineer competitors | Public workflows and capability/data reconstruction; proprietary internals unavailable |
| Recommend how to close gaps | Proposed implementation contracts and acceptance gates |
| Run LLM Council and final review | Stored in separate Council directory |
| Store additional Codex documentation | Separate REA Codex and LLM Council Codex collections; existing work preserved |

