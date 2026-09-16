# 078 — Strace startup reset and search

## Request and acceptance

- Permanently clear container/strace contents on normal stack startup, no backups.
- Respect existing startup lock, active-container and filesystem safety guards.
- Add read-only /strace navigation with filename/line-number matches across logs.
- Bound resource use and visibly report incomplete searches; never follow links.
- Rename Workspace navigation to /workspace.
- Verify synthetic cleanup/search tests, frontend build and browser behavior.
- Leave live stack and existing logs untouched; user handles restart.

## Discovery

The startup context already owns a lifetime lock and guards Claude home cleanup.
Strace writes per-process files into a fixed local mirror. Extend that same reset
transaction before deleting anything; the search needs no container API.

## Implementation and verification

- Extended clean_claude_startup to validate both fixed roots and active container
  mount overlap before deletion, using the existing lifetime lock and no-follow
  file descriptors. Deletes all trace contents, including hidden/nested entries;
  links are unlinked without following them. Directory is retained at mode 0700.
- Added GET /api/strace/search, literal case-sensitive search, relative filenames
  and line numbers, no-store responses, no session requirement, serialized scans.
  Resource limits and skipped entries explicitly produce partial-result warnings.
- Added /strace top-level search tab, retained results across navigation, safe
  text rendering, empty/missing/error states; Workspace now reads /workspace.
- ADR-0037 documents the startup retention change and bounded search tradeoff.
- Full regression: 173 tests ran, 170 passed, 3 unrelated opt-in skips, with MCP
  and isolated strace-container checks enabled. After the final byte-boundary
  guard and additional concurrency test, all 17 focused reset/search tests pass.
- npm run build and git diff --check pass. Synthetic Playwright fixtures for
  strace, workspace and ~/.claude pass, including 390px mobile layout. Browser
  served built assets via route fixtures; no app/test stack was started.
- Existing real logs were not read or removed. Browser closed. User-managed
  startup activates backend changes and clears old traces without backups.

All acceptance criteria met. Very large logs may require offline exhaustive
search; the UI never labels a bounded or skipped scan as complete.
