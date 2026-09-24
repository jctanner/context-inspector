# Task 081: Implement OAuth and Codex safe foundations

## Goal

Implement the phase-04 work that is safe without assuming a credential sharing
mechanism or Codex transport that has not been verified.

## Acceptance criteria

- [x] Credential files are denied by the backend Claude browser.
- [x] Model capture excludes auth/token traffic before body/url persistence.
- [x] Existing Claude Vertex model calls remain captured; unknown providers fail closed.
- [x] Add/reuse tests with synthetic sentinels only.
- [x] Assess available host credential concurrency evidence safely; do not read secrets.
- [x] Keep OAuth/Codex launch unavailable unless concurrency and wire inspection pass.
- [x] Update plan, ADR, task, notes and PLAN with implemented scope and blockers.

## Findings

The current proxy broad host regex selects any HTTP URL under Anthropic/Google
hosts and archives bodies. The Claude files handler shares the generic reader,
which exposes hidden files. CLI credential files exist on host according to prior
metadata-only inspection; effective storage/auth type and safe concurrent refresh
remain unverified.

## Status

Done. The auth and Codex launch gates remain tracked in task 082.

## Results and verification

- Claude workspace file listing hides `.credentials.json`, and direct reads return
  a non-disclosing 404. Synthetic tests cover nested listings and direct access.
- Proxy admission is restricted to known Anthropic message/token-count and
  Vertex prediction/token-count POST paths. Credential query parameters,
  user-info, OAuth paths and unknown operations are rejected before body capture.
- Existing Anthropic and Vertex selection paths remain covered by fixtures;
  synthetic OAuth sentinels do not appear in events or archives.
- Available evidence was reviewed without opening credential contents. User
  login status and tagged Codex source do not prove cross-process refresh safety;
  task 082 retains that gate.
- Six focused capture tests pass. Python compilation and `git diff --check` pass.
  No credentials were read, copied or mounted; no login, model call, container
  or stack restart was performed.
