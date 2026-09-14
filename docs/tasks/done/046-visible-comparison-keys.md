# Task: Show comparison keys on live cards

- [x] Display the exact comparison_lineage key beside the request summary, including
  collapsed repeat groups, without fetching details.
- [x] Do not label inferred grouping as a confirmed conversation/agent identifier.
- [x] Preserve full selectable keys with wrapping; verify browser regressions/build.

## Verification

Comparison group shows comparison_lineage verbatim on summary/full cards and
outside collapsed repeat disclosures. Tooltip clarifies that this is a grouping
key within the capture session, not necessarily a unique conversation ID. No
additional detail fetches. TypeScript/Vite build, diff check and both browser
fixtures pass, including exact-key and collapsed-group assertions. Playwright
closed. Refresh loads the rebuilt frontend; no server restart needed.
