# Task: Explain Metadata-Only Block Changes

## Acceptance criteria

- Identical text is explicitly labeled unchanged and displayed once on demand.
- Added, removed and modified non-text fields show before/after values directly.
- Real text changes still display Before/After text and any simultaneous field changes.
- Raw evidence remains available; no captured data is changed.
- Build, browser regression and real-session verification pass.

## Discovery

The inspected block's text was identical; only cache_control was removed. The
readable renderer hid that field while the comparator correctly marked the
whole block transformed. All actual system blocks were retained.

## Validation

All acceptance criteria passed. Production build and TypeScript check pass;
11 web regression tests pass. Extended synthetic Playwright checks cover field
addition/removal/modification, mixed text and metadata changes, no duplicate text
panels, and narrow-screen table layout. Live last-card verification reads
“Text unchanged · cache-control metadata removed”, shows ephemeral → Not present,
and contains zero Before/After text panels. Browser refresh loads the fix.
