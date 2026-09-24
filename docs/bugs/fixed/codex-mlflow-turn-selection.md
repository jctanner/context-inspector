# Codex MLflow notify transcript selection and usage

Upstream @mlflow/codex 0.4.0 processNotify reads getLastTurnRecords regardless of callback turn-id. A delayed callback after the next task_started can attach the wrong tool records. getTokenUsage returns the last last_token_usage counter (one model call), not an aggregate of a tool-loop turn. Verified in the local MLflow checkout. Task 092 will scope transcript input by native turn ID and normalize usage from cumulative counter deltas; omit usage when unavailable. Upstream package will remain unmodified.

Published npm 0.4.0 also ignores CODEX_HOME during transcript discovery, unlike the current checkout. Export snapshot sets both HOME and CODEX_HOME so discovery cannot fall back to unrelated real transcripts.

Initial native test sees callbacks but zero traces. Explicit synchronous export did not fix it; async export was a hypothesis, not the cause (core defaults to synchronous). Investigation continues.

Root cause of missing test callbacks: installed Codex 0.156.1 ignored the root-level notify override for `codex exec` while retaining the user config callback. Inserting the override immediately after `exec` makes native callbacks reach the adapter; exports are now created. Tests must also set the global Python MLflow tracking URI before loading mlflow-artifacts (client URI alone is insufficient).

## Resolution
Mitigated in task 092 without modifying upstream: exact-ID scoped snapshots,
conservative cumulative usage deltas, private HOME/CODEX_HOME for published package,
and native-tested override placement for interactive/exec/resume. Explicit
synchronous export plus delivery-error detection and shutdown draining are verified.
Native tests and regression suite pass.
