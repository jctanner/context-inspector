# Bug: Context Meter Never Settles

## Observed

After a Claude interaction, the context-size progress bar continues its
indeterminate animation instead of settling on a token count and percentage.

## Expected

When wire-observed response usage is available, the meter should show the
accounted input tokens against the configured context-window limit.

## Investigation

The proxy attempted gzip and UTF-8 decoding independently for every arbitrary
transport chunk. Live responses included many one-byte chunks, so their decoded
views failed and the context stream never saw the SSE usage object.

## Resolution

The context stream now reassembles exact response bytes per flow and decodes the
complete body according to its captured response headers before extracting SSE
usage. Missing or unsupported usage remains explicitly indeterminate.

Fixed by task 010 on 2026-08-19.
