# 91 · Gap closure and re-analysis (24 Oct 2026)

What was built to close the five top-of-market gaps (weighting, index scores, open-ended coding, public API,
MCP) plus plain-English search, measured on the live data, and where CIP now stands against the competitors in
`60-competitors-and-market-gaps.md`. Gemini's review was checked claim by claim; the results are in
`docs/REA Gemini Deep Dive 2026-10-23/100-CLAUDE-STATUS-FOR-GEMINI-2026-10-24.md`.

## 1. What was built

| Gap | Built | Files | Tests |
|---|---|---|---|
| Census weighting | Raking per wave to US adult shares by gender, age band and Census region (ACS 2023, `config/weighting.yml`); weights trimmed to 0.2–5× and averaging 1; respondents missing a variable sit out that margin only. Each book carries weighted figures for Total, gender, generation, prior week and last year (`row.w`). A **Weighted / Unweighted** switch in the header; unweighted is the default so screens still match Forsta and the team's Excel files. Significance stays on unweighted counts. | `etl/weighting.py`, `app/data/payloads.weighted`, `web/src/weight.ts`, `Shell.tsx` | `tests/test_weighting.py` |
| Index scores and audience profile | Audience table: Index = 100 × audience % ÷ everyone's %. "What sets this audience apart": across every question of the wave, the top 15 over- and under-indexing answers, significant only, on answers ≥ 5 % of everyone. | `api/team.py` (`_compare`, `audience_profile`), `POST /api/v1/waves/{id}/audience/profile`, `Audience.tsx` | `tests/test_team.py` |
| Open-ended coding | Every text question is coded into themes: Claude (`claude-haiku-5-5`) when `ANTHROPIC_API_KEY` is set, otherwise frequency coding (answers two or more people gave, near-spellings merged; "n/a" and the like grouped). Emails and phone numbers are stripped before coding. The book charts each coded question by Total, gender and generation. Runs after each weekly load. | `etl/open_ends.py`, `payloads.open_group`, `scripts/weekly_forsta.py` | `tests/test_open_ends.py` |
| Public API | Personal API keys: `Authorization: Bearer cip_…` on every `/api/v1` route, with the person's own access and a rate limit (`limits.api`, 120 a minute). Keys are stored as SHA-256 only, outside the repository. nginx passes key requests through to the API. | `app/core/api_keys.py`, `api/signin.user`, `deploy/cip_auth.js` | `tests/test_mcp.py` |
| MCP connector | `POST /mcp`, streamable HTTP, stateless JSON-RPC. Tools: `search_questions`, `list_waves`, `question_results` (optionally weighted), `question_trend` (one wording only), `crosstab` (any two cuts). Auth by API key. | `api/mcp.py`, `deploy/cip_locations.conf` | `tests/test_mcp.py` |
| Plain-English search | Question words ("what do people think about…") are dropped before matching; a sentence that matches nothing in full is ranked by how many of its words match, before falling back to word fragments. | `api/search.py` | `tests/test_search.py` |

The whole suite passes (332 tests); the UI type-checks and builds.

### Is MCP needed? Is a vector database needed?

- **MCP: yes, and it is cheap.** Four of the five closest competitors (Morning Consult, GWI, Statista, Attest)
  advertise Claude/ChatGPT connectors on their own sites (checked 24 Oct). CIP's connector is about 200 lines
  on the existing API and access rules; no new service or dependency.
- **Vector database: no.** The library is about 3,700 question wordings. SQLite FTS5 with stemming, synonyms,
  typo correction and question-word removal answers in about a millisecond, and through MCP the client's model
  does the semantic step itself (it rephrases and searches again). A vector index would add an embedding model and
  a service to run, for no measured gain. Revisit if the zero-result search log shows meaning-level misses.

### Using the API and the connector

```bash
python -m app.core.api_keys new ana@coresight.com "Ana's Claude"   # prints the key once
curl -H "Authorization: Bearer cip_…" https://<portal>/api/v1/waves
claude mcp add --transport http cip https://<portal>/mcp --header "Authorization: Bearer cip_…"
```

