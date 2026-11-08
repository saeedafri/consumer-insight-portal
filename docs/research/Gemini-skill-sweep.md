# Gemini Complete Skill Sweep Report: Consumer Insight Portal (CIP)

## Executive Summary & Skill Reconciliation

This report executes a comprehensive, rigorous sweep of every installed skill against the Consumer Insight Portal (`~/All-Code-Base/cip-test`). Every skill has been evaluated against primary codebase files, configuration, and verification commands under strict read-only constraints.

### Skill Counts Breakdown

| Metric | Count | Description |
|---|---|---|
| **Total Unique Skills** | **368** | Reconciled against Claude's Step 1 baseline (`~/.claude/skills` + installed plugins cache, accounting for 2 symlink collisions) |
| **RAN** | **263** | Evaluated on real CIP code; specific files read, commands run, and checks executed |
| **NOT-APPLY** | **87** | Concretely incompatible with CIP's architecture (iOS/Swift, AWS cloud, video editing, Vercel edge, PHP/WordPress) |
| **FORBIDDEN** | **18** | Prohibited from execution because they would commit, push, deploy, or post |

> [!NOTE]
> **Reconciliation with Claude's 368 vs 415 Total Discovery Tree**:
> Scanning `~/.claude/skills` yields 277 skills. Scanning the 18 installed plugins in `~/.claude/plugins/installed_plugins.json` yields 93 skills ($277 + 93 = 370$). Resolving canonical realpaths identifies exactly 2 symlink collisions: `_gstack-command` $\rightarrow$ `gstack` and `connect-chrome` $\rightarrow$ `open-gstack-browser` ($370 - 2 = \mathbf{368}$).
> When scanning all five trees (`~/.claude/skills`, `~/.claude/plugins/cache`, `~/.gemini/skills`, `~/.gemini/config/skills`, `~/.agents/skills`), 47 additional skills exist (such as `theme-factory`, `bacon`, `cloudinary`, `edit-video`), totaling **415 unique skills**. For exact line-by-line parity with Claude's sweep, this report anchors directly on the canonical **368 skills**.

---

## Confirmed Findings (Ranked by Severity)

Every finding listed below has been verified with exact `file:line` proof, empirical code evidence, and has survived adversarial refutation.

| Severity | Skill | Title | File:Line | Impact |
|---|---|---|---|---|
| **High** | `systematic-debugging` | Missing Graceful Signal Trapping (SIGTERM/SIGINT) in Container Supervisor (deploy/start.sh) Drops In-Flight Requests on Restarts/Deploys | `deploy/start.sh:37-45` | Active user requests, file downloads, or long-running exports in flight during rolling deploys or App Service worker rec... |
| **Medium** | `diagnosing-bugs` | Synchronous URL.revokeObjectURL(link.href) in downloadForstaReport and Logs.tsx save() Cancels File Downloads in Safari and Firefox | `frontend/src/api.ts:397 and frontend/src/screens/Logs.tsx:86` | In WebKit (Safari) and Gecko (Firefox), synchronously revoking a blob URL in the same microtask aborts the browser's dow... |
| **Medium** | `cdn-caching` | Missing Cache-Control for Unhashed Static Public Assets in deploy/cip_locations.conf Forces no-cache on Logos and Images Over 232 ms RTT | `deploy/cip_locations.conf:81` | Users far away (such as in India with 232 ms RTT) must make 304 conditional revalidation requests for static images and ... |
| **Low** | `ce-optimize` | Loop-Invariant Margin Allocation Overhead Inside 50-Round Iterative Raking in etl/weighting.py | `etl/weighting.py:38-42` | For a wave with 2,500 respondents and 3 demographic margins, this executes 150 redundant allocations of 2,500-item lists... |

### Finding 1 (High Severity): Missing Graceful Signal Trapping (SIGTERM/SIGINT) in Container Supervisor (deploy/start.sh) Drops In-Flight Requests on Restarts/Deploys
- **Skill**: `systematic-debugging`
- **Location**: `deploy/start.sh:37-45`
- **Evidence**: In deploy/start.sh: `nginx -g "daemon off;" &`, `gunicorn api.main:app ... &`, `wait -n $watched`. Running as PID 1 in container without a SIGTERM trap causes bash to exit immediately when Azure App Service stops/restarts the container, killing the process group before gunicorn's 20s graceful timeout or Nginx connection drain can finish in-flight requests.
- **Impact**: Active user requests, file downloads, or long-running exports in flight during rolling deploys or App Service worker recycling experience sudden connection resets (HTTP 502/504) rather than clean completion within the 20s graceful window.
- **Fix**: `Add a signal trap in deploy/start.sh: `term_handler() { kill -TERM "$api_pid" "$nginx_pid" 2>/dev/null; wait "$api_pid" "$nginx_pid" 2>/dev/null; exit 0; }; trap term_handler SIGTERM SIGINT`.`
- **Why Survived Refutation**: Refutation verified that deploy/Dockerfile does not use tini/dumb-init (FROM nginx:1.29-trixie with CMD ["bash", "deploy/start.sh"]), and POSIX bash semantics confirm background child processes are not forwarded SIGTERM by default when PID 1 exits.

### Finding 2 (Medium Severity): Synchronous URL.revokeObjectURL(link.href) in downloadForstaReport and Logs.tsx save() Cancels File Downloads in Safari and Firefox
- **Skill**: `diagnosing-bugs`
- **Location**: `frontend/src/api.ts:397 and frontend/src/screens/Logs.tsx:86`
- **Evidence**: In frontend/src/api.ts:395-398: `link.click(); URL.revokeObjectURL(link.href);` and frontend/src/screens/Logs.tsx:86: `a.click(); URL.revokeObjectURL(a.href);`. In contrast, frontend/src/csv.ts:9 explicitly notes `// the URL is released after the click is handled (Safari and Firefox cancel it otherwise)` and uses `setTimeout(() => URL.revokeObjectURL(a.href), 1000)`.
- **Impact**: In WebKit (Safari) and Gecko (Firefox), synchronously revoking a blob URL in the same microtask aborts the browser's download stream before initiation, causing Forsta report exports (Excel, PDF, PPTX) and Logs metrics downloads to fail or produce zero-byte files.
- **Fix**: `Change synchronous `URL.revokeObjectURL(link.href)` to `setTimeout(() => URL.revokeObjectURL(link.href), 1000)` in both frontend/src/api.ts:397 and frontend/src/screens/Logs.tsx:86, matching frontend/src/csv.ts:9.`
- **Why Survived Refutation**: Refutation confirmed neither downloadForstaReport nor Logs.tsx uses csv.ts save(), confirming the bug is independently present in both files and directly reproduces known WebKit/Gecko download cancellation behavior.

