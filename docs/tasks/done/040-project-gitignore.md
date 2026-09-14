# Task: Restore and extend project ignore rules

## Acceptance criteria

- [x] Ignore local credentials, captures, runtime/workspace state, Python/Node build
  outputs, test artifacts, and editor/OS temporary files.
- [x] Keep source, documentation, environment examples, dependency manifests and
  lockfiles visible to Git.
- [x] Validate rules against representative paths and the current worktree without
  removing files, changing the index, or reading secrets.

## Discoveries

The root .gitignore is deleted in the worktree. Its absence exposes .env, .state,
Playwright output, bytecode and frontend dependencies/builds as untracked files.
The user now explicitly requests a replacement. Preserve all unrelated edits.

## Verification

Two tests in src/tests/test_gitignore.py pass, checking 43 representative paths
with git check-ignore --no-index. git ls-files -ci --exclude-standard produces
no output: none of the currently tracked files match the ignore rules. Diff
whitespace check passes. No files removed or unstaged; lockfiles remain eligible
for tracking, and arbitrary JSON/JSONL source fixtures are not blanket-ignored.
