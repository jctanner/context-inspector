# Task: Readable payload outline root

## Acceptance criteria

- [x] Replace root shorthand with Request payload · N fields for objects.
- [x] Counts handle singular/empty objects; arrays and scalars are labelled accurately.
- [x] Preserve child labels, JSON Pointers and jump targets; build/browser checks pass.

## Findings

The root currently combines the synthetic $ key with an object-size shorthand.
This is navigation metadata, not captured payload text. Only the root label
needs to change; no architectural change is required.

## Verification

Frontend build passes. Worker fixture passes 166 cases including explicit
eight-field, singular, empty, array and scalar labels on both sides. Outline
browser fixture verifies readable root and first-line jump, plus existing
keyboard/layout/paging behavior. Playwright closed; no server restart or live
session input. Diff whitespace check passes.
