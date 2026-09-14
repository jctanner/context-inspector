# Task: Declare Python Project Dependencies

## Goal

Declare the Context Inspector Python application's build metadata and runtime
dependencies at the repository root, and make the launcher use the project's
local virtual environment.

## Acceptance criteria

- [x] A root `pyproject.toml` declares the Python project and its runtime and
  development dependencies.
- [x] The launcher uses `.venv/bin/python` and reports how to create/install it
  when it is missing.
- [x] Setup documentation explains the dependency installation command.
- [x] Existing launcher tests pass; the full-suite validation result is
  recorded below.

## Status

Complete

## Validation

- `uv pip install --python .venv/bin/python -e '.[dev]'` succeeded and
  installed the declared application and development dependencies.
- `./.venv/bin/python -m unittest discover -s src/tests -v` ran 59 tests; 58
  passed. The one live-server test could not open a listening socket because
  the execution sandbox denied the operation.
- `git diff --check` passed.

## Discoveries

- The launcher changes to the repository root before invoking `python -m
  src.server`.
- Python packages and tests live under the repository's `src/` namespace,
  while the web app has its own `src/web/package.json`.
- The current working tree contains pre-existing deleted and untracked files;
  this task does not modify or stage them.
