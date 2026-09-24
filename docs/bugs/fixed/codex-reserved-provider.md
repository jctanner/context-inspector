# Codex rejects overriding the built-in provider

Native live probe on 2026-09-23: Codex 0.156.0 rejects a
`model_providers.openai.base_url` override because the ID is reserved. The
inspector launcher must select the built-in provider and use its native default
route, with conflicting base-URL environment variables removed.

## Resolution

Removed reserved-provider override; subsequent real Codex run succeeded.
