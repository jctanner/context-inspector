# Phase 1: Observable Session

## Goal

Prove that one browser page can control the real containerized Claude CLI and
display each corresponding intercepted API request and response as it occurs.

## Scope

- local server bound to loopback;
- PTY lifecycle and resize propagation;
- xterm.js terminal rendering and input;
- live request, response, and error events from mitmproxy;
- chronological flow list with exact-versus-decoded labeling;
- deliberate start, stop, and cleanup behavior.

Structural diffs and subagent attribution are later phases.

## Exit criteria

- The CLI remains interactive through browser input.
- Ink/ANSI rendering survives prompt interaction and terminal resizing.
- A completed model turn produces a visible request and streamed or completed
  response in the inspector.
- Closing the session cleans up both containers and preserves diagnostics when
  an error occurs.
