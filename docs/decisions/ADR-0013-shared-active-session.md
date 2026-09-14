# ADR-0013: Server-Discovered Shared Active Session

## Status

Accepted

## Decision

The single-process server owns the shared active session. GET
`/api/sessions/active` returns its identity or null; POST `/api/sessions`
reuses it while alive. Selection uses the oldest live session deterministically.
The check and synchronous creation have no intervening await on the server loop.

Browsers discover on load and poll while idle. Local storage is a convenience
record, not the authority for session selection. Existing WebSockets fan out
terminal output and independently replay captured context to each viewer.

## Consequences

Input, terminal dimensions (last resize wins), and Stop are shared. History
clearing, expansion, and scroll position are browser-local. This does not add
durability across server restarts or multi-worker coordination. Deploy with one
Uvicorn process. Loading new Python code requires a restart; do not terminate a
user's existing session just to validate this feature.
