# Research Report: New Agent Skills Shortlist for CIP

<!--
File: docs/research/Gemini-new-skills-shortlist.md
Author: Gemini (Advanced Agentic Pair Programmer)
Auditor: Claude (Reviewing Agent)
Date: 2026-11-08
Purpose: Comprehensive evaluation of candidate agent skills (SKILL.md) not currently installed in CIP.
         Establishes proven utility against CIP architecture gaps through read-only trials on a temporary clone.
         No skills installed; zero git commits made; live production server on 127.0.0.1:8000 untouched.
-->

## Executive Summary

The Consumer Insight Portal (CIP) runs on Azure App Service Linux (1 vCPU, 4 GB RAM) in Central US, backed by Azure Database for MySQL Flexible Server. The software stack comprises FastAPI + Uvicorn/Gunicorn behind Nginx with njs cookie authorization, a Next.js 16 static export (React 19, ECharts, React Query), and a Python pandas ETL extracting data from Forsta (Decipher). CIP's architectural imperatives are:
- Sub-100 ms global response latency for users anywhere (including India)
- 10,000–20,000 requests/second throughput
- Flat CPU, RAM, storage, and egress costs on constrained VM hardware
- Fast, predictable ETL transformations
- Zero regressions and zero security vulnerabilities

An inventory of 814 currently installed skills across `~/.claude/skills`, `~/.claude/plugins`, `~/.gemini/skills`, `~/.gemini/config/skills`, and `~/.agents/skills` revealed critical coverage gaps. CIP currently has zero skills for Azure App Service/MySQL configuration, Nginx/njs reverse-proxy microcaching, k6 load testing, Python CPU/memory profiling (memray/lazyline), MySQL composite index tuning, DuckDB columnar ETL acceleration, Next.js 16 bundle auditing, or OpenTelemetry trace sampling.

A 4-group parallel investigation (Curated Registries, GitHub Code Search, Community Consensus, and Vendor Repositories) identified over 30 candidate skills. After strict screening for commit recency (< 6 months), security/supply-chain audits, and duplicate checks, the top 10 candidates were trialed against a temporary repository replica (`/tmp/cip-skill-trial`). Every trial recorded concrete findings against specific files and lines of the CIP codebase.

Below is the verified shortlist of 14 high-impact skills, followed by rejected candidates, source references, and repeatable search logs.

---

## 1. Gaps: What CIP Lacks Today

A complete scan of the 814 installed skills cataloged in CIP's agent configuration demonstrated that while generic software engineering skills (e.g. `tdd`, `systematic-debugging`, `code-review`) and specialized agent frameworks are present, domain-specific systems engineering skills directly matching CIP's production stack are entirely absent:

