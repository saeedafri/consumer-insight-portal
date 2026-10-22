# Implementation specifications for closing the gaps

These specifications turn the gap register into reviewable engineering work. They are proposed changes; source references describe where they connect to the present product. Sequence and commercial commitments are subject to the Council verdict.

## One release can be identified and reproduced

**Problem:** source, generated frontend assets and the running backend can differ. Current local Trends/Compare failures make that distinction consequential.

**Touchpoints:** `api/main.py`, `etl/serving.py`, `etl/publish.py`, frontend API types and deployment configuration.

Create a release manifest containing source commit plus dirty/snapshot digest when applicable, frontend asset manifest hash, backend build identifier, schema migration revision, serving release, analytical-policy revision and publication version. Expose nonsecret release identifiers in an authenticated diagnostic response and attach dataset/definition revisions to exported results. Reject incompatible schemas before rendering or publishing.

Treat ETL completion and publication as separate transitions: extracted → count-checked → value-checked or explicitly not-checked → derived → publication-validated → released. Preserve the previous valid release when a transition fails. A release cannot be called fully reconciled when its expected source cells were unavailable.

**Acceptance:** a synthetic reload removes a question, changes a label/base and introduces a mapping revision; a clean full build and incremental build yield the same supported outputs. Every manifest-listed file has a readable schema and digest. Reopening a frozen brief after a new release reproduces its figures and citations.

## One resource access policy covers every serving path

**Problem:** checking a dashboard product inside Python does not protect a file served directly by nginx or data exposed through a general survey endpoint.

**Touchpoints:** `api/main.py:user/dashboard/auth_check`, general endpoints, `deploy/nginx.conf`, publication route mapping and scoped caches.

Define resources first: product, study, survey release, question, saved workspace, export. A company that buys one study may need access to some surveys but not confidential ad hoc studies. The exact commercial rule is an owner decision; encode it once and default to denying unknown resources.

For static delivery, either authorize the requested canonical asset identity before its file is served, or route protected data through the same policy service. Preserve caching only where the resource policy is equivalent. Prevent catalog/search/title metadata leakage as well as number leakage.

**Acceptance:** two synthetic principals with disjoint permissions, anonymous/expired/revoked sessions, static hit/miss, encoded URLs, API fallback, copied links and cached responses all produce the same allow/deny result. Tenant confidentiality is tested only after the product actually defines organizations and dataset ownership. Do not infer a tenant model from product strings.

## A research result carries its meaning

**Problem:** apparently identical numbers can have different answering populations, wave definitions, tests or suppression.

**Touchpoints:** `app/data/cube.py`, `app/data/payloads.py`, `api/dashboards.py`, `web/src/stats.ts`, chart/source components and exports.

Version a result specification with measure/question/item/answer identity, wave set, audience expression, units, numerator, answering base, weighting scheme, source release, routing/comparability status, test and disclosure state. Distinguish zero, missing, suppressed, unsupported, not comparable and not checked. Those states must not silently become zero.

Independent-proportion tests are permitted only for approved disjoint samples. Total-versus-subgroup uses subgroup-versus-complement when valid. Cross-dimension overlapping groups require covariance-aware analysis or withheld inference. Repeated panel waves and overlapping rolling pools need their own approved comparison treatment. Record the multiple-testing family; What Changed's FDR policy should not be described as covering every test elsewhere.

A four-observation mean is not automatically a four-calendar-week mean or pooled respondent estimate. Use same-version contiguous windows, disclose the window and method, and keep gaps visible.

**Acceptance:** manually calculated fixtures cover routed questions, multi-select totals above100%, grid bases, subset comparisons, overlapping dimensions, missing weeks, sparse cells, question reuse and changed answer options. Screen, CSV, XLSX, PPT and AI consume the same approved result. Numerical tests must verify the statistical design as well as arithmetic.

## A saved brief is a small reusable product

**Problem:** an analyst can explore a result but still reconstruct its context in a deck every week.

**Touchpoints:** existing `app/data/repository.py` saved views, cohort versioning, `app/data/publications.py` frozen cells and the React route state.

Introduce a bounded saved analysis document: owner/team, access policy, question/measure, permitted waves, audience version, chart view, method version, notes, source references and live/frozen mode. A brief collects a small set of these analyses. Do not begin with an unrestricted dashboard designer.

A refresh previews changed/removed/incomparable metrics before approval. Preserve the approved version and mark new results as draft. Shared links resolve a resource policy, not possession of a URL as authorization.

**Acceptance:** save/reopen preserves all supported settings; a reviewer can trace every claim to wording/date/base/source; new waves cannot rewrite an approved report silently. Deletion, ownership transfer and retention are explicit. Permission changes apply to old links and exports as contractually required.

## Exports preserve research evidence

**Problem:** CSV/PNG/print help exploration but do not complete the recurring reporting workflow; legacy XLSX should not regress.

Reuse one report specification for server-side XLSX/PPT rendering. Include exact displayed values, denominators per grid row, fieldwork, weighting status, source release, comparison date, suppression reason and stable reference. Treat untrusted text as literal spreadsheet text. Do not label every prior comparison “last week”.

Evaluate existing rendering libraries or licensed tools for reliability, editable chart support, theme/font behavior, rights and deployment footprint. Own the analytical contract; buy commodity document rendering when justified.

**Acceptance:** inspect native artifacts, reopen XLSX/PPTX, verify ZIP/XML integrity, ensure hidden/suppressed data is absent from chart workbooks and tables, and compare exported cells to the approved result. Browser print is not equivalent to a native editable report. The selected first format comes from buyer demand.

## Alerts and AI follow a validated analytical service

Alerts reference saved measures with an approved audience and comparison. Require base sufficiency, effect size, valid comparison and repeated-testing policy. Distinguish operational pipeline alerts from customer insights. Send only to opted-in entitled recipients, with deduplication, delivery outcomes and unsubscribe/preferences.

A descriptive assistant invokes allowlisted typed services; it cannot produce arbitrary SQL or use its own arithmetic as the source of truth. It states question, release, dates, audience, base and caveats with every numerical claim. Unknown answers should trigger clarification, abstention or a follow-up research request.

**Acceptance:** gold cases include ambiguous words, incompatible waves, missing source data, small cells, adversarial survey text, unauthorized datasets and causal requests. Report supported-task accuracy with sample count and confidence limits; a passing small test set is not universal accuracy. Red-team and observe before expanding task scope.

## New data products have separate commercial and research gates

For a POS/receipt/context partner, write a data contract: metric units, coverage geography/time, population, granularity, refresh/delay, revision behavior, licence to redistribute derived outputs, permitted AI use, storage/retention, joins, privacy responsibilities and cost at expected usage.

Prefer aggregate time/geography/category overlays initially. Never join people through hashed identifiers without verified consent, licence and a scientifically valid matching method. Survey intent and observed purchase must remain distinct.

**Acceptance:** one paid use case demonstrates decision value, support burden and acceptable margin; coverage/bias are explicit. A partner outage or licence expiry removes dependent claims safely. Forecasts beat an agreed seasonal baseline on untouched holdout windows before any predictive marketing; causal claims require a separate identification design.

