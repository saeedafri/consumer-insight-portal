# Peer reviews: anonymised round

Five independent reviewer sub-agents (Claude Sonnet) each read the framed question and `00-anonymised-responses.md`. Each reviewer had a different emphasis:

| Reviewer | Emphasis |
|---|---|
| R1 | neutral |
| R2 | evidence-skeptic |
| R3 | business value |
| R4 | security |
| R5 | sequencing |

**Mapping**, revealed only after the reviews were done:

| Letter | Advisor |
|---|---|
| A | Executor |
| B | Expansionist |
| C | Contrarian |
| D | Outsider |
| E | First Principles Thinker |

## Tally

| | Strongest | Biggest blind spot |
|---|---|---|
| R1 | E | B |
| R2 | C | B |
| R3 | E | B |
| R4 | E | B |
| R5 | A | B |
| **Result** | **E (First Principles) 3 · A 1 · C 1** | **B (Expansionist), all 5** |

## R1 (neutral)

**1. Strongest: E.** It ranks actions by one test, whether the harm is irreversible and on a clock. That puts the hibernated surveys first, since Forsta could purge them at any time. It also names the root defect: integrity exits 0 on a 67% gap. It correctly says making the repo private doesn't fix a leaked password. It ties the Azure move to the cause of the failures (firewall timeouts), not to modernisation. A is a close second for a concrete Monday order, but it demotes the Azure move.

**2. Biggest blind spot: B.** It treats the gate as a sales funnel and talks up the dataset's value, but it never mentions the credential leak or the public repo. It also doesn't flag the licence risk of selling panel data. Showing a 20-user pilot to prospects ignores the shared-passphrase auth and the ALL-privileges account. B also says "about 25 of 75 weeks" without noting that integrity still passes.

**3. Missed by all five:**
- Whether anyone used the leaked credential. No response proposes checking Azure MySQL access logs, or whether the personal ALL-privileges account was used from other hosts.
- Whether the repo's public history, forks and caches can be scrubbed. This is a separate step from rotating the password.
- Whether the 43 recovered waves can be backfilled consistently with the harmonised concepts and cube. The cube and trend continuity may need recomputing.
- A named second person for the bus factor. D raises it and C notes it, but neither proposes who or how.
- A date-boxed gate. C raises this but offers no concrete trigger.

## R2 (evidence-skeptic)

**1. Strongest: C.** It attacks both plans with evidence from the facts:
- Plan C's reactivation step has no owner or deadline.
- The gate has no deadline either.
- Making the repo private doesn't fix a password already in public history.
- The Azure move leaves the bus factor at one.

It also raises the licensing question for client resale. E is close because it ranks work by irreversibility. But E asserts that Azure "fixes firewall timeouts at the source". The facts don't say that, and the container may need its own firewall allowlisting.

**2. Biggest blind spot: B.** It treats the dataset as a sellable asset without checking licence rights. These claims are all speculation:
- that enterprise buyers want OIDC and small-cell suppression;
- that the cube is something "a client can't get from Forsta";
- that 4.36 s suits a 3-5 client pilot.

B also ignores the leaked credential and the laptop single point of failure. A says "flip repo private" as if that closes the leak.

**3. What all five missed:**
- Whether the leaked password was already used. Nobody suggests auditing DB access logs or purging git history and forks.
- A backup or restore path for the existing 23.3 M answers. The untracked `backup_db.py` is never mentioned.
- Reconciliation of the recovered 43 waves, as wave 412 was verified.
- Whether reactivating or exporting hibernated surveys has a cost or Forsta terms-of-service limits.
- Whether surveys older than the 51 are also gone.

## R3 (business value)

**1. Strongest: E.**
- It ranks every item by one test: is the harm irreversible and on a clock? That puts the hibernated surveys first, because a year of tracker history can be lost permanently.
- It notes that making the repo private doesn't fix a password already in public git history.
- It names the root defect: integrity exits 0 on a 67% gap, so the system can't tell you it is wrong.
- It trims Plan C's speculative work (OIDC, small-cell suppression) until someone outside can reach the portal.

A is a close second, with concrete Monday sequencing and a note that Forsta access is a human dependency.

**2. Biggest blind spot: B.** It treats the dataset as an asset to sell. It never asks whether Coresight may resell Forsta panel data, and it never says the 50-of-75 gap undermines any sales demo. It pitches a "sales funnel" and a 3–5 client pilot on incomplete, unlicensed data, and calls the licence question a blocker nobody weighed. It also ignores the leak and the bus factor. C does flag the licensing gap, which makes B's omission more glaring.

