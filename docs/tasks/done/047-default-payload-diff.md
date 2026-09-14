# Task: Default request tabs to full payload diff

- [x] Newly opened request tabs show full payload diff immediately.
- [x] Block inspection remains one toggle away, including when baseline loading fails.
- [x] Reopened existing tabs preserve their selected view; live cards stay lazy.
- [x] Update browser regressions and documentation; build and verify.

## Implementation and verification

Reuse the existing toggle transition on request-tab initialization. Baseline
loading now starts when the tab opens, without eagerly fetching live cards.
ADR-0020 and README updated. No backend or session restart needed.

Frontend build and both fast-replay/readability Playwright fixtures pass,
including default visibility and accessible selection, cached view switching,
baseline failure/retry and optional block inspection after failure. Playwright
closed after synthetic fixture tests. Diff whitespace check passes.
