# ADR-0044: Codex MLflow tracing through native notify

## Status
Accepted, 2026-09-24.

## Context
User authorized integrating @mlflow/codex using the existing stack MLflow option,
while preserving native shared OAuth credentials and mitmproxy inspection.
The upstream 0.4.0 package selects the latest transcript turn, reports last-call
usage at the root, and resolves transcripts through HOME rather than CODEX_HOME.
Codex spawns notify without waiting. Direct use could misattribute delayed turns
or lose delivery during container exit.

## Decision
Install locked @mlflow/codex/core dependencies beside the existing Claude tracing
package and mount inspector-owned assets read-only. A non-root supervisor injects
notify per launch; no setup command or host configuration writes. The native
callback publishes a private queue record keyed by captured thread/turn IDs. The
supervisor selects that exact completed turn and supplies a private HOME and
CODEX_HOME snapshot to the unmodified exporter. Missing/incomplete transcripts
produce explicitly labeled notify-only traces, never a guessed latest turn.

Derive turn usage from monotonic cumulative counter differences with an observed
baseline (or verified zero-start); omit unavailable/reset counters. Trace metadata
records native IDs, inspector session ID, evidence source and usage source.
Native auxiliary callbacks (including title generation) keep their own IDs; captured
session-source metadata is retained without inferring parent/primary attribution.
Independent wire evidence is unchanged; no span/request join is claimed.

Use synchronous child exports (20-second deadline), serialize workers, and drain
for up to 35 seconds on CLI exit. Preserve CLI exit status on export failure and
retain private diagnostics. Inspector Stop permits 40 seconds for traced Codex.
Existing user-layer notify argv is chained; reject competing CLI/project notify
config rather than silently changing its behavior. Native override must be on the
innermost exec/resume command for the installed CLI.

## Consequences
No gateway or provider routing change, extra login, or custom Codex plugin is
required. Interrupted turns without completion callbacks, forced teardown and
export failure may leave gaps. No replay/retry guarantees. Upstream tool/span
reconstruction is limited by the installed package; timing is not exact wire
latency. Claude OAuth tracing remains outside this change. Native fixture tests
exercise published packages and installed CLI rather than assuming checkout parity.
