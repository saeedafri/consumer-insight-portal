# G02: Azure Infrastructure, Database Schema & Query Plan Forensics
**Scope:** Live Azure/MySQL System Parameters, Effective Redo/Buffer Pool Truth, Safe Table Metadata & Non-Executing Optimizer Plans  
**Host:** `csr-mysql8-flex-stg.mysql.database.azure.com` (MySQL 8.0.46-azure)  
**Verification Date:** 2026-10-25 23:35 UTC (Live Read-Only Query Session)

---

### 1. Azure Flexible Server Infrastructure Reality vs Assumptions

#### A. Verified Live MySQL System Parameters:
Directly queried from `SHOW GLOBAL VARIABLES` and `SHOW GLOBAL STATUS` on 2026-10-25:

| System Parameter | Live Verified Value | Interpretation & Impact | Previous Claim Falsified / Corrected |
| :--- | :--- | :--- | :--- |
| `VERSION()` | `8.0.46-azure` | Source distribution MySQL 8.0 Enterprise on Azure. | Confirmed. |
| `innodb_buffer_pool_size` | `2,147,483,648` (2,048 MB = **2.0 GB**) | Total RAM allocated to caching data pages. | Confirmed. |
| `innodb_buffer_pool_instances`| `8` | 256 MB per buffer pool instance. | Confirmed. |
| `innodb_redo_log_capacity` | `536,870,912` (**512 MB**) | **Effective Redo Log Storage** in MySQL 8.0.30+. | **FALSIFIED PREVIOUS CLAIM OF 48 MB**. Effective redo log is 512 MB. |
| `innodb_log_file_size` | `50,331,648` (48 MB) | Deprecated in MySQL 8.0.30; superseded by dynamic redo capacity. | Parameter exists for backward compatibility only. |
| `innodb_io_capacity` | `200` | Target background page flush rate for InnoDB cleaner threads. | **DOES NOT MEAN AZURE DISK IS 200 IOPS**. It is an engine throttle setting. |
| `innodb_io_capacity_max` | `2,000` | Maximum flush rate during aggressive checkpoint flushing. | Confirmed. |
| `max_connections` | `341` | Absolute connection ceiling before `ERROR 1040`. | Confirmed. (Peak was 313, 91.8% capacity). |
| `lock_wait_timeout` | `31,536,000` (1 Year) | Maximum time non-InnoDB locks (including MDL) will wait. | Dangerous default: allows metadata lock queues to hang indefinitely. |
| `innodb_lock_wait_timeout` | `50` (Seconds) | Maximum time InnoDB row locks will wait before rollback. | Default setting. |
| `wait_timeout` | `28,800` (8 Hours) | Time before idle sleep connections are closed. | Contributes to connection buildup if apps do not close sessions. |
| `Innodb_buffer_pool_read_requests`| `483,849,733,879` (483.8 Billion) | Total logical read requests from memory. | Proves high workload volume over uptime. |
| `Innodb_buffer_pool_reads` | `658,817,697` (658.8 Million) | Physical reads that could not be satisfied by memory. | Physical disk page misses. |
| **Cumulative Buffer Pool Hit Rate**| **99.86% Hit Rate** | `(1 - 658.8M / 483.8B) * 100 = 99.86%` | **FALSIFIED PREVIOUS CLAIM OF 99.7% CACHE MISSES**. Working set hit rate is high; bulk scans cause episodic misses. |

#### B. What is Still Missing from Infrastructure (Actionable IT Request):
* The exact Azure Compute SKU (e.g. `Standard_B2s` vs `Standard_B2ms` vs `Standard_D2ds_v4`), whether the vCPUs are Burstable with CPU credits, whether Storage Auto-grow/Auto-IOPS is enabled, and the provisioned disk tier (e.g. Premium SSD P10 vs P20 vs Standard SSD) **CANNOT be queried from MySQL variables**.
* **Actionable IT Ticket Required:**
  ```bash
  # Command for Azure Cloud Administrator:
  az mysql flexible-server show \
    --resource-group <rg-name> \
    --name csr-mysql8-flex-stg \
    --query "{sku:sku.name, tier:sku.tier, cores:sku.capacity, storageGb:storage.storageSizeGb, iops:storage.iops, autoScaleIops:storage.autoScaleIops}" \
    --output json
  ```

---

### 2. Table Design & Index Forensic Verification

