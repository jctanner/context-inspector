# Task: Inline and side-by-side payload diff layouts

- [x] Inline remains default; accessible layout buttons switch to Before/After columns.
- [x] Preserve every line, counts, baseline provenance and unequal additions/removals.
- [x] Outline and change navigation work in both layouts and retain location on switching.
- [x] Cache layout rendering without refetching; retain choice in an open request tab.
- [x] Build and browser regressions cover both layouts and narrow screens.

## Design

Reuse the same diff result. Align removed/added lines within each change hunk
by display order, leaving blank cells for unequal sides; this is visual pairing,
not an assertion of semantic identity. Build the second layout only on demand.

## Verification

Frontend build and whitespace checks pass. All four synthetic browser fixtures
pass, including 166 worker cases. Extended outline fixture verifies complete
Before/After reconstruction and sequential line numbers, aligned edits, blank
cells, first-request/identical/removal-heavy payloads, location transfer, split
Next-change and outline navigation, cached DOM/no extra fetches, open-tab layout
retention, and mobile width. README and ADR-0020 updated. Playwright closed;
no live session input, captures exported, or backend restart.
