# 079 — Clear traces on Start Claude

## Acceptance

- Clear only container/strace before creating a new real Claude session.
- Joining an active session, browser reconnect and Stop preserve traces.
- Reuse no-follow and mounted/active-container guards; no backups.
- Serialize new-session creation so simultaneous Start requests cannot clear a
  newly started session's traces. Failed cleanup must prevent launch.
- Verify synthetic cleanup and route lifecycle tests; do not restart the stack
  or remove live logs during implementation.

## Discovery

The API currently returns an active session before constructing a new one. Its
creation path is synchronous today; adding asynchronous cleanup requires a
creation lock. Stack startup cleanup already has reusable guarded deletion logic.

## Completed implementation and verification

- Added trace-only guarded cleanup before spawning each new real API session.
  Existing active-session return precedes cleanup; custom command overrides skip
  it. Stop preserves files. No home reset or backup is performed.
- Lifecycle lock covers Start and Stop; in-flight cleanup is awaited on request
  cancellation. Unsafe cleanup returns 409 and does not launch the runner.
- Updated /strace help, README and ADR-0038 for session-level retention.
- Synthetic lifecycle tests cover Stop/Start, shared joins, concurrent starts,
  pre-spawn ordering, home preservation, cleanup failure and command overrides.
  Guard tests verify active/mounted roots and symlink rejection without deletion.
- Full suite: 178 tests, 175 passed and three unrelated opt-in skips, including
  MCP and isolated strace container checks. npm run build and git diff --check pass.
- All acceptance criteria met. No live traces read/deleted, stack not restarted.
  User must restart the backend once to activate the new Start behavior.
