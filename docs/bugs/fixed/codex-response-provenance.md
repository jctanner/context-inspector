# Codex response view inherits Claude-only provenance

Discovered during task 082 browser validation on 2026-09-23. The shared response
renderer labels all evidence as reconstructed SSE correlated by an exact HTTP
flow ID. Codex uses logical WebSocket messages and lane-order pairing followed
by response IDs, so this text overstates evidence and describes the wrong
transport. Provider-specific provenance is required before enabling Codex.

Reproduction: feed a synthetic Codex `context.response` into the shared response
renderer and open its evidence disclosure.

## Resolution

Provider-specific response text now describes preserved logical WebSocket
messages and lane-order/response-ID correlation for Codex. The isolated Codex
inspection browser fixture verifies the displayed provenance and reload. Fixed
in source; live Codex launch remains gated by task 082.
