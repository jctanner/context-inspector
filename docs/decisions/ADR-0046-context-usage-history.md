# ADR-0046: Context usage history

## Status
Accepted, 2026-09-24.

## Decision
Render a dependency-free SVG line graph above the context meter from the existing
flow-keyed usage map and internal-call exclusion set. Propagate source event
occurred_at into Claude and Codex usage events; never substitute browser arrival
time. Horizontal spacing reflects capture time, percentage uses the same reported
usage/limit as the meter. Missing timestamps or measurements break the line.

## Consequences
History is explicitly scoped to loaded requests, extends with pagination/live
events, and resets on clear/new session. No new storage or API is introduced.
Replay deduplicates by flow. This remains the meter's mixed non-internal request
view, not an assertion that all points belong to a single native agent thread.
Old running backends require restart to emit timestamps. Responsive SVG points
provide hover and keyboard details; the original numeric meter remains visible.
