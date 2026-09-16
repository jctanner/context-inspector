# ADR-0035 — Shared request/response payload viewer

## Status

Accepted.

## Decision

Extract the existing worker-backed payload viewer behind a generic async loader.
Request baseline behavior is unchanged. Response tabs default to neutral full
decoded SSE event JSON with the same outline, navigation and inline/split renderer.
Retain readable reply and original wire/SSE evidence behind an explicit toggle.

Parse all SSE records in order, retaining raw field lines, non-JSON data, comments,
unknown events and unterminated tails. Pretty-printed event objects are a decoded
representation, not an original single JSON response or reconstructed reply.

Comparison is opt-in using earlier response summaries in currently loaded session
history, labeled by request number and exact flow ID. Fetch a selected baseline
only on demand; failures never substitute another response. This is a user-selected
comparison, not proof of primary/subagent identity or conversation relationship.
Closing/switching aborts baseline loads and workers. No new backend APIs required.
