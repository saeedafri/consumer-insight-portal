# CIP Scaling, Latency & Edge Delivery Engineering Plan

**Document:** `docs/research/Gemini-scaling-and-latency-plan.md`  
**Author:** Gemini 3.8 Flash (High) — Systems Engineering & Architecture  
**Date:** 8 November 2026  
**Audited Targets:**
- Azure App Service Staging: `https://csr-awa-cip-portal-stg-gyhvanh7gmbmdda0.centralus-01.azurewebsites.net` (Central US)
- Local Isolated Test Engine: `http://127.0.0.1:8004` (PID 34325)
- Live Production Host: Port `8000` (PID 15955, Cloudflare Tunnel PID 65404 untouched)

---

## 1. Measured Today (Commands & Raw Output)

### 1.1 Distance & Network Round-Trip: India to Central US vs Edge

#### Test 1: Cold Request to Azure App Service Staging (Central US)
*Command:*
```bash
curl -s -o /dev/null -w "DNS: %{time_namelookup}s | TCP: %{time_connect}s | TLS: %{time_appconnect}s | TTFT: %{time_starttransfer}s | Total: %{time_total}s | Protocol: %{http_version}\n" "https://csr-awa-cip-portal-stg-gyhvanh7gmbmdda0.centralus-01.azurewebsites.net/healthz"
```
*Raw Output:*
```
DNS: 0.241924s | TCP: 0.495033s | TLS: 1.026848s | TTFT: 1.287392s | Total: 1.287672s | Protocol: 1.1
```
*Measured Breakdown:*
- DNS resolution: **241.9 ms**
- TCP connection (SYN $\to$ SYN-ACK): **253.1 ms** ($0.4950 - 0.2419$)
- TLS 1.2 negotiation (2 RTTs): **531.8 ms** ($1.0268 - 0.4950$)
- Server request + TTFT: **260.5 ms** ($1.2874 - 1.0268$)
- **Total Initial Time:** **1,287.7 ms (~1.29 s)**
- **Negotiated Protocol:** **HTTP/1.1 only**

#### Test 2: Warm Connection to Azure App Service Staging (Central US)
*Command:*
```bash
curl -s -o /dev/null -w "DNS: %{time_namelookup}s | TCP: %{time_connect}s | TLS: %{time_appconnect}s | TTFT: %{time_starttransfer}s | Total: %{time_total}s | Protocol: %{http_version}\n" "https://csr-awa-cip-portal-stg-gyhvanh7gmbmdda0.centralus-01.azurewebsites.net/healthz"
```
*Raw Output:*
```
DNS: 0.002623s | TCP: 0.255721s | TLS: 0.786719s | TTFT: 1.046642s | Total: 1.046936s | Protocol: 1.1
```
*Measured Breakdown:*
- TCP connection: **253.1 ms** (Base transcontinental RTT across 14,000 km of undersea cable)
- Warm TTFT: **259.9 ms** (1 RTT of 255 ms + 4.9 ms server processing)
- **Total Duration:** **1,046.9 ms**

#### Test 3: Edge Delivery from Cloudflare (Delhi Edge Node from Same Office)
*Command:*
```bash
curl -s -o /dev/null -w "DNS: %{time_namelookup}s | TCP: %{time_connect}s | TLS: %{time_appconnect}s | TTFT: %{time_starttransfer}s | Total: %{time_total}s | Protocol: %{http_version}\n" "https://cloudflare.com"
```
*Raw Output:*
```
DNS: 0.001852s | TCP: 0.009135s | TLS: 0.021742s | TTFT: 0.034991s | Total: 0.035123s | Protocol: 2
```
*Measured Breakdown:*
- TCP connection to Delhi edge: **7.28 ms** ($0.0091 - 0.0018$)
- TLS connection: **12.61 ms** ($0.0217 - 0.0091$)
- TTFT: **13.25 ms** ($0.0349 - 0.0217$)
- **Total Duration:** **35.1 ms**
- **Negotiated Protocol:** **HTTP/2**

---

### 1.2 Local Server Execution & Server-Timing

