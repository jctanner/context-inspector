# Bug: Live Events Expand the Page and Scroll the Header Away

## Observed

Once a Claude session produces enough live flow cards, the document becomes
taller than the viewport and the application header scrolls off screen.

## Cause

The fixed-height workspace is a grid, but its grid items retained the default
`min-height: auto`. Their intrinsic content height could therefore enlarge the
grid track instead of constraining overflow to `.flow-events`. The workspace
also lacked an explicit overflow boundary.

## Expected

At desktop widths, the document and header remain viewport-bound while the
terminal and flow list manage their own scrolling.

## Resolution

Fixed on 2026-08-19. The body is now a viewport-height two-row grid, and the
workspace and pane grid/flex children explicitly use `min-height: 0` and
`overflow: hidden`. `.flow-events` remains the scroll owner. The narrow stacked
layout uses a sticky header. `src/tests/test_web_layout.py` guards the complete
height/overflow chain.
