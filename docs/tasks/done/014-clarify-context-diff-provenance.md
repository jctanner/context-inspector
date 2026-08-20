# Task: Clarify Context Diff Provenance

## Goal

Make it immediately clear that context-change blocks are derived from model
requests, not responses or HTTP transport chunks.

## Acceptance criteria

- [x] Pane and block labels explicitly say request context.
- [x] Every diff card states its request-only derivation.
- [x] The UI distinguishes response usage from request context.
- [x] Frontend regression coverage and production build pass.

## Status

Done

## Validation

- `npm run build` passed TypeScript checks and the Vite production build.
- All six frontend regression tests passed.
