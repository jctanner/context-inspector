# Plan: Claude OAuth and Codex harness/model selection

Date: 2026-09-23. Status: implemented and validated; user-managed startup pending.
Tracking: [task 081](../tasks/done/081-implement-oauth-codex-safe-foundation.md)
and [task 082](../tasks/done/082-oauth-codex-harnesses.md).
Architecture: [accepted ADR-0039](../decisions/ADR-0039-harness-auth-and-wire-adapters.md).

## Final implementation checkpoint

Claude/Vertex, Claude/OAuth and Codex/OAuth are selectable. Native host logins are
reused inside proxy-configured containers with inspector-owned settings/history.
The user chose normal native shared-file behavior, with no app-server requirement,
and approved the separate Claude host credential-directory mount. This supersedes
the original stricter concurrent-refresh acceptance gate: no added serialization
guarantee is claimed, and no live refresh was forced.

Actual Claude HTTP/SSE and Codex WebSocket tool round trips passed with requests,
responses, context diffs and usage. Codex HTTP fallback has synthetic coverage.
Final suite: 218 tests, five skipped, all others pass; production build and three
browser fixtures pass. Task 082 records precise evidence and limitations. Models
come from validated Claude choices and the native Codex cache, not a promise of
account entitlement. Server-held Codex context and unknown windows stay unknown.

The main stack was not started/restarted. Run src/bin/context-inspector and refresh
the browser. See README for pinned binaries, supported credential stores and
mount behavior. No further user design decision is required.

## Historical planning baseline

The remaining sections preserve the original investigation and proposed work
packages. Present-tense code descriptions, unavailable/gated statuses and research
questions below describe that earlier checkpoint, not current implementation.
The completed task and accepted ADR above supersede those statuses and record
changes to acceptance criteria authorized during implementation.

## Required outcome and confirmed user decisions

Keep Claude through Vertex available and add two selectable configurations:

| Harness | Authentication/provider | Model choices |
| --- | --- | --- |
| Claude Code | Existing Vertex / Google ADC | Preserve existing configured choices |
| Claude Code | Existing host Claude subscription OAuth login | Validate against that account/provider |
| Codex CLI | Existing host ChatGPT OAuth login | Validate against that account and pinned Codex version |

The user requires reuse of existing logins on this Linux host, concurrent use of
host CLI sessions, and working capture, request/response inspection, context
diffs, and usage visibility when Codex launches. A terminal-only Codex release
does not satisfy the request. Fresh container login is not the selected workflow.

Retain the real interactive CLI, browser PTY, independent proxy observation,
project-local workspace, and one shared active inspector session. Simultaneous
Claude and Codex sessions *inside the inspector* are not proposed; concurrent
host CLI sessions are required. Model changes inside a running CLI must remain
distinct from the model selected at launch.

## Evidence and limits of this investigation

Reviewed tracked runtime, backend, protocol, frontend, tests, README, existing
ADRs, and ledger records. Read official upstream documentation listed below.
Local `codex --version` reported `codex-cli 0.156.0`; help advertises `--model`,
`--no-daemon`, sandbox/approval controls, and login commands. This does not prove
the agent image contains Codex, nor establish the image's Claude version.

The user subsequently supplied secret-free CLI status output: Claude Code
2.1.280 reports a Claude Max account login, and `codex login status` reports
ChatGPT login. This confirms the host-side CLI sessions are authenticated in the
reported account modes; it does not identify the selected credential backend,
show whether credentials are OAuth-backed files or OS keyring entries, or prove
that refresh state can be shared across concurrent processes. Account identifiers
were intentionally omitted from this plan. No token values were requested or
read.

