# MLflow v3 trace-detail endpoint returns HTTP 500

Observed during read-only inspection on 2026-09-15: GET
`/api/3.0/mlflow/traces/get?trace_id=...` returned HTTP 500 for both the delegation
and follow-up traces of the latest Claude session. Search succeeds and direct
GET of each trace's `traces.json` artifact succeeds. Cause uninvestigated; this
does not establish missing trace data or a frontend failure. No fix attempted.

## Task 093 workaround
The integrated trace browser uses the trace-info endpoint plus MLflow's own
get-trace-artifact endpoint. Real MLflow v3.16.0 REST validation passed for
metadata, session filtering, inputs/outputs, timestamps and parent IDs. The
underlying traces/get defect is not claimed fixed.
