# Session Log

## 2026-08-19

Agent: Codex

Completed:

- Created the `context-inspector` project.
- Adopted the filesystem-native Agent Work Ledger.
- Recorded the real-Claude-CLI requirement as ADR-0001.
- Decomposed the observable-session milestone into initial tasks.

Decided:

- All executable code and tests will live under `src/`.
- Exact wire evidence will remain distinct from interpreted UI views.
- Agent-stream attribution will expose uncertainty rather than inventing a
  definitive primary/subagent identifier.

Next:

- Define the live proxy/server/browser event protocol.
- Decide whether to accept the proposed Python and TypeScript stack.

## 2026-08-19 — Runtime recipe

Agent: Codex

Completed:

- Inspected the validated Podman runner, mitmproxy addon, experiment README,
  and representative `pexpect` drivers.
- Added `docs/notes/validated-podman-mitm-runtime.md` with an implementation
  recipe and failure checklist.
- Distinguished runtime pieces that can be reused from changes required for
  live events, browser PTY control, and concurrent sessions.

Discovered:

- The existing addon emits only from mitmproxy's completed-response hook.
- The fixed proxy name and second-resolution run ID are unsafe for concurrent
  GUI sessions.
- Launching the existing runner beneath a server-owned PTY preserves the real
  CLI path and is a viable first implementation boundary.

Next:

- Define the live event protocol before modifying the capture addon.

## 2026-08-19 — Live event protocol

Agent: Codex

Completed:

- Defined protocol v1 for request, response, block, completion, error, and gap
  events.
- Added a dependency-free Python reference validator and six passing tests.
- Accepted Python and TypeScript as the initial implementation stack.

Decided:

- Live delivery is at least once and deduplicated by stable event ID.
- Reconnect uses a per-session sequence cursor and bounded replay.
- Lost live events are represented by `stream.gap` and degrade completeness.
- Exact base64 bytes remain alongside optional decoded convenience views.
- Response transport chunks are not labeled semantic model content blocks.

Validation:

- `python -m unittest discover -s src/tests -v` — 6 tests passed.

Next:

- Build the PTY-to-WebSocket terminal bridge against this protocol boundary.

## 2026-08-19 — PTY bridge, first implementation

Agent: Codex

Implemented:

- Added a FastAPI server with loopback-only default configuration.
- Added session create/delete routes and a binary-output terminal WebSocket.
- Added a PTY session manager using `ptyprocess` and the existing MITM runner.
- Preserved raw ANSI output and unmodified UTF-8 browser input.
- Added PTY resize propagation and graduated Ctrl-C, `/exit`, then forced
  termination cleanup.

Validated:

- Existing runner path and argv construction.
- ANSI byte preservation, full-duplex input, resize, and forced termination.
- Browser control-message input and resize semantics.
- Loopback binding enforcement.
- `python -m unittest discover -s src/tests -v` — 15 tests passed.

Discovered:

- Reading and writing through the same buffered `ptyprocess` file object can
  stall full-duplex input. The bridge uses the library reader and direct
  `os.write` on the PTY file descriptor.
- The installed Starlette `TestClient` hangs before app startup completes;
  recorded as an open bug rather than hiding it with an unbounded test.

Remaining for Task 002:

- Validate the real ASGI WebSocket and disconnect cleanup with a running server.
- Connect xterm.js and visually confirm Claude's Ink rendering.

## 2026-08-19 — PTY bridge completed

Agent: Codex

Completed:

- Added the xterm.js browser terminal and responsive two-pane shell.
- Added a one-command launcher at `src/bin/context-inspector`.
- Added static browser delivery through the FastAPI server.
- Added an environment-only JSON argv override for harmless integration tests.
- Replaced the unusable in-process TestClient path with a real loopback Uvicorn
  and WebSocket integration test.

Validated:

- TypeScript type checking and Vite production build.
- Headless Chrome loaded the two-pane shell at 1600×1000; xterm calculated a
  93×55 grid.
- Real HTTP session creation, binary ANSI WebSocket output, terminal input,
  resize submission, disconnect cleanup, and subsequent 404 for the removed
  session.
- 17 Python tests pass when loopback socket creation is permitted.

Next:

- Stream live mitmproxy request and response lifecycle events to the server.
## 2026-08-19 — Live proxy event path

