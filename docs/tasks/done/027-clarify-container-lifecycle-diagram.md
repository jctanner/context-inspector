# Task: Clarify Container Lifecycle Diagram

## Goal

Make the README diagram distinguish runtime orchestration from actual Podman
container ownership and execution.

## Acceptance criteria

- [x] The runner is labeled as an orchestration script, not a container owner.
- [x] Podman is explicitly shown as the component running both containers.
- [x] The foreground agent lifecycle and detached proxy cleanup differ clearly.
- [x] README regression test passes.

## Status

Complete

## Validation

- Diagram arrows match the foreground agent `podman run`, detached proxy
  `podman run`, and runner exit-trap cleanup behavior.
- The focused README regression test and `git diff --check` pass.
