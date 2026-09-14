# ADR-0027: Standalone random skill generator

## Status

Accepted.

## Context and decision

The user explicitly requested `scripts/skill-maker.py` (renamed from `script/`
in task 062), an exception to the usual
src-only executable layout. Keep this standard-library-only experiment utility
at that path, with tests under src/tests. Never run it automatically at startup.

Random words belong in the advertised description as well as the skill body.
Use bounded descriptions, optional reproducible seeds, and exclusive creation
without replacement or cleanup of existing skills.

## Consequences

The default ignored container workspace holds generated data, not source.
Actual token inclusion remains subject to Claude's discovery and description
budgets; generation is not evidence that all descriptions reached the model.

Task 063 changes size control from body word count to uniformly random total
file lengths (500–5,000 inclusive by default), counting the nine header lines.
Each remaining line contains 20 random words by default. Seeded randomness
controls both lengths and content; line-by-line writes avoid buffering a batch.
