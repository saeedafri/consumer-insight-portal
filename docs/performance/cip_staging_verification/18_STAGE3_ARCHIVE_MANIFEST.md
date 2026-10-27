# CIP Stage 3 archive manifest

Date: 2026-10-27

The companion ZIP is a sanitized review artifact, not a deployable release or Git commit.

## Included

- Complete `etl/`, `tests/`, `app/`, `api/`, `sql/` and `config/` trees.
- Stage 1-3 deliverables and sanitized evidence.
- Fixed staging execution scripts and disposable MySQL benchmark source.
- Before/after JSON, index experiment, regression results and proposed next SQL.
- Current tracked patch, untracked source/test patches, Git state and SHA-256 inventory.

## Excluded or sanitized

- `.env`, credentials, databases, private TLS material, caches, `.git`, prior ZIP files and macOS metadata.
- Real routing addresses in `config/notify.yml`; the archive contains the complete
  file structure with email-shaped values replaced by `[REDACTED_EMAIL]`.
- Raw database account/host/connection identifiers, respondent data and survey answers.
- Email-shaped literals in the archive copy are replaced with `[REDACTED_EMAIL]`.

The local MySQL container used tmpfs-only synthetic data. The exact container was removed and Colima stopped after evidence capture.

