# Deploying CIP to Azure App Service

One web app runs one container image. Inside it: nginx (port 8080) serves the website and the published files, the API
(FastAPI) answers the rest, and the ETL scheduler runs the Forsta pipeline by itself. The server is in Azure (US) and
connects to the MySQL database directly: no VPN.

## 1. Build and release (Bitbucket → ACR → web app)

Repository: `https://bitbucket.org/coresight_admin/cip-portal`, branch `stg-deploy`. Build from the repository root:

```bash
docker build -f deploy/Dockerfile --target app --build-arg CIP_BUILD=$BITBUCKET_COMMIT -t <acr>.azurecr.io/cip-portal:$BITBUCKET_COMMIT .
docker push <acr>.azurecr.io/cip-portal:$BITBUCKET_COMMIT
# then point the web app at the new tag (as for Directus)
```

- No start command: the image starts itself (`bash deploy/start.sh`).
- The build needs no secrets and no network beyond npm and PyPI. It builds the website (Node) and the Python environment
  in one Dockerfile.
- `bitbucket-pipelines.yml` builds the image on every push to `stg-deploy` (no tests: they run locally before a push);
  add the push to ACR and the web app update after its build step.

## 2. Web app settings

| Setting | Value |
|---|---|
| Publish | Docker container, Linux |
| Plan | P0v3 (1 vCPU, 4 GB) is enough (tested: 10,000 users, p99 7 ms, 690 MB). P1v3 if 20,000 people may use it at once |
| Instances | **1**, no autoscale (the ETL and the published files belong to one instance) |
| Always On | **On** (the ETL scheduler must keep running) |
| HTTPS Only | On; minimum TLS 1.2 |
| Health check path | `/healthz` |
| App Service logs | File System on (the platform's docker log then appears on the Logs page) |

Application settings (environment variables):

| Name | Value |
|---|---|
| `WEBSITES_PORT` | `8080` |
| `WEBSITES_ENABLE_APP_SERVICE_STORAGE` | `true` (keeps `/home`: logs, the ETL heartbeat, the open-ended coding) |
| `WEBSITES_CONTAINER_START_TIME_LIMIT` | `300` |
| `APP_ENV` | `staging` (until SSO is on; then `production`) |
| `CIP_SESSION_SECRET` | 64 random characters (`openssl rand -hex 32`). The API refuses to start with fewer than 32 |
| `STG_DB_HOST`, `STG_DB_PORT`, `STG_DB_NAME`, `STG_DB_USER`, `STG_DB_PASSWORD` | the `cip_stg` database (pipeline account) |
| `APP_DB_USER`, `APP_DB_PASSWORD` | the portal's read-only account |
| `FORSTA_HOST`, `FORSTA_API_KEY` | `se1.decipherinc.com` and the Forsta key |
| `CIP_DEMO_LOGIN` | `1` **only until SSO is on** (sign-in by email, no password); remove it when SSO is on |
| `CIP_ADMIN_TOKEN` | 48 random characters: the Logs page and other admin pages ask for it while SSO is off |
| `EMAIL_SMTP`, `EMAIL_PORT`, `EMAIL_FROM`, `EMAIL_PASSWORD` | the mailbox that sends the load and failure emails |
| `TEAMS_WEBHOOK_URL` | optional: the Teams heads-up on launch Mondays |
| `ANTHROPIC_API_KEY` | optional: Ask CIP answers in words and open-ended answers are coded into themes by Claude |
| `CIP_PUBLISH_BACKUP_URL` | recommended: a Blob container SAS URL. After a deploy the published files come back in seconds; without it the first start rebuilds them (about 16 minutes, the site works meanwhile) |

Store the secrets in Key Vault and reference them from these settings.

## 3. Network

- The web app reaches MySQL `csr-mysql8-flex-stg.mysql.database.azure.com:3306` (TLS; the certificate is in the image):
  add the web app's outbound IPs to the server's firewall, or use VNet integration.
- Outbound HTTPS to `se1.decipherinc.com` (Forsta), the SMTP host, Teams, Blob storage and, optionally,
  `api.anthropic.com`. If the Forsta key is restricted by IP, add the web app's outbound IPs to it.

## 4. Sign-in (SSO): off until the address is known

SSO (Microsoft Entra ID, OIDC) is built and stays off. Until it is on, people sign in by email at `/auth/dev-login`
(`CIP_DEMO_LOGIN=1`) and admin pages also need `CIP_ADMIN_TOKEN`. To turn SSO on once the domain is confirmed:

1. Entra ID → App registrations → New: name "CIP", Web redirect URI `https://<domain>/auth/callback`; create a client secret.
2. Settings: `CIP_OIDC_ISSUER=https://login.microsoftonline.com/<tenant-id>/v2.0`, `CIP_OIDC_CLIENT_ID`,
   `CIP_OIDC_CLIENT_SECRET`; remove `CIP_DEMO_LOGIN`; set `APP_ENV=production`. Restart.

With `APP_ENV=production` the API refuses to start if `CIP_DEMO_LOGIN=1` is still set.

## 5. The ETL runs by itself

`deploy/etl-loop.sh` starts with the container. Times are UTC (`CIP_ETL_RUNS` overrides them):

| When | What |
|---|---|
| Monday 12:00 (17:30 IST) | the launch run: watches the new weekly wave and loads it when its fieldwork ends (up to 54 h) |
| Every day 03:30 (09:00 IST) | loads any other survey that closed (annual, ad hoc); Friday's also runs the integrity check |
| Every hour at :05 | the watchdog: emails if a run is stuck or has not run |

Each run takes a lock in the database, so two runs never overlap. A loaded wave is verified against Forsta, published and
announced by email; a failure is emailed to `config/notify.yml` `failure`.

## 6. Logs

Admins open **`/app/logs`** (the Logs entry in the menu). While SSO is off the page asks for `CIP_ADMIN_TOKEN`.

| Log | What it holds |
|---|---|
| nginx: every request | one JSON line per request: time, visitor, path, status, size, time taken, cache |
| nginx: warnings and errors | nginx's own errors |
| API | startup, slow requests, errors |
| ETL runs, ETL errors | each scheduled run, every failure |
| Publish at start | the restore or rebuild of the published files after a deploy |
| Container supervisor | when the container started and which process stopped |
| Azure App Service (docker) | the platform's own log: image pulls, starts, restarts (needs App Service logs: File System) |
| Security events | sign-ins, sign-outs, denied and revoked access, every 401/403/429 |

Files live in `/home/cip/logs` and are rotated at 20 MB. App Service's Log stream shows the same API and container output.

## 7. Check after each deploy

```bash
curl -s https://<app>.azurewebsites.net/healthz        # {"ok":true,"build":"<commit>"}
```

Then sign in, open a wave, and open `/app/logs` → Container supervisor: one "started" line with the new build.
