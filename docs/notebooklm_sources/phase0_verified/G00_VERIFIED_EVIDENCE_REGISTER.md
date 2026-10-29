# G00: Verified Evidence Register & Audit Reconciliation
**Scope:** Forensic Verification of Evidence, Correction of Speculative Claims & Confidence Classification  
**Target Host:** `csr-mysql8-flex-stg.mysql.database.azure.com` (MySQL 8.0.46-azure)  
**Investigation Period:** October 17 – October 24, 2026  
**Status:** PHASE 0 EVIDENCE VERIFICATION COMPLETE (READ-ONLY)

---

### 1. Evidence Inventory & Checksum Verification

All analyses are grounded strictly in the original raw telemetry and configuration artifacts. Duplicate files have been identified and deduplicated via MD5 hash comparison:

| Artifact Path | File Size (Bytes) | MD5 Checksum | Status / Classification | Notes |
| :--- | :--- | :--- | :--- | :--- |
| `server-logs/IT-Metrics/mysql-slow-csr-mysql8-flex-stg-2026101823.log` | 0 | `d41d8cd98f00b204e9800998ecf8427e` | **EMPTY** | Zero bytes; no query logged on 2026-10-18. |
| `server-logs/IT-Metrics/mysql-slow-csr-mysql8-flex-stg-2026101923.log` | 6,615,453 | `389b4a288fef1974358515004f94593c` | **UNIQUE RAW SLOW LOG** | 1,836 slow query entries. |
| `server-logs/IT-Metrics/mysql-slow-csr-mysql8-flex-stg-2026102023.log` | 2,397,422 | `de76d70be35ee9c495c9fbeb4c45b2b7` | **UNIQUE RAW SLOW LOG** | 2,662 slow query entries. Contains Oct 21 TRUNCATE event. |
| `server-logs/IT-Metrics/mysql-slow-csr-mysql8-flex-stg-2026102123.log` | 3,484,221 | `14abedcbab6fd20142fb9ccf0d37012e` | **UNIQUE RAW SLOW LOG** | 1,029 slow query entries. |
| `server-logs/IT-Metrics/mysql-slow-csr-mysql8-flex-stg-2026102223.log` | 2,012,119 | `3fcba41c818ac6f94dab1412da19efea` | **UNIQUE RAW SLOW LOG** | 2,571 slow query entries. Contains 10,823s scan. |
| `server-logs/IT-Metrics/New Logs/mysql-slow-*.log` (5 files) | Identical | Identical to above | **DUPLICATE DIRECTORY** | Byte-for-byte exact clones of the 5 files in `IT-Metrics/`. |
| `server-logs/IT-Metrics/server-logs-20261023_211951.log` | 36,936,629 | `d143b3dd65e941c818998bbcb6d7953d` | **APP CONTAINER LOG** | Streamlit `vis-portal-stg` application runtime log. |
| `server-logs/server-log.log` | 1,042 | `f5642fe32d24fcf00a0836b857ab9544` | **LOCAL BOOT LOG** | Python app boot log recording 6,066 ms `SELECT 1` warm ping. |
| `server-logs/restarts.log` | 166 | `375961ef768b75df1b3e9403f87d8482` | **LOCAL BOOT LOG** | Records two local process boots on Oct 24 (PID 28955, 29282). |
| `server-logs/Active connections.png` | 91,699 | `N/A (Image)` | **AZURE MONITOR CHART** | Metric: `Max Active Connections for csr-mysql8-flex-stg`. |
| `server-logs/CPU percentage.png` | 91,505 | `N/A (Image)` | **AZURE MONITOR CHART** | Metric: `Max Host CPU Percent for csr-mysql8-flex-stg`. |
| `server-logs/Storage IO percentage.png` | 117,256 | `N/A (Image)` | **AZURE MONITOR CHART** | Metric: `Max Storage IO Percent for csr-mysql8-flex-stg`. |
| `server-logs/HTTP 4xx.png` | 36,573 | `N/A (Image)` | **AZURE MONITOR CHART** | Metric: `Sum Http 4xx for vis-portal-stg`. |

---

### 2. Master Verification & Contradiction Resolution Matrix

