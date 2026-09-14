# ADR-0015: Recover Context Streams Independently

## Status

Accepted

## Decision

Context sockets have separate status and reconnect with bounded exponential
backoff after closure/errors. Capture-record errors also trigger replay, enabling
recovery from a partial write even with the old server reader. Advance the cursor
only after successful rendering. Resume one sequence before the last processed
event and deduplicate by sequence, kind and flow: usage and response can share
the same wire completion sequence. Honor the browser's clear-history watermark.

Invalidate old sockets and retry timers when leaving a session. Preserve rendered
history during reconnect. Server readers advance only past newline-terminated
records, retrying an incomplete final line on their next poll.

## Consequences

No server/session restart is required to deploy browser recovery. The reader fix
requires a server restart, which should wait until the user's live session can
end. The precise cause in a remote browser cannot be asserted without its logs;
these are independently verified failure paths, not proof of that browser's cause.
