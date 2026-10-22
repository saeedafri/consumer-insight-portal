# Backend, data and statistical evidence

Date: 21 October 2026 (Asia/Kolkata). Target: `/Users/mohdsaeedafri/All-Code-Base/consumer-insight-portal`.

## Scope and evidence boundary

This is a source investigation using the REA skill's observation/inference/unknown discipline. The skill explicitly routes complete source-repository analysis to normal repository tools. No database connection, external request, application launch, secret/configuration-value read, data mutation or code change was performed. No REA runtime observation is claimed for this sub-report. Parent investigation owns any separate REA tool evidence.

The existing dirty working tree is the target, including modified API, payload, Forsta ETL, serving, schema and test files. Line citations identify that snapshot, not necessarily committed HEAD or a deployed release. Source support proves an implemented code path; it does not prove deployment, successful execution or production data coverage. Tests were inspected, not executed. Some older tests directly use the configured repository and must not be run as if the whole suite were isolated.

## Reconstructed data lifecycle

| Layer | Observed implementation | Evidence |
|---|---|---|
| Source ingestion | Forsta API discovery/load/reconcile; legacy Qualtrics/SurveyMonkey migration; local definitions/record loaders and crosstab export | `etl/forsta_etl.py:284-360`, `etl/legacy_dwh.py:285-342`, `etl/run_pipeline.py`, `etl/qualtrics_export.py` |
| Identity and source hygiene | Forsta UUID identifies respondents; RID becomes SHA-256 respondent key; explicit personal-field denylist drops browser agent, URL, session, fingerprint, IP and RID fields | `etl/forsta_etl.py:272-281`, `etl/forsta_api.py:22-25,62-64` |
| Canonical storage | Survey → question → item/option/field; respondent → profile and long answers. Answers include codes, numbers and text; respondent qualification is explicit | `sql/001_schema.sql:215-260`, `etl/forsta_etl.py:369-400` |
| Verification | Incoming respondent count, field coverage and per-field nonempty answer counts compared before profile/cube/serving build; separate source-value reconciliation | `etl/forsta_etl.py:329-346,452-503` |
| Harmonisation | Exact normalized wording/type/options confirm automatically; changed answers or similar wording propose review; new units get concepts; grid rows form separate concept units | `app/data/harmonise.py:1-14,87-116,256-294` |
| Review and provenance | Confirm, keep separate and reject operations record reviewer and guard duplicate decisions | `app/data/harmonise.py:307-360` |
| Cohorts | Nested AND/OR/NOT over confirmed concept answers, answered/asked semantics; versioned definitions, qualified respondent membership | `app/data/cohorts.py:58-105,108-131,150-173` |
| Aggregation | Qualified categorical answers only. Total plus gender, age band, generation, income band, census region, urbanicity. Counts and question/row answering bases; optional cohort cells | `app/data/cube.py:34,43-107,120-141` |
| Serving | Transactional per-wave finished results with labels, percentages, prior/last-year comparisons and flags; respondent-level six-cut serving rows retained for two-cut queries | `etl/serving.py:98-183`, `sql/005_serving.sql:21-80` |
| Delivery | Precompressed books, dashboard documents, question cut aggregates and trends; atomic symlink publish, last versions, optional Azure backup; cached API fallback and nginx static serving | `etl/publish.py:57-178,187-232`, `api/main.py:249-273`, `deploy/nginx.conf:42-70` |
| Analyst publications | Freeze definition/cells/version/owner/footnote; recompute drift against frozen cells with tolerance and exact-count checks | `app/data/publications.py:69-109,138-166,188-235` |

## Capabilities already present: retain and strengthen

1. **Question bases are first-class.** Single/grid bases are answering respondents per row; multi-select bases are distinct respondents answering any item in the question. This avoids dividing routed answers by wave totals (`app/data/cube.py:70-107`). These are unweighted answering bases, not proof of population representativeness.
2. **Comparability protection exists.** Reused question codes are insufficient: serving compares normalized wording or confirmed shared concept answers; dissimilar wording clears comparison and raises flags. Base-share changes over 10 percentage points raise routing warnings (`etl/serving.py:89-125`). Trend/compare/crosstab also group question versions (`app/data/payloads.py:131-157,297-307,353-387`).
3. **Small-base controls exist in particular paths.** Two-cut crosstabs suppress count/share below 30 and flag bases below 50 (`app/data/payloads.py:333-341`). Frozen publications suppress share/count under configurable minimum and withhold thin averages (`app/data/publications.py:69-101`). These controls are not uniformly applied to all outputs.
4. **Saved views are implemented in the analyst repository.** Listing includes owner or shared views; deletion is owner-scoped. Definitions rerun against current data (`app/data/repository.py:691-742`). Do not describe the entire product as lacking saved analysis; React/API exposure is a separate question.
5. **Export provenance exists.** Branded Excel includes an About sheet, timestamp, source, supplied notes, and own-base interpretation (`app/components/export.py:27-137`). Complete export metadata remains caller-dependent.
6. **Operational performance design is substantial.** Compressed immutable response files, ETags, cache byte cap, admission semaphore, queue timeout and 503 retry guidance exist (`api/main.py:225-230,249-273`; `etl/publish.py:57-65`). Performance claims in comments are historical measurements, not new measurements from this audit.

