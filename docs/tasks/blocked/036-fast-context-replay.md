# Task: Fast Context Replay

## Acceptance criteria

- Cache derived context once per session rather than replay raw capture per viewer.
- Send lightweight summaries; fetch full per-flow request/response evidence on expansion.
- Initial history is paged newest-first with a consistent live handoff.
- Batch browser updates and avoid building hidden block lists.
- Preserve reconnect, clear-history, provenance, and individual flow identity.
- Measure traffic reduction and verify snapshot/live/evidence paths with tests.

## Baseline

44 requests produced about 13.9 million serialized characters on replay; local
delivery without rendering took about 1.45 seconds. Browser rendered every event
and repeatedly measured layout. Full evidence repeated across the stream.

## Implementation and verification

- Per-session index and compact history/detail endpoints are implemented; live
  summary batches use a distinct cursor and snapshot-to-live handoff.
- Frontend shows newest requests first, 25 per page, with lazy evidence and older
  pages. Legacy-server fallback remains functional until deployment.
- 61 Python tests pass, including cache pagination/evidence separation and real
  HTTP/WebSocket tests of the compact protocol. Production build passes.
- Synthetic Playwright checks pass for 25 initial cards, newest-first ordering,
  zero initial evidence fetches, individual lazy fetch, older pages, live updates,
  reconnect cursor and no duplicates. Existing readability/recovery scenario passes.
- Current 44-request capture benchmark: cold index 1.087 s; warm snapshot generation
  0.72 ms; initial payload 94,259 characters versus 14,076,823 for full derived replay
  (99.33% reduction). Synthetic browser first-page render approximately 200 ms.
- Executable benchmark and browser scenarios live under src/tests; only synthetic
  content is committed as fixture code. No live capture content was copied.

## Awaiting deployment

The browser bundle is rebuilt, but the current Python process lacks the new API.
Restarting ends the active Claude session. Await user direction before restart;
current clients continue via legacy replay in the meantime.
