# Task: Clean Claude state on stack startup

- [x] Reset agreed transcript, memory, history and generated-state allowlist once per stack launch.
- [x] Preserve settings, credentials, plugins, authored instructions and workspace.
- [x] Refuse active-container use, concurrent stack ownership and symlinked roots.
- [x] Permanently delete only agreed entries, without backups (explicit user direction).
- [x] Test on synthetic homes only; user restarts the real stack.

MLflow Stop hooks need active transcripts until completion. Cleanup belongs to
the stack entrypoint before MLflow/Claude launch, never per browser or per turn.

## Verification

115 tests pass including 10 temporary-home reset tests, entrypoint ordering,
real Claude Stop-hook export against a fake model, synthetic subagent hierarchy,
MLflow origin controls and ephemeral DB/artifact reset. Cleanup tests verify all
14 allowlisted entries, memory deletion, preserved configuration/workspace,
top-level/nested symlinks, unsafe home rejection, mountpoint checks, live/paused
container mount overlap, Podman failure, lifetime locking and disabled fixtures.
Whitespace check passes. README and ADR-0026 describe irreversible cleanup.

No real Claude home entries were removed and no active stack was restarted.
User must stop the old stack/Claude container and relaunch normally. The next
normal startup permanently removes allowlisted prior data with no backup.
