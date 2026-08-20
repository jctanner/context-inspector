# Bug: Starlette TestClient Hangs During Startup

## Summary

The installed synchronous Starlette `TestClient` hangs while entering its
application context, before a request or WebSocket connection reaches Context
Inspector routes.

## Environment

- Python 3.14
- FastAPI 0.139.2
- Starlette 1.0.0
- HTTPX 0.28.1

## Reproduction

1. Construct the app with `create_app(settings=Settings())`.
2. Enter `with TestClient(app) as client:`.
3. Observe that `TestClient.__enter__` waits indefinitely in the AnyIO portal.

The same behavior occurs for a simple health request and a terminal WebSocket
test. A faulthandler dump placed the main thread in
`starlette.testclient.TestClient.__enter__` and the portal thread in the asyncio
selector.

## Expected

The test client's lifespan startup completes and tests can drive HTTP and
WebSocket routes in process.

## Actual

Startup does not return.

## Impact

Medium. Direct PTY and message-routing tests work, but end-to-end ASGI socket
tests require either a compatible dependency set or an external Uvicorn test
process.

## Workaround

Keep protocol and PTY lifecycle tests dependency-free. Validate the real socket
against a running loopback Uvicorn process until the compatibility issue is
resolved. Do not weaken production cleanup to accommodate the test client.

## Related tasks

- `docs/tasks/current/002-build-terminal-bridge.md`
- `docs/tasks/pending/004-build-browser-shell.md`
