# ADR-0040: Codex catalog-derived context budgets

## Status

Accepted, 2026-09-23. Implemented by task 085.

## Decision

Derive effective context budgets from the inspector-owned native model cache:
context_window multiplied by effective_context_window_percent, rounded down.
Select by exact captured request model; never substitute catalog maximum or an
unrelated launch model. Explicit inspector window overrides retain precedence.
Missing/invalid metadata and unknown models remain unknown.

Freeze validated metadata to a private session file at first inspection so
reconnect/replay do not silently use newer cache values. Both HTTP and WebSocket
interpreters use the same resolver. Token usage remains wire-observed; limit
provenance explicitly says native catalog default, includes cache fetch time,
and notes runtime overrides may differ. This is not runtime telemetry correlation
and does not infer full server-held context or an auto-compaction threshold.

## Consequences

Current catalog defaults produce 258400 effective tokens. Cache absence at first
inspection preserves an unknown snapshot; a later session can use refreshed
metadata. Runtime configuration changes are not detected by this catalog fallback.
A future exact session telemetry integration can supersede the catalog default
without mislabeling this implementation as observed runtime evidence.
