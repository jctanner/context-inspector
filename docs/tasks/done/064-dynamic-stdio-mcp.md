# Task: Dynamic stdio MCP dump

- [x] Python stdio script advertises deterministic dummy tools from workspace config.
- [x] Config edits grow/shrink tool lists and emit list_changed without restart.
- [x] Invalid/partial edits retain last valid config; tool calls have no side effects.
- [x] Wire into Claude startup without changing other MCP configuration.
- [x] Verify real stdio protocol, notifications, config errors and runtime wiring.
- [x] Document configuration and deferred-loading caveat; user restarts stack.

No HTTP service or listening port. Source belongs under src/runtime. Python's
standard library is sufficient for the limited JSON-RPC tools server; stdout
must contain only protocol messages. Default starts with one tool.

## Implementation and evidence

`src/runtime/mcp_dump/server.py` implements stdio initialization, ping, paginated
tools/list and harmless tools/call. Polls once per second on the main thread;
stdin reader thread lets idle clients receive notifications. Stable per-tool
seeds and revision-bearing cursors isolate count edits from content changes.
Invalid/partial/missing config keeps last valid state; initially invalid config
starts empty. Zero removes all tools. Bounds prevent accidental oversized loads.

`mcp-dump-env.sh` adds a read-only source/config mount and additive --mcp-config
only for Claude. It does not use --strict-mcp-config or edit existing server
registrations. Disabled via CONTEXT_INSPECTOR_MCP_DUMP_ENABLED=0. Source stays
under src; Python 3.13.14 is already available in the agent image.

Created ignored `container/workspace/.context/mcp-dump/config.json` with one
tool, 200 description words, 20 schema properties and seed 42. A missing file
is created exclusively at server start, not overwritten on subsequent launches.
README covers workflow, bounds, context-vs-discovery distinction and tests.

## Verification

Six focused tests pass, including network-isolated agent-container stdio tests.
Real subprocess exchange verifies initialization; 1→1,000→2→0 tool changes;
notification-driven refresh; pagination and stale cursors; stable descriptions;
changed schemas/seeds; calls and errors; partial/missing config retention;
recovery; unchanged config silence; clean stdin-EOF shutdown; shell wiring.

Full suite outside the filesystem/network sandbox:
`CONTEXT_INSPECTOR_TEST_MCP=1 .venv/bin/python -m unittest discover -s src/tests -p 'test_*.py' -v`
ran 129 tests in 17.7 seconds: 126 passed, three unrelated opt-in MLflow container
tests skipped. The initial sandboxed full run hit a local-network error and
stalled; it was interrupted before the successful unsandboxed retry. Shell
syntax, git diff --check, and workspace-config ignore checks pass.

This validates protocol behavior in the actual agent image, not a live Claude
UI/model request. User-managed restart is required to mount/register the server;
then /mcp and captured requests can verify Claude's loading behavior. No active
stack restart or live-session prompts were performed by the assistant.
