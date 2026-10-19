# 01 · Evidence from SIP and MIP: verified, with corrections

**What this is:** every claim in [`docs/12-ui-technology-decision.md`](../12-ui-technology-decision.md) re-checked on 20 Oct 2026 against the real repositories, logs and the Azure usage export.

**Rules followed:** read-only; no server or database touched.

**What changed:** where docs/12 overstated the case against Streamlit, this file corrects it. The recommendation has to survive the fairest reading of the evidence.

**Repositories used**

| App | Repository | Branch / note | Commits |
|---|---|---|---|
| SIP | `All-Code-Base/SIP-Prod` | `pro-deploy`, production | 1,027 |
| SIP | `Code-Base/Modular-Code` | `stg-deploy`, 2 commits ahead of `pro-deploy` | 1,028 |
| MIP | `All-Code-Base/market-data-stg` | `stg-deploy`, deployed | 747 non-merge |
| MIP | `Code-Base/Real/CapIQReplacement` | Holds MIP's specs, `OIDC_FLOW.md` and logs | 121 |
| MIP-FAST-React | `All-Code-Base/MIP-FAST-React` | A React + FastAPI port, created 18 Oct 2026, not in git | — |

## 1. Production evidence from Azure (strongest: measured on the real servers)

Source: `~/Downloads/SIP & MIP Info.xlsx`, Azure portal export, last 3 months.

| App Service | SKU | RAM | Average memory | **Peak memory** | Average response | **Worst response** |
|---|---|--:|--:|--:|--:|--:|
| `csr-awa-sip-portal-pro` (SIP prod) | P1v3, 2 vCPU | 8 GB | 1.8 GB | **6.9 GB (86 %)** | 15.6 ms | **22.0 s** |
| `csr-awa-marketdata-pro` (MIP prod) | P0v3, 1 vCPU | 4 GB | 1.4 GB | **3.2 GB (80 %)** | 60 ms | **44.7 s** |
| `csr-awa-data-portal-stg` (MIP stg) | P0v3 | 4 GB | 0.93 GB | **3.4 GB (85 %)** | 46.4 ms | **1.92 min** |
| `vis-portal-stg` (SIP stg) | P0v3 | 4 GB | 0.78 GB | **3.1 GB (78 %)** | 17.7 ms | **50.5 s** |

- **Peaks.** Every Streamlit app has peaked at 78–86 % of its server's memory.
- **Averages hide the stalls.** Average response times look healthy (15–60 ms) because Azure counts the small websocket frames. The worst cases are 22 s to 1.9 min. Users feel the worst cases, not the averages.
- **These are the boxes CIP would get.** CIP staging (about 4.5 GB) and production (about 9.88 GB) are the same class: P0v3 = 4 GB and P1v3 = 8 GB in the export. The "4.5" and "9.88" figures are as quoted by the business. The SKU behind them is unknown.

## 2. MIP Azure-staging logs, 12–19 Oct 2026

| Measure | Value | Source |
|---|---|---|
| Click-to-render, 758 renders | median 0.30 s · p95 **4.30 s** · max **62.19 s** (screening, 16 Oct) | `CapIQReplacement/server-logs/server-logs-20261019_075003.log:3625` |
| Click-to-render, 12–17 Oct | max **240.74 s** (screening, 15 Oct) | `CapIQReplacement/logs/server-logs-20261016_193052.log.gz` |
| Slow DB queries | 62,120 lines, median 2.7 s, max 213.9 s | `server-logs-20261019_075003.log:47644` |
| Memory | median 1,491 MB, **peak 2,736 MB with 367 MB free** (18 Oct) | `server-logs-20261019_075003.log:124847` |
| Process starts | 13 boots between 12 and 17 Oct | `server-logs-20261016_193052.log.gz` |
| 3 Jul Newsroom | render **106 s** with 2,764 MB used, 344 MB free | `logs/server-logs-20260703_022556.log:9476` |

Much of this time is database work, not Streamlit. Queries taking 2.7 s on median are an indexing and data-model problem that has to be fixed on any stack (§5).

## 3. MIP load tests: the corrected reading

