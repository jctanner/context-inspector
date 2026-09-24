# Codex context limits observed on this installation

Investigated 2026-09-23 (America/New_York); cache fetch timestamps are September
24 in UTC. Native CLI and both caches report client version 0.156.0.

## Findings

Read only selected model metadata, context configuration keys and numeric native
session fields. No credentials, prompt text or response text were printed.

| Models visible in native catalog | Default window | Effective percent | Derived default effective window | Catalog maximum |
| --- | ---: | ---: | ---: | ---: |
| gpt-6-astra, gpt-6-sol, gpt-6-luna | 272,000 | 95% | 258,400 | 872,000 |
| gpt-5.6-sol, gpt-5.6-terra, gpt-5.6-luna | 272,000 | 95% | 258,400 | 872,000 |
| gpt-5.5 | 272,000 | 95% | 258,400 | 272,000 |

Sources: host native models_cache.json and inspector-owned
container/home/evaluator/.codex/models_cache.json agree on these fields. Metadata
is a dated local observation, not a universal API limit or entitlement guarantee.
Field names: context_window, effective_context_window_percent, max_context_window.
The derived column is 272000 * 95 / 100, not a separate catalog field.

Both available inspector session logs identify gpt-6-luna in turn_context and
report info.model_context_window = 258400 in native token_count events. Thus the
effective figure is directly corroborated for that model in this installation.
Other rows have catalog-derived defaults, not observed session measurements.
Native telemetry is separate evidence from the intercepted model request/response.

The inspector-owned config.toml has no top-level model_context_window,
model_auto_compact_token_limit, model_catalog_json or profile override. This check
does not establish the absence of every possible configuration layer or future
in-session change. The observed runtime field is the stronger evidence here.

## Meaning for the inspector

The active session's effective budget is 258,400, not the catalog maximum of
872,000. The larger maximum alone does not mean that long context is enabled.
Do not subtract max output tokens speculatively or label the effective window as
an auto-compaction threshold. The threshold was not established by this probe.

Official configuration documentation defines model_context_window separately
from model_auto_compact_token_limit, which controls automatic compaction and uses
model defaults when unset:
https://learn.chatgpt.com/docs/config-file/config-reference

Current Responses usage interpretation deliberately leaves the window unknown
unless explicitly overridden. Model traffic alone has not supplied this limit.
A future meter integration should prefer session-matched native runtime window
metadata, preserve its provenance and timestamp, and use a catalog-derived
fallback only with an explicit label. Keep catalog default, effective budget,
maximum and compaction threshold separate. Never join a transcript to a wire
request solely because their model names or timestamps match. Snapshot metadata
for replay so later cache updates cannot silently change historical percentages.

No runtime setting, active session, model request or meter behavior was changed
by this investigation. The result establishes the current limit and the evidence
needed for a subsequent implementation.
