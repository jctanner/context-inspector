# MLflow v3 trace-detail endpoint returns HTTP 500

Observed during read-only inspection on 2026-09-15: GET
`/api/3.0/mlflow/traces/get?trace_id=...` returned HTTP 500 for both the delegation
and follow-up traces of the latest Claude session. Search succeeds and direct
GET of each trace's `traces.json` artifact succeeds. Cause uninvestigated; this
does not establish missing trace data or a frontend failure. No fix attempted.
