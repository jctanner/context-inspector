# Bug: Git does not trust the capture proxy CA

## Evidence

Current session e4d456ff7c424493b2846fe17021ef89 captured three GitHub clone
failures: certificate signer not trusted. The runner routes all HTTPS through
mitmproxy but sets NODE_EXTRA_CA_CERTS only; Git uses the system CA bundle.

Read-only git ls-remote against octocat/Hello-World in the running Claude
container reproduces the error. The same command with
`-c http.sslCAInfo=/mitmproxy-ca-cert.pem` succeeds and returns HEAD.

## Proposed fix

Configure Git to trust the mounted proxy CA in the launcher, keeping TLS
verification enabled. No runtime settings or application code changed during
diagnosis. Provider access and repository permissions are separate from this
confirmed TLS failure.

## Resolution

Task 041 adds container system-trust bootstrap before the curl probe and Claude,
with UID/GID 1000 privilege drop. Applied the same bootstrap to the current agent
without restart. Ordinary Git access to a previously failing repository and
ordinary curl HTTPS now succeed. Host CA bundle SHA-256 is unchanged.
