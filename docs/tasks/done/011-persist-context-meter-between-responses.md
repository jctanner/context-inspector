# Task: Persist Context Meter Between Responses

## Goal

Keep the last completed context measurement visible while a newer request is
awaiting response usage.

## Acceptance criteria

- [x] A new request does not make a previously measured meter indeterminate.
- [x] The UI identifies the displayed value as the previous completed measure.
- [x] New response usage replaces the retained value.
- [x] A session with no measurement remains indeterminate.
- [x] Frontend regression coverage and production build pass.

## Status

Done

## Implementation

`renderContextDiff()` now checks whether the progress element already has a
determinate value. If so, it retains the bar and token label and marks them as
the previous completed measurement while the new request awaits usage. The
session reset path still removes the value, and `renderContextUsage()` still
replaces it with exact newer response accounting.

## Validation

- `npm run build` passed TypeScript checking and the Vite production build.
- All four frontend regression tests passed.
