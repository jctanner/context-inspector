# Task: Document Stack Architecture

## Goal

Add a Mermaid diagram to the README showing the stack's runtime pieces,
trust boundaries, storage, and connections.

## Acceptance criteria

- [x] Diagram distinguishes browser, host application, Podman containers,
  external model provider, and local state.
- [x] Terminal/control traffic is distinct from proxied model traffic and
  captured observation flow.
- [x] Persistent Claude state, workspace, live events, archives, CA, and ADC
  relationships are represented accurately.
- [x] README documentation regression test passes.

## Status

Complete

## Validation

- The README Mermaid source contains all required runtime boundaries and paths.
- The focused documentation regression test passes.
- `git diff --check` passes.
