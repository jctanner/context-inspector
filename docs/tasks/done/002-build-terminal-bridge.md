# Task: Build the PTY-to-WebSocket Terminal Bridge

## Goal

Expose the real interactive Claude CLI running in the agent container to a
browser terminal without using an agent SDK.

## Acceptance criteria

- [x] The backend launches the existing container runner through a real PTY.
- [x] Browser input reaches the CLI unchanged.
- [x] ANSI output renders correctly in xterm.js.
- [x] Browser resize events update the PTY dimensions.
- [x] Exit, disconnect, interruption, and failure cleanup are tested end to end.
- [x] The service binds to loopback by default.

## Files likely involved

- `src/server/`
- `src/tests/`

## Status

Done

## Notes

- `src/server/terminal.py` owns the PTY and preserves raw ANSI bytes.
- `src/server/app.py` exposes session lifecycle and terminal WebSocket routes.
- The default argv invokes the existing MITM runner without a shell.
- Direct tests cover input, output, ANSI preservation, resize, forced cleanup,
  control messages, runner resolution, and loopback enforcement.
- The installed Starlette `TestClient` hangs during application startup on this
  Python 3.14 environment; the end-to-end test instead launches real Uvicorn.
- The minimal two-pane xterm.js shell builds and was rendered in headless Chrome
  at 1600×1000 with a calculated 93×55 terminal grid.
- The real Uvicorn test covers HTTP session creation, binary ANSI WebSocket
  output, browser input, resize submission, disconnect, and session cleanup.
- `python -m unittest discover -s src/tests -v` passes 17 tests when loopback
  socket creation is permitted.
