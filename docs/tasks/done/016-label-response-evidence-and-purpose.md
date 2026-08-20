# Task: Label Response Evidence and Purpose

## Goal

Separate exact response wire evidence from decoded views and conservatively
identify likely internal title-generation calls.

## Acceptance criteria

- [x] Exact headers/wire bytes and decoded SSE have distinct labels.
- [x] Reconstructed semantic blocks remain explicitly interpreted.
- [x] Title-generation classification requires request and response evidence.
- [x] Purpose labels expose inference confidence and evidence.
- [x] Unmatched responses remain unclassified, never assumed primary.
- [x] Server and frontend regression tests pass.

## Status

Done

## Validation

- The actual captured title call was classified
  `likely_internal_title_generation` with medium confidence from two explicit
  evidence signals; the user-facing story response remained unclassified.
- TypeScript checks and the Vite production build passed.
- All 20 context, response-replay, and frontend regression tests passed.
