# Task: Generated skill count widget

- [x] Matching positive-integer skill count control with Apply/Refresh and progress.
- [x] Count and adjust generated skills only in the workspace skill-dump directory.
- [x] Reuse generator content defaults; delete excess generated files permanently.
- [x] Preserve project-authored/foreign files; no backups or restore mechanism.
- [x] Verify filesystem safety, background job behavior, UI, and build.

User explicitly rejected backups/restoration. Current count means generated
files on disk, not Claude's registry or model-visible skill descriptions.

## Implementation

Shared generator under src/runtime/skill_dump with the existing executable CLI
wrapper preserved. New SkillCount service scans fixed-path recognized files,
tracks revisions, runs one background job and reports progress. Adds missing
files exclusively; decreases unlink generated SKILL.md and its empty directory
without recursive removal/backups. Retained bytes remain unchanged. Source paths
use no-follow descriptors; unsafe names/contents/links block mutation. API uses
positive-integer request validation, no-store responses and mutation headers.
UI distinguishes on-disk count from registration and warns about permanent
deletion. ADR-0030 documents behavior and partial completion boundaries.

## Verification

- Full suite with CONTEXT_INSPECTOR_TEST_MCP=1: 146 tests, 143 passed and three
  unrelated opt-in MLflow integration tests skipped (18.1 seconds).
- Nine new API/filesystem tests: fresh generation, CLI adoption, 500–5,000-line
  defaults, growth/decrease, retained-file identity, no backups, unrelated
  contents preserved, symlinks/hardlinks, revision conflicts, background progress,
  duplicate Apply, disk-error recovery, integer validation and mutation headers.
- Existing eight generator tests still pass after extracting shared code.
- Production build and git diff --check pass.
- Synthetic Playwright skill and MCP fixtures pass: current values, positive
  validation, large-count input (mocked only), polling, decreases, warning,
  conflicts, Refresh, mobile fit and MCP right alignment.

No live skills/config were changed, no Claude inputs sent, and no stack restart.
Browser closed. User restarts to activate the new API and refreshes frontend.
