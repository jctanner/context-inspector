# Sourced by run.sh. Keep MCP registration separate from MLflow and user settings.
configure_mcp_dump() {
    mcp_dump_args=()
    if [[ ${agent_command##*/} != claude || ${CONTEXT_INSPECTOR_MCP_DUMP_ENABLED:-1} == 0 ]]; then
        return
    fi
    mounts+=(--volume "${runtime_dir}/mcp_dump:/opt/context-inspector/mcp-dump:ro,z")
    mcp_dump_args=(--mcp-config /opt/context-inspector/mcp-dump/claude.json)
}
