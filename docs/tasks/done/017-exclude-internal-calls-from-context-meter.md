# Task: Exclude Classified Internal Calls from the Context Meter

## Goal

Make the headline context meter reflect the latest measured non-internal model
request rather than a small auxiliary call such as title generation.

## Acceptance criteria

- [x] Usage is retained by exact request `flow_id`.
- [x] A classified internal response cannot remain the headline measurement.
- [x] The latest measured non-internal request is restored automatically.
- [x] Unclassified requests remain eligible without being called primary.
- [x] The meter states its selection policy and exact measured flow.
- [x] Frontend regression tests and production build pass.

## Status

Done

## Evidence

- The auxiliary title request used 385 input tokens and was request sequence
  297.
- The adjacent user-facing story request accounted for approximately 34.8K
  input/cache tokens, consistent with Claude `/context` reporting 34.9K.
- The discrepancy was selection, not token arithmetic.

## Validation

- TypeScript checks and the Vite production build passed.
- All eight frontend regression tests passed, including internal-call
  exclusion and completion-order handling.
