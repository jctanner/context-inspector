# Task: Initialize Standalone Repository

## Goal

Turn Context Inspector into a standalone Git repository and publish its initial
source history to `jctanner/context-inspector`.

## Acceptance criteria

- [x] Runtime state, captures, credentials, dependencies, caches, and build
  output are excluded by `.gitignore`.
- [x] The initial staged tree contains only intended project source and records.
- [x] The repository uses the `main` branch.
- [x] `origin` points to `git@github.com:jctanner/context-inspector.git`.
- [x] The initial commit is pushed and tracks `origin/main`.

## Status

Complete

## Validation

- Root commit `687c5d5` is present on `main` and `origin/main`.
- The nested repository has the requested SSH origin.
- The staged-tree review found no ignored runtime, capture, credential,
  dependency, cache, or build paths.
