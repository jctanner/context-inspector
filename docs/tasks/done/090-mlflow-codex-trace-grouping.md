# Task 090: Investigate MLflow Codex gateway trace grouping

Read the linked MLflow Codex gateway guide and local checkout implementation.
Establish request/trace/session grouping, distributed trace support and OAuth
transport implications. Record evidence without changing runtime or checkout.

## Complete

Reviewed fetched official guide, gateway/provider wrappers, distributed tracing
tests, session metadata API and OTLP ingestion. Findings and concrete file/line
references recorded in ../../notes/mlflow-codex-trace-grouping.md. No runtime or
checkout changes; source review only. Request-level export/session grouping is
feasible; automatic full Codex conversation reconstruction not established.
