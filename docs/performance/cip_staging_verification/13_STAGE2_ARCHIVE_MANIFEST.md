# CIP Stage 2 review archive manifest

Date: 2026-10-27

The companion ZIP is a sanitized review artifact, not a deployable release or Git commit.

## Included

- Complete current `etl/` and `tests/` trees.
- Complete `app/`, `api/` and `sql/` trees.
- Stage 2 fixed-allowlist execution script and the isolated benchmark script.
- All CIP performance deliverables, Stage 1 and Stage 2 sanitized evidence, and verified NotebookLM evidence sources.
- Exact approved Stage 2 SQL manifest, human-readable plan analysis and proposed Stage 3 test manifest.
- Current tracked worktree patch, untracked source/test patches, changed-file lists and Git state.
- SHA-256 inventory for every archive member.

## Excluded or sanitized

- `.env`, credentials, databases, TLS private material, caches, build outputs and `.git`.
- `config/notify.yml`, which contains real notification routing and is unrelated to the database review.
- Existing ZIP archives and macOS metadata.
- Raw database hostname/account/connection ID, view definer, credentials, respondent data and survey answers.
- Email-shaped literals in the archive copy are replaced with `[REDACTED_EMAIL]`, including synthetic test values.

Full-file copies show the current uncommitted worktree. Some edits predate Stage 2; the repository was not reset, committed, pushed, deployed or restarted.

