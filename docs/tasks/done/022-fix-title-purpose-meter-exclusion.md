# Task: Fix Title-Purpose Meter Exclusion

## Goal

Prevent ordinary tool-bearing requests from being mislabeled as internal title
generation and excluded from the context meter.

## Acceptance criteria

- [x] Tool descriptions cannot trigger title-purpose classification.
- [x] The captured main request is unclassified and the adjacent title request
  remains classified as internal.
- [x] The main request's usage remains eligible for the context meter.
- [x] Tests and frontend build pass.

## Status

Complete

## Findings

The only matching title text in captured event 344 was
`create --title "the pr title"` inside `tools/2/description`. Title-purpose
classification now scans only system and message instruction content and
requires an empty tool set.

## Validation

- Captured replay classifies event 344 as unclassified and event 345 as likely
  internal title generation.
- All focused server/UI tests and the TypeScript/Vite production build pass.
