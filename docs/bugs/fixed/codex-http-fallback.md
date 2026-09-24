# Codex HTTP Responses fallback is not captured/interpreted

Task 082, 2026-09-23: capture supports Codex WebSockets but excludes its HTTP POST
Responses route. Enabling the profile would silently lose fallback requests.
The Claude normalizer can also misclassify a Responses request containing tools.
Add an exact-route HTTP selector and separate interpreter before enabling Codex.

## Resolution

Exact-route HTTP selection, distinct SSE interpreter and replay/gap/compression tests pass.
