# 08 · Sources

All sources were checked on **20 Oct 2026**.

## Internal evidence

Paths are relative to `~` unless stated.

### Azure usage
- `Downloads/SIP & MIP Info.xlsx`: Azure portal export, last 3 months
  - SKUs
  - average and peak memory
  - response times

### SIP
- **Repositories**
  - `All-Code-Base/SIP-Prod` (branch `pro-deploy`)
  - `Code-Base/Modular-Code` (branch `stg-deploy`)
- **Performance docs**
  - `docs/performance/enhancement-journey/02-problems-findings-fixes.md`
  - `05-render-speed-research.md`
  - `docs/performance/2026-08-07-sip-speed-and-ram-investigation.md`
  - `docs/performance/05-concurrency-and-scaling.md`
- **Code**
  - `sip_components/active_data.py`
  - `auth_utils.py`
  - `pages/logs.py`
  - `.streamlit/config.toml`
  - `patch_streamlit_splash.py`

### MIP
- **Repositories**
  - `All-Code-Base/market-data-stg`
  - `Code-Base/Real/CapIQReplacement`
- **Specs**
  - `docs/superpowers/specs/2026-10-01-mdp-full-e2e-timing-ram-capacity-report.md`
  - `2026-10-17-gemini-change-review-and-capacity-design.md`
  - `2026-10-17-independent-investigation-design.md`
  - `OIDC_FLOW.md`
- **Staging server logs**
  - `server-logs/server-logs-20261019_075003.log`
  - `logs/server-logs-20261016_193052.log.gz`
  - `logs/server-logs-20260703_022556.log`

### MIP-FAST-React
- `All-Code-Base/MIP-FAST-React`: README, `benchmark_proof.py`, `frontend/dist`, `backend/auth.py`

### CIP (this repository)
- `scripts/ui_benchmark/*`: the benchmark harness
- `docs/14-pipeline-validation-report.md`: network round trip 263 ms
- Live `cip_stg` cube, read-only: wave pack size measured on survey 415

### Shipped bundles measured
- Streamlit 1.55.0 `static/js/index.RuhrnD1v.js`
- Dash 4.4.1 renderer
- MIP-FAST-React `dist/assets/index-CCoQ40OZ.js`

## Streamlit
- Architecture: https://docs.streamlit.io/develop/concepts/architecture/architecture
- Session State: https://docs.streamlit.io/develop/concepts/architecture/session-state
- Caching: https://docs.streamlit.io/develop/concepts/architecture/caching
- Fragments: https://docs.streamlit.io/develop/concepts/architecture/fragments
- Multithreading: https://docs.streamlit.io/develop/concepts/design/multithreading
- st.login: https://docs.streamlit.io/develop/api-reference/user/st.login
- Release notes 2026 (1.57 Starlette/Uvicorn; 1.66.0): https://docs.streamlit.io/develop/quick-reference/release-notes/2026
- Advisories: https://github.com/streamlit/streamlit/security/advisories
- Snowflake acquisition: https://techcrunch.com/2022/03/02/snowflake-acquires-streamlit-for-800m-to-help-customers-build-data-based-apps

## Other frameworks
- Dash, sharing data between callbacks: https://dash.plotly.com/sharing-data-between-callbacks
- Reflex: https://reflex.dev/docs/state/overview/
- NiceGUI: https://nicegui.io/documentation/section_configuration_deployment
- Panel: https://panel.holoviz.org/how_to/concurrency/index.html
- Solara: https://solara.dev/documentation/getting_started/deploying/state-persistence
- Gradio advisories: https://github.com/gradio-app/gradio/security/advisories
- Mesop (archived): https://github.com/google/mesop
- HTMX 2: https://htmx.org/posts/2024-06-17-htmx-2-0-0-is-released/
- Phoenix LiveView: https://phoenix-live-view.hexdocs.pm/welcome.html
- Livewire: https://livewire.laravel.com/docs/4.x/actions
- Turbo: https://turbo.hotwired.dev/handbook/introduction
- Blazor Server: https://learn.microsoft.com/en-us/aspnet/core/blazor/host-and-deploy/server/
- Next.js CVE-2025-29927: https://github.com/vercel/next.js/security/advisories/GHSA-f82v-jwr5-mffw
- React2Shell CVE-2025-55182: https://react.dev/blog/2025/12/03/critical-security-vulnerability-in-react-server-components
- Remix → React Router: https://remix.run/blog/merging-remix-and-react-router
- TechEmpower Round 23 release: https://github.com/TechEmpower/FrameworkBenchmarks/releases
- TechEmpower sunset: https://github.com/TechEmpower/FrameworkBenchmarks/issues/10932
- Gunicorn design: https://gunicorn.org/design/
- App Service Python: https://learn.microsoft.com/en-us/azure/app-service/configure-language-python
- PEP 779: https://peps.python.org/pep-0779/
- DuckDB-WASM: https://duckdb.org/docs/current/clients/wasm/overview
- Perspective: https://github.com/finos/perspective
- AG Grid licensing: https://www.ag-grid.com/javascript-data-grid/licensing/

## Network, caching and Azure
- Azure network latency: https://learn.microsoft.com/en-us/azure/networking/azure-network-latency
- Front Door overview: https://learn.microsoft.com/en-us/azure/frontdoor/front-door-overview
- HTTP caching: https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/Caching
- Azure Retail Prices API: https://prices.azure.com/api/retail/prices
- App Service Linux pricing: https://azure.microsoft.com/en-us/pricing/details/app-service/linux/
- Static Web Apps pricing: https://azure.microsoft.com/en-us/pricing/details/app-service/static/
- Front Door pricing: https://azure.microsoft.com/en-us/pricing/details/frontdoor/
- Power BI Embedded pricing: https://azure.microsoft.com/en-us/pricing/details/power-bi-embedded/
- Fabric pricing: https://azure.microsoft.com/en-us/pricing/details/microsoft-fabric/
- Embedded capacity: https://learn.microsoft.com/en-us/power-bi/developer/embedded/embedded-capacity

## Popularity and hiring
- Stack Overflow Developer Survey 2025: https://survey.stackoverflow.co/2025/technology
- Stack Overflow Developer Survey 2026: https://survey.stackoverflow.co/2026/technology/data
- State of JS 2025: https://2025.stateofjs.com/en-US/libraries/front-end-frameworks/
- India job postings: freehire aggregator snapshot, 20 Oct 2026 (one source, a rough signal)

## Marketplace
Vendor and third-party URLs are listed in [04 §6](04-marketplace-buy-vs-build.md).
