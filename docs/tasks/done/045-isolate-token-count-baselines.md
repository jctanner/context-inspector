# Task: Isolate token-count request baselines

- [x] Classify token-count operations from captured method/URL.
- [x] Keep ancillary requests and request numbering but never use them as generation baselines.
- [x] Label token-count cards and retain exact request evidence.
- [x] Replay current captures to verify request 130 no longer compares foo to reminder.
- [x] Add regression tests for helper interleaving; document deployment requirements.
- [x] Activate corrected comparisons for the user's session.

## Discoveries and verification

Excluding token counts alone selected non-streaming request 124, still a poor
baseline. Streaming API histories now exclude those separate non-streaming calls
as well. Positional transformations require compatible role/category/kind/origin.

Fresh ContextEventStream/ContextIndex replay of the existing session capture
retains all 130 request numbers and classifies 27 token counts. Request 130 selects
request 93, not 128: 41 retained, 4 added, 1 removed, 1 transformed (messages/7/0).
The messages/0/0 foo-to-reminder transformation is gone. No captured data changed.

Full Python suite: 77 tests pass. TypeScript/Vite build, diff check, fast-replay
browser fixture (including ancillary token-count card styling) and readability
fixture pass. Playwright closed. ADR-0021 records comparison boundaries.

## Deployment history

Current server retains old code and indexes. Restart ends the active Claude
session; approval not yet granted. Historical APIs currently require a manager
entry, so a restart alone will not restore access to the old session's cards.
Need a read-only archived-session route/view as part of restoring captured history
after an approved restart. Do not claim the live UI is fixed yet.

## Deployment confirmed — 2026-09-14

User restarted and started a new conversation. Active session
9737831f45f2420387ff9e03ab3e11ba serves request_operation and isolated lineages.
At inspection: 28 requests, 13 response records, no capture error. Token counts
#18 and #24 are skipped by generation requests #19 (baseline #17) and #25
(baseline #23); #24 compares only to token count #18. The new-session fix is live.
Old-session read-only browsing remains optional follow-up, not implemented here.
