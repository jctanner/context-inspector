# Task 080: Plan OAuth authentication and Codex harness support

## Goal

Inspect the existing project and verified upstream documentation, then write a
reviewable enhancement plan under docs/plans. Planning only; no runtime changes.

## Acceptance criteria

- [x] Map current launch, credentials, capture, interpretation, and UI coupling.
- [x] Distinguish verified support, proposals, and unresolved validation gates.
- [x] Ask the user about credential workflow and Codex inspection expectations.
- [x] Document phased changes, tests, risks, and implementation dependencies.
- [x] Update the ledger, session log, and a proposed architectural decision.

## Notes

- Initial inspection: run.sh passes Vertex variables and mounts ADC, config.py
  builds Claude-only commands, and the start dialog only chooses a Claude model.
- Existing untracked checkouts/ and demo-script.md are outside this task.

## Results and verification

- Wrote [the plan](../../plans/phase-04-oauth-and-codex.md) and proposed ADR-0039.
- User confirmed Linux host-login reuse, concurrent host CLI use, and mandatory
  Codex capture/inspection at launch. Effective credential store is unverified.
- Metadata-only checks found both candidate credential files, regular and 0600;
  did not read credential contents or verify account entitlement.
- Verified official Claude/Codex docs and local Codex 0.156.0 help. No assumption
  that host CLI version equals the agent image version.
- Synthetic temporary fixtures reproduced credential-file browsing and OAuth
  request-body persistence; recorded both defects immediately. Initial capture
  fixture used a plain dict instead of mitmproxy's headers interface; corrected
  fixture reproduced the issue. No runtime defect inferred from that fixture error.
- Cross-checked launch/config, cleanup, proxy/protocol, interpreter, UI, optional
  integrations, tests and existing ADRs. Plan includes phased acceptance gates.
- Documentation link and whitespace checks passed. No runtime suite run: only
  documentation changed, and no live stack/model/login operations performed.
