# Task: Render Correlated Model Responses

## Goal

Show each model response alongside the request-context diff with explicit
wire-versus-reconstructed provenance.

## Acceptance criteria

- [x] Responses correlate to requests by exact `flow_id`.
- [x] Gzip/SSE responses are reconstructed only after complete wire capture.
- [x] Semantic response content blocks and completion metadata are summarized.
- [x] Exact captured response headers and bytes remain separately expandable.
- [x] Response transport chunks are not presented as semantic blocks.
- [x] Server, frontend, and replay regression tests pass.

## Status

Done

## Implementation

- The derived context stream now emits `context.response` after a complete SSE
  response is captured and decoded.
- Text, thinking, signature, and tool-input deltas are reconstructed into
  semantic response content blocks.
- The browser attaches the response to the matching request card by exact
  `flow_id`, shows model/stop/output-token metadata, and separates reconstructed
  blocks from exact response evidence.

## Validation

- TypeScript checks and the Vite production build passed.
- All 45 Python tests passed, including gzip one-byte reassembly, semantic SSE
  reconstruction, exact response evidence, replay, and real WebSockets.
