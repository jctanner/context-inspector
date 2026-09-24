import io
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from uuid import uuid4

from fastapi import HTTPException, Response
from src.server.app import create_app
from src.server.config import Settings
from src.server.mlflow import MLflowSettings, mlflow_service, RUNTIME_KEYS
from src.server.mlflow_traces import MLflowTraces

ENV = {'CONTEXT_INSPECTOR_MLFLOW_ENABLED': '1', 'CONTEXT_INSPECTOR_MLFLOW_TRACING_ENABLED': '1',
       'CONTEXT_INSPECTOR_MLFLOW_CONTAINER': 'context-inspector-mlflow-' + 'a' * 32,
       'CONTEXT_INSPECTOR_MLFLOW_EXPERIMENT_ID': '9'}
INFO = {'trace_id': 'tr-fixture', 'state': 'OK',
        'trace_location': {'mlflow_experiment': {'experiment_id': '9'}},
        'trace_metadata': {'mlflow.trace.session': 'native-session', 'codex.turn_id': 'turn-1',
                           'mlflow.trace.tokenUsage': '{"input_tokens": 20}'},
        'request_preview': '"fixture input"'}


class MLflowTraceTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, ENV)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.client = MLflowTraces()

    def test_status_and_no_unmanaged_endpoint(self):
        self.assertTrue(self.client.status()['available'])
        with patch.dict(os.environ, {'CONTEXT_INSPECTOR_MLFLOW_CONTAINER': ''}):
            client = MLflowTraces()
            self.assertFalse(client.status()['available'])
            with patch.object(client, '_request') as fetch, self.assertRaises(HTTPException):
                client.search()
            fetch.assert_not_called()
        with patch.dict(os.environ, {'CONTEXT_INSPECTOR_MLFLOW_ENABLED': '0'}):
            self.assertIn('disabled', MLflowTraces().status()['message'])

    def test_search_scoped_paged_and_ids_not_sql(self):
        with patch.object(self.client, '_request', return_value={'traces': [INFO], 'next_page_token': 'next'}) as fetch:
            result = self.client.search('native-session', 'page')
            self.assertEqual(result['next_page_token'], 'next')
            self.assertEqual(result['traces'][0]['usage'], {'input_tokens': 20})
            self.assertEqual(result['traces'][0]['request_preview'], 'fixture input')
            body = fetch.call_args.args[1]
            self.assertEqual(body['locations'], [{'mlflow_experiment': {'experiment_id': '9'}}])
            self.assertEqual(body['page_token'], 'page')
            self.assertIn('native-session', body['filter'])
            for bad in ("' OR 1=1", '../../secret', 'http://evil', 'x\n'):
                with self.assertRaises(HTTPException):
                    self.client.search(bad)
                with self.assertRaises(HTTPException):
                    self.client.detail(bad)

    def test_detail_uses_artifact_and_preserves_nanosecond_text(self):
        span = {'name': 'llm', 'context': {'span_id': 's1'}, 'parent_id': None,
                'start_time_ns': 1760000000000000001, 'end_time_ns': 1760000000000000021,
                'attributes': {'mlflow.spanType': '"LLM"', 'mlflow.spanInputs': '{"prompt":"fixture"}'}}
        with patch.object(self.client, '_request', side_effect=[{'trace': {'trace_info': INFO}}, {'spans': [span]}]) as fetch:
            result = self.client.detail('tr-fixture')
            self.assertEqual(result['spans'][0]['inputs'], {'prompt': 'fixture'})
            self.assertEqual(result['spans'][0]['start_ns'], '1760000000000000001')
            self.assertIn('1760000000000000001', result['raw'])
            self.assertIn('/ajax-api/3.0/mlflow/get-trace-artifact?', fetch.call_args.args[0])

    def test_detail_rejects_dot_segments(self):
        for value in (".", ".."):
            with self.assertRaises(HTTPException):
                self.client.detail(value)

    def test_detail_rejects_other_experiment_before_artifact(self):
        with patch.object(self.client, '_request', return_value={'trace': {'trace_info': {**INFO, 'trace_location': {}}}}) as fetch:
            with self.assertRaises(HTTPException) as error:
                self.client.detail('tr-fixture')
            self.assertEqual(error.exception.status_code, 404)
            self.assertEqual(fetch.call_count, 1)

    def test_request_is_fixed_loopback_bypasses_proxy_and_bounds_response(self):
        with patch.object(self.client.opener, 'open', return_value=io.BytesIO(b'{}')) as request:
            self.client._request('/api/3.0/mlflow/traces/search', {})
            self.assertTrue(request.call_args.args[0].full_url.startswith('http://127.0.0.1:'))
            self.assertEqual(request.call_args.kwargs['timeout'], 10)
        with patch('src.server.mlflow_traces.MAX_BYTES', 2), \
             patch.object(self.client.opener, 'open', return_value=io.BytesIO(b'{"large":true}')):
            with self.assertRaises(HTTPException) as error:
                self.client._request('/fixture')
            self.assertEqual(error.exception.status_code, 502)
        for error in (URLError('private upstream detail'), HTTPError('private', 500, 'private', {}, None)):
            with patch.object(self.client.opener, 'open', side_effect=error), self.assertRaises(HTTPException) as caught:
                self.client._request('/fixture')
            self.assertNotIn('private', caught.exception.detail)


