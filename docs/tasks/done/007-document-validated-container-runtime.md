# Task: Document the Validated Container Runtime

## Goal

Give future implementers enough operational detail to reproduce and adapt the
working Claude CLI plus mitmproxy Podman setup without rediscovering its failure
modes.

## Acceptance criteria

- [x] Identify the authoritative existing scripts and image prerequisites.
- [x] Describe network, proxy, CA, workspace, credentials, and environment setup.
- [x] Record the permission and TLS failures encountered and their fixes.
- [x] Describe capture extraction, validation, and cleanup ordering.
- [x] Explain the PTY/`pexpect` lessons relevant to a browser terminal.
- [x] Identify what can be reused unchanged and what live inspection must alter.
- [x] Link the note from `PLAN.md`.

## Files likely involved

- `docs/notes/validated-podman-mitm-runtime.md`
- `PLAN.md`
- `docs/notes/session-log.md`

## Status

Done

## Notes

The recipe was derived from the current runner, capture addon, experiment
README, and representative interactive experiment drivers on 2026-08-19.