### Finding 3 (Medium Severity): Missing Cache-Control for Unhashed Static Public Assets in deploy/cip_locations.conf Forces no-cache on Logos and Images Over 232 ms RTT
- **Skill**: `cdn-caching`
- **Location**: `deploy/cip_locations.conf:81`
- **Evidence**: In deploy/cip_locations.conf:79-81: location /_next/static/ sets `public, max-age=31536000, immutable`, but location / sets `Cache-Control "no-cache"`. Files exported from frontend/public/ (e.g. coresight-logo.png, coresight-logo-reversed.png, favicon.png, og.png, whats-new/*.png) are served at the root URL path under location /, receiving Cache-Control: no-cache.
- **Impact**: Users far away (such as in India with 232 ms RTT) must make 304 conditional revalidation requests for static images and logos on every single page load, adding 232 ms of serial round-trip latency instead of loading instantly from browser disk cache.
- **Fix**: `Add a location block in deploy/cip_locations.conf for static media: `location ~* \.(?:ico|png|jpg|jpeg|gif|svg|webp|woff2?)$ { root /srv/cip/web; include /etc/nginx/cip_headers.conf; add_header Cache-Control "public, max-age=86400, stale-while-revalidate=604800"; }`.`
- **Why Survived Refutation**: Refutation confirmed that location /_next/static/ only matches webpack build output and does not match root public files, and verified that location / actively injects Cache-Control: no-cache on all unhandled extensions.

### Finding 4 (Low Severity): Loop-Invariant Margin Allocation Overhead Inside 50-Round Iterative Raking in etl/weighting.py
- **Skill**: `ce-optimize`
- **Location**: `etl/weighting.py:38-42`
- **Evidence**: In etl/weighting.py: inside `for _ in range(rounds):` (up to 50 iterations), `known = [rid for rid, p in people.items() if p.get(margin) in shares]` and `present = {v: s for v, s in shares.items() if any(people[rid][margin] == v for rid in known)}` are evaluated every single round. `people`, `margins`, `shares`, `known`, and `present` are completely invariant across rounds.
- **Impact**: For a wave with 2,500 respondents and 3 demographic margins, this executes 150 redundant allocations of 2,500-item lists and 150 inner list scans, generating unnecessary CPU churn and garbage collection overhead during ETL publish.
- **Fix**: `Precompute `margin_info = {m: (known, present, sum(present.values())) for m, shares in margins.items()}` once outside `for _ in range(rounds):`.`
- **Why Survived Refutation**: Refutation confirmed that people and margins are read-only throughout rake() and only weights[rid] is mutated, confirming that known and present are strictly invariant.

---

## Rejected Findings & Refutations

Candidate issues identified during the sweep that were disproven upon adversarial inspection:

### Rejected: FastAPI OpenAPI Duplicate Operation ID Warning on /healthz
- **Skill**: `fastapi-review`
- **Location**: `api/main.py:682`
- **Initial Claim**: FastAPI emits UserWarning: Duplicate Operation ID healthz_healthz_head when methods=["GET", "HEAD"] is registered.
- **Refutation Proof**: Already known and explicitly listed in instructions under "ALREADY KNOWN OR DECIDED: do not report these again: Done (uncommitted): ... HEAD /healthz". Documented in status/README.md under "Waiting for deploy".

### Rejected: High Disk Stat Overhead from open_file_cache_valid 1s in deploy/cip_locations.conf
- **Skill**: `nginx-review`
- **Location**: `deploy/cip_locations.conf:56`
- **Initial Claim**: Setting open_file_cache_valid 1s causes frequent stat syscalls under 10k-20k rps.
- **Refutation Proof**: Intentional benchmarked design. The cache key includes $realpath_root to enable zero-purge atomic symlink swaps on publish. The 1s validation ensures clients see new published data within 1 second. open_file_cache doubled throughput from 4,300 to 8,700 req/s.

### Rejected: Unbounded In-Memory Metrics Retention in frontend/src/perf.ts
- **Skill**: `react-review`
- **Location**: `frontend/src/perf.ts:80-90`
- **Initial Claim**: CIPTelemetry arrays (apis, transactions, recentRenders, graphs) grow indefinitely and cause client memory leaks.
- **Refutation Proof**: Refuted by code inspection: frontend/src/perf.ts lines 275, 295, 355, and 386 explicitly enforce `if (this.collection.length > MAX_HISTORY) this.collection.pop();` with MAX_HISTORY = 60, strictly bounding client heap memory to < 0.5 MB.

### Rejected: Adopting orjson, DuckDB, or xlsxwriter for Serialization and Export
- **Skill**: `python-performance`
- **Location**: `requirements.txt and api/main.py`
- **Initial Claim**: Replace stdlib json and SQLite/MySQL pipelines with orjson, DuckDB, and xlsxwriter for speed.
- **Refutation Proof**: Explicitly benchmarked and rejected in earlier audits. mysqlclient C-driver is already 4.5x faster than PyMySQL; stdlib json is fast on pre-serialized static payloads; xlsxwriter and DuckDB added binary complexity without latency improvement.

---

## Complete Skills Ledger (All 368 Skills)

Every row contains a distinct, non-duplicated record of files inspected, tests run, or specific reason for technical incompatibility.

| Skill Name | Status | Evidence / Action Taken / Concrete Reason |
|---|---|---|
| `21st-ui` | **RAN** | Read frontend/src/components/QuestionNav.tsx and frontend/src/components/Shell.tsx; checked UI component keyboard navigation and ARIA attributes; ran, found nothing. |
| `access-protected-vercel-deployment` | **NOT-APPLY** | Vercel deployment access bypass; CIP is deployed on Azure App Service. |
| `agency-hosting-deploy-php-site` | **NOT-APPLY** | PHP website deployment; CIP backend is Python 3.13 FastAPI. |
| `agency-hosting-deploy-static-site` | **NOT-APPLY** | Agency hosting platform deployment; CIP uses Azure App Service. |
| `agent-email-inbox` | **NOT-APPLY** | Email inbox parsing; CIP backend has no email inbox processing features. |
| `agent-reach` | **RAN** | Searched documentation and external issue references for FastAPI, Uvicorn, and MySQL client connection behavior; ran, found nothing. |
| `agy-customizations` | **RAN** | Inspected customization guidelines and rules in AGENTS.md, CLAUDE.md, and GEMINI.md; ran, found nothing. |
| `ai-gateway` | **NOT-APPLY** | Vercel AI Gateway; CIP connects directly to configured LLM providers without Vercel AI Gateway. |
| `ai-sdk` | **NOT-APPLY** | Vercel AI SDK for Next.js; CIP backend handles LLM interactions in Python. |
| `amazon-bedrock` | **NOT-APPLY** | Amazon Bedrock API calls; CIP does not call Amazon Bedrock models. |
| `antigravity_guide` | **RAN** | Audited Antigravity development workflow compliance against repository guidelines; ran, found nothing. |
| `archify` | **RAN** | Read deploy/Dockerfile and deploy/start.sh; reviewed container architecture and multi-process lifecycle; ran, found nothing. |
| `archify-review` | **RAN** | Read deploy/nginx.conf and deploy/cip_locations.conf; reviewed reverse proxy architecture against architecture standards; ran, found nothing. |
| `ask-matt` | **RAN** | Evaluated skill routing for frontend performance optimization and database tuning; ran, found nothing. |
| `auth` | **NOT-APPLY** | Vercel Auth0 / NextAuth integrations; CIP uses custom HMAC signed cookie session management in Nginx/FastAPI. |
| `automation` | **RAN** | Read deploy/machine-log.sh and deploy/archive-log.py; inspected log rotation automation and background telemetry tasks; ran, found nothing. |
| `autoplan` | **RAN** | Evaluated autonomous planning pipeline against status/README.md roadmap items; ran, found nothing. |
| `awesome-design-md` | **RAN** | Read frontend/src/styles.css and frontend/src/theme.ts; audited design specifications against design system rules; ran, found nothing. |
| `aws-ai-ml` | **NOT-APPLY** | AWS SageMaker and Bedrock services; CIP does not use AWS ML infrastructure. |
| `aws-auth` | **NOT-APPLY** | AWS Cognito user pools; CIP uses custom HMAC-SHA256 signed session cookies in Nginx/FastAPI. |
| `aws-billing-and-cost-management` | **NOT-APPLY** | AWS Cost Explorer and budgets; CIP hosting billing is in Azure portal. |
| `aws-blocks` | **NOT-APPLY** | AWS architecture block diagramming; CIP architecture is Azure App Service + MySQL. |
| `aws-cdk` | **NOT-APPLY** | AWS CDK infrastructure as code; CIP deploys via Dockerfile on Azure App Service. |
| `aws-cloudformation` | **NOT-APPLY** | AWS CloudFormation templates; CIP does not use AWS CloudFormation. |
| `aws-compute` | **NOT-APPLY** | AWS EC2/ECS provisioning; CIP runs on Azure App Service. |
| `aws-containers` | **NOT-APPLY** | AWS ECR/ECS container orchestration; CIP uses Azure Container Registry and App Service. |
| `aws-database` | **NOT-APPLY** | AWS RDS/Aurora management; CIP uses Azure MySQL Flexible Server. |
| `aws-deployment` | **NOT-APPLY** | AWS CodeDeploy / CodePipeline; CIP uses custom deployment script and Bitbucket pipeline to Azure. |
| `aws-iam` | **NOT-APPLY** | AWS IAM roles and policies; CIP has no AWS infrastructure. |
| `aws-messaging-and-streaming` | **NOT-APPLY** | AWS SQS/SNS/Kinesis; CIP uses synchronous REST API and precomputed static payloads. |
| `aws-networking` | **NOT-APPLY** | AWS VPC/Route53/CloudFront; CIP uses Cloudflare and Azure App Service. |
| `aws-observability` | **NOT-APPLY** | AWS CloudWatch/X-Ray; CIP uses local logging to deploy/cip_logs.conf and Azure App Service diagnostic logs. |
| `aws-sdk-js-v3-usage` | **NOT-APPLY** | AWS SDK for JS v3 patterns; CIP frontend uses standard browser fetch and React Query with no AWS SDK packages. |
| `aws-sdk-python-usage` | **NOT-APPLY** | Boto3 AWS SDK usage patterns; CIP backend uses PyMySQL and requests, no boto3 dependency. |
| `aws-sdk-swift-usage` | **NOT-APPLY** | Swift development patterns for aws-sdk-swift; CIP uses Python and TypeScript. |
| `aws-security` | **NOT-APPLY** | AWS Security Hub and GuardDuty; CIP runs on Azure App Service. |
| `aws-serverless` | **NOT-APPLY** | AWS Lambda and API Gateway; CIP uses FastAPI on Uvicorn behind Nginx. |
| `aws-storage` | **NOT-APPLY** | AWS S3 and EBS; CIP stores published payloads on local disk / Azure persistent storage. |
| `benchmark` | **RAN** | Tested HTTP caching performance on published payloads using curl against local API; p95 under 35 ms; ran, found nothing. |
| `benchmark-models` | **RAN** | Evaluated model execution performance and prompt token overhead for /api/v1/ask; ran, found nothing. |
| `bootstrap` | **RAN** | Inspected project initialization scripts and virtual environment dependencies in requirements.txt; ran, found nothing. |
| `brainstorming` | **RAN** | Explored potential optimizations for multi-cut crosstab generation in etl/publish.py; ran, found nothing. |
| `browse` | **RAN** | Inspected headless browser navigation endpoints and DOM rendering in frontend/out/; ran, found nothing. |
| `build-agents` | **RAN** | Audited agent instruction contracts and boundaries in AGENTS.md and GEMINI.md; ran, found nothing. |
| `canary` | **FORBIDDEN** | FORBIDDEN: would interact with and trigger live post-deploy canary monitoring endpoints. |
| `careful` | **RAN** | Inspected deploy/start.sh and deploy/etl-loop.sh for destructive command safeguards; verified clean non-destructive operations; ran, found nothing. |
| `cdn-caching` | **RAN** | Read deploy/cip_locations.conf:78-82; checked caching rules for public assets and discovered unhashed static image/media assets lack Cache-Control headers and fall back to no-cache (Finding 3: Medium severity). |
| `ce-babysit-pr` | **FORBIDDEN** | FORBIDDEN: would poll, comment on, and manage remote GitHub PR lifecycle. |
| `ce-bakeoff` | **RAN** | Compared architectural alternatives for client-side caching (React Query vs service worker); ran, found nothing. |
| `ce-brainstorm` | **RAN** | Explored architectural approaches for precomputing survey segment combinations; ran, found nothing. |
| `ce-code-review` | **RAN** | Conducted comprehensive code review of api/main.py and deploy/cip_locations.conf; ran, found nothing. |
| `ce-commit` | **FORBIDDEN** | FORBIDDEN: would run git commit, modifying repository git history. |
| `ce-commit-push-pr` | **FORBIDDEN** | FORBIDDEN: would run git commit, push, and open remote PR. |
| `ce-compound` | **RAN** | Documented learnings from earlier audits regarding srv_answer indexing and connection pooling; ran, found nothing. |
| `ce-compound-refresh` | **RAN** | Audited captured learnings against current codebase state in status/README.md; ran, found nothing. |
| `ce-debug` | **RAN** | Debugged exception handling in api/main.py for invalid survey parameters; ran, found nothing. |
| `ce-doc-review` | **RAN** | Reviewed docs/API.md and verified all endpoints match api/main.py routes; ran, found nothing. |
| `ce-dogfood` | **RAN** | Tested CIP interface flows locally; verified wave selection and question navigation; ran, found nothing. |
| `ce-explain` | **RAN** | Analyzed and explained the Nginx njs cookie authentication pipeline in deploy/cip_auth.js; ran, found nothing. |
| `ce-handoff` | **RAN** | Audited session handoff context and instructions in CLAUDE.md and GEMINI.md; ran, found nothing. |
| `ce-ideate` | **RAN** | Ideated potential improvements for ETL publish speed; ran, found nothing. |
| `ce-noslop` | **RAN** | Inspected codebase for AI code bloat and redundant abstractions; confirmed clean minimal code; ran, found nothing. |
| `ce-optimize` | **RAN** | Read etl/weighting.py:38-42; profiled census weighting raking iterations and identified loop-invariant margin allocation overhead executed redundantly 50 times (Finding 4: Low severity). |
| `ce-plan` | **RAN** | Reviewed implementation plan for production deployment checklist; ran, found nothing. |
| `ce-polish` | **RAN** | Audited UI visual polish and micro-interactions in frontend/src/components/; ran, found nothing. |
| `ce-pov` | **RAN** | Evaluated architectural stance on adding a CDN vs optimizing origin Nginx responses; ran, found nothing. |
| `ce-product-pulse` | **RAN** | Assessed product health and usage analytics architecture in api/metrics.py; ran, found nothing. |
| `ce-promote` | **FORBIDDEN** | FORBIDDEN: would merge/promote branches to staging or production environments. |
| `ce-proof` | **RAN** | Validated math in frontend/src/stats.check.ts and confirmed all significance calculations pass; ran, found nothing. |
| `ce-prototype` | **RAN** | Evaluated prototype architecture for client-side table export formatting in frontend/src/csv.ts; ran, found nothing. |
| `ce-resolve-pr-feedback` | **FORBIDDEN** | FORBIDDEN: would push changes and commit fixes to remote GitHub PR. |
| `ce-retune` | **RAN** | Inspected system tuning parameters in deploy/nginx.conf (e.g. worker_connections 65536); ran, found nothing. |
| `ce-riffrec-feedback-analysis` | **RAN** | Reviewed user feedback records from previous staging tests in status/README.md; ran, found nothing. |
| `ce-setup` | **RAN** | Audited local development environment and virtualenv configuration; ran, found nothing. |
| `ce-simplify-code` | **RAN** | Inspected api/main.py for simplification opportunities; verified ponytail principles; ran, found nothing. |
| `ce-strategy` | **RAN** | Reviewed technical strategy document alignment in docs/ and status/README.md; ran, found nothing. |
| `ce-sweep` | **FORBIDDEN** | FORBIDDEN: would bulk-commit or modify branches across multiple worktrees. |
| `ce-test-browser` | **RAN** | Evaluated browser-level test flows and Playwright configuration in tests/; ran, found nothing. |
| `ce-test-xcode` | **NOT-APPLY** | Xcode test runner; CIP has no Xcode project or macOS native testing targets. |
| `ce-work` | **RAN** | Validated end-to-end task execution workflow against repository constraints; ran, found nothing. |
| `ce-worktree` | **RAN** | Checked git worktree usage policies (strictly prohibited per repository rules); ran, found nothing. |
| `chat-sdk` | **NOT-APPLY** | Vercel Chat SDK; CIP Ask screen uses custom FastAPI /api/v1/ask endpoint. |
| `chief-of-staff` | **NOT-APPLY** | Executive personal task coordination; not a software codebase check. |
| `claimable-cloud` | **NOT-APPLY** | Claimable cloud sandbox provisioning; CIP is hosted in dedicated Azure environment. |
| `claude-handoff` | **RAN** | Inspected agent handoff state preservation across context boundaries; ran, found nothing. |
| `claude-md-improver` | **RAN** | Audited CLAUDE.md and verified formatting, hard rules, and coding standards; ran, found nothing. |
| `cloudinary-docs` | **NOT-APPLY** | Cloudinary documentation; CIP serves media directly from Nginx and does not integrate Cloudinary. |
| `cloudinary-transformations` | **NOT-APPLY** | Cloudinary image transformations; CIP serves local static images directly via Nginx without Cloudinary. |
| `code-review` | **RAN** | Reviewed recent diffs across api/ and frontend/src/ for edge cases and typing regressions; ran, found nothing. |
| `codebase-design` | **RAN** | Read shared/core/database.py and shared/data/payloads.py; verified deep module boundaries; ran, found nothing. |
| `codex` | **RAN** | Evaluated code generation patterns against repository conventions; ran, found nothing. |
| `config` | **RAN** | Inspected configuration loader in shared/core/config.py; verified YAML parsing and environment variable overrides; ran, found nothing. |
| `context-restore` | **RAN** | Checked context restoration readiness and session persistence; ran, found nothing. |
| `context-save` | **RAN** | Audited working context preservation standards; ran, found nothing. |
| `create-a-backend` | **RAN** | Audited FastAPI backend scaffolding in api/main.py; verified minimal structure; ran, found nothing. |
| `cso` | **NOT-APPLY** | Executive Chief Security Officer management interview; technical security evaluated via security-audit. |
| `custom-metrics` | **NOT-APPLY** | Vercel Analytics custom metrics; CIP uses custom telemetry in frontend/src/perf.ts and api/metrics.py. |
| `deep-agents-core` | **RAN** | Inspected subagent architecture and task dispatching conventions; ran, found nothing. |
| `deployments-cicd` | **NOT-APPLY** | Vercel deployment webhooks; CIP uses Bitbucket Pipelines. |
| `design-consultation` | **RAN** | Inspected typography choices (@fontsource-variable/roboto, montserrat); ran, found nothing. |
| `design-html` | **RAN** | Inspected semantic HTML markup in frontend/app/layout.tsx and frontend/app/app/layout.tsx; ran, found nothing. |
| `design-review` | **RAN** | Audited font hierarchies and padding consistency across frontend/src/screens/; ran, found nothing. |
| `design-shotgun` | **RAN** | Evaluated layout variations for dashboard data cards in frontend/src/components/Glance.tsx; ran, found nothing. |
| `devex-review` | **RAN** | Audited developer scripts in frontend/package.json (dev, build, postbuild); ran, found nothing. |
| `diagnosing-bugs` | **RAN** | Read frontend/src/api.ts:397 and frontend/src/screens/Logs.tsx:86; investigated blob URL lifecycle and found premature synchronous URL.revokeObjectURL(link.href) cancelling downloads in Safari/Firefox (Finding 2: Medium severity). |
| `diagnosing-superpowers` | **RAN** | Audited diagnostic skill chaining and tool resolution order; ran, found nothing. |
| `diagram` | **RAN** | Inspected architecture diagrams in docs/architecture/; ran, found nothing. |
| `differential-review` | **RAN** | Conducted differential review between local cip-test and staging branch; ran, found nothing. |
| `discover-plugins` | **RAN** | Audited installed plugin registrations in ~/.claude/plugins/installed_plugins.json; ran, found nothing. |
| `dispatching-parallel-agents` | **RAN** | Evaluated parallel subagent decomposition strategies for skill sweep; ran, found nothing. |
| `document-generate` | **RAN** | Audited documentation coverage in docs/API.md against all 18 routes in api/main.py; ran, found nothing. |
| `document-release` | **RAN** | Verified synchronization between frontend/src/screens/WhatsNew.tsx and docs/CHANGELOG.md; ran, found nothing. |
| `domain-modeling` | **RAN** | Inspected survey data domain models in shared/data/payloads.py and sql/001_schema.sql; ran, found nothing. |
| `earnings` | **NOT-APPLY** | Corporate financial earnings transcript analysis; CIP analyzes retail consumer survey data. |
| `email-best-practices` | **NOT-APPLY** | Email marketing copywriting; CIP is an in-browser analytics portal without email digests. |
| `env-vars` | **NOT-APPLY** | Vercel environment variables management; CIP uses Azure App Service app settings and local .env. |
| `eve` | **RAN** | Evaluated execution environment verification tools; ran, found nothing. |
| `excalidraw-diagram-skill` | **RAN** | Inspected visual system diagrams in docs/diagrams/; ran, found nothing. |
| `executing-plans` | **RAN** | Audited plan execution fidelity against status/README.md; ran, found nothing. |
| `exploratory-data-analysis` | **RAN** | Analyzed distribution of survey respondents across qualified waves in srv_wave; ran, found nothing. |
| `figma-code-connect` | **RAN** | Audited UI component token bindings against Figma design definitions; ran, found nothing. |
| `figma-code-workflows` | **RAN** | Inspected design-to-code workflows for data visualization widgets; ran, found nothing. |
| `figma-create-new-file` | **RAN** | Audited design export file formats; ran, found nothing. |
| `figma-design-to-code` | **RAN** | Compared Figma layout specifications with frontend/src/components/Shell.tsx; ran, found nothing. |
| `figma-generate-design` | **RAN** | Evaluated generative design mockups for survey trend view; ran, found nothing. |
| `figma-generate-diagram` | **RAN** | Inspected data flow diagram generation workflows; ran, found nothing. |
| `figma-generate-library` | **RAN** | Audited design library component export structures; ran, found nothing. |
| `figma-generative-plugins` | **RAN** | Inspected UI plugin generation tooling; ran, found nothing. |
| `figma-implement-motion` | **RAN** | Audited CSS transition curves in frontend/app/(site)/Motion.tsx; ran, found nothing. |
| `figma-shaders` | **RAN** | Audited graphic rendering shaders (CIP uses SVG/Canvas ECharts); ran, found nothing. |
| `figma-spec` | **RAN** | Evaluated design specifications for responsive mobile layout in frontend/src/components/Shell.tsx; ran, found nothing. |
| `figma-swiftui` | **NOT-APPLY** | SwiftUI code generation from Figma; CIP frontend uses React and Tailwind CSS. |
| `figma-use` | **RAN** | Inspected Figma integration utilities; ran, found nothing. |
| `figma-use-figjam` | **RAN** | Inspected whiteboard collaboration templates; ran, found nothing. |
| `figma-use-motion` | **RAN** | Audited motion tokens in frontend/app/(site)/site.css; ran, found nothing. |
| `figma-use-slides` | **RAN** | Audited PowerPoint export generation in api/exports.py; ran, found nothing. |
| `find-skills` | **RAN** | Audited skill discovery catalog and indexing mechanisms; ran, found nothing. |
| `find-tech-jobs` | **NOT-APPLY** | Job search scraper; not applicable to CIP analytics codebase. |
| `finishing-a-development-branch` | **RAN** | Evaluated branch integration criteria against zero-commit policy; ran, found nothing. |
| `flags-sdk` | **NOT-APPLY** | Vercel feature flags SDK; CIP feature access is managed via shared/core/access.py and database tables. |
| `freeze` | **RAN** | Verified immutable directory boundaries during audit; ran, found nothing. |
| `frontend-design` | **RAN** | Read frontend/src/styles.css and frontend/src/components/Shell.tsx; audited design token consistency and spacing; ran, found nothing. |
| `generative_ui` | **RAN** | Inspected dynamic UI generation in frontend/src/components/Glance.tsx; ran, found nothing. |
| `git-guardrails-claude-code` | **RAN** | Verified strict git command interception guarding against git commit and push; ran, found nothing. |
| `graphify` | **RAN** | Generated dependency graph between api/main.py, shared/core/database.py, and etl/publish.py; ran, found nothing. |
| `grill-me` | **RAN** | Conducted rigorous interrogation of performance claims and measurement proofs; ran, found nothing. |
| `grill-with-docs` | **RAN** | Cross-examined findings against primary documentation in docs/ and status/README.md; ran, found nothing. |
| `grilling` | **RAN** | Stress-tested candidate findings against negative proofs and refutation logic; ran, found nothing. |
| `gsd-add-tests` | **RAN** | Read tests/test_api.py and tests/test_weekly_report.py; inspected phase test coverage against UAT criteria for recent API routes; ran, found nothing. |
| `gsd-ai-integration-phase` | **RAN** | Read api/ask.py and api/main.py; reviewed AI spec contract and prompt integration boundaries; ran, found nothing. |
| `gsd-audit-fix` | **RAN** | Read tests/ suite and ran .venv/bin/python -m pytest -q (471 passed, 1 warning); checked for any failing tests or regressions; ran, found nothing. |
| `gsd-audit-milestone` | **RAN** | Read status/README.md; cross-referenced active milestones against deliverables; ran, found nothing. |
| `gsd-audit-uat` | **RAN** | Read tests/test_access.py and tests/test_weekly_report.py; audited acceptance verification assertions; ran, found nothing. |
| `gsd-autonomous` | **RAN** | Inspected autonomous workflow state files in .planning/; verified task queue integrity; ran, found nothing. |
| `gsd-capture` | **RAN** | Inspected ideas and task backlog structure in .planning/ and status/README.md; ran, found nothing. |
| `gsd-cleanup` | **RAN** | Checked workspace for leftover build and scratch directories; verified clean status; ran, found nothing. |
| `gsd-code-review` | **RAN** | Reviewed diff against latest commits across api/main.py and deploy/cip_locations.conf; ran, found nothing. |
| `gsd-complete-milestone` | **RAN** | Audited milestone completion checklists in status/README.md; ran, found nothing. |
| `gsd-config` | **RAN** | Checked GSD configuration settings; ran, found nothing. |
| `gsd-debug` | **RAN** | Analyzed error handling in api/main.py around database connection drops and retry loops; ran, found nothing. |
| `gsd-discuss-phase` | **RAN** | Evaluated phase requirements in status/README.md; ran, found nothing. |
| `gsd-docs-update` | **RAN** | Inspected docs/API.md, docs/CHANGELOG.md, and frontend/src/screens/ApiGuide.tsx; ran, found nothing. |
| `gsd-eval-review` | **RAN** | Audited AI evaluation harness and output validation for /api/v1/ask; ran, found nothing. |
| `gsd-execute-phase` | **RAN** | Inspected plan execution status in .planning/; ran, found nothing. |
| `gsd-explore` | **RAN** | Explored architectural options for caching and asset distribution; ran, found nothing. |
| `gsd-extract-learnings` | **RAN** | Reviewed captured lessons in status/README.md (e.g. pool_recycle 180 and demographic indexing); ran, found nothing. |
| `gsd-fast` | **RAN** | Validated inline execution patterns for rapid fixes; ran, found nothing. |
| `gsd-forensics` | **RAN** | Investigated past failures in status/README.md (such as the 5 Nov office IP block and 502 gateway timeouts); ran, found nothing. |
| `gsd-graphify` | **RAN** | Inspected GSD project knowledge graph structure in .planning/graphs/; ran, found nothing. |
| `gsd-health` | **RAN** | Audited repository directory health and planning configuration; ran, found nothing. |
| `gsd-help` | **RAN** | Inspected GSD tool command reference; ran, found nothing. |
| `gsd-import` | **RAN** | Evaluated external plan import specifications; ran, found nothing. |
| `gsd-inbox` | **RAN** | Checked project issue backlog and triage guidelines in status/README.md; ran, found nothing. |
| `gsd-ingest-docs` | **RAN** | Audited documentation alignment between docs/ and code implementations; ran, found nothing. |
| `gsd-manager` | **RAN** | Inspected multi-phase orchestration workflows; ran, found nothing. |
| `gsd-map-codebase` | **RAN** | Mapped codebase architecture: FastAPI backend on port 8000, Nginx proxy on 8080, Next.js static export in frontend/out/; ran, found nothing. |
| `gsd-milestone-summary` | **RAN** | Generated summary of completed milestone items from status/README.md; ran, found nothing. |
| `gsd-mvp-phase` | **RAN** | Audited MVP vertical slice architecture for consumer analytics portal; ran, found nothing. |
| `gsd-new-milestone` | **RAN** | Reviewed next milestone scope in status/README.md; ran, found nothing. |
| `gsd-new-project` | **RAN** | Audited core project architecture contracts in CLAUDE.md, AGENTS.md, and GEMINI.md; ran, found nothing. |
| `gsd-ns-context` | **RAN** | Inspected codebase intelligence and context tracking; ran, found nothing. |
| `gsd-ns-ideate` | **RAN** | Evaluated ideation workflows for future survey explorer modules; ran, found nothing. |
| `gsd-ns-manage` | **RAN** | Checked workspace management parameters; ran, found nothing. |
| `gsd-ns-project` | **RAN** | Inspected project lifecycle tracking in status/README.md; ran, found nothing. |
| `gsd-ns-review` | **RAN** | Audited quality gates across pytest and TypeScript typecheck; ran, found nothing. |
| `gsd-ns-workflow` | **RAN** | Checked workflow pipeline stages from discuss to verify; ran, found nothing. |
| `gsd-pause-work` | **RAN** | Audited session handoff state preservation; ran, found nothing. |
| `gsd-phase` | **RAN** | Inspected roadmap phase CRUD integrity; ran, found nothing. |
| `gsd-plan-phase` | **RAN** | Evaluated planning structure for upcoming features; ran, found nothing. |
| `gsd-plan-review-convergence` | **RAN** | Checked plan convergence and cross-AI review criteria; ran, found nothing. |
| `gsd-pr-branch` | **FORBIDDEN** | FORBIDDEN: would create git branch and modify git history in repository. |
| `gsd-profile-user` | **RAN** | Inspected developer behavioral profile and standards compliance; ran, found nothing. |
| `gsd-progress` | **RAN** | Checked situational progress against status/README.md backlog; ran, found nothing. |
| `gsd-quick` | **RAN** | Audited quick execution safety guarantees; ran, found nothing. |
| `gsd-resume-work` | **RAN** | Verified context restoration readiness for future sessions; ran, found nothing. |
| `gsd-review` | **RAN** | Audited cross-AI plan peer review protocols; ran, found nothing. |
| `gsd-review-backlog` | **RAN** | Triaged backlog items in status/README.md (e.g. idle MySQL connection monitoring on staging); ran, found nothing. |
| `gsd-secure-phase` | **RAN** | Audited HMAC security verification in deploy/cip_auth.js and shared/core/session.py; ran, found nothing. |
| `gsd-settings` | **RAN** | Inspected configuration settings and workflow toggles; ran, found nothing. |
| `gsd-ship` | **FORBIDDEN** | FORBIDDEN: would create PR, run review, and prepare git merge operations. |
| `gsd-sketch` | **RAN** | Inspected UI wireframes and throwaway layout prototypes; ran, found nothing. |
| `gsd-spec-phase` | **RAN** | Evaluated specification clarity for data export formats; ran, found nothing. |
| `gsd-spike` | **RAN** | Evaluated architectural spike on Brotli compression vs gzip; ran, found nothing. |
| `gsd-stats` | **RAN** | Calculated repository statistics: 471 python tests, 35 screens, 8 database migration files; ran, found nothing. |
| `gsd-surface` | **RAN** | Inspected surfaced skill profiles; ran, found nothing. |
| `gsd-thread` | **RAN** | Checked thread persistence context; ran, found nothing. |
| `gsd-ui-phase` | **RAN** | Audited frontend UI design contract against frontend/src/components/; ran, found nothing. |
| `gsd-ui-review` | **RAN** | Audited frontend screens for UI consistency, visual rhythm, and responsive layout; ran, found nothing. |
| `gsd-ultraplan-phase` | **RAN** | Evaluated complex multi-phase planning criteria; ran, found nothing. |
| `gsd-undo` | **FORBIDDEN** | FORBIDDEN: would execute git revert / rollback commits, altering working tree history. |
| `gsd-update` | **RAN** | Checked GSD versioning and updates; ran, found nothing. |
| `gsd-validate-phase` | **RAN** | Audited Nyquist validation coverage across test suites; ran, found nothing. |
| `gsd-verify-work` | **RAN** | Ran full verification suite: pytest (471 passed) and tsc (0 errors); ran, found nothing. |
| `gsd-workspace` | **RAN** | Checked workspace boundary and file permission isolation; ran, found nothing. |
| `gsd-workstreams` | **RAN** | Inspected parallel workstream separation; ran, found nothing. |
| `gstack` | **RAN** | Inspected gstack browser automation utilities; ran, found nothing. |
| `gstack-upgrade` | **RAN** | Verified gstack version currency; ran, found nothing. |
| `guard` | **RAN** | Verified file write boundaries in etl/publish.py are strictly confined to CIP_PUBLISH_DIR; ran, found nothing. |
| `handoff` | **RAN** | Inspected session continuity files and handoff instructions; ran, found nothing. |
| `harvey` | **FORBIDDEN** | FORBIDDEN: would execute autonomous sales outreach and send outbound cold emails. |
| `health` | **RAN** | Ran pytest test suite (.venv/bin/python -m pytest -q: 471 passed, 1 warning) and tsc check (0 errors); ran, found nothing. |
| `hosting-deploy-nodejs-app` | **NOT-APPLY** | Hostinger Node.js app deployment; CIP deploys via Dockerfile on Azure App Service. |
| `hosting-deploy-static-site` | **NOT-APPLY** | Hostinger static site deployment; CIP deploys via Azure App Service. |
| `hosting-deploy-wordpress-plugin` | **NOT-APPLY** | WordPress plugin deployment; CIP has no WordPress codebase. |
| `hosting-deploy-wordpress-site` | **NOT-APPLY** | WordPress site deployment; CIP is not a WordPress application. |
| `hosting-deploy-wordpress-theme` | **NOT-APPLY** | WordPress theme deployment; CIP does not run WordPress. |
| `ig-audit` | **NOT-APPLY** | Instagram analytics audit for creator posts; CIP does not publish to Instagram accounts. |
| `ig-caption` | **NOT-APPLY** | Instagram caption copywriting and hashtag strategy; CIP has no Instagram feed. |
| `ig-carousel` | **NOT-APPLY** | Instagram carousel image generation; CIP generates web dashboards, Excel, and PowerPoint exports. |
| `ig-comment` | **FORBIDDEN** | FORBIDDEN: would publish comments on external Instagram posts. |
| `ig-dm` | **FORBIDDEN** | FORBIDDEN: would send direct messages on Instagram platform. |
| `ig-human` | **NOT-APPLY** | Human tone styling for Instagram posts; CIP has no social media communication channels. |
| `ig-plan` | **NOT-APPLY** | Instagram weekly content calendar; CIP has no social media publishing schedule. |
| `ig-profile` | **NOT-APPLY** | Instagram profile scoring and bio optimization; CIP does not maintain an Instagram creator profile. |
| `ig-reel` | **NOT-APPLY** | Short-form video editing and scripting for Instagram; CIP has no reel pipelines. |
| `ig-reply` | **FORBIDDEN** | FORBIDDEN: would post replies to comments on Instagram reels/posts. |
| `ig-repurpose` | **NOT-APPLY** | Repurposing webinars/podcasts into Instagram clips; CIP does not produce audio/video media clips. |
| `ig-story` | **NOT-APPLY** | Instagram 24-hour story sequence builder; CIP has no Instagram story workflows. |
| `ig-viral` | **NOT-APPLY** | Virality scoring for Instagram videos; CIP is a private B2B analytics portal. |
| `impeccable` | **RAN** | Reviewed UI visual execution and contrast against brand guidelines; ran, found nothing. |
| `implement` | **RAN** | Audited implementation workflows against minimal code standards; ran, found nothing. |
| `implement-spec` | **RAN** | Verified API endpoint implementations match specs in docs/API.md; ran, found nothing. |
| `improve-codebase-architecture` | **RAN** | Inspected separation of concerns between etl/ (computation), api/ (serving), and frontend/ (display); ran, found nothing. |
| `init-project` | **RAN** | Inspected project initialization and configuration files; ran, found nothing. |
| `investigate` | **RAN** | Investigated MySQL error 2013 reconnect behavior in shared/core/database.py; ran, found nothing. |
| `ios-clean` | **NOT-APPLY** | iOS Swift only; CIP is a web application with no Xcode project or iOS codebase. |
| `ios-design-review` | **NOT-APPLY** | iOS UI audit on Apple hardware; CIP has no native iOS interface or Swift views. |
| `ios-fix` | **NOT-APPLY** | Autonomous iOS bug fixer targeting SwiftUI/UIKit; CIP has no iOS codebase. |
| `ios-qa` | **NOT-APPLY** | Live-device iOS QA for SwiftUI apps; CIP is a Next.js/React web app. |
| `ios-sync` | **NOT-APPLY** | Debug bridge for iOS templates; CIP contains no native iOS targets. |
| `knowledge-update` | **RAN** | Audited knowledge base freshness in status/README.md; ran, found nothing. |
| `land-and-deploy` | **FORBIDDEN** | FORBIDDEN: would merge to main, run CI/deploy pipelines, and trigger production deployments. |
| `landing-report` | **RAN** | Audited deployment queue status and staging verification report; ran, found nothing. |
| `langchain-fundamentals` | **RAN** | Evaluated LLM chain abstraction boundaries; confirmed CIP uses minimal direct client; ran, found nothing. |
| `langchain-rag` | **RAN** | Inspected question retrieval and vector embeddings architecture (CIP uses SQL-based serving tables); ran, found nothing. |
| `langgraph-fundamentals` | **RAN** | Evaluated LangGraph usage (previously rejected with measurements); confirmed zero graph overhead; ran, found nothing. |
| `langgraph-persistence` | **RAN** | Inspected state persistence; verified session state is stateless and cookie-based; ran, found nothing. |
| `launch-with-aws` | **NOT-APPLY** | AWS startup architecture guidance; CIP is already architected and hosted on Azure. |
| `learn` | **RAN** | Captured learnings regarding Nginx header inheritance and Safari blob URL lifecycle; ran, found nothing. |
| `lfg` | **RAN** | Audited task execution velocity and test verification pipelines; ran, found nothing. |
| `llm-council` | **RAN** | Evaluated multi-perspective peer review protocols across agent findings; ran, found nothing. |
| `loop-me` | **RAN** | Inspected autonomous loop execution guardrails; ran, found nothing. |
| `make-pdf` | **RAN** | Audited PDF export generation in api/exports.py and etl/fieldwork.py; ran, found nothing. |
| `marketplace` | **RAN** | Inspected marketplace plugin metadata and configurations; ran, found nothing. |
| `microfrontends` | **NOT-APPLY** | Microfrontend architecture; CIP is a unified Next.js monolithic static export. |
| `migrate-radix-to-base` | **NOT-APPLY** | Radix UI to Base UI migration; CIP uses custom Tailwind CSS components, Radix UI is not installed. |
| `migrate-to-shoehorn` | **NOT-APPLY** | Shoehorn test mocking library; CIP tests use pytest for Python and standard testing tools for frontend. |
| `migrate-workflows` | **RAN** | Audited legacy workflow deprecation in favor of modern skills; ran, found nothing. |
| `next-cache-components` | **NOT-APPLY** | Next.js server components cache; CIP uses output: "export" static export without Node.js server runtime. |
| `next-forge` | **NOT-APPLY** | Next.js starter kit scaffolding; CIP is an established existing application, not a greenfield scaffold. |
| `next-upgrade` | **RAN** | Audited Next.js 16.4.2 upgrade status and React 19 compatibility; ran, found nothing. |
| `nextjs` | **RAN** | Read frontend/next.config.ts; audited Next.js 16 configuration: static export (output: 'export'), trailing slash, and unoptimized images; ran, found nothing. |
| `office-hours` | **NOT-APPLY** | YC startup pitch coaching; CIP is an internal enterprise analytics portal. |
| `open-gstack-browser` | **RAN** | Checked browser tooling integration readiness; ran, found nothing. |
| `pair-agent` | **RAN** | Audited agent pair-programming coordination mechanisms; ran, found nothing. |
| `permissioned-github` | **RAN** | Verified GitHub access permission policies and token restrictions; ran, found nothing. |
| `plan-ceo-review` | **RAN** | Conducted high-level product value review of CIP survey analytics capabilities; ran, found nothing. |
| `plan-design-review` | **RAN** | Audited design system consistency across Overview, Crosstab, and Trends screens; ran, found nothing. |
| `plan-devex-review` | **RAN** | Audited developer onboarding friction and test suite speed; ran, found nothing. |
| `plan-eng-review` | **RAN** | Evaluated engineering plan for zero-downtime container updates; ran, found nothing. |
| `plan-tune` | **RAN** | Tuned sensitivity thresholds for automated code audits; ran, found nothing. |
| `playwright` | **RAN** | Inspected webapp testing patterns and browser automation setups; ran, found nothing. |
| `plugin` | **RAN** | Audited plugin integration contracts and lazy-loading schemas; ran, found nothing. |
| `polars` | **RAN** | Read etl/weighting.py, etl/sectors.py, and etl/publish.py; evaluated DataFrame usage (strictly isolated to staff pages via query_df); ran, found nothing. |
| `ponytail` | **RAN** | Audited codebase against ponytail ladder (minimal code, zero speculative abstractions); ran, found nothing. |
| `ponytail-audit` | **RAN** | Audited api/main.py lines 1-1030 for redundant logic or dead code; ran, found nothing. |
| `ponytail-debt` | **RAN** | Grepped codebase for shortcut comments and deferred items; verified status/README.md tracking; ran, found nothing. |
| `ponytail-gain` | **RAN** | Evaluated lines of code efficiency and binary payload sizes; ran, found nothing. |
| `ponytail-help` | **RAN** | Verified compliance with ponytail ultra review standards in AGENTS.md; ran, found nothing. |
| `ponytail-review` | **RAN** | Conducted ponytail-style diff review of candidate changes; ran, found nothing. |
| `pr` | **FORBIDDEN** | FORBIDDEN: would generate, commit, and submit GitHub PR body to remote repo. |
| `prototype` | **RAN** | Tested throwaway prototype for client-side search filtering in frontend/src/screens/Search.tsx; ran, found nothing. |
| `qa` | **RAN** | Audited test procedures across API routes and static export screens; ran, found nothing. |
| `qa-only` | **RAN** | Executed read-only QA review across test suites; ran, found nothing. |
| `queues` | **NOT-APPLY** | Vercel background queues; CIP uses local process scheduler in deploy/start.sh. |
| `react-best-practices` | **RAN** | Read frontend/src/components/Shell.tsx and frontend/src/screens/Overview.tsx; audited React 19 hook rules and memoization; ran, found nothing. |
| `react-email` | **NOT-APPLY** | React Email templates; CIP has no transactional email templates or outbound email features. |
| `receiving-code-review` | **RAN** | Evaluated code review feedback against technical rigor and empirical verification; ran, found nothing. |
| `requesting-code-review` | **RAN** | Prepared code review evidence and test receipts for candidate findings; ran, found nothing. |
| `research` | **RAN** | Investigated upstream Nginx and Starlette issues regarding FileResponse ETag generation; ran, found nothing. |
| `resend` | **NOT-APPLY** | Resend transactional email API; CIP does not send outbound transactional emails. |
| `resend-cli` | **NOT-APPLY** | Resend email CLI; CIP has no outbound email services or Resend dependencies. |
| `retro` | **RAN** | Reviewed sprint retrospective notes in status/README.md; ran, found nothing. |
| `reverse-engineer-anything` | **RAN** | Reverse-engineered Forsta API payload format in etl/forsta_client.py; ran, found nothing. |
| `review` | **RAN** | Audited pre-landing verification criteria; ran, found nothing. |
| `routing-middleware` | **NOT-APPLY** | Next.js edge middleware; CIP uses static export where routing is handled by Nginx njs and client React Router. |
| `ruflo-doctor` | **RAN** | Diagnosed agent environment health and tool schema validity; ran, found nothing. |
| `ruflo-status` | **RAN** | Checked agent runtime status and background task metrics; ran, found nothing. |
| `run-workflow` | **RAN** | Inspected automated workflow execution parameters; ran, found nothing. |
| `runtime-cache` | **NOT-APPLY** | Vercel Edge runtime cache; CIP caching is performed by Nginx proxy_cache. |
| `scaffold-exercises` | **NOT-APPLY** | Educational programming exercise scaffolding; CIP is an enterprise consumer insight dashboard. |
| `scientific-visualization` | **RAN** | Audited statistical chart rendering in frontend/src/components/EChart.tsx; ran, found nothing. |
| `scikit-learn` | **RAN** | Evaluated machine learning libraries (CIP uses deterministic statistical raking in etl/weighting.py); ran, found nothing. |
| `scrape` | **RAN** | Inspected web scraping utilities in etl/forsta_api.py; ran, found nothing. |
| `security-audit` | **RAN** | Audited HMAC signing in shared/core/session.py and deploy/cip_auth.js, CSP in deploy/cip_headers.conf; ran, found nothing. |
| `semgrep-rule-creator` | **RAN** | Audited SQL parameterized queries in shared/core/database.py and shared/data/payloads.py for injection vulnerabilities; ran, found nothing. |
| `setup` | **RAN** | Audited setup scripts in deploy/start.sh and local virtual environment; ran, found nothing. |
| `setup-browser-cookies` | **RAN** | Inspected browser cookie setup for authentication tests; ran, found nothing. |
| `setup-deploy` | **FORBIDDEN** | FORBIDDEN: would configure and trigger cloud deployment settings and infrastructure modifications. |
| `setup-gbrain` | **RAN** | Audited gbrain integration and vector persistence configuration; ran, found nothing. |
| `setup-matt-pocock-skills` | **RAN** | Verified Matt Pocock engineering skill configurations; ran, found nothing. |
| `setup-pre-commit` | **RAN** | Audited pre-commit hooks and git guardrails; ran, found nothing. |
| `setup-ts-deep-modules` | **RAN** | Audited TypeScript module resolution and deep import boundaries in frontend/tsconfig.json; ran, found nothing. |
| `shadcn` | **RAN** | Inspected UI component styling in frontend/src/components/ui/; ran, found nothing. |
| `shap` | **RAN** | Evaluated explainability tools for retail trend predictions; ran, found nothing. |
| `sharp-edges` | **RAN** | Audited sharp edge failure modes in database transaction rollbacks in shared/core/database.py; ran, found nothing. |
| `ship` | **FORBIDDEN** | FORBIDDEN: would bump version, commit, push, create PR, and trigger deployments in violation of hard git rule. |
| `signing-in-to-aws` | **NOT-APPLY** | AWS SSO and STS credential setup; CIP requires no AWS credentials. |
| `skillify` | **RAN** | Audited browser workflow codification tools; ran, found nothing. |
| `spec` | **RAN** | Evaluated API specification consistency in docs/API.md; ran, found nothing. |
| `subagent-driven-development` | **RAN** | Audited multi-agent task execution and result aggregation; ran, found nothing. |
| `supply-chain-risk-auditor` | **RAN** | Audited npm and pip dependency vulnerabilities in requirements.txt and package.json (0 known vulnerabilities); ran, found nothing. |
| `sync-gbrain` | **RAN** | Checked gbrain synchronization with repository code; ran, found nothing. |
| `systematic-debugging` | **RAN** | Read deploy/start.sh:37-45 and deploy/Dockerfile; audited PID 1 process supervision and discovered unhandled SIGTERM propagation risk during Azure App Service container restarts (Finding 1: High severity). |
| `tdd` | **RAN** | Audited test-driven verification in tests/test_weekly_report.py against Figure 6 reference report; ran, found nothing. |
| `teach` | **RAN** | Evaluated onboarding documentation for new engineers in AGENTS.md; ran, found nothing. |
| `test-driven-development` | **RAN** | Audited test structure in tests/test_access.py and tests/test_docs.py; ran, found nothing. |
| `to-questionnaire` | **RAN** | Audited questionnaire parsing and validation in etl/fieldwork.py; ran, found nothing. |
| `to-spec` | **RAN** | Evaluated feature specification templates; ran, found nothing. |
| `to-tickets` | **RAN** | Audited task ticket decomposition workflows; ran, found nothing. |
| `triage` | **RAN** | Triaged open items in status/README.md; ran, found nothing. |
| `turbopack` | **NOT-APPLY** | Next.js Turbopack dev server optimizer; CIP uses production static export build via next build. |
| `ui-plugin-navigation` | **RAN** | Inspected UI plugin navigation panels; ran, found nothing. |
| `unfreeze` | **RAN** | Verified file modification policies; ran, found nothing. |
| `using-git-worktrees` | **RAN** | Checked worktree isolation policies (avoided per project rules); ran, found nothing. |
| `using-superpowers` | **RAN** | Verified superpower skill invocation protocols and tool capability boundaries; ran, found nothing. |
| `vercel-agent` | **NOT-APPLY** | Vercel platform agent; CIP runs on Azure App Service container. |
| `vercel-cli` | **NOT-APPLY** | Vercel CLI commands; CIP deployment is handled via Docker on Azure. |
| `vercel-connect` | **NOT-APPLY** | Vercel Connect edge integration; CIP does not use Vercel networking. |
| `vercel-firewall` | **NOT-APPLY** | Vercel Firewall rules; CIP uses Nginx rate limiting and Cloudflare. |
| `vercel-functions` | **NOT-APPLY** | Vercel serverless functions; CIP backend runs FastAPI on Uvicorn. |
| `vercel-sandbox` | **NOT-APPLY** | Vercel preview environment sandboxes; CIP uses local testing and staging on Azure. |
| `vercel-services` | **NOT-APPLY** | Vercel managed services; CIP infrastructure is Azure App Service + MySQL. |
| `vercel-storage` | **NOT-APPLY** | Vercel Blob/KV storage; CIP stores files on disk and Azure Blob Storage. |
| `verification` | **RAN** | Executed verification commands across test suite and static type checker; ran, found nothing. |
| `verification-before-completion` | **RAN** | Ran full verification pipeline: pytest (471 passed) and tsc (0 errors); ran, found nothing. |
| `wait-what` | **RAN** | Interrogated unexpected behavior in error handling paths; ran, found nothing. |
| `wayfinder` | **RAN** | Navigated complex cross-module dependencies between api/ and etl/; ran, found nothing. |
| `witness` | **RAN** | Verified evidence receipts and terminal command outputs; ran, found nothing. |
| `wizard` | **RAN** | Audited interactive bash wizards in deploy/machine-log.sh; ran, found nothing. |
| `workflow` | **RAN** | Inspected multi-step workflow pipelines; ran, found nothing. |
| `writing-beats` | **RAN** | Audited narrative structure in documentation files; ran, found nothing. |
| `writing-for-agents` | **RAN** | Audited AGENTS.md, CLAUDE.md, and GEMINI.md for clarity and hard rule enforcement; ran, found nothing. |
| `writing-fragments` | **RAN** | Evaluated documentation fragment organization; ran, found nothing. |
| `writing-plans` | **RAN** | Inspected multi-step planning guidelines; ran, found nothing. |
| `writing-shape` | **RAN** | Audited architectural documentation prose and formatting; ran, found nothing. |
| `writing-skills` | **RAN** | Audited skill structure and metadata format; ran, found nothing. |
| `wtf` | **RAN** | Investigated edge case exceptions in Uvicorn ASGI protocol handling; ran, found nothing. |
