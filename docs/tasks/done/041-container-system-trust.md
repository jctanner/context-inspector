# Task: Install proxy CA in container system trust

## Acceptance criteria

- [x] Automatically install the mounted public proxy CA in new agent/probe containers.
- [x] Preserve system roots and TLS verification; never modify host trust.
- [x] Drop startup privileges before executing Claude or other requested commands.
- [x] Ordinary Git and curl work through the proxy, including the current container.
- [x] Test startup ordering, argument forwarding, failure behavior and live trust.

## Discoveries

The active agent image is Debian 13 with update-ca-certificates and setpriv.
Claude runs as UID/GID 1000. The public CA is mounted read-only; system trust
directories are not bind-mounted from the host. The proxy validates upstream
servers using its existing trust store and does not need to trust its own CA.

## Verification

- bash -n on runner and entrypoint passes; git diff --check passes.
- Full unittest suite passes: 70 tests, including startup ordering and quoted
  argument forwarding assertions. Live-server tests use local socket permission.
- Disposable agent-image smoke test invoked bootstrap with sh -ec and a script
  argument containing spaces/semicolons. It reported UID/GID 1000, correct home
  and Claude executable; ordinary Git ls-remote and curl HTTPS succeeded.
- Disposable container with no CA exited 1 before requested command execution.
- Current agent's system trust updated using the same wrapper over root exec;
  ordinary Git to a previously failing repo and curl now succeed, no restart.
- Host trust bundle hash unchanged (recorded in session log); no host trust
  files or bind mounts modified. New sessions automatically use the wrapper.
