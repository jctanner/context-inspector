# Task: Closable request evidence tabs

## Goal and acceptance

- [x] Open request evidence in full-width in-app tabs labeled by request number.
- [x] Each request has an accessible close button; Live session stays pinned.
- [x] Deduplicate tabs, select an adjacent tab on close, and allow reopening.
- [x] Preserve live DOM/connections/scroll; show background activity.
- [x] Present changes first with wider before/after views and collapsed raw evidence.
- [x] Verify build and browser interactions without leaving stale test connections.

## Discoveries

Summary cards currently hydrate evidence inline via lazyDetails. Full legacy
events already contain evidence; both paths must open the same tab UI.

## Implementation and verification

- RequestTabs owns view selection, accessible close controls, abortable fetches,
  retry UI, background badge and keyboard navigation. No additional sockets.
- Full-width evidence uses the existing renderer with no card-registration side
  effects. Before/after columns stack on narrow screens; captured content is text.
- `npm --prefix src/web run build` passes; bundle rebuilt for browser refresh.
- `.venv/bin/python -m unittest discover -s src/tests`: 67 tests pass with local
  socket permission. Updated layout assertion to include the tab-strip row.
- Playwright fast-replay fixture passes including tab close/reopen/dedup, keyboard
  closing, adjacent selection, lazy loading/retry, full-width/side-by-side bounds,
  live badge, scroll restoration and unchanged connection counts.
- Legacy readability fixture passes including grouping, metadata-only changes,
  safe captured text, narrow screens, clear, scroll, and reconnect behavior.
- `git diff --check` passes. All isolated test contexts and Playwright tabs closed.
- No server restart or live Claude input was performed. Refresh loads this change.
