# Task: Reuse full payload viewer for responses

User authorized implementation of the proposed shared response payload viewer.

- [x] Response tabs default to complete decoded SSE event payloads with outline.
- [x] Reuse request diff renderer, inline/split and navigation; readable reply
  and exact wire/raw SSE remain available.
- [x] Optional explicit earlier-response comparison, no inferred thread certainty.
- [x] Preserve unknown/malformed SSE data, cancellation, lazy fetch and safety;
  verify response and request browser regressions.

Captured response SSE is not a single JSON document. The view must distinguish
parsed events from raw evidence and never substitute reconstructed reply blocks.

## Verification

- Production TypeScript/Vite build and `git diff --check` pass.
- Response browser fixture: full neutral payload, usage outline jump, raw comment/
  non-JSON/[DONE] retention, explicit comparison, split values, synchronized change
  navigation, failed baseline/retry, readable reply/raw evidence, tab reuse,
  canceled detail loads, grouped access and mobile layout all pass.
- Request outline fixture passes (paged arrays, nested navigation, split layout).
- Shared worker fixture passes 166 lossless before/after reconstruction cases.
- 18 Python context parsing/accounting tests pass. No backend modifications.
- Browser closed; no live model inputs or capture mutations. Refresh the frontend
  to activate; no backend restart required for this task.
