# Task 087: Install latest harnesses inside the agent image

Replace host executable mounts and fixed CLI version checks with complete
container-installed latest Claude/Codex packages. Keep host credential sharing,
proxy/CA setup, owned settings and existing Vertex integrations. Cache built
images, provide explicit refresh, record actual versions and validate installed
commands/helpers. Verify isolated image behavior without restarting the main stack.


## Completed implementation

Added complete latest package image recipe and cache/refresh builder. OAuth
preflight now validates only host credentials; removed host executable mounts
and exact version checks. Runtime selects installed executables for Vertex and
OAuth. MLflow image preparation reuses the same complete harness image. Build
records versions; startup verifies executable/help, companion helper and OAuth
selection. Credential mounts, ownership, proxy CA and tracing gates preserved.

## Verification

- Actual derived image: localhost/context-inspector-harnesses:3ba873ab1aa6eebb7d89;
  Claude 2.1.281, Codex 0.156.1. Installed packages and helper are inside the image.
- Full Python regression: 225 tests run, five skipped, all others pass. Coverage
  includes image reuse/refresh args, credential preflight without host binaries,
  no executable mounts and existing Vertex/MLflow behavior.
- Real isolated image-installed Codex tool round trip: exit 0, 79 WebSocket
  messages, three completed responses/diffs/usage. Private evidence directory:
  /tmp/ci-live-oauth-99a6501u. Input usage 10395 / 11781 / 11892.
- Real isolated image-installed Claude tool round trip: exit 0, two HTTP calls,
  tool_use/end_turn, two responses/diffs/usage. Private evidence directory:
  /tmp/ci-live-oauth-l5bw700c. Input usage 10294 / 10533.
- Initial build exposed older base-image Claude shadowing new installation;
  fixed explicit paths and PATH ordering, recorded under fixed bugs.
- No live Vertex model call or interactive browser/code-mode clone was performed.
  Full helper package is installed; native helper startup is verified.
- Shell syntax and whitespace checks pass. Main stack was not restarted or altered.
  Refresh command and current image behavior documented in README and ADR-0041.

Restart backend to remove its old host-binary preflight, then create a new session.
No host executable path configuration is needed. Captures stay private/untracked.
