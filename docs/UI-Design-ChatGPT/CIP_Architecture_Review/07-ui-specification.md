# 07. UI specification and interaction design

[Package index](README.md) | [System design](04-system-design.md)

**Status:** proposed information architecture and wireframes, not a shipped frontend or a pixel-validated design file.

## 1. Design objective

Make it easy to find a trusted answer, understand its source/base and return to the same analysis. The primary interface should feel like one research product rather than a collection of scripts. Maintain the established direction of top navigation, compact page headers, collapsible filters and efficient use of screen space.

The initial content emphasis is U.S. consumer/survey research. Do not populate navigation with unavailable regions or promise datasets not yet published.

## 2. Application shell

```text
+--------------------------------------------------------------------------------+
| CORESIGHT  |  CIP                         Search research...  Help  [Account]    |
| Overview     Explore data     Analysis     Trends     Publications     Saved     |
+--------------------------------------------------------------------------------+
| Consumer insights                                         Data as of: [date]   |
| Dataset: [name]  Wave: [period]  Source: [source]  Version: [published revision]   |
+--------------------------------------------------------------------------------+
| Filters [collapsed / expanded]     Active filters: [chip] [chip]   Clear         |
+--------------------------------------------------------------------------------+
| [Research summary / eligible base] [Selected metric] [Comparable prior wave]     |
+--------------------------------------------------------------------------------+
| Main chart                                         | Context and methodology   |
|                                                    | Base / weighting / notes  |
|                                                    | Related permitted data    |
+--------------------------------------------------------------------------------+
| Table view   [sort] [columns]                       Save view   Export           |
| Bounded rows, clear denominator, paging                                         |
+--------------------------------------------------------------------------------+
```

The account area shows plan/capability information only where useful. Administrative tools are role-gated and separated from the subscriber navigation. Consistent branding does not require copying every SIP screen; CIP has a different analytical task.

## 3. Core screens

| Screen | User task | Required components |
|---|---|---|
| Overview | Understand what is new and relevant | Latest published waves, curated insights, saved work, freshness and methodology links |
| Explore data | Discover an answerable question | Search, source/topic/wave filters, clear scope, approved additional-product previews |
| Analysis Builder | Create an authorized comparison | Dataset/question selection, validated cohort filters, breakdown, chart/table, base and save/export |
| Trends | Compare compatible waves | Concept mapping, wave range, visible definition changes and comparability notes |
| Publications | Use stable research output | Published snapshot, source/version, notes and authorized download |
| Saved | Resume a prior workflow | Owned/shared views, permission scope, pinned-versus-latest behavior |
| Account/access | Understand current rights and additional options | Purchased scope, approved upgrade/contact workflow, session/account settings |
| Internal operations | Maintain data safely | Mapping queue, quality failures, publication jobs and audit history behind research/admin roles |

The first release should perfect Overview and one Analysis journey rather than launch every route with shallow functionality.

## 4. Analysis Builder wireframe

```text
+--------------------------------------------------------------------------------+
| Analysis Builder                                           [Save] [Export]      |
| Dataset [v]   Question/concept [search...]   Published version [v]                |
+------------------------+-------------------------------------------------------+
| ANALYSIS SETTINGS      | [Chart] [Table] [Methodology]                          |
| Wave [v]               |                                                       |
| Cohort [v]             | Selected question / metric                            |
| Breakdown [v]          | Chart with bounded categories and accessible labels   |
| Measure [v]            |                                                       |
|                        | Base: ...  Weighting: ...  Source: ...                |
| Active filters         | Missing/suppressed values explained                   |
| [filter] [filter]      +-------------------------------------------------------+
|                        | Table: category | estimate | n | base | notes         |
| [Apply]  Reset         | [Previous]     Page ...      [Next]                   |
+------------------------+-------------------------------------------------------+
| Result scope / version / freshness / request status                             |
+--------------------------------------------------------------------------------+
```

On narrower screens, collapse settings into a drawer and preserve the result context. Keep filters in the URL or a saved definition where safe, so navigation and sharing retain the analysis without sharing credentials or private tokens.

## 5. Interaction rules for speed and clarity

