# Task 089: Enable OAuth syscall tracing and search

User explicitly requests tracing for this personal stack, including OAuth.
Enable existing strace collection for Claude/OAuth and Codex/OAuth and expose the
search tab. Retain opt-out, trace cleanup, non-root execution and shared trace
storage. Verify runtime wrapping, capability UI/reconnect and search regressions.
No main stack restart or live-session attachment.


## Completed

Generalized the strace image/mount configuration and entrypoint wrapper to both
CLIs, and moved configuration outside the Vertex-only branch. Removed OAuth's
forced disable. All profiles advertise strace search; frontend legacy fallback
and browser fixtures updated. Existing output permissions, cleanup, opt-out and
non-root execution remain. ADR-0043 records explicit user authorization.

## Validation

- Full regression: 226 tests run, five skipped, all others pass (before adding
  the isolated container smoke test).
- Additional opt-in container test passes: installed Claude and Codex --version
  run under strace as UID/GID 1000 with network disabled, no credentials/workspace
  mounted, and mode-0600 per-process trace files. Image:
  localhost/context-inspector-strace-test:089.
- Runtime tests exercise Codex and Claude enable/disable, absolute executable
  paths and OAuth trace mount/capability. API checks expect tracing for both OAuth
  profiles. Browser OAuth launch/reconnect and five search scenarios pass.
- Frontend build, shell syntax and whitespace checks pass. Temporary server stopped.

Restart backend, create a new session and refresh browser to activate. Main stack
and active CLI untouched; no real OAuth credential traces collected during tests.
