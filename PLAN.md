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

Task 064 is ready for user-managed restart: Claude will launch the stdio MCP
dump script with the workspace config at `.context/mcp-dump/config.json`.
One tool initially; later count/schema edits emit live notifications without
restart. Protocol verified in the agent image; live Claude UI/loading verification
awaits restart. Full suite: 126 passed, three unrelated opt-in tests skipped.

Task 060 is ready for user-managed restart. Normal startup now permanently clears
the agreed Claude history, memories and generated-state allowlist, with no backups.
Settings, credentials, plugins, instructions and workspace remain. Active/paused
container use and concurrent stack ownership block cleanup. 115 tests pass;
the agent did not clean the real home or restart the active stack.

Task 059 fixes remote MLflow chart POSTs by configuring browser origins separately
from allowed hosts. Approved-origin POSTs and rejection cases pass in a real
MLflow container. Local .env is updated; user restart is required. No active-stack
restart or data changes were performed.

Task 058 configures this installation's ignored .env for remote MLflow access
on 0.0.0.0:5000 with explicit host/IP allowances. Configuration and focused tests
pass; user restart is required. The agent has not restarted the stack or changed
firewall rules. Code defaults remain loopback; remote access is unauthenticated.

Task 057 is ready for user-managed launch/restart. User confirmed task 056's
MLflow server is running; the agent did not restart it. The next normal launch
adds pinned Claude tracing, a cached Node-enabled derived agent image and a fresh
Claude Code experiment. New Claude sessions export completed turns to MLflow;
the database/artifacts still reset per stack launch. 103 tests pass, including
real-CLI export against a fake model and synthetic nested-subagent reconstruction.
User explicitly requested that the agent NOT start the stack. Persistent home
and workspace remain unchanged. Span-to-request UI correlation is not implemented.

Current handoff: user stopped the stack. Tasks 053/054 are built and tested;
the next normal launch uses container/workspace and container/home/evaluator
mounts and exposes read-only Memory navigation. The workspace was moved intact;
old .state/claude remains as a backup. No test servers are left running. Older
deployment notes below describe previous runs, not the current mount defaults.

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

- [ADR-0028 — Dynamic stdio MCP](docs/decisions/ADR-0028-dynamic-stdio-mcp.md)

- [ADR-0027 — Random skill generator](docs/decisions/ADR-0027-random-skill-generator.md)

- [ADR-0026 — Clean Claude startup](docs/decisions/ADR-0026-clean-claude-startup.md)

- [ADR-0025 — Claude MLflow plugin](docs/decisions/ADR-0025-claude-mlflow-plugin.md)

- [ADR-0024 — Ephemeral MLflow](docs/decisions/ADR-0024-ephemeral-mlflow.md)

- [ADR-0023 — Read-only mirrored memory](docs/decisions/ADR-0023-read-only-memory.md)

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

- [Dynamic stdio MCP](docs/tasks/done/064-dynamic-stdio-mcp.md) — Python script,
  live config-driven tools, isolated-container validation; ready for restart.

- [Variable skill lengths](docs/tasks/done/063-variable-skill-lengths.md) —
  random 500–5,000 total lines per generated skill; eight tests pass.

- [Rename scripts directory](docs/tasks/done/062-rename-scripts.md) — generator
  now lives at `scripts/skill-maker.py`; five tests pass.

- [Random skill generator](docs/tasks/done/061-random-skill-generator.md) —
  standalone 1,000-skill experiment utility; five tests pass; live workspace untouched.

- [Clean Claude startup](docs/tasks/done/060-clean-claude-startup.md) — allowlisted
  permanent history/memory reset, safety guards, no backups; 115 tests pass.

- [MLflow browser origins](docs/tasks/done/059-mlflow-browser-origins.md) — fixes
  chart POST 403s, with real-container origin/host regression tests; restart needed.

- [Remote MLflow access](docs/tasks/done/058-mlflow-remote-access.md) — local
  bind and host allowlist ready for user-managed restart.

- [Claude MLflow integration](docs/tasks/done/057-claude-mlflow-integration.md) —
  bounded official 3.16-compatible Stop hook, private networking, per-launch
  experiment and read-only mounts; ready for user-managed restart.

- [Ephemeral MLflow](docs/tasks/done/056-ephemeral-mlflow.md) — stack-owned
  disposable tracking server; 96 tests pass including real DB/artifact reset.

- [Response evidence tabs](docs/tasks/done/055-response-tabs.md) — independent
  closable Response #N views, lazy full replies/tool calls/exact evidence; refresh to load.

- [Container filesystem mirror](docs/tasks/done/054-container-mirror.md) — migrated
  workspace, corrected home mounts, direct local memory reads; ready for startup.
- [Read-only memory browser](docs/tasks/done/053-read-only-memory.md) — Session /
  Memory navigation, safe source viewer, refresh; 86 Python tests and five browser fixtures pass.

- [Split header layout](docs/tasks/done/052-split-header-layout.md) — grouped
  headings and compact gutters; no text overlap at tested desktop/mobile widths.

- [Side-by-side payload diff](docs/tasks/done/051-split-payload-diff.md) — toggle
  between Inline and Before/After columns; outline/navigation work in both.

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
