# Structural Context Diff Model

Context Inspector derives one context snapshot from each captured JSON model
request containing at least one of `system`, `tools`, or `messages`. OAuth and
other non-model JSON requests are ignored.

The normalizer creates deterministic blocks for each system content block,
complete tool definition, and message content block. It retains category, path,
role, type, canonical byte count, exact value, and SHA-256 fingerprint.

Comparison first matches identical fingerprints at the same path, then
identical moved blocks, then changed values at the same path. Remaining blocks
are additions or removals. This ordering prevents a shifted message from being
misreported as a chain of transformations.

Request-body byte counts come from the exact capture-boundary representation.
A token count is displayed only when an explicit supported field exists in the
request; otherwise the UI says it is unavailable. It does not estimate tokens
and present that estimate as wire evidence.

Predecessor semantics and their current limitations are recorded in ADR-0005.
Exact request fields are lazily materialized in the browser so large prompts do
not inflate the DOM until the user explicitly expands them.
