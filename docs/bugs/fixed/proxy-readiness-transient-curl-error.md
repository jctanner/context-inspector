# Bug: Terminal Shows a Transient Proxy Connection Error

## Observed

Immediately after **Start Claude**, the terminal can show:

```text
curl: (7) Failed to connect to context-inspector-proxy-... port 8080
```

The stack subsequently works because curl retries.

## Cause

The runner treated Podman's `State.Running=true` as proxy readiness. That only
means the container process exists; mitmproxy may not yet have bound port 8080.

## Expected

The runner waits for mitmproxy's actual `HTTP(S) proxy listening at ...` log
marker before launching the smoke-test client. Retry remains defensive but
normal startup produces no false error.

## Failed first fix

The first attempted fix depended on mitmproxy's listening log text. Under the
GUI PTY launch, `podman logs` remained empty until cleanup, so the runner timed
out and exited before starting either the curl smoke-test or Claude container.
This was a regression: only the proxy container appeared.

## Resolution

Readiness is now tested directly inside the proxy network namespace by opening
a TCP connection to `127.0.0.1:8080`. Container state is retained only as an
early crash detector; human-readable log text is diagnostic evidence, not the
machine readiness contract.

Validated with the real two-container runner and a no-model-call Anthropic curl
request: the runner advanced past readiness, started the agent container,
produced five valid live events, wrote one completed archive record, and exited
successfully without the transient curl error.
