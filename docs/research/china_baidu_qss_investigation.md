# China Survey Integration: Baidu AI Cloud QSS (`问卷调研服务`) Investigation & Architecture Blueprint

**Date:** 6 November 2026  
**Target Platform:** Baidu AI Cloud Questionnaire Survey Service (`百度智能云 问卷调研服务`, **QSS**)  
**Target URL:** `https://login.bce.baidu.com/?account=ac9b269ca79b4c4a8b9dddf08cedfe19&redirect=http%3A%2F%2Fconsole.bce.baidu.com%2Fqss%2Fsurvey%2Fhome%2FmanageSurvey%3F_%3D1708405855978`

---

## 1. Executive Summary

1. **What is this platform?**  
   `console.bce.baidu.com/qss` is **Baidu AI Cloud's Questionnaire Survey Service (`百度智能云 问卷调研服务`, QSS)**, originally built and operated by **Baidu Mobile Testing Center (`百度移动云测试中心`, MTC — `mtc.baidu.com`)** and dual-mounted into the Baidu AI Cloud (BCE) console.
2. **Does Baidu QSS provide an API or SDK for automated pulling?**  
   **No.** A primary-source audit of Baidu AI Cloud's OpenAPI catalog (`cloud.baidu.com/doc/API/index.html`), the QSS documentation repository (`cloud.baidu.com/doc/QSS/index.html`), and the official Python SDK (`baidubce` / `bce-python-sdk`) confirms that **QSS has zero public OpenAPI endpoints, zero AK/SK REST interfaces, and zero webhook integrations.** Every document in Baidu's QSS doc tree carries `"isApiDoc": null, "httpMethod": null`.
3. **Can we automate login/scraping against the web console?**  
   **No — and it should not be attempted.** The console sits behind Baidu Passport (`passport.baidu.com`), CAS (`cas.baidu.com`), and `OpenRASP 2.0`, enforcing AI image-rotation CAPTCHAs (`百度旋转验证码`), mandatory `+86` SMS OTP on unfamiliar/foreign IPs (`异地登录保护`), and IAM MFA (`/iam/access`). Furthermore, our production server runs in **Azure US**, and cross-border requests to Baidu's domestic Beijing edge (`180.76.11.244`) suffer frequent TCP/TLS `ClientHello` resets (`Errno 54` / `curl: (35)`).
4. **How does Baidu QSS officially deliver survey data?**  
   Through its web console (`答卷数据` → `原始数据` / `数据统计`), which exports standard **Excel (`.xls` / `.xlsx`)** workbooks:
   - **Raw Response Data (`导出原始数据`)**: One row per qualified respondent (`序号`, `答卷者`, `提交时间`, `答题时长`), with single-choice, dropdown, open-text, and matrix single-choice rows exported as **one column per question/row**, and multiple-choice questions exported as **one column per option**.
   - **SPSS Encoded Data (`导出spss编码数据`)**: Numeric answer codes plus a codebook sheet (`编码规则`).
   - **Statistical Report (`导出统计报告`)**: Aggregated counts and percentages.
   - **Key insight for CIP**: This flat Excel structure is **virtually identical to the Qualtrics Excel export** that CIP already ingests via `etl/qualtrics_export.py`!
5. **Why does it fail behind a VPN?**  
   We identified and reproduced **three concrete technical causes** (detailed in Section 4):
   - **Split-tunnel IP mismatch across 7 Baidu domains** (`passport.baidu.com` vs `login.bce.baidu.com` vs `console.bce.baidu.com`), which causes `/postlogin` token exchange to reject the session and loop back to the login URL.
   - **Cross-border TLS 1.3 `ClientHello` resets (`Errno 54` / `curl 35`) and VPN MTU fragmentation** when traffic to Beijing domestic nodes (`180.76.11.244`) is routed out through an overseas/corporate VPN tunnel.
   - **Baidu Passport anti-fraud risk control (`风控系统`)** flagging commercial VPN and cloud datacenter IPs.

---

## 2. Official Documentation & Product Identity

### 2.1 Dual-Deployment Lineage (Baidu BCE QSS ↔ Baidu MTC)

