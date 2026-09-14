# Task: Claude Code MLflow tracing integration

## Scope

Load the official pinned Claude Code tracing plugin in new agent sessions and
send traces directly to the stack's ephemeral MLflow server. Preserve existing
Claude settings and wire-capture behavior; do not change comparison lineages.

## Acceptance criteria

- [x] Reproducible plugin dependency, no global host/Claude installation.
- [x] Container-to-container tracking connectivity, proxy bypass and Host allowlist.
- [x] Fresh experiment resolution per stack launch; no persisted stale ID.
- [x] Automatic plugin/config injection for new Claude sessions, with disablement.
- [x] Unit/runtime regression tests and isolated actual-plugin export smoke test.
- [x] Document export timing, provenance, limitations and restart requirements.

## Discoveries

MLflow 3.16's Python setup installs the same marketplace plugin; Python hooks
are legacy. Official @mlflow/claude-code 0.4.0 ships self-contained Node bundles
and a Stop hook. Prefer loading that pinned package through --plugin-dir over
editing the user's persisted settings or installing a floating marketplace.

Agent base image has native Claude but no Node; add a derived image with only
Node 24.21.0, cached by base image ID and Containerfile hash. The breadboard
reference uses a legacy Python hook, but its bounded-timeout pattern remains
applicable: a minimal local hook-only plugin invokes the unmodified official
Node bundle with a 30s deadline and 5s kill grace. No setup/status skills needed.

## Verification

103 Python tests pass with CONTEXT_INSPECTOR_TEST_MLFLOW=1, including the
standalone DB/artifact reset test and a real Claude CLI against a local fake
Anthropic endpoint. Claude reads a fixture file, finishes the response, and its
automatically loaded Stop hook exports one trace with the exact Claude session
ID, LLM span, Read tool ID and tool result. A separate synthetic transcript
verifies Task → subagent → nested LLM parentage; this is not claimed as an actual
subagent model execution. No real credentials, user state, or paid model calls.

Derived image build confirms Node v24.21.0 and timeout are available under the
original image user. Tests cover runtime env restoration/disablement, image cache
identity, private network/Host allowlist, runner argv/mount/proxy injection,
bounded-hook failure behavior, and prior lifecycle/capture regressions. Bash
syntax and git diff whitespace checks pass. No frontend changes needed.

Two initial verification failures came from the test SDK's artifact downloader
using its global SQLite URI despite an HTTP client URI; setting the global HTTP
tracking URI fixes the query. Export itself succeeded. No new production defect.

## Handoff

User will launch/restart the stack themselves. Do not start it. No active-stack
stop/restart or persistent Claude/workspace modification was performed. The next
normal launch provisions the derived image/plugin, starts a fresh MLflow server
and experiment, and supplies new Claude containers with tracing mounts/config.
Open MLflow → Claude Code → Traces after a completed turn, keeping the stack up
while inspecting traces. This task does not add request/span correlation in the UI.
