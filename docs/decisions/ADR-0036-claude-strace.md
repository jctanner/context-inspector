# ADR-0036 — Trace Claude syscalls inside its container

## Status

Accepted.

## Decision

Default Claude launches to `strace -ffttv -A -o /strace/pid claude ...` after trust
setup and UID/GID 1000 privilege drop. Bind the project container/strace directory
to /strace. Append mode preserves PID files across launches; files may mix runs.
Directory mode 0700 and trace creation umask 077; existing /container ignore covers
all logs. No automatic deletion, backup or host tracing.

Build a cached derived image over the already selected agent image (including
MLflow's Node layer when enabled), installing strace with apt if missing. This
works independently of MLflow enablement. Add SYS_PTRACE to the agent container
only; retain seccomp/SELinux and rootless user namespace, never use --privileged.
The proxy/readiness probe and non-Claude commands are not traced. An explicit
CONTEXT_INSPECTOR_STRACE_ENABLED=0 disables the layer, mount and capability.

## Consequences

Syscalls can reveal filesystem discovery that model traffic and MLflow omit;
they do not directly identify application-level registry updates. -ff writes
pid.<PID> files including descendants/threads, -tt adds microsecond wall-clock
timestamps, -v expands structures. Default string abbreviation still applies.
Traces can expose credentials, environment and file contents and add substantial
overhead/disk usage. Users must keep them private and manage retention themselves.

References: [strace manual](https://man7.org/linux/man-pages/man1/strace.1.html)
and [Podman run options](https://docs.podman.io/en/latest/markdown/podman-run.1.html).
The required launch combination was validated locally, not inferred solely from
documentation; no seccomp=unconfined option was needed.
