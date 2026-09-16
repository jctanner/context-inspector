#!/usr/bin/env bash
# Sourced by run.sh after MLflow/MCP configuration; no live process attachment.
configure_strace() {
    strace_options=()
    if [[ ${agent_command##*/} != claude || ${CONTEXT_INSPECTOR_STRACE_ENABLED:-1} == 0 ]]; then
        return
    fi
    local trace_dir="${project_dir}/container/strace"
    if [[ -L ${project_dir}/container || -L ${trace_dir} ]]; then
        echo "ERROR: strace output directory must not be a symlink" >&2
        return 1
    fi
    (umask 077; mkdir -p "${trace_dir}")
    chmod 700 "${trace_dir}"
    local base_id digest trace_image
    base_id=$(podman image inspect --format '{{.Id}}' "${agent_image}")
    digest=$( { printf '%s\n' "${base_id}"; cat "${runtime_dir}/strace/image/Containerfile"; } | sha256sum)
    trace_image="localhost/context-inspector-claude-strace:${digest:0:20}"
    if ! podman image exists "${trace_image}"; then
        echo "Building Claude strace image (base image unchanged)…" >&2
        podman build --build-arg "BASE_IMAGE=${agent_image}" --tag "${trace_image}" "${runtime_dir}/strace/image"
    fi
    agent_image=${trace_image}
    mounts+=(--volume "${trace_dir}:/strace:rw,Z")
    strace_options=(--cap-add SYS_PTRACE --env CONTEXT_INSPECTOR_STRACE_ENABLED=1)
    echo "Claude syscall trace: ${trace_dir}/pid.* (append mode; sensitive data)" >&2
}
