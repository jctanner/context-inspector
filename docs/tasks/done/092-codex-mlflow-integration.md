# Codex MLflow integration

## Goal
Enable opt-in stack-owned MLflow turn tracing for Codex OAuth using @mlflow/codex, preserving native auth and independent wire captures.

## Acceptance criteria
- [x] Package installed with existing MLflow runtime dependencies; only inspector launches configured.
- [x] Native thread/turn IDs select the correct transcript slice, including delayed callbacks; usage is per turn or omitted when unverified.
- [x] Existing notify behavior preserved, exporter errors bounded and private; normal shutdown drains exports.
- [x] Synthetic tests and isolated container/native callback plus MLflow delivery validation; no main stack restart.
- [x] Capabilities, documentation, ADR and ledger reflect evidence and limitations.

## Discoveries
Source review found upstream selects latest turn rather than callback ID and labels last request usage as root usage. Adapter must scope transcript and usage before export. Interrupted turns without a completion notification must not be invented as completed traces.


## Implementation
- Locked @mlflow/codex and @mlflow/core 0.4.0 installed alongside Claude tracing;
  startup verifies all package versions/entrypoints. Read-only runtime assets,
  per-launch injection, private stack MLflow endpoint; OAuth/provider/proxy unchanged.
- Python supervisor receives atomic, deduplicated native notify jobs. Exact-ID
  snapshot selection avoids latest-turn races; cumulative counter delta supplies
  per-turn usage only with a verified baseline. Node invokes unmodified upstream
  exporter with captured IDs/source and explicitly reconstructed evidence metadata.
- Existing inspector user-layer notify is chained. Competing CLI/project notify
  overrides fail with an actionable message; host config is never modified.
- Export children isolated from terminal signals; 20-second export deadline,
  35-second shutdown drain, 40-second Inspector Stop allowance. Errors private,
  CLI exit preserved. Completed exports/errors in .codex/mlflow-tracing.log (0600).
- Native title-generation callbacks keep their own thread/turn IDs. No automatic
  primary/subagent or wire-span attribution. No completion trace invented for an
  interrupted turn; no durable retry on forced container removal.

## Validation (2026-09-24)
- Full regression: 238 tests run, seven opt-in skips, all others pass.
- Separate opt-in native Codex and Claude MLflow tests: two tests passed (34.9s).
  Installed image: Codex 0.156.1 / Claude 2.1.281. Local fixture model, fresh homes,
  real MLflow v3.16.0 on isolated loopback ports/private networks; no credentials.
- Codex exec + resume: two turns under one native thread, distinct turn metadata,
  real exec_command tool result, root usage 20 then 10 input tokens (not cumulative
  30 nor last-call 10 for the first tool-loop turn). Native interactive --no-daemon
  prompt and /exit also export successfully; auxiliary title callback separate.
- Third interrupted exec produced no completed trace. Existing callback invoked
  once per completed native notification. All completed callbacks exported before
  container removal. Claude real Stop/Read and synthetic nested-child test pass.
- Focused tests cover delayed/missing/reset/resumed counters, model changes,
  duplicates, private files, disabled launch, config preservation/conflicts,
  exporter timeout, expired drain deadline, and CLI exit 7 after exporter failure.
- PTY regression proves traced-session Stop permits export completion beyond
  the old three-second timeout. Shell syntax and git diff --check pass.

## Deployment
Complete, awaiting normal user-managed restart/new Codex session. Existing stack
and sessions untouched. MLflow must remain enabled; restarting resets its existing
ephemeral data as before. No new login required. See ADR-0044 and README.
