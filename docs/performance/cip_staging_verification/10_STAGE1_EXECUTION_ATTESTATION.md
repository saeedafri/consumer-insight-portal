# Stage 1 execution attestation

Date: 2026-10-27  
Database: `cip_stg` on the authorized Azure MySQL staging server  
Execution class: read-only metadata and status inspection

## Execution controls

- One short-lived TLS PyMySQL connection; no SQLAlchemy pool.
- Client timeouts: connect 5 seconds, read 10 seconds, write 10 seconds.
- Local infile disabled.
- Autocommit verified as `1`.
- `transaction_read_only` verified as `1`.
- `max_execution_time` verified as 5,000 ms.
- Metadata and InnoDB lock waits verified as 3 seconds.
- `IS_USED_LOCK('cip_etl')` returned `NULL` before table inspection.
- `Threads_running` was 5, below the approved stop threshold of 8.
- Statements executed once, serially, with no automatic retries.
- Connection closed after completion.

## Statement outcome

- Executed: SQL-001 through SQL-018 and SQL-020 through SQL-022.
- Not executed: SQL-019, any actual workload query, any view count, DML, DDL, `EXPLAIN ANALYZE`, ETL, scheduler, deployment, or service restart.
- Approved statements attempted: 21.
- Successful statements: 21.
- SQL errors/timeouts: 0.
- Rows affected: 0.
- Slowest statement: SQL-009 at 1,723.479 ms.
- Raw respondent/survey result rows returned: 0.

## Communication and environment safety

- Test network guards remained active for the local regression suite.
- No email, Teams, Slack, webhook, SMS, push, queue, or other notification transport was invoked.
- No shared database setting was changed. The five guard settings were session-local and ended when the dedicated connection closed.
- No database credentials, raw account/host values, connection identifier, view definer, PII, or raw survey answers are retained in the review archive.

The detailed sanitized statement evidence is in `evidence/STAGE1_SANITIZED_RESULTS.json`.
