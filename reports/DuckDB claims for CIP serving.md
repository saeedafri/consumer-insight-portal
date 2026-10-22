# DuckDB earns one job in CIP, not two

Gemini's report (`docs/research/columnar_cube_architecture.md`) is right that DuckDB is a fast columnar engine, but it gets most of its supporting details wrong, and its headline recommendation solves a problem CIP doesn't have. CIP serves crosstabs from gzip JSON files that the weekly ETL pre-publishes. The FastAPI API answers in about **1 ms warm and 9 ms cold**, and pages load in 39–88 ms through the tunnel. No engine that runs queries on request can beat a pre-built file, and in the researchers' own single-thread test DuckDB took **3–19 ms on 3M rows**. Gemini's "2^N storage explosion" argues against a SQLite cube that CIP never built. His PARQUET-1201 page-skipping claim is false for released DuckDB. Chimp/Patas compression was retired in 2024. A composite ART index on `(survey_id, qcode)` would never be used for lookups, `max_memory` does not cap total memory, and his benchmark numbers come from a 4-core M-series laptop, not CIP's 1-core servers. DuckDB does have one real job in CIP: the **Audiences** path, where arbitrary respondent filters can't be precomputed and MySQL takes 1.1–1.2 s. To make CIP truly great, keep the pre-published file layer, add a read-only columnar respondent store only behind Audiences (pinned version, `threads=1`, capped memory), move team views, alerts and /results onto pre-published files, and publish weight sums so significance testing and small-cell suppression use the right base.

## Gemini's claims, checked one by one

The table gives the verdict for each claim. The sections after it explain the ones that change a decision.

| Claim in Gemini's report | Verdict | What is actually true |
|---|---|---|
| DuckDB as primary serving engine | Wrong for CIP | Pre-published JSON (about 1 ms) already beats it. DuckDB fits only arbitrary-filter paths. |
| Parquet as cold/archival storage | Unnecessary | The whole corpus is about 74–116 MB, so there is no "cold" tier to tier off. Parquet is useful as an immutable hand-off file, not as an archive. |
| 2^N cube storage explosion | Mislabeled | A pairwise cube grows as C(N,2), not 2^N, and CIP has neither. |
| PARQUET-1201 page skipping | False for DuckDB 2.0.0 | DuckDB has no released option to write a page index and doesn't read one. PR #27326 is still open. |
| Chimp/Patas for float weights | Outdated | Replaced by ALP/ALPRD in v0.10.0 (Feb 2024). |
| DuckDB deliberately avoids mmap (Crotty et al.) | Half true, now outdated | The paper is real but DuckDB never cited it. 2.0 adds an opt-in `IO_MODE 'MMAP'`. |
| ART index on `(survey_id, qcode)` | Wrong | Only single-column indexes are used for index scans. ART memory can't be evicted. |
| `SET max_memory='2GB'` bounds memory | Wrong | The limit covers only the buffer manager. |
| 0.69 ms P95, 28 ms full scan, 2,085 QPS | Unrepresentative | Synthetic data, warm runs, 4-core laptop, 160-query sample. |

### The cube argument attacks a design CIP never built

