# ADR-0009: Persist Claude User State Inside Project-Local State

## Status

Accepted — 2026-08-19

## Decision

Context Inspector persists the Claude CLI's user-level `.claude` directory and
`.claude.json` file on the host, then bind-mounts them into each disposable
agent container at `/home/runner/.claude` and `/home/runner/.claude.json`.

The host root is fixed at this project's ignored `.state/claude` directory.
It is not externally configurable, preventing the runner from writing outside
the project boundary. Directories are mode `0700`; the top-level JSON file is
mode `0600`.

Project-local `/workspace/.claude` remains distinct. It continues to represent
shared project instructions, agents, and skills rather than private CLI state.

The agent containers use `--userns=keep-id:uid=1000,gid=1000`, mapping the
invoking host user to the image's `runner` identity. This keeps host ownership
and private modes while allowing Claude to read and update the bind mounts.

## Consequences

- Onboarding, theme, trust, and acceptance state can survive `podman run --rm`.
- The state may contain sensitive account, project, history, or preference
  metadata and must not be committed. `.state/` is ignored by Git.
- Sessions share one mutable Claude user configuration. Context Inspector does
  not currently support safely running multiple agent containers concurrently
  against this directory.
- Deleting `.state/claude` intentionally restores first-run behavior.
