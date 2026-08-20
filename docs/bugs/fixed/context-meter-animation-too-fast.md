# Bug: Context Meter Animation Is Too Fast

## Observed

The browser-native indeterminate progress animation moves rapidly and is
distracting while the application awaits its first usage measurement.

## Expected

The unmeasured state should be calm and clearly labeled without implying that
zero tokens were actually observed.

## Resolution

The unmeasured meter is now a static zero-width bar with explicit “Awaiting
response usage” copy. Measurement availability is tracked separately, and the
first wire-observed usage replaces the placeholder normally.

Fixed by task 012 on 2026-08-19.
