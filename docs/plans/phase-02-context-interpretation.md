# Phase 2: Context Interpretation

## Goal

Turn exact captured payloads into a readable, testable representation of how
context changes between model calls.

## Scope

- canonical request model;
- system, tool, message, tool-result, and response block views;
- raw request and response views;
- structural diffs against the previous request in a stream;
- byte, token, tool, and message counts;
- compaction, retry, and context-window-error annotations;
- sanitized fixtures and deterministic parser/diff tests.

## Exit criteria

The UI can explain both what changed and which exact captured fields support
that explanation.
