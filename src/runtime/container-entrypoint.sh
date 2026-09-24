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

if [[ ${1##*/} == codex ]]; then
    if ! setpriv --reuid=1000 --regid=1000 --clear-groups --no-new-privs \
        /usr/local/bin/codex-code-mode-host --help >/dev/null; then
        echo "ERROR: Codex workspace execution helper cannot start" >&2
        exit 1
    fi
    if [[ ${CONTEXT_INSPECTOR_AUTH_INODE:-} != "$(stat -c '%i' /home/evaluator/.codex/auth.json 2>/dev/null)" ]]; then
        echo "ERROR: host Codex credentials changed during container startup; retry launch" >&2
        exit 1
    fi
fi

if [[ ${1##*/} == claude && -n ${CONTEXT_INSPECTOR_CLAUDE_AUTH_INODE:-} ]]; then
    if [[ ${CONTEXT_INSPECTOR_CLAUDE_AUTH_INODE} != "$(stat -c '%i' /host-claude-auth 2>/dev/null)" ]]; then
        echo "ERROR: host Claude credential directory changed during startup; retry launch" >&2
        exit 1
    fi
fi

# Resolve from the image PATH and record actual installed versions, never pins.
if [[ ${1##*/} == claude || ${1##*/} == codex ]]; then
    setpriv --reuid=1000 --regid=1000 --clear-groups --no-new-privs \
        env "HOME=${agent_home}" "USER=${agent_user}" "LOGNAME=${agent_user}" "$1" --version
    setpriv --reuid=1000 --regid=1000 --clear-groups --no-new-privs \
        env "HOME=${agent_home}" "USER=${agent_user}" "LOGNAME=${agent_user}" "$1" --help >/dev/null
fi

# Only the container writable layer is changed. Keep all existing system roots.
install -m 0644 /mitmproxy-ca-cert.pem /usr/local/share/ca-certificates/context-inspector-proxy.crt
update-ca-certificates >/dev/null

if [[ -n ${CONTEXT_INSPECTOR_CLAUDE_AUTH_INODE:-} ]]; then
    if ! setpriv --reuid=1000 --regid=1000 --clear-groups --no-new-privs \
        env "HOME=${agent_home}" "USER=${agent_user}" "LOGNAME=${agent_user}" \
        /usr/local/bin/claude --setting-sources '' --strict-mcp-config auth status --json | \
        python3 -c 'import json,sys
try:
    value=json.load(sys.stdin)
    sys.exit(0 if value.get("loggedIn") is True and value.get("authMethod") == "claude.ai" else 1)
except (ValueError, AttributeError):
    sys.exit(1)'; then
        echo "ERROR: native Claude did not select the shared subscription login" >&2
        exit 1
    fi
elif [[ ${1##*/} == codex ]]; then
    native_login_status=$(setpriv --reuid=1000 --regid=1000 --clear-groups --no-new-privs \
        env "HOME=${agent_home}" "USER=${agent_user}" "LOGNAME=${agent_user}" \
        /usr/local/bin/codex -c 'cli_auth_credentials_store="file"' login status 2>&1) || native_login_status=
    if [[ ${native_login_status##*$'\n'} != 'Logged in using ChatGPT' ]]; then
        echo "ERROR: native Codex did not select the shared ChatGPT login" >&2
        exit 1
    fi
    unset native_login_status
fi

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
if [[ ${1##*/} == claude && ${CONTEXT_INSPECTOR_STRACE_ENABLED:-0} == 1 ]]; then
    if ! command -v strace >/dev/null || [[ ! -d /strace ]]; then
        echo "ERROR: Claude strace requires the tracing image and /strace mount" >&2
        exit 1
    fi
    umask 077
    set -- strace -ffttv -A -o /strace/pid "$@"
fi
exec setpriv --reuid=1000 --regid=1000 --clear-groups --no-new-privs \
    env "HOME=${agent_home}" "USER=${agent_user}" "LOGNAME=${agent_user}" "$@"
