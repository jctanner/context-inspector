# Task: Read-only Claude memory browser

## Acceptance criteria

- [x] Persistent Session / Memory navigation; request tabs stay in Session.
- [x] Read-only file tree/source viewer with path, size, modified time and refresh.
- [x] Only mirrored Claude memory: projects/*/memory/**/*.md and CLAUDE.md.
- [x] No host-home browsing, arbitrary paths, symlinks, credentials or mutation API.
- [x] Bounded reads, safe text display, clear empty/error/stopped-session states.
- [x] Tests cover filesystem containment, API permissions and frontend lifecycle.
- [x] Ready for user-controlled startup; no live session terminated by implementation.

## Findings

Active image's UID 1000 home is /home/evaluator. Initial container-discovery
implementation was replaced at user request by task 054's direct local-mirror
reader. No container APIs or host HOME fallback remain. User stopped the stack
and requested notification when ready to start it again.

Scope is view-only. No create, edit, rename or delete features are planned.

## Verification

86 Python tests pass, including descriptor-based containment/symlink/hardlink,
size/binary/FIFO rejection and GET-only active-session/no-store routes. HTTP
checks against a temporary cat-only server verified listing, mutation rejection
and path-escape rejection. Memory browser fixture verifies exact inert source,
lazy loading, refresh, deleted files, errors/empty states, session exit clearing,
request-tab preservation, one pair of live sockets and mobile layout. All four
existing browser fixtures pass too. Test server and Playwright stopped.
