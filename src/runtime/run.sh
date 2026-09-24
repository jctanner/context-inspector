#!/usr/bin/env bash
set -euo pipefail

runtime_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
project_dir=$(cd "${runtime_dir}/../.." && pwd)
session_id=${CONTEXT_INSPECTOR_SESSION_ID:?CONTEXT_INSPECTOR_SESSION_ID is required}
event_host_file=${CONTEXT_INSPECTOR_EVENT_FILE:?CONTEXT_INSPECTOR_EVENT_FILE is required}
session_slug=${session_id//[^a-zA-Z0-9_.-]/-}
application_state_dir=${CONTEXT_INSPECTOR_STATE_DIR:-"/tmp/context-inspector-$(id -u)"}
state_dir=${CONTEXT_INSPECTOR_RUNTIME_STATE_DIR:-"${application_state_dir}/runtime"}
capture_dir=${CONTEXT_INSPECTOR_CAPTURE_DIR:-"${application_state_dir}/captures"}
claude_state_dir="${project_dir}/container/home/evaluator"
claude_config_dir="${claude_state_dir}/.claude"
claude_config_file="${claude_state_dir}/.claude.json"
run_id="$(date -u +%Y%m%dT%H%M%SZ)-${session_slug}"
capture_name="flows-${run_id}.jsonl"
proxy_log_name="mitmproxy-${run_id}.log"
proxy_image=${MITM_PROXY_IMAGE:-docker.io/mitmproxy/mitmproxy:12.1.2}
agent_image=${AGENT_IMAGE:-localhost/claude-task-runner:latest}
network_name=${MITM_NETWORK_NAME:-agent-mitm-network}
proxy_name="context-inspector-proxy-${session_slug:0:32}"
proxy_port=${MITM_PROXY_PORT:-8080}

if [[ ${1:-} != "--" ]] || (( $# < 2 )); then
    echo "usage: $0 -- AGENT_COMMAND [ARG ...]" >&2
    exit 2
fi
shift

harness=${CONTEXT_INSPECTOR_HARNESS:-claude}
auth_mode=${CONTEXT_INSPECTOR_AUTH_MODE:-vertex}
oauth_mounts=()
oauth_security=()
auth_watch_pid=
agent_name="context-inspector-agent-${session_slug:0:32}"
case "${harness}:${auth_mode}" in
    claude:vertex) ;;
    codex:oauth)
        if [[ ${1:-} != codex ]]; then
            echo "ERROR: Codex profile requires the codex command" >&2
            exit 2
        fi
        # This reads native auth internally, prints metadata only, and creates no state.
        oauth_preflight=$("${project_dir}/.venv/bin/python" "${runtime_dir}/oauth.py")
        mapfile -t oauth_fields <<<"${oauth_preflight}"
        host_auth_file=${oauth_fields[0]}
        host_auth_identity=${oauth_fields[1]}
        codex_state_dir="${claude_state_dir}/.codex"
        # Do not relabel host credentials with :Z.
        oauth_security=(--security-opt label=disable)
        oauth_mounts=(--volume "${host_auth_file}:/home/evaluator/.codex/auth.json:rw")
        ;;
    claude:oauth)
        if [[ ${1:-} != claude ]]; then
            echo "ERROR: Claude profile requires the claude command" >&2
            exit 2
        fi
        oauth_preflight=$("${project_dir}/.venv/bin/python" "${runtime_dir}/oauth.py" claude)
        mapfile -t oauth_fields <<<"${oauth_preflight}"
        host_auth_file=${oauth_fields[0]}
        host_auth_identity=${oauth_fields[1]}
        if [[ ${host_auth_file} == "${claude_config_dir}" ]]; then
            echo "ERROR: host credentials and inspector-owned Claude configuration must use distinct directories" >&2
            exit 2
        fi
        oauth_security=(--security-opt label=disable)
        oauth_mounts=(--volume "${host_auth_file}:/host-claude-auth:rw")
        ;;
    *)
        echo "ERROR: unsupported or unvalidated harness/auth runtime" >&2
        exit 2
        ;;
