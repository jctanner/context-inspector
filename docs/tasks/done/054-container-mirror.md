# Task: Project-local container filesystem mirror

- [x] Default workspace is container/workspace, mounted at /workspace.
- [x] container/home/evaluator/.claude and .claude.json persist at matching container paths.
- [x] Memory API reads allowlisted files directly from the mirror, no container APIs.
- [x] Preserve available current Claude state and existing workspace without overwriting.
- [x] Ignore/protect mirror state, update docs/tests, complete read-only Memory UI tests.
- [x] Ready for next user-controlled startup; mount smoke test verified separately.

Supersedes task 053's initial container-command reader. No full CRUD scope.

## Migration and verification

User stopped the stack before migration; no running containers remained. The
old --rm container and its unmounted /home/evaluator state were no longer
available to copy. No memory files were recoverable from the old local config
directory (empty). Preserved that directory and the existing .claude.json by
copying into the new mirror; left .state/claude unchanged as a backup.

Moved the existing 1.7G workspace directory to container/workspace without
copying/overwriting contents. Mirror/home directories restricted to 0700 and
config remains 0600; all container/ paths ignored by Git.

Build and 86 Python tests pass, all five browser fixtures pass. A temporary
network-disabled container verified UID 1000, /home/evaluator, readable mirrored
config and /workspace with four preserved entries. No Claude process started.
HTTP fixture verified direct local-memory API operation. Temporary server and
Playwright stopped; user may now launch normally to activate production mounts.
