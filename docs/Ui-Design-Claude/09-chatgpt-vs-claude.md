# 09 · ChatGPT vs Claude: what each got right, and the merged result

**Compared:**
- [`docs/UI-Design-ChatGPT/`](../UI-Design-ChatGPT/ChatGPT-Recommended_design.md): `ChatGPT-Recommended_design.md` plus the 8-chapter `CIP_Architecture_Review/`, built from `code-baseall.zip`.
- This folder (Claude).

**Checked:** 20 Oct 2026. Every ChatGPT code finding below was re-checked against this repository.

## 1. Both reached the same decision

| | ChatGPT | Claude |
|---|---|---|
| Client UI | React + TypeScript + Vite, static | Same |
| API | Python FastAPI, modular, reuses the data layer | Same |
| Data | Keep MySQL + the cube + the Python ETL | Same |
| Streamlit | Internal tools only, not the subscriber shell | Same |
| Next.js server mode | Only if server rendering is needed | Same |
| Node/Fastify | **"Strongest alternative"** if the team is TypeScript-strong | Not optimal: measured the **same** user-visible speed, but means rewriting verified Python |
| Worst pattern | Unbounded raw data in the web process, inline heavy work, no limits, **in any language** | Streamlit "load the table" (the SIP/MIP habit) |

Two independent reviews, using different evidence, landed on the same stack. That agreement is itself a strong signal.

## 2. Where ChatGPT was better, adopted into the final design

| # | ChatGPT point | Verified? | Adopted in [06](06-system-design.md) |
|--:|---|---|---|
| 1 | **Our benchmark was not a matched workload**: the API page had no chart or selector, the timer used a text marker, and tabs piled up | ✅ Fair (`api_page.py`, `page_load.py`) | **Re-ran matched**, with load and click, in [02 §0](02-benchmarks.md). The conclusion held: click at 40 users is Streamlit 2.85 s vs FastAPI 0.12 s. |
| 2 | **Subscriber data must not sit in a public CDN cache** | ✅ Correct, and our first design did put packs on the Front Door edge | Packs are `private` in the browser cache only. Front Door is for static files only. |
| 3 | **Versioned publication with an atomic pointer**; never delete the only good cube | ✅ `cube.refresh_wave` deletes cells, commits, then rebuilds (`app/data/cube.py:171-181`) | §4: `dataset_version` + published pointer |
| 4 | **Cohort change check (count + sum of IDs) can collide**, e.g. {1,4} vs {2,3} | ✅ `cube.py:153-155` | §4: membership digest |
| 5 | **Durable job records with leases**; exports out of requests | Design point | §2, §5: `cip_job` + one worker |
| 6 | **Entitlements, default deny**; key users by IdP subject, not email; tenant scope for shared views | ✅ Gaps exist (`repository.py:698-743`; no product checks) | §6 |
| 7 | **Apps on one App Service plan share its RAM**; ask IT what "4.5 / 9.88" really is | ✅ Microsoft documents this | §7.2, plus IT questions |
| 8 | **DB pool is per engine per process** (10 + 20 today), and it multiplies | ✅ `config.py` | §8: 5 + 2 per worker |
| 9 | **Login has a 1-second sleep** | ✅ `app/pages/0_Login.py:56` | Removed in the new design. Fix it in Streamlit too. |
| 10 | **Whole-wave report fetches every answer and verbatim** without paging | ✅ `repository.py:123-148` | Bounded, paged verbatims under a separate entitlement |
| 11 | **Targets as INP / LCP / p95**, not "milliseconds everywhere"; the network cannot be beaten | ✅ web.dev thresholds | §3 targets |
| 12 | **Vertical slice on the real server before full migration** | Design point | §11 gate 2 |
| 13 | Low-code self-hosting has real infrastructure needs (Appsmith 2 vCPU / 8 GB; ToolJet + PostgreSQL + Redis) | ✅ Vendor docs | Strengthens "not optimal" in [03](03-technology-comparison.md) |
| 14 | Careful epistemics: observed vs measured vs proposed, with honest limits | — | Same labelling kept |

