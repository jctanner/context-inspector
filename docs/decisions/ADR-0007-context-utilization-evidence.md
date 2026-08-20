# ADR-0007: Base Context Utilization on Response Usage

## Status

Accepted — 2026-08-19

## Decision

The context utilization meter uses input-token accounting observed in the
model's SSE response for the exact request flow. It sums:

- `input_tokens`;
- `cache_creation_input_tokens`;
- `cache_read_input_tokens`.

It does not convert request bytes or characters into a token count. Before
response accounting arrives, the meter remains indeterminate and shows the
exact request byte count separately.

The denominator is configuration, not wire evidence. It defaults to 200,000
tokens based on the experiment baseline and can be overridden with
`CONTEXT_INSPECTOR_CONTEXT_WINDOW_TOKENS`. The UI displays whether the limit is
the configured default or an environment override.

The headline meter selects the newest completed measurement whose response has
not been classified as a known internal purpose. Measurements remain keyed by
exact `flow_id`. A classified internal title-generation call is excluded; an
unclassified call remains eligible and is not relabeled primary.

## Consequences

- Utilization appears after response usage, not immediately at request start.
- Failed responses without usage retain an explicit awaiting/unavailable state.
- Optional larger context windows must be configured rather than silently
  inferred from a model name.
- Usage is correlated by exact `flow_id` and retains stream identity.
