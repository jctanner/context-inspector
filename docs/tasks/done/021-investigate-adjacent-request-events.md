# Task: Investigate Adjacent Request Events

## Goal

Explain the observed difference between capture events 344 and 345 using the
exact retained wire evidence.

## Acceptance criteria

- [x] Identify each request's purpose from exact request fields.
- [x] Compare tool and response-transport shapes.
- [x] Record any newly discovered defect.

## Findings

- Event 344 is the main agent request containing the user's story prompt. It
  exposes 27 tools and produced 1,484 captured response transport blocks.
- Event 345 is an auxiliary conversation-title request. It exposes no tools,
  contains an explicit title instruction, and produced 123 response blocks.
- Both were started consecutively before their streamed responses completed.
- The request-time title classifier incorrectly marks event 344 as title
  generation because it searches all payload strings, including tool schemas.

## Validation

Read-only inspection of the newest session's exact `request.started`,
`response.started`, `response.block`, and `flow.completed` events.

## Status

Complete
