# Bug: Page Refresh Terminates the Claude Session

## Observed

Refreshing the browser closes the terminal WebSocket, stops the server-owned
PTY, and destroys the Claude/proxy containers. The browser also forgets its
session ID.

## Cause

The terminal WebSocket cleanup path called `TerminalManager.stop()`, conflating
a browser attachment with the lifetime of the underlying Claude session. The
frontend kept its session ID only in JavaScript memory.

## Expected

Refresh detaches and reconnects. Only explicit Stop, CLI/runner exit, or server
shutdown ends the underlying session.

## Resolution

The server now unsubscribes a disconnected terminal WebSocket without stopping
the PTY. The browser persists the session ID, checks the session-status endpoint
on load, and reconnects terminal and context streams when the process is alive.
Explicit Stop and server shutdown remain authoritative cleanup paths.

Fixed by task 009 on 2026-08-19.
