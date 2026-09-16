# ADR-0029: Frontend MCP count control

## Status

Accepted; updates ADR-0028's tool-count and aggregate-metadata limits.

## Decision

Put a compact MCP tools input, Apply and Refresh in the frontend navigation.
Accept positive decimal integers with no application count or aggregate-size
ceiling, per explicit user direction. Transfer counts as decimal strings to
avoid JavaScript numeric rounding. Preserve direct config's existing zero-count
support. Other MCP settings remain file-managed and retain their own validation.

Use fixed workspace-relative GET/PUT endpoints, no browser-supplied paths.
PUT changes only tool_count, requires a custom same-origin request header and
uses a revision check plus atomic replacement. Descriptor-relative no-follow
access rejects symlinks and special files. Do not overwrite malformed JSON or
silently replace a newer externally edited config. Revision checks mitigate
concurrent edits but are not a lock that external editors must respect.

## Consequences

Saved count is configured state, never proof of MCP reload or model-visible
schemas. User sees this distinction and explicit save errors. Large counts may
consume substantial resources or hit Claude/client limits; this control does
not guarantee client acceptance. MCP pages remain lazily generated. Names and
cursors support more than five digits. A user-managed restart activates backend
routes and removes limits from the already-running MCP process.
