# ADR-0002: Proposed Python and TypeScript Implementation

## Status

Accepted

## Context

The existing experiment drivers and mitmproxy addon are Python. The browser
needs a mature terminal emulator and interactive context views.

## Decision

Use Python for the local server, PTY orchestration, capture decoding, event
correlation, and mitmproxy addon. Use TypeScript and xterm.js for the browser.
Evaluate whether a UI framework is justified only after the first two-pane
prototype.

The protocol reference implementation begins with dependency-free Python so it
can be shared by the Python proxy and server paths without introducing a web
framework dependency into the contract itself.

## Consequences

Positive:

- Existing experiment parsing and capture logic can be reused.
- mitmproxy integration remains native.
- xterm.js provides established browser terminal behavior.

Negative:

- The project has two language toolchains.
- Packaging is less self-contained than a single Go binary.
- A final distribution strategy remains undecided.
