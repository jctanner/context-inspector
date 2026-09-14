# ADR-0018: In-app request evidence tabs

## Status

Accepted

## Context

Inline request disclosures constrain comparison readability. The user requests
full-width in-app request tabs with browser-like close buttons.

## Decision

Keep Live session pinned; hide (never recreate) its DOM while a request tab is
selected. Use session ID plus flow ID for tab identity and the displayed request
number for labels. Fetch summary evidence on first open, or reuse full legacy
events. Reuse the evidence renderer without registering new cards or streams.
Keep exact evidence and attribution collapsible; use responsive before/after
columns. Retain fetched views only in DOM until closed; abort pending loads on
close. Arrow keys/Home/End select tabs; Delete closes a selected request tab.

## Consequences

Tabs add no live connections. Live request activity is counted in a tab badge;
terminal and live scroll state survive switching. Tabs are browser-local and
do not survive page refresh. Loaded evidence remains viewable after session end,
but unavailable lazy evidence offers a retry message. Memory scales with open
tabs, which users can close and reopen from cards. No captured evidence is stored
in localStorage or committed.
