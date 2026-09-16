# Response event rendering is unwieldy for long streams

Observed 2026-09-15 in response #56: 2,102 SSE records, including 2,092
content_block_delta records, produce 35,737 table rows. A signature_delta has
11,144 characters; raw_fields repeats the serialized data alongside parsed data.
Wrapped signature lines become very tall. The initial outline exposes only a
single events array, adding navigation overhead. No evidence establishes this
response as ancillary: request and response classifiers are unclassified.

Read-only isolated browser reproduction used real captured response with API/WS
interactions mocked; no terminal input, live session changes or capture edits.
Browser closed. No captured response content is included in this record.

Potential fix: navigable reconstructed message as a clearly labeled optional
view; keep complete SSE events/raw fields available, reduce default duplication
and bound rendering work. Avoid hiding usage or confusing reconstruction with wire.
