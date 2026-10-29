# G03: Product Code, Job Mapping & Ownership Register
**Scope:** High-Impact SQL to Code Repository, Job Scheduler, Source IP, and Responsible Technical Role Mapping  
**Investigation Principle:** Strict Attribution Standard — DB username alone is NOT sufficient proof of human individual identity. Where scheduler, git author, or job trace is unconfirmed, status is marked as **HUMAN OWNER UNVERIFIED**.

---

### 1. High-Impact SQL to Codebase & Job Mapping

| Product / Platform | Database Account & Source IP | Target Schema & Table | Precise Query Fingerprint | Observed Count & Duration | Repository File, Function & Line | Trigger / Scheduler / Job Name | Business Reason for Execution | Responsible Technical Role |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **SIP (Store Intelligence Platform)** | `chainxydata_stg` @ `10.21.1.253` | `chainxydata_stg.all_active_current` | `TRUNCATE TABLE all_active_current;` | 1 query, **7,133.32s (1.98 hrs)** | `scripts/store_footprint_etl.py` / Data Pipeline | Weekly Store Data Refresh Cron / Airflow | Drops existing store slice before loading fresh weekly geocoded store data. | Data Engineering / Store Data Operations (HUMAN OWNER UNVERIFIED) |
| **SIP (Store Intelligence Platform)** | `chainxydata_stg` @ `10.2.0.4` | `chainxydata_stg.all_active_log` | `SELECT CASE WHEN Period < '2026-01-01'... FROM all_active_log WHERE runID=20` | 1 query, **10,823.47s (3.01 hrs)** | `scripts/all_active_partition_check.py` | Post-Ingestion Audit Job / Manual Data Audit | Validates row counts and distinct IDs between Current Year and Prior Year partitions. | Analytics Engineering / QA (HUMAN OWNER UNVERIFIED) |
| **SIP (Store Intelligence Platform)** | `chainxydata_stg` @ `10.2.0.4` | `chainxydata_stg.all_active_log` | `SELECT MAX(id) FROM all_active_log;` | 1 query, **10,300.82s (2.86 hrs)** | `scripts/sync_active_stores.py` | Ingestion Batch Pre-flight Check | Determines highest existing primary surrogate ID to assign next batch offset. | Data Engineering (HUMAN OWNER UNVERIFIED) |
| **SIP (Store Intelligence Platform)** | `chainxydata_stg` @ `10.2.0.4` | `chainxydata_stg.all_active_py` | `SELECT * FROM all_active_py ORDER BY id LIMIT 50000 OFFSET N;` | 521 queries, **64,656s (17.96 hrs)** | `scripts/export_py_stores.py` / Table Sync Job | Multi-batch Data Sync / Migration Worker | Iteratively pages through prior-year store data to sync to downstream cache. | Data Engineering (HUMAN OWNER UNVERIFIED) |
| **CIP (Consumer Insight Portal)** | `mohdsaeedafri` @ `10.2.0.4` | `cip_stg.srv_answer` | `SELECT survey_id, qcode, item_id, option_id, {cuts}, COUNT(*) FROM srv_answer GROUP BY ...` | 681 queries, **7,821.3s (2.17 hrs)** | `app/data/payloads.py:406` (`question_cuts`) via `etl/publish.py:121` (`wave`) | Publication Worker / `python -m etl.publish` | Pre-computes 2-cut crosstabs for all questions in fresh survey waves to serve static JSON. | Backend Engineering / Survey Platform (HUMAN OWNER UNVERIFIED) |
| **CIP (Consumer Insight Portal)** | `mohdsaeedafri` @ `10.2.0.4` | `cip_stg.cip_answer` | `UPDATE cip_answer a JOIN cip_field f ... SET a.value_label = NULL WHERE survey_id = ...` | 103 queries, **2,230.7s (37.2 min)** | `etl/run_pipeline.py:301-311` | Weekly Ingestion / Data Harmonization Job | Resets invalid or unmapped value labels for survey answers during wave ingestion. | Data Engineering / Survey Platform (HUMAN OWNER UNVERIFIED) |
| **CoreIQ / Market Data** | `shashank` @ `10.2.0.4` | `coresight_market_data_stg.coreiq_av_market_news_sentiment` | `SELECT ... FROM coreiq_av_market_news_sentiment WHERE ticker = '...' AND (title LIKE ... [120+ LIKEs])` | 877 queries, **14,406.2s (4.00 hrs)** | Financial News Sentiment Classifier Job | Automated News Tagger / Analyst Screener | Classifies financial news articles against retail and banking keyword taxonomy. | Market Data Engineering / Quantitative Analyst (HUMAN OWNER UNVERIFIED) |
| **Coresight Website (WordPress)** | `wp_stage*` @ `10.2.1.5` | `wp_stage.csr_posts` | `SELECT csr_posts.ID FROM csr_posts WHERE ... (post_title LIKE '%...' OR post_content LIKE '%...')` | 2,116 queries, **87,480s (24.3 hrs)** | WordPress Core Search / `wp-includes/query.php` | Front-end Visitor / Bot Search Requests | Performs free-text article and research report search across published posts. | Web Operations / CMS Platform (AUTOMATED WEB TRAFFIC) |
| **Matomo Web Analytics** | `matomo` @ `10.2.1.14` | `matomo_db_stg.matomo_session` | `DELETE FROM matomo_session WHERE modified + lifetime < '...';` | 511 queries, **15,787.9s (4.39 hrs)** | Matomo Core Session Pruner / `core/Session.php` | Scheduled Cron (`archive.php` / session purger) | Deletes expired web visitor browsing sessions from transactional storage. | Web Analytics Operations (SYSTEM CRON) |