docs/12 attributed its headline "**6.3 s at 5 users, 16.1 s at 10, 37.8 s at 20, 61.8 s at 30**" to "MIP's own staging server". **That attribution is wrong.**

- **Where it actually ran.** The 1 Oct test ran on a MacBook (`localhost:8531`) against the staging database over VPN. The server and 30 browsers shared the laptop, and Streamlit's file watcher was on. Source: `2026-10-01-mdp-full-e2e-timing-ram-capacity-report.md:4-7, 303-304`.
- **What the CPU was doing.** At 10 users, the report's own breakdown was:
  - 32 % parsing 10-K filings
  - about 15 % Azure Blob/TLS
  - 10 % the file watcher
  - only **11 % page scripts**

  Source: same report, `:170-178`. Average CPU was 69–73 %, not 97–99 % (`:865-869`).
- **The staging-like re-run, 17 Oct.**

  | Users | p50 | p95 | Note |
  |--:|--:|--:|---|
  | 6 | 0.6 s | — | |
  | 10 | 1.0 s | 4.4 s | 1.64 page loads/s |
  | 16 | 4.4 s | 8.5 s | 78 % CPU |

  Memory went from 396 to 624 MB, about **8 MB per extra session**. Source: `2026-10-17-gemini-change-review-and-capacity-design.md:82-92`.

**Fair conclusion:** a tuned Streamlit process handles about **10 heavy or 30–40 light users** before p95 passes about 5 s. It is still one process and one core, and time still climbs with every user. Our own controlled benchmark ([02](02-benchmarks.md)) agrees on the *shape*: 0.33 s at 1 user → 4.35 s at 40, about 0.1 s per extra simultaneous user.

## 4. Where SIP's effort went (verified)

| Claim | Status |
|---|---|
| 1,028 commits, 25 Nov 2024 – 14 Oct 2026 | ✅ |
| 403 of 958 non-merge commits change re-run, session-state, raw-HTML or injected-script code | ✅ (docs/12 says 402) |
| Sign-in commits | ≈ 295. Depending on method: 175 by subject keyword, 320 by keyword plus auth files |
| April 2026 OIDC crisis: 109 commits, 22 on 9 April | ✅ |
| September 2025 cookie crisis: 91 | ≈ 104 by the same method |
| `login.py` + `auth_utils.py` = 4,295 lines, 267 commits | ✅ |
| 52,408 lines in 74 app files; 19,478 dead lines in `pages/old/` | ✅ |
| Code shape | ✅ All match:<br>• `st.session_state` 877 (868 committed)<br>• `unsafe_allow_html=True` 194<br>• `st.rerun()` 83<br>• `<script` 34<br>• `window.parent` 21<br>• threads 30<br>• `time.sleep` 18 |
| `patch_streamlit_splash.py` rewrites Streamlit's installed `index.html` | ✅ (`:163`). MIP does the same (`app/core/boot_overlay.py:199,231`). |
| Four ~53k-line revert commits "September 2025" | ❌ They were **27–28 January 2026** |

**Fixed since, so no longer live problems.** docs/12 presented these as current:
- **SIP out-of-memory with 1–2 users.** The cause was the glibc allocator keeping freed memory. It was fixed with `MALLOC_ARENA_MAX` and `malloc_trim` (`02-problems-findings-fixes.md:46-53`). This would hit any pandas server on Linux, not only Streamlit.
- **About 502 MB per user from `st.cache_data`.** Fixed by switching to `cache_resource` (`active_data.py:1644-1649`).
- **The 142 s stall on cache expiry.** Marked fixed (`2026-08-07-sip-speed-and-ram-investigation.md:201`). After the fixes, SIP's RAM is flat at about 400 MB for 1–3 sessions.
- **"Excel build 2.3 GB".** That was total process memory; the workbook itself added +540 MB.
- **The store-map 221–242 s figure.** Its source log no longer exists, so it is dropped.

## 5. Where MIP's effort went (verified)