Opening a menu or filter panel should be local browser work. Keep chart/table presentation changes local when they reuse the same small authorized result. Apply full-dataset filters and sorts through the server contract; never imply that sorting one downloaded page sorts the whole dataset.

Use an Apply action for combined cohort/breakdown changes. Show the pending selection without replacing the current valid result until the new request completes. Cancel or disregard obsolete responses so an older slow request cannot overwrite the latest selection. Keep previous data visible with an explicit updating state where appropriate; do not label it as the new result.

Fetch shared page metadata once. Avoid one redundant request per widget. Load chart editors and administration code only when needed. Virtualize long tables, but also limit rows returned. Treat query freshness, retries and focus refetches as deliberate choices rather than library defaults. [S17](08-sources.md#s17), [S18](08-sources.md#s18), [S19](08-sources.md#s19).

Use subtle skeletons for initial loading and a clear progress state for jobs. Avoid decorative sleeps, artificial progress percentages and animations that delay the next useful action.

## 6. Research trust is part of the UI

Every result should disclose enough context to prevent misinterpretation: question/concept, wave period, source, data version/as-of date, eligible base, displayed count, weighting status and applicable methodological notes.

Question bases must remain question-specific. A missing answer, a suppressed result and a measured zero need distinct representations. Do not imply statistical significance simply because two percentages differ or automatically add significance markers without approved methodology. A multi-response question can legitimately have category percentages that do not sum to 100%.

Define small-base suppression, respondent-level access and disclosure rules with the research/privacy owners. A hard-coded arbitrary threshold is not a substitute for a policy, and repeated filtered queries can reveal information even when individual tables suppress cells. Restrict raw verbatims and respondent detail separately from aggregate access.

Keep publication snapshots reproducible. A saved view should clearly state whether it follows the newest published data or pins a version; changing a metric definition must not silently rewrite the meaning of a published figure.

## 7. Empty, unavailable and restricted states

| State | User-facing meaning | Product behavior |
|---|---|---|
| No matching results | The permitted data exists, but the filters match nothing | Preserve filters and offer reset/edit |
| No published data yet | Dataset exists but is not ready | Show approved availability context, not invented values |
| Additional subscription required | An approved catalog entry is outside current access | Describe the additional scope without leaking restricted values |
| Data delayed | Latest successful publication is older than expected | Display its real as-of time and a status message |
| Suppressed result | Policy prevents displaying a value | Explain the suppression, not a zero or a blank chart |
| System error | A request failed | Preserve user work, show retry and a support request ID |

These distinctions prevent an upgrade opportunity from misleading a user into thinking the platform lacks relevant data. Existing SIP/MIP entitlements must continue to provide their agreed benefits.

## 8. Configuration without arbitrary code

Use version-controlled, schema-validated configuration for navigation labels, permitted page templates, metric definitions, default filters, chart types, source notes and feature flags. Separate those from runtime entitlements and secrets.

A metric definition should specify allowed dimensions, denominator rules, weighting, compatible waves, display units, suppression policy and version. A chart configuration should reference an allowed metric and presentation options, not arbitrary SQL or executable JavaScript.

Share design tokens, core components and API contracts across CIP/CIQ/MIP/MDB where appropriate. Keep product-specific research definitions modular. Avoid generating one unmaintainable global configuration document that requires coordinated release of all products.

## 9. Accessibility and responsive behavior

Adopt WCAG 2.2 AA as a design/QA target, not a certification claim. Provide keyboard-accessible filters and dialogs, visible focus, meaningful field labels, sufficient contrast, non-color-only distinctions and text/table alternatives to charts. Ensure focus remains sensible after updates and that status/error messages are announced appropriately. [S50](08-sources.md#s50).

Test dense tables at realistic zoom levels and smaller viewports. A desktop-first research application can prioritize wide analysis layouts without making account, saved-view and overview tasks unusable on mobile.

## 10. UI release acceptance

A user must be able to sign in, find an entitled dataset, understand its scope, apply a comparison, inspect the correct base, save the view, reopen it and request an authorized export without losing context. The same workflow must remain understandable during slow requests, empty results and session expiry.

Assess perceived responsiveness and click-to-correct-result timing separately. Track time to first useful insight, successful analysis completion, saved-view reuse and export success. These outcomes determine whether the UI is helping attract and retain users; a frontend framework name does not.
