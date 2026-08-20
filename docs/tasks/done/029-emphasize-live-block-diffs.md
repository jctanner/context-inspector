# Task: Emphasize Live Block Diffs

## Goal

Make the README introduction immediately explain the primary user experience:
turn-by-turn, block-by-block context changes beside the live Claude console.

## Acceptance criteria

- [x] The opening description names added, removed, transformed, and retained
  request-context blocks.
- [x] It explains that each captured model call gains its correlated response
  and usage after completion.
- [x] It distinguishes model calls from user turns because one turn may produce
  auxiliary calls.
- [x] README regression test passes.

## Status

Complete

## Validation

- The primary behavior appears before the architecture section.
- Both focused README regression tests and `git diff --check` pass.
