# Task: Investigate Agent-Stream Identity

## Goal

Determine which captured evidence can distinguish primary, named-subagent,
forked-skill, and full-context model-call streams.

## Context

The proxy observes HTTP flows, not the local process or logical agent that
caused each call. Tabs must not present heuristic grouping as certainty.

## Acceptance criteria

- [x] Existing Phase 1–4 captures are checked for stable identifiers.
- [x] Message ancestry, system prompts, tool sets, delegation IDs, and timing
  are evaluated as fallback signals.
- [x] Counterexamples and ambiguous cases are recorded.
- [x] A classification confidence model is proposed.
- [x] The design includes an unclassified stream and manual reassignment.
- [x] Findings are captured in an ADR or investigation note.

## Files likely involved

- `src/server/`
- `src/tests/`
- `docs/decisions/`
- `docs/notes/`

## Findings and validation

- The Phase 1–4 evidence matrix and counterexamples are recorded in
  `docs/notes/request-stream-identity-investigation.md`.
- ADR-0006 limits automatic identity to the exact agent-ID header and requires
  an unclassified fallback.
- `src/server/identity.py` implements the high-confidence rule. Context
  predecessor baselines are now independent per identified agent stream.
- Missing agent IDs remain unclassified, specifically covering the observed
  forked-skill ambiguity.
- Deterministic identity and interleaved-stream lineage tests pass; the web
  production build displays stream identity and confidence.

## Status

Done
