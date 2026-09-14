# Session Log

## 2026-09-14 — Dynamic stdio MCP experiment

- Task 064: implemented a dependency-free Python stdio MCP server with a
  one-second config poll and tools/list_changed notifications. ADR-0028 records
  process ownership, protocol and evidence boundaries. Python 3.13.14 exists in
  the base image; no new image, HTTP port, SDK or model call is required.
- Read-only source mount plus additive --mcp-config registers only for Claude;
  opt out with CONTEXT_INSPECTOR_MCP_DUMP_ENABLED=0. Other MCP settings and
  existing MLflow arguments remain. Created the ignored workspace config with
  one tool; user must restart to activate the new mount.
- Six focused tests pass including a network-isolated real agent container:
  initialize, paginated 1,000-tool inventory, growth/shrink/zero notifications,
  stable definitions, harmless calls, invalid/missing config retention and
  recovery, invalid protocol requests, and shell wiring. This verifies MCP
  protocol exchange, not actual Claude UI refresh or model-visible schemas.
- No active-session interaction or stack restart was performed.
- Full regression: 129 tests run, 126 passed and three unrelated opt-in MLflow
  container tests skipped. Initial sandboxed run stalled after a network error;
  interrupted and reran successfully with local sockets/container access.
  Shell syntax, whitespace and ignored workspace config checks also pass.

## 2026-09-14 — Variable skill lengths

- Task 063 replaces the interrupted 1,000-line minimum request with uniformly
  random 500–5,000 total lines per file, inclusive of the nine header lines.
- Body lines contain 20 random words by default; bounded descriptions remain
  unchanged. Added line bounds and words-per-line options, replacing body-words.
- Tests use temporary directories only; existing live skills are not rewritten.
  Registration description costs and loaded skill body costs remain distinct.
- All eight tests pass, including a complete 1,000-file batch and endpoint
  checks; whitespace validation passes. No stack changes.

## 2026-09-14 — Rename scripts directory

- Task 062: renamed the generator to `scripts/skill-maker.py` per user request,
  updated tests/docs and ADR-0027; all five generator tests pass.
- Removed the obsolete directory and its disposable bytecode cache only.
  Generated skills and the running stack were untouched.

## 2026-09-14 — Random skill generator

- Task 061: added the explicitly requested `script/skill-maker.py` path;
  ADR-0027 records this source-layout exception and opt-in generation.
- Defaults: 1,000 skills in the ignored nested workspace skill-dump, with
  96 random description words and 256 body words each. Claude's description
  budget may limit actual inclusion; generated words are not observed tokens.
- Five temporary-directory tests pass, including a complete 1,000-skill CLI
  batch, deterministic seeds, collisions, dangling symlinks and invalid counts.
- No live skills were generated, no existing data deleted, and no stack restart.

## 2026-09-14 — Clean Claude startup

- Task 060: reset agreed generated state and memories before new stack sessions;
  preserve configuration/plugins/workspace. User explicitly rejected backups:
  ADR-0026 uses permanent allowlisted removal, live-container checks and a
  stack-lifetime lock, with symlink-resistant descriptor-relative traversal.
- Implementation/tests will not clean the real home or restart the active stack.
- Complete: 115 tests pass, including 10 temporary-home safety/preservation/reset
  tests and real-container MLflow export/reset/origin regressions. No archives or
  backups are created. No real home cleanup or stack restart performed; the next
  user-managed launch permanently clears the agreed entries.

## 2026-09-14 — MLflow browser-origin fix

- Task 059 adds explicit CORS origin configuration and enumerates this host's
  approved LAN/hostname/VPN URLs in ignored local .env. Code defaults remain
  loopback; Host checks and security middleware stay enabled. User will restart.
- Complete: 12 MLflow tests pass, including real-container browser POST allow/
  reject checks and database/artifact reset. 11 additional focused tests pass;
  local .env loading and whitespace checks verified. No active-stack restart.

