# Bug: Title-Purpose Classifier Scans Tool Schemas

## Observed

The main agent request at capture event 344 is labeled likely internal title
generation even though event 345 is the actual title-generation request.

## Cause

The request-time classifier recursively searches every string in the payload.
A title-related phrase inside the main request's tool definitions satisfies the
pattern even though its system and message instructions do not ask for a title.

## Expected

Purpose inference should inspect instruction-bearing system/message content and
exclude tool names, descriptions, and input schemas. The exact request remains
available independently from this inferred label.

## Evidence

- Event 344: 27 tools, main story prompt, 1,484 response blocks.
- Event 345: zero tools, explicit title instruction, 123 response blocks.
- Both currently receive the same medium-confidence request-purpose label.

## Resolution

Resolved on 2026-08-19. The classifier now searches only system/message
instruction content and requires title-generation requests to have no tools.
Captured events 344 and 345 now classify as unclassified and likely internal
title generation, respectively.
