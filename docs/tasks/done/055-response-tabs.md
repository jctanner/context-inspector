# Task: Closable response evidence tabs

- [x] Response inspection opens full-width Response #N, independently of Request #N.
- [x] Show text, tool calls and other blocks plus exact response evidence/provenance.
- [x] Fetch details lazily, reuse open tabs, support close/keyboard/retry/abort.
- [x] Live cards and collapsed repeat groups retain response inspection access.
- [x] No extra sockets or live-state side effects; build/browser regressions pass.

## Verification

Frontend build, diff whitespace check and 13 layout/documentation Python tests
pass. Response-tabs browser fixture verifies lazy loading, same-flow request and
response coexistence, both repeat-group creation paths, tool IDs/inputs, inert
text, exact wire evidence, caching, Memory navigation, mobile layout, retries,
keyboard close and actual request cancellation on close. Fast-replay, readability
and Memory fixtures also pass. Playwright closed; no backend restart or live
session input. README and ADR-0018 updated.
