# ADR-0022: Side-specific payload outline

## Status

Accepted

## Decision

Generate hierarchical JSON Pointer paths and pretty-printed start-line numbers
alongside the diff in its worker. A left-hand outline defaults to After; Before
is separately selectable so removed fields remain navigable without claiming
that same-index array entries represent the same message across requests.
Navigation targets actual rendered diff rows on the selected side.

Task 050: change-navigation buttons use the same outline selection controller.
Index each node's full line range, including closing delimiters; reveal its
ancestors/pages and scroll only the sidebar's own viewport. Removed hunk starts
select Before, added starts select After. Preserve navigation-button focus.

Use native disclosures and buttons, lazily constructing child lists in pages
of 100. Keep the outline sticky and independently scrollable on wide screens;
stack it above the diff on narrow screens. No payload previews or HTML injection.

## Consequences

No backend changes or extra requests. Outline metadata adds memory proportional
to JSON nodes but does not duplicate scalar payload contents. This indexes
decoded, pretty-printed JSON, not byte offsets in original wire evidence.
