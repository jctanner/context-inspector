# Task: Restrict the default Claude workspace

## Goal

Mount this repository's `./workspace` at `/workspace`, not its parent directory.

## Acceptance criteria

- [x] Default settings select and create the local workspace.
- [x] Explicit workspace configuration remains supported.
- [x] Regression tests verify selection and directory creation.
- [x] Document the mount and existing-container restart requirement.
- [ ] Activate the configuration and verify the replacement container mount.

## Discoveries

Settings currently default to PROJECT_ROOT.parent; the runner mounts its cwd
read/write. Live container inspection confirmed sibling repositories are exposed.
Do not interrupt the existing session without restart approval.

## Verification and deployment

`.venv/bin/python -m unittest src.tests.test_config src.tests.test_terminal src.tests.test_launcher`
passed all 13 tests; `git diff --check` passed. Local .env has no workspace
assignment. Workspace contents are ignored without modifying the deleted root
.gitignore. Code is ready; awaiting approval to restart the server and recreate
Claude, ending its current session. The existing mount remains unchanged.
