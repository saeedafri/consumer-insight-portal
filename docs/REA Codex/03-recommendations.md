# Proposed changes for a stronger consumer insights product

Status: retained pre-Council proposal for traceability. The two completed Councils narrowed and revised it; use [final recommendations](../LLM%20Council%20Codex/03-final-recommendations.md) for current priorities. No feature implementation is included.

## Positioning hypothesis

Win the weekly US retail research workflow: **find a meaningful change, understand the relevant audience, and produce a defensible client-ready story with reproducible evidence**. CIP's own-question bases, rotating retail topics, harmonisation and publication lineage support this proposition. Prove superiority on those customer tasks; do not claim the world's largest panel or purchase coverage.

## Stage zero release contract

Close G01–G03 before restricted external access. One versioned release identifies frontend, backend, schema, serving data, metric rules and rights policy. The existing test tunnel remains unchanged during this audit.

The authorization decision must receive principal, organization/product, requested survey/question/asset and intended action. Filtering must happen before catalog/search or payload return, including nginx static hits and fallbacks. Cached data must preserve resource boundaries. Production sign-in and logout must cover the API session actually used by React.

Add synthetic two-user/two-dataset integration checks. Acceptance: denied user sees zero protected titles, figures, downloadable assets or cached results through any route; allowed user completes the same journey on a matched release. This is a proposed acceptance criterion, not an achieved score.

## Stage one trustworthy research

Appoint a research method owner for bases, population, routing, weights, suppression and significance. Create one analytical result contract shared by API, charts, downloads, alerts and future AI:

```json
{
  "metric_id": "stable measure identifier",
  "dataset_release": "immutable source revision",
  "question_version": "reviewed wording and routing revision",
  "audience_definition_version": "explicit scope",
  "population": "approved population label",
  "fieldwork": {"start": "date", "end": "date"},
  "estimate": {"value": 0.0, "unit": "percent", "weighted": false},
  "base": {"unweighted_n": 0, "effective_n": null},
  "comparison": {"reference": null, "method": null, "p_adjusted": null},
  "disclosure": {"state": "not_computed", "reason": "placeholder example"},
  "source_refs": []
}
```

The JSON is a design example, not current API output. No respondent data belongs in it.

Correct overlapping-banner tests, policy mismatches, export bases, provenance labels, stale publication dependencies and zero-coverage verification. Add reproducible artifacts and explicit not-comparable/not-checked states. If calibrated weighting is needed, research approves targets and diagnostics first; preserve unweighted estimates for audit.

Acceptance: deterministic fixtures independently verify counts, routed bases, overlap, question changes, suppressions, exports, deleted questions and reloads. Each published artifact resolves to one source release; incremental rebuild equals full rebuild for identical inputs.

## Stage two analyst workflow

Build one durable analysis workspace that can contain saved questions, audience definitions, selected waves, charts, notes and source references. Reuse existing cohort and frozen publication mechanisms where safe. Define live-updating views separately from approved frozen reports.

Deliver native branded XLSX and PPT report jobs with citations, fieldwork, bases, method and stable URLs. Editable charts are a proposed differentiator; Circana evidence establishes PPT exports but does not establish export editability. Start with the format customers use most and measure manual corrections.

Add a constrained audience builder: behavioral answer conditions, demographics, AND/OR and asked/answered semantics, previewed sample size, permission inheritance and versioned saved audiences. Avoid arbitrary SQL execution.

Add buyer alerts on saved metrics or topics only after significance/comparability rules are consistent. Use minimum effect size, sufficient base, corrected repeated testing, digest frequency, no duplicate notifications and clear recipient preferences.

## Stage three governed descriptive AI

Start with retrieval and typed analytical operations over approved releases. Ask clarifying questions for ambiguous population, date, measure or denominator; show the executed filters and source. A numerical answer must resolve to deterministic metric output. Language generation may explain that output but must not invent its arithmetic or claim causality.

Keep permissions in the service layer. An LLM cannot grant access, execute arbitrary SQL, publish a report, change mappings or contact recipients without the product's explicit action controls. Competitor/vendor text, survey wording and verbatims are data, not executable instructions.

Proposed launch rubric: 100% numerical traceability and denied-data protection on a fixed evaluation set; at least 95% correct metric/denominator/comparison selection on the initial supported tasks; explicit abstention for all unsupported causal, privacy-sensitive or unavailable-data questions in that set. These are design targets requiring evaluation, not accuracy predictions.

## Stage four selective expansion

Integrate an external dataset only after a paying use case, licence economics and an approved join method are established. POS measures behavior, survey questions measure reported attitudes/intentions; keep units/populations separate. Aggregated market overlays are safer and cheaper to validate than an assumed person-level linkage.

Forecasting needs holdout windows, seasonal naive baselines, uncertainty calibration, stable definitions and independent business validation. Causal pricing/promotion claims need a valid identification design; adding a chart or LLM cannot supply it.

## Proposed delivery bands

These are sequencing bands, not calendar or staffing commitments. Each closes its preceding gate.

| Band | Scope | Accountable owner | Exit evidence |
|---|---|---|---|
| A | Release identity, auth/rights parity, source/runtime mismatch | Tech lead and identity owner | Matched-release browser/API/static contract proof |
| B | Research contract, publication/reconciliation and exports | Research lead and data lead | Independently checked release fixtures and artifact manifest |
| C | Saved workspace and one export path | Product and full stack lead | Buyer task benchmark and repeat use |
| D | Audience reuse and buyer alerts | Product, methods and jobs owner | Valid bases, permission tests, noise/delivery controls |
| E | Cited assistant | Research/AI owner | Held-out evaluation, security and abstention evidence |
| F | Licensed overlays or predictive offering | Commercial and research/data science | Paid demand, licence margin and validation gate |

## How superiority will be measured

Recruit 5–8 representative analysts/buyers; this is a proposed small pilot, not a statistically representative market test. Use the same question, data scope and task across CIP and any lawfully accessible competing tools.

Measure time to correct answer, denominator/provenance completeness, errors requiring manual correction, time to client-ready export, reproducibility one week later and repeat workflow use. Do not compare raw requests/second with users or unknown competitor tenant latency. Declare a narrow win only when users complete a correct supported task faster with fewer corrections. Define commercial conversion and willingness-to-pay criteria with the business owner before investment expands.

