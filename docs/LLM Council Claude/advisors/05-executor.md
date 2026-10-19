# Advisor 5: The Executor

*Independent sub-agent (Claude Sonnet). It saw only `00-framing/framed-question.md`.*

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
