# ADR-0033 — Model-aware context-window denominator

## Status

Accepted, 2026-09-15.

## Decision

Resolve limits per exact request flow in both decoded and reassembled SSE paths.
Explicit configured windows win, including an explicit 200K. Otherwise use the
request body model, then provider URL model, then launch model only if absent.
Never substitute the launch model for an unknown captured model. Unknown models
retain the baseline 200K with an explicit unverified-fallback label.

The bounded catalog covers the session-picker models, with dated/provider
ID normalization. Sources identify catalog inference separately from observed
usage. No live API lookup or inference from token volume is used. Model switches
and interleaved helper responses cannot overwrite another flow's denominator.

## Evidence and consequences

Task 072 adds Sonnet 4.6 with the user-specified 200K deployment default.
Sonnet 5 remains the only selectable model assigned 1M by default.

Task 071 amendment: the user specifies Opus 4.6 at 200K for this stack. Use
200K for Opus and Haiku and 1M only for Sonnet 5. Label the values as deployment
model defaults, not universal model capabilities. The original documentation
lookup below does not establish this installation's enabled Opus window.

[Anthropic context windows](https://platform.claude.com/docs/en/build-with-claude/context-windows)
documents Haiku 4.5 at 200K and Sonnet 5 / Opus 4.6 at 1M (checked 2026-09-15).
Catalog defaults cannot establish account-specific restrictions; deployments
with a different enabled window must set the existing environment override.
Future models require catalog maintenance. Wire input usage remains unchanged;
this is not a recreation of every category in Claude's local /context display.
