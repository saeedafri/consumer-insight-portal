# Advisor 2: The First Principles Thinker

*Independent sub-agent (Claude Sonnet). It saw only `00-framing/framed-question.md`.*

You're comparing two roadmaps, but the question is what CIP exists to guarantee. It exists to hold a complete, trustworthy weekly record of consumer sentiment. Your own facts say that guarantee is already broken. About 50 of 75 tracker weeks are missing, and the integrity check exits 0. A UI over a dataset with 67% of recent weeks absent is a polished wrong answer. Plan G's React SPA is also built for clients who haven't asked for it.

Rank every item by one test: is the harm irreversible and on a clock?

1. **Hibernated surveys.** Forsta's retention policy is unknown, and the documented 365 days is already contradicted. Someone could delete these surveys tomorrow. This is the only truly irreversible loss, so it goes first, before any engineering. It is one human action: reactivate or export them, today.
2. **Credential.** Rotating it fixes the leak. Making the repo private does not, because the password is already in public git history and in any clones. Rotate first, then redact.
3. **Integrity exiting 0 on a 67% gap.** This is the root defect: the system can't tell you it is wrong. Fix it before the retry caps and heartbeats, which only help the system say so politely.
4. **Laptop ETL.** Moving ingestion to Azure fixes the firewall-timeout failures at the source, because the job then runs inside the network. Plan C's weeks 3–4 are justified by the cause, not by modernisation.

Plan C's gate on the rewrite is correct, and I'd tighten it. The Streamlit hardening in weeks 3–5 is only needed to the extent that the portal is reachable. Fail-closed auth is cheap. Small-cell suppression and OIDC are speculative until someone outside the company can reach the portal.

Ask the owner one thing before week 2: who reads this data, and what decision changes if it's wrong? That answer decides whether any UI work is justified.
