# Task: Share the Active Session Across Browsers

## Goal

Discover and join the server's running Claude session without browser-local identity.

## Acceptance criteria

- Fresh and stale browser profiles discover the running session.
- Starting from two browsers reuses the same live process.
- Idle browsers discover sessions started elsewhere.
- Terminal output and captured context replay to both browsers.
- Tests and browser validation are recorded.

## Discoveries

- Session lifetime and output fan-out already belong to TerminalManager.
- Browser-local session IDs currently prevent discovery across profiles/origins.
- Updating the running Python server requires a restart that ends its current
  Claude session; preserve the user's live process during implementation.

## Validation

- All 59 Python tests pass with loopback socket permission. The live test checks
  discovery, repeated Start returning the same PID, simultaneous output fan-out,
  matching context replay, and no active session after Stop.
- `npm --prefix src/web run build` passes TypeScript checking and production build.
- Two isolated Playwright profiles on the test server: open both while idle,
  Start in one, verify both connect to the same ID; replace the other's saved ID
  with a stale value, reload, verify it rejoins the server's active session.
- Playwright attached to the existing production session using a browser-only
  discovery adapter backed by its known status endpoint: 17 request cards and
  2 response sections rendered, with live Claude terminal replay.

## Deployment

Production now serves the active-session endpoint. During the following review,
Playwright removed its temporary adapter, reloaded, discovered the new live
session normally and replayed its terminal and context. Deployment is complete.
