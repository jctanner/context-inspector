# Task: Optional full request payload diff

- [x] Add a request-tab toggle between block inspection and a complete unified diff.
- [x] Compare captured decoded JSON bodies against the recorded predecessor, never
  a guessed adjacent request. Label pretty printing and comparison confidence.
- [x] Show line numbers, additions/deletions, unchanged lines, and change navigation.
- [x] Load baseline only on demand, keep computation off the UI thread, and cancel
  on tab close. Handle first requests and missing baseline evidence explicitly.
- [x] Verify synthetic comparisons and browser behavior; rebuild frontend.

## Verification

TypeScript/Vite build and diff whitespace check pass. Worker browser test passes
155 exact reconstruction cases, including first request, identical payloads,
repeated lines and large bounded fallback. Extended fast-replay browser fixture
checks recorded-baseline fetch, no eager baseline fetch, full context lines,
toggle reuse, navigation and unavailable-baseline failure/retry. Existing
readability/browser regressions pass. Tests use only synthetic payloads; all
Playwright contexts/tabs closed. Frontend bundle rebuilt; no server restart needed.

## Design

ADR-0020 documents whole decoded-body scope, evidence limitations and bounded
worker fallback. Existing exact captured request disclosures remain available.
