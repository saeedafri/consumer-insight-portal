# Consolidated product gap register

Priorities are recommendations: **P0** before restricted external release; **P1** correct and verify the research contract; **P2** customer workflow; **P3** data expansion. No row means a fix was deployed. FE/B identifiers resolve to detailed source-line citations in [frontend evidence](frontend-evidence.md) and [backend evidence](backend-evidence.md); C identifiers resolve to official URLs in [competitor sources](competitor-sources.json).

| ID | Priority and class | Current gap and consequence | Evidence | Owner and closure |
|---|---|---|---|---|
| G01 | P0 source | Dashboard product policy differs from generic APIs and static files; restricted users could receive content outside intended product scope | B01, FE01 | Security/API: define survey/product/org rules and prove identical allow/deny across API, static, search, caches and links |
| G02 | P0 source/unknown integration | React/API production OIDC issuer/session revocation bridge not established; 401 points to local-only dev login | B02, FE14 | Identity/API: verify production login, return URL, expiry, logout, revocation and entitlement refresh |
| G03 | P0 runtime | Running Trends reached error page; Compare returned404 despite source route | REA journey ev_61f8c3a5d16688522572d471889ec4cab23da6b776b7608ab88a02c2cfa05874 | Release owner: version-match frontend/backend/data contract, expose build IDs, reproduce and pass representative journeys |
| G04 | P1 statistics | Independent z-tests compare overlapping Total/subgroups and cross-dimension banners | FE02, B04 | Research statistician/frontend: disjoint comparison groups or validated overlap-aware method |
| G05 | P1 disclosure | Small cells suppressed in some UI paths while ordinary API/book rows retain figures | B05 | Research/privacy/API: decide caution vs privacy policy; serialize consistently; test differencing if privacy intended |
| G06 | P1 provenance | Source text hardcodes US adult population even though country is a data property | FE03 | Research/data/frontend: dataset-specific population, field dates, supplier, weighting and limitations |
| G07 | P1 export | Grid CSV uses first-group bases; comparison labels may say last week for nonweekly intervals | FE08 | Frontend/research: group-specific bases and actual comparison dates; independent screen/export parity |
| G08 | P1 reliability | Incremental publish can retain dropped-question trends | B06 | Data platform: invalidate previous/current dependency union; full/incremental equivalence fixture |
| G09 | P1 reliability | Publish gate checks picker/books only; source release across build not version-pinned | B07 | Data platform: artifact inventory, semantic contracts, hashes and stable source release |
| G10 | P1 assurance | Count verification described too broadly; unavailable source reconciliation can exit success with zero checked | B08 | ETL/research: distinct completeness states, expected/checked cells, mismatch and unavailable fail gates |
| G11 | P1 provisioning | Checked-in grant plan does not cover current serving table family | B11 | Platform/DBA: fresh least-privilege install and effective-grants verification |
| G12 | P1 release evidence | PRODUCT counts and historic documents conflict with current runtime; dirty tree cannot identify deployed release | PRODUCT.md, README.md, runtime capture | Release/docs: generated inventory with build, schema, source and metric-definition revision |
| G13 | P2 methodological capability | Weight schema exists but no calibrated weighted serving; basic MOE/testing cannot represent complex designs | B03–B04 | Research: approve population/targets, weights/trim, effective n and design effects before implementation |
| G14 | P2 reproducibility | Cohort definitions versioned but old materialized memberships/cells removed; saved analysis tracks current data | B09 | Data/research: explicit live vs frozen mode, pinned dataset/mapping/cohort/weight revisions |
| G15 | P1 correctness | Cohort refresh count+sum signature can miss changed membership | B10 | Data platform: exact membership change detection and collision fixture |
| G16 | P2 workflow | React lacks durable user-created workspaces, team comments, governed reports and reusable analysis state | FE06, C01/C04/C13/C16 | Product/full stack: saved analysis spec, permissions, versions, frozen/live distinction |
| G17 | P2 workflow | React lacks native XLSX/PPT reporting; legacy XLSX and current CSV/PNG/print cover narrower needs | FE07, C01/C04/C13 | Product/export: reproducible branded report job, exact denominators, citations and retry/cancel |
| G18 | P2 workflow | No buyer-owned metric alert subscription; ETL alerts are operational | FE13, C01/C07/C18 | Product/jobs/research: sufficient n, effect threshold, corrected tests, comparable versions, delivery preferences |
| G19 | P2 audiences | Behavioral cohorts exist internally but client audience builder is fixed demographic/two-cut | FE11, C04/C05/C08/C16 | Product/data: reusable typed boolean audience expressions, asked/answered rules and correct deduped bases |
| G20 | P2 resilience | Malformed/stale URL params and empty catalogue assumptions can crash views | FE09/FE15 | Frontend: schema-valid query state, missing wave/range/group handling and meaningful empty states |
| G21 | P2 accessibility | Keyboard/touch parity for tooltip, chart and drawer interactions incomplete in inspected source | FE10 | Design/frontend: manual assisted-tech journey, contrast and mobile interaction verification |
| G22 | P2 interoperability | Internal endpoints are not scoped customer APIs/connectors with lifecycle/support contract | FE capability boundary, C04/C17 | API/product: authenticated release-pinned exports/API, quotas, documentation and customer agreements |
| G23 | P2 AI | Search is lexical and takeaways templated; no governed generative assistant | FE12, C01/C04/C07/C09 | AI/research: cited structured queries, policy enforcement, abstention and gold-question evaluation |
| G24 | P2 qualitative | Numeric/text stored but excluded from categorical fast cube; no auditable open-text coding workflow | B12, C13/C14/C21 | Research/data: separate typed numeric/text metrics, PII redaction and human coding evaluation |
| G25 | P2 export safety | CSV/XLSX literal values not consistently protected from formula interpretation | B13, FE16 | Export owner: literal-text policy preserving deliberate numeric/formula fields |
| G26 | P2 methodological UX | Four-wave average can imply contiguous/comparable weeks unless window validates dates/versions | Trends.tsx:148-150 | Research/frontend: gap-aware same-version windows, require stated count/base and label equal-wave vs pooled mean |
| G27 | P3 data moat | No demonstrated POS, purchase-receipt, loyalty or media-exposure integration | C01/C02/C03/C22, FE data boundary | Commercial/data: license sources, evaluate match/join granularity and privacy before integrations |
| G28 | P3 reach | Country field/configuration is not verified multi-market panel coverage | README countries, FE03, C04/C06/C10 | Research/commercial: validate demand, licensed sample design and comparability per market |
| G29 | P3 predictive | Preview is not demand simulation; forecasting/causal pricing/promotion models absent in inspected surface | FE12, C01/C11 | Research/data science: distinct model, holdout baseline, uncertainty, observed covariates and decision validation |
| G30 | P2 validation | Legacy analysis tests depend on populated local snapshot; isolated run lacks those tables | tests/test_analysis.py:1-34; test execution | QA: explicit fixture/read-only snapshot contract; do not claim full suite green |
| G31 | P2 discovery | Search caps60 results without total/cursor; strong lexical lookup can silently omit broad matches | FE05 | Search/API: pagination, filters, total-hit count and coverage disclosure before conversational answer generation |

## What is not a new gap

CIP already has cross-tabs, trend views, lexical search, harmonised concepts, own-question bases, change correction, source lines, static publication, legacy saved views/cohorts and legacy XLSX. Those need extension or consistency, not rediscovery as absent features. React source availability is not runtime success.

Unweighted estimates are current policy, not automatically wrong estimates. Lack of worldwide coverage or proprietary purchase data is a strategic scope choice until customer demand and economics justify expansion. No report should promise to be superior to every competitor across unrelated data categories.

