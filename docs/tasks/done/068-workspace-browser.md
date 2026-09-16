# Task: Read-only Workspace browser

- [x] Workspace navigation tab preserves Session/Memory and request views.
- [x] Lazy paginated directories, hidden files, breadcrumbs and refresh.
- [x] Safe plain-text file preview and metadata with explicit unsupported cases.
- [x] Fixed configured workspace, GET-only API, no containers or arbitrary roots.
- [x] Verify traversal/link/special-file safety, UI behavior and build.

Browse settings.workspace (the host source of /workspace), including dotfiles.
Do not require an active Claude process to read the persistent workspace.

## Implementation and verification

GET /api/workspace and /api/workspace/file read settings.workspace directly,
with no-store responses, validated relative paths and no-follow descriptors.
Lazy folder listings use cursor pagination and bounded-memory sorting. Plain
UTF-8 preview limited to 1 MiB; link/hardlink/FIFO/binary/oversize cases handled
explicitly. DOM textContent preserves source without rendering active content.
WorkspaceView and navigation retain other panels and their live connections.
ADR-0031 documents architecture, scope and sensitive-file exposure.

Full suite: 152 tests run, 149 passed and three unrelated MLflow integration
tests skipped, including six new workspace filesystem/route tests. Production
build and whitespace check pass. Synthetic Playwright Workspace and Memory
fixtures pass lazy loading, hidden folders, paged entries, text safety, unavailable
links, binary/deleted-file errors, breadcrumbs, refresh, empty folders, navigation,
mobile fit and existing Memory/request-tab/live-connection behavior. Initial
Workspace fixture used an unavailable URL global in the Playwright tool sandbox;
replaced fixture-only parsing and reran successfully.

No workspace content edits, real session interaction or stack restart. Browser
closed. User restarts for new backend routes and refreshes to load the UI.