## 3. Where Claude went further, or ChatGPT could not reach

| # | Point | Why it matters |
|--:|---|---|
| 1 | **Measured the frameworks.** ChatGPT ran one Python-vs-Python data-path test and declined to measure frameworks. Claude ran matched journeys with load + click for Streamlit 1.55 (and 1.66), Dash, FastAPI, Node and the in-browser pack. | Turns "best fit" into evidence. The pack click takes **20 ms**. Node = FastAPI for users. Streamlit's click time rises in a straight line with simultaneous users. |
| 2 | **Production evidence from Azure.** SIP peaked at 6.9 / 8 GB with a 22 s worst response; MIP at 3.2 / 4 GB with 44.7 s. MIP staging logs show a 240 s render. | ChatGPT had only the CIP zip, so it could not verify SIP or MIP. Claude verified them claim by claim against the real repos, and corrected the earlier docs (the "5-user wall" was a laptop test). |
| 3 | **The in-browser data pack**, measured at 60 KB gz per whole wave | This is the design element that delivers millisecond clicks. ChatGPT kept "local interactions" generic. |
| 4 | **The test suite actually runs: 238 passed.** ChatGPT's environment failed collection with 10 import errors. | The core is green. |
| 5 | **Real prices**: Azure Retail Prices API; 38 marketplace products priced at 300 and 1,000 viewers | ChatGPT declined to price Azure and put **Zoho Analytics** first, without checking survey statistics. Zoho has no significance letters or weighted bases ([04](04-marketplace-buy-vs-build.md)). |
| 6 | **The MySQL tier.** Staging is Burstable B2s and peaked at 100 % CPU. | A concrete ask to IT ([06 §9](06-system-design.md)) |
| 7 | **Live security exposure.** The repo is public, and `code-baseall.zip` (with `.env`) plus a DB password were pushed on 20 Oct. | ChatGPT advised rotating secrets in the zip. It could not see that the zip itself had been pushed to the public repo. |

## 4. Where ChatGPT was too cautious, or slightly off

- **"Do not derive any user capacity from RAM."** It is right that RAM alone is not enough. But measured per-process memory (FastAPI 69–100 MB flat; Streamlit "load table" peaking at 3.7 GB) *does* bound what fits. The final design budgets memory from measurements and leaves user counts to qualification.
- **"Node/Fastify is the strongest alternative."** Fair if the team were TypeScript-backend-strong. The measured journey shows no user benefit, and the Python domain logic (significance tests, cohorts, harmonisation) would have to be duplicated or bridged. It stays an alternative, not a recommendation.
- **Marketplace ranking.** Its buy shortlist started with Zoho Analytics (as the India-origin option), then Metabase and Power BI, judged on embedding features. For survey cross-tabs with significance letters, the closest products are Displayr, Harmoni and Crunch. All are per-viewer priced and still lose to build for CIP.

## 5. The merged answer

The final design is in [06-system-design.md](06-system-design.md).

**React 19 + TypeScript (Vite, static)** in the browser:
- an in-browser pack engine: 20 ms clicks [M];
- ECharts and AG Grid Community.

**FastAPI (Python)** on the server:
- a modular API with entitlements, private versioned packs, and a byte-capped version-keyed cache;
- single-flight and admission control.

**One job worker** for ETL, versioned cube builds and exports, with **leases in MySQL**.

**Azure MySQL** on a General Purpose tier, holding:
- the versioned cube and an atomic published-version pointer;
- sessions, entitlements, views, jobs and audit.

**All of it on the one server IT provides.** No Redis, no broker, no Node server, no Kubernetes.

**Proven by:**
1. a vertical slice on that server;
2. a load + soak test;
3. the Council's 1 Dec 2026 gate.
