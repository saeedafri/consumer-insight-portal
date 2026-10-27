# CIP final closure archive manifest

Date: 2026-10-27

The companion ZIP is a sanitized review artifact, not a Git commit or deployable
release.

Included:

- Complete current application, API, ETL, test, SQL, configuration, scripts,
  deployment, web and workflow source trees.
- All CIP performance reports and Stage 1-final sanitized evidence.
- Exact tracked changes, untracked source/test patch, file indexes, Git state
  and SHA-256 inventory.
- The final single-pass approval document supplied by the user.

Excluded or sanitized:

- `.env`, databases, credentials, private TLS material, caches, `.git`, prior
  ZIP files and macOS metadata.
- Email-shaped and notification-routing values are redacted in the archive copy.
- Raw database account/server identities, respondent data and survey answers.

The disposable MySQL container used synthetic tmpfs data and was removed after
the final test. Colima was stopped.
