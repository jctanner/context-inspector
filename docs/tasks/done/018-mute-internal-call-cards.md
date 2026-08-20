# Task: Mute Internal Call Cards

## Goal

Make confidently inferred internal calls visually recede without hiding their
request, response, confidence, or evidence.

## Acceptance criteria

- [x] `likely_internal_*` cards receive an explicit semantic CSS class.
- [x] Internal cards use a muted gray treatment with readable content.
- [x] Purpose text remains visible so color is not the only signal.
- [x] Unclassified cards retain their existing styling.
- [x] Frontend regression tests and production build pass.

## Status

Done

## Validation

- TypeScript checks and the Vite production build passed.
- All nine frontend regression tests passed.
