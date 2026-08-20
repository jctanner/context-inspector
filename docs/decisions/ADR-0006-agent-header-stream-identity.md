# ADR-0006: Use Only the Agent-ID Header for Automatic Stream Identity

## Status

Accepted — 2026-08-19

## Decision

Automatically assign a captured model request to a distinct logical stream
only when it carries a non-empty `x-claude-code-agent-id` header. Group exact
matching values and label the classification high-confidence identified-agent.

Requests without that header remain `unclassified`; they are not presumed to
be primary. System prompts, tool sets, ancestry, and timing may support visible
heuristic suggestions later but cannot silently assign a stream.

Manual reassignment will be a provenance-bearing local overlay and will not
mutate wire events or archives.

## Rationale

Phase 1–4 captures show that the header is stable for named agents,
full-context agents, and long-running compacted workers. Forked skills omit it,
which makes absence ambiguous. Session/user identifiers are shared, while
prompt and tool signatures change or overlap.

## Consequences

- Identified agent streams receive independent context-diff predecessors.
- Primary and forked-skill traffic may remain mixed in Unclassified until
  stronger evidence or manual reassignment exists.
- The UI must not infer a mechanism name merely from an agent-ID value format.
