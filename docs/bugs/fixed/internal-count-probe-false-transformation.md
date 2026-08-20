# Bug: Internal Count Probe Creates a False Transformation

## Observed

The diff reports `messages/0/0` transformed from the string `count` into a
large `<system-reminder>` block.

## Cause

The predecessor is a `max_tokens: 1` internal count probe. Both requests lack a
stable agent header, so global unclassified chronology incorrectly placed the
probe and the next full session request in one comparison lineage. Path equality
then produced a transformed pair.

## Expected

Recognized internal probes have purpose-specific lineages. Harness wrappers are
identified as injected context rather than unqualified user-authored content.

## Resolution

Resolved on 2026-08-19. Recognized internal requests now use purpose-specific
comparison lineages. The UI also exposes request purpose and block-origin
classification, confidence, and evidence.
