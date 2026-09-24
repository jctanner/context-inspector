# ADR-0043: Enable syscall tracing for OAuth harnesses

Accepted, 2026-09-23, task 089.

The user explicitly requests OAuth tracing for this personal stack. This
supersedes ADR-0039's OAuth syscall-tracing exclusion. Claude/Vertex,
Claude/OAuth and Codex/OAuth now share the existing strace image layer,
SYS_PTRACE capability, non-root wrapper, private container/strace output and
startup/per-session cleanup. The /strace search capability is exposed for all
three profiles, including reconnect. CONTEXT_INSPECTOR_STRACE_ENABLED=0 remains
an opt-out for trace collection; existing files can still be searched.

Trace the launched CLI and descendants with the existing -ffttv -A flags.
Bootstrap/login status checks remain before the wrapper. Runtime OAuth credential
reads/refreshes may therefore appear in unredacted syscall traces; this is the
user-authorized behavior, distinct from redacted proxy capture. Do not add trace
files to version control. MLflow and generated experiment controls remain gated
as before. No automatic attachment to existing processes or session restart.
