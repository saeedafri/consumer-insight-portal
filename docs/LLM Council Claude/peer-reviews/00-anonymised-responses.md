# Anonymised advisor responses (for peer review)

## Response A

Plan C wins on Monday-morning executability. Plan G has a first step (rotate the credential), then falls apart.

**Day 1 is concrete.** Rotate the password. Redact the two Gemini docs. Flip the repo private. `git add etl/integrity.py` and the other untracked production files. That is half a day of work and nothing blocks it. Plan G's triage also starts here, so the two plans agree on this part.

**Week 1 has a blocker neither plan owns.**
- The 51 hibernated surveys need a human with Forsta console access.
- Monday morning, send that email or file that ticket first, because the reply has unknown latency and the retention clock may be running.
- Everything else in week 1 (integrity exit codes, firewall retry) can proceed while you wait.
- Gemini's "get a Forsta service key" is a procurement dependency, not an engineering task, so it can't be scheduled.

**Plan G's 35 days is fiction for one engineer.** It packs in:
- containerising the ETL
- a FastAPI service with OIDC
- a React 19 SPA with an AG Grid crosstab and Excel/PPT export
- a 300-user load test

I'd put that at 10+ weeks. Excel/PPT export alone eats a week. No client has asked for any of it. While you build it, the ETL keeps dying on firewall timeouts, 5 failures in 10 days, and nobody tells you.

**Plan C's gate is the best design choice.** It turns the rewrite into a trigger-based decision. I'd drop the Azure Container Apps move in weeks 3–4 down to optional. Moving a failing job to the cloud before the alerts work just moves where it fails. Do the alert throttle fix, crash handler, run lock and heartbeat first. Those are about 2 days total, and they stop silent failures immediately.

**Monday order:**
1. Rotate the password.
2. Make the repo private.
3. Commit `integrity.py`.
4. Email Forsta about the hibernated surveys.
5. Fix the throttle bug (mark sent after sending, not before).

Don't open a React project until a client signs something.

## Response B

Plan C's gate protects a product that may be far bigger than "internal Streamlit". The upside everyone is undervaluing is the dataset.

**What you actually own**
- 320 verified waves, 179,612 respondents, 23.3M answers, 1,789 harmonised concepts, and a 2.1M-cell cube.
- Wave 412 matched Forsta exactly, with 0 differences across 147,635 answers.
- That is a cross-year, harmonised consumer panel with a verified ETL. The harmonised concept layer took the most work to build, and a client can't get it by exporting from Forsta.

**The recovery week is the highest-leverage move in either plan.**
- 43 weekly tracker waves, Jul 2025 to Jun 2026, are sitting hibernated. Loading them changes the tracker from about 25 of 75 weeks to near-continuous coverage.
- A continuous 2018-to-2026 tracker is the asset that justifies a client-facing product.
- Plan G buries this inside "triage". Plan C correctly makes it Week 1.
- If Forsta's real retention policy turns out to be loose, you may be able to recover far more than 51 surveys. I'd test that first.

**Plan C's gate is a sales funnel.**
- Don't treat "confirm external clients" as a blocker. It is the cheapest market test available.
- Show prospects the Trend Explorer from the hardened Streamlit portal.
- Fail-closed auth, OIDC and small-cell suppression are exactly what an enterprise buyer asks about in procurement. Hardening is the first half of productisation.
- Your own benchmark shows 20 concurrent users at 4.36s, which is fine for a pilot of 3 to 5 clients.