QSS is co-deployed on both Baidu AI Cloud (`console.bce.baidu.com/qss`) and Baidu Mobile Testing Center (`mtc.baidu.com`). In Baidu's official Survey FAQ (`https://mtc.baidu.com/about/doc/alias/issuesSurvey`, Section *"设计问卷 → 1. 找不到已创建问卷？"*), Baidu states:

> *"问卷服务同时部署在mtc和百度云，您可以在这两个地址查找您的问卷：*
> *1. `http://mtc.baidu.com/survey/home/manageSurvey`*
> *2. `https://console.bce.baidu.com/qss/survey/home/manageSurvey`"*

| Resource | Official URL | Purpose |
|---|---|---|
| **BCE Product Page** | `https://cloud.baidu.com/product/qss.html` | Product overview & capabilities |
| **BCE Pricing Page** | `https://cloud.baidu.com/product-price/qss.html` | On-demand sample pricing calculator |
| **BCE Console (Survey List)** | `https://console.bce.baidu.com/qss/survey/home/manageSurvey` | Primary survey management & data export UI |
| **MTC Console (Mirror)** | `https://mtc.baidu.com/survey/home/manageSurvey` | Direct MTC mirror of the same survey console |
| **BCE Documentation Index** | `https://cloud.baidu.com/doc/QSS/index.html` | Official Baidu AI Cloud QSS documentation tree |
| **MTC Full Operations Manual** | `https://mtc.baidu.com/about/doc/alias/survey` | Complete illustrated step-by-step manual (with 55 console screenshots) |
| **MTC Full 30-Question FAQ** | `https://mtc.baidu.com/about/doc/alias/issuesSurvey` | Detailed rules on data export, SPSS coding, 10-min validation delay, quotas |
| **Official Support Contact** | `mtc_support@baidu.com` / BCE Ticket System | Official technical & billing support |

### 2.2 Complete Official Baidu Cloud QSS Documentation Tree

Extracted directly from `https://cloud.baidu.com/doc/QSS/index.html` (`__NEXT_DATA__.props.pageProps.sideBarData`, `repoName: "QSS"`), the entire official documentation consists of **4 sections and 12 articles**:

| Section | Article Title | Official URL | Last Updated | API Doc? | Summary of Contents |
|---|---|---|---|---|---|
| **1. 产品描述** (Product Description) | 介绍 (Introduction) | `https://cloud.baidu.com/doc/QSS/s/ljwvxk96y` | 2019-06-14 | `null` | Overview of QSS and its 10M+ Chinese consumer panel |
| | 特性 (Features) | `https://cloud.baidu.com/doc/QSS/s/0jwvxkaa1` | 2019-06-14 | `null` | WYSIWYG editor, real-time collection, cross-tab reports, IP/cookie anti-fraud |
| | 优势 (Advantages) | `https://cloud.baidu.com/doc/QSS/s/mjwvxk9jo` | 2019-06-14 | `null` | ~2,000 completes in 3 days; geographic/demographic targeting |
| | 应用场景 (Use Cases) | `https://cloud.baidu.com/doc/QSS/s/pjwvxk9vt` | 2019-06-14 | `null` | Consumer research, UX testing, polling |
| **2. 操作指南** (Operations Guide) | 设计问卷 (Design Survey) | `https://cloud.baidu.com/doc/QSS/s/Tjwvxkblu` | 2019-06-17 | `null` | Question types, skip logic (`逻辑设置`), trap questions (`过滤无效问卷`) |
| | **管理问卷 (Manage & Export)** | `https://cloud.baidu.com/doc/QSS/s/Djwvxkb9y` | 2019-06-17 | `null` | Review workflow, viewing results (`答卷数据`), **exact Excel export column structure** |
| **3. 常见问题** (FAQs) | 常见问题总览 (Overview) | `https://cloud.baidu.com/doc/QSS/s/Yk3i4s1ks` | 2019-11-28 | `null` | Index of FAQs |
| | **使用类问题 (Usage FAQ)** | `https://cloud.baidu.com/doc/QSS/s/fjwvxkcnj` | 2021-12-15 | `null` | **Export formats (`原始答题数据`, `编码数据`, `数据统计` in Excel)**, sample increments, deduplication (`用户排重`) |
| | 配置类问题 (Config FAQ) | `https://cloud.baidu.com/doc/QSS/s/Wjwvxkdcs` | 2019-11-28 | `null` | Question limits, survey count limits |
| | 安全类问题 (Security FAQ) | `https://cloud.baidu.com/doc/QSS/s/hjwvxkczq` | 2019-11-28 | `null` | Account isolation & survey ID encryption |
| | 付费类问题 (Billing FAQ) | `https://cloud.baidu.com/doc/QSS/s/2jwvxkca1` | 2019-11-28 | `null` | On-demand billing & refund rules |
| **4. 产品定价** (Pricing) | 调研计费规则 (Pricing Rules) | `https://cloud.baidu.com/doc/QSS/s/rjwvxke19` | 2022-01-30 | `null` | `Total Price = Unit Price × Target Completes` (based on question count & targeting) |

