# Context Inspector Project Plan

## Objective

Build a local browser interface for interacting with the real Claude CLI in
the existing agent container while independently displaying the live model API
requests and responses captured by the mitmproxy sidecar.

## Completed milestone

- [M1 — Observable interactive session](docs/milestones/M1-observable-interactive-session.md)

## Active tasks

- None currently.

## Pending tasks

- None currently.

## Open bugs

- [Starlette TestClient hangs during startup](docs/bugs/open/starlette-testclient-startup-hang.md)
- [Browser requests a missing favicon](docs/bugs/open/missing-favicon.md)

## Decisions

- [ADR-0001 — Preserve the Claude CLI as the interaction surface](docs/decisions/ADR-0001-real-cli-over-sdk.md)
- [ADR-0002 — Python and TypeScript implementation](docs/decisions/ADR-0002-python-typescript-stack.md)
- [ADR-0003 — Versioned, replayable live flow events](docs/decisions/ADR-0003-versioned-live-flow-events.md)
- [ADR-0004 — Runtime state outside the workspace](docs/decisions/ADR-0004-runtime-state-outside-workspace.md)
- [ADR-0005 — Context-diff predecessor confidence](docs/decisions/ADR-0005-context-diff-predecessor-confidence.md)
- [ADR-0006 — Agent-header stream identity](docs/decisions/ADR-0006-agent-header-stream-identity.md)
- [ADR-0007 — Context utilization evidence](docs/decisions/ADR-0007-context-utilization-evidence.md)
- [ADR-0008 — Server-owned session lifetime](docs/decisions/ADR-0008-server-owned-session-lifetime.md)
- [ADR-0009 — Persistent Claude user state](docs/decisions/ADR-0009-persistent-claude-user-state.md)
- [ADR-0010 — Correlate responses by exact flow ID](docs/decisions/ADR-0010-correlate-responses-by-flow-id.md)
- [ADR-0011 — Purpose-specific comparison lineages](docs/decisions/ADR-0011-purpose-specific-comparison-lineages.md)
- [ADR-0012 — Require project-local environment](docs/decisions/ADR-0012-require-project-local-environment.md)

## Project plans

- [Overview](docs/plans/000-overview.md)
- [Phase 1 — Observable session](docs/plans/phase-01-observable-session.md)
- [Phase 2 — Context interpretation](docs/plans/phase-02-context-interpretation.md)
- [Phase 3 — Agent-stream attribution](docs/plans/phase-03-agent-attribution.md)

## Implementation notes

- [Validated Podman + mitmproxy runtime recipe](docs/notes/validated-podman-mitm-runtime.md)
- [Live event protocol v1](docs/notes/live-event-protocol-v1.md)
- [Structural context diff model](docs/notes/context-diff-model.md)
- [Request-stream identity investigation](docs/notes/request-stream-identity-investigation.md)

## Completed setup

- [Initialize the work ledger](docs/tasks/done/000-initialize-work-ledger.md)
- [Document the validated container runtime](docs/tasks/done/007-document-validated-container-runtime.md)
- [Define the live event protocol](docs/tasks/done/001-define-live-event-protocol.md)
- [Build the PTY-to-WebSocket terminal bridge](docs/tasks/done/002-build-terminal-bridge.md)
- [Stream mitmproxy flows while requests are active](docs/tasks/done/003-stream-proxy-events.md)
- [Build the two-pane browser shell](docs/tasks/done/004-build-browser-shell.md)
- [Render structural context diffs](docs/tasks/done/005-render-context-diffs.md)
- [Investigate request-stream identity](docs/tasks/done/006-investigate-agent-stream-identity.md)
- [Add a context utilization meter](docs/tasks/done/008-context-utilization-meter.md)
- [Make sessions survive browser refresh](docs/tasks/done/009-refresh-safe-session-reconnect.md)
- [Fix context meter settling](docs/tasks/done/010-fix-context-meter-settling.md)
- [Persist context meter between responses](docs/tasks/done/011-persist-context-meter-between-responses.md)
- [Calm the unmeasured context meter](docs/tasks/done/012-calm-unmeasured-context-meter.md)
- [Persist Claude user configuration](docs/tasks/done/013-persist-claude-user-configuration.md)
- [Clarify context diff provenance](docs/tasks/done/014-clarify-context-diff-provenance.md)
- [Render correlated model responses](docs/tasks/done/015-render-correlated-model-responses.md)
- [Label response evidence and purpose](docs/tasks/done/016-label-response-evidence-and-purpose.md)
- [Exclude internal calls from context meter](docs/tasks/done/017-exclude-internal-calls-from-context-meter.md)
- [Mute internal call cards](docs/tasks/done/018-mute-internal-call-cards.md)
- [Clear context history](docs/tasks/done/019-clear-context-history.md)
- [Classify harness context and request lineages](docs/tasks/done/020-classify-harness-context-and-request-lineages.md)
- [Investigate adjacent request events](docs/tasks/done/021-investigate-adjacent-request-events.md)
- [Fix title-purpose meter exclusion](docs/tasks/done/022-fix-title-purpose-meter-exclusion.md)
- [Initialize standalone repository](docs/tasks/done/023-initialize-standalone-repository.md)
- [Require project-local environment](docs/tasks/done/024-require-project-local-environment.md)
- [Assemble local environment](docs/tasks/done/025-assemble-local-environment.md)
- [Document stack architecture](docs/tasks/done/026-document-stack-architecture.md)
