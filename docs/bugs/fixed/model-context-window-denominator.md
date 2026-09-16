# Context meter uses 200K for Sonnet 5

Observed 2026-09-15: active session usage summary reports 289,588 input tokens,
context_window_tokens=200000, source="configured default from experiment
baseline", percent=100. Claude /context reportedly shows roughly 30%.

Sonnet 5 has a documented 1M-token context window:
https://platform.claude.com/docs/en/docs/about-claude/models/whats-new-sonnet-5
289,588 / 1,000,000 is 28.9588%, consistent with that display.

Settings defaults to 200K independently of selected model; ContextEventStream
uses that denominator and clamps percent at 100. The new session model picker
does not update context-window accounting. Response usage is wire-observed;
the default denominator is configuration, not wire evidence.

Fix should select a model-aware denominator (including per-session selection
and captured model changes), preserve explicit user overrides, and identify
fallback/unknown limits honestly.

Fixed by task 070: shared per-flow resolver in both usage paths, explicit
configuration precedence and labeled model catalog/fallback provenance.
Regression suite: 155 pass, three opt-in tests skipped. Activation awaits the
user's backend restart.
