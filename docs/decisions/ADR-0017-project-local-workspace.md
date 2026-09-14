# ADR-0017: Project-local Claude workspace

## Status

Accepted

## Context

The default parent-directory bind mount exposed sibling projects read/write.
The user requested this project's ./workspace mounted at /workspace instead.

## Decision

Default Settings to PROJECT_ROOT/workspace, creating it when missing. Preserve
explicit CONTEXT_INSPECTOR_WORKSPACE overrides and fail for missing custom paths.
Keep the runtime's cwd-to-/workspace mount: the server supplies Settings.workspace
as the runner cwd. Ignore workspace contents with a nested .gitignore.

## Consequences

New default sessions no longer mount sibling repositories. This is a narrower
mount, not a complete sandbox guarantee; existing config and credential mounts
are unchanged. Existing containers require recreation, and the server must reload
settings. Do not interrupt the active session without approval.
