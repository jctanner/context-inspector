# Validated Podman + mitmproxy Runtime Recipe

## Purpose and authority

This note records the working two-container runtime developed by the parent
context-engineering project and the failures that shaped it. It is the starting
point for Context Inspector's runtime integration; it is not a replacement for
reading the current implementation.

Authoritative reference files, relative to the parent project root:

- `experiments/mitm-agent-container/run.sh` — container orchestration;
- `experiments/mitm-agent-container/capture.py` — completed-flow capture addon;
- `experiments/mitm-agent-container/README.md` — operator instructions and
  security warnings;
- `experiments/subagents/run_phase2.py` — representative robust `pexpect`
  lifecycle and failure cleanup;
- `experiments/mcp-cli/run_experiment.py` — representative isolated config and
  interactive CLI startup handling.

When this note and those files differ, inspect git history and test the current
runtime. Do not silently assume this recipe describes a future modified runner.

## What the validated runtime does

The host runner creates two sibling containers on a private rootless Podman
network:

```text
host driver / controlling PTY
        |
        v
agent container
  real Claude CLI
  workspace mounted at /workspace
  HTTP(S)_PROXY=http://agent-mitm-proxy:8080
  NODE_EXTRA_CA_CERTS=/mitmproxy-ca-cert.pem
        |
        | TLS through explicit HTTP CONNECT proxy
        v
mitmproxy sidecar
  capture addon
  persistent experiment CA
        |
        v
Anthropic or Google Vertex endpoint
```

The proxy and terminal are independent evidence paths. A Claude response in the
terminal does not prove that its model request crossed the proxy.

## Prerequisites

The validated defaults are:

```text
container engine: rootless Podman
agent image:       localhost/claude-task-runner:latest
proxy image:       docker.io/mitmproxy/mitmproxy:12.1.2
agent userns:      keep-id
network:           agent-mitm-network
proxy container:   agent-mitm-proxy
proxy port:        8080
```

The agent image came from the reference checkout named in the experiment
README. Its documented build command is:

```bash
podman build \
  -t claude-task-runner \
  -f ~/workspace/github/jctanner.redhat/2026_07_29_strat_pull_args/scripts/Dockerfile.claude \
  ~/workspace/github/jctanner.redhat/2026_07_29_strat_pull_args
```

The inspector should make the image configurable through `AGENT_IMAGE` and
should fail early with an actionable message when the image, Podman, or required
credentials are absent.

## Operator environment

The experiments commonly use Claude Code through Vertex:

```bash
export CLAUDE_CODE_USE_VERTEX=1
export ANTHROPIC_VERTEX_PROJECT_ID=your-project
export CLOUD_ML_REGION=global
```

The Context Inspector launcher requires and sources `.env` from its own project
root before starting Python. It never falls back to a parent project. This is
essential: a fresh `CLAUDE_CONFIG_DIR` without the provider variables can open
Claude's OAuth onboarding UI instead of the expected Vertex-backed REPL.

The runtime forwards these variables individually when present:

- `CLAUDE_CODE_USE_VERTEX`
- `ANTHROPIC_VERTEX_PROJECT_ID`
- `CLOUD_ML_REGION`

Do not indiscriminately forward the complete host environment into either
container.

## Command boundary

The current runner is called as:

```bash
./experiments/mitm-agent-container/run.sh -- \
  claude --model=sonnet --dangerously-skip-permissions
```

The `--` belongs to the runner's interface. It ends runner options and marks
everything after it as the agent command and its arguments. The runner removes
that separator, uses the first following word as the container entrypoint, and
passes the remaining words as arguments.

Context Inspector should use an argument vector rather than reconstructing this
command as an interpolated shell string.

## Directory creation and host permissions

The runner resolves its own directory and creates:

```text
experiments/mitm-agent-container/
  state/
    adc.json
    mitmproxy/
      mitmproxy-ca-cert.pem
      ...other mitmproxy CA material...
  captures/
    flows-<UTC run ID>.jsonl
    mitmproxy-<UTC run ID>.log
```

`state/`, `state/mitmproxy/`, and `captures/` are mode `0700`. The generated CA
certificate is changed to mode `0644` so the unprivileged agent user can read
the bind-mounted certificate. Each extracted capture is changed to mode `0600`.

Context Inspector should use a private application state directory and a
per-session subdirectory. It must not place raw request bodies in a normal web
asset directory.

## Private Podman network

The runner checks for the named network and creates it when absent:

```bash
podman network exists agent-mitm-network
podman network create agent-mitm-network
```

