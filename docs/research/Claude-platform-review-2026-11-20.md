# Consumer Intelligence Platform: senior review, ETL to browser (20 Nov 2026)

Who reads this: the owner, IT, the research team, and every agent before the next change. It builds on the two
reviews of the same day (Codex: `CIP-platform-and-Ask-review-2026-11-20.md`; Gemini:
`Gemini-CIP-platform-and-Ask-review-2026-11-20.md`). It does not repeat them. Each finding below is marked:

- **Measured**: I ran it on 20 Nov (numbers below).
- **Code**: I read the code path on 20 Nov and it does what is described.
- **Reported**: from Codex or Gemini, not re-run by me.

## 1. The honest verdict

The architecture is right for this product and this traffic. Prebuilt files served by nginx, one API worker and
caches keyed by the published version give sub-millisecond cached reads and never show stale data after a publish.
**Speed, RAM and CPU are not where CIP is behind.**

CIP is behind in five places:

1. **Security hygiene.** The GitHub repo is public. Its history holds the staging session secret, the admin token,
   the database passwords, the Forsta key, the email password and the Teams webhook. Three of these look unrotated.
2. **Nothing checks a commit before it goes live.** The Bitbucket pipeline builds and deploys. It runs no tests.
   The 648 tests run only in GitHub CI, which does not gate the deploy.
3. **One box does everything.** On 1 vCPU, one container runs nginx, the API, Ask's models, Excel exports, the
   weekly ETL and the publish. Any restart takes the site down for about 75 to 90 seconds while files restore.
4. **Data checks report problems but never stop them.** A wave whose answers differ from Forsta is still published,
   its alerts fire, and the team gets the "loaded" email. The email also goes out when the publish failed.
5. **Ask CIP's ceiling is its design, not its model.** Understanding a question is a 304-line function of
   wording rules. Each new phrasing needs a new rule. A 550-billion-parameter model as a second reader added
   nothing on the fresh questions.

### Scorecard

| Area | Grade | Why, in one line |
|---|---|---|
| Serving speed and latency | A- | Cached reads 0.6 ms p50; 3,600 requests/s at p95 2.6 ms with 8 parallel callers (Measured, API alone) |
| RAM and disk | A- | 254 MB at start, 463 MB with Ask's models, of 4 GB; 88 MB per published version, 3 kept (Measured) |
| Caching layers | B+ | Every layer keyed by the published version; misses are not shared between callers, caches are per process |
| Code quality | B | Readable, explained, 648 tests; three files over 800 lines, Ask's `answer()` is 304 lines |
| Ask CIP | B- | Fast and honest about what it cannot do; 154/161 golden, 46/50 fresh; meaning handled by wording rules |
| Frontend and UX | B | Strict page security policy, charts split out; 606 KB of gzip JS in total, chart-only screens, mobile drawer gaps |
| Data correctness | C+ | Strong reconciliation exists but does not block; three statistics mismatches open |
| Reliability and failover | C | Atomic publish and restore; single instance, no deployment slot, no database dump since the Mac jobs stopped |
| Monitoring | C+ | Logs page, machine numbers, failure emails; nothing outside the box watches it |
| Release safety | D | No test gate on the deploy path; no automatic rollback |
| Security | D | Good headers, cookies, sign-in and access checks, undone by public leaked secrets |

## 2. Do these first (in order)

