# Advisor 1: The Contrarian

*Independent sub-agent (Claude Sonnet). It saw only `00-framing/framed-question.md`.*

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
