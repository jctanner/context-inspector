#!/usr/bin/env bash
# Keep tracing failures and slow exports from blocking Claude indefinitely.
if [[ ${MLFLOW_CLAUDE_TRACING_ENABLED:-false} != true ]]; then
    exit 0
fi
timeout --signal=TERM --kill-after=5s 30s node /opt/context-inspector/mlflow/bundle/stop.cjs
status=$?
if (( status != 0 )); then
    echo "[context-inspector] MLflow hook failed or timed out (exit ${status}); this turn's trace may be missing." >&2
fi
exit 0
