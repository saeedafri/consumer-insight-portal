# Chairman verdict

*Chairman sub-agent (Claude Opus 5.5). It read the framed question, all five advisor responses, all five peer reviews, and the investigator's fact-check. Text as returned.*

## Where the Council Agrees

- **Plan C wins, Plan G loses.** All five advisors back hardening first with a gate before any rewrite. Plan G puts 35 days of rewrite on one engineer. The Executor estimates that work at 10+ weeks, and it builds a UI for clients who don't exist yet.
- **The 51 hibernated surveys come first.** They are the only loss that can't be undone. Forsta's retention policy is unknown, and the documented "365-day" rule is already contradicted. Recovery is a human action with unknown turnaround, so the request has to go out before any engineering starts.
- **The integrity check is the root defect.** It exits 0 while about 50 of 75 tracker weeks are missing. A trend chart drawn over those holes is worse than no chart.
- **Rotate the password, and don't count "repo private" as the fix.** Every advisor ranked rotation first.
- **Don't start React without a signed client.**

## Where the Council Clashes

- **When to move to Azure.** The Executor wants it optional: fix the alerts first, or a broken job just fails in a new place. The First Principles advisor says the move fixes the firewall timeouts at their cause. Both are partly right. The fact-check shows Azure helps only with a private endpoint or VNet rule; it doesn't fix timeouts on its own. Alerts are about two days of work, so they go first and Azure follows.
- **How much to harden Streamlit.** The First Principles advisor would cut OIDC and small-cell suppression until outsiders can reach the portal. The Expansionist wants them as procurement-ready features to show prospects. The trim wins for now. Demoing a portal that has a shared passphrase, fails open, and runs on an ALL-privileges account adds exposure.
- **What the gate is for.** The Contrarian warns that an open-ended gate becomes permanent hardening. The Expansionist wants to use it to sell. Both point to the same fix: give the gate a date.

## Blind Spots the Council Caught

- **The leak hasn't happened yet.** The fact-check shows the password is not in git history. It sits in a gitignored `.env` and in two untracked Gemini docs. The real risk is someone committing those docs by accident. No history scrub is needed, but rotation still is, because a third-party model handled the value.
- **Check whether the credential was used.** Pull the Azure MySQL access logs for the owner's account.
- **A backup exists but sits on one machine.** `backup_db.py` made a good 321 MB dump on 20 Oct. It is untracked, and its off-machine copy failed.
- **Backfilled waves need the wave-412 treatment.** Reconcile each one against Forsta, and recompute the cube and concepts.
- **Licence rights to resell Forsta panel data** were never checked.
- **The respondent panel ID is stored as an unsalted hash.** Treat it as pseudonymous personal data.
- **Nobody is named as backup.** The bus factor stays at one unless someone is.

## The Recommendation

Run Plan C as amended above. The order is:

1. **Today (Tue 20 Oct)**
   - **Human:** the owner sends Forsta a request to reactivate or export the 51 surveys, and asks about cost and retention terms.
   - **Admin:** rotate the DB password, and pull access logs for the old one.
   - **Engineering:** delete or redact the two Gemini docs. Make the repo private. Commit `integrity.py`, `backup_db.py` and the other untracked production files. Copy the 20 Oct dump off the laptop.
2. **Week 1 (to 30 Oct), engineering:**
   - Make integrity fail on coverage gaps.
   - Fix the alert throttle so it marks an alert sent only after sending.
   - Add the crash handler, run lock, retry cap, DB timeouts and heartbeat.
   - Stop tests from sending real email and Teams messages.
3. **Week 2 (to 6 Nov)**
   - **Engineering:** load the recovered waves and reconcile each against Forsta. Create least-privilege DB accounts and fix the grant script. Add the FKs.
   - **Admin:** name a second operator and hand them the runbook.
4. **Weeks 3–4 (to 20 Nov), engineering:** move ingestion to an Azure Container Apps job with a private endpoint. Retire the launchd job only after a week of clean runs in parallel.
5. **Week 5 (to 27 Nov)**
   - **Engineering:** make portal auth fail closed and turn on Streamlit's built-in OIDC.
   - **Human/legal:** get a written answer on panel-licence resale rights.
6. **Gate review, Tue 1 Dec 2026, owner plus sponsor.** Open the React/FastAPI rewrite only if all four hold:
   - a named external client has signed or sent a letter of intent;
   - licence rights are cleared;
   - the ETL has run 3+ weeks off the laptop with no silent failures;
   - measured concurrency exceeds about 10 users.

   If any condition fails, write down why. Then set the next review for no later than 2 Mar 2027.

## The One Thing to Do First

Today, the owner sends Forsta a written request to reactivate or export all 51 hibernated surveys, with a reply-by date. It is the only clock in this plan that can't be restarted.
