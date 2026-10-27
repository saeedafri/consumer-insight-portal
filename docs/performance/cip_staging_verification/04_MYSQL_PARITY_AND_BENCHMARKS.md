# CIP MySQL parity and benchmark status

Date: 2026-10-27

## Evidence completed

- Live Azure MySQL version, schema, columns, collations, indexes, FKs, triggers, table estimates and status counters captured under an approved read-only session.
- `utf8mb4_0900_ai_ci` parity confirmed for the grouping and label columns.
- Cascade rules and absence of triggers confirmed.
- No heavy query, data extract, `EXPLAIN`, `EXPLAIN ANALYZE`, DML or benchmark was run on staging.

## Test results

| Scope | Result | Environment |
|---|---|---|
| New database reliability tests | 9 passed | Offline Python/SQLite/mocked MySQL-engine boundary |
| Focused API/ETL/publish/serving suite | 178 passed | Offline synthetic SQLite; network and notifications blocked |
| Complete suite | 360 passed, 0 failed/errors/skips, 18.71 s | Offline synthetic SQLite; network and notifications blocked |
| Python compilation | Passed | Local Python 3.13 |
| Diff whitespace check | Passed | Local Git worktree |

## Not yet proven

- MySQL optimizer plans for grouped cuts, extraction, serving join and replacement predicates.
- MySQL transaction rollback, lock timeout, deadlock and `LOAD DATA LOCAL INFILE` behavior on a disposable MySQL 8 database.
- MySQL output hashes versus clean base on representative anonymized waves.
- Stage timing, rows examined/sent, temp-table deltas, network bytes, CPU, I/O and RSS.
- Worker comparison at 1, 2 and 4 on MySQL.

Existing SQLite performance numbers remain local evidence only. No staging or Azure performance improvement is claimed.

## Next gates

1. Approve and execute the Stage 2 nonexecuting plans.
2. Select one candidate from SQL-019 and submit a separate Class C read-only benchmark proposal.
3. Build or authorize a disposable MySQL 8 fixture for write/rollback/import parity.
4. Require exact output hashes and numerical parity before accepting any SQL/index rewrite.
