# For IT: Azure Container Registry is filling up — please add image cleanup

*Prepared 15 November 2026. Everything below is an Azure-side change; the dev team cannot run these (no registry
credentials). Forward this as-is.*

## The problem, in one line

Every CIP deploy pushes a new, uniquely-tagged Docker image to the registry **csrdockerregistry.azurecr.io**, and nothing
ever deletes the old ones, so registry storage grows with every build and never comes back down.

## Why it happens

The Bitbucket pipeline tags each image with the build number and commit, e.g. `stg-91-3be1b2c1`, and also moves a
`stg-latest` / `pro-latest` tag used as the build cache. The numbered tags accumulate forever. There is currently no
retention policy and no purge task on the registry.

## What we need from IT (one task, ~10 minutes)

Create a **scheduled ACR purge task** that keeps a few recent images per environment and deletes the rest. This is
Microsoft's supported way to clean a registry (`acr purge`, run as an ACR Task). Please run, as a registry owner:

```bash
# Repository name = the Bitbucket APP_NAME variable. The web app is "<APP_NAME>-stg" = csr-awa-cip-portal-stg,
# so APP_NAME is almost certainly "csr-awa-cip-portal". Confirm with:  az acr repository list -n csrdockerregistry -o tsv
REPO=csr-awa-cip-portal

az acr task create \
  --name cip-purge \
  --registry csrdockerregistry \
  --context /dev/null \
  --schedule "0 3 * * Sun" \
  --cmd "acr purge --filter '${REPO}:stg-[0-9].*' --filter '${REPO}:pro-[0-9].*' --ago 21d --keep 5 --untagged"
```

What this does, and why it is safe:
- **`stg-[0-9].*` / `pro-[0-9].*`** match the numbered build tags (`stg-91-...`, and the older date-based tags like
  `stg-20261112-...`, which also begin with a digit). They deliberately do **not** match `stg-latest` or `pro-latest`,
  so the build cache tags are never touched.
- **`--keep 5`** always keeps the 5 most recent images per environment, so the currently-deployed image and the last
  few rollback targets survive regardless of age.
- **`--ago 21d`** only considers images older than 21 days for deletion.
- **`--untagged`** also removes manifests left with no tag.
- Runs **Sundays 03:00 UTC**. Adjust the cron if you prefer.

**Please dry-run it first** to see exactly what it would delete, before scheduling:

```bash
az acr run --registry csrdockerregistry --cmd \
  "acr purge --filter '${REPO}:stg-[0-9].*' --filter '${REPO}:pro-[0-9].*' --ago 21d --keep 5 --untagged --dry-run" \
  /dev/null
```

### Optional backstop (only if the registry is on the Premium SKU)

A retention policy auto-deletes **untagged** manifests after N days. It needs the **Premium** SKU; on Basic/Standard it
is not available, and the purge task above is enough.

```bash
az acr config retention update --registry csrdockerregistry --status enabled --days 21 --type UntaggedManifests
```

## Two smaller, related IT items (not urgent)

1. **Registry login in the pipeline uses a username/password on the `az` command line.** Bitbucket masks it in logs, but
   the clean fix is a **managed identity / `az acr login` via the service principal** instead of
   `--container-registry-password`. IT's call.
2. **Deployment slot + Azure Front Door** (already on our status board as pending IT): the app code is ready
   (`/readyz` health endpoint, `CIP_ETL` slot setting). A warm staging slot swapped on `/readyz` removes the ~75–90 s
   outage on every deploy, and Front Door fixes the slow first-connection latency from India. Happy to brief separately.

## What the dev team is handling (no IT action)

Build **time** and **image size** are mostly our side: confirming BuildKit is enabled, installing the two database
libraries from prebuilt wheels instead of compiling them, and keeping the 130 MB geo-IP file out of the image. We will
test these locally before spending a Bitbucket build. Smaller images also mean less registry storage, which compounds
with the cleanup above.

---
*Contact: the CIP dev team. Registry: csrdockerregistry.azurecr.io. Web apps: csr-awa-cip-portal-stg (staging),
csr-awa-cip-portal-pro (production).*
