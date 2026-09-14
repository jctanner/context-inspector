# ADR-0020: Full-payload unified diff

## Status

Accepted

## Decision

Updated 2026-09-14 by task 047: request tabs default to Full payload diff,
with optional Block inspection available through the toggle. Existing open tabs
preserve their selected view. Compare complete decoded captured JSON bodies against the recorded
predecessor_flow_id through the existing detail API; never reconstruct a payload
from block changes or substitute chronological adjacency. Fetch baseline only
when a request tab opens, never for live summary cards. Explain pretty printing,
baseline identity, and comparison confidence.
Headers, wire encoding and original whitespace remain in exact request evidence,
not in this explicitly labelled decoded-body view.

Use an isolated worker for bounded Myers line comparison; beyond the time/edit
budget, show the changed region as an explicitly labelled full replacement.
Include every unchanged and changed line, two line numbers, +/- markers, and
change navigation. Build rows in frame-sized batches, use textContent only, and
terminate work when the request tab closes. A missing baseline is an error, not
an empty request. Only a genuinely absent predecessor means all additions.

## Consequences

Task 051 adds Inline / Side-by-side layout controls (Inline remains default).
Cache a second DOM layout on demand using the same diff lines; align each hunk's
removals/additions by order with blank cells for unequal lengths. This is visual
alignment, not semantic block matching. Each layout has side-specific outline
targets; transfer the selected side/line when switching and retain hunk position.
Both layouts share counts, provenance and the original bounded-diff fallback.

No backend restart, new dependencies, live sockets, or persisted captured content.
Repeated toggles reuse the view. Full payloads consume memory proportional to
their size and open tabs; no block expansion is required. Very long JSON strings
wrap as escaped JSON lines, not reconstructed multiline source. The bounded
fallback may be less minimal than a Git diff but never hides payload content.