Both containers join that network. The agent reaches the proxy by container
name, not through a host-published port:

```text
http://agent-mitm-proxy:8080
```

The current names are global constants, so simultaneous runners would collide:
the runner forcibly removes any existing container named `agent-mitm-proxy`.
Context Inspector must derive proxy and agent names from a validated session ID,
or explicitly enforce a single active session. Run IDs currently have one-second
resolution and likewise should not be treated as collision-proof identifiers.

## Persistent CA generation

Before the agent container starts, the runner ensures that the mitmproxy CA
exists. It launches the proxy image once as root, points its configuration at
the writable bind mount, and exits immediately:

```bash
podman run --rm \
  --user 0 \
  --volume "$STATE_DIR/mitmproxy:/tmp/mitmproxy:Z" \
  --entrypoint mitmdump \
  docker.io/mitmproxy/mitmproxy:12.1.2 \
  --set confdir=/tmp/mitmproxy --commands 'quit'
```

Two details are fixes rather than decoration:

1. The proxy runs with `--user 0` for CA generation and capture. Attempts to
   remap the image's built-in user produced permission errors and an invalid
   `usermod` invocation.
2. `confdir` is `/tmp/mitmproxy`, the mounted writable state directory. Letting
   mitmproxy inspect `/home/mitmproxy/.mitmproxy/config.yaml` caused
   `PermissionError: [Errno 13] Permission denied` under the rootless setup.

Do not regenerate the CA per HTTP request or per model call. Generate or select
it before mounting the certificate into the agent.

## Proxy sidecar startup

The sidecar is detached and uses the same writable configuration mount:

```bash
podman run --detach --rm \
  --name "$PROXY_NAME" \
  --network "$NETWORK_NAME" \
  --user 0 \
  --env "CAPTURE_FILE=/tmp/$CAPTURE_NAME" \
  --env "CAPTURE_HOST_RE=$CAPTURE_HOST_RE" \
  --volume "$STATE_DIR/mitmproxy:/tmp/mitmproxy:Z" \
  --volume "$EXPERIMENT_DIR/capture.py:/addons/capture.py:ro,Z" \
  --entrypoint mitmdump \
  "$PROXY_IMAGE" \
  --listen-host 0.0.0.0 \
  --listen-port 8080 \
  --set block_global=false \
  --set confdir=/tmp/mitmproxy \
  --scripts /addons/capture.py
```

The `:Z` suffix supplies a private SELinux relabel for each bind mount. Omitting
SELinux handling can look like an ordinary Unix permission failure.

The runner polls `podman logs` for `proxy server listening` up to 30 times at
0.2-second intervals. The GUI implementation should turn failure to observe
readiness into an explicit startup error and retain the sidecar log.

## Agent proxy and TLS environment

The agent receives uppercase and lowercase forms because runtimes do not honor
proxy variables consistently:

```text
HTTP_PROXY=http://<proxy-name>:8080
HTTPS_PROXY=http://<proxy-name>:8080
http_proxy=http://<proxy-name>:8080
https_proxy=http://<proxy-name>:8080
NO_PROXY=localhost,127.0.0.1,<proxy-name>
no_proxy=localhost,127.0.0.1,<proxy-name>
NODE_EXTRA_CA_CERTS=/mitmproxy-ca-cert.pem
```

The CA is mounted read-only at the exact path named by
`NODE_EXTRA_CA_CERTS`:

```bash
--volume "$STATE_DIR/mitmproxy/mitmproxy-ca-cert.pem:/mitmproxy-ca-cert.pem:ro,Z"
```

An earlier run failed with curl error 77 because the certificate path existed
in configuration but was not readable at the expected location. Validate both
the mount and readability from the agent's actual unprivileged UID.

`MITM_INSECURE_TLS=1` adds `NODE_TLS_REJECT_UNAUTHORIZED=0`. This was retained
only as a diagnostic escape hatch for determining whether Node ignored the
custom CA. It disables TLS verification for every destination and must not be
the normal GUI path or a hidden fallback.

## Google ADC handling

The runner resolves the source credential file from
`GOOGLE_APPLICATION_CREDENTIALS`, falling back to:

```text
$HOME/.config/gcloud/application_default_credentials.json
```

It does not bind-mount that host file directly. It copies it to
`state/adc.json`, changes the copy to mode `0644` inside the enclosing mode
`0700` state directory, and mounts the copy read-only:

