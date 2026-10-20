# 06. Infrastructure, cost and migration

[Package index](README.md) | [Source register](08-sources.md)

## 1. Use the supplied limits, not the old report's assumptions

The current brief gives approximately **4.5 GB for staging** and **9.88 GB for production**, with the same configuration mentioned for CIQ, MIP and MDB. Previous documents in the archive discuss different RAM figures and App Service SKUs. Those older assumptions are not adopted.

RAM does not identify vCPU count, disk throughput, host type, available CPU credits, database capacity or an Azure price. Confirm whether these numbers mean provisioned RAM, a container limit or currently free memory, and whether they are GB or GiB. This report preserves the brief's approximate GB convention for planning.

## 2. Hosting scenarios

| Actual arrangement | Consequence |
|---|---|
| One VM shared by CIP, CIQ, MIP and MDB | One total CPU/RAM envelope; worker peaks, backups and deployments compete with every app |
| Multiple apps on one App Service plan | App separation is not dedicated compute; count all apps and deployment slots against the plan |
| Separate VM/plan per product with identical sizing | Each product has its own allocation and corresponding infrastructure cost |
| MySQL also on the application host | Database buffers, connections, storage and backup work must be added; the sample allocation below is invalid until recalculated |
| Staging and production share physical capacity | Testing can affect live work; isolate or strictly control qualification tests |

