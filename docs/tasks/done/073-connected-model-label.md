# Task: Display selected session model in connection status

User requested the model name beside the frontend connection label.

- [x] Expose launch model in session creation/discovery/status metadata.
- [x] Show it beside Claude connected, including refresh and shared reconnect.
- [x] Keep unknown/legacy metadata safe; verify backend and browser behavior.

This is the selected launch model, not inferred current routing after /model.

Validation: 27 focused tests pass; full Python suite with MCP enabled runs 161
tests, 158 pass and three unrelated opt-in MLflow tests skip. Production build
and whitespace checks pass. Mocked Playwright verifies all model labels, shared
discovery on refresh, reconnect, missing metadata, and existing modal behavior.
No live sessions created or restarted; browser closed. Backend restart and
frontend refresh are user-managed.
