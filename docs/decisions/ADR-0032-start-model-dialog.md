# ADR-0032: Per-session model selection

## Status

Accepted.

## Decision

Use native dialog/select controls before creating a Claude session. Always
default the UI to claude-haiku-4-5; also offer the exact user-requested
claude-sonnet-5, claude-sonnet-4-6 (task 072), and claude-opus-4-6 identifiers. POST an optional validated model
field; explicit selection affects only the new argv, never persisted settings
or an existing shared session. Requests omitting the field keep configured
model behavior. Explicit model selection is unavailable in command-override
fixtures; reject competing extra_args model flags when selection is supplied.

## Consequences

Task 073: expose optional `selected_model` in creation, active discovery and
session status, read from the actual session argv rather than a browser's picker
or current global default. Show it in the connected label with launch-provenance
tooltip. Missing metadata omits the model; /model routing changes are not inferred.

Cancel/Escape do not launch anything. Pending submit disables duplicate starts
and cancellation; failures remain visible for retry. Reconnect and automatic
shared-session discovery bypass selection because they do not create a new
session. Provider availability/errors remain Claude's responsibility; do not
silently substitute other models. User restart activates the backend field.
