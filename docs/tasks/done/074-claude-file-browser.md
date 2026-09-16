# Task: Replace Memory tab with ~/.claude browser

Implementation authorized by user request.

- [x] Browse the local container/home/evaluator/.claude mirror read-only without
  requiring an active session; include dotfiles and nested folders.
- [x] Reuse Workspace browsing controls, pagination, text safety and confinement.
- [x] Rename tab, document sensitive files, verify both browsers and API safety.

User requests whole-folder browsing, not editing or CRUD. Current files do not
prove model ingestion. No real files should be opened during synthetic tests.

## Verification

- Full suite with MCP enabled: 163 tests, 160 pass and three unrelated opt-in
  MLflow tests skip. New routes tested with temporary mirrors: hidden settings,
  nested memory, GET-only methods, no session dependency, no-store errors,
  missing root without creation, traversal/link/hardlink/special-file refusal.
- Workspace's shared reader tests retain pagination, binary/size limits and
  exact text coverage. TypeScript/Vite build and git diff --check pass.
- Both synthetic browser fixtures pass: hidden folders, paginated entries,
  inert source text, errors, breadcrumbs, refresh, independent section state,
  no active session and mobile layout. Fixed an ambiguous test breadcrumb locator
  now that the tab and root button share the ~/.claude label. Browser closed.
- Retired src/web/memory.ts (recoverable from git); replaced its test fixture.
  No user files read, removed or modified. No stack restart.
- User-managed backend restart and browser refresh activate the new API/view.