- Implemented a mitmproxy addon that emits sanitized protocol-v1 lifecycle
  events without modifying streamed response bytes and retains an independent
  completed-flow archive.
- Added a replayable server-side JSONL tail and per-session flow WebSocket.
- Added a Context Inspector runner derived from the validated experiment
  recipe, with unique proxy names, verified CA smoke test, retained failure
  logs, and explicit empty-capture warnings.
- Discovered that placing proxy state beneath the agent's `:Z`-mounted
  workspace causes an SELinux relabel race and addon `EACCES`. Moved runtime
  state to private `/tmp/context-inspector-<uid>` storage (ADR-0004).
- Verified the actual two-container path without a model call: five live events
  and one completed archive for one intercepted Anthropic HTTP response.

## 2026-08-19 — Two-pane live browser shell

- Connected the evidence pane to the per-session flow WebSocket and rendered
  chronological request, response, byte-block, completion, error, and gap
  states.
- Kept exact base64 wire observations visibly separate from decoded JSON/text/
  SSE interpretations.
- Added a pointer- and keyboard-resizable separator, responsive stacked layout,
  focus-preserving terminal refits, semantic event list, live-region updates,
  and explicit start/stop controls.
- Production TypeScript/Vite build and all 21 Python tests passed. Headless
  Chrome validation at 1600×1000 showed no clipping; it did reveal the missing
  favicon logged under `docs/bugs/open/`.

## 2026-08-19 — Fixed live-event page expansion

- Reproduced the header scrolling away after the flow list accumulated content.
- Identified missing `min-height: 0` constraints on nested CSS grid/flex items,
  which allowed intrinsic event-card height to enlarge the document.
- Made the desktop body a viewport-bound two-row grid and kept scrolling inside
  `.flow-events`; narrow layouts retain a sticky header.
- The Vite production build and the new layout regression test pass.

## 2026-08-19 — Collapsed streaming response noise

- Confirmed that rendering every wire-level `response.block` as a card floods
  the evidence pane and hides request-level context changes.
- Changed the default projection to one updating response row per exact
  `flow_id`, with chunk and byte totals and the latest exact/decoded block.
- Completion updates that row with final archive totals. The header separately
  reports observed events and visible rows, making the collapse explicit.
- TypeScript/Vite production build and UI regression tests pass.

## 2026-08-19 — Corrected proxy readiness

- Traced the transient frontend `curl: (7)` message to the runner checking only
  Podman's running state before starting its proxy smoke test.
- Readiness now also requires mitmproxy's actual listening log marker and fails
  early if the container exits.
- Bash syntax, the real log-marker expression, and runner-order regression test
  pass.

### Readiness regression and correction

- The log-marker gate proved invalid under the GUI PTY: proxy logs could remain
  buffered until cleanup, so the runner exited before launching Claude.
- Replaced log parsing with an in-container TCP connection to the configured
  proxy port. Logs remain retained for diagnosis but no longer control startup.

## 2026-08-19 — Structural context diffs

- Added deterministic normalization of system blocks, complete tool
  definitions, and message content blocks with paths, roles, types, bytes, and
  fingerprints.
- Added retained/moved, added, removed, and transformed comparison semantics.
- Added a replayable derived-context WebSocket that rebuilds its baseline even
  when reconnecting after a sequence cursor.
- Changed the right pane to one card per model request with grouped changes,
  byte/token evidence, lazy exact-field disclosure, and visible predecessor
  confidence.
- Exact duplicate retries do not advance the baseline; message shrinkage is
  labeled a compaction candidate. Global chronology remains explicitly low
  confidence until agent-stream identity is investigated.
- Production web build and all 30 tests pass.

## 2026-08-19 — Agent-stream identity investigation

- Re-examined 14 Phase 1–4 analysis files and their wire captures.
- Found `x-claude-code-agent-id` on every Phase 1/2 subagent and Phase 4 worker
  request, with no occurrences on Phase 1/2/4 parent requests.
- Confirmed the Phase 3 counterexample: forked-skill workers omit the header;
  absence therefore cannot mean primary.
- Rejected shared session/user IDs as stream identifiers and retained system,
  tool, ancestry, and timing features only as heuristics.
