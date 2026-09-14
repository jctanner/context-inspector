# ADR-0019: Container-local system trust for the capture proxy

## Status

Accepted

## Context

HTTPS is routed through mitmproxy, but NODE_EXTRA_CA_CERTS covers Node only.
Git failed certificate validation. The user requests transparent system trust
inside containers without altering host trust.

## Decision

Run agent and curl-probe containers with a mounted startup wrapper as container
root. Install only the public proxy CA under /usr/local/share/ca-certificates,
run update-ca-certificates, then exec the requested command through setpriv as
UID/GID 1000 with no supplementary groups and no-new-privs. Restore the target
account's HOME/USER/LOGNAME while retaining the image PATH and provider/proxy env.
Retain NODE_EXTRA_CA_CERTS for Node's separate trust behavior. No trust directories
are host mounts, no private CA key is added to agent mounts, and verification is
never disabled. The curl probe now uses ordinary system trust rather than --cacert.

## Consequences

Every new agent/probe container receives trust in its disposable writable layer;
no image rebuild or host CA installation is needed. Custom agent images must
provide Debian-style update-ca-certificates, setpriv, and a UID/GID 1000 account.
Startup fails if prerequisites or the CA are missing. The existing proxy's
upstream verification remains unchanged: it does not need to trust its own CA.
Tools with separate private trust stores may still need their own configuration.
The wrapper refuses execution outside a recognized container. Current-container
trust can be installed using the same wrapper via root exec without restarting
Claude; existing commands remain non-root.
