# Task: Recover Context Streams Without Refresh

## Acceptance criteria

- Context connections have independent visible status and automatic reconnect.
- Replay recovers missed events without duplicate cards, including derived events
  sharing a wire sequence; old session sockets/timers cannot reconnect.
- Partial JSONL writes are retried instead of consumed as broken records.
- Browser reconnect and server partial-write regressions pass.

## Investigation

The user's browser stalls while capture continues. Its exact disconnect cause
is not directly observable here. Code confirms no close/retry handling in the
browser and both JSONL readers advance past incomplete trailing writes.

## Validation and deployment

- 60 Python tests pass, including deterministic partial-write tests for both readers.
- TypeScript and production build pass.
- Synthetic Playwright checks pass: close context socket, recover missing cards,
  deduplicate replay, receive response sharing a usage sequence, recover a record
  error, and show independent context status without browser refresh.
- Live Playwright reloaded the built frontend and connected to both streams.
- Frontend recovery is deployed; existing browsers must refresh once to load it.
  Server reader fix awaits the next normal server restart to preserve the current
  Claude session. Browser replay also handles errors from the old reader.
