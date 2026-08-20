# Task: Fix Context Meter Settling

## Goal

Make the context utilization meter settle on wire-observed response usage after
each completed Claude interaction.

## Acceptance criteria

- [x] Real captured response usage is recognized in its observed SSE form.
- [x] Usage is correlated to the request whose context is displayed.
- [x] The meter becomes determinate after a normal interaction.
- [x] Missing usage remains explicitly indeterminate rather than estimated.
- [x] Regression tests cover the failing capture shape and browser behavior.

## Status

Done

## Findings

- The observed Vertex response is a gzip-compressed SSE stream.
- mitmproxy supplied arbitrary transport chunks, frequently one byte each.
- Decoding every chunk as an independent gzip document failed, even though the
  concatenated exact wire bytes formed a valid gzip response containing usage.
- Context derivation now buffers exact response bytes by `flow_id`, applies the
  wire-observed content encoding after completion, and parses the reassembled
  SSE. It retains the prior incremental path for independently decodable SSE.

## Validation

- Inspected a live capture without exposing request or response content: the
  response blocks were marked failed individually, while their exact combined
  bytes decoded as gzip SSE with a `message_start` usage object.
- Added a regression using a gzip SSE response split into one-byte blocks.
- `npm run build` passed.
- `python -m unittest discover -s src/tests -v` — 39 tests passed.
