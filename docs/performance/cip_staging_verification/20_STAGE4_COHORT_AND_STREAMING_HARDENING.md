# CIP Stage 4 cohort and streaming hardening

Date: 2026-10-27  
Environment: disposable MySQL 8.4.13, loopback only, synthetic data

Evidence: [STAGE4_MYSQL_HARDENING_RESULTS.json](evidence/STAGE4_MYSQL_HARDENING_RESULTS.json)  
SHA-256: `c4344f0a1b84b0ba796c77ab36bbe2aa0999aa66ee7bf174df04732e82aafc44`

## Cohort contract and writers

The schema documents `NULL = all qualified respondents`. Current writers use:

- `None` -> SQL `NULL` in `cip_agg_cell.cohort_id`.
- Positive `cip_cohort_def` auto-increment identifiers for named cohorts.
- Numeric zero only inside `cell_key`, never intentionally as the column value.

The table has no FK or CHECK on `cip_agg_cell.cohort_id`, so historical zero
rows are possible. The previous reader treated zero as everyone. The Stage 3
`IS NULL` predicate therefore changed behavior for that legacy case.

Final local policy:

- Reads for everyone use `(c.cohort_id IS NULL OR c.cohort_id = 0)`, preserving
  historical results.
- Positive cohort reads remain `c.cohort_id = :coh`.
- `cube.build_cube()` rejects zero or negative cohort identifiers, preventing
  new ambiguous rows.
- `analyse_cube()` retains its old `COALESCE` predicate: SQL-042 estimates only
  seven indexed cells, so changing it has no demonstrated benefit.
- The targeted rebuild deletion retains `COALESCE`: it intentionally removes
  both the current everyone rows and any legacy zero rows before rebuilding.

## MySQL predicate comparison

Three surveys contained explicit `NULL`, zero, and 200 positive cohort values.
Thirty samples were taken per predicate.

| Predicate | Returned everyone rows | n sum | Access | Cells examined | Index parts |
|---|---:|---:|---|---:|---|
| Old `COALESCE(...)=0` | 6 | 42 | `ALL` | 606 | none |
| Stage 3 `IS NULL` | 3 | 30 | `ref` | 3 | all four |
| Final `IS NULL OR = 0` | 6 | 42 | `ref_or_null` | 6 | all four |
| Positive cohort `=1` | 3 | 6 | `ref` | 3 | all four |

The compatibility predicate exactly matched the old row hash and output while
retaining index access locally. Its Azure plan remains unverified.

## Streaming extraction at scale

Dataset: 30 questions per respondent, repeated respondent rows, stable but
non-insertion-order IDs, missing demographic values, and deterministic outputs.
Each value is the median of three isolated child processes.

| `srv_answer` rows | Baseline wall | Streaming wall | Baseline traced peak | Streaming traced peak | Baseline RSS | Streaming RSS |
|---:|---:|---:|---:|---:|---:|---:|
| 60,000 | 0.725 s | 0.668 s | 35.3 MB | 8.0 MB | 161.8 MB | 75.1 MB |
| 300,000 | 4.011 s | 3.468 s | 176.2 MB | 33.7 MB | 540.7 MB | 123.7 MB |
| 900,000 | 11.626 s | 10.497 s | 529.5 MB | 122.1 MB | 1,236.8 MB | 255.0 MB |

At 900,000 rows, traced Python peak fell 76.9%, process peak RSS fell 79.4%,
and median wall time fell 9.7%. Exact payload hashes matched the materialized
baseline at all sizes. The largest run transferred 65,392,592 protocol bytes
and produced 1,291,320 bytes of canonical JSON.

The streaming result still scales with respondents and answer membership; it
is bounded by enforced test ceilings, not constant-memory. All runs stayed
under 512 MiB traced allocation and 1 GiB process RSS.

Each run executed exactly one `srv_answer` read and one `srv_result` metadata
read. Pool checkouts returned to zero. An injected failure after 4,999 streamed
rows proved that the result closed, the connection remained reusable, the
exception propagated, and the pool returned to zero.

## Connection capacity

The former configuration permitted up to 128 CIP connections across two API
workers plus the ETL process. Role-specific caps now produce a theoretical
maximum of 24:

- Each API worker: app 4 plus transactional writer 2+2 = 8; two workers = 16.
- ETL process: app 4 plus ETL 4 = 8.

Actual MySQL contention testing with eight callers and a 4+0 pool produced
exactly four connections and four bounded timeouts; all four connections were
returned.

## Candidate index remains unapproved

`(survey_id,dim,cohort_id,question_id)` remains a DBA proposal only. At the
reported ~2.79 million rows, a rough secondary-index estimate is 170-450 MiB,
depending mainly on encoded `dim` length and InnoDB overhead. It adds one index
entry to every cube insert/delete and requires a full index build. Build time,
Azure I/O pressure and start/end metadata-lock duration are unmeasured. No DDL
was executed.
