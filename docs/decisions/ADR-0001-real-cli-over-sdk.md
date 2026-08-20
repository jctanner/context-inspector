# ADR-0001: Preserve the Claude CLI as the Interaction Surface

## Status

Accepted

## Context

The product must reveal the behavior of the Claude CLI harness itself. Replacing
it with an SDK-driven chat application would construct a different context and
would no longer measure the product under investigation.

## Decision

Run the real Claude CLI in the existing agent container through a pseudo-terminal.
Bridge terminal input, output, and resize events to a browser terminal. Observe
model traffic independently through the mitmproxy sidecar.

## Consequences

Positive:

- The inspected harness is the same interface the user operates normally.
- Slash commands, compaction, subagents, tools, and Ink terminal behavior remain
  in scope.
- Terminal behavior and wire evidence remain independent evidence layers.

Negative:

- PTY lifecycle, ANSI rendering, resize, and disconnect handling add complexity.
- Terminal text cannot be treated as authoritative evidence of model inputs.
- Product updates may change interactive behavior without notice.