#### A. Table `chainxydata_stg.all_active_log` (The 217 GB Offender)
* **Approximate Physical Size:** **216,975.98 MB (216.97 GB data)**, **9,163.98 MB (9.16 GB index)** across **491,470,817 rows**.
* **Index Structure (`SHOW INDEX`):**
  * `idx_runid` on `runid` (`Seq: 1`, `Cardinality: 14,284`).
  * **PRIMARY KEY: NONE.**
  * **UNIQUE KEY: NONE.**
* **Column `id` Status (`information_schema.COLUMNS`):**
  * Data Type: `int(11)`, `IS_NULLABLE: NO`, `COLUMN_KEY: ''`, `EXTRA: ''`.
* **Critical Finding on Suggesting a Primary Key:**
  * While `id` is `NOT NULL`, it has **no uniqueness constraint**.
  * In active store logging, where records are logged iteratively per run (`runid`), whether `id` represents an autoincrement sequence or an upstream store identifier that repeats across runs is **UNVERIFIED**.
  * **Safety Mandate:** Do NOT execute `ALTER TABLE ... ADD PRIMARY KEY (id)` without first verifying uniqueness via ETL code logic. A composite key `(runid, Period, id)` or adding an independent auto-increment column is required to avoid breaking data integrity.

#### B. Table `cip_stg.srv_answer` (The CIP Serving Cube)
* **Approximate Physical Size:** **1,217.97 MB data**, **0.00 MB secondary indexes**, **12,061,859 rows**.
* **Index Structure (`SHOW INDEX`):**
  * `PRIMARY KEY`: Composite on `(survey_id, qcode, item_id, option_id, respondent_id)`.
  * Secondary Indexes: **NONE (0.00 MB)**.
* **Critical Correction on Indexing Recommendations:**
  * Previous audits recommended: `ALTER TABLE srv_answer ADD INDEX idx_survey_qcode (survey_id, qcode);`.
  * **This recommendation was false and redundant**: The existing Clustered Primary Key already begins with `(survey_id, qcode, ...)`. In MySQL B-Trees, any leftmost prefix of an index is fully usable for lookups. Adding a secondary index on `(survey_id, qcode)` would be an exact duplicate that wastes disk space and slows down ETL inserts.
  * The actual reason queries on `srv_answer` were slow was NOT a missing `(survey_id, qcode)` filter index; it was the **10-dimension `GROUP BY`** requiring on-disk temporary tables (`Using temporary`).

#### C. Table `cip_stg.cip_answer` (The Raw Answer Store)
* **Approximate Physical Size:** **2,641.00 MB data**, **3,347.95 MB index (Total 5.98 GB)** across **27,796,732 rows**.
* **Index Structure (`SHOW INDEX`):**
  * `PRIMARY`: `(answer_id)`
  * `uq_answer`: `(respondent_id, field_id)`
  * `fk_answer_field`: `(field_id)`
  * `ix_answer_cover`: `(survey_id, field_id, value_code, respondent_id)`
* **Performance Mechanism:** Fully indexed for survey ingestion, but massive row volume (27.8M rows) means multi-table `UPDATE` joins without partition pruning hold extensive row locks and generate high redo log traffic.

---

### 3. Non-Executing Query Optimizer Plans (`EXPLAIN FORMAT=JSON`)

All execution plans below were captured using non-executing `EXPLAIN FORMAT=JSON` on the live database. No expensive table scans or full executions were performed.

#### Plan 1: `SELECT MAX(id) FROM chainxydata_stg.all_active_log;`
```json
{
  "select_id": 1,
  "cost_info": {
    "query_cost": "62447049.70"
  },
  "table": {
    "table_name": "all_active_log",
    "access_type": "ALL",
    "rows_examined_per_scan": 491470817,
    "rows_produced_per_join": 491470817,
    "filtered": "100.00",
    "cost_info": {
      "read_cost": "13299968.00",
      "eval_cost": "49147081.70",
      "prefix_cost": "62447049.70",
      "data_read_per_join": "10T"
    },
    "used_columns": ["id"]
  }
}
```
* **Optimizer Mechanism:** `access_type: ALL`. Cost: **62.4 Million**.
* **Forensic Reality:** Because `id` is unindexed, MySQL cannot read the maximum leaf node of a B-Tree. It must sequentially scan all 491.4 million records from disk, explaining the **10,300.82 second (2.86 hour)** logged runtime.

