# Task: Trace Claude syscalls in the agent container

Base image is Debian 13 and currently lacks strace; apt-get is available.

- [x] Install strace in a cached derived image without changing the base image.
- [x] Bind container/strace to /strace and trace Claude with -ffttv -o /strace/pid.
- [x] Scope tracing permissions to agent container; preserve non-root execution,
  MLflow/MCP integration and normal terminal/exit behavior.
- [x] Verify in disposable containers; document sensitive output and overhead.

User will restart the stack. Do not attach to or restart the current process.

## Verification

- Built localhost/context-inspector-strace-test:077, installing strace 6.13 in
  a derived Debian image; base image and running containers unchanged.
- Isolated network-none tests ran through the actual trust/drop-privilege wrapper
  with SYS_PTRACE and default seccomp/SELinux: UID 1000, stdin/stdout preserved,
  child file reads in per-PID traces, microsecond timestamps, 0600 files, exit 7
  propagated, existing files preserved by -A across two container launches.
- Native `claude --version` succeeds under strace, with no model call or credentials.
- Enabled/disabled/non-Claude wiring, symlink-root rejection, plugin ordering,
  ignored paths and shell syntax checks pass.
- Full suite with MCP and strace integration enabled: 167 tests, 164 pass,
  three unrelated opt-in MLflow tests skip. git diff --check passes.
- No persistent test containers, live session attachment or stack restart. Test
  image remains cached; normal next launch derives a content-keyed image over
  the chosen agent image. User can restart when ready. Trace directory is created
  at the next Claude launch, not populated with test data.