## 2026-09-14 — MLflow remote chart diagnosis

- Confirmed read-only search POST returns 403 with the LAN browser Origin and
  200 without it. Logs explicitly block that Origin for chart metrics requests.
- Task 058 missed the separate CORS/origin allowlist. Recorded open bug; no
  service/configuration changes or restart during diagnosis.

## 2026-09-14 — Remote MLflow access

- Task 058: configured ignored local .env for 0.0.0.0:5000 and explicit host
  name/LAN/VPN IPv4 allowances. Kept code defaults on loopback and the automatic
  per-container tracing hostname allowance. No wildcard Host bypass, firewall
  changes or stack restart. User performs restart; MLflow remains unauthenticated.

## 2026-09-14 — Claude MLflow integration

- Task 057: user confirms MLflow is running. Official 3.16 Python setup delegates
  to the Node plugin; inspect and pin that package directly. Keep transcript-derived
  traces separate from exact proxy evidence. No running session restart yet.
- Agent image lacks Node; derived image adds Node 24.21.0 and preserves the base.
  Read-only hook-only adapter invokes @mlflow/claude-code 0.4.0 with a 30s deadline.
- Breadboard's reference confirms setup-before-launch, health checks and bounded
  hooks. Retain those safeguards, not its legacy Python hook installation.
- Real Claude against a local fake model completed a Read tool turn and exported
  a trace. Verification SDK required global HTTP tracking URI for artifact download;
  this was a test-query configuration issue, not missing export.
- Complete: 103 Python tests passed, including automatic real-CLI hook export
  with exact session/tool IDs and separate synthetic nested-subagent reconstruction.
  Database/artifact reset, shell syntax and whitespace checks pass. No frontend edits.
- User explicitly wants to launch the stack themselves. No active stack was
  stopped/restarted and no persistent Claude/workspace files were modified.

## 2026-09-14 — Ephemeral MLflow infrastructure

- Task 056: stack entrypoint owns MLflow; the Claude runner is session-scoped
  and is not the correct lifecycle boundary. SQLite/artifacts stay container-local.
- ADR-0024 records disposable storage, loopback binding and deferred integration.
- Complete: 96 Python tests pass including real-container UI, experiment/run,
  artifact upload/download and fresh-launch database/artifact reset checks.
  Initial test search needed explicit max_results; fixture corrected.
- MLflow test containers removed; active stack and Claude session untouched.
  Next normal stack launch starts MLflow. No Claude export is configured yet.

## 2026-09-14 — Response evidence tabs

- Task 055 extends existing closable evidence tabs with Response #N. Current
  response hydration replaces live card content; separate pure rendering keeps
  tab loading from changing live cards, usage accounting or request numbering.
- Complete: shared kind-specific tabs, full ordered response blocks and tool IDs,
  provenance/exact evidence, shortcuts on collapsed repeat groups. Build, 13
  Python checks and response/fast-replay/readability/Memory browser fixtures pass.
  Confirmed fetch cancellation on close; Playwright closed. No session restart.
## 2026-09-14 — Project-local container mirror

- User approved storage redesign: container/home/evaluator/.claude and
  container/workspace. Task 054 replaces Podman-based browsing with direct,
  allowlisted filesystem reads. Existing wrong-home mount recorded as a bug.
- Initial migration check: previous happy_franklin container no longer exists;
  resolving current session before any state migration. Workspace remains intact.
- User confirmed stack was killed; requested handoff rather than automatic
  restart. Moved workspace intact into container/workspace, copied remaining
  local config (empty memory directory), and retained old .state as backup.
  Previous ephemeral evaluator-home files were already unavailable.
- Removed memory container discovery/exec code. Direct local reader enforces
  allowlist/descriptor containment and read limits; no mutation API.
- Build, 86 Python tests and five browser fixtures pass. Network-disabled mount
  probe verified evaluator home and workspace. HTTP cat-only fixture confirmed
  no-store listing and 405/400 mutation/path rejection. All test processes closed.