#### Plan 2: 3-Hour Partition Verification Query on `all_active_log`
```sql
EXPLAIN FORMAT=JSON 
SELECT CASE WHEN Period < '2026-01-01' THEN 'PY' ELSE 'CY' END AS part, 
       COUNT(*) AS rows_, COUNT(DISTINCT id) AS distinct_ids, MIN(id), MAX(id) 
FROM chainxydata_stg.all_active_log WHERE runID = 20 GROUP BY 1;
```
```json
{
  "select_id": 1,
  "cost_info": {
    "query_cost": "111594132.13"
  },
  "grouping_operation": {
    "using_filesort": true,
    "cost_info": {
      "sort_cost": "49147082.43"
    },
    "table": {
      "table_name": "all_active_log",
      "access_type": "ALL",
      "possible_keys": ["idx_runid"],
      "rows_examined_per_scan": 491470817,
      "filtered": "10.00",
      "cost_info": {
        "read_cost": "57532341.46",
        "eval_cost": "4914708.24",
        "prefix_cost": "62447049.70"
      },
      "attached_condition": "(`chainxydata_stg`.`all_active_log`.`runid` = 20)"
    }
  }
}
```
* **Optimizer Mechanism:** Query cost: **111.5 Million**. `using_filesort: true`.
* **Forensic Reality:** Although `idx_runid` is listed in `possible_keys`, MySQL’s cost model chose a full table scan (`access_type: ALL`) because the secondary index did not cover `Period` or `id`. It scanned 491M rows and performed an on-disk filesort, explaining the **10,823.47 second (3.01 hour)** logged runtime.

#### Plan 3: Naive Pagination on `all_active_py`
```sql
EXPLAIN FORMAT=JSON 
SELECT * FROM chainxydata_stg.all_active_py ORDER BY id LIMIT 50000 OFFSET 20500000;
```
```json
{
  "select_id": 1,
  "cost_info": {
    "query_cost": "3128304.65"
  },
  "ordering_operation": {
    "using_filesort": false,
    "table": {
      "table_name": "all_active_py",
      "access_type": "index",
      "key": "PRIMARY",
      "key_length": "4",
      "rows_examined_per_scan": 20550000,
      "filtered": "100.00"
    }
  }
}
```
* **Optimizer Mechanism:** `access_type: index`, `rows_examined_per_scan: 20,550,000`.
* **Forensic Reality:** Proves mathematically that `OFFSET 20500000` forces MySQL to traverse 20.55 million index entries to discard them before returning 50,000 rows, explaining why 521 batches accumulated 17.96 hours of pure disk reading.

#### Plan 4: CIP 10-Dimension GROUP BY on `srv_answer`
```sql
EXPLAIN FORMAT=JSON 
SELECT survey_id, qcode, item_id, option_id, gender, age_band, generation, 
       income_band, census_region, urbanicity, COUNT(*) 
FROM cip_stg.srv_answer WHERE survey_id IN (262) 
GROUP BY survey_id, qcode, item_id, option_id, gender, age_band, generation, 
         income_band, census_region, urbanicity;
```
```json
{
  "select_id": 1,
  "grouping_operation": {
    "using_temporary_table": true,
    "using_filesort": false,
    "table": {
      "table_name": "srv_answer",
      "access_type": "ref",
      "key": "PRIMARY",
      "used_key_parts": ["survey_id"],
      "key_length": "4",
      "ref": ["const"],
      "rows_examined_per_scan": 639576,
      "filtered": "100.00"
    }
  }
}
```
* **Optimizer Mechanism:** `key: PRIMARY` (leftmost part `survey_id` used), `using_temporary_table: true`.
* **Forensic Reality:** Because the `GROUP BY` clause includes 6 demographic VARCHAR columns not present in index sort order, MySQL cannot perform stream aggregation. It must create an on-disk temporary table (`using_temporary_table: true`). When `etl/publish.py` executes 4 workers in parallel, this creates 4 concurrent multi-megabyte temporary tables on disk.

#### Plan 5: Matomo Expiry Arithmetic Expression
* **SQL:** `DELETE FROM matomo_session WHERE modified + lifetime < '1792781510';`
* **Mechanism:** In MySQL, evaluating an arithmetic expression (`modified + lifetime`) across two table columns prevents index range scanning. The optimizer is forced into `access_type: ALL` with row-level locks on every session record.