## Source-verified gaps and corrections

### B01 — Product entitlements are bypassed by generic endpoints and nginx static dashboards

**Priority: P0 before restricted commercial subscriptions. Confidence: high, static.**

`api/main.py:241-242` checks `who['products']` for the dashboard handler. Generic waves, book, results, search, trends, crosstab and compare handlers only depend on the signed-session validator; their data lookups/cache keys do not scope by entitled products (`api/main.py:290-381`). A valid restricted session therefore reaches cross-product generic source data in the code as written.

In addition, nginx sends published dashboard files directly after `/auth/check` (`deploy/nginx.conf:53-56`). That endpoint validates the session only (`api/main.py:391-394`), so existing static dashboard files bypass the API's dashboard product check. This is a reproducible source-level authorization inconsistency, not a demonstrated live incident. Actual deployment and customer restrictions are unknown.

**Correction:** define a single survey/product access policy; apply it before catalog/search/result generation and before static file authorization. Supply requested resource identity to the authorization check. Partition any user-dependent caches. Add restricted-session parity tests across direct API, nginx static hit, static miss/fallback, catalog and search. If customers share a product but require distinct confidential data, introduce explicit organization/dataset scope; current product strings alone do not express it.

### B02 — React/API production authentication is separate from the implemented Streamlit OIDC session flow

**Priority: P0 launch dependency. Confidence: high for source boundary; live configuration unknown.**

The API uses an HMAC-signed `cip_session`, 12-hour expiry, and startup secret requirement (`api/main.py:51-54,192-222`). Its local issuer is guarded by explicit `APP_ENV=local` (`api/main.py:397-404`). The API source has no production OIDC authorization/callback/session-exchange/logout route. The comment says production signs in through OIDC; this is not an implemented issuer within that module.

Streamlit has a different `csi_session` cookie and server-side `cip_auth_session` records with audit/revocation (`app/core/auth.py:18-24,45-47`; `sql/001_schema.sql:660-674`). Those records do not revoke API HMAC cookies: `api/main.py:212-222` makes no server-side session lookup. An external gateway may bridge this, but was not established by this source inspection.

**Correction:** implement or document and verify the exact production OIDC-to-API session bridge, secure cookie issuance, logout/revocation, key rotation and entitlement refresh. Test with the deployed frontend route family. Do not count the older Streamlit auth tests as coverage of the API authentication path.

### B03 — Weighting storage exists; weighted population estimates do not flow through serving

**Priority: P1 methodological capability. Confidence: high, static.**

`cip_profile.weight` is explicitly reserved/unweighted (`sql/001_schema.sql:233`). Named weight schemes and per-respondent weight tables exist (`sql/001_schema.sql:497-523`), and aggregate schema includes weighted placeholders (`sql/001_schema.sql:574-580`). Active cube input does not select weights and active aggregation uses `COUNT`, selected counts and answering counts (`app/data/cube.py:43-107`). Serving computes `100*n/base_n` (`etl/serving.py:108-117`). Merely having weight tables does not establish raking, calibration or weighted analysis.

**Correction:** approve target population/source controls; implement scheme version, calibration/trim policy, sum-of-weight numerator/denominator, unweighted base, effective sample size and design-effect-aware uncertainty end to end. Preserve unweighted outputs and label them now. Do not assert weights alone make a sample representative.

### B04 — Significance is a basic independent two-proportion test

**Priority: P1 before expanding automated conclusions. Confidence: high, static.**

`api/dashboards.py:82-89` computes a pooled two-sided z-test at 0.05 from two percentages and raw bases. Takeaways use it to state significant moves and selected highest-versus-lowest segment differences (`api/dashboards.py:192-239`). This implementation has no overlap covariance, survey design/weight adjustment or multiplicity parameter. Selecting the extreme groups and testing them as a single unplanned contrast increases false-discovery risk. Whether actual waves contain repeat respondents is unverified.

**Correction:** attach test method and assumptions to each result, require sample sufficiency, distinguish disjoint versus overlapping groups and repeated waves, implement approved multiple-testing policy and confidence intervals. Keep automated language conditional when a valid test is unavailable. Preserve existing tests as basic arithmetic checks, not methodological certification.

