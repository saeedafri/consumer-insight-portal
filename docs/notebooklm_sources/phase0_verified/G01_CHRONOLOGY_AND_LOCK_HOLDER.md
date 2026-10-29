# G01: Chronology & Lock Holder Forensic Analysis
**Scope:** Reconstructed UTC Timeline, Slow-Log Semantics, and Metadata Lock (MDL) Convoy Forensics  
**Host:** `csr-mysql8-flex-stg.mysql.database.azure.com`  
**Primary Datasets:** 4 Non-Empty Slow Query Logs, Container App Logs, and Azure Monitor Telemetry Images

---

### 1. Slow Query Log Semantics & Time Re-Alignment

A critical source of past confusion was the interpretation of timestamps in MySQL slow query logs. The raw log format is:
```text
# Time: 2026-10-21T03:13:25.123456Z
# User@Host: chainxydata_stg[chainxydata_stg] @  [10.21.1.253]  Id: 942756
# Query_time: 7133.321000  Lock_time: 0.000000 Rows_sent: 0  Rows_examined: 0
SET timestamp=1792559539;
TRUNCATE TABLE `all_active_current`;
```

#### Ground-Truth Mathematical Relationship:
1. `# Time:` represents the **Query Start Timestamp** (or the timestamp printed when query execution begins).
2. `SET timestamp=` is an **Epoch Timestamp (in seconds)** recorded when the query **Finishes and Writes to the Log**.
3. `Query_time:` is the **Wall-Clock Duration in Seconds**.
4. **Verification:**
   * `# Time:` = `2026-10-21 03:13:25 UTC`
   * `SET timestamp=1792559539` = `2026-10-21 05:12:19 UTC`
   * Difference: `05:12:19` - `03:13:25` = **7,134 seconds**
   * Logged `Query_time` = **7,133.321000 seconds** (Exact match within sub-second precision).

---

### 2. The Reconciled Chronological Incident Timeline (UTC)

The investigation conclusively reveals that the past week did **NOT** represent a single continuous incident. Rather, it comprised **seven temporally separate episodes** across different dates and systems:

```
[Oct 4-5 IST] ──────► Episode 1: Early Streamlit [STORE_MAP] 180s Timeouts (Independent code issue)
                             │
[Oct 17-19 UTC-5] ──► Episode 2: Host CPU 100% Flatline + Peak 313 Active Connections (Monday Oct 19)
                             │
[Oct 20 08:53 UTC] ─► Episode 3: SIP active_full 506k Row Fetch Latency (225 seconds)
                             │
[Oct 21 03:13 UTC] ─► Episode 4: TRUNCATE all_active_current 2-Hour Metadata Lock (MDL) Convoy
                             │
[Oct 22 UTC] ───────► Episode 5: Giant all_active_log Full Table Scans (10,823s & 10,300s, 580M rows)
                             │
[Oct 23 UTC-5] ─────► Episode 6: Post-Incident HTTP 4xx Spike (814 errors on vis-portal-stg)
                             │
[Oct 24 03:07 IST] ─► Episode 7: App Boot Engine Warm Ping SELECT 1 Stalled for 6,066 ms
```

#### Detailed Chronological Events:

