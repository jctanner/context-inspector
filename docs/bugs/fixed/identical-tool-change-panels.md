# Bug: Metadata-only tool changes duplicate identical red/green content

## Evidence

Request 83 in session e4d456ff7c424493b2846fe17021ef89 has one transformed
block at messages/119/1, type tool_use. Exact value comparison shows only
cache_control was added with {"type":"ephemeral"}. Type, ID, name and input
are unchanged; wrapper byte_count and fingerprint change as a consequence.

## Cause

readableChange recognizes unchanged top-level text/thinking only. For tool_use
it displays the metadata change table, then renders red/green Before/After
panels. readableValue renders the same name/input on both sides, omitting
cache_control from those panels. This implies a visible change that did not occur.

## Expected

Show cache-control metadata added with its exact value; present unchanged tool
content once, neutrally. Extend metadata-only detection beyond text blocks.
No application fix applied during diagnosis.

## Resolution

Task 042 adds canonical comparison of tool fields excluding cache_control.
Metadata-only changes display one neutral unchanged-tool disclosure and exact
metadata differences. Real input and identity changes are not suppressed.
Browser regressions pass; frontend rebuilt.