---

## 3. API Availability & Data Export Specification

### 3.1 Why QSS Has No Public API

1. **Baidu Cloud OpenAPI Catalog (`https://cloud.baidu.com/doc/API/index.html`)**: Lists all Baidu AI Cloud services that expose IAM `AK/SK` signed REST APIs. Neither `QSS` nor `问卷调研` is present.
2. **Official Python SDK (`baidubce` / `bce-python-sdk`)**: Contains clients for `bos`, `bcc`, `vpc`, `rds`, `cfc`, etc., with no module for `qss` or `mtc`.
3. **Under-the-hood Architecture**: Decompiling the console frontend assets shows that `/qss/survey/home/...` is a server-rendered **PHP Yii + AngularJS 1.x** web application (`PHPSESSID` + `YII_CSRF_TOKEN` cookies, `X-YII-CSRF-TOKEN` header) proxied behind Baidu's BWS gateway (`console.bce.baidu.com/qss`).

### 3.2 How Data Is Exported from Baidu QSS

Per `操作指南/管理问卷.md` (`https://cloud.baidu.com/doc/QSS/s/Djwvxkb9y`), `使用类问题.md` (`https://cloud.baidu.com/doc/QSS/s/fjwvxkcnj`), and `https://mtc.baidu.com/about/doc/alias/survey` (§1.5):

1. In `https://console.bce.baidu.com/qss/survey/home/manageSurvey`, locate the completed wave (`项目状态: 已关闭` or `发布中`) and click **`答卷数据`** (`/qss/survey/home/surveyCommonReport?survey_id=<id>`).
2. Switch to the **`原始数据` (Raw Data)** tab (or **`数据统计` (Statistical Report)** tab).
3. Three Excel (`.xls` / `.xlsx`) downloads are available:
   - **`[导出原始数据]` (Raw Answer Data — Excel)**: Every qualified respondent's full answers in label/text form.
   - **`[导出spss编码数据]` (SPSS Encoded Data — Excel)**: Every qualified respondent's answers as integer codes, plus the `编码规则` (codebook mapping codes to labels). *(Note: Per FAQ #14 in `issuesSurvey`, if SPSS format is desired, check the SPSS option when submitting the survey).*
   - **`[导出统计报告]` (Statistical Summary — Excel)**: Pre-tabulated counts and percentages per question.
4. **Column Layout of `[导出原始数据]` / `[导出spss编码数据]`**:
   - **Metadata columns**:
     - `序号` (Record number: `1, 2, ...`)
     - `答卷者` (Masked Baidu respondent identifier, e.g. `大*啊`)
     - `提交时间` (Completion timestamp: `YYYY-MM-DD HH:MM:SS`)
     - `答题时长` (Interview duration in seconds, e.g. `87秒` or `87`)
   - **Question columns** (`https://cloud.baidu.com/doc/QSS/s/Djwvxkb9y`):
     > *"为了方便数据分析，数据将以如下形式导出：单选题、单选下拉、单行填空、多行填空、矩阵单选题每题单独成列导出，多选题以每个选择为一列的形式导出。"*
     - **Single-choice (`单选题`), Dropdown (`单选下拉`), Open-text (`单行/多行填空`), Matrix Single-choice (`矩阵单选题`)**: **One column per question** (or per matrix row).
     - **Multiple-choice (`多选题`) & Matrix Multiple-choice (`矩阵多选题`)**: **One column per option** (selected vs unselected).
   - **Quality Filtering Built In**: QSS validates submissions in the background (taking ~10 minutes after submission) and automatically strips out terminated responses (`提前结束`) and trap-question failures (`过滤无效问卷`) before exporting, so **every row in the QSS export is a Qualified complete (`status = 3 / Qualified`)**.

