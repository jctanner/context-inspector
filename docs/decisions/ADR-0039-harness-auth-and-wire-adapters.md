# ADR-0039: Separate harness, authentication and wire interpretation

## Status

Accepted and implemented (2026-09-23), tasks 081 and 082.

## Context and decision

Retain native CLIs over PTYs and independent mitmproxy observation. Expose
validated harness/auth/model profiles, preserve explicit launch metadata across
reconnect, and use provider-specific interpreters over preserved wire evidence.
Vertex remains supported. OAuth profiles launch only after native credential and
binary preflight; no inferred authentication or silent provider fallback.

The user selected normal host CLI workflows and native shared-file handling.
Run Claude 2.1.280 or Codex 0.156.0 inside the proxy-configured container. Do not
require an app-server broker or separate login. Broker diagnostics are historical
feasibility experiments, not production architecture. Synthetic Codex tests show
completed-refresh reload but overlapping refresh can submit the same old token;
sharing does not add serialization or establish the provider's rotation policy.

Mount only Codex auth.json; keep other Codex state inspector-owned. Stop on inode
replacement to avoid stale file mounts. Claude requires a shared directory for
native locks and atomic credential replacement. The user explicitly approved
mounting the existing host directory at /host-claude-auth and its resulting
container access. Set CLAUDE_SECURESTORAGE_CONFIG_DIR there, but use owned
CLAUDE_CONFIG_DIR for settings/history. Never browse or clean the host mount.
Exclude OAuth exchanges before recording, redact credential headers, and disable
OAuth syscall tracing and Claude MLflow export. Hide unsupported experiment UI.

## Wire evidence

Protocol 1.1 preserves assembled logical WebSocket messages, their exact bytes,
order, direction and connection identity. It does not claim raw network frames.
Responses pairing uses lane order followed by observed response IDs, with medium
confidence. HTTP/SSE fallback has exact flow correlation. Only an observed
previous_response_id links Codex comparisons. Server-held context is not
reconstructed; unknown agent identities/windows remain unknown. Cached/reasoning
usage stays a subset. Raw evidence remains distinct from reconstructed output.

Live Claude HTTP and Codex WebSocket tool round trips pass through mitmproxy;
HTTP fallback, gaps, output reconstruction and replay have synthetic coverage.
See [task 082](../tasks/done/082-oauth-codex-harnesses.md) for precise validation
and remaining limits, and [Phase 04](../plans/phase-04-oauth-and-codex.md) for the
original planning baseline. The main stack remains user-managed.
