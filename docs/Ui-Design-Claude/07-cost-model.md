# 07 · Cost model: hosting, licences and developer time

**Prices:** Azure Retail Prices API, Central US, Linux, queried 20 Oct 2026. Licence prices are from [04](04-marketplace-buy-vs-build.md).

**Labels used below:** inputs are observed; results are inferences, with the arithmetic shown.

## 1. Azure prices used

| Item | Pay-as-you-go / month | 1-yr reserved / yr |
|---|--:|--:|
| P0v3 (1 vCPU / 4 GB), staging class | $62.05 | $443 |
| P1v3 (2 vCPU / 8 GB), production class | $124.10 | $885 |
| P1mv3 (2 vCPU / 16 GB) | $148.92 | $1,059 |
| Front Door Standard (base $35 + traffic; 50 GB and 2 M requests ≈) | ≈ $41 | — |
| Static Web Apps Standard (alternative for static files) | $9 | — |

**SKU note.** The quoted "4.5 GB / 9.88 GB" doesn't match any App Service SKU exactly. The nearest are P0v3 (4 GB) and P1v3 (8 GB), which are what SIP and MIP run on today. This model uses those two. If production is P1mv3, add $25/month.

## 2. Hosting per product, recommended design

| | Pay-as-you-go / yr | Reserved / yr |
|---|--:|--:|
| Staging P0v3 | $745 | $443 |
| Production P1v3 | $1,489 | $885 |
| Front Door (one profile can serve CIP, CIQ, MIP and MDB) | $492 | $492 |
| **Total for one product** | **$2,726** | **$1,820** |

**How many users one production server carries** ([06 §8](06-system-design.md)):
- Supply: about 2,400 cached requests/s per worker on Azure. That is ⅓ of the 7,391 measured on an M4.
- Demand: 300 active users make about 10–60 API requests/s, because most clicks are answered in the browser.
- So **one P1v3 carries 300 active users with about 50× headroom**, and about 1,000 with about 15×.
- A second instance ($1,489/yr) is for availability, not capacity.

## 3. Hosting if the client product were Streamlit

**Capacity per process.** This is set by the measured slope, not by memory:
- Our benchmark: about 0.1 s per extra simultaneous user on an M4 ([02](02-benchmarks.md)). Azure vCPUs are 2–3× slower, so about 0.2–0.3 s per user.
- MIP's staging-like run: about **10 heavy users per process** before p95 passes 5 s ([01 §3](01-evidence-from-sip-and-mip.md)).

This model uses the Streamlit-friendly figure: **10 active users per process**.

**Capacity per server.** A Streamlit process uses one core and there is no worker mode, so a P1v3 (2 vCPU) runs 2 processes behind sticky sessions. That gives **about 20 active users per P1v3**.

| Active users at once | Streamlit P1v3 servers | Streamlit / yr (PAYG) | Recommended servers | Recommended / yr (PAYG) |
|--:|--:|--:|--:|--:|
| 20 | 1 | $1,489 | 1 | $1,489 |
| 50 | 3 | $4,468 | 1 | $1,489 |
| 100 | 5 | $7,446 | 1 | $1,489 |
| 300 | 15 | **$22,338** | 1 | **$1,489** |
| 1,000 | 50 | **$74,460** | 1–2 | $1,489–2,978 |

**Hidden extras on the Streamlit side**
- Each server repeats every cache.
- A sticky load balancer is needed.
- The "load the table" habit breaks the memory budget first: it peaked at 3.67 GB for one table (02).

**Corrections to docs/12 §7.1**
- Its 20–60 servers for 300 users used the discredited "~5 users per server" laptop figure.
- The corrected figure is **about 15 servers**. That is still 15× the recommended design.

## 4. Three-year total cost: hosting plus licences

The table covers one product at 300 and at 1,000 client viewers, and assumes 300 active at peak for the 300-viewer case.

| Option | 3-yr cost, 300 viewers | 3-yr cost, 1,000 viewers | Also needs |
|---|--:|--:|---|
| **Build: React + FastAPI (this design)** | **$5.5k–8.2k** | **$5.5k–12.7k** | The build effort (§5) |
| Build on Streamlit | $67k | $223k | The same build effort, plus the workaround tax (§5) |
| Power BI Embedded (F8 / F16 reserved) + app shell hosting | $23.5k + $8.2k = $31.7k | $46.0k + $8.2k = $54.2k | DAX survey statistics, Power BI look, app shell |
| Infotools Harmoni | $57.6k + $10–40k services | $162.6k + services | A second pipeline, competitor ownership |
| Displayr Enterprise | $57.4k + hosting fee | $121.7k + hosting fee | Viewer-hour metering (dashboards stop) |
| Retool / Budibase | $65–72k | $187–191k | Enterprise tier for SSO; no survey statistics |
| Tableau / Looker | $373k / $900k+ | $1.2M / $1.7M+ | — |

**Growth works in opposite directions.** Build costs stay flat as clients sign up. Every buy option, and Streamlit, grow roughly in line with users.

## 5. Developer time

**What SIP and MIP spent on sign-in, performance and framework workarounds** ([01](01-evidence-from-sip-and-mip.md)):
- SIP: about **38 %** of 1,028 commits.
- MIP: about **22 %** of 743 commits, over about 8 months.
- Features and data got 27 % (SIP) and 43.5 % (MIP).

**What changes on the recommended stack:**
- **Sign-in** becomes a one-off library flow, written once in `coresight-platform` and reused by four products. SIP spent about 295 commits on it and MIP 72.
- **Re-run and session-state bookkeeping and HTML injection disappear.** That covers 403 of SIP's 958 non-merge commits touching such code.
- **Performance work is still needed in the database**: indexes, the cube, and SQL totals instead of pandas. But it stops multiplying with the number of users.

**Estimate:**
- If the "plumbing" share falls from about 30 % to about 10 %, one developer gains about **10 weeks a year** for features.
- Across four products, that is about **40 developer-weeks a year**.
- The 10 % target is an assumption from typical web projects; it was not measured here.

**Up-front cost:**
- CIP's first release on the new stack is about **11–12 weeks** ([06 §11](06-system-design.md)).
- The data layer and the reconciliation already exist.
- CIQ, MIP and MDB then start from the shared UI kit and service core.
- **Payback is about one year for CIP alone**, and shorter once a second product reuses the kit.

**To turn this into money:** multiply the weeks by your loaded weekly cost for a developer. No rate is assumed here.

## 6. Risk cost (not priced)

A credential leak or a client data exposure costs more than every line above. As of today, CIP's own repository has pushed `.env` and a DB password to a public GitHub repo (see the REA Claude findings and the alert in this session).

Neither framework prevents that. Process does:
- Key Vault;
- `gitleaks` in CI;
- a private repo;
- no auto-commit of the working tree.
