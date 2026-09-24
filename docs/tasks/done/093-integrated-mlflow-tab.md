# Integrated MLflow trace browser

## Goal
Expose the stack MLflow traces through Context Inspector backend routes and a new frontend tab, without asking users to find MLflow URLs/ports.

## Acceptance criteria
- [x] Backend uses stack-owned endpoint and experiment, offers bounded read-only status/search/detail APIs; no arbitrary URL proxying or trace writes.
- [x] New MLflow tab lists paginated traces, session filter, refresh and spans/inputs/outputs/usage/raw details, with clear disabled/error/empty states.
- [x] Preserve native IDs and transcript-derived evidence; do not infer wire correlation.
- [x] Verify published MLflow REST behavior including recorded trace GET failure, unit/API/browser tests and production build.
- [x] Record architecture, evidence, limitations and activation; no restart of active stack.

## Scope
Asked whether default should be all stack traces or active session; recommend all traces with native session filter. Independent backend and display work proceeds while awaiting preference.


## Outcome
Implemented backend /api/mlflow/status, /api/mlflow/traces and trace detail
routes; new always-available MLflow navigation tab. Default all current-stack
traces, exact native-session filter with suggestions and Show this session.
Paginated summaries, parent-ID span tree, inputs/outputs/usage/status/attributes,
raw JSON and precision-preserving nanosecond duration calculations. List polling
only while visible; paging older results pauses automatic refresh.

Backend uses existing stack endpoint/config and requires its experiment identity.
Search is a read-only REST POST, details use trace-info plus MLflow UI artifact
endpoint. Validates experiment membership before artifact reads; browser cannot
specify URLs. No redirects/host proxy forwarding, no-store responses, bounded
reads/timeouts/concurrency. Clear disabled/unmanaged/unavailable/empty states.
Known traces/get 500 bypassed, not declared fixed. Current and legacy artifact
span schemas normalized; raw JSON retains timestamps as exact text.

## Validation (2026-09-24)
- Full suite: 246 tests run, eight opt-in skips, all others pass.
- Separate isolated MLflow v3.16.0 REST test passed: real synthetic AGENT/TOOL
  spans, search, exact native-session filter, missing-session empty result,
  metadata, span artifact, inputs/outputs, timestamps and exact parent ID.
- Unit/API tests: stack ownership/disable, fixed loopback, paging parameters,
  invalid IDs/filter injection/dot segments, wrong-experiment rejection,
  size limits/timeouts, private errors, read-only/no-store endpoints.
- MLflow Playwright fixture passed: same-origin GET-only browser requests,
  no fetch before tab opens, visible polling and hidden-tab cancellation,
  selection/span details/raw precision, native-session filter, older pages,
  XSS-as-text handling, empty/disabled/unavailable states, 390px viewport.
- Existing strace browser regression passed. Production TypeScript/Vite build
  and git diff --check pass. No active stack restart or private trace access.

## Activation and limits
Restart the backend/stack normally and refresh the browser to activate the API
and tab. Existing stack shutdown still clears ephemeral MLflow data. No separate
MLflow address or login needed. Native sessions are not automatically equated to
Inspector sessions, and trace spans are not claimed to be exact wire requests.
No MLflow administration, editing or deletion is exposed. See ADR-0045.
