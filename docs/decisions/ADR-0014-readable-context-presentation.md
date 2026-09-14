# ADR-0014: Content-First Context Presentation

## Status

Accepted

## Decision

Render normalized request blocks as readable content with labeled Before/After
sections, and reconstructed response text before other response block types.
Use textContent throughout; never interpret captured strings as executable HTML.
Large blocks have short previews and full-content disclosures. Raw evidence,
fingerprints, provenance and attribution remain inspectable separately.

For transformed blocks, compare text separately from other value fields. Show
added/removed/modified fields with their before/after values, distinguish absent
fields from null values, and disclose identical text once. This prevents a
metadata-only change from appearing to be a text edit. Raw evidence remains intact.

Group adjacent requests only when decoded bodies and comparison lineage/stream
match and the later comparison reports a repeat without additions, removals or
transformations. Preserve every numbered request inside the group and show reply
previews outside it. Grouping is a presentation decision, not proof of retry intent.

Request numbers enumerate the displayed requests; original wire event sequences
remain in evidence. Missing reconstructed responses are labeled unavailable,
because lack of a response does not establish an in-flight lifecycle.

The context meter retains reported usage and accounting provenance with shorter
visible labels. New traffic follows the bottom only when the reader is there;
otherwise it preserves scroll position and offers a jump-to-latest button.

## Consequences

The evidence/classification pipeline is unchanged. Readable views are explicitly
interpreted and full captures remain available. Disclosure and scroll states are
local to each browser. UI updates require a browser refresh, not a server restart.
