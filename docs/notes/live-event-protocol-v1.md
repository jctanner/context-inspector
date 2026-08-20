# Live Event Protocol v1

## Scope

This protocol carries intercepted model HTTP lifecycle observations from the
mitmproxy addon through the local Context Inspector server to the browser. It
does not carry terminal bytes, commands, or inferred agent-stream assignments.

The protocol describes observations. `response.block` means that another
response byte range was observed; it does not claim that the range is an
Anthropic content block or another provider's semantic unit.

## Envelope

Every event is a JSON object:

```json
{
  "protocol_version": "1.0",
  "event_id": "01J...",
  "session_id": "session-01J...",
  "sequence": 17,
  "occurred_at": "2026-08-19T18:42:31.123456Z",
  "kind": "request.started",
  "flow_id": "mitmproxy-flow-id",
  "sanitization": {
    "applied": true,
    "policy": "browser-v1",
    "redacted_fields": ["request.headers.authorization"]
  },
  "payload": {}
}
```

Rules:

- `protocol_version` is exactly `1.0` for this contract.
- `event_id` is stable across retries and unique within the session.
- `sequence` starts at one and increases by one for every produced event in a
  session, including `stream.gap`.
- `occurred_at` is an RFC 3339 UTC timestamp. It describes observation time,
  not model or terminal chronology inferred after the fact.
- `flow_id` is required for flow lifecycle events and absent for `stream.gap`.
- `sanitization.applied` must be true before an event may be sent to a browser.
- Unknown top-level fields are rejected in v1 so producer/consumer drift is
  detected during development.

## HTTP message representation

Request and response messages contain metadata and an explicit body:

```json
{
  "method": "POST",
  "url": "https://example.googleapis.com/v1/messages",
  "http_version": "HTTP/2.0",
  "headers": {
    "content-type": "application/json",
    "authorization": "[REDACTED]"
  },
  "body": {
    "wire": {
      "encoding": "base64",
      "data": "eyJtb2RlbCI6Ii4uLiJ9",
      "byte_length": 15,
      "content_encoding": "identity"
    },
    "decoded": {
      "kind": "json",
      "value": {"model": "..."}
    },
    "decode_status": "decoded"
  }
}
```

`body.wire` is the exact byte sequence exposed by the capture boundary, always
base64-encoded. `byte_length` is the decoded base64 length. `content_encoding`
records the HTTP encoding associated with those bytes.

`body.decoded` is optional and never replaces `wire`:

- `kind: json` has any JSON value;
- `kind: text` has a string;
- `kind: sse` has a string containing the decoded event stream observed so far.

`decode_status` is `decoded`, `unsupported`, or `failed`. A failure may include
a non-sensitive `decode_error`, but never a credential or body excerpt.

This dual representation prevents a normalized JSON tree from being mistaken
for byte-exact evidence. It also avoids the earlier error of treating compressed
gzip bytes as UTF-8 text.

## Event kinds

### `request.started`

Emitted when the complete outgoing HTTP request is available to the addon and
before waiting for the upstream response.

Payload:

```json
{
  "request": {"method": "POST", "url": "...", "http_version": "...", "headers": {}, "body": {} }
}
```

Exactly one is expected per captured flow.

### `response.started`

Emitted when upstream response status and headers are available.

Payload:

```json
{
  "status_code": 200,
  "reason": "OK",
  "http_version": "HTTP/2.0",
  "headers": {"content-type": "text/event-stream"}
}
```

The event does not assert that the response body is complete.

### `response.block`

Emitted for an observed response byte range.

Payload:

```json
{
  "block_index": 0,
  "offset": 0,
  "body": {
    "wire": {"encoding": "base64", "data": "...", "byte_length": 128, "content_encoding": "identity"},
    "decoded": {"kind": "sse", "value": "event: message_start\n..."},
    "decode_status": "decoded"
  },
  "final": false
}
```

