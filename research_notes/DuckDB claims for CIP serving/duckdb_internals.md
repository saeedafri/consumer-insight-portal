# DuckDB internals: checking the claims behind the CIP serving recommendation (as of 22 Oct 2026)

Version context: DuckDB **2.0.0 (LTS, "Cinnamon Teal") released 2026-10-21**. Latest 1.5.x is 1.5.6 (2026-09-28, non-LTS) and latest 1.4.x LTS is 1.4.5 (2026-06-17) — [Release calendar](https://duckdb.org/release_calendar). `duckdb.org/docs/stable/...` now redirects to `/docs/2.0/`. The report being checked (`docs/research/columnar_cube_architecture.md`) says it benchmarked "DuckDB 2.0.0", which came out one day before these notes. So it ran either on the release itself or on a 2.0 alpha/main build ([2.0 alpha post, 2 Sep 2026](https://duckdb.org/2026/09/02/try-duckdb-20-alpha)).

## Claim 1: vectorized execution with STANDARD_VECTOR_SIZE = 2048

### Takeaway
**True.** It is a compile-time constant (`DEFAULT_STANDARD_VECTOR_SIZE 2048U`) that can be overridden at build time. It has not changed through 2.0.

### Cited Findings
- `vector_size.hpp` on main (2.0-era) defines `#define DEFAULT_STANDARD_VECTOR_SIZE 2048U` and `#ifndef STANDARD_VECTOR_SIZE #define STANDARD_VECTOR_SIZE DEFAULT_STANDARD_VECTOR_SIZE`, and requires a power of two — [vector_size.hpp](https://github.com/duckdb/duckdb/blob/main/src/include/duckdb/common/vector_size.hpp)
- The default row group is 122,880 rows (`DEFAULT_ROW_GROUP_SIZE 122880ULL`, which is 60 × 2048). There is a static check that the row group size is a multiple of STANDARD_VECTOR_SIZE. The default block allocation is 256 KiB — [storage_info.hpp](https://github.com/duckdb/duckdb/blob/main/src/include/duckdb/storage/storage_info.hpp)
- Parallelism is per row group. To use k threads, a query "needs to scan at least k * 122,880 rows" — [How to tune workloads (2.0 docs)](https://duckdb.org/docs/2.0/guides/performance/how_to_tune_workloads.html)

### Inferences
- The report's advice to set `row_group_size = 500,000` (its lines 186-187, 431) is Parquet-writer guidance. A native `.duckdb` file uses 122,880 rows per group by default, settable per file with `ATTACH ... (ROW_GROUP_SIZE n)` ([storage docs](https://duckdb.org/docs/2.0/internals/storage.html)). For 10.4M rows that gives about 85 row groups, which is plenty for parallelism.

### Gaps
- None material.

## Claim 2: lightweight compression (Dictionary, Bitpacking, Chimp/Patas for float survey weights)

### Takeaway
**Outdated.** Chimp and Patas were replaced by **ALP** (and its ALPRD fallback for "real doubles") in **v0.10.0 (Feb 2024)**. In current source they are hard-flagged "deprecated / phased out" and are never chosen for new writes. Plain **Dictionary** (and standalone FSST) are also deprecated for storage versions newer than v1.2.0. **DICT_FSST** (added in storage v1.3.0) replaces them and is **enabled by default in 2.0**. Bitpacking (and RLE, FOR, Constant) is still in use.

### Cited Findings
- v0.10.0 release post: ALP "replaces Chimp and Patas". It is "x2-4 times faster than Patas (at decompression)", and DuckDB "automatically decide[s] during checkpointing whether using ALP is beneficial" — [Announcing DuckDB 0.10.0 (13 Feb 2024)](https://duckdb.org/2024/02/13/announcing-duckdb-0100.html)
- In `CompressionTypeIsAvailable`, `COMPRESSION_PATAS` and `COMPRESSION_CHIMP` have their max storage version capped at `V0_10_2` and return `Deprecated()` unconditionally ("phased out"). `COMPRESSION_DICTIONARY` and `COMPRESSION_FSST` count as deprecated when the storage version is newer than `V1_2_0`. `DICT_FSST` requires at least `V1_3_0`. `ROARING` and `ZSTD` require at least `V1_2_0` — [compression_type.cpp](https://github.com/duckdb/duckdb/blob/main/src/common/enums/compression_type.cpp)
- The 2.0 storage docs still *list* Constant, RLE, Bit Packing, FOR, Dictionary, FSST, ALP, Chimp, Patas and Zstd, and note that "available compression algorithms depend on the storage version used" — [Storage internals (2.0)](https://duckdb.org/docs/2.0/internals/storage.html). The list is about read compatibility, not what gets written today.
- 2.0 makes storage format v2.0.0 the default (older DuckDB versions cannot read it) and enables `DICT_FSST` by default (#23733) — [DuckDB 2.0 preview](https://duckdb.org/2026/08/17/duckdb-20-highlights); [Storage internals (2.0)](https://duckdb.org/docs/2.0/internals/storage.html)
- ALP paper: Afroozeh, Kuffó, Boncz, SIGMOD 2024. The ALP repo says its "effectiveness and speed led to deprecating Chimp128 and Patas in DuckDB" — [cwida/ALP](https://github.com/cwida/ALP); [ALP in the DuckDB library](https://duckdb.org/library/alp/)
- In-memory (`:memory:`) databases are **not compressed by default**. Only persistent files are. TPC-H Q1 SF30: 4.22 s uncompressed in-memory vs about 0.55 s compressed — [How to tune workloads (2.0)](https://duckdb.org/docs/2.0/guides/performance/how_to_tune_workloads.html)

### Inferences
- Correct wording: "Survey weights (DOUBLE) are compressed with ALP/ALPRD. Categorical codes use bitpacking/RLE/FOR/constant. Strings use DICT_FSST." Citing Chimp/Patas signals pre-2024 knowledge.
- If the portal loads data into an in-memory DuckDB, none of the compression claims apply unless compression is turned on explicitly.

### Gaps
- I could not pin the exact PR/commit that first stopped *writing* Chimp/Patas. The 0.10.0 post and the `V0_10_2` cap are the best anchors.

## Claim 3: own buffer manager, deliberately avoids OS mmap, citing Crotty/Leis/Pavlo (CIDR 2022)

### Takeaway
**Paper real. DuckDB link unsourced. "Avoids mmap" was true up to 1.5.x and is outdated for 2.0.** The paper exists and argues against mmap as a replacement for a buffer pool. DuckDB has its own buffer manager and historically read with `pread`/`pwrite`. **I found no DuckDB document that cites the paper or describes the design as a deliberate rejection of mmap.** **DuckDB 2.0 adds an opt-in `IO_MODE 'MMAP'`.** The default remains buffered I/O.

### Cited Findings
- Paper: Andrew Crotty (CMU), Viktor Leis (FAU Erlangen-Nürnberg), Andrew Pavlo (CMU), "Are You Sure You Want to Use MMAP in Your Database Management System?", CIDR 2022, 9-12 Jan 2022. Abstract: there are "severe correctness and performance issues with mmap". The authors conclude that mmap "is not a suitable replacement for a traditional buffer pool" and "strongly urge DBMS developers to avoid using mmap". Section 6 gives guidance on when it *might* be acceptable — [CIDR 2022 PDF](https://www.cidrdb.org/cidr2022/papers/p13-crotty.pdf); [abstract page](https://vldb.org/cidrdb/2022/are-you-sure-you-want-to-use-mmap-in-your-database-management-system.html)
- DuckDB's buffer manager "is responsible for caching pages from DuckDB's own persistent storage" and "abides by the same memory limit as any intermediate data structures". That blog post does not mention mmap and does not cite the paper — [Memory Management in DuckDB (9 Jul 2024)](https://duckdb.org/2024/07/09/memory-management.html)
- Source: `LocalFileSystem` reads with `pread(...)` and writes with `pwrite(...)`. `local_file_system.cpp` at tag **v1.5.0 has no `mmap(` call**. At tag **v2.0.0** there is a new `MemoryMapFile` / `UnixMemoryMappedFile` path that calls `mmap(..., MAP_SHARED, ...)` — [local_file_system.cpp @v2.0.0](https://github.com/duckdb/duckdb/blob/v2.0.0/src/common/local_file_system.cpp) (checked by grepping the raw files at both tags)
- PR #22988 (merged 2 Jun 2026) adds the `IO_MODE` attach option. The modes are `BUFFERED_IO` (the default, and previously the only mode), `MMAP` (OS page cache does the caching) and `DIRECT_IO`. Usage: `ATTACH 'f.db' (IO_MODE 'MMAP')`. There is also a `default_io_mode` setting. MMAP does not work with encrypted files, and writes reserve address space (default max(256GB, 2 × file size), override with `MMAP_RESERVE_SIZE`) — [PR #22988](https://github.com/duckdb/duckdb/pull/22988)
- The 2.0 preview lists "MMAP and DIRECT_IO modes" and says local storage "benefits a little", with network storage seeing "the big gains" — [DuckDB 2.0 preview](https://duckdb.org/2026/08/17/duckdb-20-highlights)
- A third-party blog groups DuckDB with systems that manage their own pages. That is secondary and not from DuckDB — [mohakchugh blog](https://mohakchugh.is-a.dev/blog/mmap-considered-harmful-database-buffer-management)

### Inferences
- Defensible wording: "DuckDB manages its own buffer pool, with pages cached under `memory_limit` and default buffered I/O. That matches the guidance in Crotty et al. (CIDR 2022)." Stating that DuckDB cites the paper, or that 2.0 never uses mmap, is not supported.
- The report's own SQLite advice (line ~440, using SQLite's mmap to eliminate `read()` syscalls) sits awkwardly next to citing an anti-mmap paper.

### Gaps
- No DuckDB statement of design rationale for avoiding mmap was found. I did not check whether the 2.0 MMAP mode bypasses or sits under the buffer manager; the PR page does not say.

## Claim 4: ART index on (survey_id, qcode) for sub-ms point lookups, and zonemaps pruning row groups

### Takeaway
**Zonemap part true. ART part largely false as written.** The 2.0 docs say only **single-column, expression-free** ART indexes are eligible for index scans. A composite `(survey_id, qcode)` index enforces constraints but **is not used for lookups**. ART buffers are **not evicted** under memory pressure and count against memory, and writes get slower. DuckDB's own advice is to avoid explicit indexes unless queries are highly selective and memory is ample. Sorting on filter columns **does** improve zonemap pruning and is the recommended approach.

### Cited Findings (all from [Indexing guide, 2.0 docs](https://duckdb.org/docs/2.0/guides/performance/indexing.html) unless noted)
- "DuckDB automatically creates zonemaps (also known as min-max indexes) for the columns of all general-purpose data types". DuckDB "can skip any row group whose min-max range does not contain that filter value."
- "The more ordered the data within a column, the more valuable the zonemap indexes will be". "If you query specific columns with selective filters, it is best to pre-order data by those columns when inserting it". "Even an imperfect ordering will still be helpful."
- ART is created implicitly for PRIMARY KEY, FOREIGN KEY and UNIQUE, and explicitly by `CREATE INDEX`.
- "DuckDB will try to use an index scan for equality and IN(...) conditions". Default threshold: "MAX(2048, 0.001 * table_cardinality)" rows. For 10.4M rows that is about 10,400 rows.
- "**Indexes are only eligible for index scans if they index a single column without expressions.**"
- "An ART index does not affect the performance of join, aggregation, and sorting queries". "Changes on indexed tables perform worse".
- "DuckDB does not yet destroy any index buffers if it has to evict memory", so "indexes can take up a significant portion of DuckDB's available memory". Advice: "Do not define explicit indexes unless you have highly selective queries and enough memory available", and create them after bulk load.
- Roadmap: ART indexes become buffer-managed (evictable) "later this year" (#21458, #23605), and 2.0 checkpoint vacuuming can remap ART row IDs (#23653) — [DuckDB 2.0 preview](https://duckdb.org/2026/08/17/duckdb-20-highlights)

### Inferences
- The report's line 156 ("ART indexes ... loaded lazily ... point filtering down to the exact row-group offsets") and lines 397-402 (`CREATE INDEX ... (survey_id, qcode)`) conflict with the docs. A composite index will not be chosen for scans. Even a single-column index on `survey_id` only helps when one wave matches ≤ about 10.4k rows. With about 40k rows per wave (10.4M / 260), it would not qualify.
- The sub-ms 2-cut latency is better explained by zonemap pruning on data that is physically sorted by `(survey_id, qcode)`. The recommendation should be "ORDER BY survey_id, qcode on load, no explicit index". That also saves memory on the 1-core, 4.5 GB staging box.

### Gaps
- No DuckDB-published per-key ART memory figure was found.

## Claim 5: `SET max_memory = '2GB'` bounds DuckDB memory

### Takeaway
**The name is right; "bounds all memory" is false.** `max_memory` and `memory_limit` are aliases (default 80% of RAM). The docs state the limit applies to the buffer manager only. Other allocations can exceed it, and on top of that comes the Python process (FastAPI, pandas/Arrow result sets).

### Cited Findings
- Config table row: "`max_memory`, `memory_limit` | The maximum memory of the system (e.g., 1GB). | VARCHAR | 80% of RAM" — [Configuration overview (2.0)](https://duckdb.org/docs/2.0/configuration/overview.html)
- Limits page: memory use defaults to 80% of RAM via `memory_limit`, and "This limit only applies to the buffer manager" — [Limits (2.0)](https://duckdb.org/docs/2.0/operations_manual/limits.html)
- The buffer manager and intermediates share the limit. Intermediates spill to `temp_directory` past the limit, and when spilling is impossible an out-of-memory error is raised — [Memory Management in DuckDB](https://duckdb.org/2024/07/09/memory-management.html)
- Related 2.0 settings: `operator_memory_limit` (per-connection cap on intermediates, default NULL) and `block_allocator_memory` ("allocated once, never freed") — [Configuration overview (2.0)](https://duckdb.org/docs/2.0/configuration/overview.html). 2.0 also adds spilling for aggregations (#24499) — [2.0 preview](https://duckdb.org/2026/08/17/duckdb-20-highlights)
- `threads` is an alias of `worker_threads` (default = number of CPU cores). Too many threads, for example from hyperthreading, can slow queries down — [Configuration overview](https://duckdb.org/docs/2.0/configuration/overview.html); [Tune workloads](https://duckdb.org/docs/2.0/guides/performance/how_to_tune_workloads.html)
- Non-evictable ART buffers (claim 4) count toward the buffer manager's memory but cannot be freed.

### Inferences
- Size the container on process RSS, not on `memory_limit`. Set `memory_limit` well below the container limit, and also set `temp_directory` and `threads=1` on the 1-core servers.

### Gaps
- No exhaustive DuckDB list of allocations outside the limit was found.

## Claim 6: 10.4M-row aggregate in 15-28 ms, 2-cut P95 0.69 ms, ~2,085 QPS at 8 threads / 142 MB RSS

### Takeaway
**Plausible as warm, in-process, laptop micro-benchmark numbers; not evidence for production.** Per the report's own setup section, the numbers come from an Apple M-series machine with 4 cores and 16 GB, DuckDB 2.0.0, 30 warm iterations, and a dataset "matching the schema and distribution" of CIP waves, so it appears synthetic. The QPS figure is 160 queries finished in 0.077 s. The production and staging servers have **1 core** each.

### Cited Findings
- The report's setup lists the hardware, the DuckDB 2.0.0 stack, cold vs 30 warm runs, and the 10.4M rows across 260 waves. The concurrency figure is "8 Threads, 160 Requests": 2,085.7 QPS, 0.077 s total, 142.8 MB peak RSS, shared read-only connection with per-thread cursors — `docs/research/columnar_cube_architecture.md` §4.1, §4.5 (lines 242-248, 360-366)
- The DuckDB-native file is 115.8 MB for 10.4M rows, so the whole working set fits in the buffer pool after the first query — same file, lines 20 and 274
- DuckDB keeps cached data and metadata in memory only while a connection is open, so it recommends reusing one connection — [Tune workloads (2.0)](https://duckdb.org/docs/2.0/guides/performance/how_to_tune_workloads.html)
- k-way parallelism needs at least k × 122,880 rows scanned. A 2-cut crosstab on one wave (~40k rows) runs on a single thread anyway — [Tune workloads (2.0)](https://duckdb.org/docs/2.0/guides/performance/how_to_tune_workloads.html)
- The repo's own end-to-end FastAPI stress run (`scripts/stress_benchmark_results.json`) shows crosstab p50 0.78 ms but **p95 13.7 ms** at about 811 RPS in phase 1, with RSS about 115 MB. Phase 2 bursts run at about 2,937 RPS with a p50 of 13 ms. So HTTP-level tail latency is about 20× the engine-only 0.69 ms P95.

### Inferences
- 10.4M rows in 28 ms is about 370M rows/s, which is reasonable for a warm, multi-core vectorized scan of a few compressed integer columns. On **1 core** expect roughly 3-4× slower, so around 100 ms. That is still inside the 350 ms SLA, but the "12× to 500× headroom" claim shrinks.
- 2,085 QPS from 160 queries over 77 ms is too small a sample (no steady state, no GC or OS noise). Also, 8 worker threads on a 1-core host would mostly add contention. Re-run on the 1-core VM with `threads=1`, for at least 60 s, measuring at the HTTP layer.
- The 142 MB RSS fits a 116 MB file fully cached plus a small Python process. Real CIP data with more columns or string answers will be larger.
- Cold-start latency (first query after process start or connection reopen) is reported for SQLite (1,446 ms) but should also be stated for DuckDB.

### Gaps
- I did not find an official DuckDB benchmark at this exact shape (10M rows, 1 core). ClickBench and the H2O db-benchmark use different hardware and data, so they were not used as direct comparators.
- I could not verify that the benchmark data is synthetic; the report does not say "synthetic" explicitly.
