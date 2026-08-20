# Task: Clarify Terminal Data Path

## Goal

Make the README architecture diagram explicitly show how the browser sees and
interacts with the real Claude CLI console.

## Acceptance criteria

- [x] The browser terminal is identified as xterm.js.
- [x] Keyboard input, resize messages, and raw terminal output cross the
  terminal WebSocket visibly.
- [x] The full-duplex path continues through the PTY, foreground Podman attach,
  and agent-container TTY.
- [x] The terminal path remains visually distinct from the context viewer.
- [x] README regression test passes.

## Status

Complete

## Validation

- The README diagram and explanatory prose name every hop in the bidirectional
  console path.
- The focused README regression test and `git diff --check` pass.
