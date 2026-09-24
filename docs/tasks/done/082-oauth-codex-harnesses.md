# Task 082: Add OAuth Claude and Codex harness profiles

## Outcome

Implemented Claude subscription OAuth and Codex ChatGPT OAuth alongside the
existing Vertex profile. Both run native CLIs inside the proxy-configured
container, reuse Linux host logins, and keep inspector settings/history separate.
User selected normal concurrent host CLI use and explicitly approved the separate
Claude credential-directory mount. No host app server or fresh login is required.

See [Phase 04](../../plans/phase-04-oauth-and-codex.md),
[ADR-0039](../../decisions/ADR-0039-harness-auth-and-wire-adapters.md) and
[task 081](081-implement-oauth-codex-safe-foundation.md).

## Acceptance criteria and evidence

- [x] Validate supported native file stores and login methods without printing
  secrets. Host and container status checks confirmed Claude subscription and
  ChatGPT modes. Unsupported Codex keyring/auto stores fail explicitly.
- [x] Preserve native shared-state semantics for concurrent normal host use.
  This replaces the original stronger requirement to demonstrate serialized
  refresh in both orderings for both CLIs, following the user's explicit choice.
  Synthetic native Codex tests show reload after completed refresh and duplicate
  old-token submissions under forced overlap. They do not establish provider
  rotation policy. Claude source and synthetic storage tests establish separate
  auth/config paths and directory locking/replacement. No live refresh was forced;
  no stronger concurrency guarantee is claimed.
- [x] Scoped mounts, isolated settings/history and cleanup: only Codex auth.json
  is mounted; approved Claude directory uses /host-claude-auth. Credentials are
  excluded from browsing and OAuth exchanges from capture. OAuth disables strace,
  MLflow export and experiment controls. Mount replacement stops stale sessions.
- [x] Pin Claude 2.1.280 and Codex 0.156.0; validate auth/version before execution.
  Claude prefers the installed versioned binary. Codex models come from its native
  cache; account entitlement remains a service decision. API preflight precedes
  cleanup. No silent authentication/model fallback.
- [x] Observe real Claude HTTP/SSE and Codex Responses WebSocket tool round trips.
  HTTP fallback has synthetic compression/chunk/gap/replay coverage.
- [x] Integrate per-call context diffs, readable/raw responses, usage and replay.
  Exact HTTP correlation and medium-confidence WebSocket lane/response-ID pairing
  are distinct. Only observed predecessor references link Codex comparisons;
  server-held context, agent identity and unknown context windows stay unknown.
- [x] Enable profile selection, model validation, metadata/reconnect and supported
  controls after live inspection validation. Existing Vertex regressions pass.
- [x] Unit, browser, native-container and replay validation completed below.

## Final validation (2026-09-23)

- Python suite: 218 tests run, 5 skipped, all remaining tests pass.
- Frontend production build, shell syntax and git diff whitespace checks pass.
- Browser fixtures: start-model, codex-inspection, oauth-profiles all pass.
  These use synthetic API/capture fixtures; no live browser TUI round trip claimed.
- Final isolated Codex probe: gpt-5.6-luna, exit 0, 81 logical WebSocket messages,
  one close, three completed responses/context diffs/usage records. Input usage
  10395 / 11781 / 11902. Private evidence: /tmp/ci-live-oauth-x2hts0vt.
- Final isolated Claude probe: selected claude-haiku-4-5, observed
  claude-haiku-4-5-20251001, exit 0, two requests and responses, two context diffs
  and usage records; tool_use then end_turn; input usage 10294 / 10491.
  Private evidence: /tmp/ci-live-oauth-ra685dwu.
- Both probes used existing host login mounts and real proxy/CA configuration,
  small shell-tool round trips and isolated workspaces/networks. No captured
  traffic or token values are committed. Subsequent host login checks still pass.
- Live evidence exposed reserved-provider override and WebSocket control-event
  handling defects; both fixed with regression coverage. Other discovered defects
  are recorded under docs/bugs/fixed/.

## Deployment and limits

The main stack was not started/restarted. Temporary validation server and owned
containers were stopped; final Podman process listing was empty. Start normally
with src/bin/context-inspector and refresh the browser to load these changes.
Host default Claude now reports 2.1.281; inspector keeps installed 2.1.280. Source
review found the same refresh lock in 2.1.281, but forced refresh was not tested.
Native shared-file handling does not guarantee serialized Codex refresh. Cached
models do not prove account entitlement. Native interactive launch is covered by
command/API/PTY tests; live probes exercise native noninteractive tool turns.