## 2026-09-14 — Read-only memory browser

- Task 053 and ADR-0023: top-level navigation plus container-only allowlisted
  Markdown viewing. Confirmed UID 1000 home /home/evaluator and project memory
  directory; no file contents exported. No editing or other CRUD scope.
- New backend needs restart; live session will remain untouched during testing.
## 2026-09-14 — Split header overlap

- Task 052: Change overflowed its 32px desktop / 16px mobile gutter. Inline
  nth-child width rules also leaked into the split header at narrow widths.
- Use explicit colgroups, grouped Before/After headings and compact gutter
  labels with accessible names. No data, navigation or baseline changes.
- Completed: build, whitespace and split/fast-replay browser tests pass. Text
  containment and equal half widths verified at 1280, 901, 768, 390 and 320px.
  Playwright closed; refresh loads the corrected header.
## 2026-09-14 — Side-by-side payload diff

- Task 051 adds an optional split layout from the existing unified diff result.
  Each side retains its line numbers and outline targets; unequal hunks get
  blank cells. No new baseline selection or backend calls.
- Completed: accessible cached layouts, location transfer and tab-local choice.
  Build and all four browser fixtures pass, including exact split reconstruction,
  empty/identical/removal-heavy payloads, outline/change navigation and mobile.
  Playwright closed; refresh loads the frontend without a server restart.
## 2026-09-14 — Synchronize change navigation

- Task 050 fixes independently maintained outline and change-navigation state.
  Added bug record; also found initial Previous skips the final hunk.
- Use side-specific containing-node ranges and explicitly reveal lazy ancestors.
- Completed and verified: build plus all four synthetic browser fixtures,
  including 166 worker cases, added/removed side switches, message 204 paging,
  collapsed ancestor reopening, initial Previous/wrap and preserved focus/scroll.
  Playwright closed; no live session input or restart.

## 2026-09-14 — Readable payload root

- Task 049 replaces cryptic root notation with a plain-language payload label
  and count. Child labels and JSON Pointer navigation remain unchanged.
- Verified frontend build, 166 worker cases and outline browser regression,
  including root jump. Playwright closed; refresh loads the updated label.

## 2026-09-14 — Payload outline implementation

- Task 048: index decoded JSON paths in the worker and map side-specific line
  numbers to diff rows. Separate Before/After trees avoid implying semantic
  identity between positional array entries. ADR-0022 records the design.
- Completed: sticky desktop outline, stacked mobile layout, side-specific jump
  highlighting, native disclosures and lazy 100-entry child pages.
- Build and all four synthetic browser fixtures pass (156 worker cases and
  205-message outline fixture). Playwright closed; refresh loads new frontend.

## 2026-09-14 — Default payload diff

- Task 047 makes full payload diff the initial request-tab view and retains
  block inspection as a toggle, even after baseline loading fails.
- Reuses the existing transition and preserves selected views in open tabs;
  live summary loading remains lazy. Updated ADR-0020 and README.
- Frontend build and both browser fixtures pass, including baseline retry.
  Playwright closed; no live session input or restart.

## 2026-09-14 — Visible comparison keys

- Task 046 exposes the exact comparison_lineage under “Comparison group” on
  live cards and collapsed repeat groups. Keys wrap and remain selectable.
- Grouping is not labelled as confirmed agent/conversation identity. Existing
  confidence labels remain. No new API requests or sockets.
- Build/diff checks and both browser fixtures pass; Playwright closed.

## 2026-09-14 — Verify user restart

- New active session 9737831f45f2420387ff9e03ab3e11ba exposes the new operation
  classifications. At inspection: 28 requests, 13 response records, no index error.
- Generation requests #19/#25 use #17/#23, skipping token-count calls #18/#24.
  Task 045 deployed; token-count baseline contamination resolved for new history.
- No session input, restart, or browser connection was introduced by verification.

## 2026-09-14 — Operation-aware baseline fix (awaiting deployment)

