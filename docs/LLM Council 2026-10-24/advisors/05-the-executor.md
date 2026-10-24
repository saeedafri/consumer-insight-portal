# Advisor 5: The Executor
## Pragmatic Critical Path, Monday-Morning Triage & Operational Sequencing

**Perspective:** The Executor  
**Mandate:** Filter out the noise, establish the shortest execution path, and specify what must be done step-by-step.

---

### The Executor Analysis

We have had enough debate and philosophical discussions. Here is the operational reality:
The engineering team closed all five major strategic gaps in the codebase today (weighting, index scores, open-ended coding, API keys, MCP). All 332 tests are passing (`pytest` clean in 47 seconds). The UI compiles and type-checks cleanly.

Do not waste engineering cycles worrying about YouGov's 30M panel. Enterprises buy this tool for analytical depth and speed. Fix uptime and metric consistency first.

Here is the exact, sequenced execution roadmap:

---

### Monday 09:00 – 12:00: Infrastructure Cutover & Secrets (P0)
1. **Azure VM Cutover:**  
   Running commercial demos off a MacBook behind an ephemeral tunnel is an immediate operational hazard.  
   - SSH into the Azure Ubuntu VM.  
   - Configure systemd for Uvicorn on localhost (`/etc/systemd/system/cip-api.service`).  
   - Bind a persistent Cloudflare Tunnel (`cloudflared tunnel run <named-tunnel>`) mapped to a permanent corporate domain (`insights.coresight.com`).  
   - Verify `/healthz` returning 200 with hardened security headers.  
   - Only after verifying public VM traffic do we retire the local MacBook tunnel.
2. **Secrets Injection:**  
   - Provision production `ANTHROPIC_API_KEY` directly into `/etc/environment` or the systemd unit file on the VM.  
   - Smoke-test `etl/open_ends.py` to confirm LLM thematic clustering runs and no longer drops back to word-frequency fallbacks.  
   - Set `CIP_DEMO_LOGIN=0` (enforcing company SSO) and `CIP_RESPONDENT_SALT=<crypto_salt>`.

---

### Monday 13:00 – 17:00: Eliminate Metric Split-Brain (PR #1 – P0)
Clients will churn on day one if the Trends tab contradicts the Wave tab.
1. **Extract Aggregator:**  
   - Abstract the weighting math from `etl/weighting.py` into a shared core function: `apply_weights(data, weight_col)`.
2. **Route Updates:**  
   - Wire the helper into `api/trends.py`, `api/compare.py`, `api/crosstabs.py`, and topic dashboard handlers.  
   - Make `weighted=true` default whenever weights exist in the database.  
   - Ensure crosstab marginals sum weight factors rather than raw record counts.  
   - If a screen cannot support weighted data yet, place an unambiguous badge: *"Displaying unweighted raw counts ($n=400$)."* Never leave the user guessing.
3. **Parity Tests:**  
   - Add integration tests asserting that filtering a Trend or Compare query down to a single wave produces mathematical parity with the Wave and MCP endpoints.

---

### Tuesday 09:00 – 13:00: API Key Management UI (PR #2 – P1)
Insights managers and agency leads do not open terminal windows. If provisioning access requires `python -m`, it is an internal dev tool, not an enterprise SaaS platform.
1. **Admin Endpoints:**  
   - Wrap `app/core/api_keys.py` with:  
     - `POST /api/v1/admin/api-keys` (generate)  
     - `GET /api/v1/admin/api-keys` (list metadata, masked keys)  
     - `DELETE /api/v1/admin/api-keys/{key_id}` (revoke)  
   - Gate endpoints by admin session authentication.
2. **Frontend Settings View:**  
   - Add an "API Access" tab in the admin panel with key generation and copy-to-clipboard functionality so client onboarding requires zero terminal access.

---

### Tuesday 14:00 – 17:00: Commercial MCP Integration Kit (PR #3 – P1)
1. **Ship 1-Page Claude Desktop & Cursor Integration Guide:**
   ```json
   {
     "mcpServers": {
       "consumer-insights": {
         "url": "https://insights.coresight.com/mcp",
         "headers": {
           "Authorization": "Bearer cip_live_..."
         }
       }
     }
   }
   ```
2. **Enterprise Client Onboarding:**  
   - Enable retail analysts to ask Claude Desktop: *"What are the top 3 over-indexing categories for Walmart shoppers this week compared to Target?"* and receive verified, weighted data with citation metadata in under 5 seconds.
