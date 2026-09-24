# Native Codex control events prematurely interrupt call pairing

Live OAuth/proxy probe on 2026-09-23 observed `codex.rate_limits` and
`codex.response.metadata` before `response.created`, plus
`responsesapi.websocket_timing` around completion. The adapter incorrectly
classifies the first control event as a response missing its creation event,
removing the pending request and losing readable responses and usage. Keep
these observed connection-control events in the raw stream without assigning
or interrupting a model call.

## Resolution

Observed control events remain raw without call attribution; replay of the actual capture yields three completed responses and usage; synthetic regression added.