| Claim / Metric | Previous Speculative Claim | Verified Evidence / Factual Ground Truth | Resolution / Verdict | Proof Source & Citation |
| :--- | :--- | :--- | :--- | :--- |
| **Total Slow Queries** | ~8,000 queries | **Exactly 8,098 entries** across 4 unique non-empty files | **CONFIRMED** | Sum of parsed entries from `2026101923` to `2026102223`. |
| **Total Slow Duration** | ~118 hours | **442,126.259 seconds = 122.81285 hours** | **CONFIRMED** | Summed `Query_time` fields across all 8,098 log entries. |
| **Total Rows Examined** | ~8.6 Billion | **8,704,656,696 rows examined** | **CONFIRMED** | Summed `Rows_examined` fields across all 8,098 log entries. |
| **ChainXY Share of Slow Queries** | 58% of server resource consumption | **1,424 queries, 71.839 cumulative hours (58.494% of slow query duration)** | **CONFIRMED (With Scope Clarification)** | Duration share only (`chainxydata_stg` 71.241h + `dwh_ro_stg` 0.598h = 71.839h); does NOT measure CPU or IOPS share. |
| **313 Active Connections Peak** | Attributed to Oct 21 TRUNCATE lock convoy | **Peak occurred on Monday, October 19 (UTC-05:00)**; on Oct 21 connections were fluctuating between 25 and 180 | **CONTRADICTED & CORRECTED** | Direct visual reading of `Active connections.png` X-axis. |
| **10,823s & 10,300s Worst Queries** | Claimed to cause or initiate the Oct 21 lockup | **Occurred on October 22 UTC** (`mysql-slow-2026102223.log`), **AFTER** the Oct 21 TRUNCATE event | **CONTRADICTED & CORRECTED** | Timestamps in `mysql-slow-csr-mysql8-flex-stg-2026102223.log`. |
| **Streamlit 180s Timeouts** | Claimed as direct impact of the Oct 21 database freeze | **Occurred on 04-Oct-2026 and 05-Oct-2026 IST**, more than two weeks prior to the Oct 21 incident | **CONTRADICTED & CORRECTED** | Lines 12429, 14321 in `server-logs-20261023_211951.log`. |
| **HTTP 4xx Spike (814 errors)** | Claimed as immediate symptom of Oct 21 TRUNCATE lock | **Occurred on/after Friday, October 23 (UTC-05:00)**; near zero on Oct 17–22 | **CONTRADICTED & CORRECTED** | Direct visual reading of `HTTP 4xx.png` X-axis. |
| **App 6-Second `SELECT 1` Ping** | Claimed as proof of engine freeze during lock convoy | **Occurred on 24-Oct-2026 at 03:07:20 AM IST**, three days after the Oct 21 lock event | **CONTRADICTED & CORRECTED** | Lines 1-4 in `server-log.log`. |
| **Original TRUNCATE Lock Holder** | Conclusively claimed as connection 941032 | **Connection 941032 finished at 03:18:18Z; TRUNCATE waited until 05:12:19Z**. Holder of lock during remaining 1h 54m is **UNKNOWN** | **STRONGLY SUPPORTED HYPOTHESIS ONLY** | `mysql-slow-2026102023.log` lines 4209 & 7845. No persistent MDL history exists. |
| **Effective Redo Log Capacity** | Claimed as 48 MB (`innodb_log_file_size = 48MB`) | **Live `innodb_redo_log_capacity = 536,870,912` (512 MB)**. In MySQL 8.0.30+, `innodb_log_file_size` is deprecated | **FALSIFIED & CORRECTED** | Live query `SHOW GLOBAL VARIABLES LIKE 'innodb_redo_log_capacity'`. |
| **Buffer Pool Hit Rate** | Claimed 99.7% cache miss rate due to 2GB RAM / 704GB disk | **Live lifetime Hit Rate is 99.86%** (483.8 Billion read requests vs 658.8 Million disk reads) | **FALSIFIED & CORRECTED** | Live status `Innodb_buffer_pool_read_requests` vs `Innodb_buffer_pool_reads`. |
| **`innodb_io_capacity = 200`** | Claimed Azure disk was capped at 200 IOPS | **`innodb_io_capacity` is MySQL background flush target, NOT Azure disk IOPS cap**. Disk IOPS depends on Azure storage SKU | **FALSIFIED & CORRECTED** | MySQL 8.0 Reference Manual §15.8.3.1. |
| **CIP `srv_answer` PK & Indexing** | Recommended adding `idx_survey_qcode (survey_id, qcode)` | **`srv_answer` PRIMARY KEY already starts with `(survey_id, qcode, ...)`**. Duplicate index is redundant | **FALSIFIED & CORRECTED** | Live `SHOW INDEX FROM cip_stg.srv_answer`. |
| **CIP 681 `GROUP BY` Rows Examined**| Claimed examining 12 Million rows per query | **Examined 29,409,649 rows COMBINED across 681 queries** (avg ~43,185 rows per wave query) | **CORRECTED** | Log aggregation across user `mohdsaeedafri` entries. |
| **CoreIQ News 341 `LIKE` Clauses** | Claimed across all 877 `shashank` queries | **Found in specific representative logged queries**, while other queries had varied keyword sets | **CORRECTED** | Inspection of SQL strings in slow logs for user `shashank`. |

