# Bug: Response Blocks Flood the Context View

## Observed

Streaming model responses can produce dozens or hundreds of `response.block`
events. Rendering every transport chunk as a full card overwhelms the right
pane and obscures the much less frequent model-request context changes.

## Cause

The initial browser shell rendered protocol events one-to-one. That preserves
chronology but mistakes transport chunk boundaries for useful semantic units.

## Expected

The default view should keep one updating response-lifecycle row per HTTP flow.
It should report observed chunk and byte totals while leaving exact individual
events in the live log/archive evidence path.

## Resolution

Fixed on 2026-08-19. The browser now maintains one response-lifecycle row per
wire-observed `flow_id`. `response.started` creates it, every `response.block`
updates its chunk/byte totals and latest-byte disclosure in place, and
`flow.completed` converts it to the final archive summary. The header reports
both observed event count and visible row count so collapsing is explicit.
