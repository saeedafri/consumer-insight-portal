# Framed question given to all five advisors

**Decision:** What should Coresight do with the Consumer Insight Portal (CIP) over the next 6 weeks? Two plans compete:

- **Plan G** (from a Gemini review): one week of triage, then a 35-day modernisation:
  - rotate the leaked credential, get a Forsta service key, reactivate the hibernated surveys, add FKs and drop an index;
  - containerise the ETL to Azure and extract a FastAPI service with OIDC;
  - build a 2-screen React 19 SPA for enterprise clients (Trend Explorer and an AG Grid crosstab with Excel/PPT export);
  - load-test for 300 users.
  - Later options: an AI copilot, data syndication.
- **Plan C** (from a Claude review): about 12 engineer-days of hardening in place, then a **gate** before any rewrite:
  - Day 1: stop the exposure (rotate the leaked password, redact the docs that leaked it, make the public repo private, commit the untracked production code).
  - Week 1: recover the missing data. A human reactivates or exports the 51 hibernated surveys, and integrity fails loudly on coverage gaps.
  - Weeks 1–2: make failures loud (alert throttle, crash handler, run lock, retry cap, DB timeouts, heartbeat, stop tests sending real email).
  - Week 2: least privilege and schema fixes.
  - Weeks 3–4: move ingestion to an Azure Container Apps job.
  - Weeks 3–5: harden the internal Streamlit portal (fail-closed auth, Streamlit's built-in OIDC, formula escaping, small-cell suppression).
  - The React/FastAPI rewrite opens only when external clients are confirmed, concurrency is proven to be the limit, ops is fixed, and panel-licence terms are cleared.

**Verified facts (20 Oct 2026, from code, logs and read-only live queries):**

What it is:
- CIP automates the weekly Forsta consumer survey (about 400 US respondents) into Azure MySQL `cip_stg`.
- 320 verified waves (2018 onward), 179,612 respondents, about 23.3 M answers, 1,789 harmonised concepts, a 2.1 M-cell pre-computed cube.
- Wave 412 matched Forsta exactly, 147,635 answers with 0 differences. 238 tests pass.
- Built by one engineer (the owner).

Data coverage:
- 51 closed Forsta surveys are hibernated and were never loaded. This includes 43 weekly tracker waves, Jul 2025 – Jun 2026, so about 50 of 75 tracker weeks since May 2025 are missing.
- The integrity run still exits 0.
- Forsta's real retention policy is unknown: the documented "deleted after 365 days" is contradicted by 460-day-old surveys still listed.

Operations:
- The ETL runs from launchd on the owner's MacBook, every 30 minutes on Mon–Wed and 3 times a day otherwise.
- It failed on 5 of the last 10 days from DB firewall timeouts; two runs died silently.
- It runs **untracked** code (`etl/integrity.py` is not in git).

Security:
- The GitHub repo is **public**. It contains DB host names, internal docs and personal paths.
- `.env` has a bare DB password. The Gemini review copied that password verbatim into two untracked docs in the repo.
- The portal and the views use the owner's personal ALL-privileges MySQL account. The grant script is broken (it uses table-name wildcards).
- Portal auth is a shared passphrase. The SSO button is not implemented. Auth fails open if `APP_ENV` is unset.

Pipeline defects:
- The alert throttle marks an alert sent before it sends, so failed sends are swallowed.
- A crash after the DB check gives no alert.
- Running pytest sends real email and Teams messages.

Portal state:
- Streamlit, internal only, run locally. No external clients today.
- The React + FastAPI design (docs/13) is marked "proposed".

Performance:
- CIP's own benchmark: the Overview page median is 0.56 / 1.16 / 1.99 / 4.36 s as load rises to 20 concurrent users, versus 0.12 s for a static page + FastAPI.
- The "6.3 s at 5 users, 61.8 s at 30" figures often quoted are from a different app (MIP).
- The repo's own decision doc says "Streamlit written well" is acceptable for internal tools under about 10 concurrent users, and that an independent review recommended fixing, not rewriting.

**What is at stake:**
- Permanent loss of a year of tracker history.
- A credential leak through a public repo.
- One person being the only way production runs.
- Versus: the commercial upside of a client-facing product, and the risk of spending 5+ weeks on a UI no client has asked for yet.