```text
host state/adc.json → container /tmp/adc.json
GOOGLE_APPLICATION_CREDENTIALS=/tmp/adc.json
```

This fixed `EACCES: permission denied, open '/tmp/adc.json'` from the
unprivileged container. The containing host directory prevents other host users
from discovering the otherwise container-readable copy.

The GUI must never send ADC contents to the browser, capture event stream, log,
or diagnostic bundle.

## Workspace and Claude configuration

The current working directory is mounted read-write with SELinux relabeling:

```bash
--volume "$PWD:/workspace:rw,Z"
--workdir /workspace
```

The agent runs with `--userns=keep-id`, which preserves useful ownership for
workspace writes without mutating the image's user database.

Experiments needing isolation create a config directory under the mounted run
directory and invoke the runner with an `env` entrypoint, for example:

```text
run.sh -- env CLAUDE_CONFIG_DIR=/workspace/<run-relative-config> \
  claude --model=sonnet --dangerously-skip-permissions
```

Context Inspector needs an explicit product choice between:

- an isolated per-inspector-session `CLAUDE_CONFIG_DIR`, which improves
  reproducibility but may trigger first-run dialogs and lacks the user's normal
  configuration; and
- a deliberately mounted persistent config, which better resembles normal use
  but can modify or expose user state.

Do not accidentally use whichever config happens to be visible inside the
image. Record the selected mode in session metadata.

## Independent proxy smoke test

Before Claude starts, the runner launches the agent image with `curl` as its
entrypoint and requests:

```text
https://www.googleapis.com/discovery/v1/apis
```

It uses the same network, proxy variables, user namespace, CA mount, and:

```bash
curl --fail --silent --show-error --output /dev/null \
  --cacert /mitmproxy-ca-cert.pem <URL>
```

This checks network membership, proxy DNS/reachability, TLS interception, and CA
trust without relying on Claude. The addon excludes this exact URL from model
captures. `--no-smoke-test` exists for non-Google providers.

The GUI should expose smoke-test failure as a runtime diagnostic, not start a
session that later appears to contain mysteriously empty traffic.

## Launching the real interactive CLI

The validated runner ends with an interactive container:

```bash
podman run --rm -it \
  --network "$NETWORK_NAME" \
  --userns=keep-id \
  --workdir /workspace \
  --entrypoint "$AGENT_COMMAND" \
  <proxy env> <mounts> "$AGENT_IMAGE" <agent arguments>
```

For Context Inspector, the local server should itself run this command under a
real PTY. The browser WebSocket forwards bytes between that PTY and xterm.js.
Do not remove `-it`, pipe Claude through ordinary subprocess pipes, or parse the
terminal as if it were line-oriented stdout.

The experiment drivers used:

```python
pexpect.spawn(
    command,
    args,
    encoding="utf-8",
    timeout=5,
    maxread=65536,
    dimensions=(50, 200),
)
```

They attached `logfile_read` to a transcript. The GUI needs the same underlying
PTY properties but should forward raw ANSI terminal output to xterm.js. It must
also propagate xterm.js resize events back to the PTY rather than retaining the
experiments' fixed 50-by-200 dimensions.

## Interactive startup lessons

Claude Code uses an Ink terminal UI. Startup is not reliably represented by a
fixed delay or a single shell prompt. Fresh configurations can display:

- theme/style selection;
- security notes;
- workspace trust;
- bypass-permissions confirmation;
- provider authentication/onboarding.

The automated experiments used a state machine that waited for complete dialog
text before sending keys and required the actual ready status marker. Sending a
cursor key before Ink completed a redraw could be lost. Treating a merely quiet
screen as ready caused prompts to be typed into a confirmation dialog.

For a human-operated browser terminal, these screens should normally be shown
and controlled by the user rather than automated away. The server must still
avoid declaring the session dead merely because no model traffic occurs during
setup.

## Capture addon behavior

The current addon filters `pretty_host` using:

```text
(^|\.)(anthropic\.com|googleapis\.com|googleusercontent\.com)$
```

`CAPTURE_HOST_RE` can override it. Authentication headers including
`authorization`, cookies, proxy authorization, and common API-key headers are
replaced with `[REDACTED]`.

For each completed matching flow, the addon records:

- capture timestamp;
- request method, URL, HTTP version, redacted headers, and body;
- response status, reason, HTTP version, redacted headers, and body.

Text, JSON, and event streams are stored as UTF-8. Other bodies are base64.
Bodies with a non-identity `Content-Encoding` are always stored as base64 with
the HTTP content encoding recorded separately. This preserves compressed bytes
instead of mistakenly decoding gzip as text—a failure that previously weakened
response-to-next-request comparisons.

