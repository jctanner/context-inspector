# Task: Readable Context Inspector

## Acceptance criteria

- Cards prioritize numbered requests, change counts, readable block content and replies.
- Repeated unchanged context is grouped without discarding individual evidence.
- Attribution/provenance, raw JSON and accounting details remain available in disclosures.
- No indefinite waiting label is inferred for missing captured responses.
- Reading text is larger; readable content uses the outer scroll region.
- Incoming traffic preserves a reader's position and provides a new-activity button.
- Empty state and context usage labels are concise.
- Build, regression tests and real-session browser validation pass.

## Discoveries

- The active session now loads through server discovery; task 032 is deployed.
- Most visible cards are unchanged repeats; event sequence was mislabeled as request number.
- Missing reconstructed response does not establish that a request is still pending.

## Completion and validation

All acceptance criteria implemented. Full Python suite: 59 tests passed.
Production build and TypeScript checking passed. The repeatable browser scenario
in `src/tests/readability.browser.js` passed against the rebuilt assets with
isolated synthetic session traffic: grouping and evidence retention, visible
replies, safe literal content, before/after, preserved scroll position, following
response growth, narrow-screen layout and clearing grouping state.

Real-session Playwright inspection confirmed the first 13 matching requests now
occupy a 67px collapsed row instead of thousands of pixels. Readable reply text,
expandable accounting and labeled changes render on the existing shared session.
Refresh the page to load the new bundle; no Python restart is needed.

Architecture: ADR-0014. Readable views do not change classification or raw capture.
