# Task 085: Use native catalog evidence in the Codex context meter

Use inspector-owned model metadata to derive effective budgets. Preserve a
per-session snapshot for replay; label catalog-derived values separately from
wire usage, use the captured request model, honor explicit overrides, and leave
unknown/invalid models unknown. Cover HTTP and WebSocket usage and model changes.


## Completion and validation

Implemented shared catalog resolver for HTTP/WebSocket, exact request model
selection, override precedence and private per-session snapshot. Provenance is
catalog-derived with cache timestamp and runtime-override caveat. Unknown inputs
remain unknown; cached/reasoning token accounting is unchanged.

221 regression tests run, five skipped, all others pass. New tests cover metadata
validation, max-vs-effective distinction, immutable replay metadata, file mode,
model changes, unknown models, overrides and both transports. Mocked browser
inspection/reload displays 120 / 258,400 tokens with percentage and usage subsets.
No frontend source change or rebuild needed. Temporary server stopped. Backend
restart required; active user session untouched. See ADR-0040 for cache absence
and runtime override limitations.
