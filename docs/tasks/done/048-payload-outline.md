# Task: Navigable payload outline

## Acceptance criteria

- [x] Diff view has a left-hand expandable JSON outline with jump links.
- [x] After and Before outlines target their own diff line numbers, including removals.
- [x] Nested messages/tools are identifiable without expanding the diff itself.
- [x] Outline remains usable with keyboard, narrow screens and large arrays.
- [x] Build and synthetic browser regressions pass; no live session changes.

## Findings

The worker already pretty-prints decoded JSON. Generate an outline from the same
objects in that worker; map each side's line numbers to rendered rows, rather
than guessing paths from unified diff text. Arrays are positional, not identities.

## Verification

- Frontend build passes.
- Worker fixture: 156 cases preserve complete before/after reconstruction and
  validate every outline path/start line, including escaped keys and empty nodes.
- Fast-replay fixture: keyboard expansion/jumps, After additions and Before
  removals, accessible selected entry, mobile width and existing tab regressions.
- Dedicated outline fixture: 205 messages, lazy children, 100-entry paging,
  visible target after jump, tool labels, literal HTML-like keys, absent Before
  disabled, left-hand desktop and stacked mobile layout without overflow.
- Readability fixture passes; Playwright closed. No live input or restart.
- README, ADR-0022 and PLAN updated; diff whitespace check passes.
