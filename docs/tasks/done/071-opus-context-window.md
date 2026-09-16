# Task: Correct this stack's Opus context window

Implementation authorized by the user's correction.

- [x] Set Opus 4.6 to 200K; retain Sonnet 5 at 1M and Haiku at 200K.
- [x] Update provenance and documentation to distinguish deployment defaults
  from advertised model capabilities.
- [x] Verify canonical/provider IDs and usage percentages.

User clarified that Opus runs with 200K in this stack. Task 070 incorrectly
applied the advertised larger window to the deployment.

Validation: 23 focused context tests pass; `git diff --check` passes. Opus 60K
input tokens now yields 30%, with explicit 1M override still yielding 6%.
User-managed backend restart required; no stack restart performed.
