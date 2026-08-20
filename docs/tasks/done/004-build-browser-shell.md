# Task: Build the Two-Pane Browser Shell

## Goal

Create a browser page with the Claude terminal on the left and chronological
captured model traffic on the right.

## Acceptance criteria

- [x] The panes are resizable and usable at common desktop widths.
- [x] The left pane hosts xterm.js and preserves terminal focus behavior.
- [x] The right pane shows live request, response, error, and completion states.
- [x] Exact/raw and interpreted data are visibly distinguished.
- [x] Keyboard and screen-reader navigation are supported.
- [x] The page exposes explicit session start and stop controls.

## Files likely involved

- `src/web/`
- `src/tests/`

## Discoveries and implementation

- The terminal and flow views use separate WebSockets for the same session;
  terminal output is never treated as proof of intercepted model traffic.
- Chronological cards distinguish request, response-header, response-byte,
  completion, error, and gap states through labels and color-independent text.
- Exact base64 capture-boundary bytes and decoded interpretation are separate,
  labeled disclosure regions. DOM nodes are built with `textContent`, not HTML
  interpolation, because captured bodies are untrusted sensitive input.
- The separator supports pointer dragging and keyboard arrow adjustment with
  ARIA range state. xterm is refit after every split change.
- Below 840 CSS pixels, panes stack vertically to preserve usable terminal and
  evidence regions rather than forcing a narrow two-column layout.

## Validation evidence

- `npm run build` passed TypeScript checking and the Vite production build.
- `python -m unittest discover -s src/tests -v` passed all 21 tests. The live
  Uvicorn test exercised terminal and flow WebSockets concurrently.
- Headless Chrome rendered the production build at 1600×1000; the two panes,
  controls, headers, divider, terminal sizing, and waiting state were fully
  visible without clipping. The screenshot is temporary and is not committed.
- The rendering check exposed a missing favicon request, recorded separately as
  an open bug.

## Status

Done
