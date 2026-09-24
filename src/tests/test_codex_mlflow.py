"""Turn association and runtime supervision tests use only synthetic data."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1] / 'runtime' / 'mlflow'
spec = importlib.util.spec_from_file_location('codex_tracing', ROOT / 'codex-tracing.py')
tracing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tracing)


def event(kind, **values):
    return {'type': 'event_msg', 'timestamp': '2026-09-23T00:00:00Z', 'payload': {'type': kind, **values}}


def tokens(total, last):
    usage = lambda n: {'input_tokens': n, 'output_tokens': n, 'total_tokens': n * 2}
    return event('token_count', info={'total_token_usage': usage(total), 'last_token_usage': usage(last)})


class CodexMLflowTests(unittest.TestCase):
    def test_delayed_callback_selects_exact_turn_and_aggregate_usage(self):
        rows = [event('task_started', turn_id='1'), tokens(10, 10), tokens(30, 20),
                event('task_complete', turn_id='1'), event('task_started', turn_id='2'),
                tokens(35, 5), event('task_complete', turn_id='2')]
        first, source = tracing.scoped_records(rows, '1')
        self.assertIn('delta', source)
        self.assertEqual(first[-2]['payload']['info']['last_token_usage']['input_tokens'], 30)
        second, _ = tracing.scoped_records(rows, '2')
        self.assertEqual(second[-2]['payload']['info']['last_token_usage']['input_tokens'], 5)
        self.assertNotIn('2', [r['payload'].get('turn_id') for r in first])
        self.assertEqual(rows[1]['payload']['info']['last_token_usage']['input_tokens'], 10)

    def test_missing_interrupted_or_reset_usage_is_not_invented(self):
        self.assertEqual(tracing.scoped_records([event('task_started', turn_id='1')], '1'), ([], 'unavailable'))
        rows = [tokens(100, 10), event('task_started', turn_id='1'), tokens(10, 10), event('task_complete', turn_id='1')]
        selected, source = tracing.scoped_records(rows, '1')
        self.assertEqual(source, 'unavailable')
        self.assertNotIn('last_token_usage', selected[1]['payload']['info'])
        self.assertEqual(tracing.scoped_records(rows, 'missing'), ([], 'unavailable'))

    def test_resumed_baseline_missing_omits_usage_and_uses_current_model(self):
        rows = [{'type': 'turn_context', 'payload': {'model': 'old'}},
                event('task_started', turn_id='1'),
                {'type': 'turn_context', 'payload': {'model': 'new'}}, tokens(100, 10),
                event('task_complete', turn_id='1')]
        selected, source = tracing.scoped_records(rows, '1')
        self.assertEqual(source, 'unavailable')
        self.assertEqual(selected[0]['payload']['model'], 'new')

    def test_queue_is_private_and_deduplicated(self):
        with tempfile.TemporaryDirectory() as directory:
            queue = Path(directory)
            raw = json.dumps({'type': 'agent-turn-complete', 'thread-id': 'thread', 'turn-id': '1'})
            tracing.enqueue(queue, raw)
            tracing.enqueue(queue, raw)
            files = list(queue.iterdir())
            self.assertEqual(len(files), 1)
            self.assertEqual(files[0].stat().st_mode & 0o777, 0o600)

    def test_existing_notify_preserved_without_config_write(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            config = home / 'config.toml'
            config.write_text('notify = ["example", "arg"]\n')
            self.assertEqual(tracing.existing_notify(home, ['codex']), ['example', 'arg'])
            self.assertEqual(config.read_text(), 'notify = ["example", "arg"]\n')
            self.assertEqual(tracing.existing_notify(home, ['codex', 'notify=[] is my prompt']), ['example', 'arg'])
            for override in (['-c', 'notify=[]'], ['-cnotify=[]'], ['--config=notify=[]']):
                with self.assertRaises(ValueError):
                    tracing.existing_notify(home, ['codex', *override])

    def test_supervisor_preserves_cli_exit_after_unexpected_export_failure(self):
        import sys
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            cli = home / 'fixture-cli'
            cli.write_text(f'#!{sys.executable}\n' + '''import json, subprocess, sys
notify = json.loads(sys.argv[2].split("=", 1)[1])
subprocess.run([*notify, json.dumps({"type": "agent-turn-complete", "thread-id": "fixture", "turn-id": "1"})], check=True)
sys.exit(7)
''')
            cli.chmod(0o700)
            with patch.dict(os.environ, {'CODEX_HOME': directory}), \
                 patch.object(tracing, 'export_job', side_effect=ValueError('sensitive fixture detail')):
                code = tracing.supervise([str(cli)])
            self.assertEqual(code, 7)
            self.assertNotIn('sensitive fixture detail', (home / 'mlflow-tracing.log').read_text())

    def test_export_failure_is_private_and_does_not_raise(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            path = home / 'job.json'
            path.write_text(json.dumps({'thread-id': 'fixture', 'turn-id': '1'}))
            log = home / 'log'
            with patch.object(tracing, 'read_turn', return_value=([event('task_complete', turn_id='1')], 'unavailable')), \
                 patch.object(tracing.subprocess, 'run', side_effect=subprocess.TimeoutExpired('node', 20)):
                tracing.export_job(path, home, [], log, [None])
            self.assertIn('export failed', log.read_text())

    def test_shutdown_deadline_skips_expired_jobs(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            path = home / 'job.json'
            path.write_text(json.dumps({'thread-id': 'fixture', 'turn-id': '1'}))
            with patch.object(tracing.subprocess, 'run') as run:
                tracing.export_job(path, home, [], home / 'log', [0.0])
            run.assert_not_called()

    def test_launch_injection_and_disabled_path(self):
        script = '''set -euo pipefail
runtime_dir=$1
agent_command=/usr/local/bin/codex
proxy_name=fixture-proxy
session_id=fixture-session
agent_env=(); mounts=()
source "$runtime_dir/mlflow-env.sh"
configure_codex_tracing >&2
printf '%s\\0' "${agent_env[@]}" "${mounts[@]}"
'''
        for enabled in (False, True):
            env = {**os.environ, 'CONTEXT_INSPECTOR_MLFLOW_CONTAINER': 'context-inspector-mlflow-' + 'a' * 32 if enabled else '',
                   'CONTEXT_INSPECTOR_MLFLOW_EXPERIMENT_ID': '1'}
            result = subprocess.run(['bash', '-c', script, 'fixture', str(ROOT.parent)], env=env, capture_output=True, check=True)
            self.assertEqual(b'CONTEXT_INSPECTOR_CODEX_TRACING_ENABLED=1' in result.stdout, enabled)
            self.assertEqual(b'MLFLOW_TRACKING_URI=' in result.stdout, enabled)
            self.assertNotIn(b'OPENAI_BASE_URL', result.stdout)

@unittest.skipUnless(os.environ.get('CONTEXT_INSPECTOR_TEST_MLFLOW') == '1', 'opt-in Podman integration')
class CodexMLflowContainerTests(unittest.TestCase):
    def test_native_notify_exports_turns_tools_usage_and_drains_on_exit(self):
        import socket
        from uuid import uuid4
        from src.server.mlflow import MLflowSettings, mlflow_service, RUNTIME_KEYS
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            port = listener.getsockname()[1]
        network = 'ci-codex-mlflow-' + uuid4().hex
        agent_name = 'ci-codex-tracing-' + uuid4().hex
        settings = MLflowSettings(port=port, network=network, experiment_name='Codex fixture')
        try:
            with mlflow_service(settings):
                container, experiment, image = [os.environ[k] for k in RUNTIME_KEYS]
                result = subprocess.run([
                    'podman', 'run', '--rm', '--name', agent_name, '--network', network,
                    '--env', f'MLFLOW_TRACKING_URI=http://{container}:5000',
                    '--env', f'MLFLOW_EXPERIMENT_ID={experiment}',
                    '--env', 'MLFLOW_TRACE_LOCATION=', '--env', 'CONTEXT_INSPECTOR_SESSION_ID=fixture-session',
                    '--volume', f'{ROOT}:/opt/context-inspector/codex-mlflow:ro,z',
                    '--volume', f'{Path(__file__).with_name("mlflow-codex-fixture.mjs")}:/fixture.mjs:ro,z',
                    '--volume', f'{Path(__file__).with_name("codex-tui-fixture.py")}:/tui-fixture.py:ro,z',
                    '--entrypoint', 'node', image, '/fixture.mjs',
                ], capture_output=True, text=True, timeout=150)
                self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
                cli = json.loads(result.stdout)
                query = '''
import json, sys
import mlflow
mlflow.set_tracking_uri("http://127.0.0.1:5000")
from mlflow import MlflowClient
client = MlflowClient(tracking_uri="http://127.0.0.1:5000")
traces = client.search_traces(locations=[sys.argv[1]])
print(json.dumps([{"metadata": t.info.trace_metadata,
    "spans": [{"name": s.name, "type": s.span_type, "parent": s.parent_id,
               "attributes": s.attributes, "outputs": s.outputs} for s in t.data.spans]} for t in traces]))
'''
                result = subprocess.run(['podman', 'exec', container, 'python', '-c', query, experiment],
                                        capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr)
                traces = json.loads(result.stdout)
                self.assertEqual(len(traces), len(cli["callbacks"]), {"count": len(traces), "exports": cli["exports"]})
                self.assertEqual({t['metadata']['codex.turn_id'] for t in traces}, {c['turn-id'] for c in cli['callbacks']})
                for trace in traces:
                    expected_session = next(c['thread-id'] for c in cli['callbacks'] if c['turn-id'] == trace['metadata']['codex.turn_id'])
                    self.assertEqual(trace['metadata']['mlflow.trace.session'], expected_session)
                    if trace['metadata']['codex.turn_id'] in cli['turns']:
                        self.assertEqual(trace['metadata']['context_inspector.evidence'], 'transcript reconstruction')
                    self.assertEqual(trace['metadata']['context_inspector.session_id'], 'fixture-session')
                    self.assertTrue(any(s['type'] == 'LLM' for s in trace['spans']))
                first = next(t for t in traces if t['metadata']['codex.turn_id'] == cli['turns'][0])
                tool = next(s for s in first['spans'] if s['type'] == 'TOOL')
                self.assertIn('fixture-tool-result', json.dumps(tool['outputs']))
                for trace, expected_input in [(first, 20), (next(t for t in traces if t['metadata']['codex.turn_id'] == cli['turns'][1]), 10)]:
                    root = next(s for s in trace['spans'] if s['parent'] is None)
                    self.assertEqual(root['attributes']['mlflow.chat.tokenUsage']['input_tokens'], expected_input)
                print('Verified Codex native notify: exec/resume and interactive turns, thread/turn IDs, tool result, per-turn usage, interruption and exit drain.')
        finally:
            subprocess.run(['podman', 'rm', '--force', '--ignore', agent_name], capture_output=True)
            subprocess.run(['podman', 'network', 'rm', network], capture_output=True)


if __name__ == "__main__":
    unittest.main()
