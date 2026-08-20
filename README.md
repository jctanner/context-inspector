# Context Inspector

Context Inspector is a proposed local GUI that combines:

- an interactive browser terminal connected to the real Claude CLI running in
  the existing agent container; and
- a live, evidence-aware view of the model API context observed by the existing
  mitmproxy sidecar.

Implementation code lives exclusively under `src/`. Project state and design
records follow the filesystem-native work ledger indexed by [`PLAN.md`](PLAN.md).

## Run the current prototype

From this directory:

```bash
./src/bin/context-inspector
```

The launcher sources the parent project's `.env`, builds the browser bundle if
needed, and starts the server on `http://127.0.0.1:8765`. Open that URL and use
**Start Claude** to launch the existing two-container runner under the browser
terminal's PTY.

The active session ID is retained in browser storage. Refreshing or navigating
back to the page reconnects to the same live Claude process and replays its
available terminal and context history. Closing the page only detaches the
browser; use **Stop** to terminate Claude and its containers. Restarting the
Context Inspector server still shuts down all server-owned sessions.

The context pane connects to a derived context WebSocket and presents one
structural comparison per model request. Added, removed, transformed, and
retained blocks remain expandable to exact captured request fields. The raw
flow WebSocket and completed archives remain independent evidence paths. Drag
the divider—or focus it and use the left/right arrow keys—to resize the panes.

The utilization meter defaults to a configured 200,000-token window. Override
that denominator for a different enabled model/window configuration:

```bash
CONTEXT_INSPECTOR_CONTEXT_WINDOW_TOKENS=1000000 ./src/bin/context-inspector
```

The numerator comes from wire-observed response usage; the application does
not estimate tokens from request bytes.

Claude's private user configuration persists across disposable agent
containers under this project's ignored `.state/claude` directory. The runner
does not write this state outside the project. It may contain sensitive account,
project, history, or preference metadata and must remain uncommitted.
Project-local `.claude/` instructions remain separate.

For a harmless terminal-only test that does not start Podman or Claude, set
`CONTEXT_INSPECTOR_COMMAND_JSON` to a JSON argv array before launching.
