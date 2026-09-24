# Context usage over time

## Acceptance
Line graph above context meter, response capture timestamps on horizontal axis, percentage on vertical axis. Same usage and internal-call exclusions as meter. Unknown values are gaps, replay deduplicates by flow, clear/new session resets, loaded history is explicitly scoped. Build and synthetic browser validation plus timestamp producer tests. No running stack restart.

## Discovery
Usage events omitted capture timestamps; propagate occurred_at from source event for both providers. Existing history pagination supplies loaded samples only.

## Result
Implemented timestamp propagation and responsive SVG with real time spacing,
percentage grid, focus/hover details, unknown gaps, flow deduplication and existing
internal-call exclusions. Loaded-history scope labeled. Clear/new session resets.

## Validation
- 32 context diff/Codex/index tests passed, including new timestamp assertions.
- Production TypeScript/Vite build passed.
- Synthetic context-history.browser.js passed: live updates, replay, duplicates,
  unknown gaps, keyboard detail, clear, narrow viewport. Desktop screenshot inspected.
- git diff --check passed.

No running stack restart. Normal backend restart and browser refresh required
to supply timestamps and activate the rebuilt frontend. ADR-0046 records choices.