- Task 045 isolates token-count and streaming API histories, labels ancillary
  cards, and rejects positional transformations across incompatible block origins.
- Replaying current saved capture preserves 130 requests; #130 now compares with
  #93, retains 41 blocks and no longer pairs foo with a system reminder.
- 77 Python tests, frontend build and both browser fixtures pass; Playwright closed.
- Live server unchanged. Restart requires approval and terminates Claude; an
  archived-session access path is also needed to inspect old cards afterward.

## 2026-09-14 — Transcript correlation experiment

- Task 044 finds exact main-transcript joins for 64 captured requests using both
  response message IDs and response request-id headers. Every distinct transcript
  assistant identifier is represented; no real subagent transcripts available.
- Crucially, foo baseline #128 is a captured count-tokens:rawPredict request.
  All five foo requests are token counting; #130 matches the main transcript.
- Recorded token-count-baseline-contamination bug and aggregate experiment report.
  Reproducible read-only diagnostic and three synthetic join tests added/passing.
- No MLflow installation, Claude input, live-session changes or production
  classification fixes were performed. Unmatched traffic remains unattributed.

## 2026-09-14 — Request 130 block pairing diagnosis

- Confirmed foo-to-system-reminder comparison comes from positional matching at
  messages/0/0 against a one-message baseline. Current request has nine messages
  and a substantially different request shape; predecessor confidence is none.
- Recorded unrelated-request-block-pairing bug. Internal-probe purpose remains
  a hypothesis, not captured fact. No application change made during diagnosis.

## 2026-09-14 — Full request payload diff

- Task 043 adds an optional complete unified diff to request tabs. The recorded
  predecessor is fetched lazily; labels distinguish pretty-printed captured JSON
  from wire formatting and preserve comparison confidence (ADR-0020).
- Worker-based bounded Myers diff, line numbers, +/- coloring, change navigation,
  frame-batched rows and tab-close cancellation keep live-session work separate.
- Worker tests reconstruct both inputs across 155 cases, including first requests,
  identical/repeated lines and a large replacement fallback. Browser fixtures
  verify baseline fetch/reuse, view switching and existing inspection behavior.

## 2026-09-14 — Fix metadata-only tool comparisons

- Task 042 treats cache-only tool_use/tool_result changes as unchanged tool
  content: one neutral disclosure, plus the exact metadata change table.
- All non-cache fields must compare equal, including tool identity and nested
  input. Actual input/ID changes retain before/after views.
- Build/diff checks and both browser fixtures pass, including six new regression
  cases. Playwright closed; frontend refresh loads the fix without server restart.

## 2026-09-14 — Request 83 identical comparison panels

- Compared request 83's exact transformed block: tool_use, same type/ID/name/input,
  only cache_control added (ephemeral). The visible red/green values are identical.
- readableChange's unchanged-content check covers text/thinking but not tool calls.
  Recorded identical-tool-change-panels bug; no application changes made.

## 2026-09-14 — Container-local proxy system trust

- Task 041 adds a container-only trust bootstrap for new agent and probe
  containers. It installs the mounted public CA, preserves existing system roots,
  and drops to UID/GID 1000 before running commands (ADR-0019).
- Fresh disposable-container checks passed: ordinary Git/curl through the proxy,
  expected agent home/PATH/Claude executable and UID/GID 1000. Missing CA fails
  startup with exit 1. No workspace/credentials mounted in smoke-test containers.
- Applied the same bootstrap inside the current agent, without session restart.
  Ordinary Git now reaches a previously failing repository; curl also succeeds.
- Host /etc/ssl/certs/ca-certificates.crt SHA-256 remained
  8c97794a899a32666593979dc7adfaec8bda2b420eb092ff0d987e44ad0bf6ea.
- Shell syntax and diff checks pass; full Python suite passes all 70 tests.

## 2026-09-13 — Diagnose GitHub clone failures

