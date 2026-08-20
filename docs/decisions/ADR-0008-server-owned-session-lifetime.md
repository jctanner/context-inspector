# ADR-0008: Keep Session Lifetime Independent of Browser Attachments

## Status

Accepted — 2026-08-19

## Decision

The Context Inspector server owns each Claude PTY session. Terminal and context
WebSockets are detachable views of that session; disconnecting a view does not
terminate the process. The browser persists the opaque session ID and validates
it with `GET /api/sessions/{session_id}` before reconnecting.

Sessions end when the user invokes the explicit Stop endpoint, the underlying
CLI exits, or the Context Inspector server shuts down. Runtime state is not yet
recoverable across server restarts.

## Consequences

- A refresh or transient WebSocket failure no longer destroys Claude or the
  proxy container.
- Multiple sequential browser attachments can observe the same PTY session.
- Terminal history is bounded by the server's replay buffer; captured context
  history is reconstructed from the session event log.
- Persisted stale IDs are harmless: validation clears them instead of creating
  a misleading connection state.
