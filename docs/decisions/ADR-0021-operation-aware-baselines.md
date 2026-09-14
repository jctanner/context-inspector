# ADR-0021: API-operation-aware comparison histories

## Status

Accepted

## Decision

Classify token-count POST endpoints from their captured URL, including Anthropic
messages/count_tokens and Vertex models/count-tokens:rawPredict. Keep these
requests and their numbers, but isolate their baseline history from generation.
Streaming generation endpoints also receive their own history, keeping separate
non-streaming requests from becoming their baselines. Existing purpose/stream
identity boundaries remain, and operation evidence does not establish agent
identity. Unknown operations retain conservative existing attribution labels.

Require matching category, role, kind and origin before positional unmatched
blocks can become transformations. Otherwise report removal/addition. This
prevents user text becoming a system reminder solely by array position, but is
not a complete semantic alignment solution.

## Consequences

Raw captures and request numbering stay intact. Token-count cards are labelled
ancillary and cannot supply headline usage. Baseline changes require rebuilding
derived indexes, not editing captured evidence. Replaying the current saved
capture selects request 93 for request 130, with 41 retained blocks; no foo/reminder
transformation remains. The selected generation baseline is still unclassified,
not a transcript-confirmed primary baseline. Transcript attribution is separate
future work.

Deployment needs a server restart because this process has no hot reload. That
ends its owned Claude session; preserving access to historical cards after restart
also needs a read-only archived-session path, since current APIs require a live
manager entry. Await restart approval rather than mutating the running process.