- Current session captures show Git certificate-signer failures on three clones.
- Read-only GitHub ls-remote inside Claude reproduces the failure; explicitly
  supplying the mounted proxy CA succeeds. Runner config sets Node trust only.
- Recorded git-proxy-ca-trust bug. No fix applied or live agent input sent.

## 2026-09-13 — Restore project ignore rules

- Task 040 recreates the deleted root .gitignore at the user's request, extending
  coverage for credentials, captures, workspace state, Python packaging/caches,
  frontend builds/dependencies, browser artifacts, and editor/OS files.
- Two tests cover ignored paths and retained source/examples/lockfiles. No
  tracked files match the rules; no index changes or deletion were needed.
- git diff --check passes. Unrelated source and documentation remain visible.

## 2026-09-13 — Closable request evidence tabs

- Task 039 replaces inline request hydration with deduplicated full-width tabs,
  keeping the live DOM and its existing connections. Summary and legacy replay
  share the evidence renderer. ADR-0018 records tab lifetime and evidence handling.
- Added ×/Delete closing, adjacent selection, keyboard tab navigation, lazy fetch
  cancellation/retry, scroll restoration, and a background request badge.
- Browser validation covers full-width side-by-side views, close/reopen/dedup,
  unchanged socket counts, scrolling, pagination, replay, safe text, metadata-only
  diffs, and narrow screens. Tests use isolated synthetic sessions.
- Final build and all 67 Python tests pass, as do both browser fixtures. All
  Playwright tabs closed afterward. Refresh loads the rebuilt frontend without
  restarting the server or changing the live Claude session.

## 2026-09-13 — Default Claude model

- Task 038 changes the default CLI model to the requested claude-haiku-4-5,
  sharing one constant between direct settings and environment fallback.
- Explicit model overrides remain supported; local .env has no model assignment.
- Configuration/launcher tests: 8 passed; diff check passed. Server and current
  Claude session unchanged; restart required to load the new default.

## 2026-09-13 — Project-local Claude workspace

- Container mount inspection confirmed the default exposed sibling repositories.
- Task 037 changes the default to PROJECT_ROOT/workspace, creates it if missing,
  ignores its contents, and retains explicit workspace overrides (ADR-0017).
- Configuration, terminal and launcher tests: 13 passed. Diff whitespace check passed.
- Deployment awaits restart approval; existing container mounts remain unchanged.

## 2026-09-13 — Fast context replay

- Task 036 adds one context index per session, recent-history pages, no-store
  detail endpoints and compact live batches with a separate replay cursor.
- Browser draws summaries newest first in batches, fetching evidence on expansion
  and older requests on demand. Closed block groups build their contents lazily.
- 61 Python tests and frontend build pass. Both legacy readability/recovery and
  compact-history Playwright scenarios pass.
- Benchmark on current capture: 44 requests, ~14 MB full replay reduced to 94 KB
  initial page (99.33% smaller); 1.087 s cold scan and 0.72 ms warm snapshot.
- New server API is not yet loaded in production. Deployment awaits restart
  direction, since restarting terminates the active Claude session.

## 2026-09-13 — Context stream recovery

- Implemented independent context status, bounded reconnect/replay, and event
  deduplication that preserves usage/response events sharing a wire sequence.
- Confirmed and fixed a separate reader defect: partial trailing JSONL records
  were consumed instead of retried. Added deterministic tests for both readers.
- 60 Python tests, frontend build and synthetic browser recovery tests pass.
- Live browser loads recovery now. Python reader fix waits for next server
  restart; current Claude session preserved. Remote browser's exact failure cause
  remains unverified; both identified code paths are addressed.

## 2026-09-13 — Explain metadata-only changes

- Task 034 fixes readable views that hid removed cache_control behind identical
  Before/After text. Direct field tables now accompany explicit unchanged/changed
  text labels; identical text appears once on demand.
- Build, 11 web regression tests, and extended synthetic browser checks pass.
  Live last-card verification confirms unchanged text and removed ephemeral
  cache-control metadata. No capture data or comparison classification changed.

