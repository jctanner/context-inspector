# Task: Model-aware context-window accounting

- [x] Resolve appropriate limits for selected/captured models with explicit provenance.
- [x] Preserve configured overrides; handle model switches and unknown models.
- [x] Test Sonnet 5 usage above 200K against 1M rather than clamping to 100%.

See docs/bugs/fixed/model-context-window-denominator.md. User authorized the fix.
The observed 289,588 input tokens are correct; the static 200K denominator is not.
Both decoded SSE and compressed-response replay need the same per-flow resolver.

## Verification

- `src.tests.test_context_window` covers all three model limits, dated and provider
  IDs, URL detection, unknown/missing model fallback, explicit overrides (including
  200K), out-of-order responses, model changes and replay after a cursor.
- Decoded SSE and gzip replay both preserve 289,588 tokens and yield 28.9588%.
- Focused context tests: 22 pass.
- `CONTEXT_INSPECTOR_TEST_MCP=1 .venv/bin/python -m unittest discover -s src/tests -p 'test_*.py'`:
  158 tests, 155 pass, three unrelated opt-in MLflow tests skip.
- `git diff --check` passes. No frontend changes required.
- User-managed backend restart needed. No live session or stack changes made.
