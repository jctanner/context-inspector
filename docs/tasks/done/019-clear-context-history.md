# Task: Clear Context History

## Goal

Let the user clear the right-pane request/response history without stopping or
altering the Claude session.

## Acceptance criteria

- [x] The context pane has an explicit Clear history control.
- [x] Clearing removes displayed cards but preserves terminal and Claude state.
- [x] New context events continue rendering after the clear point.
- [x] The clear watermark survives browser refresh for the active session.
- [x] Starting/stopping a session does not leak a stale watermark.
- [x] The context meter remains visible and unchanged.
- [x] Frontend regression tests and production build pass.

## Status

Done

## Implementation

The browser stores the latest derived-context event sequence as a per-session
watermark when Clear history is pressed. Cards and card-correlation maps are
cleared locally; terminal state, Claude, captured evidence, and the context
meter are untouched. Reconnect requests derived events strictly after the saved
sequence while the server still rebuilds its comparison baseline from history.

## Validation

- TypeScript checks and the Vite production build passed.
- All ten frontend regression tests passed.
