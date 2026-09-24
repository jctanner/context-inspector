# ADR-0041: Complete latest harness installations in the agent image

## Status

Accepted and implemented, 2026-09-23. Supersedes the executable-mount and fixed
CLI-version portions of ADR-0039 and tasks 082/086. Credential decisions stand.

## Decision

Install @anthropic-ai/claude-code@latest and @openai/codex@latest with their native
package dependencies in a derived agent image; copy the full installation and
Node runtime into the existing AGENT_IMAGE. All three profiles use these image
executables. Preserve the base image, UID/GID 1000, workspace, auth mounts,
proxy/trust setup and capability-specific integrations. No host CLI executable
is mounted or inspected during credential preflight.

Cache the image by base image ID and build recipe. Latest means latest resolved
during installation, not auto-update during a session. Explicit --refresh supplies
a new install-layer build argument and resolves latest packages again. Existing
containers stay on their image. Resolve commands with explicit /usr/local/bin
paths so older base-image installations cannot shadow them. Disable Claude's
runtime auto-updater; image refresh owns CLI updates.

Record actual installed versions in /opt/context-inspector-harnesses/versions.json
and print the selected version during session startup. Startup checks executable
help/version, Codex helper startup and native OAuth login selection; strict
version equality checks are removed. New incompatible releases can fail these
checks or need capture/parser updates; no promise of compatibility with unseen
versions. Host credential concurrency semantics remain native.

## Validation

Image built with Claude 2.1.281 and Codex 0.156.1. Real isolated OAuth tool turns
pass through proxy for both, with interpreted context/responses/usage. No host
executable mounts. Vertex retains tracing/MCP/ADC handling and uses the same
image-installed Claude; covered by regression suite, not a new live Vertex call.
See task 087 for evidence and user-managed activation.
