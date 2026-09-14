# ADR-0026: Allowlisted Claude startup reset

## Status

Accepted

## Decision

Reset session history and memories once per normal stack launch, before starting
MLflow/Uvicorn. Hold a project-local advisory lock for the stack lifetime and
refuse cleanup if Podman reports a live container mounting the Claude home or
an overlapping path. Container inspection failures fail closed.

Open the fixed project-local mirror without following symlinks. Permanently
delete only explicitly agreed top-level entries using descriptor-relative,
symlink-resistant removal. Do not follow symlink targets or accept a user-supplied
cleanup path. Per explicit user direction, make no backups or archives. Partial
failure aborts startup; deletion is irreversible.

Keep settings, credentials, plugins, authored instructions, unknown entries,
the sibling .claude.json and workspace. This is not a factory reset: workspace
instructions, custom memory locations and plugin-owned data are out of scope.
Direct ASGI fixtures do not reset data. Runtime command overrides skip the reset
for non-Claude development; the normal launcher resets by default.