For the locally pinned Codex CLI version, the tagged upstream source shows a
process-local refresh coordination mechanism and a file-backed auth storage path
that truncates and rewrites `auth.json`. The source does not establish an
inter-process lock or safe concurrent use between host and container; this is a
reason to keep shared writable-file use gated, not proof that every supported
credential backend races. Verify the exact binary's selected backend before any
integration. [Codex v0.156.0 auth manager](https://github.com/openai/codex/blob/rust-v0.156.0/codex-rs/login/src/auth/manager.rs),
[Codex v0.156.0 auth storage](https://github.com/openai/codex/blob/rust-v0.156.0/codex-rs/login/src/auth/storage.rs).

The pinned Codex v0.156.0 provider source confirms the built-in provider supports
Responses WebSockets. For ChatGPT login modes it chooses
`https://chatgpt.com/backend-api/codex` as the default base URL; the Responses
WebSocket client appends `/responses`. This gives a source-verified default path
for a narrowly scoped probe. The host's effective provider configuration was not
read and can override the base URL, so the actual request remains unobserved.
[Codex v0.156.0 provider configuration](https://github.com/openai/codex/blob/rust-v0.156.0/codex-rs/model-provider-info/src/lib.rs)
and [Responses WebSocket client](https://github.com/openai/codex/blob/rust-v0.156.0/codex-rs/codex-api/src/endpoint/responses_websocket.rs).

The current capture addon selects only HTTP POST model operations and has no
WebSocket lifecycle/message hooks. Mitmproxy exposes WebSocket
start/message/end hooks; its message hook observes logical text/binary messages,
so any future capture must label that boundary accurately and version/replay the
added event shape. [mitmproxy event hooks](https://docs.mitmproxy.org/stable/api/events.html).

A metadata-only check found regular credential candidate files at the effective
Claude configuration directory's `.credentials.json` and Codex home's
`auth.json`, each mode 0600. Neither file was opened. Presence does not prove
OAuth auth type, freshness, account entitlement, or that file storage is active
instead of a keyring. No host credentials, private config, live captures, or
user prompts were read. No model calls, logins, containers, resets, or stack
restarts were performed.

### Current code and concrete changes needed

| Area | Confirmed current behavior | Planned change |
| --- | --- | --- |
| `src/server/config.py` | `claude_command()`, fixed Claude model tuple, Claude home constant | Harness/provider registry; validated launch specification |
| `src/server/app.py` | Claude model `Literal`; session metadata recovers model from argv; inherited server env; shared-session lifecycle lock | Validate harness/auth/model combination; retain immutable launch metadata; reject conflicting starts |
| `src/server/terminal.py` | Generic PTY and subscription lifecycle | Reuse; attach safe launch metadata, not credentials |
| `src/runtime/run.sh` | Forwards three Vertex variables, copies ADC if present, mounts Claude state, probes Google discovery URL; proxy does not receive a capture-profile setting | Conditional credentials/mounts/env, selected image, provider-specific readiness and proxy profile |
| `src/runtime/container-entrypoint.sh` | Installs CA, drops to UID/GID 1000; strace and MLflow checks are Claude-specific | Preserve non-root bootstrap; validate Codex trust and execution policy separately |
| `src/server/__main__.py`, `startup_reset.py` | Stack startup clears allowlisted Claude state and traces before app startup; new sessions clear traces | Harness-aware owned-state cleanup; never reset imported host state/credentials |
| `src/proxy/live_capture.py` | Anthropic/Google HTTP POST capture; exact default Codex ChatGPT Responses WebSocket matcher now emits assembled logical messages only after upgrade | Add validated provider-config coverage; preserve handshake secrecy; correlate multiple responses on one socket |
| `src/protocol/events.py`, `server/flows.py` | Strict v1.0 HTTP events; v1.1 now admits `websocket.message` while retaining v1.0 validation/replay | Add close/error and archival semantics; test old readers |
| `src/server/context.py` | Anthropic `system/messages/tools`, Anthropic SSE reconstruction, cache-token accounting | Separate Anthropic and Codex wire interpreters; preserve raw evidence |
| `identity.py`, `context_window.py`, `context_index.py` | Claude agent headers, Claude model/window defaults, derived-context indexing | Provider-qualified lineages, conservative Codex attribution, verified model metadata and replay |
| `src/web/start-dialog.ts`, `index.html`, `main.ts` | Claude-only labels and static model options | Server-backed harness/auth/model selector and honest readiness/status |
| `readable.ts`, `response-payload.ts`, `request-tabs.ts`, payload/diff modules | Generic JSON views alongside Anthropic-oriented presentation | Reuse structural views; test new item/event shapes and usage semantics |
| `mlflow-env.sh`, `mcp-dump-env.sh`, `strace-env.sh`, skill/file browsers | Claude-specific hooks/configuration/state | Explicit capabilities; no automatic claim of Codex compatibility |
| `.env.example`, launcher, README, tests | Vertex-oriented setup and Claude terminology | Document three profiles, credential reuse, pinning, verification and recovery |

### Verified upstream support

- Claude documents Linux `.credentials.json` storage, `CLAUDE_CONFIG_DIR`,
  subscription OAuth login, and competing authentication sources. It also
  documents `claude setup-token` / `CLAUDE_CODE_OAUTH_TOKEN`; that is a separately
  generated token, not proof that exporting a cached access token provides
  equivalent refresh behavior. Prefer the existing-login requirement here.
  [Claude authentication](https://code.claude.com/docs/en/authentication).
- Claude documents HTTP(S) proxy environment variables.
  [Claude network configuration](https://code.claude.com/docs/en/network-config).
- Codex documents file/keyring credential storage, `CODEX_HOME/auth.json`, copying
  a local auth cache to a container, and automatic token refresh. It documents
  `CODEX_CA_CERTIFICATE` with `SSL_CERT_FILE` fallback for HTTPS and secure
  WebSockets. Copy support alone does not establish safe concurrent refresh.
  [Codex authentication](https://learn.chatgpt.com/docs/auth).
- Codex configuration exposes credential-store and model settings. The supported
  configuration must be checked against the pinned runtime, not assumed from
  current online docs. [Configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference).
  Model defaults and offerings change; this plan does not invent a fixed list
  or promise account access. [Models](https://learn.chatgpt.com/docs/models).
- The public OpenAI Responses documentation describes typed streaming events
  and WebSocket continuations using `previous_response_id`. These are references
  for fixture design, **not evidence that this host's OAuth Codex traffic uses
  identical endpoints, fields, or transport**.
  [Streaming](https://developers.openai.com/api/docs/guides/streaming-responses),
  [WebSocket mode](https://developers.openai.com/api/docs/guides/websocket-mode).

## Prerequisites: fix credential exposure paths

Two defects were confirmed using disposable synthetic fixtures and have now been
fixed in the backend/proxy paths:

1. [Credential browser exposure](../bugs/fixed/credential-files-browser-exposure.md):
   the Claude file browser can read a regular `.credentials.json` file. Enforce
   The Claude browser now hides and rejects the `.credentials.json` basename
   server-side, including direct reads and nested listings, while continuing to
   serve ordinary hidden settings files. This handles configured Claude roots
   because the exclusion is applied relative to the configured browser root.
2. [OAuth exchange body capture](../bugs/fixed/oauth-exchange-body-capture.md):
   a synthetic Google token POST is selected and its refresh-token body persisted.
   The addon now captures only POST requests to known Anthropic message/token-count
   paths and Google model prediction/token-count paths. It rejects credential-like
   query keys and user-info before recording request metadata or bodies. Unknown
   hosts/paths, GETs, OAuth endpoints and unrelated Google traffic fail closed.
   Existing Anthropic and Vertex operation fixtures pass. Codex paths are not yet
   admitted because the installed CLI transport has not been observed.

Extend synthetic sentinel checks across terminal diagnostics, proxy logs,
archives, APIs and optional tracing. Existing syscall tracing can observe secret
file reads or traffic; keep it disabled for OAuth sessions until its handling is
proven safe. Header redaction cannot sanitize syscall logs. Do not put tokens in
browser forms, launch argv, `.env`, container image layers, or Podman env options.
The selected CLI necessarily needs credentials; avoid additional copies/surfaces.

The current app defaults to 0.0.0.0 following an earlier remote-access change.
Do not assume loopback protection exists. OAuth development/validation should
explicitly bind loopback; document any deliberate remote deployment separately.
Changing the user's established remote deployment is outside this planning task.

## Proposed architecture

### Separate harness, authentication, model and observation

Introduce a small server-side registry (suggested files under `src/server/`:
`harnesses.py`, `credentials.py`, and provider interpreter modules). Names are
proposals, not existing APIs. Each profile supplies command construction,
credential requirements, environment allowlist, image/version requirements,
capture profile, model catalog, and optional feature capabilities.

Proposed create-session fields: `harness`, `auth_mode`, `model`, plus constrained
existing `extra_args`. Valid pairs are Claude/Vertex, Claude/OAuth and Codex/OAuth.
Preserve omitted-field behavior for existing Vertex clients. Never accept a
browser-provided credential path, token, arbitrary provider URL, or shell command.
Prevent extra args/config from overriding the chosen harness, credentials or
model. Preserve command-override test behavior explicitly.

Store launch metadata on the session: harness, auth mode, selected model, CLI
version, capture profile/version and supported capabilities. Return only safe
metadata via create/active/status. A new Start request selecting a different
profile while a session is active must return a conflict with current metadata;
a reconnect attaches without altering configuration or resetting logs.

Keep container PTY execution. For the inspected Codex 0.156.0, evaluate
`--no-daemon` to keep execution owned by this container/session and avoid routing
to an unrelated background server. Pin/check the actual image version before
using any flags. Do not transplant Claude's permission-bypass flag into Codex;
validate an explicit Codex sandbox/approval policy within Podman.

### Reuse host credentials without assuming safe refresh

Concurrent host use is mandatory. A read-only credential file mount may prevent
refresh persistence; an independently refreshed copy may race with the host;
a writable whole-home mount exposes unrelated state and interacts dangerously
with existing cleanup. None is accepted as a proven solution.

Phase 0 must establish, separately for Claude and Codex:

- Which credential store and auth method the installed CLI actually selects,
  using supported status interfaces and secret-free metadata.
- How it loads, refreshes, atomically replaces and reloads credentials, including
  what happens when another process refreshes first.
- Whether native cross-process coordination works across the proposed
  host/container boundary; an inspector-only file lock cannot coordinate an
  unmodified host CLI. Test rotation, stale copies, expiry and crash recovery.
- Whether the CLI supports a suitably scoped shared credential location without
  sharing settings, histories, plugins or cleanup targets.

Evaluate a narrowly scoped native credential-store sharing approach first if
its concurrent behavior is supported and demonstrated. An imported snapshot is
only acceptable if concurrent refresh and subsequent host use are demonstrated;
copying on every Start is not itself a refresh design. A single-refresh-owner
broker is a research alternative only if both actual CLIs support an integration
that preserves their native auth behavior. Do not invent a token-helper contract,
OAuth client ID, refresh endpoint, token schema, or host synchronization daemon.

If no supported approach passes concurrent-refresh validation, record that as a
feature blocker and return the evidence to the user. Do not quietly require host
sessions to stop, replace OAuth with API keys, or introduce a new login.
Credentials survive inspector restarts; owned transcript/cache cleanup cannot
remove them. Never write refreshed credentials back over host files without a
verified ownership/concurrency design.

### Native provider selection and model choices

For Claude OAuth, remove Vertex/Google routing and ADC mounts. Exclude conflicting
API-key, bearer, cloud-provider, gateway and custom-base-url configuration from
the launched profile, while respecting managed policy rather than bypassing it.
Check the selected auth method before claiming readiness. For Codex, select its
native ChatGPT login; do not send subscription tokens to a guessed public API
endpoint. Verify image-baked environment and config as well as inherited values.

Add a backend capabilities/models endpoint so UI and server share one catalog.
Populate it from a verified supported discovery interface for the pinned CLI and
account if available; otherwise use a documented, configurable validated list.
Do not assume a `codex models` command exists. Each entry records harness/auth
compatibility and the source of any context limit. Keep existing Vertex choices;
validate Claude OAuth IDs separately rather than translating names speculatively.
Never silently substitute a model after a provider rejection.

The dialog chooses Harness → Authentication → Model. It displays missing-login,
unsupported-store, model-unavailable and capture-not-validated states without
exposing tokens/account details. The connected label shows launch choices;
observed per-request model changes use separate wire provenance.

### Independent capture and interpretation

Determine actual hosts, paths, compression and transport in an isolated probe
before broadening capture. The current addon has no WebSocket message callbacks;
adding a hostname cannot capture messages inside an upgraded connection.

If Codex uses HTTP/SSE, add a provider adapter over existing chunks. If it uses
WebSockets, implement message capture with connection ID, direction, ordering,
logical request/response correlation, close/error and replay semantics. One socket
may carry multiple calls; its HTTP flow ID alone is insufficient. Preserve bytes
at the boundary mitmproxy actually exposes, labeling assembled WebSocket messages
accurately rather than claiming raw frame/TLS capture. Pin and test mitmproxy's
behavior. Update strict protocol validation and replay consumers deliberately;
retain v1 HTTP fixture compatibility. Do not silently disable a native transport
merely to make capture appear complete.

For each validated Codex request shape, retain the complete captured payload and
normalize instructions, input items, tool definitions, tool calls/results and
observable reasoning/compaction items with pointers to original fields. Unknown
items remain inspectable. Reconstruct readable responses from verified events;
never present reconstruction as the original wire response.

Diff lineage must include provider/harness, operation and supported conversation
identifiers. Keep retries, compaction and token-count operations separate. A
response/conversation ID does not prove primary/subagent attribution. When no
stable agent identifier exists, display unclassified identity with evidence.

If continuation requests reference server-held context, show their exact delta
and references; reconstruct only previously observed links in a separately
labeled view. Missing predecessors or opaque/compacted state mean incomplete
visibility, not an empty or fully known context. Do not fabricate hidden context
or chain-of-thought.

Derive usage from observed provider usage fields, keeping input/output/cached/
reasoning counts distinct. Verify whether cache counts are subsets before doing
arithmetic; the existing Anthropic sum cannot be reused blindly. Deduplicate
streaming/final usage, handle missing/error usage as unknown, and use only verified
context limits or explicit labeled overrides. No Claude 200K fallback for Codex.

## Delivery sequence and acceptance gates

These work packages are tracked below. A can ship before B, but B stays unavailable
until capture and inspection pass.

| Phase | Work | Acceptance evidence / dependency |
| --- | --- | --- |
| 0: Compatibility research | Pin CLI/image versions; determine native auth store, safe concurrent refresh, actual model catalog and transport; use controlled synthetic/model probes after secret exclusions | Partially complete: local Codex CLI is 0.156.0; user-provided status confirms Claude Max and Codex ChatGPT login modes. Tagged source establishes the built-in ChatGPT provider's default Responses WebSocket route, but the host's effective provider config and traffic through this proxy remain unverified. Selected host auth backend, Claude refresh behavior and container versions also remain unverified. Host session refresh compatibility is a gate. |
| 1: Secret boundaries | Fix both recorded defects, scoped mounts/env, disable unsafe OAuth tracing, owned-state reset isolation | Credential API and broad auth-host capture fixes are implemented and synthetic checks pass. Scoped launch mounts/reset behavior is not implemented; broader sentinel coverage remains. |
| 2: Profile/session refactor | Registry, launch metadata, capability/model endpoint, conditional images/mounts/readiness, reconnect/conflict behavior | Existing Vertex tests pass; invalid combinations rejected; mocked argv/env/mount tests; defaults preserved |
| 3: Claude OAuth | Implement Phase 0's proven host-store integration and native provider selection | Two turns including a tool result, raw request/response, diffs and usage; restart/reconnect and concurrent host refresh succeed; no ADC/cloud/API-key fallback |
| 4: Codex observation | Install pinned Codex; native OAuth runtime; verified HTTP/WebSocket capture; protocol/interpreter/usage/window updates | Synthetic WebSocket message capture/protocol/UI foundation implemented for source-verified default route. A standalone parser prototype recognizes `response.create` fields and `response.completed` usage, leaves context-window size unknown, and passes three unit tests. Still required: actual transport validation, prompt→tool round trip, request/response correlation, context-diff integration, visible usage, replay validation and concurrent host refresh. |
| 5: UI and release | Harness/auth/model dialog, capability-aware labels/controls, docs, migration/recovery instructions | Browser tests cover all three profiles, failures, active-session conflicts and reconnect; end-to-end matrix passes before Codex is offered as ready |

Phases 0 and 1 are interdependent: safe exclusions and synthetic tests precede
any probe with real credentials. Research can inspect versions/help first. The
Codex UI can be built with mocks before Phase 4, but it must remain unavailable
for real launches until the observation gate passes.

Claude-only MLflow hooks, generated skill/MCP experiments, Claude state browsing
and strace are optional capabilities, not implied Codex parity. Disable or label
unsupported controls. If equivalent Codex integrations are wanted, create separate
validated tasks; never use transcripts/MLflow as a substitute for required wire
inspection. Generic workspace browsing and terminal lifecycle remain available.

## Verification matrix

Extend meaningful tests under `src/tests/`, including existing config/runtime,
start-model, session, capture/protocol, context/window/identity, file-browser,
startup-reset and browser suites. Use sanitized synthetic fixtures in source;
keep live traffic outside version control.

- All three profiles: correct image/command/env/mounts/model; no conflicting
  provider leakage; missing/expired/revoked credentials fail clearly; no silent
  provider/model fallback; working TLS with proxy CA and no verification bypass.
- Credential reuse: both refresh orderings, simultaneous host/container activity,
  atomic replacement, stale credentials, restart, cancellation/crash, permissions,
  and account/store incompatibility. Test with actual pinned CLIs as well as
  fixtures; a mocked refresh test cannot establish native concurrency safety.
- Capture: selected model traffic only, excluded OAuth request and response bodies,
  header/query/error sanitation, chunk boundaries/UTF-8, observed compression,
  HTTP errors, retries and interrupted streams. WebSocket fixtures if applicable
  include repeated calls, interleaving, fragmentation/message assembly and close.
- Interpretation: tool round trips, model changes, compaction, missing predecessor,
  unknown item types, absent usage, cache accounting and unknown limits. Verify
  old Claude fixtures and new Codex fixtures independently, plus reload/replay.
- UI: dialog defaults, cancel/duplicate start, incompatible choices, actionable
  errors, launch metadata after refresh, observed model distinction, readable/raw
  request/response navigation, context diff accuracy and capability gating.
- Real release run: record image/CLI versions, selected profile/model, test prompt
  identifiers (sanitized), expected call/usage observations and pass/fail results.
  Confirm concurrent host CLI remains usable. Do not infer success from a rendered
  terminal or nonempty capture file.

Rollback: disable new profiles and retain the Vertex default. Preserve credentials
and evidence outside transient cleanup. Version new capture schemas and retain
legacy readers; rollback must not overwrite host auth or relabel new traces as v1.

## Open questions resolved and remaining

Resolved by user: existing host logins, this Linux host, concurrent host use,
Codex capture/inspection required at launch. User-provided CLI status identifies
Claude Max and Codex ChatGPT login modes. Metadata-only file checks found
credential candidates, but the selected stores and native refresh behavior remain
unverified; do not treat status output or file presence as proof of safe sharing.

Remaining are research gates, not assumptions requiring the user to design the
solution: refresh coordination, actual CLI/image versions, transport/endpoints,
account model availability and context limits. No specific Codex model was
requested; offer only validated choices and leave unsupported choices explicit.
Task 081 implements the two narrow security fixes above. The OAuth and Codex
launch integrations remain future work under task 082: the current environment
does not establish that either CLI can share refresh state safely with a host
session, and the Codex Responses WebSocket has not been observed in this app or
passed through its real capture/replay path. A narrow synthetic message capture
foundation and a standalone Responses usage parser prototype are implemented,
but neither supplies validated per-call context diffs, integrated usage display,
or safe OAuth launch. Do not advertise either option as implemented until its
acceptance gates pass.
