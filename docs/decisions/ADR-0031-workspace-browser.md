# ADR-0031: Read-only local workspace browsing

## Status

Accepted.

## Decision

Add Workspace as a top-level view alongside Session and Memory, preserving
existing terminal/request state. Read settings.workspace directly (host source
of /workspace), independent of Claude session lifetime. No container APIs,
user-chosen filesystem roots, mutations, downloads or active Markdown rendering.

GET-only endpoints lazily list immediate directories, including dotfiles, sorted
folders first. Cursor pages hold at most 200 entries, scanning only the selected
directory with bounded sorting memory. Concurrent filesystem changes make a
listing a best-effort snapshot; Refresh starts over. Breadcrumbs and file list
navigation avoid recursively enumerating potentially enormous skill dumps.

Descriptor-relative no-follow traversal from an absolute configured root blocks
path escapes. Symlinks (including internal ones), hard-linked files and special
files are shown as unavailable and never opened as previews. UTF-8 plain-text
previews are limited to 1 MiB, detect mid-read size/mtime changes, and use DOM
textContent. Responses are no-store; safe errors omit host filesystem details.

## Consequences

Workspace files may contain credentials/source/prompts: anyone with access to
this already-unauthenticated development UI can read them. Keep network access
trusted. Binary/large-file rendering and editing are out of scope. Local files
are not evidence that their content was sent to the model. User restart required
for new backend endpoints; frontend is built without restarting active sessions.
