# Task: Synchronize change navigation and payload outline

- [x] Next/Previous selects the containing JSON node and highlights the target row.
- [x] Automatically reveal collapsed/paged ancestors; choose Before for removed rows.
- [x] Preserve keyboard focus and scroll the outline without displacing the diff target.
- [x] Verify initial Previous, wraparound, nested/paged paths and existing regressions.

## Findings

Navigation and outline currently maintain independent selection state. Return a
row-selection controller from the outline and index node end lines as well as
starts, so closing delimiters map to their containing object rather than a leaf.

## Verification

- Frontend build and git diff whitespace check pass.
- All four synthetic browser fixtures pass; worker checks 166 cases including
  every node's end line as well as pointer/start line.
- Outline fixture covers first Previous/Next wrap, added/removed side switches,
  message 204 auto-paging, collapsed ancestors reopening, visible selection and
  actual diff target, and focus remaining on the navigation button.
- Existing request tabs, baseline retries, mobile layout and readability pass.
- Playwright closed; no live input or restart. Updated README and ADR-0022.
