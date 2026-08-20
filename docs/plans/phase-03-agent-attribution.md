# Phase 3: Agent-Stream Attribution

## Goal

Group model calls into primary, subagent, forked-skill, and unknown streams
without presenting heuristic inference as wire-observed fact.

## Investigation inputs

- stable identifiers or metadata in captured requests;
- message-prefix ancestry;
- system-prompt and tool-set fingerprints;
- delegation tool calls and their returned identifiers;
- timing and request ordering;
- parent delegation text appearing in fresh worker histories;
- compaction and retry relationships.

## Exit criteria

- Every assignment records its evidence and confidence.
- Requests that cannot be classified remain visibly unclassified.
- Users can inspect and override inferred grouping.
- Known Phase 1–4 subagent captures form a regression corpus after sanitization.
