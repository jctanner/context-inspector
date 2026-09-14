# Sourced by run.sh after agent_env/mounts and agent_command are initialized.
# No credentials, persistent settings writes, or host tracking URL forwarding.
configure_claude_tracing() {
    tracing_args=()
    agent_env+=(--env MLFLOW_CLAUDE_TRACING_ENABLED=false)
    local tracking_container=${CONTEXT_INSPECTOR_MLFLOW_CONTAINER:-}
    local experiment_id=${CONTEXT_INSPECTOR_MLFLOW_EXPERIMENT_ID:-}
    if [[ -z ${tracking_container} || ${agent_command##*/} != claude ]]; then
        return
    fi
    if [[ ! ${tracking_container} =~ ^context-inspector-mlflow-[a-f0-9]{32}$ || ! ${experiment_id} =~ ^[0-9]+$ ]]; then
        echo "ERROR: invalid stack-owned MLflow endpoint or experiment ID" >&2
        return 1
    fi
    local plugin_root="${runtime_dir}/mlflow/node_modules/@mlflow/claude-code"
    if [[ ! -f ${plugin_root}/bundle/stop.cjs || ! -f ${plugin_root}/.claude-plugin/plugin.json ]]; then
        echo "ERROR: MLflow plugin missing; run npm --prefix src/runtime/mlflow ci --ignore-scripts" >&2
        return 1
    fi
    mounts+=(--volume "${plugin_root}:/opt/context-inspector/mlflow:ro,z")
    mounts+=(--volume "${runtime_dir}/mlflow/plugin:/opt/context-inspector/mlflow-plugin:ro,z")
    agent_env+=(
        --env MLFLOW_CLAUDE_TRACING_ENABLED=true
        --env "MLFLOW_TRACKING_URI=http://${tracking_container}:5000"
        --env "MLFLOW_EXPERIMENT_ID=${experiment_id}"
        --env MLFLOW_EXPERIMENT_NAME=
        --env MLFLOW_TRACE_LOCATION=
        --env MLFLOW_WORKSPACE=
        --env MLFLOW_MODEL_CATALOG_URI=
        --env "NO_PROXY=localhost,127.0.0.1,${proxy_name},${tracking_container}"
        --env "no_proxy=localhost,127.0.0.1,${proxy_name},${tracking_container}"
    )
    tracing_args=(--plugin-dir /opt/context-inspector/mlflow-plugin)
    echo "MLflow tracing: enabled for completed Claude turns (experiment ${experiment_id})"
}
