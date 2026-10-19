# REA Claude: Consumer Insight Portal investigation

**Date:** 20 October 2026 · **Investigator:** Claude (Opus 5.5, Claude Code) · **Target:** this repository, its working tree (including uncommitted files), its logs, the installed launchd jobs and the live `cip_stg` database (read-only queries).

This folder is an independent investigation, written after reading `docs/REA Gemini/` and `docs/LLM Council Gemini/`, so the two can be compared. Every finding was re-derived from code, logs or live queries; nothing was copied from Gemini or from earlier reports without being checked again.

| File | What it holds |
|---|---|
| [01-system-reconstruction.md](01-system-reconstruction.md) | How the system actually works, end to end, with live numbers |
| [02-identified-gaps.md](02-identified-gaps.md) | Ranked defect and risk ledger (44 items) with evidence and fixes |
| [03-build-plan.md](03-build-plan.md) | What to build next, in order, with exit criteria |
| [04-gemini-verification.md](04-gemini-verification.md) | Gemini's REA dossier checked claim by claim |
| [05-evidence-ledger.md](05-evidence-ledger.md) | Commands run, live query results, the test run, and the investigation checklist |

## Method

The REA skill was loaded first. Its own routing rule says that for "ordinary analysis of a complete source repository, use normal repository tools and do not run REA readiness or provider commands". REA's binary, bundle and runtime tools were therefore **not** used: there is no shipped binary or opaque bundle here. The skill's investigation discipline was followed instead:

1. Turn the request into a checklist of questions, each with the evidence it needs ([05 §4](05-evidence-ledger.md)).
2. Split the questions into independent scopes: ETL, schema, app, security and ops. Run three read-only audit agents in parallel and do the security, ops, test and live-data checks directly.
3. Corroborate each claim with the evidence type it needs: code (file:line), runtime (logs, `launchctl`), live state (read-only SQL against `cip_stg`), or a test run.
4. Keep a finding ledger with Evidence IDs (`E-xx`, see 05) and mark every statement:
   - **[O] observed:** seen directly in code, logs, a query result or command output;
   - **[I] inferred:** follows from observations;
   - **[U] unknown:** not checkable from here.

Nothing was written to any database. Nothing was sent to Forsta. Nothing was committed. No secret values appear in this folder.

## The five things that matter most

1. **Gemini's output contains a live database password.** It is in `docs/REA Gemini/05-IDENTIFIED-GAPS-AND-DEFECT-LEDGER.md` and `docs/LLM Council Gemini/advisors/01-the-contrarian.md`. The GitHub repo is **public**. Committing either folder publishes the password. Rotate it and redact both files first. [O] E-01, E-02
2. **The warehouse is missing about 50 of the 75 tracker weeks since May 2025.** 51 closed Forsta surveys are hibernated and were never loaded. The pipeline logs a "watch" warning, but the integrity run still exits 0. [O] E-10, E-11
3. **The portal runs with the owner's personal, all-privileges account.** `APP_DB_USER` is empty, so the "read-only" app role falls back to the writer account `mohdsaeedafri@%`. All 12 views also use that account as DEFINER. The grant script that would fix this (`sql/004_grants.sql`) does not work as written. [O] E-12, E-13
4. **Production runs uncommitted code from a laptop.** The launchd job imports `etl/integrity.py`, which is untracked; a fresh clone of the repo cannot run the scheduled job. [O] E-14
5. **The pipeline is sound at its core but has alerting holes.** Loads, verification and reconciliation work: wave 412 matched Forsta 147,635/147,635 (per docs/14), and the 238 tests pass. But:
   - a failed email send silences the same alert for 6 hours;
   - a crash after the DB check exits with no alert;
   - running pytest sends real email and Teams messages.

   [O] E-20…E-23

## Model used

**Claude.** This investigation was produced by Claude (Anthropic, Opus 5.5) running in Claude Code.
