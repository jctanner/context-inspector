# Bug: Chronological fallback pairs unrelated blocks as transformations

## Evidence

Request 130 (flow e14fb5d6-d42f-44ae-8fa4-db34ff2602e1) compares against flow
00476479-3dae-4ce4-8c92-6fd5259001c0 under session_chronology_unclassified, with
no attribution confidence. Baseline has one message containing foo, no system
blocks and one tool. Current request has nine messages, three system blocks and
27 tools. A shared session hint is not stable agent-stream identity.

compare_snapshots pairs unmatched blocks at messages/0/0 as transformed solely
by path: unclassified user text becomes a harness-classified system reminder.
There is no evidence this is an edit to the same logical block. The tiny request
may be an internal probe, but its purpose is not established from this evidence.

## Expected

Avoid presenting same-position blocks as confirmed edits across incompatible
contexts/origins. Strengthen predecessor selection with explicitly uncertain
classification where appropriate, and block correspondence independently. Keep
raw requests available; do not silently rewrite evidence or assert agent identity.
Diagnosis only; no implementation change yet.

Task 045 adds role/category/kind/origin compatibility before positional
transformation, plus API-operation isolation. Offline replay removes request 130's
bad match. Broader semantic correspondence and transcript attribution remain
follow-up work; new code is not deployed to the running server yet.