## 2026-09-13 — Readable inspector cards

- Confirmed task 032 deployment through the real active-session endpoint;
  Playwright reconnected without the temporary discovery adapter.
- Task 033 moves classification details behind evidence disclosures, renders
  readable before/after blocks and replies, groups adjacent matching requests,
  fixes request numbering and neutral missing-response labels, and makes token
  accounting expandable. Reading text is 15px and supporting labels about 13px.
- Added a synthetic Playwright regression scenario under src/tests covering
  grouping, individual evidence, direct replies, text safety, before/after,
  scroll preservation/follow, narrow layout and clear-history behavior.
- Live browser verification: 13 matching requests collapse to one row; the
  continuing session and model replies remain visible. Captured traffic is not
  added as a fixture. Build passes; full-suite results recorded in task 033.

## 2026-09-13 — Shared session discovery

- Added server-authoritative active-session discovery and reuse on Start;
  browsers poll while idle and attach regardless of saved identity.
- Recorded ADR-0013. Session clear-history cursors and expanded cards remain
  browser-local; terminal input, resize, and Stop are shared.
- All 59 tests pass, including simultaneous viewers and matching context replay;
  TypeScript/production build passes. Two isolated Playwright profiles verify
  automatic joining and stale-ID recovery on an isolated cat fixture.
- Attached Playwright to the user's existing live session using a browser-only
  adapter for the new discovery endpoint: 17 requests, 2 response sections.
- Production Python remains unchanged in memory. Task awaits restart direction
  because restarting terminates the user's current Claude session.

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

## 2026-08-20 — README stack architecture

- Added a Mermaid architecture diagram spanning the browser, loopback server,
  PTY/runner, Podman agent and proxy containers, Vertex, and local state.
- Distinguished terminal/control flow, bidirectional proxied model traffic, and
  the independent observation/projection path.
- Included workspace, persistent Claude state, live events, captures, proxy CA,
  and ADC-copy relationships.
- Added a focused README architecture regression test.

## 2026-08-20 — Container lifecycle diagram clarification

- Replaced ambiguous claims that the runner owns containers with an explicit
  Podman engine node.
- Documented that the runner requests a foreground interactive agent, a
  detached proxy, and proxy removal through its exit trap.
- The focused README regression test passes.

## 2026-08-20 — Browser-to-Claude terminal path clarification

- Expanded the Mermaid diagram from a generic terminal WebSocket into the
  complete xterm.js-to-agent-container TTY path.
- Labeled browser keystrokes, resize control, raw output bytes, PTY I/O,
  `run.sh` stdin/stdout, foreground Podman attachment, and container TTY.
- Expanded the README prose to explain that this full-duplex console path is
  independent of the proxy-derived context viewer.
- The focused README regression test passes.

## 2026-08-20 — README live-diff emphasis

- Rewrote the README opening to lead with the visible block-by-block comparison
  of successive captured request contexts.
- Named added, removed, transformed, and retained blocks, plus the correlated
  response and measured usage attached when a call completes.
- Clarified that the viewer tracks model calls rather than assuming one API
  exchange per user turn.
- Both focused README regression tests pass.

## 2026-09-13 — Python project dependency declaration

- Added root `pyproject.toml` for the Python application using the existing
  `src` namespace, with FastAPI, Uvicorn, Pydantic, and PTY runtime
  dependencies plus development and proxy extras.
- Updated the launcher and README to use and provision the project-local
  `.venv`.
- The project-local editable install succeeded; 58 of 59 Python tests passed.
  The remaining live-server test was blocked by the sandbox's socket policy.

## 2026-09-13 — Enable remote server access

- Changed the default Uvicorn bind address to `0.0.0.0` while retaining an
  explicit loopback override through `CONTEXT_INSPECTOR_HOST`.
- Documented remote URL access and the unauthenticated-tool security boundary.
- Configuration tests pass, including rejection of unapproved non-loopback
  addresses.