**Adjacent upside**
- The Azure Container Apps ingestion job and the least-privilege schema make a second panel, or a second client's survey stream, a configuration change instead of a rebuild.
- Syndication and the AI copilot (both in Plan G's "later") only work on a complete, trusted dataset. Complete the data first, then sell it.

**Verdict:** run Plan C. Use the gate to sell, not just to wait. Build the React SPA only once a client's money pays for it.

## Response C

**Plan G fails first, but Plan C has holes the safer-looking framing hides.**

**Plan G**
- It spends week 1 on triage, then builds a UI that no client has asked for. "Enterprise clients" are asserted, not confirmed; the fact sheet says there are none today.
- Meanwhile an ETL that failed on 5 of the last 10 days stays on a laptop for 35 days. The dashboard it feeds is missing about 50 of 75 tracker weeks, so a polished Trend Explorer would show confident trend lines with holes in them.
- Reactivation is treated as a checklist item. Forsta's retention policy is unknown, and the "365-day deletion" claim is already contradicted. If the surveys purge while you build React, the loss is permanent.
- It bundles OIDC, Azure containerisation, FastAPI, AG Grid, Excel/PPT export and a 300-user load test into 35 days for one engineer. That schedule will slip, and the slip will fall on ops work, the part the owner needs most.

**Plan C**
- "A human reactivates the surveys" has no named owner and no deadline. It is the highest-stakes line and the least specified.
- The gate has no deadline either. "External clients confirmed" can stay unconfirmed forever, and the plan then becomes permanent hardening with no commercial outcome.
- Making the repo private on day 1 does nothing for the leaked password, because the credential is already in public history, forks and caches. Rotation has to come before anything else, and the plan must confirm nobody used the old credential.
- Moving to Azure Container Apps in weeks 3–4 still leaves the single engineer as the only person who can run production. The plan fixes the laptop and keeps the bus factor at one.
- Streamlit's built-in OIDC may not meet enterprise auth needs, so the rewrite could return anyway.

**Shared blind spot:** neither plan asks whether the weekly data feed itself is licensed for client resale.

## Response D

**What alarms me as a newcomer: the plan debate is a distraction from a house that's on fire.**

Read cold, this document describes a company whose main data product has these problems:

- About two-thirds of the recent weekly data is missing, and the integrity check says "all good" (exit 0). That check is lying to you. Nobody outside this project would trust a number from this system.
- The whole thing runs on one person's laptop, on a schedule, and it has already failed silently. If that laptop closes, production stops.
- The database password is in a public repo and was pasted into docs by a reviewer. Fixing that is not a "plan" with a gate. It's something you do today, before reading anything else.

Plan G's week-one "triage" is the same list Plan C does on day 1 and week 1, so the real disagreement is only whether to build a React app now. Nobody has asked for that app; the doc says "no external clients today." Building a client-facing product for a client who doesn't exist, on data that is silently incomplete, is how you ship embarrassment. The first customer who spots the gap in the trend chart ends the product.

Jargon I can't evaluate and the doc never explains: "hibernated surveys," "panel-licence terms," "small-cell suppression," "harmonised concepts." If these gate the whole business, they should be in plain words at the top.

Also odd: the doc calls itself a fair frame, yet half its facts exist to knock down the "61.8 s" claim. That feels like winning an argument, not weighing a decision.

**My call:** Plan C. But it's one engineer. Twelve days of work for one person with no backup is the real risk, and neither plan names a second human.

## Response E

You're comparing two roadmaps, but the question is what CIP exists to guarantee. It exists to hold a complete, trustworthy weekly record of consumer sentiment. Your own facts say that guarantee is already broken. About 50 of 75 tracker weeks are missing, and the integrity check exits 0. A UI over a dataset with 67% of recent weeks absent is a polished wrong answer. Plan G's React SPA is also built for clients who haven't asked for it.

Rank every item by one test: is the harm irreversible and on a clock?

1. **Hibernated surveys.** Forsta's retention policy is unknown, and the documented 365 days is already contradicted. Someone could delete these surveys tomorrow. This is the only truly irreversible loss, so it goes first, before any engineering. It is one human action: reactivate or export them, today.
2. **Credential.** Rotating it fixes the leak. Making the repo private does not, because the password is already in public git history and in any clones. Rotate first, then redact.
3. **Integrity exiting 0 on a 67% gap.** This is the root defect: the system can't tell you it is wrong. Fix it before the retry caps and heartbeats, which only help the system say so politely.
4. **Laptop ETL.** Moving ingestion to Azure fixes the firewall-timeout failures at the source, because the job then runs inside the network. Plan C's weeks 3–4 are justified by the cause, not by modernisation.

Plan C's gate on the rewrite is correct, and I'd tighten it. The Streamlit hardening in weeks 3–5 is only needed to the extent that the portal is reachable. Fail-closed auth is cheap. Small-cell suppression and OIDC are speculative until someone outside the company can reach the portal.

Ask the owner one thing before week 2: who reads this data, and what decision changes if it's wrong? That answer decides whether any UI work is justified.

