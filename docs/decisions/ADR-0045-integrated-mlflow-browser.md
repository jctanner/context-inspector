# ADR-0045: Integrated MLflow trace browser

## Status
Accepted, 2026-09-24.

## Context
Users should not need to discover a separate MLflow hostname/port to inspect
traces. The stack already owns the endpoint, experiment and service lifecycle.
Existing Claude and Codex exports have native session IDs; matching arbitrary
Claude traces to Inspector session IDs is not yet implemented. A previously
recorded v3 traces/get failure affects artifact-backed traces.

## Decision
Add an always-accessible MLflow navigation tab and read-only Inspector API routes.
The backend resolves the stack-owned loopback URL/experiment; the browser only
contacts Inspector. No arbitrary endpoint/path forwarding, redirects, API writes,
or upstream credential forwarding from the browser. Disabled/unmanaged services
get a clear status rather than connecting to an unrelated MLflow installation.

Search via POST /api/3.0/mlflow/traces/search (a read operation), scoped to the
stack experiment, 50 rows/page and optional exact native session metadata filter.
Detail verifies experiment membership with the trace-info REST endpoint, then
loads /ajax-api/3.0/mlflow/get-trace-artifact, the endpoint MLflow's own UI uses.
This works for artifact-backed traces without the known failing traces/get call.
Normalize legacy and current artifact span IDs/timestamps while preserving raw
MLflow JSON text and integer timestamp precision. Do not infer wire joins.

Default to all traces in this stack run, with native-session suggestions and a
Show this session action. Auxiliary callbacks retain their own recorded IDs.
The view lists span parentage, inputs, outputs, usage, attributes and raw data.
Poll every ten seconds only while the tab/document is visible; older pagination
pauses polling. Read-only controls and no-store responses apply throughout.
Fetches have ten-second timeouts and 16 MiB response bounds, with four concurrent
backend viewer operations. Values render as text, never executable HTML.

## Consequences
No separate browser origin, port entry or MLflow Python dependency is needed.
The full MLflow UI remains available separately; this tab does not provide
experiment editing, evaluations, trace deletion or other MLflow administration.
Native session filtering is exact; active Inspector/Claude session correlation is
not guessed. Ephemeral data lifetime and existing export gaps remain unchanged.
Large responses beyond the viewer limit get an explicit error.