### B05 — Suppression is inconsistent across delivery contracts

**Priority: P1, elevated if suppression is a contractual privacy rule. Confidence: high, static.**

Two-cut crosstabs hide `n`/`pct` below base 30, and frozen publications have minimum-base controls. Ordinary serving retains low-base counts/shares with `small_base` only (`etl/serving.py:108-125`); book and result outputs read these rows (`app/data/payloads.py:44-53,83-122`), and compare returns raw percentages/bases (`app/data/payloads.py:383-387`). Thus “the portal suppresses all small bases” would be false. Suppression may be an analytical caution rather than a privacy promise; that policy must be explicit.

**Correction:** define one disclosure/caution policy and enforce it in server-side result serialization, exports and publications, with path-parity tests. If privacy protection is intended, assess complementary suppression/differencing, not only a fixed threshold. Do not expose respondent cut aggregates as publicly addressable files.

### B06 — Incremental publication can retain stale trends after a question disappears

**Priority: P1 correctness. Confidence: high, static and explicit code comment.**

Publisher hard-links unchanged trend folders, then regenerates questions present in fresh wave data. The code explicitly acknowledges that reload dropping a question leaves that question's old trend (`etl/publish.py:119-131`, particularly line 122). Removed questions require invalidating the union of previous/current question membership, not only current rows.

**Correction:** persist dependency membership in manifests, invalidate removed questions and affected family trends, and add reload-removal test comparing incremental output against a clean full build.

### B07 — Publication quality gates are narrower than their documentation

**Priority: P1 correctness/reliability. Confidence: high, static.**

`etl/publish.py:152-168` describes readable books with questions and no corrupt/empty file. Actual checks validate picker length, each book's survey id and that questions is a list. An empty question list passes; cuts, trends and dashboard payloads are not traversed or cross-validated. Atomic symlink swap prevents half-file deployment, but cannot certify semantic correctness or consistency across multiple independent database queries during a long build.

**Correction:** validate every manifest-listed artifact/schema/hash, expected nonempty questions where applicable, cut/total arithmetic parity, trend dependency freshness and source release identity. Build from a stable source snapshot or version-pinned serving release. Gate publication on zero unresolved critical checks.

### B08 — Loader verification proves count coverage, not full value equality

**Priority: P1 trust/evidence accuracy. Confidence: high, static.**

`load_survey` says every respondent and answer is proven equal before visibility (`etl/forsta_etl.py:285-288`), but `verify` checks respondent count, datamap field presence and per-field answer counts (`452-468`). Separate `reconcile_survey` performs value comparisons (`472-503`). Values can differ while counts match; do not interpret the verify gate as cell-by-cell reconciliation.

When source fetching raises `ForstaError`, reconcile logs “not checked” and returns `(0, [])` (`484-487`). CLI aggregates only problems and exits 0 if none (`575-583`), so an unavailable/hibernated source can produce successful exit with no compared answers.

**Correction:** separate verified-counts, verified-values, skipped/unavailable and failed states; return coverage and expected/checked counts; make scheduled acceptance require explicit reconciliation completeness for the release. Count extra stored cells as well as missing/different incoming cells. Preserve source digests or immutable extracts under the retention policy.

### B09 — Cohort version history retains rules but deletes historical materialized results

**Priority: P2 reproducibility. Confidence: high, static.**

Changing a cohort retires the prior definition, then deletes its respondent memberships and cube cells (`app/data/cohorts.py:108-125`). Saved views follow cohort code to current version (`app/data/repository.py:368`). This supports current analysis but does not reproduce a past cohort computation from its historical materialization. Frozen publications preserve cells, which partially mitigates the issue.

**Correction:** distinguish live views from frozen releases; pin cohort version, concept-map revision, source wave revision and weight scheme to each approved output. Retain reproducibility snapshots or immutable rebuild inputs rather than promising historical reruns from deleted cells.

### B10 — Cohort refresh change detection has a collision-prone signature

**Priority: P2 correctness. Confidence: high for mechanism; observed collision unknown.**

Refresh compares `(COUNT(*), SUM(respondent_id))` before/after cohort derivation (`app/data/cube.py:153-165`). Different equal-sized member sets can have equal sums, e.g. `{1,4}` and `{2,3}`; a real membership change can therefore skip cube rebuild. This is mathematical insufficiency in the detector, not evidence that current data has hit it.

**Correction:** compare member sets with database anti-joins or an exact membership revision/change count. Add a test with equal count/sum but changed member identities and responses.

### B11 — Supplied least-privilege grants do not cover current serving tables

**Priority: P1 deploy reproducibility. Confidence: high for SQL mismatch; deployed grants unknown.**

