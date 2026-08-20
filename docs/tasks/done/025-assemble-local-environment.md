# Task: Assemble Local Environment

## Goal

Create the ignored project-root `.env` from the user's existing Claude Vertex
launcher configuration without exposing its values.

## Acceptance criteria

- [x] `.env` exists only inside this repository and remains ignored.
- [x] The three required Vertex variables are present and non-empty.
- [x] Launcher commands or unrelated shell logic are not copied into `.env`.
- [x] File contents are not printed or committed.

## Status

Complete

## Validation

- `.env` passes `bash -n` and has mode `0600`.
- An isolated source check confirmed all three required variables are non-empty.
- A structural check found exactly three assignments and no executable lines.
- `git check-ignore .env` succeeds.
