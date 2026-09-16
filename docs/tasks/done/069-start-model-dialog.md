# Task: Model selection before starting Claude

- [x] Start Claude opens an accessible modal; Haiku is selected by default.
- [x] Exact options: claude-haiku-4-5, claude-sonnet-5, claude-opus-4-6.
- [x] Cancel/Escape creates nothing; pending start prevents duplicate submits.
- [x] Backend passes validated model to new-session argv without changing defaults.
- [x] Existing shared-session/reconnect behavior preserved; tests and build pass.

Model identifiers are user-specified; no provider availability guarantee or
automatic fallback is introduced. No live session is started for validation.

Native dialog/select with accessible labels, initial focus, cancellation before
submission, pending-submit guard and inline failure/retry. Optional validated
model field in session creation flows to a single --model argv. Legacy omitted
field preserves server defaults. Existing active session is returned unchanged.
ADR-0032 records per-session selection and provider-availability boundaries.

Verification: 154 tests run, 151 pass and three unrelated opt-in MLflow tests
skip. New tests cover all choices, argv, legacy defaults, invalid IDs, conflicting
extra model args, command override and shared-session reuse. Production build,
whitespace and synthetic Playwright modal fixture pass (choices/default, focus,
Cancel/Escape, pending guard, retry, exact POST model and mobile fit).

No live sessions created or restarted; browser closed. User restart required
for backend model support, then browser refresh to load the dialog.