`sql/004_grants.sql:7-14` grants roles access to `cip_%` and app SELECT on `v_cip_%`. Current serving tables are `srv_wave`, `srv_result`, `srv_answer` (`sql/005_serving.sql:21-80`), with ETL writes and API reads (`etl/serving.py:143-183`; `api/main.py:41`). No matching serving grants occur in the inspected provisioning locations. Running only this supplied script does not provision all required privileges. The database may have manual grants not represented here.

**Correction:** provision explicit serving SELECT/DML rights per role and verify with a fresh least-privilege installation. App role's AUTOCOMMIT setting (`app/core/database.py:81-98`) is a performance choice, not an enforcement mechanism for read-only access.

### B12 — General numeric/text facts are stored but excluded from the fast categorical analysis cube

**Priority: P2 capability boundary. Confidence: high, static.**

Canonical answers support `value_number` and `value_text` (`sql/001_schema.sql:252-255`), while cube input requires nonnull `value_code` and handles multi, single and grid-single categorical options (`app/data/cube.py:43-56`). Do not describe this fast serving path as general verbatim analytics, arbitrary numeric distribution analysis or open-ended thematic coding. Midpoint age/income averages are a distinct implemented capability.

**Correction:** add separate governed numeric and verbatim analysis contracts where customer demand warrants them: valid/invalid/nonresponse counts, redacted text, language, coding provenance, auditable themes and quality evaluation. A privacy-aware text service requires more than reusing the categorical cube.

### B13 — Export cells are written without formula neutralization

**Priority: P2; validate exposure before escalation. Confidence: high for source mechanism.**

Excel builder writes titles, headers, dataframe values and notes directly with openpyxl `ws.cell(..., value=...)` (`app/components/export.py:54,67,85,126-129`). No literal-text escape is applied there. A source/caller-controlled string beginning with `=` can be interpreted as an Excel formula. This audit did not execute a spreadsheet payload or establish whether present source labels contain such values.

**Correction:** emit untrusted text as explicit literal strings while preserving deliberately authored formulas. Test question labels, verbatims, saved-view names and provenance fields using inert formula-like strings.

## Test evidence and verification limits

| Existing test area | What source tests exercise | Execution status |
|---|---|---|
| `tests/test_serving.py:42-207` | Routing/base flags, reused question code, late last-year load, two-cut reconciliation/suppression, book/trend/compare, cache cap | Inspected only |
| `tests/test_publish.py:14-79` | Published bytes, atomic swap/rollback, failed gate, mocked Azure backup/restore | Inspected only; mocked backup is not live recovery proof |
| `tests/test_harmonise.py:89-288` | Exact matching, added answer proposals, grid units, reject/confirm, reviewer/duplicate-decision safeguards | Inspected only |
| `tests/test_pipeline_hardening.py:14-71` | Significance letters, TSV escaping, integrity healing and secret masking | Inspected only |
| `tests/test_auth.py:24-120` | Streamlit providers, allowlist, claim rejection, expiry and local debug bypass | Inspected only; not API/nginx entitlement coverage |
| `tests/conftest.py:12-34` | Per-test SQLite app/ETL fixture, temp publication root, temp notification state | Isolation exists for tests using those fixtures |
| `tests/test_analysis.py:21-34` | Repository fixture resolves questions from configured survey id 1 without a `csi_db` argument | Do not run indiscriminately: potentially configured external DB |

Recommended validation order: add isolated source-level policy/correctness cases; run selected SQLite tests under explicitly isolated environment; run nginx/API contract tests against synthetic local releases; verify least-privilege provisioning and source reconciliation coverage in an approved environment. This report does not claim those checks passed.

## Decisions to feed into the Council

1. Treat authorization parity, production sign-in integration and release validity as launch gates.
2. Build on bases, harmonisation review, frozen publications, provenance and static performance strengths.
3. Decide whether the first differentiation is trustworthy survey intelligence or licensed purchase/POS/receipt intelligence. Existing survey storage cannot conjure competitor transaction panels.
4. Label weighted statistics, generalized verbatim analytics, explicit tenant policy and complete audit/reproducibility as proposed until implemented and validated.
5. Keep any AI-generated answer grounded in release-pinned structured metrics, question wording, population/base and comparison flags; reject unsupported causal/population claims.

## Unknowns requiring separate evidence

Live database row/wave/sample counts; deployed schema/grants; customer entitlements and tenancy contracts; API gateway/IdP bridge; actual repeat-panel overlap; calibration targets; actual quality/integrity metrics; release/source consistency during concurrent reloads; operational RPO/RTO and backup recovery; production latency/concurrency. None should be inferred from historical comments or test names.
