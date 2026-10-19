# Claude vs Gemini: REA and LLM Council compared

**Inputs compared**

| | Gemini | Claude |
|---|---|---|
| REA | `docs/REA Gemini/` (8 files) | `docs/REA Claude/` (6 files) |
| LLM Council | `docs/LLM Council Gemini/` (9 files) | `docs/LLM Council Claude/` (this folder) |

The claim-by-claim check of Gemini's REA is in [`docs/REA Claude/04-gemini-verification.md`](../../REA%20Claude/04-gemini-verification.md).

## 1. Method

| | Gemini | Claude |
|---|---|---|
| REA tooling | Claims "REA v42". Shows no REA tool output. | Loaded the REA skill and followed its routing: source repo → normal tools, no binary or runtime providers. Used its checklist and evidence-ledger discipline. |
| Evidence base | Mostly restated `docs/14`, `docs/12` and the README | Code (file:line), logs, `launchctl`, a fresh test run, and **read-only live SQL** against `cip_stg` |
| Checking existing docs | Took the README and docs/14 as true | Re-checked every headline number. Found 6 stale figures. |
| Council | One author writing five voices, a peer review and a verdict | **11 separate sub-agents**: 5 advisors who saw only the framed question; 5 anonymous reviewers with randomised letters; 1 chairman. The moderator fact-checked the peer round before synthesis. |
| Secret handling | Printed the live DB password into 2 docs | Never printed secret values. Used masked shapes, lengths and match counts only. |

## 2. Accuracy (52 Gemini REA claims checked)

| Verdict | Count | Examples |
|---|---|---|
| ✅ Correct | 18 | Architecture, LOAD DATA fallback, two-base design, 51 hibernated, laptop dependency, duplicate index |
| ⚠️ Partly or stale | 18 | Schedule, healthcheck "backoff", 16 vs 19 integrity checks, 365-day deletion stated as fact |
| ❌ Wrong | 12 | 26 FKs (live 39); 10.4 M answers (live 23.3 M); 985 queue (live 2,625); "salted" hash (unsalted); app role read-only (it is the personal ALL account); **Forsta key disabled as the #1 critical gap** (it works; a wave loaded on 20 Oct); MIP's benchmark attributed to CIP; CSRF said to be off (it is on) |
| 🚫 Unsupported or fabricated | 4 | **The pytest transcript**: 237 passed, a pyproject.toml that doesn't exist, wrong per-file counts. Actual: 238 passed. Also benchmark numbers found nowhere in the repo, the "REA v42" framework, and an OpenAI-embedding step with no basis. |

## 3. Coverage: what each found

| Finding | Gemini | Claude |
|---|---|---|
| 51 hibernated surveys | ✅ | ✅, plus scale (about 50 of 75 tracker weeks) and integrity exiting 0 |
| `.env` bare secret | ✅ (and leaked it) | ✅, plus the duplicate, differing `FORSTA_API_KEY` |
| Laptop / firewall dependency | ✅ | ✅, plus two silent mid-retry deaths and a heartbeat fix |
| Streamlit limits | ✅ (inflated with MIP numbers) | ✅, using CIP's own figures (4.36 s at 20 users) |
| Redundant index | ✅ | ✅, plus the bigger unused FULLTEXT index |
| Portal on the personal ALL-privileges account; personal view DEFINER | ❌ missed | ✅ G-03 |
| Untracked code runs in production | ❌ | ✅ G-04 |
| Public repo as a risk | ❌ | ✅ G-05 |
| Alert throttle swallows alerts | ❌ | ✅ G-07 |
| Crash path with no alert | ❌ | ✅ G-08 |
| Tests send real email and Teams messages | ❌ | ✅ G-09 |
| Auth fails open without `APP_ENV` | ❌ | ✅ G-10 |
| Grant script cannot work | ❌ | ✅ G-11 |
| Fresh install fails (syntax error at 001:759) | ❌ | ✅ G-12 |
| 8 views show unverified waves (incl. Trends) | ❌ | ✅ G-13 |
| Excel formula injection | ❌ | ✅ G-15 |
| OIDC not implemented; no logout | ❌ (said OIDC works) | ✅ G-24 |
| Pipeline correctness: lock, fallback, retries, timeouts | ❌ | ✅ G-16 to G-20 |
| Total distinct gaps | 10 REA + 6 council | 44 REA + 12 council |

## 4. Recommendations

| | Gemini | Claude |
|---|---|---|
| Verdict | Triage 1 week, then a 35-day React 19 + FastAPI rewrite for enterprise clients | About 12 engineer-days hardening in place, then a **dated gate** (1 Dec 2026) for the rewrite |
| First action | Delete `.env` lines and rotate the password; send the IT checklist | Send the Forsta admin a written request for the 51 surveys. Rotate the password the same day. |
| Basis for the rewrite | A "5-user wall" that is MIP's data, not CIP's | CIP's own measurements, and docs/12's own "fix, not rewrite" note |
| Feasibility | 35 days for one engineer. The Claude council's Executor estimated it at 10+ weeks. | Phased, with exit checks |

## 5. What Gemini did best (worth keeping)

Credit where it is due. These are better in Gemini's output, or missing from Claude's:

1. **Diagrams.** Mermaid architecture, ER, sequence and Gantt diagrams make Gemini's dossier easier for a business reader to scan.
2. **The "base shift" explanation for clients** (Gemini council, GAP-STRAT-02). A non-statistician sees the base drop from 404 to 71 and thinks it is a bug. Plain-language base badges and tooltips are a good product requirement.
3. **Jargon purge** for any client-facing screen (`DP7r3`, `TOP2`, `stub_key`).
4. **Licence and syndication question.** Gemini's peer round raised the panel-licence question independently. Claude's council reached the same point.
5. **An OpenAPI contract sketch** for the future API. It is useful if the gate opens.
6. **Auto-confirming exact-text mappings** to shrink the review queue. Both reached this.

## 6. Merged best-of-both plan

Use [`../action-plan/01-action-plan.md`](../action-plan/01-action-plan.md) as the backbone (evidence-based, ordered, dated). Add from Gemini:
- Mermaid diagrams for the business audience, redrawn with live numbers;
- base-shift badges and the jargon rule as requirements, **if and when** the gate opens a client UI;
- the OpenAPI sketch as the starting point for docs/13's API.

Discard from Gemini:
- the benchmark table;
- the test transcript;
- the "Forsta key disabled" critical gap;
- the stale counts;
- the OpenAI-embedding step.

## 7. Bottom line

Gemini produced a readable, well-structured dossier. Its correct parts are mostly a restatement of `docs/14`. It invented two pieces of evidence (the test run and part of the benchmark), led with a gap that was already fixed, missed most of the live risks, and **leaked a production password into the repository**.

Claude's investigation re-derived the findings from code, logs and the live database, and found about 4× more gaps. The council was run as genuinely independent agents, and it chose hardening plus a dated gate over an immediate rewrite.

**Model used for the Claude folders: Claude.**
