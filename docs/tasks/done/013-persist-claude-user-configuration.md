# Task: Persist Claude User Configuration

## Goal

Persist Claude CLI onboarding and acceptance choices across disposable agent
containers while keeping every created file inside this project directory.

## Acceptance criteria

- [x] Claude's `.claude` directory and `.claude.json` survive container exit.
- [x] Persistent state lives under ignored project-local `.state/` with private permissions.
- [x] The runner cannot redirect this state outside the project.
- [x] Existing choices from the active container are migrated when available.
- [x] Runtime regression tests cover initialization and both mounts.
- [x] Documentation states security and concurrency implications.

## Status

Done

## Findings

- Claude writes user state to both `/home/runner/.claude/` and the sibling
  `/home/runner/.claude.json`; mounting only the workspace cannot retain it.
- The prior container containing accepted choices exited before it could be
  copied, so one final onboarding pass is unavoidable.
- Plain `--userns=keep-id` left image UID 1000 unable to access host-UID-owned
  mode-0700 state. Explicit `keep-id:uid=1000,gid=1000` provides the required
  identity translation without weakening permissions.

## Validation

- Bash syntax validation passed.
- Both runtime-runner regression tests passed.
- A disposable real agent-image container ran as `runner:runner` (1000:1000),
  statted the mode-0700 project-local mount, and created/removed a test file.
