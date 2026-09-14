# Task: Ephemeral stack-managed MLflow

## Scope

Run a standalone MLflow container with each normal stack launch. No Claude
tracing, credentials, shared volumes, or persistent tracking state.

## Acceptance criteria

- [x] Normal launcher starts MLflow and waits for health before serving the app.
- [x] Every launch creates a new container/database/artifact store.
- [x] Shutdown and startup failure clean up only the owned container.
- [x] Loopback defaults, explicit image/port/host overrides and disable switch.
- [x] Unit lifecycle tests and real-container fresh-database smoke check.
- [x] Document launch, access, data loss, and deferred Claude integration.

## Discoveries

The launcher execs Python/Uvicorn; run.sh instead belongs to a Claude session.
Own MLflow in the Python entrypoint so browser reconnects and new Claude sessions
do not reset it. Direct ASGI test fixtures remain infrastructure-free.

## Verification

96 Python tests passed with CONTEXT_INSPECTOR_TEST_MLFLOW=1, including actual
Podman runs of ghcr.io/mlflow/mlflow:v3.16.0. UI returned HTML; experiment/run
creation and artifact upload/download succeeded. A second container on the same
port had neither the experiment nor the artifact (404). Image inspection confirms
no implicit volumes. Lifecycle unit tests cover readiness/retry/timeout/early exit,
startup errors, application errors, interrupts, disablement, unique ownership,
configuration validation, and entrypoint ordering. Whitespace check passes.

Initial smoke search returned 400 without max_results; fixture now supplies the
explicit limit recommended by the REST documentation and reports API error bodies.
No production defect discovered. Active stack/Claude session untouched; normal
restart is needed to activate MLflow. README and .env.example describe access and
ephemeral data loss. No Claude integration or host dependency added.
