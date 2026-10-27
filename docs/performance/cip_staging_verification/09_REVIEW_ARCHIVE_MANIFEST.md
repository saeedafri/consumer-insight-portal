# CIP Stage 1 review archive manifest

Date: 2026-10-27

The companion ZIP is a review artifact, not a deployable release and not a Git commit.

## Included

- Complete `etl/` tree.
- Complete `tests/` tree, including new reliability and isolation tests.
- Complete `app/`, `api/`, and `sql/` trees needed to review changed query and database behavior.
- `scripts/cip_final_benchmark.py`.
- `.env.example`, dependency manifests, and test configuration.
- All `docs/performance/` deliverables, Stage 1 sanitized evidence, and prior verified NotebookLM evidence sources.
- The two user-provided staging-review prompt/template files.
- A curated worktree patch against base HEAD `6f978b0595b2c71c064991ae10b832514637a0da`.
- Git state, changed-file lists, test commands/results, Stage 1 execution attestation, and SHA-256 inventory.

## Deliberately excluded

- `.env`, credentials, TLS private material, databases, caches, build products, and `.git`.
- `config/notify.yml`, because it contains real notification routing information and is unrelated to the approved database investigation.
- Existing ZIP files and macOS metadata.
- Raw database account, host, connection identifier, view definer, or survey/respondent rows.

Email-shaped literals in the temporary archive copy are replaced with
`[REDACTED_EMAIL]`, including mocked/synthetic test addresses. This protects
notification routing details but means those string literals are not byte-for-byte
identical to the working tree. No notification transport was invoked while
producing the archive.

## State and interpretation

- The working tree is intentionally uncommitted and contains pre-existing changes.
- Full-file copies preserve additions and the current ETL/test implementation for review.
- `EVIDENCE/CIP_CURATED_WORKTREE_PATCH.diff` is the reviewable source/test/config delta. Notification configuration and unrelated notification edits are excluded from that patch.
- `EVIDENCE/DELETIONS.txt` records deletions; none were present at packaging time.
- Local test success is not staging performance proof.
- Stage 1 contains metadata/status reads only. Stage 2 plans remain proposed and unexecuted.
