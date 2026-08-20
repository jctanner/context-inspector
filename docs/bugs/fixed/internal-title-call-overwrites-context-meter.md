# Bug: Internal Title Call Overwrites the Context Meter

## Observed

Claude `/context` reports approximately 34.9K tokens while the meter shows 385.

## Cause

The 385-token measurement belongs to a later auxiliary title-generation call.
The meter selected the chronologically latest request before its purpose was
classified, overwriting the roughly 34.8K user-session request measurement.

## Expected

Known internal calls do not replace the headline measurement. The UI retains
the latest measured request not classified as internal.

## Resolution

Usage is retained by exact `flow_id`. When a response is classified with a
supported `likely_internal_*` purpose, its measurement is excluded and the
newest completed eligible measurement is selected. Selection uses response
sequence, so title and main-response completion order does not affect the final
value. The UI exposes the selected flow and policy.

Fixed by task 017 on 2026-08-19.
