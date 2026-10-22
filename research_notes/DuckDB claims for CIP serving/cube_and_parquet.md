# Data cube scaling and Parquet layout claims (checked 22 Oct 2026)

Context: the claims come from `docs/research/columnar_cube_architecture.md` in this repo (lines 20-21, 186-199, 222-233). That doc gives no reproducible script for its numbers. No `to_parquet` / `COPY ... PARQUET` benchmark script was found in `scripts/` or `docs/research/`.

## Claim 1: Gray et al. 2^N cube growth, "12 dims pairwise means ~100 MB to 15-35+ GB"

### Takeaway
Gray et al. do say a CUBE over N attributes produces 2^N grouping combinations (2^N - 1 super-aggregates plus the core GROUP BY), and that the cube holds ∏(Ci+1) cells. But storing only pairwise (2-way) interactions grows as C(N,2) = N(N-1)/2 (66 for N=12), not 2^N (4,096). The "15-35 GB" figure does not follow from either paper. It depends on assumed cardinalities, question counts, wave counts and bytes per row, none of which the claim states. The repo doc's own text gives ">15 GB" for **3-way** cubes over **6** dimensions, not pairwise over 12, so the claim as quoted does not match its own source.

### Cited Findings
- Paper: Gray, Chaudhuri, Bosworth, Layman, Reichart, Venkatrao, Pellow, Pirahesh, "Data Cube: A Relational Aggregation Operator Generalizing Group-By, Cross-Tab, and Sub-Totals". arXiv copy dated May 1997 (Data Mining and Knowledge Discovery 1(1), 1997). An earlier version appeared at ICDE 1996 and as MSR-TR-95-22, and the paper says that version "and the Microsoft SQL Server 6.5 product implemented a slightly different syntax." — [arXiv cs/0701155](https://arxiv.org/abs/cs/0701155), [PDF](https://arxiv.org/pdf/cs/0701155)
- Group-by count, quoted: "If there are N attributes in the <select list>, there will be 2^N − 1 super-aggregate values." So 2^N groupings including the core. — [Gray et al. PDF, §3](https://arxiv.org/pdf/cs/0701155)
- Cube size, quoted: "If the cardinality of the N attributes are C1, C2, ..., CN then the cardinality of the resulting cube relation is ∏(Ci + 1). The extra value in each domain is ALL. For example, the SALES table has 2x3x3 = 18 rows, while the derived data cube has 3x4x4 = 48 rows." — [Gray et al. PDF](https://arxiv.org/pdf/cs/0701155)
- Gray et al. expect the overhead to be small when cardinalities are large, quoted: "If each Ci = 4 then a 4D CUBE is 2.4 times larger than the base GROUP BY. We expect the Ci to be large (tens or hundreds) so that the CUBE will be only a little larger than the GROUP BY. By comparison, an N-dimensional roll-up will add only N records to the answer set." The 2.4 is 5^4/4^4 = 625/256. — [Gray et al. PDF, §5](https://arxiv.org/pdf/cs/0701155)
- Compute cost: the "2^N-algorithm" calls Iter() "T x 2^N times" for a base table of cardinality T, because each coordinate is either xi or ALL. The paper says it is often faster to compute super-aggregates from the core GROUP BY. — [Gray et al. PDF, §5](https://arxiv.org/pdf/cs/0701155)
- Sparsity, quoted: "It is possible that the core of the cube is sparse. In that case, only the non-null elements of the core and of the super-aggregates should be represented." — [Gray et al. PDF](https://arxiv.org/pdf/cs/0701155)
- Maintenance: inserting one base record means visiting its 2^N super-aggregates. — [Gray et al. PDF, §6](https://arxiv.org/pdf/cs/0701155)
- HRU: Harinarayan, Rajaraman, Ullman, "Implementing Data Cubes Efficiently", SIGMOD 1996, pp. 205-216, DOI 10.1145/233269.233333. It asks which views (cells) to materialize when materializing all of them is too expensive. It models dependencies as a lattice, uses a linear cost model (query cost ≈ size of the view it is answered from), and uses greedy view selection, with a TPC-D example over part/supplier/customer (2^3 = 8 views). — [TAU seminar summary](https://cs.tau.ac.il/~matias/courses/sem_fall98/datacube/New_Data.htm), [ACM DOI](https://doi.org/10.1145/233269.233333)
- HRU greedy guarantee: "always within 63% of the optimal solution for all lattices". 63% ≈ (e-1)/e, meaning greedy gets at least 63% of the optimal benefit. — [Sookocheff summary (secondary)](https://sookocheff.com/post/databases/implementing-data-cubes-efficiently/)

### Inferences
- Arithmetic for N = 12: full cube = 2^12 = 4,096 groupings. Pairwise only = C(12,2) = 66 two-way tables, plus 12 one-way and 1 total. Three-way = C(12,3) = 220. The source doc used 6 dims: C(6,2) = 15 and C(6,3) = 20.
- Pairwise cell count with ∏(Ci+1)-style ALL margins: if each demographic has about 6 levels, one pairwise table is 7×7 = 49 cells, and 66 pairs give about 3,234 cells per (question-option × wave). A dense full cube would be 7^12 ≈ 1.38×10^10 cells, but sparsity caps the non-empty cells at min(∏(Ci+1), T·2^N).
- Is 15-35 GB derivable? Only with chosen inputs. Example: 144 waves × ~250 question-options (50 Qs × 5 options) = 36,000 slices × 3,234 cells ≈ 116 M rows. At ~40-100 B/row in SQLite with indexes, that is ≈ 4.7-12 GB. Reaching 15-35 GB needs more questions, higher cardinalities, extra measures, or 3-way terms. The order of magnitude is possible, but it is an assumption-driven estimate, not a result from Gray or HRU. The "~100 MB" baseline is not sourced either.
- Correct framing: full CUBE grows as 2^N groupings and ∏(Ci+1) cells. Pairwise-only grows polynomially (O(N²) tables). HRU shows partial materialization of a few chosen views captures most of the query benefit.
- The repo doc's line 21 labels the SQLite precomputed cube "Storage explosion (2^N combinatorial)", but per lines 222-233 the cube it describes is pairwise. That is a C(N,2) design, so the 2^N label is wrong for it.

### Gaps
- Could not download the HRU full text (Berkeley and NYU links returned HTML/XML, not the PDF). The 63% / (e-1)/e figure comes from a secondary summary and was not checked against the paper. TPC-D view sizes from the paper could not be quoted.
- The MSR-TR-95-22 / ICDE 1996 version was not read. Formulas quoted above are from the 1997 journal / arXiv version.
- No source for the "~100 MB" and "15-35 GB" figures was found anywhere.

## Claim 2: PARQUET-1201, write_page_index = true, 120k-250k row groups, 1 MB pages

### Takeaway
PARQUET-1201 is real. It is the parquet-mr JIRA "Column indexes" (implementation of the page index), fixed in parquet-mr 1.11.0 / format 2.5.0 in 2018. The spec itself is PageIndex.md (PARQUET-922). `write_page_index` is a **PyArrow** option (default False). As of DuckDB v2.0.0 (released 21 Oct 2026), DuckDB has **no released option to write the page index**, and its reader does not use ColumnIndex/OffsetIndex. PR #27326 adding both (`WRITE_PAGE_INDEX`, off by default) is open and unmerged as of 22 Oct 2026. Row-group sizes of 120k-250k rows fit DuckDB's 122,880 default, but the Parquet project recommends 512 MB-1 GB row groups. The 1 MiB page is the parquet-mr/Arrow default, while DuckDB's default page limit is 100 MiB, meaning one page per column chunk, so DuckDB-written files have nothing to skip at page level.

### Cited Findings
- PARQUET-1201 "Column indexes": Resolved/Fixed. Fix versions format-2.5.0 and 1.11.0. Created 22 Jan 2018, resolved 18 Oct 2018. Description: "Write the column indexes described in PARQUET-922", covering read/write utilities, parquet-tools/cli output, limiting index size, truncating min/max, and filtering based on column indexes. — [Apache JIRA PARQUET-1201](https://issues.apache.org/jira/browse/PARQUET-1201)
- Page index spec: an optional per-ColumnChunk structure (ColumnIndex + OffsetIndex in parquet.thrift) with per-page statistics so readers can skip pages. ColumnIndex holds per-page lower/upper bounds (may be truncated), null pages and null counts, and boundary order. OffsetIndex maps row index to page location: offset, compressed size, first_row_index. "The new index structures are stored separately from RowGroup, near the footer". Readers binary-search ordered columns or scan unordered ones. Readers supporting ColumnIndex should not use page-header statistics. The spec gives **no** page or row-group size recommendation. — [parquet-format PageIndex.md](https://github.com/apache/parquet-format/blob/master/PageIndex.md), [parquet.apache.org Page Index](https://parquet.apache.org/docs/file-format/pageindex/)
- Official Parquet configuration guidance: "We recommend large row groups (512MB - 1GB)" and "We recommend 8KB for page sizes." The 8 KB advice is old and differs from implementation defaults of 1 MB. — [Parquet docs: Configurations](https://parquet.apache.org/docs/file-format/configurations/)
- PyArrow `ParquetWriter`: `write_page_index` default `False`, "Whether to write a page index in general for all columns". `data_page_size` default None means "the default data page size of 1MByte". Compression default `'snappy'`. — [PyArrow ParquetWriter docs](https://arrow.apache.org/docs/python/generated/pyarrow.parquet.ParquetWriter.html)
- DuckDB v2.0 COPY Parquet options: `ROW_GROUP_SIZE` default **122880**. `ROW_GROUP_SIZE_BYTES` default `row_group_size * 1024`, only used with `preserve_insertion_order = false`. `COMPRESSION` default **snappy** (options uncompressed, snappy, gzip, zstd, brotli, lz4, lz4_raw). `COMPRESSION_LEVEL` 1-22, default **3**. `DATA_PAGE_SIZE_LIMIT` default **104857600 (100 MiB)**. `PARQUET_VERSION` default V1. **No page-index option listed.** — [DuckDB 2.0 COPY docs](https://duckdb.org/docs/2.0/sql/statements/copy.html)
- DuckDB tips: row group size has "a minimum value equal to DuckDB's vector size, 2,048, and a default of 122,880". It reads row groups in parallel within a file. Rule of thumb: number of row groups per file at least the number of CPU threads. "Compression algorithms are only applied per row group." — [DuckDB 2.0 Parquet tips](https://duckdb.org/docs/2.0/data/parquet/tips.html)
- DuckDB reader: "supports filter pushdown into the Parquet reader" and can "skip parts of the file using the built-in zonemaps", which are row-group min/max statistics. Page index is not mentioned. — [DuckDB 2.0 Parquet overview](https://duckdb.org/docs/2.0/data/parquet/overview.html)
- DuckDB PR #27326, "Parquet: read and write the page index (ColumnIndex / OffsetIndex)": **OPEN**, opened 15 Oct 2026, labels "Ready For Review", "backport v2.0-cyanoptera". It adds COPY option `WRITE_PAGE_INDEX` (**off by default**) and reader use (setting `parquet_use_page_index`, default true), plus a `parquet_page_index()` function. With `WRITE_PAGE_INDEX true` the default `DATA_PAGE_SIZE_LIMIT` becomes 1 MiB. The PR states that today DuckDB's existing header-based page pruning "never fires on Spark files". Benchmarks (10 M rows, one row group, 1 MiB pages): point lookup 0.080 s vs 0.165 s, range scan 0.109 s vs 0.197 s, write 0.47 s vs 0.42 s. The PR says it "was generated by an AI coding agent and reviewed by the author." — [duckdb/duckdb#27326](https://github.com/duckdb/duckdb/pull/27326)
- DuckDB release timeline: v2.0.0 on 21 Oct 2026, v1.5.6 on 28 Sep 2026. — [DuckDB releases](https://github.com/duckdb/duckdb/releases)

### Inferences
- As of 22 Oct 2026, "DuckDB performs page skipping via PARQUET-1201" is **false** for released DuckDB. Page skipping in DuckDB today relies on row-group zonemaps, with limited page-header stats on its own files. If #27326 merges and is backported, it would arrive in a v2.0.x patch, opt-in for writing.
- To get a page index today, write with PyArrow (`write_page_index=True`, 1 MB pages default) or parquet-mr/Spark (on by default). DuckDB's reader would not exploit it until #27326 ships.
- For ~10.4 M rows, 122,880-row groups give ~85 row groups, enough for parallelism on many threads. CIP servers are 1 core, so parallel-scan benefits are moot there. Sorting by `(survey_id, qcode)` makes row-group zonemaps effective without any page index.
- "row groups of 120k-250k rows" is a DuckDB-flavoured choice. It is not a Parquet project recommendation, which says 512 MB-1 GB.

### Gaps
- Did not check the DuckDB source for whether the current writer emits page-header statistics. The PR implies header-based page pruning exists for DuckDB-written files.
- Did not confirm the default `row_group_size` of PyArrow `write_table` (the page was truncated).

## Claim 3: ZSTD gives 10.4 M rows at ~74 MB (~7.1 B/row); Parquet "stateless/immutable" means zero lock contention

### Takeaway
74.0 MB / 10.4 M = 7.1 B/row is arithmetically consistent and plausible for long-format survey answers (low-cardinality ints, sorted, dictionary + RLE + ZSTD). However, it comes from an unreproduced benchmark in the repo doc with no script, and it depends on schema and sort order. "Zero lock contention" is broadly right in that Parquet files are write-once and readers take no file locks. Caveats: per-process memory duplication, atomic file replacement during the weekly ETL, and CPU contention on the 1-core servers.

### Cited Findings
- Repo doc figures: Parquet 74.0 MB (ZSTD) / 81.5 MB (Snappy), DuckDB native 115.8 MB, SQLite 1,386.3 MB. "18.7× (ZSTD)". ZSTD vs Snappy 73.98 MB vs 81.54 MB. Hardware: Apple M-series. — `docs/research/columnar_cube_architecture.md` lines 20-21, 199, 242 (local file; no generating script found).
- Repo data volume: "144 waves, 71,474 qualified respondents, 10.4 M answer rows". — `docs/13-ui-system-design.md` line 21 (local).
- DuckDB applies compression per row group, so larger row groups give more compression opportunity. ZSTD level default is 3 (range 1-22), and the DuckDB default codec is Snappy, so ZSTD must be requested explicitly. — [DuckDB tips](https://duckdb.org/docs/2.0/data/parquet/tips.html), [DuckDB COPY](https://duckdb.org/docs/2.0/sql/statements/copy.html)
- DuckDB concurrency for the native DB file: "Read-only mode: multiple processes can read from the database, but no processes can write (access_mode = 'READ_ONLY')." The page does not cover Parquet or external files. — [DuckDB 2.0 concurrency](https://duckdb.org/docs/2.0/connect/concurrency.html)

### Inferences
- 7.1 B/row: 74.0e6 / 10.4e6 = 7.12. Plausible for columns like (survey_id, qcode, respondent_id, option code, weight) when sorted by survey/qcode: dictionary/RLE collapse repeated keys, and ZSTD shrinks the rest. A float64 weight column or free-text answers would push this up a lot. Snappy is ~10% larger (81.5 MB), which fits typical ZSTD vs Snappy gaps. Treat it as a single unverified measurement. Re-run with the real schema before quoting.
- The 18.7× ratio is measured against the 1.38 GB SQLite file (1386.3/74.0 = 18.7), which includes indexes and the precomputed cube. It is not raw data size, so "compression ratio vs raw" is mislabeled.
- Concurrency: Parquet files are immutable once written. Each FastAPI worker opening its own in-memory DuckDB connection and calling `read_parquet()` uses no shared lock, so "no lock contention" holds for reads. Caveats:
  1. Each worker process has its own DuckDB buffer pool and Parquet metadata, so memory is multiplied by the worker count. That matters on 4.5 GB staging / 8-9 GB prod servers.
  2. Weekly refresh must write a new file and atomically `rename`/`os.replace` it. On POSIX, open readers keep the old inode, and in-place overwrite risks torn reads.
  3. On a 1-core box, multiple workers contend for CPU even without locks.
  4. Within one process, share one DuckDB database and use per-thread cursors rather than one connection across threads.
- "Stateless" is loose wording. The file has no runtime state, but readers cache metadata, so the benefit is "no writer coordination", not "zero state".

### Gaps
- No primary source benchmarks bytes/row for survey data. The 74 MB figure cannot be checked without re-running on `cip_stg` data.
- DuckDB docs found here do not state explicit guarantees about concurrent multi-process reads of the same Parquet file. The no-lock behaviour is inferred from immutability and POSIX semantics, not from a documented statement.
