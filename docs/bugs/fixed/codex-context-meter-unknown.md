# Codex context meter ignores available model metadata

Codex usage always has an unknown denominator unless explicitly configured, even
when the native model catalog supplies default window and effective percentage.
Task 085 integrates catalog evidence with explicit provenance and replay stability.

Fixed in task 085; validated by resolver/transport tests and browser replay.
