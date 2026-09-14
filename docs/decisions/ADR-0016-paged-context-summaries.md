# ADR-0016: Cached Summaries and On-Demand Context Evidence

## Status

Accepted

## Decision

Create one ContextIndex per server-owned session. It consumes ContextEventStream
once and retains derived events and compact summaries in process memory. The
first history request waits for its initial scan; later readers reuse that index.
Stop/session shutdown cancels the index. Captured JSONL remains the independent
wire evidence and is not rewritten or committed.

GET context-history returns the latest 25 requests by default (maximum 100),
with older-page cursor, total count, latest eligible usage and journal cursor.
Summaries omit full changes and captures; replies contain a 500-character preview.
GET context-details/{flow}/{request|response} returns the original derived event
and its evidence, with no-store caching. Scope every lookup to its session.

Compact WebSockets resume after a separate monotonically increasing journal
cursor, including distinct usage/response events sharing a wire sequence. Snapshot
and cursor are selected without an intervening await, so events appended after
snapshot creation are delivered on the live connection. Empty batches act as
connection-status heartbeats. The legacy full-event socket remains supported.

The browser draws summaries in batches, newest first, fetches details only on
expansion, and appends older pages on demand. Closed change groups do not build
block lists. Local clear-history watermark and reconnect behavior remain intact.
Clients fall back to legacy replay when the history endpoint is unavailable,
allowing the rebuilt browser to operate before a Python restart.

## Tradeoffs

The in-memory index grows with session history and is rebuilt after server
restart; this change does not provide cross-worker caching or archived-session
restoration. Cold scans still cost time once per session. Pagination boundaries
can split a repeat group; individual request identity remains preserved.
