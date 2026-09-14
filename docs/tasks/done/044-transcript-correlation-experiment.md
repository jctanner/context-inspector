# Task: Test transcript-to-wire correlation

## Acceptance criteria

- [x] Inspect existing main/subagent transcript identifiers without changing Claude.
- [x] Measure exact joins against current-session captures; inspect the foo baseline.
- [x] Distinguish confirmed matches, ambiguity, and unmatched traffic; absence is not
  proof of helper purpose. No timing-only primary/subagent attribution.
- [x] Record reproducible diagnostic code and aggregate results without raw prompts,
  source content, credentials, or transcript fixtures. No MLflow installation.

## Results and verification

See docs/notes/transcript-correlation-experiment.md. All 64 distinct main-transcript
assistant responses join captured requests by both message ID and request-id.
130 total requests include 27 explicit token-count calls; the five foo requests
are among them. Request 130 is main-correlated but incorrectly uses token-count
request 128 as baseline. Recorded token-count-baseline-contamination bug.

Read-only diagnostic ran three times with stable aggregate results. Three unit
tests pass (duplicate records, exact joins, conflicting/ambiguous identifiers).
Diff whitespace check passes. No subagent transcript exists in this session:
real subagent correlation is a follow-up, not an outcome claimed by this task.
