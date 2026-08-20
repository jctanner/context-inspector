# Task: Stream mitmproxy Events

## Goal

Extend the proxy capture path so request and response lifecycle events reach the
local GUI server while a Claude turn is active.

## Acceptance criteria

- [x] A complete request is emitted before the upstream response completes.
- [x] Streaming response content is represented without corrupting SSE data.
- [x] Completed-flow capture remains available for validation.
- [x] Credential headers are redacted before emission.
- [x] Proxy or receiver failure does not silently produce a successful-looking
  empty session.
- [x] Sanitized tests cover JSON, compressed, streaming, and error responses.

## Files likely involved

- `src/proxy/`
- `src/server/`
- `src/tests/`

## Discoveries and implementation

- `src/proxy/live_capture.py` emits protocol-v1 request, response-header,
  response-byte-range, completion, and error events. Each body retains the
  capture-boundary bytes as base64; decoded JSON/text/SSE is explicitly a
  derived view.
- The addon installs mitmproxy's response streaming callback at
  `responseheaders`, returns every chunk unchanged, and independently
  accumulates bytes for a completed archive record.
- `src/server/flows.py` validates and tails the per-session JSONL stream. The
  flow WebSocket accepts `after_sequence` for replay and sends malformed input
  as an explicit `stream-error` rather than an apparently empty session.
- The adapted runner uses unique proxy names, retains stopped proxy containers
  until logs are copied, checks both process liveness and event-file
  writability, runs the independent TLS smoke test, and warns on zero completed
  flows.
- The first real-container attempt proved that runtime state cannot be beneath
  the `:Z`-mounted workspace: the agent mount changed its SELinux label and the
  proxy addon received `EACCES`. ADR-0004 records the move to private `/tmp`
  state.

## Validation evidence

- `python -m unittest discover -s src/tests -v`: 21 tests passed, including the
  real loopback Uvicorn/WebSocket test.
- `bash -n src/runtime/run.sh` and `python -m compileall -q src` passed.
- A no-model-call real Podman run sent `curl https://api.anthropic.com/` through
  the sidecar using the mounted CA. It produced one completed archive and five
  validated live events in order: request, response headers, two response byte
  blocks, and completion. The retained proxy log contained no addon error.

## Status

Done
