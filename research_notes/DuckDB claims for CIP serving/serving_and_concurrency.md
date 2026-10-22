# Low-latency survey crosstab serving and DuckDB concurrency (as of 22 Oct 2026)

Version context: DuckDB **v2.0.0 was released 21 Oct 2026** (previous: v1.5.6 on 28 Sep 2026) — [GitHub releases API](https://github.com/duckdb/duckdb/releases). `duckdb.org/docs/stable/*` now redirects to `/docs/2.0/`. PyPI `duckdb==2.0.0` manylinux x86_64 wheel = ~24.4 MB (cp311 24,351,483 bytes; cp312-abi3 24,371,005 bytes) — [PyPI](https://pypi.org/project/duckdb/2.0.0/).

"Local measurement" below = run by this researcher on 22 Oct 2026, macOS laptop (Apple, 10 cores, 16 GiB), Python 3.14, duckdb 2.0.0, `threads=1`. Not the target 1-core Linux box, so treat the numbers as indicating the order of magnitude only. Script: synthetic 3M-row table, 4 int/float columns.

## 1. DuckDB concurrency: multiple processes, read-only, threads, file swapping

### Takeaway
Several gunicorn workers can each open the same `.duckdb` file **only if every process opens it `read_only=True`**. A read-write open takes an exclusive file lock and fails while any reader holds the file. Inside one process, a single connection runs one call at a time and **raises** (it does not queue) if another thread calls it, so each FastAPI threadpool thread needs its own `cursor()`. To publish a new file, write it to a new versioned path and reopen. The Python client caches the open database instance per path, so reconnecting to a path that was swapped by rename still serves the **old** data until every connection to it is closed.

### Cited Findings
- Read-only mode: "multiple processes can read from the database, but no processes can write." Read-write mode allows one process to read and write. Multi-threaded writes happen "all within that single writer process" — [DuckDB 2.0 Concurrency](https://duckdb.org/docs/2.0/connect/concurrency.html)
- Within the single process, threads can update separate tables or rows. Optimistic concurrency: "any transactions that modify the same rows at the same time will cause a transaction conflict error". The docs suggest retrying — [DuckDB 2.0 Concurrency](https://duckdb.org/docs/2.0/connect/concurrency.html)
- Multi-process **writes** to the native format are "supported through the Quack remote protocol" (client-server). DuckLake with a PostgreSQL catalog is the other option for concurrent read-write. The page says nothing about replacing files and warns: "Exercise extra caution when accessing a DuckDB database file in a shared directory." — [DuckDB 2.0 Concurrency](https://duckdb.org/docs/2.0/connect/concurrency.html)
- Quack status: the docs call it experimental, with the protocol and function names subject to change, and expected stable in v2.0.0. It is served via `CALL quack_serve(...)` plus a new `CONNECT` statement. `CONNECT` can also push SQL down to MySQL/PostgreSQL — [Quack extension docs](https://duckdb.org/docs/current/core_extensions/quack.html); [DuckDB v2.0 preview blog, 17 Aug 2026](https://duckdb.org/2026/08/17/duckdb-20-highlights); [InfoQ, Aug 2026](https://infoq.com/news/2026/08/duckdb-v2-distributed)
- Python thread safety: "A single connection runs one call at a time: a call from another thread while it is busy raises a `ResourceInUseException` instead of waiting, so give each thread its own cursor." "A cursor has its own transaction and its own session settings, and cursors can run queries at the same time." — [DuckDB 2.0 Python DB API](https://duckdb.org/docs/2.0/clients/python/dbapi.html)
- Multi-threading guide pattern: open one connection, pass it to the workers, and have each worker call `duckdb_con.cursor()` ("Each thread must use the `.cursor()` method to create a thread-local connection") — [DuckDB 2.0 multiple threads guide](https://duckdb.org/docs/2.0/guides/python/multiple_threads.html)
- "Within one Python process, all connections to a database file must use the same configuration, `read_only` included." "Once the last connection to a database instance is closed, the database instance is closed as well." "Closing a connection closes its cursors." — [DuckDB 2.0 Python DB API](https://duckdb.org/docs/2.0/clients/python/dbapi.html)
- **Local measurement (multi-process):** with process A holding the file `read_only=True`, process B also opened it `read_only=True` and queried it. Process C failed to open it read-write with `IOException: Could not set lock on file ...`.
- **Local measurement (file swap):** process A opened `t.duckdb` read-only. A new file was then `os.replace()`d over that path. A's existing handle kept returning the old data (POSIX semantics: the inode stays open). A **fresh `duckdb.connect(same_path, read_only=True)` in the same process also returned the OLD data**, because the instance is reused while any connection is open. Only after closing every connection did a new connect see the new file.
- Third-party guidance (oneuptime.com blog, 8 Sep 2026; secondary source, not authoritative): publish a new versioned file, open it read-only, swap the application's handle, and delete the old file only after it is closed. Never overwrite a file a process has open. Don't copy a live main file without its WAL — [oneuptime: share prebuilt DuckDB files across read-only replicas](https://oneuptime.com/blog/post/2026-09-08-share-prebuilt-duckdb-files-read-only-replicas/view); [oneuptime: single-process write lock](https://oneuptime.com/blog/post/2026-09-08-handle-duckdb-single-process-write-lock/view)
- A gist reports DuckDB failing silently when several Node.js cluster processes share the same read-only DB. This is the Node client, not Python — [bermi gist](https://gist.github.com/bermi)

### Inferences
- A workable pattern for 2 gunicorn workers: the ETL builds `cip_<version>.duckdb` offline in a separate process, then atomically updates a pointer (symlink or a small "current" file). Each worker opens the file `read_only=True` on first request, or when the pointer changes, and keeps one connection per worker with one `cursor()` per thread. Reopen by **new path**, not the same path, to avoid the instance-cache trap. Close the old connection, then delete old files after a grace period.
- The ETL must never open the live file read-write while workers hold it. The lock error would make the ETL fail rather than corrupt data, but it would still break publishing.
- On a 1-core box, DuckDB's parallelism adds nothing. Set `threads=1` per process so 2 workers don't oversubscribe the core.

### Gaps
- No official doc statement on the semantics of renaming a file over one that is open. The findings above come from local POSIX testing only, not tested on Windows or network filesystems.
- Not verified whether `ResourceInUseException` behaviour (raise instead of block) is new in 2.0 or already existed in 1.x. The 2.0 docs state it explicitly.

## 2. DuckDB in Python: memory footprint, cold start, read-heavy serving patterns

### Takeaway
Measured on duckdb 2.0.0: `import duckdb` ≈ 0.6 s and +17 MB RSS. Opening a 3M-row file read-only took 6 ms and +64 MB RSS. After queries, total process RSS was about 99 MB. Grouped aggregations over 3M rows took 12–19 ms single-threaded, and a selective filter took 3 ms. The default `memory_limit` is about 80% of RAM, so on a 4 GB box with 2 workers it must be capped explicitly.

### Cited Findings
- Wheel size about 24 MB (manylinux x86_64, 2.0.0) — [PyPI](https://pypi.org/project/duckdb/2.0.0/)
- **Local measurement:** `import duckdb` 603 ms, +17 MB RSS. `connect(path, read_only=True, threads=1)` 6.1 ms, +64 MB RSS. Query `SELECT a,b,q,SUM(w),COUNT(*) ... WHERE a<10 GROUP BY ALL` on 3M rows: cold 19 ms, warm median 12 ms. `WHERE a=3 AND b=2 GROUP BY q`: 3 ms. RSS after queries: 99 MB.
- **Local measurement:** default `memory_limit` = 12.7 GiB on a 16 GiB machine (≈80%). Default `threads` = core count (10).
- "Aim for 1-4 GB memory per thread". Aggregation-heavy work needs 1–2 GB/thread for ideal performance, joins 3–4 GB. "DuckDB requires a minimum of 125 MB of memory per thread." Limit threads when memory is constrained. DuckDB spills to disk for larger-than-memory work — [DuckDB 2.0 performance: environment](https://duckdb.org/docs/2.0/guides/performance/environment.html)
- v2.0 also brings asynchronous I/O, a new PEG-based parser, a new storage format and a versioned C API — [DuckDB v2.0 preview blog](https://duckdb.org/2026/08/17/duckdb-20-highlights); [InfoWorld](https://infoworld.com/article/4210635/duckdb-2-0-coming-this-fall-with-client-server-mode.html)

### Inferences
- For 2 workers on 4 GB: set `memory_limit` to about 512 MB–1 GB per worker plus `threads=1`. Expect about 80–150 MB RSS per worker at idle with a modest file, on top of the existing FastAPI footprint. That is the order of magnitude seen locally and should be checked on the Linux box.
- Pay the cold start (import ≈0.6 s) at worker boot (gunicorn `--preload` or eager open), not on the first user request. Don't open the connection before fork with `--preload`; open it in each worker after fork, because file handles and locks shouldn't be shared across a fork.
- Read-heavy pattern: one read-only connection per process, a cursor per request or thread, parameterised prepared queries, and an `lru_cache` in front of the hot query shapes.

### Gaps
- No official published figure for the idle memory of the Python package or connection. The numbers above are local and macOS-only (macOS RSS accounting differs from Linux).
- Not measured on a 1-vCPU Azure VM. Latencies there will likely be higher than on an Apple laptop core.

## 3. Low-latency crosstab serving practice: precompute vs on-the-fly, weighting, suppression, significance, caching

### Takeaway
Commercial survey platforms that advertise sub-second ad-hoc crosstabs (Crunch.io) do it by aggregating **on the fly over a respondent-level columnar store** built for survey data. Desktop and report tools (Q/Displayr, WinCross, Alida, Datatile) compute weighting, effective base and minimum-base suppression at table time. None of the vendors documents their caching internals publicly.

### Cited Findings
- Crunch.io markets "subsecond query response" on datasets "with millions of respondents and thousands of variables", "powered by the Crunch columnar database built for survey data" (vendor claim, no published benchmark) — [Crunch: enterprise scalable](https://crunch.io/product/enterprise-scalable)
- YouGov Profiles on Crunch: 192,000 respondents × 48,000 variables, with sub-second "on-the-fly" crosstabs for over 14,000 users (Greenbook case study, 26 Sep 2020). A later Crunch case study cites 309,000 rows × 300,000 columns. The figures differ by date — [Greenbook case study](https://greenbook.org/case-study/subsecond-response-times-for-one-of-the-world-s-largest-research-networks); [Crunch YouGov case study](https://crunch.io/case-studies/yougov)
- Crunch also offers an asynchronous batch Tabulation API, output as long-form CSV with one row per cell (heavy tabs run as background jobs, not inline) — [Crunch Tabulation API](https://help.crunch.io/hc/en-us/articles/43108717800461-Tabulation-API)
- Q (Displayr's sibling product) treats weights as sampling weights by default. Results don't change with the average weight ("the same significance testing results are obtained whether the average weight is 1.0 or 1,000,000"). Q uses Taylor series linearization for tests of means and proportions on tables, and the Kish effective sample size otherwise. Design effect = actual n / effective n. Q4.10+ allows an "Extra deff" — [Q wiki: Weights, Effective Sample Size and Design Effects](https://wiki.q-researchsoftware.com/wiki/Weights,_Effective_Sample_Size_and_Design_Effects)
- WinCross: optional minimum base for a column to qualify for significance testing, default 30 when enabled — [WinCross help](https://www.analyticalgroup.com/WinCrossExecutiveHelp1/Desktop/Edit_Crosstab.htm)
- Alida: the minimum sample size applies per banner column. Below it, the test is not run and the cell shows "N/A" — [Alida significance testing](https://insightcommunity.help.alida.com/enus/adhoc/reports_modern/significance_testing/significance_testing_apply_modern.html)
- Datatile: options for "Use weighted base when calculating significance" and excluding low-base values from significance — [Datatile](https://support.datatile.eu/en/articles/6798133-significance-in-crosstab)
- Q weight-per-column: a separate weighted table is built and its significance results are copied into the original table — [Q help: crosstab with weights for each time period](https://help.qresearchsoftware.com/hc/en-us/articles/8484535277711-How-to-Generate-a-Crosstab-With-Weights-for-Each-Time-Period)

### Inferences
- CIP's current design publishes count tables and computes two-cut crosstabs in memory in about 1 ms. That is a precomputed-aggregate design, and for the fixed set of cuts it is already faster than any on-the-fly engine (DuckDB took 3–19 ms locally on 3M rows). On-the-fly columnar only wins when cuts can't be enumerated in advance.
- To weight correctly from count tables, publish Σw and Σw² (or the effective n) per cell alongside the raw counts. Kish n_eff = (Σw)²/Σw² can then be computed server-side without respondent data. Taylor linearization needs respondent-level data.
- Server-side minimum-base suppression (n<30 is a common default) and significance must use the **unweighted or effective** base, never the weighted sum.

### Gaps
- Found no public engineering write-up from Displayr, Forsta (Dapresy) or Crunch describing cache layers or measured latencies. Only marketing claims.
- Displayr's own default minimum base was not found in its docs.

## 4. When respondent-level ad-hoc filtering justifies DuckDB/Parquet vs MySQL

### Takeaway
Use an embedded columnar engine once users can build **arbitrary audiences** (many AND/OR conditions across demographics and answers) that can't be precomputed. Columnar scans over a few million rows answer in milliseconds locally. A row store doing the same aggregations is published as 100×+ slower at scale, and CIP's MySQL also adds about 250 ms per round trip. No rigorous same-hardware MySQL-vs-DuckDB benchmark at a few million rows was found.

### Cited Findings
- Percona (vendor blog, MySQL 9.7 with DuckDB as a storage engine): at the 10 GB scale, InnoDB is 100–340× slower per analytical query and did not finish 6 of 22 queries within a 180 s cap. InnoDB was dropped at 600M rows — [Percona blog](https://www.percona.com/blog/running-duckdb-as-a-mysql-9-7-storage-engine/)
- DuckDB vs SQLite (100M rows, Apple M2 Pro, third-party): DuckDB 12–35× faster cold and 8–20× faster warm on aggregations — [getgalaxy](https://www.getgalaxy.io/learn/glossary/duckdb-vs-sqlite-benchmarks)
- Contrasting third-party measurement of DuckDB aggregation latency growing with size: 1.23 s at 5M, 4.15 s at 15M, 10.60 s at 25M rows (commodity hardware, query shape not verified; much slower than the local test, so the workload probably differs) — [Level Up: practical limits of DuckDB](https://levelup.gitconnected.com/the-practical-limits-of-duckdb-on-commodity-hardware-3d6d6cf2bdde)
- **Local measurement:** 3M rows, 4 columns, single thread: 12 ms grouped aggregation with a range filter, 3 ms with a two-condition equality filter.

### Inferences
- Rule of thumb for CIP: if the custom-audience feature is in scope (unbounded combinations of filters), respondent-level columnar storage in an embedded engine is the right tool. MySQL over a 250 ms link cannot be on the hot path either way. Without that feature, published count tables plus in-memory math (the current design) is simpler and faster.
- DuckDB v2's `CONNECT` pushdown to MySQL is an ETL convenience at most. It doesn't remove the 250 ms round trip from request paths.

### Gaps
- No published, same-hardware latency comparison of MySQL (InnoDB) vs DuckDB on about 1–5M survey rows was found. A local benchmark on the real schema would be needed.

## 5. Downsides and risks of adding DuckDB

### Takeaway
The main risks are operational: an extra artifact to build and atomically publish, the per-path instance cache and lock semantics, a ~24 MB wheel, memory defaults that assume a whole machine, and **storage-format lock-in by version**. Files written by 2.0 can't be read by pre-2.0 DuckDB, so the ETL and API must be upgraded together or pin `storage_compatibility_version`.

### Cited Findings
- Backward compatibility has been guaranteed since v0.10: newer versions read older files. Forward compatibility is "best effort". New databases default to the v2.0.0 format (storage version 69), and "DuckDB versions before 2.0 cannot read database files that use the v2.0.0 storage format." Use `storage_compatibility_version` (e.g. `'v1.4.0'`) or `EXPORT/IMPORT DATABASE` for older readers. The setting "specifies the minimum DuckDB version that should be able to read the database file" — [DuckDB 2.0 storage internals](https://duckdb.org/docs/2.0/internals/storage.html)
- Single-writer lock: a read-write open fails while other processes hold the file (local measurement, section 1) — [DuckDB 2.0 Concurrency](https://duckdb.org/docs/2.0/connect/concurrency.html)
- Default `memory_limit` ≈ 80% of RAM and threads = all cores (local measurement). Minimum 125 MB per thread — [DuckDB 2.0 performance: environment](https://duckdb.org/docs/2.0/guides/performance/environment.html)
- Wheel ~24 MB — [PyPI](https://pypi.org/project/duckdb/2.0.0/)
- v2.0.0 is one day old (released 21 Oct 2026). Quack/server features were described as experimental before release — [GitHub releases](https://github.com/duckdb/duckdb/releases); [Quack docs](https://duckdb.org/docs/current/core_extensions/quack.html)

### Inferences
- Pin the exact `duckdb==` version in `requirements.txt` for both ETL and API. Alternatively, pin to 1.5.x until 2.0.x has a patch release or two, since 2.0.0 is brand new and changed the storage format, parser and I/O layer.
- Two uncapped workers could each try to use about 3.2 GB on a 4 GB box. Always set `memory_limit` and `threads=1`.
- Parquet files (instead of a `.duckdb` database) avoid the storage-version and lock problems entirely and can be atomically replaced per wave. The trade-off is the loss of DuckDB's native indexes and zone-map statistics persisted in the database file. Not benchmarked here.

### Gaps
- No measurement of DuckDB 2.0 on the actual 1-core/4 GB Linux server or on CIP's real respondent-level data.
- Gunicorn `--preload` plus DuckDB fork-safety is not covered in the official docs that were reviewed.
