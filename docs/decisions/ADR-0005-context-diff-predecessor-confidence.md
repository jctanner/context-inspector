# ADR-0005: Label Context-Diff Predecessors by Evidence Confidence

## Status

Accepted — 2026-08-19

## Context

A structural diff needs a predecessor, but the captured HTTP API does not yet
provide a proven primary-agent/subagent stream identifier. Blindly comparing
each model request with the globally preceding request could present a
subagent-to-primary transition as a context mutation.

Retries also duplicate a request without creating a new logical context state,
and a smaller message array is suggestive of compaction but is not proof of the
harness mechanism that caused it.

## Decision

Until stream attribution is established:

- compare model requests by observed session chronology;
- label that basis `session_chronology_unclassified` with `low` confidence;
- label byte-identical normalized payloads `retry_or_duplicate` and do not
  advance the comparison baseline;
- label a decrease in message count `compaction_candidate`, never confirmed
  compaction;
- retain exact flow IDs and captured request fields so users can audit every
  derived comparison.

Task 006 may replace this policy with stable per-stream predecessors if the
wire/runtime evidence supports them.

## Consequences

The UI is useful for ordinary sequential sessions without overstating agent
identity. Cross-agent comparisons may still occur, but they are visibly
low-confidence rather than silently presented as fact.
