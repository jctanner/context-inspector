# Task: Frontend MCP tool count control

- [x] Add current count, positive integer input, Apply and refresh/error feedback.
- [x] Save only tool_count atomically; preserve other config fields.
- [x] Remove MCP count and aggregate-size caps; support names/cursors beyond 99,999.
- [x] Verify API/file safety, large counts, frontend behavior and build.

User explicitly wants only positive-integer count validation, no size ceiling.
Saving configuration is not evidence that Claude has refreshed its tools.

## Implementation

Fixed workspace-relative GET/PUT /api/mcp-dump/count; decimal strings avoid JS
rounding; positive integers only in the widget. Atomic descriptor-relative
file replacement, no symlink traversal, revision conflicts and mutation header.
Other fields are preserved, not revalidated by this control. Invalid JSON must
be repaired rather than implicitly discarded. A missing config uses defaults.
Large MCP names/cursors were formerly five-digit-limited; both now handle
100,000+ tools while lazily generating paginated results. Direct config retains
its existing zero-tool support. ADR-0029 records the uncapped-count decision.

## Verification

- Full suite: 137 tests, 134 pass and three unrelated opt-in MLflow tests skip,
  with CONTEXT_INSPECTOR_TEST_MCP=1 and sandbox restrictions lifted for tests.
- Seven config/API tests cover field preservation, 100,000+ and exact large
  integers, invalid inputs, conflicts, malformed JSON, symlinks/FIFOs and headers.
- MCP regression verifies 200,000 accepted plus tool/cursor beyond 100,000;
  existing protocol and isolated-container tests still pass.
- npm run build and git diff --check pass.
- Playwright synthetic-route fixture passes initial read, invalid positive
  input, Apply/Enter, 100,000, exact >JS-safe integer, conflict, Refresh and
  390px layout. No live API writes; browser closed afterwards.

Live config unchanged; no stack restart. User must restart once to activate
backend routes and reload the MCP script, then refresh the browser.