class MLflowTraceAPITests(unittest.IsolatedAsyncioTestCase):
    async def test_endpoints_are_read_only_no_store_and_need_no_agent_session(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, ENV):
            app = create_app(settings=Settings(workspace=Path(directory), command_override=('true',)))
            for path in ('/api/mlflow/status', '/api/mlflow/traces', '/api/mlflow/traces/{trace_id}'):
                self.assertEqual(next(r.methods for r in app.routes if r.path == path), {'GET'})
            endpoint = next(r.endpoint for r in app.routes if r.path == '/api/mlflow/traces')
            response = Response()
            with patch('src.server.mlflow_traces.MLflowTraces.search', return_value={'traces': []}):
                self.assertEqual(await endpoint(response, '', ''), {'traces': []})
            self.assertEqual(response.headers['Cache-Control'], 'no-store')
            with patch('src.server.mlflow_traces.MLflowTraces.search', side_effect=HTTPException(503, 'unavailable')):
                with self.assertRaises(HTTPException) as caught:
                    await endpoint(Response(), '', '')
                self.assertEqual(caught.exception.headers['Cache-Control'], 'no-store')


@unittest.skipUnless(os.environ.get('CONTEXT_INSPECTOR_TEST_MLFLOW') == '1', 'opt-in Podman integration')
class MLflowRESTTests(unittest.TestCase):
    def test_real_search_session_filter_and_span_artifact(self):
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            port = listener.getsockname()[1]
        network = 'ci-mlflow-view-' + uuid4().hex
        settings = MLflowSettings(port=port, network=network)
        try:
            with mlflow_service(settings), patch.dict(os.environ, {'CONTEXT_INSPECTOR_MLFLOW_PORT': str(port)}):
                name, experiment, _ = [os.environ[k] for k in RUNTIME_KEYS]
                seed = '''
import mlflow, sys
mlflow.set_tracking_uri('http://127.0.0.1:5000')
mlflow.set_experiment(experiment_id=sys.argv[1])
with mlflow.start_span(name='fixture turn', span_type='AGENT') as root:
    root.set_inputs('fixture question')
    root.set_outputs('fixture answer')
    mlflow.update_current_trace(metadata={'mlflow.trace.session':'native-fixture', 'codex.turn_id':'turn-1'})
    with mlflow.start_span(name='fixture tool', span_type='TOOL') as child:
        child.set_inputs({'text':'<script>fixture</script>'})
        child.set_outputs('fixture result')
mlflow.flush_trace_async_logging()
'''
                subprocess.run(['podman', 'exec', name, 'python', '-c', seed, experiment], check=True,
                               capture_output=True, text=True, timeout=30)
                client = MLflowTraces()
                traces = client.search()['traces']
                self.assertEqual(len(traces), 1)
                self.assertEqual(client.search('native-fixture')['traces'][0]['trace_id'], traces[0]['trace_id'])
                self.assertEqual(client.search('absent')['traces'], [])
                detail = client.detail(traces[0]['trace_id'])
                self.assertEqual(len(detail['spans']), 2)
                tool = next(s for s in detail['spans'] if s['type'] == 'TOOL')
                self.assertEqual(tool['inputs'], {'text': '<script>fixture</script>'})
                self.assertEqual(tool['outputs'], 'fixture result')
                self.assertTrue(tool['start_ns'].isdigit(), tool['start_ns'])
                root = next(s for s in detail['spans'] if s['type'] == 'AGENT')
                self.assertEqual(tool['parent_id'], root['id'])
                print('Verified REST search, native session filter, trace metadata and span artifact against MLflow v3.16.0.')
        finally:
            subprocess.run(['podman', 'network', 'rm', network], capture_output=True)


if __name__ == '__main__':
    unittest.main()
