# Task 086: Mount the native Codex execution helper

Codex interactive workspace execution fails because codex-code-mode-host is not
mounted beside the CLI. Validate the matching installed helper, mount it read-only
and verify helper startup in an isolated container plus runtime regression tests.
Do not restart the user's active stack.


## Implementation and evidence

Native package contains both codex and codex-code-mode-host, but runtime mounted
only codex. Mount the adjacent helper at /usr/local/bin/codex-code-mode-host,
read-only without relabeling the host executable. Native preflight rejects missing
or nonexecutable companions before session cleanup. Container entrypoint checks
helper --help as UID/GID 1000 before allowing the interactive session.

Eight focused runtime tests pass, including missing/nonexecutable helper rejection
and full fake-Podman mount assertions. Real isolated network-disabled agent-image
container successfully runs the helper --help as UID/GID 1000, with no credentials
or workspace mounted. Shell syntax and whitespace checks pass. This verifies
helper availability/startup, not a live model-driven clone. No active stack or
user session restarted. Stop/start the Codex session to recreate its mounts.