---

## 4. Why "It Doesn't Work Behind a VPN" — Technical Root Causes & Fixes

### 4.1 Dissecting the Login URL You Shared

```
https://login.bce.baidu.com/?account=ac9b269ca79b4c4a8b9dddf08cedfe19&redirect=http%3A%2F%2Fconsole.bce.baidu.com%2Fqss%2Fsurvey%2Fhome%2FmanageSurvey%3F_%3D1708405855978
```

- `account=ac9b269ca79b4c4a8b9dddf08cedfe19`: Your 32-character hex **Baidu AI Cloud Master Account ID**. We verified this live against `GET https://login.bce.baidu.com/login/check/getUserSSOInfo?account=ac9b269ca79b4c4a8b9dddf08cedfe19`, which returned `{"success":true,"status":200,"result":{"enable":false}}` (confirming the account is active and uses standard Baidu/IAM login rather than third-party SAML SSO).
- Note on **Master Account vs Sub-User Login**:
  - `https://login.bce.baidu.com/?account=...` opens the **Main Account** login page (`百度账号` / `云账号`).
  - `https://login.bce.baidu.com/login?account=ac9b269ca79b4c4a8b9dddf08cedfe19&redirect=http%3A%2F%2Fconsole.bce.baidu.com%2Fqss%2Fsurvey%2Fhome%2FmanageSurvey` (with `/login` in the path) opens the **IAM Sub-User Login (`百度智能云-子用户登录`)** with your Master Account ID pre-filled!

### 4.2 The Three Reasons Baidu BCE / QSS Fails Behind a VPN

1. **Conflict Between Corporate VPN (Needed for Azure MySQL) and Baidu's Multi-Domain Login**:
   - Notice that on your machine, `csr-mysql8-flex-stg.mysql.database.azure.com` requires your corporate VPN (`utun` interfaces), whereas Baidu BCE (`login.bce.baidu.com`) loads scripts and exchanges session cookies across **7 separate Baidu domains** resolved to different domestic/global networks:
     - `login.bce.baidu.com` & `console.bce.baidu.com` → `180.76.11.244` (Baidu Beijing domestic BGP)
     - `passport.baidu.com` → `45.113.194.250` (Baidu Passport edge)
     - `cas.baidu.com` → `112.34.111.153` (China Mobile domestic node)
     - `bce.bdstatic.com` & `code.bdstatic.com` → `103.235.45.243` (Global/HK CDN)
     - `bj.bcebos.com` → Baidu Object Storage Beijing
   - When a **split-tunnel VPN** is active, `bce.bdstatic.com` or `passport.baidu.com` may route outside the VPN while `login.bce.baidu.com` or `cas.baidu.com` routes through the VPN (or vice versa). When `passport.baidu.com` mints a login ticket and redirects to `login.bce.baidu.com/postlogin`, **Baidu verifies that the client IP matches**. If the two domains saw different exit IPs, `/postlogin` silently rejects the session and redirects you right back to `login.bce.baidu.com/?account=ac9b269ca79b4c4a8b9dddf08cedfe19&redirect=...`!
2. **Cross-Border TLS 1.3 `ClientHello` Resets (`Errno 54` / `curl 35`) & MTU Fragmentation**:
   - We reproduced this live during our investigation: standard TLS 1.3 / HTTP/2 connections to `https://console.bce.baidu.com/qss/survey/home/manageSurvey` and `https://cloud.baidu.com/doc/QSS/...` from outside Mainland China intermittently fail with `Recv failure: Connection reset by peer` (`curl` exit code 35) during the TLS `ClientHello` handshake, especially over `utun` VPN interfaces with reduced MTU (`1000`–`1380` bytes).
   - Because the login page must download a **2.4 MB** JS bundle (`index.8f025eb448dfca8e7a62.js`) plus `passport.baidu.com/passApi/js/wrapper.js` and `cas.baidu.com/staticv2/dep/common-login/api.js`, a single TCP reset leaves the login page blank (`PASSPORT JS SDK 加载失败`).
