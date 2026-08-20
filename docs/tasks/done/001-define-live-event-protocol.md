# Task: Define the Live Event Protocol

## Goal

Define the versioned messages exchanged among the proxy addon, local server,
and browser for request and response lifecycles.

## Context

The existing capture format records completed flows. The GUI also needs to
represent a request before its streaming response has completed.

## Acceptance criteria

- [x] Request-start, response-start, response-block, completion, and error
  events have stable schemas.
- [x] Events share an unambiguous flow identifier.
- [x] Exact bytes and decoded representations are distinguishable.
- [x] Redaction occurs before sensitive metadata reaches the browser.
- [x] Backpressure, reconnect, and partial-flow behavior are specified.
- [x] Schema validation tests are defined.

## Files likely involved

- `src/server/`
- `src/proxy/`
- `src/web/`
- `docs/decisions/`

## Status

Done

## Notes

- Protocol v1 is specified in `docs/notes/live-event-protocol-v1.md`.
- ADR-0003 records replay, gap, and exact-versus-decoded decisions.
- `src/protocol/events.py` is the dependency-free reference validator.
- `python -m unittest discover -s src/tests -v` passed 6 tests on
  2026-08-19.