| Timestamp (UTC) | Local Time | Source Artifact & Line | Event / Observed Action | Account & Connection ID | Duration / Value | Proven Link to Incident |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **2026-10-04 13:28:37 UTC** | 04-Oct-2026 06:58:37 PM IST | `server-logs-20261023_211951.log:12429` | `[STORE_MAP][ERROR] layer load timed out \| active did not return within 180s` | App Container (`store_footprint.py`) | 180s timeout | **NO CAUSAL LINK to Oct 21 lockup**. Occurred 16 days prior; proves pre-existing application query inefficiency. |
| **2026-10-17 05:00 UTC** | 17-Oct-2026 00:00 UTC-05 | `CPU percentage.png` | Host CPU Percent flatlines at **100%** continuously | Azure Host Metric | ~48 hours | CPU saturation begins 4 days before TRUNCATE. |
| **2026-10-19 15:00–18:00 UTC** | 19-Oct-2026 10:00–13:00 UTC-05 | `Active connections.png` | **Max Active Connections hits peak 313** (Limit 341) | Azure Host Metric | 313 sessions | **Occurred on Oct 19, NOT Oct 21**. Proves connection pool pressure peaked 2 days before the TRUNCATE incident. |
| **2026-10-20 08:53:34 UTC** | 20-Oct-2026 02:23:34 PM IST | `server-logs-20261023_211951.log:116187`| `[TIMING][store_map] query=active_full 225629ms rows=506895` | `vis-portal-stg` (Streamlit) | 225.6 seconds | 506k raw unaggregated rows pulled across network during storage I/O contention. |
| **2026-10-21 03:02:00 UTC** | 21-Oct-2026 08:32:00 IST | `mysql-slow-2026102023.log:4209` | `SELECT runID, MIN(Period)... FROM all_active_current GROUP BY runID` | `chainxydata_stg` (Conn 941032 @ 10.2.0.4) | 978.50s (16.3 min), 21.5M rows | **ACTIVE READER**. Held shared lock when TRUNCATE arrived at 03:13:25Z; finished at 03:18:18Z. |
| **2026-10-21 03:13:25 UTC** | 21-Oct-2026 08:43:25 IST | `mysql-slow-2026102023.log:7845` | `TRUNCATE TABLE all_active_current;` initiates and enters lock wait | `chainxydata_stg` (Conn 942756 @ 10.21.1.253)| **7,133.32s (1.98 hrs)** | **THE MDL LOCK CONVOY BEGINS**. Waited for exclusive metadata lock until 05:12:19Z. |
| **2026-10-21 03:17:05 UTC** | 21-Oct-2026 08:47:05 IST | `mysql-slow-2026102023.log:7875` | `SELECT COUNT(*) FROM all_active_current WHERE Period='2026-07-01'` arrives | `chainxydata_stg` (Conn 941896 @ 10.21.1.253)| 6,917.58s wait | **BLOCKED WAITER**. Queued behind TRUNCATE in MySQL MDL queue. Finished at 05:12:23Z. |
| **2026-10-21 03:23:19 UTC** | 21-Oct-2026 08:53:19 IST | `mysql-slow-2026102023.log:7921` | `SELECT Period AS mp, COUNT(*) FROM all_active_current...` arrives | `chainxydata_stg` (Conn 943094 @ 10.21.1.253)| 6,543.83s wait | **BLOCKED WAITER**. Queued behind TRUNCATE. Finished at 05:12:23Z. |
| **2026-10-21 03:31:31 UTC** | 21-Oct-2026 09:01:31 IST | `mysql-slow-2026102023.log:7890` | `SELECT Period AS mp... FROM all_active_current...` arrives | `chainxydata_stg` (Conn 942775 @ 10.21.1.253)| 6,051.53s wait | **BLOCKED WAITER**. Finished at 05:12:23Z. |
| **2026-10-21 03:37:31 UTC** | 21-Oct-2026 09:07:31 IST | `mysql-slow-2026102023.log:7905` | `SELECT MIN(Period), MAX(Period) FROM all_active_current` arrives | `chainxydata_stg` (Conn 943570 @ 10.21.1.253)| 5,691.04s wait | **BLOCKED WAITER**. Finished at 05:12:23Z. |
| **2026-10-21 03:49:32 UTC** | 21-Oct-2026 09:19:32 IST | `mysql-slow-2026102023.log:7860` | `SELECT COUNT(*) FROM all_active_current WHERE Period='2026-07-01'` arrives | `chainxydata_stg` (Conn 943964 @ 10.21.1.253)| 4,970.12s wait | **BLOCKED WAITER**. Finished at 05:12:23Z. |
| **2026-10-21 03:56:37 UTC** | 21-Oct-2026 09:26:37 IST | `mysql-slow-2026102023.log:7850` | `SELECT Period AS mp... FROM all_active_current...` arrives | `chainxydata_stg` (Conn 944197 @ 10.21.1.253)| 4,545.95s wait | **BLOCKED WAITER**. Finished at 05:12:23Z. |
| **2026-10-21 05:12:19 UTC** | 21-Oct-2026 10:42:19 IST | `mysql-slow-2026102023.log:7845` | **TRUNCATE TABLE completes execution** (`ts=1792559539`) | `chainxydata_stg` (Conn 942756) | Completed | **LOCK RELEASED**. Queue flushes. |
| **2026-10-21 05:12:23 UTC** | 21-Oct-2026 10:42:23 IST | `mysql-slow-2026102023.log:7850-7933` | **11 Queued SELECT queries all finish simultaneously** (`ts=1792559543`) | Multiple Connections (@ 10.21.1.253) | All finish in 4s | **INCONTROVERTIBLE PROOF OF MDL CONVOY**. |
| **2026-10-22 04:30–07:30 UTC** | 22-Oct-2026 10:00–13:00 IST | `mysql-slow-2026102223.log:412` | 3-Hour `all_active_log` queries run (`MAX(id)` and `runID=20`) | `chainxydata_stg` | 10,823s and 10,300s | **Occurred on Oct 22**, 24 hours AFTER the TRUNCATE incident. Caused separate disk/CPU thrashing. |
| **2026-10-23 23:00+ UTC** | 23-Oct-2026 18:00+ UTC-05 | `HTTP 4xx.png` | **Surge of 814 HTTP 4xx errors on vis-portal-stg** | Azure Monitor Metric | 814 errors | Occurred at the end of Friday Oct 23; does not overlap with Oct 21 lock convoy. |
| **2026-10-24 03:07:20 AM IST** | 23-Oct-2026 21:37:20 UTC | `server-log.log:2` | `[TIMING][store_map] engine warm SELECT 1 in 6066ms` | Local Python App (PID 28955) | 6.066 seconds | Cross-region network latency + server CPU/worker thread congestion on boot. |

