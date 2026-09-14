# ADR-0023: Read-only container memory and top-level navigation

## Status

Accepted

## Decision

Add persistent Session / Memory navigation. Keep existing closable request tabs
inside Session; switching sections never creates or closes live sockets.

Expose GET-only session-scoped memory listing and reading. Per the user's revised
direction (task 054), read directly from the project-local
container/home/evaluator/.claude mirror. No container discovery, subprocesses,
container APIs, client-selected roots, or host HOME fallback.

Mount container/home/evaluator/.claude and .claude.json at their matching
container paths, and container/workspace at /workspace. Require the runtime
UID 1000 home to be /home/evaluator, failing clearly for incompatible images.
Ignore the entire mirror and keep Claude state private. Preserve older workspace
and state before changing paths; never silently overwrite existing destinations.

Allow only ~/.claude/CLAUDE.md and Markdown files under
~/.claude/projects/<project>/memory/. Never expose general ~/.claude browsing.
Open paths relative to directory descriptors with O_NOFOLLOW on every component,
reject nonregular/hardlinked files, enforce bounded UTF-8 reads and traversal.
Serve no-store JSON; render source using textContent, never HTML or remote assets.
Display current file content, not a claim that the model loaded it.

## Consequences

No container tooling required for memory reads. Lists memory directories across
the mirrored Claude projects, not other host projects. State survives container
removal. Active-session API gating remains, even though the files persist.
Custom memory locations outside the allowlist are unsupported. Listing/content
are on-demand snapshots; refresh explicitly reloads them. No mutation routes or
CRUD roadmap. Existing session/API access controls also govern sensitive memory;
this does not add authentication to the development server.
