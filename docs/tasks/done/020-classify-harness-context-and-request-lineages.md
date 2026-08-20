# Task: Classify Harness Context and Request Lineages

## Goal

Prevent recognized internal probes from being diffed against session requests
and identify harness-injected context blocks explicitly.

## Acceptance criteria

- [x] `max_tokens: 1` / `count` probes receive a conservative internal purpose.
- [x] Supported title-generation requests receive a purpose before response.
- [x] Recognized internal purposes use separate comparison lineages.
- [x] `<system-reminder>` and local-command wrappers expose harness origin.
- [x] Path reuse across internal/session requests cannot create transformations.
- [x] Purpose/origin labels expose confidence and evidence.
- [x] Captured regression and frontend tests pass.

## Status

Complete

## Findings

- The observed `count` request was an auxiliary request with `max_tokens: 1`,
  not a prior state of the main conversation.
- Missing agent headers remain insufficient to identify a primary agent, but a
  recognized internal purpose is sufficient to prevent cross-purpose diffs.
- `<system-reminder>` and local-command wrappers are visible on the request
  wire. Their harness origin is an interpretation based on wrapper syntax, so
  the UI labels it medium-confidence rather than exact provenance.

## Validation

- The production TypeScript/Vite build passes.
- All 54 Python tests pass, including the real loopback server test.
- Replaying the active 114-request capture identified ten count probes and zero
  `count` to `<system-reminder>` transformations.