---

### 3. Detailed Forensic Lock-Holder Analysis (October 21)

#### What the Slow Log Proves with 100% Certainty:
1. At **03:13:25 UTC**, `TRUNCATE TABLE all_active_current` was submitted by connection `942756`.
2. `TRUNCATE` was blocked waiting for an exclusive metadata lock until **05:12:19 UTC (7,133.32 seconds)**.
3. While `TRUNCATE` waited, 11 distinct `SELECT` statements from client IP `10.21.1.253` requested shared metadata read locks on `all_active_current`.
4. MySQL's metadata lock subsystem placed the `TRUNCATE` at the head of the lock queue and blocked all subsequent `SELECT` statements.
5. At **05:12:19 UTC**, the exclusive lock was granted and `TRUNCATE` finished.
6. Exactly 4 seconds later at **05:12:23 UTC**, all 11 waiting `SELECT` statements logged their completion simultaneously.

#### The Lock Holder Dilemma: Is Connection 941032 Proven?
* **Evidence Regarding Connection 941032:**
  * Connection `941032` (User `chainxydata_stg` from IP `10.2.0.4`) was executing:
    ```sql
    SELECT runID, MIN(Period), MAX(Period), COUNT(DISTINCT Period), COUNT(*), MAX(id) 
    FROM all_active_current GROUP BY runID;
    ```
  * Query started at **03:02:00 UTC** and completed at **03:18:18 UTC (978.5 seconds)**.
  * Therefore, between **03:13:25 UTC** (when `TRUNCATE` arrived) and **03:18:18 UTC**, connection `941032` was actively reading `all_active_current` and holding `MDL_SHARED_READ`.
* **The Missing Gap (03:18:18 UTC to 05:12:19 UTC):**
  * Connection `941032`'s query finished at **03:18:18 UTC**.
  * The `TRUNCATE` remained blocked for an additional **1 hour and 54 minutes (until 05:12:19 UTC)**.
  * **Why did TRUNCATE continue to wait?**
    * *Possibility A:* Connection `941032` was in an explicit transaction (`BEGIN` or `autocommit=0`) and did not execute `COMMIT`/`ROLLBACK` until 05:12:19 UTC, retaining its shared metadata lock on `all_active_current`.
    * *Possibility B:* Another unlogged query or open transaction on another connection held `MDL_SHARED_READ`. (Queries taking less than `long_query_time` or idle connections do NOT appear in the slow query log).
    * *Possibility C:* MySQL's `metadata_locks` table in `performance_schema` is transient in-memory state; without a real-time snapshot captured at 04:00 UTC, the identity of the session holding the lock between 03:18 and 05:12 UTC **CANNOT BE PROVEN**.
* **Verdict:**  
  **ACTUAL LOCK HOLDER DURING 03:18–05:12 UTC IS NOT RECOVERABLE FROM SUPPLIED EVIDENCE.**  
  Connection 941032 is a strongly supported hypothesis for the initial blockage, but claiming it as the proven holder for the entire 2 hours is technically unverified.

