# Codex readable response omits completed output-item events

Discovered during task 082 native synthetic callback validation on 2026-09-23.
The context adapter derives readable response blocks only from the final
`response.output` array. When a response supplies completed items through
`response.output_item.done` but omits that final array, raw evidence survives
but the readable response is empty. Preserve observed completed items with
explicit provenance; do not invent missing streamed content or total context.

## Resolution

The adapter retains completed items by output index, rejects conflicting duplicate
indices from the derived view, and uses observed items only when the final output
array is omitted. It exposes output-source metadata and retains all raw messages.
Regression cases for omitted output, conflicts and explicit empty output pass.