Claude Desktop and other clients take the same URL and header. claude.ai's web connectors need OAuth, which the
portal will get with company sign-in on the Azure VM.

## 2. Measured on the live data

**Weighting, the latest 8 weekly tracker waves:**

| Wave | n | Weight range | Design effect | Effective n | Mean shift (pts) | Largest shift | Rows moving > 3 pts |
|---|---|---|---|---|---|---|---|
| 415 (19 Oct) | 400 | 0.72–2.29 | 1.14 | 350 | 1.0 | 6.2 | 42 / 575 |
| 412 (12 Oct) | 404 | 0.82–1.95 | 1.08 | 373 | 0.8 | 9.7 | 17 / 640 |
| 266 (5 Oct) | 401 | 0.77–2.09 | 1.11 | 361 | 0.9 | 14.6 | 23 / 578 |
| 235 | 403 | 0.87–1.29 | 1.01 | 399 | 0.3 | 2.7 | 0 / 746 |
| 265 | 404 | 0.65–1.47 | 1.09 | 371 | 0.8 | 6.0 | 16 / 646 |
| 264 | 402 | 0.70–2.41 | 1.14 | 352 | 1.1 | 11.6 | 44 / 542 |
| 260 | 403 | 0.80–2.41 | 1.16 | 349 | 1.2 | 10.7 | 45 / 543 |
| 258 | 401 | 0.62–3.84 | 1.34 | 300 | 1.4 | 21.9 | 66 / 560 |

The Forsta quotas already keep the sample close to the Census: weighting moves a typical figure by about one
point and costs about 10 % of the effective sample. The large shifts are on small sub-bases. Example (wave 415,
"met up with friends or family locally"): 62.2 % unweighted, 60.2 % weighted.

**Search** (real catalogue, before → after):

| Query | Before | After |
|---|---|---|
| what do people think about tariffs | 1,586 fragment matches | 275, tariff questions first (T1, T2) |
| do consumers trust brands | 308 fragment matches | 45, trust questions first |
| how are shoppers feeling about inflation | (fragments) | 789, two inflation questions in the top 3 |
| weight loss drugs | 10 | 10 (unchanged: already worked) |

**MCP** on a test instance (:8001): initialize, tools/list and all five tools answered; no key and a wrong key → 401.

## 3. Where CIP stands now

| Capability | Before (23 Oct) | Now | Leaders |
|---|---|---|---|
| Census weighting | none | raked by gender, age and region, switchable | Morning Consult, YouGov, GWI |
| Index scores / distinctiveness | none | index per answer and an audience profile | YouGov Profiles, GWI |
| Open-ended coding | not shown | coded and charted (frequency; Claude when keyed) | Attest, Suzy, Displayr |
| Public API | none | API keys on every route | GWI, Statista, Attest, Morning Consult |
| AI connector (MCP) | none | 5-tool MCP connector | Morning Consult, GWI, Statista, Attest |
| Plain-English search | word matching | question words dropped, best-match ranking | Statista Consumer AI |
| Speed | 0.3–8 ms reads | unchanged | (not published by competitors) |
| Hosting | laptop + quick tunnel | unchanged until the Azure VM (IT, ~26 Oct) | managed cloud |

## 4. Still open

1. **Hosting**: the Azure VM (IT). Until then a quick-tunnel link can expire, as it did on 24 Oct.
2. **Weighting beyond the wave screens**: Trends, Compare, the topic dashboards and cross-tabs are still unweighted.
3. **Claude coding**: set `ANTHROPIC_API_KEY` on the server, then `python -m etl.open_ends --all` re-codes with Claude.
4. **Key admin screen**: keys are issued from the command line; an admin page can come with company sign-in.
5. **ACS targets** are rounded; check them against the latest ACS release before quoting weighted figures to clients.
6. **Sample scale** (400 a week against competitors' tens of thousands) is a business decision, not a code gap.