| # | Action | Owner | Effort |
|---|---|---|---|
| 1 | Make the GitHub repo private today. Rotate `CIP_SESSION_SECRET` (this also signs everyone out), `CIP_ADMIN_TOKEN`, `FORSTA_API_KEY`, `EMAIL_PASSWORD`, the Teams webhook and `APP_DB_PASSWORD`. Then remove the two files from history (`git filter-repo`) and turn on secret scanning and push protection. | You, IT | 2 hours |
| 2 | Run `pytest -q` in the Bitbucket build step before the image is built, so a failing commit never deploys. About 1.5 minutes a build. | You (pipeline) | 1 hour |
| 3 | Stop announcing bad data: when reconciliation finds differences or the publish fails, hold the "loaded" email and the alerts, and exit non-zero so the Logs page shows red. | Code | Half a day |
| 4 | A staging deployment slot warmed on `/readyz`, then swapped. Zero-downtime deploys and a one-click rollback. Settings are already in status/README.md. | IT | 1 hour |
| 5 | Confirm the Azure MySQL backup retention (raise to 35 days) and time one restore. The weekly `mysqldump` stopped with the Mac jobs on 10 Nov. | IT | 2 hours |
| 6 | Move the ETL off the web instance: `CIP_ETL=off` on the web app, the same image as a small second app or WebJob with `CIP_ETL=on`. The image already supports it. | IT, you | Half a day |
| 7 | Ask CIP: one step that reads the question into a typed request (dates, groups, counts versus shares, overlap, weighting) before search, replacing the wording rules. Then 100 human-checked questions before any training. | Code, research team | 1 to 2 weeks |
| 8 | Statistics decisions for the research team: the weekly report's star on the 4-week change (test week t against t-4), the dashboard's quiet-week fallback, answer codes swapped between waves (DATA-01). | Research team, then code | Days |
| 9 | Next.js 16.4.2 → 16.4.6 (1 moderate advisory). Add `npm audit` and `pip-audit` to the pipeline. | Code | 1 hour |
| 10 | Azure Front Door in front of Central US. From India the first byte took about 1.4 s (Codex), most of it distance and TLS. | IT | Half a day |

## 3. Security

**Good, verified in code:** a strict Content-Security-Policy with per-page script hashes, HSTS, `X-Frame-Options`,
`nosniff`, `Referrer-Policy`. Cookies are `HttpOnly`, `SameSite=Lax` and `Secure` over HTTPS. Sign-in uses one
tenant's issuer and checks the token. Every API and MCP tool checks the same menu as its screen. The image's
`.dockerignore` is an allow-list, so no `.env` reaches it. Staging's `/auth/login` goes to Coresight's sign-in,
not the open demo login (checked 20 Nov).

| Finding | Severity | Evidence |
|---|---|---|
| Repo public with staging secrets in history (`cip-staging.env`, `cip_staging.env`, still reachable from `master`) | Critical | Code: `gh repo view` says PUBLIC. The files hold 18 settings, including the session secret, the admin token, both database passwords, the Forsta key, the email password and the Teams webhook. The local `.env` still holds the same Forsta key, email password and webhook. The database owner password differs, so that one was changed. |
| With the leaked session secret, anyone can forge a "sees everything" cookie for any email, unless it was rotated | Critical if not rotated | Code: `deploy/cip_auth.js` trusts any cookie signed with the secret; scope `*` passes nginx with no API call |
| The API writes with the ETL owner account | Medium | Code: `shared/core/config.py` maps `api_write` to `STG_DB_USER`. The fix needs IT to create a write-only account. Gemini's patch would point writes at the SELECT-only account and break sign-in. |
| Unknown emails sign in as staff (analyst, enterprise) | Medium | Code: `config/access.yml` `unknown:`. The tenant issuer limits this to Coresight's tenant, which includes guest accounts. |
| MCP calls are not in the access log | Medium | Code: `api/mcp.py` never calls `audit.record`; the REST Ask does |
| Ask's spelling fix uses every survey's words, so it can confirm a word exists in a study the user cannot see | Low | Reported (Gemini GEM-008); real only once client-only studies exist |
| Survey text goes into Excel cells and chart tooltips unescaped | Low | Reported (GEM-026, 027): survey text is written by Coresight, so it is a hardening item |
| Rate limits are per worker | Low | Code: `access.spend` buckets in process memory; correct for today's single worker |

## 4. Release and deploy safety

- **No test gate.** `bitbucket-pipelines.yml` has four steps: build and deploy, staging and production. `next build`
  type-checks the frontend; no Python test runs. Code.
- **No rollback button.** A bad image stays until the next push. `etl.publish --rollback` covers the data, not the
  code. A deployment slot fixes both.
- **The first build after an upgrade notice fails.** Next.js 16.4.2 stops on its security reminder when an
  automated agent runs it; the second build passes. Measured 20 Nov. Upgrading removes it.
- The deploy waits for `/readyz` and the right build number (done 15 Nov). Good.

## 5. Reliability, fallbacks and failsafes

