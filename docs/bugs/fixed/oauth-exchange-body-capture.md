# Bug: Host-only capture selection can persist OAuth exchange secrets

## Summary

`src/proxy/live_capture.py` captures all paths on selected Anthropic and Google
hosts except one readiness URL. Sanitization removes selected headers only;
request URLs and request/response bodies are stored unchanged, including base64
wire copies. An OAuth token exchange on a selected host can therefore persist
credentials even when Authorization is redacted.

## Original reproduction

Use a synthetic POST to `https://oauth2.googleapis.com/token` with a fake
`refresh_token` in its form body and fake `access_token` in its response. `_selected`
returns true; `request`, streaming response, and archive paths retain the bodies.
No production credential or actual token exchange is needed.

## Expected

Authentication exchanges are excluded before body capture/serialization; unsafe
URLs and errors cannot put credentials into events, archives, or diagnostics.

## Original impact and evidence

Code-confirmed selection/sanitization gap. No claim that a real OAuth exchange
had leaked in the current installation. Expanding capture hosts for Codex would
widen this risk unless selection is restricted to validated model operations.

## Resolution

The addon now checks host, POST method, parsed URL, sensitive query names, and
recognized Anthropic/Vertex model paths before it stores URL, headers or body.
Google token endpoints, unknown paths and other methods are excluded. Synthetic
regression tests verify no event or archive is created for an OAuth exchange and
that current Anthropic/Vertex model operations remain selected. Codex traffic is
not enabled pending transport validation.

## Related work

Task 081: implemented the allowlist; task 082 tracks Codex transport work.