`block_index` begins at zero and is contiguous within a flow. `offset` is the
number of previously observed response body bytes. Chunk boundaries are not
semantic boundaries and may differ across otherwise identical requests.

### `flow.completed`

Emitted after the response is complete and the archival record has been
written or its failure recorded.

Payload:

```json
{
  "request_body_bytes": 12345,
  "response_body_bytes": 678,
  "response_blocks": 8,
  "archive": {
    "status": "written",
    "record_id": "flows.jsonl:12"
  }
}
```

`archive.status` is `written`, `disabled`, or `failed`. A completed HTTP flow
with failed archival persistence remains visible but is explicitly degraded.

### `flow.error`

Emitted when a flow cannot complete normally.

Payload:

```json
{
  "stage": "response",
  "code": "upstream_disconnect",
  "message": "Upstream connection closed before response completion",
  "retryable": true,
  "request_observed": true,
  "response_observed": true
}
```

`stage` is `request`, `connect`, `response`, `archive`, or `internal`. Messages
must be safe for browser display and must not include raw headers or bodies.

### `stream.gap`

Emitted when the producer or server knows that live events were dropped or a
requested replay cursor is older than the retained buffer.

Payload:

```json
{
  "first_missing_sequence": 41,
  "last_missing_sequence": 52,
  "reason": "producer_buffer_overflow",
  "archive_may_recover": true
}
```

A UI that observes a gap must label the affected live session incomplete until
it reconciles against the completed archive.

## Header sanitization

Before an event leaves the proxy/server trust boundary, these header names are
case-insensitively replaced with `[REDACTED]`:

- `authorization`;
- `cookie`;
- `proxy-authorization`;
- `set-cookie`;
- `x-api-key`;
- `x-goog-api-key`.

The sanitization record lists paths that were replaced. HTTP bodies are
intentionally not generically redacted because they are the context being
inspected; they remain sensitive and the application is loopback-only by
default. UI logs and error messages must not echo body content accidentally.

## Delivery, acknowledgement, and deduplication

Delivery is at least once:

1. The producer assigns `event_id` and `sequence` before enqueueing.
2. It retains unacknowledged events in a bounded queue.
3. The server acknowledges the greatest contiguous sequence it has accepted.
4. After reconnect, the producer resends events after that acknowledgement.
5. The server and browser deduplicate by `event_id`.

The server maintains a bounded replay buffer per session. A browser reconnects
with `after_sequence=N`; the server replays retained events greater than `N`
before switching to live delivery. If `N+1` is no longer available, the server
first emits `stream.gap` describing the unavailable interval.

Duplicate events must have identical content. Reuse of an event ID with
different content is a protocol violation and terminates that producer
connection.

## Backpressure

Inspection must not indefinitely block the model request. Both producer and
server queues are bounded by event count and encoded byte size, with exact
limits configurable and recorded in session metadata.

When a queue fills:

1. preserve flow errors, completion events, and the newest state when possible;
2. record the exact dropped sequence interval;
3. emit `stream.gap` when delivery resumes;
4. keep the completed archival capture path independent;
5. surface the session as degraded in the browser.

Silently dropping response blocks or silently blocking mitmproxy is forbidden.

## Partial-flow reconstruction

The server keeps a state machine per `flow_id`:

```text
unknown
  └─ request.started
       ├─ response.started ─ response.block* ─ flow.completed
       └─ flow.error
```

Events can be replayed or duplicated, but a lower lifecycle state cannot replace
a higher one. Missing predecessors, noncontiguous block indexes, byte-offset
mismatches, or a gap mark the reconstructed flow incomplete. The exact event
log remains inspectable even when reconstruction fails.

## Compatibility

Consumers reject unsupported major versions. A future `1.x` producer may add
new optional payload fields only after the validator and compatibility policy
are revised; v1 currently rejects unknown fields to expose accidental drift.

The executable reference validator is `src/protocol/events.py`. Its examples
and failure cases are tested by `src/tests/test_event_protocol.py`.
