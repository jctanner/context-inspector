# Context Inspector Project Plan

## Objective

Build a local browser interface for interacting with the real Claude CLI in
the existing agent container while independently displaying the live model API
requests and responses captured by the mitmproxy sidecar.

## Completed milestone

- [M1 — Observable interactive session](docs/milestones/M1-observable-interactive-session.md)

## Active tasks

- None currently.

## Awaiting deployment

- [Project-local workspace](docs/tasks/blocked/037-local-workspace.md) — 13 tests
  pass; restart and container recreation needed to replace the parent-directory mount.

- [Fast context replay](docs/tasks/blocked/036-fast-context-replay.md) — tested;
  new Python API requires a restart that ends the active Claude session. Frontend
  bundle is rebuilt and falls back to legacy replay until then.

## Deployment note

User restarted and began a new conversation on 2026-09-14. Operation-aware
baselines are confirmed live: generation comparisons skip token-count requests.
Old-session read-only browsing is not implemented.

The default model is now `claude-haiku-4-5` in code (task 038); it takes effect
for new sessions after the server restarts. Existing sessions are unchanged.

Context reconnect/replay is built and served; refresh existing browsers once.
The complete-record capture reader fix takes effect on the next server restart.
The current Claude session has been preserved.

## Pending tasks

- None currently.

## Open bugs

- [Unrelated request block pairing](docs/bugs/open/unrelated-request-block-pairing.md) —
  chronological fallback can present unrelated same-position blocks as edits.

- [Overbroad workspace mount](docs/bugs/open/overbroad-workspace.md) — fixed in code,
  awaiting deployment.


- [Starlette TestClient hangs during startup](docs/bugs/open/starlette-testclient-startup-hang.md)
- [Browser requests a missing favicon](docs/bugs/open/missing-favicon.md)

## Decisions

- [ADR-0022 — Payload outline](docs/decisions/ADR-0022-payload-outline.md)

- [ADR-0021 — Operation-aware baselines](docs/decisions/ADR-0021-operation-aware-baselines.md)

- [ADR-0020 — Full payload diff](docs/decisions/ADR-0020-full-payload-diff.md)

- [ADR-0019 — Container system trust](docs/decisions/ADR-0019-container-system-trust.md)

- [ADR-0018 — In-app request evidence tabs](docs/decisions/ADR-0018-request-evidence-tabs.md)

- [ADR-0017 — Project-local Claude workspace](docs/decisions/ADR-0017-project-local-workspace.md)

- [ADR-0016 — Paged context summaries](docs/decisions/ADR-0016-paged-context-summaries.md)

- [ADR-0015 — Context stream recovery](docs/decisions/ADR-0015-context-stream-recovery.md)

- [ADR-0014 — Readable context presentation](docs/decisions/ADR-0014-readable-context-presentation.md)

- [ADR-0013 — Shared active session](docs/decisions/ADR-0013-shared-active-session.md)

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

- [Transcript correlation experiment](docs/notes/transcript-correlation-experiment.md) —
  exact joins demonstrated; token counting explains request 130's bad baseline.

- [Validated Podman + mitmproxy runtime recipe](docs/notes/validated-podman-mitm-runtime.md)
- [Live event protocol v1](docs/notes/live-event-protocol-v1.md)
- [Structural context diff model](docs/notes/context-diff-model.md)
- [Request-stream identity investigation](docs/notes/request-stream-identity-investigation.md)

## Completed setup

- [Synchronized change navigation](docs/tasks/done/050-sync-change-outline.md) —
  Previous/Next follows the outline, reveals nested entries and selects the correct side.

- [Readable payload root](docs/tasks/done/049-readable-payload-root.md) — plain-language
  root label with dynamic field count; build and browser checks pass.

- [Payload outline](docs/tasks/done/048-payload-outline.md) — expandable left-hand
  JSON navigation for either diff side; keyboard/mobile/large-array checks pass.

- [Default payload diff](docs/tasks/done/047-default-payload-diff.md) — request tabs
  open in full diff; block inspection is optional. Build and browser checks pass.

- [Visible comparison keys](docs/tasks/done/046-visible-comparison-keys.md) — exact
  comparison_lineage shown on live cards and collapsed groups; refresh to load.

- [Operation-aware baselines](docs/tasks/done/045-isolate-token-count-baselines.md) —
  verified in the user's new live session following restart.

- [Transcript correlation experiment](docs/tasks/done/044-transcript-correlation-experiment.md) —
  64 exact main-transcript joins; subagent correlation still needs a real sample.

- [Full request payload diff](docs/tasks/done/043-full-payload-diff.md) — optional
  complete unified JSON diff in request tabs; refresh to load the rebuilt frontend.

- [Metadata-only tool comparisons](docs/tasks/done/042-metadata-only-tool-changes.md) —
  unchanged tool calls/results shown once; cache metadata changes remain explicit.

- [Container system trust](docs/tasks/done/041-container-system-trust.md) — startup
  installs proxy CA inside agent/probe containers; current agent fixed in place,
  host trust unchanged.

- [Project ignore rules](docs/tasks/done/040-project-gitignore.md) — sensitive local
  state and generated output ignored; source, examples and lockfiles preserved.

- [Closable request evidence tabs](docs/tasks/done/039-request-evidence-tabs.md) —
  full-width browser-local views with pinned live session; refresh to load.

- [Default to Claude Haiku 4.5](docs/tasks/done/038-default-haiku-model.md)

- [Recover context streams](docs/tasks/done/035-recover-context-stream.md)

- [Explain metadata-only changes](docs/tasks/done/034-explain-metadata-only-changes.md)

- [Readable context inspector](docs/tasks/done/033-readable-context-inspector.md) —
  grouped repeats, readable changes/replies, expandable evidence and accounting,
  preserved reading position. Rebuilt frontend; refresh browser to load.

- [Share the active session](docs/tasks/done/032-share-active-session.md) —
  deployment confirmed by live server discovery and Playwright reconnection.

- [Enable remote server access](docs/tasks/done/031-enable-remote-server-access.md)
- [Declare Python project dependencies](docs/tasks/done/030-declare-python-project-dependencies.md)
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
- [Clarify container lifecycle diagram](docs/tasks/done/027-clarify-container-lifecycle-diagram.md)
- [Clarify terminal data path](docs/tasks/done/028-clarify-terminal-data-path.md)
- [Emphasize live block diffs](docs/tasks/done/029-emphasize-live-block-diffs.md)