---

### 2. Operational Reality of CIP 4-Worker Publisher & Session Memory

#### A. Presence in Code vs Actual Execution Truth:
* In `etl/publish.py`:
  ```python
  def build(root: Path = ROOT, jobs: int = 4) -> Path:
      ...
      with ThreadPoolExecutor(max_workers=jobs) as pool:
          size += sum(pool.map(wave, fresh))
  ```
* In `app/core/database.py`:
  ```python
  ETL_SESSION = ("SET SESSION sort_buffer_size = 16777216, join_buffer_size = 16777216,"
                 " tmp_table_size = 536870912, max_heap_table_size = 536870912")
  ```
* **Forensic Verification:**
  * **Was `publish.py` active during the incident period?**
    * **YES.** In the slow query logs for `mohdsaeedafri` from client `10.2.0.4`, the query `SELECT survey_id, qcode, item_id, option_id, ... COUNT(*) FROM srv_answer ... GROUP BY ...` appears **681 times** across Oct 19, Oct 20, and Oct 22. This query is generated exclusively by `payloads.py:406` during wave crosstab publishing.
  * **Did `tmp_table_size = 512 MB` immediately allocate 2 GB of physical RAM?**
    * **NO.** In MySQL InnoDB, `tmp_table_size` is an **upper ceiling threshold**, not an upfront allocation. MySQL allocates memory dynamically for temporary tables in memory (using the TempTable engine). However, when a query's temporary table exceeds `tmp_table_size` (or when the global `temptable_max_ram` is reached), MySQL writes the temporary table to physical disk (`Created_tmp_disk_tables`).
    * Therefore, the high `tmp_table_size` allowed each session to buffer up to 512 MB in RAM before spilling to disk, increasing memory pressure on the 2 vCPU / 4–8 GB host and contributing to page evictions.

---

### 3. Application Latency, 180s Timeouts & HTTP 4xx Causal Reconciliation

#### A. Streamlit 180s Timeouts (`[STORE_MAP][ERROR]`):
* **Observed Data:** Logged in `server-logs-20261023_211951.log:12429` on **04-Oct-2026 06:58:37 PM IST** and **05-Oct-2026 07:07:49 PM IST**.
* **Causal Link:** **NO DIRECT LINK TO THE OCTOBER 21 TRUNCATE INCIDENT.**
  * The Oct 4–5 timeouts occurred 16 days prior to the Oct 21 lock event.
  * Root Cause: Streamlit's `store_footprint.py` executes query `active_full`, which attempts to fetch **506,895 raw records** over the network into Python memory. During periods of high network latency or database read delays, the query exceeded the hardcoded 180-second application timeout.

#### B. Post-Incident HTTP 4xx Spike (814 Errors):
* **Observed Data:** `HTTP 4xx.png` shows near-zero 4xx errors from Oct 17 to Oct 22, with a sharp spike to **814 errors after Friday Oct 23 (UTC-05)**.
* **Causal Link:** **NO DIRECT CORRELATION TO THE OCTOBER 21 LOCKUP.**
  * The HTTP 4xx errors (client-side bad requests, expired sessions, or broken API tokens) occurred two days after the TRUNCATE incident had fully resolved. They represent an independent front-end session or routing issue.

#### C. `active_full` 225-Second Latency Spike (Oct 20):
* **Observed Data:** Logged in `server-logs-20261023_211951.log:116187` on **20-Oct-2026 02:23:34 PM IST (08:53:34 UTC)**:
  `query=active_full 225629ms rows=506895`.
* **Causal Link:** **STRONGLY CORRELATED WITH OCTOBER 20 STORAGE I/O SATURATION.**
  * On Oct 20, Storage IO Percent hit 100% flatline due to simultaneous background scans from `all_active_py` pagination and WordPress queries. Fetching 506k unaggregated rows from a disk-throttled MySQL instance took 225.6 seconds.

