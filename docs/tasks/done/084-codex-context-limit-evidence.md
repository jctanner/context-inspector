# Task 084: Establish Codex context-limit evidence

## Goal

Identify model context budgets from native metadata and inspector-session evidence,
distinguishing defaults, maximum windows and compaction thresholds. Determine a
trustworthy source for the inspector meter without guessing limits.

## Acceptance criteria

- [x] Inspect official context configuration guidance and native model metadata.
- [x] Compare inspector-owned runtime evidence without exposing prompts/tokens.
- [x] Record findings and appropriate display semantics with explicit limits.

## Result

[Evidence and display semantics](../../notes/codex-context-limits.md) recorded.
Two inspector gpt-6-luna sessions report 258400. Both model caches list 272000
default and 95 percent effective capacity for all seven visible models; maximums
are distinct. Official configuration guidance distinguishes compaction threshold
from window size. Read-only validation; no model calls or active-session changes.
Application integration is not part of this evidence-only task.
