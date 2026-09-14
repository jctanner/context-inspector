# Bug: Side-by-side diff header text overlaps

The Change heading is wider than its fixed 2rem column (1rem on mobile), so it
overlaps the payload heading. Before line also overflows at narrow widths.
Reproduced with browser text-range measurements at 1280px and 390px.
Task 052 replaces verbose gutter headings and fixes explicit column sizing.

Fixed: grouped Before/After headers, # and +/− gutters with accessible names,
explicit colgroups and scoped split header styles. Five-width browser checks pass.
