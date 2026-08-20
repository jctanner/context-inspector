# ADR-0010: Correlate Reconstructed Responses by Exact Flow ID

## Status

Accepted — 2026-08-19

## Decision

Each displayed model response attaches to its request-context card using the
exact mitmproxy `flow_id`. The server buffers the complete captured response,
decodes its observed content encoding, parses complete SSE records, and
reconstructs semantic model content blocks from start/delta events.

The reconstructed blocks are labeled interpreted data. Exact sanitized
response headers and compressed wire bytes have their own expandable evidence
section; the losslessly decoded SSE has a separate interpreted section.
Arbitrary `response.block` transport chunks are never labeled semantic model
blocks.

Purpose is conservative inference, not capture evidence. A likely internal
title-generation label requires both a title-generation instruction in the
request and a response consisting of one JSON object with only a `title` field.
The UI exposes confidence and evidence. All unmatched calls remain unclassified
rather than being assumed primary.

## Consequences

- Request and response provenance is visible as a matched pair.
- Response content appears after flow completion, not token-by-token.
- Exact response evidence can be large and sensitive, so the browser
  materializes its textual rendering only when expanded.
- Non-SSE or unsupported-encoding responses remain absent from this semantic
  projection while remaining available in raw captures.
