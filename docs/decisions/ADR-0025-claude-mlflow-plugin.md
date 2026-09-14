# ADR-0025: Pinned Claude tracing plugin, separate from wire evidence

## Status

Accepted

## Decision

Pin @mlflow/claude-code 0.4.0 (the plugin shipped with MLflow 3.16.0) in a
runtime-only npm project with a lockfile. Load its self-contained Node bundle
read-only through a minimal hook-only --plugin-dir adapter. The adapter invokes
the upstream Stop bundle with a 30s timeout and 5s kill grace; errors do not block
Claude. Do not install a marketplace, modify existing settings, or add a host
Python SDK. Add Node 24.21.0 to a derived agent image, preserving the base image
and its user; cache by base image ID and Containerfile hash.

Put MLflow on the existing private Podman network. Allow only its own unique
container hostname in addition to configured browser hosts. Resolve/create the
experiment each stack startup and pass container address and current experiment
ID via launch-scoped environment. Explicitly bypass the MITM proxy for tracking.
No database/artifact mounts; shutdown still discards tracking data.

## Evidence and limits

The pinned package's Stop hook exports the latest user turn from the transcript,
with Claude's session ID and available tool/subagent structure. Some timings and
costs are reconstructed/estimated, and this is not a complete copy of each model
request. Keep proxy captures authoritative for payload diffs. No automatic join
between MLflow spans and inspector request numbers is added in this task.

The top-level guide describes session-end export, but the pinned source uses Stop
(Claude finishes responding). Hard interruption, hook disablement, export errors
or stack teardown can lose a turn's trace. Existing sessions need recreation to
load the plugin. MLflow needs to stay running to view exported traces.

References: [MLflow guide](https://mlflow.org/docs/latest/genai/tracing/integrations/listing/claude_code/),
[pinned hook](https://github.com/mlflow/mlflow/blob/v3.16.0/libs/typescript/integrations/claude-code/hooks/hooks.json),
[Claude plugin loading](https://code.claude.com/docs/en/plugins).