Gray et al. do say a full CUBE over N attributes produces **2^N groupings** and **∏(Ci+1) cells**. The same paper expects the overhead to be modest when cardinalities are large, and says sparse cubes should store only non-empty cells ([Gray et al.](https://arxiv.org/pdf/cs/0701155)). Storing only pairwise combinations grows as C(N,2). For 12 dimensions that is **66 two-way tables, not 4,096**. Gemini's own report describes "materializing all 15 pairwise demographic combinations" over 6 dimensions, which is C(6,2), yet labels the result "2^N combinatorial". Harinarayan, Rajaraman and Ullman showed that materializing a few well-chosen views captures most of the query benefit, which is exactly what partial precomputation exploits ([HRU, SIGMOD 1996](https://doi.org/10.1145/233269.233333)). Neither paper supports the "~100 MB to 15–35 GB" figure. Matching it requires picking question counts, cardinalities and bytes per row, and the report states none of them.

More to the point, CIP has no 2^N cube. Its cube is single cuts plus pairwise cut counts that are computed on demand, so storage grows linearly with questions and waves. The 1.38 GB SQLite file Gemini benchmarked against is his own construction. That is also why his "18.7× compression ratio vs raw" is mislabeled: it compares Parquet with a SQLite file that includes indexes and the precomputed cube, not with the raw data.

### Parquet page skipping, compression and mmap claims are a release behind

PARQUET-1201 is real. It is the parquet-mr "Column indexes" ticket, fixed in parquet-mr 1.11.0 / format 2.5.0 in 2018 ([Apache JIRA](https://issues.apache.org/jira/browse/PARQUET-1201)). But DuckDB 2.0's COPY options list **no page-index setting**, and its default `DATA_PAGE_SIZE_LIMIT` is **100 MiB**, which in practice means one page per column chunk and nothing to skip at page level ([DuckDB COPY](https://duckdb.org/docs/2.0/sql/statements/copy.html)). The PR that adds page-index reading and writing (`WRITE_PAGE_INDEX`, off by default) is **open and unmerged** as of 22 Oct 2026 ([duckdb#27326](https://github.com/duckdb/duckdb/pull/27326)). The `write_page_index` setting Gemini describes is a PyArrow option ([PyArrow](https://arrow.apache.org/docs/python/generated/pyarrow.parquet.ParquetWriter.html)). Today DuckDB skips data using row-group zonemaps (min/max statistics per row group) ([DuckDB Parquet overview](https://duckdb.org/docs/2.0/data/parquet/overview.html)). Sorting the data by `(survey_id, qcode)` gets the skipping benefit without any page index.

On compression, DuckDB 0.10.0 introduced ALP, which "replaces Chimp and Patas" ([DuckDB 0.10.0](https://duckdb.org/2024/02/13/announcing-duckdb-0100.html)). Current source marks both as phased out ([compression_type.cpp](https://github.com/duckdb/duckdb/blob/main/src/common/enums/compression_type.cpp)). In 2.0, strings use DICT_FSST by default ([2.0 preview](https://duckdb.org/2026/08/17/duckdb-20-highlights)). One more catch: in-memory DuckDB databases are **not compressed by default**, so none of these compression claims apply to a `:memory:` design ([tuning guide](https://duckdb.org/docs/2.0/guides/performance/how_to_tune_workloads.html)).

The Crotty, Leis and Pavlo paper does warn DBMS builders off mmap ([CIDR 2022](https://www.cidrdb.org/cidr2022/papers/p13-crotty.pdf)). However, DuckDB's own memory-management write-up neither mentions mmap nor cites the paper ([DuckDB memory management](https://duckdb.org/2024/07/09/memory-management.html)). DuckDB 2.0 also merged an opt-in `IO_MODE 'MMAP'`; buffered I/O remains the default ([PR #22988](https://github.com/duckdb/duckdb/pull/22988)). None of this changes any decision for CIP. What it shows is that the report's internals section is built from pre-2024 knowledge.

### The index and memory advice would hurt on a 4.5 GB box

The DuckDB 2.0 indexing guide says outright that "indexes are only eligible for index scans if they index a single column without expressions" ([DuckDB indexing](https://duckdb.org/docs/2.0/guides/performance/indexing.html)). Gemini's composite `(survey_id, qcode)` index would still enforce constraints and cost memory, but no query would use it for lookups. The guide adds that index buffers are not evicted under memory pressure, and it advises against explicit indexes unless queries are highly selective and memory is plentiful. Even a single-column `survey_id` index would fail the default threshold of max(2,048, 0.1% of rows), which is about 10,400 rows here, because each wave holds roughly 40,000 rows. His sub-ms crosstab numbers are better explained by zonemap pruning on sorted data.

`max_memory` is an alias for `memory_limit`, whose default is 80% of RAM, and the limit "only applies to the buffer manager" ([DuckDB limits](https://duckdb.org/docs/2.0/operations_manual/limits.html), [configuration](https://duckdb.org/docs/2.0/configuration/overview.html)). On staging (1 core, 4.5 GB), two uncapped gunicorn workers could each claim most of the RAM before Python and FastAPI take their share. Size the container on process RSS, not on the setting.

### The benchmark measured a laptop, not CIP

Gemini's setup section lists an Apple M-series machine with **4 cores and 16 GB**, DuckDB 2.0.0, 30 warm iterations, and 10.4M rows "matching the schema and distribution" of CIP, which is synthetic data. He compared against SQLite, not MySQL or the JSON files CIP actually serves. His 2,085 QPS figure is **160 queries finished in 77 ms**, which is too small a sample to reach steady state. DuckDB parallelizes by row group, and using k threads needs at least k × 122,880 rows scanned ([tuning guide](https://duckdb.org/docs/2.0/guides/performance/how_to_tune_workloads.html)). A single-wave crosstab of about 40k rows therefore runs on one thread anyway, and on a 1-core server 8 threads only fight over the CPU. CIP's own HTTP-level stress run (`scripts/stress_benchmark_results.json`) shows a crosstab **p50 of 0.78 ms but a p95 of 13.7 ms** at about 811 RPS. Real tail latency sits about 20× above Gemini's engine-only 0.69 ms P95. His version choice adds risk too. DuckDB 2.0.0 was released 21 Oct 2026, one day ago ([release calendar](https://duckdb.org/release_calendar)). Its storage format can't be read by pre-2.0 versions ([storage internals](https://duckdb.org/docs/2.0/internals/storage.html)). He installed it into `.venv`, but it is not in `requirements.txt`.

## Measured on CIP's own data

All of `srv_answer` was copied read-only from `cip_stg`: 9,532,424 rows with six cuts, sorted by `(survey_id, qcode, respondent_id)` with no index. It was queried in-process with DuckDB 2.0.0 on the Mac, warm, 200 runs each. `threads=1` approximates the 1-core servers.

| Query | threads=1 p50 / p95 | threads=4 p50 / p95 | MySQL today |
|---|---|---|---|
| Audience: wave 415 D29 for Female × GenZ/Millennial who chose ChatGPT at D28 | 0.80 / 0.93 ms | 0.82 / 0.97 ms | 1,130–1,190 ms |
| Everyone else: wave 415 D29 | 0.38 / 1.10 ms | 0.36 / 0.39 ms | (same query) |
| Pooled: q1 by gender × income, 13 waves | 5.1 / 5.3 ms | 2.6 / 3.0 ms | — |
| Full scan: distinct respondents by generation × region | 113 / 122 ms | 36 / 37 ms | — |

- **Storage:** the DuckDB file is 66.8 MB and the zstd Parquet file 22.5 MB. The CSV export was 639 MB. Peak process RAM was 115 MB at `threads=1`.
- **Audiences:** about 1,400× faster than live MySQL, and under the 10 ms server budget even on one thread. That is DuckDB's one job in CIP.
- **Fixed cuts:** the pre-published JSON (about 1 ms) still matches or beats DuckDB, so it stays.
- **Caveats:**
  - Measured on a laptop, not the 1-core server, and in-process rather than over HTTP.
  - A wide scan (113 ms on one thread) is the worst case to keep away from interactive endpoints.
  - The copy took 581 s over the India↔Azure link. In production the ETL would write this file at publish time from rows it already holds, not re-download them.

## Making CIP great means attacking the three slow paths

CIP's fast path is already near its floor. Commercial tools that promise sub-second ad-hoc tabs, such as Crunch.io, get there by aggregating respondent-level columnar data on the fly ([Crunch](https://crunch.io/product/enterprise-scalable)). That is the right model only for queries that can't be listed in advance. For CIP's fixed set of cuts, pre-publishing is strictly better. The remaining slowness lives in three places, and the ETL's 243 s per wave is mostly India↔Azure transfer time that no query engine touches. DuckDB 2.0's `CONNECT` pushdown to MySQL doesn't remove that network round trip either ([Quack docs](https://duckdb.org/docs/current/core_extensions/quack.html)).

**Audiences (1.1–1.2 s) is DuckDB's legitimate job.** Arbitrary respondent filters can't be precomputed, and a row store running these aggregations is published as roughly 100–340× slower than DuckDB at scale ([Percona](https://www.percona.com/blog/running-duckdb-as-a-mysql-9-7-storage-engine/)). Setup:

- Have the ETL export `srv_answer` sorted by `(survey_id, qcode)` into a versioned file, either `cip_<version>.duckdb` or Parquet.
- In each worker, open it `read_only=True` after fork, with `threads=1` and an explicit `memory_limit`.
- Give every request thread its own `cursor()`. A shared connection raises an error on concurrent calls instead of queueing them ([Python DB API](https://duckdb.org/docs/2.0/clients/python/dbapi.html)).
- Republish by **new path**, never by renaming over the old one. A read-write open fails while readers hold the file, and the Python client keeps serving old data from a same-path reconnect until every connection closes ([concurrency](https://duckdb.org/docs/2.0/connect/concurrency.html)).
- Pin one exact `duckdb==` version in both the ETL and the API, either 1.5.x or 2.0.x after its first patch release.

Parquet avoids the storage-version and lock issues entirely, at the cost of the statistics a native `.duckdb` file keeps. A dependency-free alternative is worth testing on the same data: hold a per-wave respondent-by-question code matrix in memory as numpy arrays and filter with boolean masks. At about 9M rows it may come close enough without adding a 24 MB wheel. This is untested; the pending measurement should decide between the two.

**Team views, alerts (about 300 ms) and /results** belong in the pre-published layer, not in a faster engine. If their inputs change only when the ETL runs, writing them as files during publish turns 300 ms into the same 1–9 ms the crosstabs already get.

**Statistical correctness is the next quality jump.** Weighted significance needs an effective base. Kish n_eff = (Σw)²/Σw² can be computed from cell totals, so the publisher should write **Σw and Σw² per cell** next to the counts ([Q wiki](https://wiki.q-researchsoftware.com/wiki/Weights,_Effective_Sample_Size_and_Design_Effects)). CIP's hide-under-30 / flag-under-50 rule matches industry practice: WinCross uses a minimum base of 30 for significance by default ([WinCross](https://www.analyticalgroup.com/WinCrossExecutiveHelp1/Desktop/Edit_Crosstab.htm)), and Alida shows N/A below its minimum per banner column ([Alida](https://insightcommunity.help.alida.com/enus/adhoc/reports_modern/significance_testing/significance_testing_apply_modern.html)). The rule must be applied to the **unweighted or effective** base, never the weighted sum, and Audiences results need the same server-side check.

## Conclusion

The real lesson from Gemini's report is about evaluation method, not DuckDB. A benchmark that compares candidate engines against each other, rather than against the system already running, will always crown an engine. CIP's baseline is a file read, and nothing wins against it. So the question for each slow endpoint is whether the work can be done during the weekly ETL rather than at request time. Two of the three slow paths can. Only Audiences needs a query engine at request time, and for that one endpoint a read-only columnar store is the right tool.

The decision should rest on the pending real-data measurement, taken on the 1-core server at the HTTP layer with `threads=1`, and not on any laptop number in this report or Gemini's. If DuckDB brings Audiences from 1.1 s to tens of milliseconds there, the case for it is closed. If a numpy mask gets close enough, CIP gains the speed without a new runtime dependency on a one-day-old release.

## Decision taken (22 Oct 2026): bitsets, not DuckDB

We tested a lighter option than DuckDB and built it instead. The ETL now publishes, for each wave, one bitset per cut value and per answer: `api/v1/waves/<id>/people.json.gz`, where each respondent is one bit. The API works out an audience with bitwise AND and bit counts. It never serves the file itself, so nobody can download respondent-level data.

| | Bitsets (shipped) | DuckDB (tested) | MySQL (before) |
|---|---|---|---|
| Storage, all 371 waves | 6.9 MB | 66.8 MB (22.5 MB as Parquet) | in `srv_answer` |
| RAM | 4.7 MB for the 16 largest waves cached | 115 MB per process | — |
| Audience, warm | 0.008 ms in process, about 1 ms over HTTP | 0.8 ms | 780–4,800 ms |
| Audience, first use of a wave | 1–1.7 ms | — | — |
| New dependency | none | duckdb (2.0.0, one day old) | — |

The results are byte-identical to the MySQL path on three real test cases. DuckDB remains worth considering only if CIP later needs ad-hoc queries that pool many waves.
