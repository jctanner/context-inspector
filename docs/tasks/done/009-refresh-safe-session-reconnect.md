# Task: Make Sessions Survive Browser Refresh

## Goal

Decouple browser WebSocket attachment lifetime from the real Claude CLI session
and reconnect to an existing session after navigation or refresh.

## Acceptance criteria

- [x] Terminal WebSocket disconnect does not stop the PTY or containers.
- [x] Explicit Stop remains authoritative and cleans up the session.
- [x] Browser persists and validates the active session ID.
- [x] Refresh reconnects terminal output and replays context observations.
- [x] A stale persisted session is cleared safely.
- [x] CLI exit is distinguished from browser disconnect.
- [x] Real-server tests cover detach, reconnect, and explicit stop.

## Status

Done

## Findings

- A terminal WebSocket is an attachment to a server-owned PTY, not its owner.
- The browser stores only the opaque session ID and validates it through the
  session-status endpoint before reconnecting.
- Context observations replay from the recorded event stream. Terminal output
  replays from the PTY session's bounded in-memory history.
- Browser refresh survives; server restart remains an intentional lifetime
  boundary and invokes `stop_all()`.

## Validation

- `npm run build` — TypeScript checks and production build passed.
- `python -m unittest discover -s src/tests -v` — 37 tests passed.
- The real-server test detached its first terminal WebSocket, confirmed the PTY
  remained alive, reconnected and exchanged input, then explicitly stopped the
  session and confirmed a subsequent status lookup returned 404.