esac

agent_image=$("${project_dir}/.venv/bin/python" "${runtime_dir}/harness_image.py" --base "${agent_image}")

event_host_dir=$(dirname "${event_host_file}")
event_name=$(basename "${event_host_file}")
mkdir -p "${application_state_dir}" "${state_dir}/mitmproxy" "${capture_dir}" "${event_host_dir}"
if [[ ${harness} == codex ]]; then
    if [[ -L ${codex_state_dir} ]]; then
        echo "ERROR: inspector Codex state must not be a symlink" >&2
        exit 2
    fi
    mkdir -p "${codex_state_dir}"
    chmod 700 "${codex_state_dir}"
fi
mkdir -p "${claude_config_dir}"
chmod 700 "${application_state_dir}" "${state_dir}" "${state_dir}/mitmproxy" "${capture_dir}"
chmod 700 "${claude_state_dir}" "${claude_config_dir}"
if [[ ! -s ${claude_config_file} ]]; then
    printf '{}\n' >"${claude_config_file}"
fi
chmod 600 "${claude_config_file}"
# mitmdump drops from container root to its image user after startup. The file
# must therefore be writable by that UID. The mounted leaf directory is 0733;
# the enclosing application state directory remains 0700 and is never mounted
# into the agent container.
chmod 733 "${event_host_dir}"
: >"${event_host_file}"
chmod 666 "${event_host_file}"

if ! podman network exists "${network_name}"; then
    podman network create "${network_name}" >/dev/null
fi
if [[ ! -f "${state_dir}/mitmproxy/mitmproxy-ca-cert.pem" ]]; then
    podman run --rm --user 0 \
        --volume "${state_dir}/mitmproxy:/tmp/mitmproxy:Z" \
        --entrypoint mitmdump "${proxy_image}" \
        --set confdir=/tmp/mitmproxy --commands quit >/dev/null
fi
chmod 644 "${state_dir}/mitmproxy/mitmproxy-ca-cert.pem"

podman rm -f "${proxy_name}" >/dev/null 2>&1 || true
# Do not use --rm here: if the addon crashes during startup, its stopped
# container must remain long enough for cleanup to preserve diagnostic logs.
podman run --detach --name "${proxy_name}" --network "${network_name}" --user 0 \
    --env "CAPTURE_FILE=/tmp/${capture_name}" \
    --env "CONTEXT_INSPECTOR_SESSION_ID=${session_id}" \
    --env "CONTEXT_INSPECTOR_EVENT_FILE=/events/${event_name}" \
    --volume "${state_dir}/mitmproxy:/tmp/mitmproxy:Z" \
    --volume "${event_host_dir}:/events:Z" \
    --volume "${project_dir}/src/proxy/live_capture.py:/addons/live_capture.py:ro,Z" \
    --entrypoint mitmdump "${proxy_image}" \
    --listen-host 0.0.0.0 --listen-port "${proxy_port}" \
    --set block_global=false --set confdir=/tmp/mitmproxy --scripts /addons/live_capture.py >/dev/null

