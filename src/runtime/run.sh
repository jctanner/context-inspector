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
claude_state_dir="${project_dir}/.state/claude"
claude_config_dir="${claude_state_dir}/config"
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

event_host_dir=$(dirname "${event_host_file}")
event_name=$(basename "${event_host_file}")
mkdir -p "${application_state_dir}" "${state_dir}/mitmproxy" "${capture_dir}" "${event_host_dir}"
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
for name in CLAUDE_CODE_USE_VERTEX ANTHROPIC_VERTEX_PROJECT_ID CLOUD_ML_REGION; do
    if [[ -n ${!name:-} ]]; then agent_env+=(--env "${name}=${!name}"); fi
done

adc_path=${GOOGLE_APPLICATION_CREDENTIALS:-"${HOME}/.config/gcloud/application_default_credentials.json"}
mounts=(
    --volume "${state_dir}/mitmproxy/mitmproxy-ca-cert.pem:/mitmproxy-ca-cert.pem:ro,Z"
    --volume "${PWD}:/workspace:rw,Z"
    --volume "${claude_config_dir}:/home/runner/.claude:rw,Z"
    --volume "${claude_config_file}:/home/runner/.claude.json:rw,Z"
)
if [[ -f ${adc_path} ]]; then
    adc_copy="${state_dir}/adc.json"
    cp "${adc_path}" "${adc_copy}"
    chmod 644 "${adc_copy}"
    mounts+=(--volume "${adc_copy}:/tmp/adc.json:ro,Z" --env GOOGLE_APPLICATION_CREDENTIALS=/tmp/adc.json)
fi

podman run --rm --network "${network_name}" --userns=keep-id:uid=1000,gid=1000 "${agent_env[@]}" \
    --volume "${state_dir}/mitmproxy/mitmproxy-ca-cert.pem:/mitmproxy-ca-cert.pem:ro,Z" \
    --entrypoint curl "${agent_image}" --fail --silent --show-error --output /dev/null \
    --retry 10 --retry-delay 1 --retry-connrefused \
    --cacert /mitmproxy-ca-cert.pem https://www.googleapis.com/discovery/v1/apis

agent_command=$1
shift
podman run --rm -it --network "${network_name}" --userns=keep-id:uid=1000,gid=1000 --workdir /workspace \
    --entrypoint "${agent_command}" "${agent_env[@]}" "${mounts[@]}" "${agent_image}" "$@"

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