| Failure | What happens now | Gap |
|---|---|---|
| A process in the container stops | `start.sh` exits, App Service restarts the container | 75 to 90 s down while published files restore from `/home` (Codex) |
| Publish fails half-way | The previous version stays live (atomic symlink swap) | Good. Rolling back past more than three leftover builds deleted the target; fixed 20 Nov |
| Database unreachable | Screens keep working from files; sign-in renewal keeps the session | Good for availability; a revoked session renews during an outage (Gemini GEM-005) |
| Azure MySQL lost | Azure's automated backups, if configured | No dump since 10 Nov; no restore has ever been timed |
| Forsta down | The wave retries every run, then every 6 hours after 3 failures | Good |
| Answers differ from Forsta | Published, alerts sent, "loaded" email sent, failure email after | Should hold the email and alerts (action 3) |
| Disk full during publish | Failure email, then the "loaded" email anyway, exit 0 | Reported by Codex; the code confirms the email order |
| The one instance is slow | Everyone waits | No second instance; fine at today's traffic |

## 6. Performance: CPU, RAM, latency, disk

These numbers are from my run on 20 Nov: the API alone on an Apple-silicon Mac, no nginx, local published data.
Azure's one vCPU is slower; expect two to four times these times.

| Measure | Result |
|---|---|
| API memory at start | 254 MB |
| After Ask's search model, reader and index load | 463 MB (staging's Logs page showed 648 MB for the whole box, 16 % of 4 GB) |
| Cached reads: waves list, book, question file, search, retailers | p50 0.5 to 1.0 ms, p95 0.6 to 1.3 ms |
| 8 parallel callers, 200 requests | 3,564 to 3,614 requests/s, p95 2.6 ms |
| First read of a file after start | about 1.3 s (includes the first sign-in database lookup from India) |
| Ask, first question after start | 291 ms (loads the index); then 9 to 113 ms |
| JavaScript shipped, all screens | 50 files, 1,825 KB raw, 606 KB gzip; the largest chunk 578 KB raw (charts are already split by type) |
| One published version | 13,776 files, 88 MB; three kept (about 65 MB on disk with hard links, Gemini) |

**Where CPU really goes.** One vCPU is shared by nginx, the API, Ask's ONNX models (one thread each), Excel and
PowerPoint exports, the 30-minute ETL check, the publish (6 to 11 minutes) and the 15-second machine log. Codex
measured exports raising other requests' p95 about seven times. `nice` lowers the ETL's priority but cannot make
a single core do two things at once. Action 6 fixes this. Do not buy RAM: there is room for three more workers.

**Traffic today is small.** Staging had 236 Ask questions from people in 30 days. Throughput is not the problem.
Build for correctness and safety first.

## 7. Caching layers

| Layer | Keyed by | Cleared by | Verdict |
|---|---|---|---|
| Browser: hashed JS and CSS | file hash | new build | Correct |
| nginx: prebuilt gzip files of the published version | file path in the version folder | the version swap | The main speed layer; correct |
| nginx proxy cache, 512 MB | `$realpath_root` (the version) plus the request | a new version means new keys | Correct; old keys age out after 7 days |
| nginx sign-in check, 60 s | the cookie | time | A revoked session works up to 60 s more (stated in the code) |
| Python answer cache, 32 MiB | version, route, access scope | version change | Correct after the 20 Nov race fix; scope now separates staff (fixed 20 Nov) |
| Ask answers (500), readings memo (20,000), parsed counts (48 MiB) | version, scope, question | version change | Correct; per process |
| Ask index | version | rebuilt after each publish | The first question after a publish waits for the build (2.6 s under a lock, Gemini) |

**Gaps:** a cold miss is not shared, so ten people opening a new wave's crosstab at once each build it (Gemini
GEM-021). All Python caches are per process, so a second worker doubles memory and halves hit rates. Neither
matters at one worker; both matter before scaling.

## 8. Data correctness: ETL and statistics

- **Reconciliation does not block** (Code, `scripts/weekly_forsta.py` run). See action 3.
- **The check itself had a hole:** a multi-answer flipped between 0 and 1 passed on its shared label. Fixed 20 Nov,
  with a test.
- **Weekly report stars** (Code, `etl/weekly_report.py` table). The 4-week-average change is shown with a star
  from a single-week test. The one-week change of a 4-week average equals (week t − week t−4) / 4, so that is the
  contrast to test. Research team to decide.
