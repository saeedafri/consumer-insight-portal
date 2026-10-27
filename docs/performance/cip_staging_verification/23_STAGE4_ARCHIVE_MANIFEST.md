# CIP Stage 4 archive manifest

Date: 2026-10-27

The companion ZIP is a sanitized review artifact, not a deployable release or
Git commit.

## Included

- Complete current `app/`, `api/`, `etl/`, `tests/`, `sql/`, `config/`,
  `scripts/`, `deploy/`, `web/` and `.github/` trees.
- Stage 1-4 performance reports and sanitized JSON evidence.
- Stage 4 staging executor and disposable MySQL benchmark source.
- Current tracked patch, untracked source/test patch, Git state and SHA-256
  inventory.
- The two user-supplied Stage 4 review/approval documents.

## Excluded or sanitized

- `.env`, credentials, databases, TLS private material, caches, `.git`, prior
  ZIP files and macOS metadata.
- Email-shaped values are replaced by `[REDACTED_EMAIL]` in the archive copy,
  including routing values in `config/notify.yml`.
- Raw server/account identity, respondent data and survey answers.

The local MySQL container used synthetic tmpfs-only data and is removed after
final evidence capture.
