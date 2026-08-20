# M1: Observable Interactive Session

## Status

Complete — 2026-08-19

## Outcome

A local user can open the browser, interact with the real Claude CLI, and see
the associated intercepted model flows appear alongside it.

## Required tasks

- `001-define-live-event-protocol.md`
- `002-build-terminal-bridge.md`
- `003-stream-proxy-events.md`
- `004-build-browser-shell.md`

## Validation

Run one ordinary Claude turn through the two-container setup and demonstrate:

1. interactive terminal input and ANSI output;
2. a live request event before model completion;
3. response blocks or a completed response event;
4. matching flow identity across the event lifecycle;
5. clean shutdown of the CLI and proxy containers.

## Evidence

- Tasks 001–006 are complete in the filesystem ledger.
- The user validated real interactive Claude sessions through the browser and
  observed live request/response traffic.
- Real no-model-call container validations independently proved proxy startup,
  TLS interception, live lifecycle emission, archive extraction, and cleanup.
- The complete automated suite passes 33 tests, including real loopback HTTP,
  terminal WebSocket, raw-flow WebSocket, and derived-context WebSocket paths.
- The production TypeScript/Vite build passes.