- Added conservative identity classification and independent per-agent context
  baselines; documented Unclassified and non-mutating manual overlay design.

## 2026-08-19 — Context utilization meter

- Added an always-visible utilization meter for the most recent model request.
- Correlated SSE response usage to exact request flow IDs and summed uncached,
  cache-creation, and cache-read input tokens.
- Kept the meter indeterminate before usage arrives rather than estimating
  tokens from request bytes.
- Added a documented 200k configured default and
  `CONTEXT_INSPECTOR_CONTEXT_WINDOW_TOKENS` override with visible provenance.
- Production web build and all 36 tests pass, including fragmented SSE and
  real-WebSocket usage delivery.

## 2026-08-19 — Refresh-safe session reconnect

- Decoupled terminal WebSocket attachment lifetime from the server-owned Claude
  PTY; disconnect now unsubscribes without stopping the process or containers.
- Added session-status lookup and browser persistence/validation of the opaque
  active session ID.
- Refresh now reconnects to bounded terminal history and replays recorded
  context observations from the start of the session.
- Kept explicit Stop and server shutdown as authoritative cleanup paths, and
  made CLI exit distinct from a browser detach in the UI.
- TypeScript/Vite production build passed. All 37 Python tests passed, including
  real-server detach, reconnect, input, explicit stop, and 404 validation.

## 2026-08-19 — Context meter SSE reassembly fix

- Diagnosed the permanently indeterminate meter from a live capture: a
  gzip-compressed SSE response arrived in arbitrary, often one-byte transport
  chunks, and per-chunk decompression/UTF-8 decoding failed.
- Changed context derivation to buffer exact wire bytes by response flow,
  decompress the complete response according to observed headers, and then
  extract the `message_start` usage object.
- Preserved explicit indeterminate behavior where usage cannot be observed and
  retained exact request-to-response correlation by `flow_id`.
- Added a one-byte gzip-chunk regression. The production web build and all 39
  Python tests pass.

## 2026-08-19 — Persistent context meter between turns

- Stopped removing the progress value whenever a new request appears.
- The last completed token measurement now remains visible during the next
  in-flight request, with copy explicitly identifying it as the previous
  completed measurement.
- Fresh sessions still use the honest indeterminate state until their first
  wire-observed usage arrives.
- TypeScript/Vite production build and all four frontend regression tests pass.

## 2026-08-19 — Calm unmeasured context state

- Replaced the browser-native indeterminate progress animation with a static
  zero-width placeholder while awaiting the first response usage.
- Added separate measurement-state tracking so the placeholder is never
  represented as an observed zero or a prior completed measurement.
- The production frontend build and all five UI regression tests pass.

## 2026-08-19 — Project-local persistence boundary correction

- Corrected the unfinished Claude-state persistence implementation after an
  unacceptable write outside the project boundary.
- Fixed the persistent location at ignored `.state/claude`; removed the home/
  XDG default and the external path override from the runner and documentation.
- Added regression assertions that reject those external path mechanisms.
- Bash syntax and both runtime-runner tests pass.

## 2026-08-19 — Persistent Claude state and UID correction

- Added project-local, ignored persistence for `/home/runner/.claude` and
  `/home/runner/.claude.json` under `.state/claude` with private permissions.
- Diagnosed `EACCES` from plain keep-id mapping: the image ran as UID 1000 but
  saw the private mount owned by host UID 13437.
- Switched both agent-image invocations to explicit
  `keep-id:uid=1000,gid=1000` mapping.
- A disposable real-image test confirmed `runner:runner` could stat and write
  the mode-0700 mount; shell syntax and runtime regression tests pass.
- The earlier ephemeral container disappeared before its settings could be
  migrated, so the next launch requires one final onboarding pass.

## 2026-08-19 — Explicit request-context provenance

- Renamed the context pane and change groups to explicitly identify model
  request context and request-context blocks.
- Added a request-only provenance statement to every structural diff card.
- Clarified that matching response usage measures request context size but
  response content is not part of the added/removed/transformed/retained diff.
- The production frontend build and all six UI regression tests pass.

## 2026-08-19 — Correlated model responses

- Added a `context.response` projection correlated to request cards by exact
  mitmproxy `flow_id`.
