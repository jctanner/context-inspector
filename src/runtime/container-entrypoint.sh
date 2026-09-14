#!/usr/bin/env bash
# Invoked by bash inside the agent image, never on the host.
set -euo pipefail

if [[ ! -f /run/.containerenv && ! -f /.dockerenv ]]; then
    echo "ERROR: trust bootstrap must run inside a container" >&2
    exit 1
fi
if [[ $(id -u) != 0 ]]; then
    echo "ERROR: trust bootstrap requires container root" >&2
    exit 1
fi
if (( $# == 0 )); then
    echo "ERROR: trust bootstrap requires an agent command" >&2
    exit 1
fi
for command in update-ca-certificates setpriv getent install; do
    if ! command -v "${command}" >/dev/null; then
        echo "ERROR: agent image must provide ${command}" >&2
        exit 1
    fi
done
if [[ ! -s /mitmproxy-ca-cert.pem ]]; then
    echo "ERROR: mounted proxy CA is missing or empty" >&2
    exit 1
fi
agent_record=$(getent passwd 1000)
IFS=: read -r agent_user _ agent_uid agent_gid _ agent_home _ <<<"${agent_record}"
if [[ ${agent_uid} != 1000 || ${agent_gid} != 1000 || -z ${agent_home} ]]; then
    echo "ERROR: agent image must provide a UID/GID 1000 account with a home directory" >&2
    exit 1
fi
if [[ ${agent_home} != /home/evaluator ]]; then
    echo "ERROR: agent image home must be /home/evaluator to match the persistent mounts" >&2
    exit 1
fi

# Only the container writable layer is changed. Keep all existing system roots.
install -m 0644 /mitmproxy-ca-cert.pem /usr/local/share/ca-certificates/context-inspector-proxy.crt
update-ca-certificates >/dev/null

if [[ ${1##*/} == claude && ${MLFLOW_CLAUDE_TRACING_ENABLED:-false} == true ]]; then
    if ! command -v node >/dev/null || ! command -v timeout >/dev/null; then
        echo "ERROR: Claude tracing requires the stack's Node-enabled agent image" >&2
        exit 1
    fi
    if ! curl --fail --silent --show-error --output /dev/null --connect-timeout 3 --max-time 5 \
        "${MLFLOW_TRACKING_URI:?MLFLOW_TRACKING_URI is required}/health"; then
        echo "ERROR: agent cannot reach the stack's MLflow server" >&2
        exit 1
    fi
fi

# Preserve the image PATH and provider/proxy environment, but restore the agent
# account's home after Podman started the bootstrap as root. Never run Claude as root.
exec setpriv --reuid=1000 --regid=1000 --clear-groups --no-new-privs \
    env "HOME=${agent_home}" "USER=${agent_user}" "LOGNAME=${agent_user}" "$@"
