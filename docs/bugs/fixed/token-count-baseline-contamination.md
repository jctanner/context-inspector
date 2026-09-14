# Bug: Token-count API calls contaminate model-context history

## Evidence

The foo baseline for request 130, request 128, targets the captured endpoint
suffix count-tokens:rawPredict. Request 130 targets claude-haiku-4-5:streamRawPredict.
normalize_request admits requests containing messages/system/tools without first
distinguishing token counting from generation. They share an unclassified lineage.

## Impact and expected behavior

The context pane can report unrelated token-count inputs as conversation edits.
Classify API operation from captured method/URL before selecting model-generation
baselines. Retain token-count wire evidence as ancillary traffic, but never let
it replace a generation baseline. This operation evidence is stronger than a
heuristic based on tiny prompt text. Identified during task 044; not fixed yet.

Task 045 fixes operation separation in code; replay validates request 130 against
93 instead of 128. Awaiting deployment; live server remains unchanged.

Deployment confirmed after user's restart: new-session generation requests #19
and #25 skip token-count requests #18 and #24 respectively. Resolved.
