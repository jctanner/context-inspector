# Source tree

All executable Context Inspector code and its tests belong in this directory.

The intended components are:

```text
src/
  server/       local orchestration, PTY, WebSocket, and event correlation
  proxy/        mitmproxy live-event addon
  web/          browser terminal and context inspector
  tests/        cross-component and sanitized-fixture tests
```

These component directories should be created by the tasks that establish
their concrete build systems, rather than committing empty placeholders.