| Claim | Status |
|---|---|
| 743 deployed non-merge commits, 4 authors | ✅ |
| 72 sign-in commits | ✅ |
| History length | About **8 months** of real work (from 25 Feb 2026), not 12 |
| `st.rerun` 21 → 144; threads 2 → 43 (3 Mar → 17 Oct) | ✅ |
| `session_state` 404 → 1,727 | ≈ 401–436 → 1,755 |
| `OIDC_FLOW.md` 2,118 lines | ✅ |
| Its workarounds:<br>• a cookie check<br>• dedup of the single-use login code in `/tmp`<br>• six logout fallbacks | ✅ (`:1476-1482`, `:1628-1632`, `:1756-1761`) |
| 17 Oct review: "189 of 198 caches unbounded; fix, don't rewrite" | ✅ (`2026-10-17-independent-investigation-design.md:52,122`) |
| Incidents:<br>• 2 Jul: 0 of 24 actions met the 1 s target<br>• 17 Jul: blank home page<br>• 19 Jul: 18 restarts<br>• 30 Jul: oversized websocket message (102 MB workbook, 136 MB once encoded)<br>• 30 Sep: PDF freeze (local) | ✅ |

## 6. Security: framework-forced vs our own

| Finding | SIP | MIP | Caused by Streamlit? |
|---|---|---|---|
| Session cookie written by JavaScript, so it cannot be HttpOnly | ✅ `auth_utils.py:165` | ✅ `auth_manager.py:335-344` | **Yes.** Python code cannot set a response cookie. `st.login` (since 1.42) now covers identity, but not custom sessions. |
| Session cookie not signed or verified | ✅ `auth_utils.py:86-100, 220-255` | ✅ `auth_manager.py:1020-1050` | **No.** HMAC-signing was possible. The React port (MIP-FAST-React) *also* kept an unsigned, non-HttpOnly cookie (`backend/auth.py:146-168`). |
| XSRF protection off | ✅ `.streamlit/config.toml:5` | ❌ (on by default) | No, it is a setting. docs/12 wrongly said "both". |
| Logs page that runs shell commands, without a real login | ✅ `pages/logs.py:43-48, 66-70` | ✅ `app/pages/logs.py:43-52, 85-86` | No |
| Login check commented out on pages | 2 password gates (`store_tracker*.py`) | 6 routed pages | No |
| Secrets committed | `.streamlit/secrets.toml`; DB-password fallbacks in `pages/store_tracker*.py` | `.env2` in CapIQReplacement (GitHub) | No. **Rotate these credentials.** |

**Lesson:** a new framework does not fix security by itself. MIP-FAST-React proves it: same unsigned cookie, now in FastAPI. The design in [06](06-system-design.md) specifies the controls explicitly, and the build has to implement them.

## 7. MIP-FAST-React: not usable as evidence

It looks like same-app proof, but it is not:
- **Mostly not real React.** Only 5 routes have real React pages. Most other pages replay captured Streamlit HTML. The current source would not build: `App.tsx:38` imports a missing file.
- **Its benchmark numbers have no source.** The README's figures cite result files that **do not exist**. `benchmark_proof.py` never measures Streamlit. `test_browser_e2e.py` hard-codes `"PASS"` and fixed time splits.
- **One fact is usable:** its production build's **entry bundle is 81 KB gzipped**, against Streamlit's own entry script at **512 KB gzipped** ([02 §7](02-benchmarks.md)).

## 8. What survives, in one paragraph

**Measured in production**
- Streamlit apps peak at about 80–86 % of server memory, with 22 s to 2 min worst-case responses, on the same server class CIP will get.

**Measured under control**
- Even well-written Streamlit adds about 0.1 s per simultaneous user, because one process re-runs one script per user.
- A static page plus an API stays flat.

**Verified history**
- SIP spent about 30 % of its commits on sign-in and Streamlit workarounds; MIP about 22 %.

**Corrected**
- The "5-user wall" overstates it. Tuned Streamlit holds about 10 heavy users per process.
- Several SIP memory disasters were our own allocator and cache mistakes, now fixed.
- Security holes mostly came from our own code, not from the framework.

The case against Streamlit **for a client product with hundreds of users** still stands on the measured scaling slope, the per-session execution model and the cookie constraint. It does not rest on the discredited numbers.
