# Bug: Context Meter Animates During Every Turn

## Observed

Every new model request removes the progress value, causing the bar to animate
until that request's response usage arrives.

## Expected

The last completed measurement remains visible while the current request is in
flight, then is replaced by the newer measurement.

## Cause

The request renderer unconditionally removed the progress element's `value`
attribute, which is the browser's signal to render an indeterminate meter.

## Resolution

New requests retain an existing determinate value and visibly identify it as
the previous completed measurement. Only a fresh/reset session without usage
uses the indeterminate state.

Fixed by task 011 on 2026-08-19.
