# ADR-0024: Ephemeral MLflow owned by the stack entrypoint

## Status

Accepted

## Decision

The Python entrypoint owns one uniquely named Podman MLflow container around
Uvicorn. Pin the official image version; use explicit SQLite and artifact paths
in the disposable writable container layer, with no mounts or forwarded host
environment/credentials. Wait for HTTP health, fail startup on failure, and
remove only this launch's container in a finally block. Never reuse old state.

Default to loopback port 5000. Remote access requires explicit bind and Host
allowlist configuration; do not disable MLflow security middleware. A disable
switch supports frontend-only development. Direct create_app/ASGI use does not
own infrastructure; src/bin/context-inspector and python -m src.server do.

## Consequences

Database and artifacts disappear on normal shutdown. A hard kill may leave an
orphan container (manual removal by exact name), but subsequent launches never
adopt it; a port collision fails rather than silently replacing another stack.
Images are cached, not tracking data. First pull can take time. Separate Claude
sessions and browser reloads do not reset MLflow. No tracing export, SDK dependency,
shared Claude state, or agent network integration is added in this phase.

Task 057 / ADR-0025 subsequently adds Claude tracing over the existing private
container network. The ephemeral storage and loopback host-access policy remain.

Task 058 uses the explicit remote-access opt-in for this installation only:
local .env binds 0.0.0.0 with enumerated hostnames/IPv4 addresses. Code defaults
remain loopback; no wildcard Host allowance or authentication is introduced.

Task 059 adds an independently configured browser-origin allowlist via
--cors-allowed-origins. Remote browser origins include scheme and port; Host
allowance alone is insufficient for browser POSTs. Keep both protections enabled
and list explicit remote origins rather than using a global wildcard.

References: [official image](https://mlflow.org/docs/latest/ml/docker/),
[tracking server](https://mlflow.org/docs/latest/self-hosting/architecture/tracking-server/).
