"""Explicit opt-in live OAuth/proxy validation in a disposable workspace.

Uses the user's existing native login. Retains private evidence under /tmp,
prints only transport/count metadata, and never starts the project's main stack.
"""
from __future__ import annotations
import argparse
import asyncio
from collections import Counter
import json
import os
from pathlib import Path
import pty
import select
import shutil
import signal
import subprocess
import tempfile
import time
import uuid

from src.server.context import ContextEventStream


async def observations(path, session):
    stream = ContextEventStream(path, session).events(mark_ready=True)
    results = []
    try:
        async for item in stream:
            if item.get('type') == 'replay-ready':
                break
            results.append(item)
    finally:
        await stream.aclose()
    return results


def probe(harness, model):
    project = Path(__file__).resolve().parents[2]
    root = Path(tempfile.mkdtemp(prefix='ci-live-oauth-'))
    root.chmod(0o700)
    runtime = root / 'src/runtime'
    runtime.mkdir(parents=True)
    for name in ('run.sh', 'oauth.py', 'container-entrypoint.sh', 'harness_image.py', 'strace-env.sh', 'mlflow-env.sh'):
        shutil.copyfile(project / 'src/runtime' / name, runtime / name)
    shutil.copytree(project / 'src/runtime/harnesses', runtime / 'harnesses')
    shutil.copytree(project / 'src/runtime/strace', runtime / 'strace')
    proxy = root / 'src/proxy'
    proxy.mkdir()
    shutil.copyfile(project / 'src/proxy/live_capture.py', proxy / 'live_capture.py')
    (root / '.venv').symlink_to(project / '.venv', target_is_directory=True)
    workspace = root / 'workspace'
    workspace.mkdir()
    session = 'probe-' + uuid.uuid4().hex[:12]
    network = 'ci-probe-' + uuid.uuid4().hex[:12]
    state = root / 'state'
    events = state / 'session/events.jsonl'
    env = {**os.environ, 'CONTEXT_INSPECTOR_HARNESS': harness, 'CONTEXT_INSPECTOR_AUTH_MODE': 'oauth',
           'CONTEXT_INSPECTOR_SESSION_ID': session, 'CONTEXT_INSPECTOR_EVENT_FILE': str(events),
           'CONTEXT_INSPECTOR_STATE_DIR': str(state), 'CONTEXT_INSPECTOR_RUNTIME_STATE_DIR': str(state / 'runtime'),
           'CONTEXT_INSPECTOR_CAPTURE_DIR': str(state / 'captures'), 'MITM_NETWORK_NAME': network}
    prompt = 'Use the shell tool once to run printf CONTEXT_INSPECTOR_PROBE. Then reply exactly CONTEXT_INSPECTOR_PROBE. Do not read files or use other tools.'
    if harness == 'codex':
        args = ['codex', 'exec', '--ephemeral', '--skip-git-repo-check', '--sandbox', 'danger-full-access',
                '--model', model, '-c', 'model_provider="openai"', '-c', 'cli_auth_credentials_store="file"',
                prompt]
    else:
        args = ['claude', '--print', '--no-session-persistence', '--model', model,
                '--dangerously-skip-permissions', '--setting-sources', '', '--strict-mcp-config',
                '--tools', 'Bash', '--', prompt]
    master, slave = pty.openpty()
    process = None
    timed_out = False
    log = root / 'terminal.log'
    try:
        process = subprocess.Popen(['bash', str(runtime / 'run.sh'), '--', *args], cwd=workspace,
            env=env, stdin=slave, stdout=slave, stderr=slave, start_new_session=True)
        os.close(slave)
        slave = None
        deadline = time.monotonic() + 150
        with log.open('wb') as output:
            log.chmod(0o600)
            while process.poll() is None:
                if time.monotonic() > deadline:
                    timed_out = True
                    os.killpg(process.pid, signal.SIGTERM)
                    break
                if select.select([master], [], [], 0.2)[0]:
                    try:
                        output.write(os.read(master, 65536))
                    except OSError:
                        break
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            while select.select([master], [], [], 0)[0]:
                try:
                    data = os.read(master, 65536)
                except OSError:
                    break
                if not data:
                    break
                output.write(data)
    finally:
        if slave is not None:
            os.close(slave)
        os.close(master)
        for name in ('context-inspector-agent-' + session, 'context-inspector-proxy-' + session):
            subprocess.run(['podman', 'rm', '--force', name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        subprocess.run(['podman', 'network', 'rm', network], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
    raw = [json.loads(line) for line in events.read_text().splitlines()] if events.exists() else []
    derived = asyncio.run(asyncio.wait_for(observations(events, session), timeout=10)) if events.exists() else []
    responses = [item for item in derived if item.get('kind') == 'context.response']
    return {'harness': harness, 'requested_model': model, 'exit_code': process.returncode if process else None,
            'timed_out': timed_out, 'private_evidence_directory': str(root),
            'event_counts': dict(Counter(item['kind'] for item in raw)),
            'derived_counts': dict(Counter(item.get('kind', item.get('type')) for item in derived)),
            'response_statuses': [item['response']['stop_reason'] for item in responses],
            'observed_response_models': sorted({item['response']['model'] for item in responses if item['response'].get('model')}),
            'input_usage': [item.get('used_input_tokens') for item in derived if item.get('kind') == 'context.usage']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', required=True)
    parser.add_argument('--harness', choices=('claude', 'codex'), required=True)
    parser.add_argument('--model', required=True)
    options = parser.parse_args()
    print(json.dumps(probe(options.harness, options.model), indent=2))
