# Context Inspector Agent Handbook

## Required workflow

This project follows the [Agent Work Ledger](https://gist.githubusercontent.com/jctanner/7f1d5f132cf3f9b7fc67fbb3e3c8ff4c/raw/0a1381f3b2059825192dd5ccb7055e65c77b9f68/agentic_work_ledger.md).

Before changing the project:

1. Read `AGENTS.md` and `PLAN.md`.
2. Select or create a task under `docs/tasks/pending/`.
3. Move it to `docs/tasks/current/` before implementation.
4. Record discoveries in the task and `docs/notes/session-log.md`.
5. Record architectural choices as ADRs under `docs/decisions/`.
6. Record newly discovered defects under `docs/bugs/open/` immediately.
7. Verify the task's acceptance criteria.
8. Move the task to `done/` or `blocked/` and update `PLAN.md`.

Task status is determined by directory location, not by prose alone.

## Source layout

- All executable application source belongs under `src/`.
- Tests are application source and belong under `src/` as well.
- Project-management records, design documents, and user documentation belong
  outside `src/`.
- Generated files and captured model traffic must not be committed unless a
  task explicitly requires a sanitized fixture.

## Evidence rules

- Preserve the distinction between exact wire-observed data and an interpreted
  or reconstructed view.
- Never label inferred primary/subagent attribution as certain without a stable
  captured identifier.
- Record the evidence and confidence behind request-stream classification.
- Treat request bodies, responses, credentials, source code, and user prompts
  as sensitive data.
- Bind development services to loopback by default.

## Completion rules

A feature is not complete merely because the UI renders. Its task must include
the relevant tests or reproducible validation evidence, and `PLAN.md` must make
the resulting project state understandable without chat history.