**3. Missed by all five:**
- No cost or budget. Nobody prices engineer-days, Azure spend, or the commercial value of the tracker.
- No stakeholder accountability. Nobody asks who sponsors this or who decides to run the gate.
- Nobody quantifies the leak. Was the credential used? Do the logs show access? Is there a disclosure duty?
- Nobody asks about backups or recovery of the existing database.
- D alone names the bus factor, and no one proposes a fix, such as cross-training or a runbook owner.

## R4 (security)

**1. Strongest: E.** It ranks every action by whether the harm is irreversible and on a clock, which puts the hibernated surveys first since Forsta's retention policy is unknown. It also catches that making the repo private does not fix the leak, because the password is already in public history, clones and caches. It names the integrity check exiting 0 on a 67% gap as the root defect. C also catches the history point and adds more critique of Plan C, but E's ordering is more actionable.

**2. Biggest blind spot: B.** It treats the exposure as background and focuses on commercial upside. It never mentions that private-repo does not undo the leak, and it says nothing about rotation order. It also proposes demoing the Streamlit portal to prospects. That portal has a shared passphrase, fails open when `APP_ENV` is unset, and runs on an ALL-privileges personal DB account. Putting it in front of prospects adds exposure.

**3. Missed by all five:**
- Nobody audits whether the leaked credential was already used. That needs DB access logs and an actual review for compromise. C only says to "confirm nobody used it".
- The leaked material is in git history, forks and caches, so history needs scrubbing, GitHub support or cache purge requests, and a check for exposed host names and paths. Rotation alone does not cover this.
- The 179,612 respondent rows may contain personal data. Nobody covers privacy law, retention or what a breach notification would require.
- Nobody mentions a backup or restore test for `cip_stg`. A new `backup_db.py` is untracked, so it is not in version control.
- Nobody says to snapshot the laptop's `.env`, launchd state and untracked code before any change.
- Nobody tells the owner not to run the Gemini docs' instructions as-is, since they contain the credential.

## R5 (sequencing)

**1. Strongest: A.** It is the only response that sequences the work:
- It starts the Forsta request first because the reply latency is unknown and the retention clock may be running.
- It runs the quick fixes (integrity, firewall retry) while that request is pending.
- It moves the throttle fix to Monday.
- It sees that moving the ETL to Azure Container Apps before alerts work only changes where it fails.
- It gives a concrete Monday order.

E ranks by irreversibility, which is also good, but it only partly addresses order for a single engineer.

**2. Biggest blind spot: B.** It treats the gate as a sales funnel and never mentions the live failures. It has no sequence, no day-1 credential rotation, and nothing on silent ETL failures. It also assumes the dataset can be sold, without checking Forsta's licence terms or the missing weeks. C at least flags the licensing question.

**3. Missed by all five:**
- Nobody proposes a cheap check on whether the credential was already used. Rotating the password does not tell you that.
- Nobody proposes a one-off export of the data as a fallback, such as a `mysqldump` plus a Forsta data pull. A backup script exists but is untracked, and none of the five mention it.
- Nobody asks whether the owner's unplanned absence needs a runbook or a second person within the 12 days. D names the gap but sets no deadline or fix.
- Nobody sets a fixed date for the gate decision.
- Nobody mentions that the leaked password is in untracked files that could be committed by accident.

---

## Investigator's fact-check of the peer round (added by the moderator, Claude)

Several reviewers and advisors assumed facts that the evidence contradicts. These corrections went to the Chairman:

1. **The password is not in git history.** `git log --all -S` finds nothing (REA Claude E-01). It is in `.env`, which is gitignored and was never committed, and in two **untracked** Gemini docs. The exposure is a *pending* leak: it happens if those docs are committed. "Already in public history, forks and caches" is wrong. Rotation is still required, because the value was handled by a third-party model and written to disk in plain text. Scrubbing git history is not needed.
2. **A backup exists.** `scripts/backup_db.py` produced a proven 321 MB dump on 20 Oct (40 tables, 31.6 M rows). It is untracked, and its off-machine OneDrive copy did not happen.
3. **Azure still needs network work.** An Azure job removes the *laptop's changing public IP* problem only if it reaches MySQL over a private endpoint or VNet rule. R2's caveat is right.
4. **Respondent data** holds no names or emails: the personal Forsta fields are dropped on load. It does keep an **unsalted** hash of the panel ID plus the Forsta record UUID (REA Claude G-26).