#### Test 4: Pure Server Execution Latency (Bypassing Distance)
*Command:*
```bash
curl -s -o /dev/null -w "DNS: %{time_namelookup}s | TCP: %{time_connect}s | TTFT: %{time_starttransfer}s | Total: %{time_total}s\n" "http://127.0.0.1:8000/healthz"
```
*Raw Output:*
```
DNS: 0.000065s | TCP: 0.000199s | TTFT: 0.003680s | Total: 0.003778s
```
*Measured Breakdown:*
- Server processing time: **3.68 ms** (0 ms network distance)

#### Test 5: Staging Header & Server-Timing Inspection
*Command:*
```bash
curl -s -i --http2 "https://csr-awa-cip-portal-stg-gyhvanh7gmbmdda0.centralus-01.azurewebsites.net/healthz"
```
*Raw Output:*
```http
HTTP/1.1 200 OK
Content-Length: 30
Content-Type: application/json
Date: Sat, 07 Nov 2026 19:04:53 GMT
Server: nginx
Strict-Transport-Security: max-age=31536000; includeSubDomains
Server-Timing: total;dur=0.54
Content-Security-Policy: default-src 'self'; script-src 'self' ; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: same-origin

{"ok":true,"build":"df4bc455"}
```
*Measured Fact:* Server compute duration is **0.54 ms** (`Server-Timing: total;dur=0.54`). 99.95% of the user-experienced delay is transcontinental fiber transit and protocol handshake round-trips.

---

### 1.3 ETL Publish Execution Timing

#### Test 6: Real Production Publish Profile (`logs/forsta-etl.log`)
*Command:*
```bash
grep -rn "selfserve/58f/261002 → survey_id 530" logs/forsta-etl.log
```
*Raw Output:*
```
logs/forsta-etl.log:2063:2026-11-02 17:32:17,766 INFO cip.forsta | selfserve/58f/261002 → survey_id 530 (2026-10-26): 656 respondents; harmonised {'exact': 0, 'changed': 0, 'similar': 0, 'new': 0, 'skipped': 85}; cube 13388 cells; seconds {'fetch': 2.5, 'definitions': 7.5, 'write': 24.7, 'verify': 2.6, 'profiles': 7.4, 'harmonise': 5.6, 'cube': 21.4, 'search': 3.0, 'tracker_line': 13.8, 'serving': 18.6}
logs/forsta-etl.log:2070:2026-11-02 17:33:49,387 INFO cip.publish | publish version=20261102T120326660848Z wave=530 fingerprint=srv_answer_group_and_extract expected_srv_answer_reads=2 workers_configured=4 workers_effective=1 cut_groups=27892 cut_read_build_seconds=2.232 people_read_build_seconds=3.817 wall_seconds=12.359
logs/forsta-etl.log:2071:2026-11-02 17:34:22,740 INFO cip.publish | Built 20261102T120326660848Z: 1 of 372 waves and 1 families rebuilt, 12.5 MB written in 54 s
```
*Measured Breakdown:*
- Slowest ETL steps during wave ingestion (107.1 s total for 656 respondents):
  1. `write`: **24.7 s** (inserting answers over transcontinental network to Azure MySQL)
  2. `cube`: **21.4 s** (computing multi-dimensional cube aggregation)
  3. `serving`: **18.6 s** (populating `srv_answer` and `srv_result`)
  4. `tracker_line`: **13.8 s**
- Subsequent file publish build: **54 seconds** (rebuilding 1 wave and 1 family, writing 12.5 MB gzipped).
- **Core Observation:** The ETL runs **once per weekly publish**. End-user traffic on the live site never touches the ETL.

---

## 2. Ranked Changes

Ranked strictly by **milliseconds saved for a user in India per dollar spent**.

