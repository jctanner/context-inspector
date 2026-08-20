# ADR-0003: Use Versioned, Replayable Live Flow Events

## Status

Accepted

## Context

The completed-flow JSONL capture cannot update a UI while a request is waiting
for a streamed model response. The proxy, server, and browser need a shared
contract that tolerates partial flows, reconnects, duplicates, and overload
without confusing an interpreted live view with the lossless archive.

## Decision

Use a versioned JSON event envelope with one monotonically increasing sequence
per inspector session and a stable event ID. Version 1 defines:

- `request.started`;
- `response.started`;
- `response.block`;
- `flow.completed`;
- `flow.error`; and
- `stream.gap`.

Every flow event carries the mitmproxy flow ID. Request and response bodies use
an explicit representation that distinguishes exact base64-encoded wire bytes
from optional decoded text, JSON, or SSE views. Browser-bound events declare
the applied sanitization policy.

Delivery is at least once. Consumers deduplicate by event ID and request replay
using the last accepted sequence. A bounded server buffer supports ordinary
browser reconnects. If any producer or server buffer loses events, the stream
must disclose the missing sequence interval with `stream.gap`; it must not
present the resulting state as complete.

The completed, lossless capture remains the authoritative archival artifact.
The live stream is an observable operational view.

## Consequences

Positive:

- The UI can render partial requests and streaming responses.
- Reconnect and duplicate delivery have deterministic behavior.
- Exact bytes remain distinguishable from decoded convenience views.
- Backpressure becomes a visible evidence-quality condition.

Negative:

- The producer must queue, retry, and number events.
- A bounded replay buffer cannot satisfy arbitrarily old cursors.
- Response blocks are transport observations and may not align with semantic
  model content blocks.
- Version evolution requires compatibility discipline.
