# CIP architecture decision and source review

**Prepared:** October 20, 2026  
**Input:** `code-baseall.zip`  
**Decision status:** Recommended architecture; production performance and capacity not yet qualified.

## Recommendation

Build the customer-facing CIP product with **React + TypeScript + Vite**, backed by a **Python FastAPI modular API**, retaining **MySQL and the existing Python ETL/domain logic**. Run ingestion, heavy analyses and exports in a separately controlled worker. Keep Streamlit available for internal research and operations rather than making it the default subscriber-product shell.

This is a **best-fit decision**, not a claim that Python beats Node.js in benchmarks. React + TypeScript + Node.js/Fastify is the strongest alternative when the delivery team is demonstrably stronger in TypeScript. A fair implementation trial can change that choice.

## Read this package

| Document | Purpose |
|---|---|
| [01 - Decision](01-decision.md) | Recommendation, business explanation, decision rules and honest limitations |
| [02 - Code audit](02-code-audit.md) | What the ZIP actually implements; source locations; security, correctness and performance findings |
| [03 - Technology and marketplace comparison](03-technology-marketplace.md) | Streamlit, web frameworks, backend alternatives, Indian and international buy/build options |
| [04 - System design](04-system-design.md) | Components, data publication, authentication, authorization, API contracts, jobs, deployment and recovery |
| [05 - Performance and validation](05-performance-validation.md) | Actual local results, benchmark weaknesses, proposed latency budgets and production qualification protocol |
| [06 - Cost and migration](06-cost-migration.md) | Server scenarios, resource budgets, cost model, migration gates and scaling triggers |
| [07 - UI specification](07-ui-specification.md) | Navigation, page wireframes, interaction model, research semantics and configuration boundaries |
| [08 - Primary sources](08-sources.md) | Dated source register with official documentation links |

`CIP_Full_Report.md` combines these chapters into one readable Markdown file. The numbered chapters remain the easiest way to navigate the package.

## Evidence that accompanies the report

- `evidence/archive-inventory.json`: archive identity, source counts and cache inventory.
- `evidence/source-probes.json`: narrowly scoped offline probes of session validation and a cohort-signature counterexample.
- `evidence/data-path-results.json`: raw local synthetic SQLite measurements, environment and limitations.
- `evidence/test-collection-output.txt`: the unsuccessful attempt to collect the full repository test suite.
- `validation/source_probes.py` and `validation/data_path_probe.py`: the two scripts actually used for the bounded checks.

The original code, `.env`, credentials, customer data and original operational logs are **not redistributed** in this package.

## Immediate caution

The uploaded archive contains populated credential settings. Rotate the affected credentials and review where the archive has been distributed. Presence in the archive does not establish compromise, but these values should not travel with source-review bundles.

## Evidence labels

**Observed** means inspected directly in the supplied source. **Measured** means executed in the isolated local environment and recorded here. **Documented** means supported by the linked primary documentation. **Proposed** means a design choice or acceptance target, not an achieved result. **Unknown** means the required evidence was not supplied or could not be obtained.

There is no claim that the complete CIP application, live Azure environment, SIP or MIP production deployments were load-tested. The archive is a CIP source tree, not two separate SIP/MIP implementation repositories.