---

### 3. Classification of Core Claims

* **CONFIRMED (Indisputable Raw Proof):**
  1. The 4 slow query logs contain exactly 8,098 entries, 122.81285 cumulative hours, and 8,704,656,696 rows examined.
  2. `chainxydata_stg` and `dwh_ro_stg` account for 71.839 hours (58.494% of logged slow duration).
  3. A Metadata Lock (MDL) convoy occurred on `all_active_current` on October 21 between 03:13:25Z and 05:12:23Z UTC, where `TRUNCATE TABLE` waited 7,133.321 seconds, and multiple SELECT queries on the same table completed simultaneously within 4 seconds of TRUNCATE completion.
  4. Table `all_active_log` has 491,470,817 rows and lacks a Primary Key (only `idx_runid` exists).
  5. Live MySQL engine has `innodb_buffer_pool_size = 2,147,483,648` (2.0 GB), `max_connections = 341`, and `innodb_redo_log_capacity = 536,870,912` (512 MB).

* **STRONGLY SUPPORTED (High Confidence Correlation):**
  1. High disk I/O saturation (100% Storage IO Percent flatline) on Oct 20–21 and Oct 22–23 was heavily exacerbated by multi-million row table scans from `all_active_py` deep pagination and unindexed `all_active_log` queries.
  2. The MDL wait on `all_active_current` was initiated by a long-running reader holding `MDL_SHARED_READ` at or before 03:13:25Z UTC on October 21.

* **HYPOTHESIS ONLY (Unverified):**
  1. Connection 941032 was the sole or primary lock holder that blocked TRUNCATE for the entire 2 hours. (It completed its logged query at 03:18:18Z; whether it held an open transaction or another unlogged session held the lock is unproven).
  2. CIP 4-worker publisher execution directly overlapped with the Oct 21 TRUNCATE incident. (CIP slow queries on `srv_answer` were logged predominantly on Oct 19, 20, and 22, but exact thread execution logs during the 03:13–05:12Z window require host scheduler audit).

* **CONTRADICTED (Falsified by Evidence):**
  1. *Claim:* The 313 active connection spike was caused by the Oct 21 TRUNCATE lock convoy. *Correction:* Chart shows peak was on Monday Oct 19.
  2. *Claim:* The 10,823s and 10,300s queries on `all_active_log` initiated the Oct 21 TRUNCATE lockup. *Correction:* Those queries ran on Oct 22.
  3. *Claim:* Streamlit 180s [STORE_MAP] errors occurred during the Oct 21 lockup. *Correction:* Those errors occurred on Oct 4–5.
  4. *Claim:* Azure server effective redo log is 48 MB. *Correction:* Live variable proves `innodb_redo_log_capacity = 512 MB`.
  5. *Claim:* Server has 99.7% cache misses. *Correction:* Status counters prove 99.86% buffer pool hit rate.
  6. *Claim:* `srv_answer` needs `idx_survey_qcode`. *Correction:* PK already starts with `(survey_id, qcode, ...)`.

* **STILL UNKNOWN (Requires External Data from IT/Azure):**
  1. Actual Azure VM SKU, provisioned compute tier, and disk provisioning type (Burstable vs General Purpose vs Memory Optimized).
  2. Minute-level UTC Azure Monitor metrics CSV (CPU, disk IOPS, network, latency).
  3. Exact identity of the session holding the metadata lock on `all_active_current` between 03:18:18Z and 05:12:19Z UTC on October 21.

