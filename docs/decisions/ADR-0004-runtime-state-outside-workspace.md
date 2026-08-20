# ADR-0004: Keep Runtime State Outside the Mounted Workspace

## Status

Accepted — 2026-08-19

## Context

The agent container mounts the selected workspace with Podman's private SELinux
relabel option (`:Z`). The proxy sidecar separately mounts its live-event
directory with the same option. When that event directory was stored beneath
the workspace, starting the agent recursively relabeled it for the agent
container and the already-running mitmproxy addon began receiving `EACCES`.

The proxy image also starts as container root but mitmdump later writes addon
output as its runtime image user. A root-only directory check therefore gave a
false positive.

## Decision

Runtime state defaults to `/tmp/context-inspector-<host uid>`, mode `0700`,
outside the mounted workspace. Each session receives a private subdirectory.
The proxy's mounted leaf directory is mode `0733` and its pre-created event file
is mode `0666` so the image runtime UID can append; the enclosing application
directory remains mode `0700`, and the event path is never mounted into the
agent container.

The runner verifies the exact event file as container UID 1000 before starting
the agent. Raw captures, logs, credentials, and live events all remain beneath
the private application state root unless the operator explicitly overrides
it with `CONTEXT_INSPECTOR_STATE_DIR`.

## Consequences

- Agent workspace relabeling cannot revoke the proxy's event-file access.
- Runtime captures are ephemeral across host reboot by default.
- An operator choosing a custom state directory must keep it outside the
  workspace and preserve the private-parent/public-leaf permission pattern.
- A stopped proxy container is retained until cleanup copies its logs, so
  startup crashes remain diagnosable.
