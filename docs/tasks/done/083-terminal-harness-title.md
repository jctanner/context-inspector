# Task 083: Match terminal title to session harness

## Goal and discovery

The terminal heading is hard-coded as Claude CLI even for Codex. Use the existing
session harness metadata for both new connections and reconnects, with a neutral
heading before a session is selected. No architecture change is required.

## Acceptance criteria

- [x] Codex sessions show Codex CLI; Claude sessions show Claude CLI.
- [x] Reconnect preserves the appropriate heading.
- [x] Frontend build and existing OAuth lifecycle browser fixture pass.

## Validation

Production build passes. Existing OAuth lifecycle browser fixture, augmented
temporarily with title and accessible-label assertions, passes for Claude and
Codex on launch and reload. Temporary validation server stopped; no live session
was touched. Refresh browser to load the rebuilt bundle.