cleanup() {
    if [[ -n ${auth_watch_pid} ]]; then
        kill "${auth_watch_pid}" >/dev/null 2>&1 || true
        wait "${auth_watch_pid}" 2>/dev/null || true
    fi
    podman logs "${proxy_name}" >"${capture_dir}/${proxy_log_name}" 2>&1 || true
    podman rm -f "${proxy_name}" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

ready=0
for _ in $(seq 1 60); do
    proxy_running=$(podman inspect --format '{{.State.Running}}' "${proxy_name}" 2>/dev/null || true)
    if [[ ${proxy_running} != true ]]; then
        break
    fi
    if podman exec --env "PROBE_PORT=${proxy_port}" "${proxy_name}" python -c \
        'import os, socket; connection = socket.create_connection(("127.0.0.1", int(os.environ["PROBE_PORT"])), 0.2); connection.close()' \
        >/dev/null 2>&1; then
        ready=1
        break
    fi
    sleep 0.2
done
if (( ! ready )); then
    echo "ERROR: mitmproxy did not accept connections on port ${proxy_port}" >&2
    exit 1
fi
if ! podman exec --user 1000 "${proxy_name}" test -w "/events/${event_name}"; then
    echo "ERROR: mitmproxy runtime user cannot write the live-event file" >&2
    exit 1
fi

proxy_url="http://${proxy_name}:${proxy_port}"
agent_env=(
    --env "HTTP_PROXY=${proxy_url}" --env "HTTPS_PROXY=${proxy_url}"
    --env "http_proxy=${proxy_url}" --env "https_proxy=${proxy_url}"
    --env "NO_PROXY=localhost,127.0.0.1,${proxy_name}"
    --env "no_proxy=localhost,127.0.0.1,${proxy_name}"
    --env NODE_EXTRA_CA_CERTS=/mitmproxy-ca-cert.pem
)
mounts=(
    --volume "${state_dir}/mitmproxy/mitmproxy-ca-cert.pem:/mitmproxy-ca-cert.pem:ro,Z"
    --volume "${PWD}:/workspace:rw,Z"
)
bootstrap_mount=(--volume "${runtime_dir}/container-entrypoint.sh:/context-inspector-entrypoint.sh:ro,Z")
if [[ ${auth_mode} == vertex ]]; then
    for name in CLAUDE_CODE_USE_VERTEX ANTHROPIC_VERTEX_PROJECT_ID CLOUD_ML_REGION; do
        if [[ -n ${!name:-} ]]; then agent_env+=(--env "${name}=${!name}"); fi
    done
    mounts+=(--volume "${claude_config_dir}:/home/evaluator/.claude:rw,Z"
             --volume "${claude_config_file}:/home/evaluator/.claude.json:rw,Z")
    adc_path=${GOOGLE_APPLICATION_CREDENTIALS:-"${HOME}/.config/gcloud/application_default_credentials.json"}
    if [[ -f ${adc_path} ]]; then
        adc_copy="${state_dir}/adc.json"
        cp "${adc_path}" "${adc_copy}"
        chmod 644 "${adc_copy}"
        mounts+=(--volume "${adc_copy}:/tmp/adc.json:ro,Z" --env GOOGLE_APPLICATION_CREDENTIALS=/tmp/adc.json)
    fi
else
    agent_env+=(--env CONTEXT_INSPECTOR_STRACE_ENABLED=0
                --env MLFLOW_CLAUDE_TRACING_ENABLED=false)
    if [[ ${harness} == codex ]]; then
        agent_env+=(--env CODEX_HOME=/home/evaluator/.codex
                    --env CODEX_CA_CERTIFICATE=/mitmproxy-ca-cert.pem
                    --env "CONTEXT_INSPECTOR_AUTH_INODE=${host_auth_identity##*:}")
        mounts+=(--volume "${codex_state_dir}:/home/evaluator/.codex:rw,Z")
    else
        agent_env+=(--env CLAUDE_CONFIG_DIR=/home/evaluator/.claude
                    --env CLAUDE_SECURESTORAGE_CONFIG_DIR=/host-claude-auth
                    --env "CONTEXT_INSPECTOR_CLAUDE_AUTH_INODE=${host_auth_identity##*:}"
                    --env CLAUDE_CODE_DISABLE_LEGACY_MODEL_REMAP=1)
        mounts+=(--volume "${claude_config_dir}:/home/evaluator/.claude:rw,Z"
                 --volume "${claude_config_file}:/home/evaluator/.claude.json:rw,Z")
    fi

    for name in OPENAI_API_KEY OPENAI_BASE_URL OPENAI_ORG_ID OPENAI_PROJECT_ID \
                ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN ANTHROPIC_BASE_URL CLAUDE_CODE_OAUTH_TOKEN \
                CLAUDE_CODE_OAUTH_TOKEN_FILE_DESCRIPTOR CCR_OAUTH_TOKEN_FILE \
                CLAUDE_CODE_USE_BEDROCK CLAUDE_CODE_USE_FOUNDRY \
                CLAUDE_CODE_USE_VERTEX ANTHROPIC_VERTEX_PROJECT_ID CLOUD_ML_REGION \
                GOOGLE_APPLICATION_CREDENTIALS CODEX_REFRESH_TOKEN_URL_OVERRIDE CODEX_AUTHAPI_BASE_URL; do
        agent_env+=(--unsetenv "${name}")
    done
    mounts+=("${oauth_mounts[@]}")
fi

if [[ ${auth_mode} == vertex ]]; then
podman run --rm --network "${network_name}" --userns=keep-id:uid=1000,gid=1000 --user 0 "${agent_env[@]}" \
    --volume "${state_dir}/mitmproxy/mitmproxy-ca-cert.pem:/mitmproxy-ca-cert.pem:ro,Z" \
    "${bootstrap_mount[@]}" --entrypoint bash "${agent_image}" /context-inspector-entrypoint.sh \
    curl --fail --silent --show-error --output /dev/null \
    --retry 10 --retry-delay 1 --retry-connrefused \
    https://www.googleapis.com/discovery/v1/apis

fi

agent_command=$1
if [[ ${agent_command} == claude || ${agent_command} == codex ]]; then
    agent_command="/usr/local/bin/${agent_command}"
fi
shift
tracing_args=()
mcp_dump_args=()
strace_options=()
if [[ ${auth_mode} == vertex ]]; then
    source "${runtime_dir}/mlflow-env.sh"
    configure_claude_tracing
    source "${runtime_dir}/mcp-dump-env.sh"
    configure_mcp_dump
    source "${runtime_dir}/strace-env.sh"
    configure_strace
else
    agent_command="/usr/local/bin/${harness}"
    # A file bind cannot follow host logout/login or atomic replacement. Stop
    # this inspector session if that happens; never overwrite host auth to recover.
    (
        while true; do
            current_identity=$(stat -c '%d:%i' "${host_auth_file}" 2>/dev/null || true)
            if [[ ${current_identity} != "${host_auth_identity}" ]] || { [[ ${harness} == claude ]] && [[ ! -f ${host_auth_file}/.credentials.json ]]; }; then
                echo "ERROR: host credential mount was replaced or removed; restart this inspector session" >&2
                # The replacement may precede podman run. Keep trying until
                # the named session exists or the parent's cleanup stops us.
                until podman stop --time 2 "${agent_name}" >/dev/null 2>&1; do
                    sleep 0.2
                done
                exit
            fi
            sleep 0.5
        done
    ) &
    auth_watch_pid=$!
fi
set -- "${tracing_args[@]}" "${mcp_dump_args[@]}" "$@"
agent_exit=0
podman run --rm -it --name "${agent_name}" --network "${network_name}" --userns=keep-id:uid=1000,gid=1000 --user 0 --workdir /workspace \
    --entrypoint bash "${agent_env[@]}" "${mounts[@]}" "${bootstrap_mount[@]}" "${strace_options[@]}" "${oauth_security[@]}" "${agent_image}" \
    /context-inspector-entrypoint.sh "${agent_command}" "$@" || agent_exit=$?

if ! podman cp "${proxy_name}:/tmp/${capture_name}" "${capture_dir}/${capture_name}"; then
    : >"${capture_dir}/${capture_name}"
fi
chmod 600 "${capture_dir}/${capture_name}"
flow_count=$(wc -l <"${capture_dir}/${capture_name}")
echo "Capture: ${capture_dir}/${capture_name} (${flow_count} completed flows)"
if (( flow_count == 0 )); then
    echo "WARNING: agent completed but no matching model traffic crossed the proxy." >&2
    echo "Proxy log: ${capture_dir}/${proxy_log_name}" >&2
fi
exit "${agent_exit}"