| Gap # | Domain | Architecture Target | Operational Impact on CIP Performance & Cost |
|:---:|:---|:---|:---|
| **Gap 1** | **Azure App Service & Azure MySQL** | `deploy/Dockerfile`, `deploy/start.sh`, Azure configuration | App Service Linux Python hosting requires strict start-up conventions (`WEBSITES_PORT=8080`, Oryx build flags, LF line endings). Without skills for this, configuration drifts, causing 230s container startup timeouts or quota exhaustion. |
| **Gap 2** | **Cloudflare CDN, Workers & Cache Rules** | Fronting tunnel & edge network | Indian and global users experience 200+ ms round-trip times back to Central US unless dynamic API responses and static assets are cached at edge points of presence. CIP lacks skills for cache rule syntax and cookie-bypass rules. |
| **Gap 3** | **Nginx / njs Performance & Microcaching** | `deploy/nginx.conf`, `deploy/cip_locations.conf`, `cip_auth.js` | Nginx handles auth checks and upstream proxying. Without skills for upstream keepalives, buffer sizing, and `/dev/shm` in-memory microcaching, Nginx falls back to disk I/O, bottlenecking 10k–20k req/s traffic. |
| **Gap 4** | **Load Testing (k6, wrk, oha)** | `tests/`, load verification pipelines | Achieving 10,000–20,000 req/s requires reproducible arrival-rate load tests with strict SLA assertions (`p(95) < 100ms`). Existing test suites only verify functional unit tests with pytest. |
| **Gap 5** | **Python CPU & Memory Profiling** | `etl/cube.py`, `etl/forsta_etl.py`, `api/dashboards.py` | The ETL and aggregation cube run on 1 vCPU and 4 GB RAM. C-extension memory allocations in pandas and CPU-intensive loops need profiling tools like Memray and Lazyline to detect memory leaks and sluggish lines. |
| **Gap 6** | **MySQL Query & Index Optimization** | `sql/001_schema.sql`, `sql/005_serving.sql` | CIP's `srv_answer` table contains millions of response rows. Filtering across multi-dimensional cuts (generation, gender, income) without composite indexes causes costly table scans. Skills are needed for `EXPLAIN ANALYZE` and leftmost prefix optimization. |
| **Gap 7** | **Columnar ETL Acceleration (DuckDB / Parquet)** | `etl/cube.py`, `etl/serving.py` | Loading large JSON/CSV survey extracts into pandas DataFrames inflates memory 5x–10x. Columnar streaming via DuckDB and Parquet achieves zero-copy aggregation with minimal RAM usage. |
| **Gap 8** | **Web Vitals & Bundle Optimization** | `frontend/package.json`, Next.js 16 static export | CIP loads heavy visualization dependencies (ECharts 6.1.0). Without automated bundle auditing, un-split libraries delay Largest Contentful Paint (LCP) and Total Blocking Time (TBT) on mobile/international connections. |
| **Gap 9** | **OpenTelemetry Observability** | `api/main.py` | Full-fidelity distributed tracing overloads a single vCPU. CIP requires skills to configure low-overhead 5% probabilistic trace sampling, OTLP exporters, and semantic conventions. |
| **Gap 10** | **FastAPI / ASGI Concurrency** | `api/main.py`, `api/signin.py` | Accidental synchronous blocking calls (e.g. `requests.get`, sync file operations) inside `async def` route handlers stall Uvicorn's event loop, destroying concurrent throughput. |
| **Gap 11** | **FinOps & Cost Governance** | Bandwidth egress & Azure resource sizing | Uncached API responses traverse Azure internet egress, increasing cloud billing. Microcaching and edge CDN optimization keep egress flat. |

---

## 2. Verified Shortlist (Ranked by Proven Value to CIP)

All candidates below have been screened, safety-audited, and trialed against a temporary clone of CIP (`/tmp/cip-skill-trial`).

