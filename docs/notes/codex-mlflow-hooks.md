# Native Codex hooks and the existing MLflow integration

2026-09-23; Codex checkout 7dae8c53d9; MLflow checkout 25b1af314.
Original source/docs investigation; see task 092 for the implemented integration
and native container validation completed on 2026-09-24.

## Main finding

MLflow already supplies @mlflow/codex, version 0.4.0 in this checkout:
checkouts/mlflow/libs/typescript/integrations/codex/package.json.
It uses native notify callbacks and rollout transcripts, not the AI Gateway.
Official guide: https://mlflow.org/docs/latest/genai/tracing/integrations/listing/codex
This corrects the earlier implication that a request-only custom exporter was
necessary: task 090 accurately described the gateway path but missed the separate
existing turn-level integration.

## Native hook support

codex-rs/hooks/src/legacy_notify.rs:18 serializes agent-turn-complete with thread-id,
turn-id, cwd, optional client, input-messages and last-assistant-message. notify
configuration supplies an argv vector; the JSON is appended as its final argument.
The callback is spawned without waiting; stdout/stderr are discarded. This means
exporter logs and shutdown handling need explicit runtime treatment.

Codex also has modern Claude-style hooks:
- config/src/hook_config.rs: Pre/PostToolUse, UserPromptSubmit, Stop, Interrupt,
  SessionStart/End, SubagentStart/Stop and compaction events.
- hooks/src/schema.rs:588 Stop input includes session_id, turn_id, transcript_path,
  model, stop_hook_active and last_assistant_message. Tool inputs include
  tool_use_id; subagent payloads include agent_id and transcript paths.
- hooks/src/registry.rs loads plugin hook sources; hooks feature defaults on in
  the reviewed source. PluginHooks is a removed compatibility flag.
- core/src/hook_runtime.rs dispatches native Stop requests using session/turn IDs.

Official plugin docs describe hooks/hooks.json discovery and inline/path hooks
in the plugin manifest, PLUGIN_ROOT/PLUGIN_DATA and Claude-compatible aliases.
Non-managed plugin hooks require trust review; enabling a plugin alone does not
trust its hooks. These modern hooks are distinct from legacy notify.
https://developers.openai.com/plugins/build/plugins
https://learn.chatgpt.com/docs/hooks

Installed container Codex 0.156.1 successfully ran features list in a network-free
container with a temporary CODEX_HOME and no credentials. No hook was installed or
fired. The checkout is a moving source revision; actual hook payload compatibility
still needs an isolated native completion test.

## What @mlflow/codex implements

src/hooks/stop.ts consumes the notify JSON argument and calls processNotify.
src/tracing.ts:55 creates one AGENT root per callback, adds LLM/TOOL child spans
when a transcript is found, attaches mlflow.trace.session from thread-id and
flushes traces. Without transcript data it falls back to a simple AGENT/LLM trace.

src/transcript.ts:206 locates rollout files under CODEX_HOME/sessions (or the
normal home fallback), which fits our isolated container Codex storage. It selects
the latest task_started/task_complete slice, rather than selecting by the callback's
turn-id. This deserves tests for delayed callbacks/rapid consecutive turns.
Root usage reads transcript counters; verify cumulative-vs-per-turn accounting
before presenting it as exact per-turn usage. Child span times are reconstructed
from rollout boundaries, not inherently exact wire timings.

## Concrete integration direction

Use the existing @mlflow/codex package before inventing an exporter. Install it
in inspector-owned runtime assets or the image, inject an argv notify override
for inspector-launched Codex, and supply MLFLOW_TRACKING_URI/EXPERIMENT_ID through
the container environment and private MLflow network. Do not run global setup
against the user's host config. Our image Node 24 satisfies the checkout package's
Node >=22 requirement (the public page currently says 18+).

A bounded wrapper should preserve exit behavior, record failures privately and
handle exporter completion before container teardown. Preserve/chains existing
notify configuration deliberately rather than silently overwriting it. Retain
our mitmproxy capture as independent exact evidence. Native transcript-based
turn grouping can coexist with wire-level inspection; exact linking of each wire
call to a transcript span remains a separate validation requirement.

No OAuth routing change is implied: this hook exports telemetry locally after
turns and does not replace the provider URL. Native hook completion, transcript
format, export delivery, repeated turns, interruption, helper tools, replay and
shutdown still need container tests. No implementation or activation in this task.

## Implementation follow-up (task 092)

The published npm 0.4.0 package differs from checkout HEAD: transcript lookup ignores
CODEX_HOME. The adapter sets both HOME and CODEX_HOME to a private turn snapshot.
Native testing verified that exec/resume overrides must be placed on the innermost
subcommand. The normal interactive --no-daemon launch is also verified. Native
interactive title generation emits an additional completion callback; preserve
its IDs rather than attributing it to the user turn. The exporter now records
searchable thread/turn/inspector IDs and captured source metadata when available.
Turn usage is normalized from monotonic cumulative counters; unverified usage is
omitted. The package remains unmodified. See ADR-0044 and README for limits.