- **Dashboard quiet week** (Code, `api/dashboards.py` tested). When no move in a wave survives the false-discovery
  correction, the dashboard falls back to uncorrected single tests. It labels them "single comparison", but this
  is the opposite of what the correction is for.
- **Answer codes swapped between waves** (Reported, Codex DATA-01; Gemini GEM-013). Pooling matches on code, so a
  wave that swapped codes pools wrongly. The cross-code join of 15 Nov matches on answer text, which is the
  safer rule; pooling should use the same.
- **China weighting uses US targets** (Reported, Codex DATA-02). Turn weighting off for China until it has its own
  targets.
- **Disclosure** (Code). Every group is shown however small (your rule of 23 Oct). The Channels text and README
  that promised hiding under 30 were corrected on 20 Nov. Before clients get access, decide a floor: a group of 3
  people in a client's own study can identify them.

## 9. Ask CIP

**What is good.** Fast (9 to 291 ms locally), no paid model needed, honest refusals (cause, median, overlap,
weighted), a sample size on every figure, sources linked.

**Where the ceiling is.** `api/assistant.py` `answer()` is 304 lines. Most of its decisions are wording rules
(`re.search` on "weighted", "both", "cause", "median"). Gemini found seven everyday phrasings that slip past them.
Every fix adds a rule, and every rule can misfire. Of the 11 questions Ask misses in its two test sets:

- 7 pick the wrong survey question. A better reader could help these.
- 4 need understanding that no reader gives: "October vs September", a cause, a vague product, a China gap.

A 550B model as a second reader (NVIDIA, 20 Nov) lifted the golden set from 154 to 157 and the fresh set from 46
to 46. So the next step is not training. It is:

1. **A typed request.** One small function turns the question into dates (with "this quarter" and "last month"
   resolved), group, measure (share, count, change, rank), overlap and weighting. Search and figures then read
   that request, and the wording rules are deleted. Test it with a table of question-to-request pairs.
2. **A real test set.** About 100 questions checked by a person, a third about the newest waves, including ones
   the surveys cannot answer. The existing 161 and 50 were used to tune Ask and no longer measure it fairly.
3. **Then one training run**, only if the reader is what the new test set shows failing.

## 10. Code health

Measured: 904 functions; six are over 100 lines (`assistant.answer` 304, `ask_index.Index.__init__` 133,
`publish._build` 131, `loaders.load_definitions` 119, `wave_loader.rebuild_profiles` 114,
`workbook.build_workbook` 111). The largest files are `api/main.py` (1,183 lines: routes, caches, startup, files,
Ask and admin in one), `api/assistant.py` (836) and `api/metrics.py` (720). The rest is readable, every file says
what it is for and who calls it, and the tests cover the risky paths. Suggested splits, only when next touched:
the Ask routes and the answer cache out of `main.py`; the typed request out of `answer()`.

Two test-hygiene slips were found on 20 Nov. One test wrote the real `logs/` folder on Fridays and failed in a clean
checkout; fixed. Python can also reuse an old compiled file after a same-size, same-second file swap, as seen in
cip-stg. Run tests with `PYTHONDONTWRITEBYTECODE=1` in CI.

## 11. Frontend and UX

Measured or code: charts load by type, the page security policy is strict, and every screen has an export. Open,
from the other reviews: Home downloads about 426 KB of JS before it needs it (Codex), chart-only screens have no
data table for screen readers (Codex UX-02), and the 390-px drawer covers its close button (Gemini GEM-024). The
dark-mode series colours and Retailer trend markers that were hidden inside comments were fixed on 20 Nov.

## 12. Monitoring

There is a Logs page, machine numbers every 15 s, failure emails and a Teams channel. Missing: anything outside the
box. If the container hangs, nobody is told. Add an Azure availability test on `/readyz` every 5 minutes with an
email alert (free tier). Log archives are kept forever and hold IP addresses and emails: set 90 days.

## 13. What I did not verify

Azure's actual CPU and memory limits, the Azure MySQL backup settings, a container start under nginx, an India-side
timing, and whether the session secret and admin token on staging were already rotated. I did not try the leaked
secret against staging.
