# ADR-0011: Separate Recognized Internal Request Purposes into Comparison Lineages

## Status

Accepted — 2026-08-19

## Decision

Keep wire-observed agent-header identity as the primary stream identifier. For
the small set of conservatively recognized internal request purposes, append
the purpose to that stream identifier when selecting a diff predecessor.

Recognize the exact `max_tokens: 1` single-user-message `count` shape as likely
internal token counting. Recognize supported title-generation instructions at
request time. All other requests continue to use their existing stream lineage.

Classify `<system-reminder>` and local-command wrapper blocks as likely
harness-injected, with medium confidence and explicit lexical evidence. Preserve
the exact captured block separately.

## Rationale

An internal count probe and the next full conversation request can both lack an
agent header. Comparing them by global unclassified chronology turns reuse of
`messages/0/0` into a fictitious transformation. Purpose-specific lineages fix
that comparison error without claiming the unclassified request is primary or
inventing an agent identity.

## Consequences

- Internal probes compare only with earlier requests of the same recognized
  purpose and stream identity.
- Session requests no longer inherit an internal probe as their predecessor.
- Purpose and origin are interpreted metadata with confidence and evidence,
  while exact request fields remain available as wire evidence.
- Unknown auxiliary requests remain unclassified rather than guessed.
