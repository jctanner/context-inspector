# Task: Enable Remote Server Access

## Goal

Allow the Context Inspector server to accept connections from another machine
on the host network.

## Acceptance criteria

- [x] The default server bind address is `0.0.0.0`.
- [x] Configuration validation permits the wildcard bind and still rejects
  arbitrary unapproved addresses.
- [x] Documentation explains how to connect remotely and warns that this is
  an unauthenticated local tool.
- [x] Configuration tests pass.

## Status

Complete

## Validation

- `./.venv/bin/python -m unittest src.tests.test_terminal -v` — 7 tests
  passed.
- `git diff --check` passed.