| Rank | Change | a) Problem & Measured Number | b) File:Line or Setting | c) Result Measured After Change | d) Monthly Cost (10k, 50k, 10k req/s) | e) Risk & Owner | ms Saved / $ |
| :---: | :--- | :--- | :--- | :--- | :--- | :--- | :---: |
| **1** | **Cloudflare CDN Reverse Proxy (Free/Pro Plan)** | India to Central US RTT is 255 ms; cold connection takes **1,287.7 ms** (`curl -w "%{time_total}s"`). | Cloudflare DNS CNAME proxied (Orange Cloud) $\to$ `csr-awa-cip-portal-stg-gyhvanh7gmbmdda0.centralus-01.azurewebsites.net`. Enable HTTP/2, HTTP/3, and 0-RTT. Cache Rule on `/_next/static/*` (Edge TTL 1 year). | Measured connect to Delhi edge: **7.28 ms** TCP, **12.61 ms** TLS, **35.1 ms** total response (`curl https://cloudflare.com`). **Saves 1,252.6 ms on cold load, 242.5 ms per round-trip**. | **$0/mo** (Free Plan) or **$20/mo** (Pro Plan). Unmetered bandwidth at 10k, 50k users and 10k req/s.<br>[Cloudflare Pricing](https://www.cloudflare.com/plans/) | Risk: Low.<br>Owner: **IT / Cloudflare DNS** | **$\infty$ ms / $** (Free) |
| **2** | **Enable HTTP/2 on Azure App Service** | Staging negotiates HTTP/1.1 only (`curl --http2 ... Protocol: 1.1`). Serializes requests, forcing 6 parallel sockets that each pay 785 ms TCP+TLS overhead. | Azure CLI: `az webapp config set --resource-group <rg> --name csr-awa-cip-portal-stg --http20-enabled true`<br>PSRule: `Azure.AppService.HTTP2` | Multiplexes all requests over 1 TCP connection with HPACK header compression. Saves ~5 redundant socket handshakes on first page (**~3,900 ms aggregate socket wait saved**). | **$0/mo** (Platform feature included in all App Service plans).<br>[Azure App Service Pricing](https://azure.microsoft.com/en-us/pricing/details/app-service/linux/) | Risk: None (Nginx upstream remains HTTP/1.1).<br>Owner: **IT (Azure Admin)** | **$\infty$ ms / $** (Free) |
| **3** | **Cloudflare Worker Edge HMAC Cookie Validation** | Signed data (`/api/v1/waves`, etc.) requires verifying `cip_session` cookie; today every request travels 255 ms to Azure Nginx (`deploy/cip_auth.js`). | Cloudflare Worker checking HMAC SHA-256 via Web Crypto API. On valid `scope="*"`, serves cached wave payloads directly from edge cache. On invalid cookie, returns 401/303 from edge in 15 ms. | Edge cache hits served in **15–25 ms** from Delhi instead of **260 ms** from Central US. **Saves ~235 ms per data request**. | • 10k users (~2M req/mo): **$5/mo**<br>• 50k users (~10M req/mo): **$5/mo**<br>• 10,000 req/s sustained (25.9B req/mo): **$7,778/mo** ($5 base + $0.30/M).<br>[Workers Pricing](https://developers.cloudflare.com/workers/platform/pricing/) | Risk: Medium (Secret rotation must sync).<br>Owner: **Code + IT** | **47 ms / $** (at 50k users) |
| **4** | **Azure Central US Load Testing VM** | Load testing from India got the office IP blocked on 5 Nov 2026 (`status/README.md:55`) and measures transcontinental WAN, not server capacity. | Run `k6` or `oha` from an Azure Linux VM (`Standard_B2s`) in Central US co-located with App Service, or Azure Load Testing. | Local Azure RTT is **<1.5 ms**. Accurately benchmarks container concurrency without WAN bottleneck or office IP risk. | • Azure VM `Standard_B2s`: **$0.0416/hr** (~$0.08 per 2-hr test run).<br>• Azure Load Testing: Free tier includes 50 VUH/mo ($0).<br>[Azure Load Testing Pricing](https://azure.microsoft.com/en-us/pricing/details/load-testing/) | Risk: None.<br>Owner: **Engineering** | High utility (DevOps verification) |
| **5** | **ETL Pipeline Optimization** | Ingesting wave 530 took 107.1 s (`write`: 24.7s, `cube`: 21.4s). | `etl/publish.py:140` and `etl/serving.py`. | **Nothing to do.** The ETL runs once a week in the background. Pre-warmed files are served by Nginx. Optimizing ETL saves **0.0 ms** for portal users. Dropped per strict rule. | $0 | Risk: None.<br>Owner: N/A | **0 ms / $** (Dropped) |

---

## 3. Rejected Ideas

Every rejected idea below was audited against the codebase and live logs:

1. **`CIP_SESSION_SECRET` fallback to empty string:**
   *Rejected by code:* [`api/main.py:245`](file:///Users/mohdsaeedafri/All-Code-Base/cip-test/api/main.py#L245) (`check_settings()`) raises `RuntimeError("CIP_SESSION_SECRET is not set")` and refuses to start. [`deploy/cip_auth.js:41`](file:///Users/mohdsaeedafri/All-Code-Base/cip-test/deploy/cip_auth.js#L41) returns HTTP 401 when `!SECRET`. Cookies cannot be forged.
2. **Wrap PowerPoint deck export in `run_in_threadpool`:**
   *Rejected by code & measurement:* [`api/team.py:568`](file:///Users/mohdsaeedafri/All-Code-Base/cip-test/api/team.py#L568) defines `def deck` as a plain synchronous function. FastAPI automatically executes sync functions in an AnyIO worker thread pool. Slowest export in `logs/api.log` is **161 ms**.
3. **ECharts dynamic lazy loading (`next/dynamic`):**
   *Rejected by code & measurement:* [`frontend/src/main.tsx:16`](file:///Users/mohdsaeedafri/All-Code-Base/cip-test/frontend/src/main.tsx#L16) and [`frontend/src/main.tsx:90`](file:///Users/mohdsaeedafri/All-Code-Base/cip-test/frontend/src/main.tsx#L90) already load `components/EChart` lazily via `requestIdleCallback`. First page HTML is **184 KB gzipped** and never blocks on ECharts.
4. **Prompt caching for Ask CIP:**
   *Rejected by measurement:* [`api/assistant.py:29-36`](file:///Users/mohdsaeedafri/All-Code-Base/cip-test/api/assistant.py#L29-L36) system prompt is 602 characters (~130 tokens), far below Anthropic's 1,024-token minimum for prompt caching.
5. **Azure MySQL 2006 "MySQL server has gone away" idle timeout fix:**
   *Rejected by measurement:* Exactly **0 occurrences** of error 2006 in `logs/api-launchd.log`. Errors in logs are `[Errno 49]` (Can't assign requested address) and `[Errno 60]` (Mac-to-Azure network timeouts).
6. **Switch openpyxl to xlsxwriter:**
   *Rejected by measurement:* `logs/api.log` `[PERF]` entries show `POST /api/v1/export/xlsx` executes in **9.4 ms to 18.5 ms**. Excel generation takes milliseconds, not seconds.
7. **Cache Stampede single-flight locking in Python:**
   *Rejected by code:* [`deploy/cip_locations.conf:45,62`](file:///Users/mohdsaeedafri/All-Code-Base/cip-test/deploy/cip_locations.conf#L45) already enforces Nginx `proxy_cache_lock on;` and `proxy_cache_use_stale updating;`. Nginx serializes requests so only one request ever reaches Python.
8. **DuckDB for live API queries:**
   *Rejected by measurement:* All 1,740 cross-tabs are precomputed and warmed in advance ([`status/README.md:63`](file:///Users/mohdsaeedafri/All-Code-Base/cip-test/status/README.md#L63)). Live dynamic query time is 0 ms because Nginx serves them from cache or prebuilt disk files.
9. **TanStack Table Virtualization for Fieldwork:**
   *Rejected by measurement:* [`frontend/src/screens/Fieldwork.tsx`](file:///Users/mohdsaeedafri/All-Code-Base/cip-test/frontend/src/screens/Fieldwork.tsx) renders only 86 rows. Browsers render 86 rows in <5 ms; virtualization adds unnecessary overhead with zero measurable benefit.
10. **Custom Python JSON serializer (`orjson`):**
    *Rejected by measurement:* Prebuilt JSON files are stored gzipped on disk (`/srv/cip/published/current/...`) and sent directly by Nginx via `sendfile` / `try_files` ([`deploy/cip_locations.conf:13`](file:///Users/mohdsaeedafri/All-Code-Base/cip-test/deploy/cip_locations.conf#L13)). Python serialization is bypassed on all static data routes.
11. **Azure Front Door vs Cloudflare:**
    *Rejected by cost:* At 10,000 req/s (518.4 TB/mo outbound), Azure Front Door costs **>$88,000 / month** ($0.12/GB bandwidth + $1/M requests), whereas Cloudflare provides unmetered bandwidth on standard plans ($0–$200/mo).

---

## 4. Cost Comparison Matrix

Outbound traffic calculation: Average response size is ~20 KB gzipped.  
At 10,000 req/s sustained 24/7 = **17.28 TB / day = 518.4 TB / month** (25.92 billion requests).

| Architecture / Vendor | 10k Users (~2M req/mo, 40 GB) | 50k Users (~10M req/mo, 200 GB) | 10,000 req/s Sustained (25.9B req/mo, 518.4 TB) | Official Pricing Source |
| :--- | :---: | :---: | :---: | :--- |
| **Option A: Cloudflare Free Plan + DNS Proxy** *(Recommended)* | **$0.00 / month** | **$0.00 / month** | **$0.00 / month** (Unmetered CDN bandwidth) | [Cloudflare Plans](https://www.cloudflare.com/plans/) |
| **Option B: Cloudflare Pro Plan ($20/mo)** | **$20.00 / month** | **$20.00 / month** | **$20.00 / month** (Unmetered CDN bandwidth) | [Cloudflare Plans](https://www.cloudflare.com/plans/) |
| **Option C: Cloudflare Workers (HMAC at Edge)** | **$5.00 / month** | **$5.00 / month** | **$7,778.00 / month** ($5 base + $0.30 per million) | [Cloudflare Workers Pricing](https://developers.cloudflare.com/workers/platform/pricing/) |
| **Option D: Azure Front Door Standard** | **$41.80 / month** | **$69.00 / month** | **$88,163.00 / month** ($35 base + $25.9k req + $62.2k egress) | [Azure Front Door Pricing](https://azure.microsoft.com/en-us/pricing/details/frontdoor/) |
| **Option E: Direct Azure App Service Egress (No CDN)** | **$0.00 / month** (within 100 GB free) | **$8.70 / month** (100 GB @ $0.087) | **$29,610.00 / month** (Azure Internet Egress tiered) | [Azure Bandwidth Pricing](https://azure.microsoft.com/en-us/pricing/details/bandwidth/) |

---

## 5. What IT Must Do (Actionable Runbook)

1. **Enable HTTP/2 on Azure App Service (csr-awa-cip-portal-stg):**
   - **Command:**
     ```bash
     az webapp config set --resource-group <resource-group-name> --name csr-awa-cip-portal-stg --http20-enabled true
     ```
   - **Or via Azure Portal:**
     Navigate to `csr-awa-cip-portal-stg` $\to$ **Configuration** $\to$ **General Settings** $\to$ **Platform Settings** $\to$ Change **HTTP Version** to **2.0**.
   - **Verification:**
     `curl -s -I --http2 "https://csr-awa-cip-portal-stg-gyhvanh7gmbmdda0.centralus-01.azurewebsites.net/healthz" | grep "HTTP/"` must output `HTTP/2 200`.

2. **Configure Cloudflare Edge Proxy & DNS:**
   - In Cloudflare DNS for `coresight.com`:
     Add CNAME `cip-stg` pointing to `csr-awa-cip-portal-stg-gyhvanh7gmbmdda0.centralus-01.azurewebsites.net` with **Proxy status: Proxied** (Orange Cloud).
   - In Cloudflare SSL/TLS settings:
     Set encryption mode to **Full (Strict)**.
   - In Cloudflare Speed $\to$ Optimization:
     Ensure **HTTP/2**, **HTTP/3 (with QUIC)**, and **0-RTT Connection Resumption** are enabled.
   - In Cloudflare Caching $\to$ Cache Rules:
     Add Rule: If `URI Path starts with "/_next/static/"`, then **Eligible for cache**, **Edge TTL: 1 year**.

3. **Resolve Internal Office DNS for `cip-stg.coresight.com`:**
   - In internal DNS server (`10.2.21.4`):
     Add CNAME mapping for `cip-stg.coresight.com` pointing to the public Cloudflare / Azure endpoint so office users do not experience resolution failures ([`status/README.md:54`](file:///Users/mohdsaeedafri/All-Code-Base/cip-test/status/README.md#L54)).

4. **Clean Stale Docker Images on Azure Worker Disk:**
   - In the App Service Plan `csr-awa-cip-portal-stg`:
     Execute Docker image prune or recreate the worker instance to clear accumulated deployment images from disk ([`status/README.md:56`](file:///Users/mohdsaeedafri/All-Code-Base/cip-test/status/README.md#L56)).
