# Task: Default to Claude Haiku 4.5

## Goal

Use the user-requested `claude-haiku-4-5` as the default CLI model.

## Acceptance criteria

- [x] Settings and environment fallback use the requested model.
- [x] Explicit model overrides are preserved.
- [x] Tests verify the generated CLI argument; example configuration is updated.

## Discoveries

The default is duplicated in Settings and from_environment; local .env has no
CONTEXT_INSPECTOR_MODEL assignment. Existing sessions are unaffected by a default
change. No provider calls are needed to test command construction.

## Verification

Configuration and launcher unit tests: 8 passed. `git diff --check` passed.
Default centralized in DEFAULT_MODEL; README and .env.example updated.
No live session was restarted; the new default takes effect after server restart.