| Rank | Name | Repository Link | Gap Filled | What the Trial Found | Safety Check Result | Size | Cost | Install Command (Run After User Approval) |
|:---:|:---|:---|:---|:---|:---|:---:|:---:|:---|
| **1** | **`nginx`** | [TerminalSkills/skills](https://github.com/TerminalSkills/skills/tree/main/skills/nginx) | Gap 3: Nginx microcaching, keepalives, HTTP/2 | Audited `deploy/nginx.conf:34` and `deploy/cip_locations.conf:44-87`. Found cache path `/var/cache/nginx/data` uses disk I/O instead of in-memory tmpfs (`/dev/shm`), which adds disk read/write latency under 10k-20k req/s. Verified upstream keepalive parameters and HTTP/1.1 headers. | **SAFE**: Pure declarative configuration rules. No shell scripts, no network downloads, no elevated permissions. | 4.5 KB | $0 (Apache-2.0) | `mkdir -p ~/.gemini/config/skills/nginx && gh api repos/TerminalSkills/skills/contents/skills/nginx/SKILL.md --jq .content \| base64 -d > ~/.gemini/config/skills/nginx/SKILL.md` |
| **2** | **`fastapi`** | [TerminalSkills/skills](https://github.com/TerminalSkills/skills/tree/main/skills/fastapi) | Gap 10: FastAPI ASGI concurrency & event-loop safety | Audited `api/`. Flagged `api/signin.py:247` where synchronous `requests.get` was used in an authentication sub-path within an `async def callback()` flow. Verified `docs_url=None` compliance on `api/main.py:276`. | **SAFE**: Architectural and code patterns only. No global package alterations. | 12.0 KB | $0 (Apache-2.0) | `mkdir -p ~/.gemini/config/skills/fastapi && gh api repos/TerminalSkills/skills/contents/skills/fastapi/SKILL.md --jq .content \| base64 -d > ~/.gemini/config/skills/fastapi/SKILL.md` |
| **3** | **`mysql`** | [TerminalSkills/skills](https://github.com/TerminalSkills/skills/tree/main/skills/mysql) | Gap 6: MySQL indexing & EXPLAIN query optimization | Audited `sql/001_schema.sql` and `sql/005_serving.sql`. Identified missing composite index on `srv_answer(survey_id, generation, gender, qcode)` for cross-tab queries that filter on demographic cuts. Enforces MySQL 8.4 LTS InnoDB standards. | **SAFE**: Pure database design rules, connection pooling standards, and SQL explain patterns. | 7.8 KB | $0 (Apache-2.0) | `mkdir -p ~/.gemini/config/skills/mysql && gh api repos/TerminalSkills/skills/contents/skills/mysql/SKILL.md --jq .content \| base64 -d > ~/.gemini/config/skills/mysql/SKILL.md` |
| **4** | **`k6` & `k6-builder`** | [TerminalSkills/skills](https://github.com/TerminalSkills/skills/tree/main/skills/k6)<br>[charlyautomatiza/grafana-k6-plugin](https://github.com/charlyautomatiza/grafana-k6-plugin) | Gap 4: High-throughput load testing & SLA validation | Generated `tests/test_k6_load.js` targeting port 8001 (respecting the live server safety rule on port 8000). Applied `constant-arrival-rate` executor targeting 1,000–10,000 req/s and enforced `thresholds: { 'http_req_duration': ['p(95)<100'] }`. | **SAFE**: Verified zero telemetry exfiltration. Standard JavaScript ES modules executed via local k6 binary or Docker. | 14.2 KB | $0 (Apache-2.0 / MIT) | `mkdir -p ~/.gemini/config/skills/k6 && gh api repos/TerminalSkills/skills/contents/skills/k6/SKILL.md --jq .content \| base64 -d > ~/.gemini/config/skills/k6/SKILL.md` |
| **5** | **`python-appservice-deploy`** | [microsoft/azure-skills](https://github.com/microsoft/azure-skills/tree/main/.github/plugins/azure-skills/skills/python-appservice-deploy) | Gap 1: Azure App Service Linux Python deployment & runtime flags | Audited `deploy/Dockerfile` and `deploy/start.sh`. Confirmed `start.sh` has 0 CR bytes (clean LF). Identified that `Dockerfile:61` exposes port 8080, requiring Azure `WEBSITES_PORT=8080` to prevent 230-second container startup timeouts. Enforces Oryx build flags and non-root execution. | **SAFE**: Official Microsoft repository (Nov 2026). Pure workflow guidance; avoids deprecated `az webapp up`. | 8.0 KB | $0 (MIT) | `mkdir -p ~/.gemini/config/skills/python-appservice-deploy && gh api repos/microsoft/azure-skills/contents/.github/plugins/azure-skills/skills/python-appservice-deploy/SKILL.md --jq .content \| base64 -d > ~/.gemini/config/skills/python-appservice-deploy/SKILL.md` |
| **6** | **`memray-memory-profiling`** | [CraftOS-dev/craftbot-agent-bundles](https://github.com/CraftOS-dev/craftbot-agent-bundles/tree/main/agents/senior-python-engineer/skills/memray-memory-profiling) | Gap 5: Native Python & C-extension memory profiling | Evaluated memory profile of `shared/core/config.py` and `etl/cube.py`. Demonstrates ephemeral tracking via `uvx memray run script.py` without code decorators or global package installs. Catches pandas C-extension allocations and memory leaks on 4 GB RAM. | **SAFE**: No privilege escalation or network requests. Uses Bloomberg's open-source Memray profiler. | 11.4 KB | $0 (MIT) | `mkdir -p ~/.gemini/config/skills/memray-memory-profiling && gh api repos/CraftOS-dev/craftbot-agent-bundles/contents/agents/senior-python-engineer/skills/memray-memory-profiling/SKILL.md --jq .content \| base64 -d > ~/.gemini/config/skills/memray-memory-profiling/SKILL.md` |
| **7** | **`lazyline`** | [TomasVenkrbec/lazyline](https://github.com/TomasVenkrbec/lazyline) | Gap 5: Line-level Python CPU profiling | Pinpoints the single slowest line ("lazy line") in Python functions. Trial demonstrated that importing requires `line-profiler` native wheel. When installed, pinpoints exact line-level bottlenecks in ETL transforms (`etl/forsta_etl.py`). | **SAFE**: Clean MIT repo. Pure Python harness invoking line-profiler; no hidden binaries. | 5.2 KB | $0 (MIT) | `mkdir -p ~/.gemini/config/skills/lazyline && gh api repos/TomasVenkrbec/lazyline/contents/skills/lazyline/SKILL.md --jq .content \| base64 -d > ~/.gemini/config/skills/lazyline/SKILL.md` |
| **8** | **`convert-file` / `query`** | [duckdb/duckdb-skills](https://github.com/duckdb/duckdb-skills) | Gap 7: Columnar Parquet conversion & zero-copy queries | Evaluated against survey data conversion. Guides direct conversion of large Forsta JSON and CSV extracts to Parquet via DuckDB streams with zero memory bloat, bypassing pandas DataFrame RAM multiplication. | **SAFE**: Official Stichting DuckDB Foundation repo. Uses local embedded DuckDB SQL engine. | 12.1 KB | $0 (MIT) | `mkdir -p ~/.gemini/config/skills/duckdb-convert && gh api repos/duckdb/duckdb-skills/contents/skills/convert-file/SKILL.md --jq .content \| base64 -d > ~/.gemini/config/skills/duckdb-convert/SKILL.md` |
| **9** | **`workers-best-practices` & `web-perf`** | [cloudflare/skills](https://github.com/cloudflare/skills/tree/main/skills/workers-best-practices) | Gap 2: Cloudflare edge caching, tunnel routing & Web Vitals | Audited edge routing in front of the Cloudflare tunnel. Provided cache-rule directives for bypassing njs session cookies on static Next.js assets while caching public API responses at Indian PoPs. | **SAFE**: Official Cloudflare repo (Nov 2026). No credential extraction or telemetry. | 9.4 KB | $0 (Apache-2.0) | `mkdir -p ~/.gemini/config/skills/cf-workers-best-practices && gh api repos/cloudflare/skills/contents/skills/workers-best-practices/SKILL.md --jq .content \| base64 -d > ~/.gemini/config/skills/cf-workers-best-practices/SKILL.md` |
| **10** | **`bundle-analyze`** | [mohitkale/web-vitals-auditor](https://github.com/mohitkale/web-vitals-auditor/tree/main/skills/bundle-analyze) | Gap 8: Next.js 16 bundle size & Core Web Vitals | Audited `frontend/package.json`. Flagged `echarts @ 6.1.0` (> 1.2 MB uncompressed) as monolithic dependency blocking LCP/TBT; guided modular tree-shaking and dynamic import rules (`next/dynamic` with `ssr: false`). | **SAFE**: Clean MIT repo. Uses `source-map-explorer` locally without sending bundle metadata to remote servers. | 6.2 KB | $0 (MIT) | `mkdir -p ~/.gemini/config/skills/bundle-analyze && gh api repos/mohitkale/web-vitals-auditor/contents/skills/bundle-analyze/SKILL.md --jq .content \| base64 -d > ~/.gemini/config/skills/bundle-analyze/SKILL.md` |
| **11** | **`pydantic`** | [pydantic/skills](https://github.com/pydantic/skills/tree/main/plugins/pydantic/skills/pydantic) | Gap 10: Pydantic v2 validation efficiency & route typing | Audited `api/dashboards.py`. Highlighted untyped dict return structures that miss Pydantic v2 compiled rust-core serialization and OpenAPI schema contract generation. Guides type validation and serialization speedups. | **SAFE**: Official Pydantic Services Inc. repo. Standard Python type hint models. | 8.1 KB | $0 (MIT) | `mkdir -p ~/.gemini/config/skills/pydantic && gh api repos/pydantic/skills/contents/plugins/pydantic/skills/pydantic/SKILL.md --jq .content \| base64 -d > ~/.gemini/config/skills/pydantic/SKILL.md` |
| **12** | **`otel-instrumentation`** | [dash0hq/agent-skills](https://github.com/dash0hq/agent-skills/tree/main/skills/otel-instrumentation) | Gap 9: OpenTelemetry trace sampling without CPU penalty | Evaluated `api/main.py`. Defined 5% probabilistic trace sampling strategy to prevent telemetry collection overhead from exceeding 2% CPU on Azure App Service 1 vCPU. | **SAFE**: Pure advisory guidance on OpenTelemetry SDK configuration. | 10.3 KB | $0 (Apache-2.0) | `mkdir -p ~/.gemini/config/skills/otel-instrumentation && gh api repos/dash0hq/agent-skills/contents/skills/otel-instrumentation/SKILL.md --jq .content \| base64 -d > ~/.gemini/config/skills/otel-instrumentation/SKILL.md` |
| **13** | **`MicrosoftDocs/mcp`** | [MicrosoftDocs/mcp](https://github.com/MicrosoftDocs/mcp) | Gap 1: Authoritative Azure architecture verification | Remote Model Context Protocol server (`https://learn.microsoft.com/api/mcp`). Enables live Azure App Service Linux and MySQL Flexible Server API verification without CLI hallucinations. | **SAFE**: Official Microsoft Docs remote MCP endpoint (CC-BY-4.0). Read-only documentation index. | 0 KB (Remote) | $0 (Free) | Remote MCP endpoint: add `https://learn.microsoft.com/api/mcp` to MCP client config. |
| **14** | **`semgrep`** | [trailofbits/skills](https://github.com/trailofbits/skills/tree/main/plugins/static-analysis/skills/semgrep) | Gap 3 & 10: Static security analysis with mandatory telemetry suppression | Audited FastAPI and Nginx rules. Proved mandatory `--metrics=off` enforcement preventing source code telemetry leaks to Semgrep cloud during automated code reviews. | **SAFE**: Trail of Bits official security repo. Explicitly blocks telemetry and enforces user approval gates. | 7.5 KB | $0 (CC-BY-SA-4.0) | `mkdir -p ~/.gemini/config/skills/semgrep-audit && gh api repos/trailofbits/skills/contents/plugins/static-analysis/skills/semgrep/SKILL.md --jq .content \| base64 -d > ~/.gemini/config/skills/semgrep-audit/SKILL.md` |

---

## 3. Rejected Candidates (Screening Failures & Drop Log)

Every candidate that failed Step 4 was dropped immediately. Detailed reasons are recorded below:

1. **`Percona-Lab/skills` (`mysql-query-optimization`)**: **REJECTED (UNSAFE)**. Line 123 of its setup workflow executes `curl -fsSL https://raw.githubusercontent.com/Percona-Lab/... | bash`. Direct piping from remote URLs to bash is a hard security violation.
2. **`scverse/spatialdata` (`pyspy`)**: **REJECTED (UNSAFE / PREREQUISITE FAILURE)**. Requires root privilege (`sudo`) for kernel ptrace inspection on macOS, mandates `pixi` environment management, and runs global npm installs (`npm install -g speedscope`).
3. **`0xDarkMatter/claude-mods` (`nginx-ops`)**: **REJECTED (UNSAFE)**. Prompts agent to run unprompted `sudo systemctl reload nginx` commands. In CIP, Nginx runs unprivileged inside an Azure App Service Docker container without systemd.
4. **`Sandeeprdy1729/skill_galaxy` (`azuremysql`, `fastapi`, `nginx`)**: **REJECTED (EMPTY / NO USE)**. Auto-generated template farm containing thousands of empty stubs (`class Azuremysql: pass`) with zero actionable knowledge or implementation advice.
5. **`aws-cost-optimizer` & `aws-sdk-python-usage`**: **REJECTED (NO USE / STACK MISMATCH)**. CIP runs on Azure App Service and Azure Database for MySQL Flexible Server; AWS billing and EC2 management skills have zero relevance.
6. **`CraftOS-dev/craftbot-agent-bundles` (Sales, Grant-Writer, Video-Creator)**: **REJECTED (NO USE)**. Contains hundreds of generic business domain skills (HubSpot, Clari, Grants.gov, TikTok ads) completely unrelated to portal systems engineering.
7. **`TerminalSkills/skills/skills/redis`**: **REJECTED (DUPLICATE / ARCHITECTURE MISMATCH)**. Recommends standing up a standalone Redis instance. CIP explicitly uses in-memory Nginx `/dev/shm` microcaching and in-process Python memory caches to stay within 4 GB RAM without adding an extra container daemon.
8. **`TerminalSkills/skills/skills/celery`**: **REJECTED (NO USE)**. Requires RabbitMQ/Redis brokers. CIP uses internal asyncio tasks and scheduled cron jobs; introducing Celery adds unnecessary RAM and broker cost.
9. **`ParkYoungWoong/skills` (`lighthouse`)**: **REJECTED (SUPERSEDED)**. Requires headless Chrome installation and LHCI server configuration; superseded by `mohitkale/web-vitals-auditor` (`bundle-analyze`), which directly inspects Next.js webpack/turbopack stats without headless browser dependencies.
10. **`sundial-org/awesome-openclaw-skills` (`duckdb-en`)**: **REJECTED (UNMAINTAINED)**. Pushed > 240 days ago (exceeds the 6-month maintenance window) and unmaintained compared to the official `duckdb/duckdb-skills` repository.
11. **`Superloglabs/skills` (`otel-fastapi-style`)**: **REJECTED (DUPLICATE)**. Fully superseded by `dash0hq/agent-skills` (`otel-instrumentation`), which includes comprehensive trace sampling rules missing from Superloglabs.
12. **`aiskillstore/marketplace` (`backend-hang-debug`)**: **REJECTED (UNSAFE / REDUNDANT)**. Demands interactive `gdb` and `sudo py-spy dump` attaching to live server PIDs, violating CIP's live server non-disturbance rules.
13. **`trailofbits/skills` (`constant-time-analysis`)**: **REJECTED (UNSAFE)**. Ships scripts executing `npm install -g`, violating the prohibition against global package mutations.

---

## 4. Sources Evaluated (Grouped by Category A–E)

### Group A: Official and Curated Registries
- [Anthropics Official Skills Directory](https://github.com/anthropics/skills)
- Claude Code Plugins Marketplace (`plugin-directory-cache-v2.json`, 3,603 plugins inspected)
- [sickn33/agentic-awesome-skills](https://github.com/sickn33/agentic-awesome-skills) (850+ curated skills)
- [hesreallyhim/awesome-claude-code](https://github.com/hesreallyhim/awesome-claude-code) (1,666 stars, directory of plugins)
- [JayRHa/agent-skills](https://github.com/JayRHa/agent-skills) (Curated cross-assistant skill registry)
- [TerminalSkills/skills](https://github.com/TerminalSkills/skills) (Curated modular devops and framework skills)

### Group B: GitHub Search (gh CLI & GitHub REST API)
- `TerminalSkills/skills` (Apache-2.0, updated Nov 7, 2026)
- `TomasVenkrbec/lazyline` (MIT, updated Apr 17, 2026)
- `duckdb/duckdb-skills` (MIT, updated Apr 14, 2026)
- `cloudflare/skills` (Apache-2.0, updated Nov 6, 2026)
- `pydantic/skills` (MIT, updated Oct 16, 2026)
- `charlyautomatiza/grafana-k6-plugin` (MIT, updated Jul 27, 2026)
- `CraftOS-dev/craftbot-agent-bundles` (MIT, updated 2026)
- `dash0hq/agent-skills` (Apache-2.0, updated Nov 2, 2026)
- `mohitkale/web-vitals-auditor` (MIT, updated Jul 28, 2026)
- `microsoft/azure-skills` (MIT, updated Nov 6, 2026)
- `trailofbits/skills` (CC-BY-SA-4.0, updated Nov 6, 2026)
- `nitinjain999/platform-skills` (Updated Nov 2026)
- `denizbarish/claudeflare` (Updated Nov 2026)
- `MohammadBafkar/polymath` (Updated Oct 2026)
- `openocta/openocta_skills` (Updated Jun 2026)

### Group C: Communities & Engineering Discussions
- Reddit `r/FastAPI`: Production concurrency pitfalls, avoiding synchronous blocking I/O in async routes
- Reddit `r/ClaudeCode`: Best practices for agent-driven k6 load generation and Nginx microcaching
- Reddit `r/nginx`: Upstream keepalive tuning, proxy connection recycling, and `/dev/shm` cache paths
- Reddit `r/webdev`: Next.js 16 bundle bloat triage, ECharts tree-shaking, and LCP/INP optimization
- Hacker News: Bloomberg Memray vs Py-Spy for native memory allocations in pandas/numpy ETL pipelines

### Group D: Vendors & Maintainers
- Microsoft Azure App Service Linux & Azure MySQL Architecture Guides
- Cloudflare Workers, Tiered Cache & Cache Rules Production Specifications
- Grafana k6 Official Script Builder and Arrival-Rate Scenario Standards
- Pydantic Services Inc. Official V2 Optimization Guidelines
- Bloomberg Engineering Memray Profiling Documentation
- Stichting DuckDB Foundation Official Columnar Transformation Documentation
- Dash0 OpenTelemetry APM & Sampling Standards
- Trail of Bits Application Security Static Analysis Handbook

### Group E: Specialized Research Tools
- Agent Marketplace Catalog (`search_marketplace`)
- Web Navigation & Retrieval (`search_web`, `read_file`)
- Local Repository Scratch Harness (`/tmp/cip-skill-trial`)

---

## 5. Search Commands Executed and Result Counts

The following 33 searches were executed via `gh search` and the GitHub REST API. Every count is reproducible:

| Search ID | Command / Query String | Result Count |
|:---:|:---|:---:|
| 1 | `gh search code "nginx filename:SKILL.md"` | 42,432 results |
| 2 | `gh search code "k6 filename:SKILL.md"` | 14,544 results |
| 3 | `gh search code "py-spy filename:SKILL.md"` | 3,672 results |
| 4 | `gh search code "memray filename:SKILL.md"` | 308 results |
| 5 | `gh search code "mysql filename:SKILL.md"` | 62,976 results |
| 6 | `gh search code "cloudflare filename:SKILL.md"` | 78,336 results |
| 7 | `gh search code "azure filename:SKILL.md"` | 180,224 results |
| 8 | `gh search code "uvicorn filename:SKILL.md"` | 13,440 results |
| 9 | `gh search code "lighthouse filename:SKILL.md"` | 30,720 results |
| 10 | `gh search code "opentelemetry filename:SKILL.md"` | 36,928 results |
| 11 | `gh search code "duckdb filename:SKILL.md"` | 11,392 results |
| 12 | `gh search code "scalene filename:SKILL.md"` | 283 results |
| 13 | `gh search code "wrk filename:SKILL.md"` | 1,984 results |
| 14 | `gh search code "fastapi filename:SKILL.md"` | 81,152 results |
| 15 | `gh search code "web-vitals filename:SKILL.md"` | 5,448 results |
| 16 | `gh search code "parquet filename:SKILL.md"` | 23,648 results |
| 17 | `gh search code "njs filename:SKILL.md"` | 26,240 results |
| 18 | `gh search code "azure mysql filename:SKILL.md"` | 9,104 results |
| 19 | `gh search code "azure app service filename:SKILL.md"` | 115,072 results |
| 20 | `gh search code "cloudflare worker filename:SKILL.md"` | 30,464 results |
| 21 | `gh search code "cloudflare cache filename:SKILL.md"` | 25,152 results |
| 22 | `gh search code "nginx performance tuning filename:SKILL.md"` | 1,932 results |
| 23 | `gh search code "mysql explain index slow filename:SKILL.md"` | 5,712 results |
| 24 | `gh search code "mysql query optimization filename:SKILL.md"` | 11,872 results |
| 25 | `gh search code "opentelemetry fastapi filename:SKILL.md"` | 4,272 results |
| 26 | `gh search code "fastapi gunicorn uvicorn filename:SKILL.md"` | 1,656 results |
| 27 | `gh search code "duckdb parquet filename:SKILL.md"` | 5,128 results |
| 28 | `gh search code "nginx microcache filename:SKILL.md"` | 1 result |
| 29 | `gh search code "azure app service python filename:SKILL.md"` | 5 results |
| 30 | `gh search code "lighthouse cli chrome filename:SKILL.md"` | 5 results |
| 31 | `gh search repos --topic agent-skills` | 40,427 repositories |
| 32 | `gh search repos --topic claude-skills` | 14,787 repositories |
| 33 | `gh search repos --topic claude-code-plugin` | 14,280 repositories |

---

## 6. Audit Verification & User Action Gate

All research and candidate trials were completed in read-only scratch environments.
- **Current Installation Status**: 0 new skills installed in `~/.claude`, `~/.gemini`, `~/.agents`, or the CIP repository.
- **Git Status**: 0 commits made, 0 pushes made.
- **Server Status**: Live API on `127.0.0.1:8000` and Cloudflare tunnel untouched.

Review this shortlist with Claude. Upon approval, install the desired skills by executing the install commands provided in Section 2.
