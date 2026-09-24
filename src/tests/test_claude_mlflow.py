from contextlib import redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

from src.server.mlflow import (MLflowSettings, PLUGIN_PROJECT, PLUGIN_ROOT, RUNTIME_KEYS,
                               container_command, mlflow_service, prepare_agent_image,
                               prepare_runtime, tracing_environment)


class ClaudeMLflowTests(unittest.TestCase):
    def test_hook_deadline_fails_open_and_disable_skips_hook(self):
        with tempfile.TemporaryDirectory() as directory:
            timeout = Path(directory) / 'timeout'
            timeout.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >&2\nexit 124\n')
            timeout.chmod(0o755)
            env = {**os.environ, 'PATH': directory + os.pathsep + os.environ['PATH'],
                   'MLFLOW_CLAUDE_TRACING_ENABLED': 'true'}
            result = subprocess.run(['bash', str(PLUGIN_PROJECT / 'plugin' / 'stop.sh')],
                                    env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0)
            self.assertIn('--signal=TERM --kill-after=5s 30s node', result.stderr)
            self.assertIn('trace may be missing', result.stderr)
            env['MLFLOW_CLAUDE_TRACING_ENABLED'] = 'false'
            result = subprocess.run(['bash', str(PLUGIN_PROJECT / 'plugin' / 'stop.sh')],
                                    env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stderr, '')

    def test_runtime_environment_is_scoped_and_disabled_clears_stale_values(self):
        previous = {key: 'stale' for key in RUNTIME_KEYS}
        with patch.dict(os.environ, previous):
            with tracing_environment('owned', '7', 'image'):
                self.assertEqual([os.environ[k] for k in RUNTIME_KEYS], ['owned', '7', 'image'])
            self.assertEqual({k: os.environ[k] for k in RUNTIME_KEYS}, previous)
            with mlflow_service(MLflowSettings(enabled=False)):
                self.assertTrue(all(os.environ[k] == '' for k in RUNTIME_KEYS))

    def test_network_and_allowlist(self):
        command = container_command(MLflowSettings(network='fixture-network'), 'owned')
        self.assertEqual(command[command.index('--network') + 1], 'fixture-network')
        hosts = command[command.index('--allowed-hosts') + 1]
        self.assertEqual(hosts, 'localhost:*,127.0.0.1:*,owned:5000')

    @patch('src.server.mlflow.subprocess.run')
    def test_disabled_tracing_does_not_install_plugin_or_build_agent(self, run):
        run.return_value.returncode = 0
        self.assertEqual(prepare_runtime(MLflowSettings(tracing_enabled=False)), '')
        self.assertEqual(run.call_args.args[0][:3], ['podman', 'network', 'exists'])
        self.assertEqual(run.call_count, 1)

    @patch('src.server.mlflow.subprocess.run')
    def test_derived_image_is_cached_by_base_image_id(self, run):
        run.side_effect = [Mock(stdout='base-a', returncode=0), Mock(returncode=0),
                           Mock(stdout='base-b', returncode=0), Mock(returncode=0)]
        first, second = prepare_agent_image(), prepare_agent_image()
        self.assertNotEqual(first, second)
        self.assertTrue(first.startswith('localhost/context-inspector-harnesses:'))

    def test_runner_injection_and_disable(self):
        script = PLUGIN_PROJECT.parent / 'mlflow-env.sh'
        name = 'context-inspector-mlflow-' + 'a' * 32
        # Serialize argv as NUL-delimited values, never evaluate shell output.
        command = '''
set -euo pipefail
runtime_dir=$1
agent_command=$2
proxy_name=fixture-proxy
agent_env=()
mounts=()
source "$runtime_dir/mlflow-env.sh"
configure_claude_tracing >&2
printf '%s\0' "${agent_env[@]}" "${mounts[@]}" "${tracing_args[@]}"
'''
        for enabled, agent in [(True, 'claude'), (False, 'claude'), (True, 'bash')]:
            with self.subTest(enabled=enabled, agent=agent):
                env = {**os.environ, 'CONTEXT_INSPECTOR_MLFLOW_CONTAINER': name if enabled else '',
                       'CONTEXT_INSPECTOR_MLFLOW_EXPERIMENT_ID': '9'}
                result = subprocess.run(['bash', '-c', command.replace('\0', '\\0'), 'fixture',
                                         str(script.parent), agent], env=env, capture_output=True, check=True)
                argv = result.stdout.decode().split('\0')
                if enabled and agent == 'claude':
                    self.assertIn('--plugin-dir', argv)
                    self.assertIn(f'MLFLOW_TRACKING_URI=http://{name}:5000', argv)
                    self.assertIn(f'NO_PROXY=localhost,127.0.0.1,fixture-proxy,{name}', argv)
                    self.assertIn('MLFLOW_EXPERIMENT_ID=9', argv)
                    self.assertIn('MLFLOW_MODEL_CATALOG_URI=', argv)
                    self.assertTrue(any(item.endswith(':ro,z') for item in argv))
                else:
                    self.assertNotIn('--plugin-dir', argv)
                    self.assertNotIn('--volume', argv)
                    self.assertIn('MLFLOW_CLAUDE_TRACING_ENABLED=false', argv)