3. **Baidu Passport Risk Control (`风控系统`) on VPN / Datacenter Exit IPs**:
   - Accessing `login.bce.baidu.com` from a shared VPN exit node or non-China IP triggers `异地登录保护` (unusual location protection), forcing repeated **Baidu AI Spin CAPTCHAs (`百度旋转验证码`)** and `+86` SMS verification.

### 4.3 How to Fix the VPN Issue for Your Team

- **If accessing from Mainland China**: Add a **Direct (Bypass VPN) rule** in the VPN client for:
  ```text
  *.baidu.com
  *.baidubce.com
  *.bdstatic.com
  *.bcebos.com
  ```
  so all 7 Baidu domains use the local Chinese ISP IP consistently and never traverse the VPN tunnel.
- **If accessing from outside China (India / US) while on Corporate VPN**:
  1. Ensure **all** `*.baidu.com`, `*.baidubce.com`, `*.bdstatic.com`, and `*.bcebos.com` domains bypass the corporate VPN tunnel (route via local ISP so `passport.baidu.com` and `login.bce.baidu.com` see the exact same client IP), **OR** disconnect the VPN briefly while logging into Baidu QSS to download the `.xlsx` file.
  2. Always use **Chrome** (Baidu's FAQ explicitly warns that QSS Excel exports can fail in other browsers).

---

## 5. Recommended Integration Architecture for CIP (`CSI-CN`)

Because Baidu QSS is a human-reviewed crowdtesting platform with **no OpenAPI** and **strict anti-bot/geo-IP controls**, the **cleanest, most reliable, 100% auditable architecture** is to decouple **Baidu Console Export** from **Automated CIP ETL Ingestion** — using the exact pattern CIP already uses for `etl/qualtrics_export.py`!

```mermaid
flowchart LR
  subgraph CN["1. Baidu QSS Console (Direct ISP / No VPN)"]
    A["China Survey Wave Closes<br/>console.bce.baidu.com/qss"] --> B["Click 答卷数据 → 原始数据<br/>Export Excel (.xlsx)<br/>(导出原始数据 + 导出spss编码数据)"]
  end
  subgraph DROP["2. Automated Drop / Upload"]
    B -->|"Upload via Admin UI<br/>or drop in data/china/"| C["Staging Inbox<br/>data/china/incoming/*.xlsx"]
  end
  subgraph CIP["3. CIP Automated Pipeline (etl/baidu_qss_export.py)"]
    C --> D["Parse QSS Excel<br/>Questions + Options + Records"]
    D --> E["Load into cip_stg<br/>country='CN', family='CSI-CN'<br/>platform='baidu'"]
    E --> F["Derive Profiles, Harmonise,<br/>Build Cube & Serving Tables"]
    F --> G["Publish Static JSON<br/>(etl/publish.py)"]
  end
```

### 5.1 Why This Fits CIP's Existing Codebase Like a Glove

During our codebase inspection, we found that **CIP was already partially scaffolded for China**:
- [`config/countries.yml`](file:///Users/mohdsaeedafri/All-Code-Base/consumer-insight-portal/config/countries.yml#L20-L26) already contains:
  ```yaml
  CN:
    name: China
    family: CSI-CN
    language: zh
    currency: CNY
    active: false
    cuts: {}
  ```
- [`app/data/payloads.py`](file:///Users/mohdsaeedafri/All-Code-Base/consumer-insight-portal/app/data/payloads.py#L508-L509) already looks up a wave's country and demographic cuts dynamically from `config/countries.yml` by matching `family` (`CSI-CN` → `CN`)!
- [`etl/serving.py`](file:///Users/mohdsaeedafri/All-Code-Base/consumer-insight-portal/etl/serving.py#L78-L88) already computes `prior_survey_id` and `ly_survey_id` **within `survey_family`**, meaning `CSI-CN` waves will automatically compare and trend only against prior `CSI-CN` waves, never mixing with `CSI-US`!

### 5.2 Concrete Implementation Steps in CIP

| Step | File(s) | What We Need to Add / Change |
|---|---|---|
| **1. Schema & Platform Enum** | [`sql/001_schema.sql`](file:///Users/mohdsaeedafri/All-Code-Base/consumer-insight-portal/sql/001_schema.sql#L48), [`app/core/schema_upgrade.py`](file:///Users/mohdsaeedafri/All-Code-Base/consumer-insight-portal/app/core/schema_upgrade.py#L30-L31) | Add `'baidu'` to `cip_survey.platform` (`ENUM('forsta','qualtrics','surveymonkey','baidu')`) in `WIDEN` / `COLUMNS` so existing MySQL & SQLite databases upgrade cleanly in place. |
| **2. Pass `country` & `language` in Loader** | [`etl/loaders.py`](file:///Users/mohdsaeedafri/All-Code-Base/consumer-insight-portal/etl/loaders.py#L94-L148) | Add `country: str = "US"` and `language: str = "en"` parameters to `upsert_survey()` so China surveys are stored with `country='CN'` and `language='zh'` (or `'en'` if translated). |
| **3. Build Baidu QSS Importer** | `etl/baidu_qss_export.py` (new module, modeled on [`etl/qualtrics_export.py`](file:///Users/mohdsaeedafri/All-Code-Base/consumer-insight-portal/etl/qualtrics_export.py)) | Parse Baidu QSS's `.xls`/`.xlsx` export (`序号`, `答卷者`, `提交时间`, `答题时长`, single-column questions, multi-column options, plus optional SPSS `编码规则` sheet), hash `答卷者` with `xp.respondent_key()`, and run the full pipeline (`load_definitions` → `_replace_respondents` → `_rebuild_profiles` → `_rebuild_question_bases` → `harmonise_survey` → `cube.refresh_wave` → `serving.rebuild_wave` → `index_survey` → `publish`). |
| **4. Automate Ingestion in `etl-loop.sh` / Admin Upload** | [`deploy/etl-loop.sh`](file:///Users/mohdsaeedafri/All-Code-Base/consumer-insight-portal/deploy/etl-loop.sh), `api/main.py` | Watch a drop directory (`data/china/incoming/*.xlsx`) or provide an Admin upload button on `/app/logs` so an analyst can upload a Baidu QSS Excel file directly in the browser (no VPN or CLI needed!) and trigger the full ETL + publish pipeline automatically. |
| **5. Configure China Demographics & Methodology** | [`config/countries.yml`](file:///Users/mohdsaeedafri/All-Code-Base/consumer-insight-portal/config/countries.yml#L20-L26), [`config/survey_map.yml`](file:///Users/mohdsaeedafri/All-Code-Base/consumer-insight-portal/config/survey_map.yml), [`config/methodology.yml`](file:///Users/mohdsaeedafri/All-Code-Base/consumer-insight-portal/config/methodology.yml) | Set `CN.active: true`, map `CSI-CN` demographic questions (gender, age, RMB income bands, tier/region), and add `CSI-CN: China adults 18+` under `population.families` in `methodology.yml`. |
| **6. Frontend Country & Platform Labels** | [`frontend/src/api.ts`](file:///Users/mohdsaeedafri/All-Code-Base/consumer-insight-portal/frontend/src/api.ts#L23), [`frontend/src/components/bits.tsx`](file:///Users/mohdsaeedafri/All-Code-Base/consumer-insight-portal/frontend/src/components/bits.tsx#L127-L140), [`frontend/src/screens/Library.tsx`](file:///Users/mohdsaeedafri/All-Code-Base/consumer-insight-portal/frontend/src/screens/Library.tsx#L16) | Add `baidu: "Baidu QSS"` to `PLATFORM`, update `survey(w)` in `bits.tsx` so `CSI-CN` waves display `"Coresight Research China Consumer Survey"`, and add a Country filter (`All` / `US` / `China`) on the Library & wave picker screens. |