The current implementation uses only mitmproxy's `response(flow)` hook. It is
therefore a completed-flow recorder, not a live event source. Context Inspector
must add lifecycle emission while retaining a completed, lossless record for
validation. At minimum, distinguish:

1. request available;
2. response headers available;
3. response/SSE data available or accumulated;
4. flow complete;
5. flow error.

The live channel must not mutate the exact archival representation or expose
unredacted credentials.

## Capture extraction and shutdown ordering

The addon deliberately writes to `/tmp/<capture-name>` inside the proxy
container. Writing directly to a host capture bind mount caused rootless UID and
SELinux ambiguity. After the agent exits, the runner executes `podman cp` from
the still-running sidecar, then sets the host copy to mode `0600`.

If the copy fails, the runner creates an empty private capture so downstream
tools have a known path. It counts JSONL records and prints both the path and
flow count. Zero flows generate an explicit warning and point to the proxy log.

Cleanup then:

1. saves `podman logs` to the private capture directory;
2. forcibly removes the proxy container;
3. runs on normal exit, interrupt, or termination through a shell trap.

The ordering matters: do not remove the sidecar before extracting the capture
and diagnostics. Likewise, abruptly killing the outer runner can prevent its
post-agent extraction code from running.

Experiment failure handlers first sent Ctrl-C to cancel a stuck model turn,
then attempted `/exit`, waited for EOF, and force-closed only after a timeout.
The browser server should implement an analogous graduated shutdown and retain
partial live events even when archival extraction fails.

## How to validate a session

A minimal validated test is:

```bash
./experiments/mitm-agent-container/run.sh -- \
  claude --model=sonnet --dangerously-skip-permissions \
  -p 'Reply with only: capture works'
```

Success requires all of the following:

- terminal output is `capture works`;
- the runner prints a capture path;
- the completed-flow count is greater than zero;
- the proxy log contains no unexplained interception error;
- the captured request contains the model call being tested;
- headers are redacted and the body remains decodable.

We encountered several runs where Claude printed `capture works` but the capture
contained zero model flows. Those runs established only that Claude worked—not
that the observation path worked. Context Inspector must make “terminal works,
capture missing” a prominent degraded/error state.

## Reuse versus adaptation for Context Inspector

Reuse or preserve initially:

- rootless Podman and the existing agent image;
- private sibling-container network;
- CA generation and `/tmp/mitmproxy` configuration directory;
- `--user 0` for the proxy and `--userns=keep-id` for the agent;
- explicit proxy environment and read-only CA mount;
- ADC copy/mount pattern;
- workspace mount at `/workspace`;
- proxy-routed smoke test and its capture exclusion;
- lossless completed-flow JSONL and header redaction;
- capture-before-container-removal ordering.

Adapt for the GUI:

- use unique session-scoped container names and run IDs;
- launch the runner under a server-owned PTY and support dynamic resize;
- emit live request/response lifecycle events from the addon;
- send those events to a loopback-only server through a defined authenticated or
  session-secret-bearing local channel;
- preserve partial events and diagnostics across browser disconnects;
- make config isolation versus persistent user state explicit;
- separate archival capture retention from the default in-memory viewer;
- expose proxy readiness, smoke-test status, flow counts, and degraded states in
  the UI;
- keep exact captured records separate from normalized context views and diffs.

## Known traps checklist

Before diagnosing Claude itself, check:

- [ ] Does project-root `.env` exist with the required provider variables?
- [ ] Does the agent image exist under the configured name?
- [ ] Is the proxy using a writable `/tmp/mitmproxy` `confdir`?
- [ ] Was the CA generated before the agent mount was resolved?
- [ ] Is the CA readable inside the agent at the exact configured path?
- [ ] Are uppercase and lowercase proxy variables present?
- [ ] Can the smoke-test container complete verified TLS through the proxy?
- [ ] Is ADC copied into private state and readable by the container user?
- [ ] Are bind mounts correctly SELinux-labeled?
- [ ] Is Claude attached to a PTY rather than ordinary pipes?
- [ ] Did a first-run dialog consume input intended for the prompt?
- [ ] Does `CAPTURE_HOST_RE` cover the actual provider endpoint?
- [ ] Was the smoke-test URL excluded from experimental flow counts?
- [ ] Was the capture copied before the proxy container was removed?
- [ ] Is a successful answer being incorrectly treated as proof of interception?
