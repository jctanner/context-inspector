# Bug: Context Block Provenance Is Ambiguous

## Observed

Added, removed, transformed, and retained JSON blocks do not visibly identify
whether they came from API requests or responses.

## Expected

The UI explicitly identifies them as normalized request-context blocks and
separately explains that responses supply token-usage accounting.

## Resolution

The pane, every diff card, and every change-group label now say model request or
request-context explicitly. Meter copy explains that matching response usage
measures the request context, while response content is excluded from the diff.

Fixed by task 014 on 2026-08-19.