@unittest.skipUnless(os.environ.get('CONTEXT_INSPECTOR_TEST_MLFLOW') == '1', 'opt-in Podman integration')
class ClaudeMLflowContainerTests(unittest.TestCase):
    def test_real_claude_stop_hook_exports_tool_trace(self):
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            port = listener.getsockname()[1]
        network = 'ci-mlflow-smoke-' + uuid4().hex
        agent_name = 'ci-mlflow-agent-smoke-' + uuid4().hex
        settings = MLflowSettings(port=port, network=network)
        try:
            with mlflow_service(settings):
                container = os.environ[RUNTIME_KEYS[0]]
                experiment = os.environ[RUNTIME_KEYS[1]]
                image = os.environ[RUNTIME_KEYS[2]]
                result = subprocess.run([
                    'podman', 'run', '--rm', '--name', agent_name, '--network', network,
                    '--env', 'MLFLOW_CLAUDE_TRACING_ENABLED=true',
                    '--env', f'MLFLOW_TRACKING_URI=http://{container}:5000',
                    '--env', f'MLFLOW_EXPERIMENT_ID={experiment}',
                    '--env', 'MLFLOW_MODEL_CATALOG_URI=',
                    '--env', 'HTTP_PROXY=http://127.0.0.1:9',
                    '--env', 'HTTPS_PROXY=http://127.0.0.1:9',
                    '--env', f'NO_PROXY=127.0.0.1,localhost,{container}',
                    '--volume', f'{PLUGIN_ROOT}:/opt/context-inspector/mlflow:ro,z',
                    '--volume', f'{PLUGIN_PROJECT / "plugin"}:/opt/context-inspector/mlflow-plugin:ro,z',
                    '--volume', f'{Path(__file__).with_name("mlflow-claude-fixture.mjs")}:/fixture.mjs:ro,z',
                    '--entrypoint', 'node', image, '/fixture.mjs',
                ], capture_output=True, text=True, timeout=90)
                self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
                cli = json.loads(result.stdout)
                # Read via the server's installed SDK; do not add host dependencies.
                query = '''
import json, sys
import mlflow
from mlflow import MlflowClient
mlflow.set_tracking_uri("http://127.0.0.1:5000")
client = MlflowClient(tracking_uri="http://127.0.0.1:5000")
traces = client.search_traces(locations=[sys.argv[1]])
print(json.dumps([{"session": t.info.trace_metadata.get("mlflow.trace.session"),
                   "spans": [{"name": s.name, "type": s.span_type,
                              "id": s.span_id, "parent": s.parent_id,
                              "tool_id": s.attributes.get("tool_id"),
                              "outputs": s.outputs} for s in t.data.spans]} for t in traces]))
'''
                exported = subprocess.run(['podman', 'exec', container, 'python', '-c', query, experiment],
                                          capture_output=True, text=True, timeout=30)
                self.assertEqual(exported.returncode, 0, exported.stderr)
                traces = json.loads(exported.stdout)
                self.assertEqual(len(traces), 2, traces)
                actual = next(t for t in traces if t['session'] == cli['session_id'])
                spans = actual['spans']
                self.assertTrue(any(s['type'] == 'LLM' for s in spans), spans)
                tool = next(s for s in spans if s['tool_id'] == 'toolu_fixture_read')
                self.assertIn('fixture tool result', json.dumps(tool['outputs']))
                synthetic = next(t for t in traces if t['session'] == 'synthetic-nested-session')['spans']
                task = next(s for s in synthetic if s['tool_id'] == 'toolu_fixture_task')
                child = next(s for s in synthetic if s['name'] == 'subagent_general-purpose')
                self.assertEqual(child['parent'], task['id'])
                self.assertTrue(any(s['parent'] == child['id'] and s['type'] == 'LLM' for s in synthetic))
                print('Verified real Claude Stop hook: session ID, LLM span, Read tool ID and result.')
                print('Verified synthetic transcript: Task tool → child agent → nested LLM span.')
        finally:
            subprocess.run(['podman', 'rm', '--force', '--ignore', agent_name], capture_output=True)
            subprocess.run(['podman', 'network', 'rm', network], capture_output=True)


if __name__ == '__main__':
    unittest.main()
