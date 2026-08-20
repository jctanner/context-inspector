# Task: Require Project-Local Environment

## Goal

Make the launcher require and exclusively source `context-inspector/.env`, with
a safe example file documenting supported configuration.

## Acceptance criteria

- [x] `.env.example` documents required Vertex configuration and useful local
  overrides without containing credentials.
- [x] The launcher exits with a clear error when project-root `.env` is absent.
- [x] The launcher sources only project-root `.env`, never a parent file.
- [x] README startup instructions explain how to create the local file.
- [x] Missing-file and successful-source tests pass.

## Status

Complete

## Validation

- `bash -n src/bin/context-inspector`
- All 57 Python tests and the production frontend build pass.
- Tests use an isolated temporary repository to prove both missing-file failure
  and exported project-root values without touching any external `.env`.
