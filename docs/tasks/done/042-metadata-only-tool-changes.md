# Task: Explain metadata-only tool changes

## Acceptance criteria

- [x] Metadata-only tool changes show one neutral unchanged tool call, not red/green duplicates.
- [x] Exact changed fields remain visible; real input changes still show before/after.
- [x] Browser regression tests cover tool metadata and changed inputs; build passes.

## Evidence

Request 83 changes only cache_control on a tool_use value. Current unchanged-text
handling misses tool calls. See identical-tool-change-panels bug.

## Implementation and verification

Compare all tool_use/tool_result fields except cache_control canonically before
labeling tool content unchanged. Show one neutral collapsed disclosure, preserving
the exact changed-field table and raw evidence. Changed inputs or IDs retain
before/after. This extends existing metadata presentation, without changing the
wire-derived classification or attribution.

TypeScript/Vite build and git diff --check pass. Both Playwright browser fixtures
pass; new regression cases cover cache hints added/removed/modified, key order,
tool results, changed input and changed ID. Synthetic fixtures only; no captured
request content committed. Playwright closed after testing. Refresh loads the fix.
