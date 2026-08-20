# Task: Render Structural Context Diffs

## Goal

Show how the effective model input changes from the preceding request without
reducing nested API payloads to an unreadable line diff.

## Acceptance criteria

- [x] Requests are normalized into system, tools, messages, and content blocks.
- [x] Additions, removals, retained blocks, and transformations are shown.
- [x] Users can expand from summaries to exact captured fields.
- [x] Byte and available token counts are retained with each comparison.
- [x] Retries and compaction do not produce misleading predecessor choices.
- [x] Deterministic tests cover known capture transitions.

## Files likely involved

- `src/server/`
- `src/web/`
- `src/tests/`

## Discoveries

- Wire transport chunks are not context changes. The default UI now collapses
  the response lifecycle by exact `flow_id`; otherwise high-volume SSE blocks
  obscure the request sequence that this task needs to compare. Raw block
  evidence remains in the protocol stream and completed archive.
- Podman process state is not service readiness. The runner now probes the
  proxy socket from inside its container before starting the curl smoke test.

## Implementation and validation

- `src/server/context.py` implements deterministic normalization, structural
  comparison, replay with reconstructed baselines, and explicit relationship/
  confidence metadata.
- `/api/sessions/{session_id}/contexts` exposes derived model-request
  comparisons; the raw `/flows` evidence stream remains independent.
- The browser displays one card per model request, grouped changes, exact
  captured request fields, wire byte counts, and explicit token availability.
  Large values are materialized only when expanded.
- ADR-0005 records the low-confidence chronological predecessor policy pending
  agent-stream attribution.
- `npm run build` passed. The complete Python suite passed all 30 tests,
  including concurrent real terminal, raw-flow, and context WebSockets.

## Status

Done
