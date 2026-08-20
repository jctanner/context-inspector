# Task: Add a Context Utilization Meter

## Goal

Show the most recent model request's measured input-token usage relative to an
explicitly configured context-window limit without presenting byte estimates as
token evidence.

## Acceptance criteria

- [x] Response usage is correlated to its exact request flow.
- [x] Cache-read, cache-creation, and uncached input tokens are summed.
- [x] The UI shows used tokens, configured limit, percentage, and provenance.
- [x] Before usage arrives, the meter says it is awaiting response accounting.
- [x] Identified streams retain independent latest-usage values.
- [x] Missing or malformed usage never becomes a fabricated percentage.
- [x] Deterministic and live-WebSocket tests cover the update path.

## Implementation and evidence

- The context event stream buffers arbitrary SSE chunk boundaries, extracts
  explicit response usage, and emits `context.usage` for the exact `flow_id`.
- The browser retains usage by stream and displays the most recent request's
  correlated value. A late response from an older request cannot overwrite it.
- The progress element is indeterminate before accounting arrives. Its detail
  text distinguishes exact request bytes, wire response usage, and configured
  context-window capacity.
- ADR-0007 records why bytes are not converted to tokens and why the context
  limit is configuration rather than inferred fact.
- The TypeScript/Vite production build passes. All 36 Python tests pass,
  including fragmented SSE parsing and the real context WebSocket update.

## Status

Done
