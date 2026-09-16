# ADR-0034 — Browse the entire Claude state mirror read-only

## Status

Accepted. Supersedes the frontend scope of ADR-0023, not its local-mirror boundary.

## Decision

Replace Memory navigation with ~/.claude. Reuse the Workspace frontend component
with independent element IDs, root label and API prefix. Reuse its bounded,
descriptor-relative no-follow backend reader rooted at CLAUDE_HOME/.claude.
Expose GET-only listing and preview endpoints independent of live session state.
Keep old scoped memory APIs for compatibility; retire the old frontend component.

## Consequences

Users navigate to memories themselves; all directory entries including dotfiles
are visible. Credentials, settings and transcript text are intentionally in scope
under the user's whole-folder request. Warn in UI/docs; never read real contents
as test fixtures. No host-home fallback, mutations or container API access.
No-store responses, 1 MiB UTF-8 previews, paginated directories, symlink/hardlink
and special-file refusal remain. Current file state does not prove model loading.