Microsoft documents resource sharing among apps and slots within an App Service plan. The word "server" in the brief is not enough to establish which scenario applies. [S29](08-sources.md#s29).

## 3. Illustrative shared-host memory allocation

**These are budgeting placeholders, not observed RSS, proven minimums or deployed limits.** The purpose is to expose contention before purchasing or configuring anything. This table assumes MySQL and object storage are external to the application host.

| Allocation bucket | Staging GB | Production GB |
|---|---:|---:|
| Host/runtime, proxy, telemetry and operational overhead | 0.65 | 1.00 |
| CIP API processes, excluding the separately budgeted response cache | 0.60 | 1.20 |
| CIP bounded response cache, total across processes | 0.15 | 0.40 |
| One bounded CIP job worker | 0.65 | 1.40 |
| Provisional combined reserve for CIQ, MIP and MDB | 1.35 | 3.60 |
| Unallocated headroom for peaks and deployment | 1.10 | 2.28 |
| **Total** | **4.50** | **9.88** |

There is no evidence that the three sibling products fit their provisional reserve or that the current full-wave ETL fits the proposed worker bucket. The synthetic experiment alone demonstrates how quickly a dataframe path can exceed 1 GiB process RSS. Measure actual worker peaks before setting a limit; chunk, reschedule or externalize jobs when necessary.

If the siblings already consume the available memory, adding a new framework cannot create safe capacity. A smaller cache, one API worker and scheduled ETL may help, but host isolation or an increased allocation may be the honest requirement.

Start staging with one API process. Production might use one or two, **only if measured CPU and memory support it**. More workers can improve parallelism while duplicating code, imports, caches and connection pools. FastAPI's deployment guidance explicitly warns that worker processes generally do not share memory. [S09](08-sources.md#s09).

## 4. Connection and concurrency budgets

Start from the database's safe connection/query budget and allocate it across all products. A proposed per-API-process read pool might be five connections with zero to two overflow connections; this is a test configuration, not an optimal universal setting.

For illustration:

```text
4 products x 2 API processes x (5 pool + 2 overflow)
= 56 potential research-read connections

Application-state pools, ETL connections, admin sessions and deployment overlap
must be added separately.
```

By contrast, the archive's 10 + 20 default permits 30 connections per engine/process. Four products with two processes each could therefore allow 240 connections for one role if all used that configuration. These are maximum-potential calculations, not observed open connections. SQLAlchemy pool documentation explains allocation and overflow behavior. [S24](08-sources.md#s24).

Admission limits matter more than a large pool. Prefer a bounded wait with a useful error/job response over allowing hundreds of expensive queries to compete. A user session should not permanently reserve a database connection.

## 5. What actually lowers long-run cost

The strongest mechanisms are reuse of existing research logic, shared tested UI/auth contracts across products, less data copied per request, fewer redundant queries, reusable product configuration, reduced incident/rework burden and deferred infrastructure upgrades.

**A faster application does not automatically lower the current Azure bill.** When a fixed host remains provisioned, efficiency usually creates headroom rather than a direct monthly saving. Savings require a real pricing change, such as a smaller plan, fewer instances, less paid capacity, lower metered consumption or avoiding an otherwise necessary upgrade.

Likewise, open-source frameworks are not a free operating model. Engineering, security maintenance, on-call work, backups, identity services, database hosting, storage, observability and third-party components still cost money. Compare custom engineering against applicable vendor quotes, not against a vendor's cheapest unrelated internal-user tier.

## 6. Three-year cost model

Use the same scope and service level for every alternative:

```text
36-month TCO = initial design/build/migration cost
             + 36 x (hosting + database + storage + identity + monitoring
                     + software licenses + maintenance/support)
             + expected incident/recovery cost
             + exit/migration cost
```

Separate the cost already spent on ETL from the incremental cost of retaining or replacing it. Include frontend capability-building when comparing FastAPI/React with an optimized existing Streamlit implementation. Include the additional Python/TypeScript integration burden when comparing a Node API with a Python API.

### Illustrative break-even, not a market quote

Assume a custom product layer costs an additional **400 engineering hours** at an assumed blended **INR 1,500/hour**:

```text
Initial incremental cost = 400 x 1,500 = INR 600,000

If net maintenance/rework savings are 20 hours/month:
Monthly savings = 20 x 1,500 = INR 30,000
Infrastructure savings assumed = INR 0
Break-even = 600,000 / 30,000 = 20 months

If net savings are only 5 hours/month:
Monthly savings = INR 7,500
Break-even = 80 months
```

The hourly rate, effort and savings are hypothetical planning inputs, not observed company costs or national salary benchmarks. The sensitivity is the point: the rewrite is not automatically economical. If it does not improve delivery, adoption, reliability or capacity enough to offset its cost, retaining a simpler solution is rational.

For Azure, calculate using the actual region, service/SKU, operating system, billing arrangement, database, storage, data transfer and monitoring retention. RAM alone is insufficient to quote a monthly bill. Use the official pricing calculator and the existing bill rather than a guessed dollar amount. [S31](08-sources.md#s31).

## 7. Migration gates

| Gate | Work | Evidence required to proceed |
|---|---|---|
| 0. Secure the baseline | Rotate credentials; fix environment validation, sessions, SSO, roles and permissions | Negative authorization tests; secrets absent from build artifacts |
| 1. Make the code testable | Extract pure domain/repository functions; pin dependencies; establish real-MySQL integration tests | Reproducible test run and golden research results |
| 2. Deliver one vertical slice | Overview plus one realistic analysis journey in optimized Streamlit and web/API | Same results, matched functionality, actual Azure/network measurements |
| 3. Establish publication/jobs | Immutable data versions, bounded exports, leases/retries and rollback | Failed ETL retains last good version; crash/retry and ownership tests pass |
| 4. Complete subscriber workflow | Catalog, entitlements, saved views, trends, publications and approved previews | End-to-end tests across commercial plans and tenant scopes |
| 5. Qualify operations | Load/soak, restore, upgrade/rollback and telemetry | Measured operating envelope with headroom and recovery evidence |
| 6. Expand selectively | Reuse proven contracts/components for other products | Per-product cost/benefit and regression review; no forced big-bang migration |

These are dependency gates, not delivery-date promises. A failure at gate 2 can justify staying with Streamlit longer, choosing Fastify, or changing the resource constraint. The entire SIP/MIP interface should not be rewritten before the CIP slice proves useful.

## 8. When to add infrastructure

| Observed constraint | First response | Later escalation |
|---|---|---|
| Slow SQL / large scanned rows | Index/query/aggregate redesign; correct result bounds | Separate analytics serving engine only with measured need |
| Worker peak affects UI | Chunk work, one heavy job at a time, scheduling | Isolate the worker onto separate compute |
| Duplicate cache/query work across processes | Versioned keys and request coalescing | Shared cache after measuring its benefit and footprint |
| API CPU dominates after query optimization | Profile serialization and handlers | Compare additional compute or a focused Go/.NET/Node service |
| Single-host availability unacceptable | Define outage/recovery requirement | Redundant API instances and appropriate database/storage HA |
| Shared products exhaust host | Enforce budgets and identify the largest workload | Split plans/hosts rather than hide contention with bigger pools |

Do not install Kubernetes merely because the word scalable is in the brief. The first scale improvement is often workload isolation or a second suitable instance, not a new orchestration platform.

## 9. Commercial success measures

Track time to first useful insight, successful search-to-analysis conversion, repeat use, saved-view reuse, successful exports, trusted publication consumption, support tickets and conversion to genuinely additional product access. These measures test whether the engineering investment serves the business.

A language does not attract subscribers by itself. Reliable relevant data, clear access and fast understandable workflows are the proposed adoption levers; measure them rather than promise growth from the stack.

## 10. Deployment inputs still required

Before committing capacity or a purchase, establish exact host type/SKU/region/vCPU, the meaning of the RAM figures, which products/slots share resources, database placement/version/limits, actual peak process memory, largest survey and export sizes, expected active-user behavior, identity-provider requirements, frontend/backend team capability and recovery objectives.

These are implementation qualification inputs, not reasons to delay the architectural recommendation. The recommended starting architecture remains deliberately small and reversible while they are measured.