- Reassembled complete gzip/SSE wire responses and reconstructed semantic text,
  thinking, signature, and tool-input content blocks from SSE deltas.
- Displayed model, stop reason, and output-token metadata with separate
  expandable reconstructed blocks and exact captured response evidence.
- Kept arbitrary response transport chunks out of the semantic block view.
- The frontend production build and all 45 Python tests pass.

## 2026-08-19 — Response evidence and inferred purpose labels

- Split exact captured response metadata/wire bytes from the losslessly decoded
  SSE view; kept reconstructed semantic content explicitly interpreted.
- Added conservative response-purpose inference with visible confidence and
  evidence. Calls remain unclassified unless a supported pattern matches.
- Title generation requires both a request instruction and a single-title JSON
  response. The real captured auxiliary call matched both at medium confidence.
- TypeScript/Vite build and all 20 focused server/replay/UI tests pass.

## 2026-08-19 — Context meter internal-call exclusion

- Explained the 385-versus-34.9K discrepancy: the meter selected the auxiliary
  title request, while `/context` described the main session request.
- Retained usage per exact flow and changed the headline to the newest completed
  measurement not classified as internal.
- Made selection robust to either title/main completion order and exposed the
  selected flow plus policy in the meter detail.
- The frontend production build and all eight UI regression tests pass.

## 2026-08-19 — Muted internal-call cards

- Added a semantic `purpose-internal` class when a response matches a supported
  `likely_internal_*` purpose.
- Applied muted gray card, border, evidence, and badge styling while retaining
  readable purpose/confidence text as a non-color signal.
- Unclassified cards keep their existing visual emphasis.
- The frontend production build and all nine UI regression tests pass.

## 2026-08-19 — Clearable context-pane history

- Added a Clear history control that removes only right-pane cards while
  preserving the Claude session, terminal, context meter, and captured data.
- Stored a per-session derived-event watermark so cleared cards do not reappear
  on refresh; new events continue rendering normally.
- Removed the watermark when the session ends to prevent stale state leaking to
  a later session.
- The frontend production build and all ten UI regression tests pass.

## 2026-08-19 — Internal request lineages and harness-origin labels

- Traced a false `count` to `<system-reminder>` transformation to an internal
  `max_tokens: 1` probe sharing the global unclassified predecessor chain.
- Added conservative request-time purpose classification for exact count probes
  and supported title-generation requests, with purpose-specific diff lineages.
- Added medium-confidence origin labels and evidence for `<system-reminder>` and
  local-command wrappers while preserving their exact captured request blocks.
- Internal request cards are muted as soon as the request is observed, rather
  than waiting for response-purpose inference.
- Replayed the active 114-request capture: ten count probes and zero false
  count-to-reminder transformations. The frontend build and all 54 tests pass.

## 2026-08-19 — Adjacent request-event investigation

- Confirmed that displayed numbers are global capture-event sequences, not
  request ordinals.
- Event 344 was the tool-bearing main story request; event 345 was the separate
  tool-free title-generation request started immediately afterward.
- Recorded a false-positive defect in request-time title classification: the
  current recursive scan includes title-related strings from tool schemas.

## 2026-08-19 — Context meter title-classification correction

- Confirmed the stalled meter was caused by the main request being excluded as
  internal alongside the real auxiliary title request.
- Located the false match in a tool description containing
  `create --title "the pr title"`.
- Restricted title-purpose inference to system/message instruction content and
  tool-free calls. Captured event 344 is now eligible for the meter while event
  345 remains internal.
- Focused tests and the production frontend build pass.

## 2026-08-20 — Required project-local environment

- Added a credential-free `.env.example` for the validated Vertex setup and
  common optional runtime overrides.
- Changed the launcher to require and exclusively source project-root `.env`,
  with an actionable error and no parent-directory fallback.
- Updated startup and runtime documentation for the standalone repository.
- Shell validation, all 57 Python tests, and the production frontend build pass.

## 2026-08-20 — Local Vertex environment assembled

- Assembled ignored project-root `.env` from the user-authorized
  `~/bin/claude.vertex` configuration without displaying its values.
- Retained exactly the three required Vertex assignments and excluded the
  executable Claude command.
- Confirmed non-empty values, shell syntax, mode `0600`, and Git ignore status.
