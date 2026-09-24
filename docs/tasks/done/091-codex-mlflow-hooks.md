# Task 091: Investigate native hooks for Codex MLflow integration

Inspect checkouts/codex and compare lifecycle/plugin interfaces with MLflow.
Identify turn/session data, existing integrations and dynamic runtime setup.
Research only; do not install or activate a plugin in the running session.

## Complete

Found existing @mlflow/codex notify/transcript integration, native session/turn
IDs and modern plugin hooks. Findings, source paths, configuration direction and
remaining compatibility tests recorded in ../../notes/codex-mlflow-hooks.md.
Read-only source review plus isolated installed-CLI features command; no live
hook/export tests or runtime configuration changes.
