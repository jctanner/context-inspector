# Task: Calm the Unmeasured Context Meter

## Goal

Remove the fast native indeterminate animation while preserving an honest
unmeasured state before response usage arrives.

## Acceptance criteria

- [x] A fresh/reset meter is static at zero rather than animated.
- [x] Copy continues to state that response usage is awaited.
- [x] Wire-observed usage still replaces the placeholder value.
- [x] Frontend build and regression tests pass.

## Status

Done

## Implementation

The progress element now has a determinate zero placeholder before its first
measurement, eliminating the browser-native animation. A separate boolean
tracks whether usage has actually been observed, so the UI never describes the
placeholder zero as a previous measurement.

## Validation

- `npm run build` passed TypeScript checks and the Vite production build.
- All five frontend regression tests passed.
