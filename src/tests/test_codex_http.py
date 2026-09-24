"""Synthetic native Responses HTTP transport observations."""
import asyncio
import gzip
import json
from pathlib import Path
import tempfile
import unittest

from src.proxy.live_capture import JsonlEmitter, LiveCapture, _selected
from src.server.codex_context import CodexContext
from src.server.codex_http import CodexHttpContext
from src.server.context import ContextEventStream
from src.tests.test_live_capture import flow


class CodexHttpTests(unittest.TestCase):
    def fixture(self, root, *, compressed=False):
        addon = LiveCapture(JsonlEmitter(root / "events.jsonl", "session-test"), root / "archive.jsonl")
        item = flow()
        item.request.pretty_host = "chatgpt.com"
        item.request.pretty_url = "https://chatgpt.com/backend-api/codex/responses"
        item.request.raw_content = b'{"model":"synthetic","input":[{"role":"user","content":"hello"}],"tools":[]}'
        records = [
            {"type": "response.output_item.done", "output_index": 0, "item": {
                "type": "message", "content": [{"type": "output_text", "text": "synthetic reply"}]}},
            {"type": "response.completed", "response": {"id": "synthetic-response", "usage": {
                "input_tokens": 20, "output_tokens": 3, "input_tokens_details": {"cached_tokens": 12}}}},
        ]
        raw = ''.join('data: ' + json.dumps(value) + '\n\n' for value in records).encode()
        item.response.headers['content-type'] = 'text/event-stream'
        if compressed:
            raw = gzip.compress(raw)
            item.response.headers['content-encoding'] = 'gzip'
        addon.request(item)
        addon.responseheaders(item)
        for chunk in (raw[:7], raw[7:], b''):
            item.response.stream(chunk)
        addon.response(item)
        return [json.loads(line) for line in (root / 'events.jsonl').read_text().splitlines()], raw

    def test_split_compressed_stream_usage_and_exact_http_evidence(self):
        for compressed in (False, True):
            with self.subTest(compressed=compressed), tempfile.TemporaryDirectory() as directory:
                events, raw = self.fixture(Path(directory), compressed=compressed)
                adapter = CodexHttpContext(CodexContext())
                observed = [result for event in events if adapter.handles(event) for result in adapter.consume(event)]
                self.assertEqual([item['kind'] for item in observed], ['context.diff', 'context.response', 'context.usage'])
                self.assertEqual(observed[0]['exact_request']['transport'], 'http')
                response = observed[1]
                self.assertEqual(response['correlation'], {'basis': 'exact_http_flow_id', 'confidence': 'high'})
                self.assertEqual(response['response']['content_blocks'], [{'type': 'text', 'text': 'synthetic reply'}])
                self.assertEqual(response['exact_response']['body']['wire']['byte_length'], len(raw))
                self.assertEqual(observed[2]['used_input_tokens'], 20)
                self.assertEqual(observed[2]['components']['uncached_input_tokens'], 8)
                self.assertIsNone(observed[2]['percent'])

    def test_missing_block_does_not_report_success_or_usage(self):
        with tempfile.TemporaryDirectory() as directory:
            events, _ = self.fixture(Path(directory))
            events = [event for event in events if not (event['kind'] == 'response.block' and event['payload']['block_index'] == 0)]
            adapter = CodexHttpContext(CodexContext())
            observed = [result for event in events if adapter.handles(event) for result in adapter.consume(event)]
            self.assertEqual(observed[-1]['response']['stop_reason'], 'capture_gap')
            self.assertFalse(any(item['kind'] == 'context.usage' for item in observed))

    def test_route_excludes_auth_and_query_variants(self):
        item = flow()
        item.request.pretty_host = 'chatgpt.com'
        for suffix in ('responses?access_token=synthetic', 'responses?other=value', 'responses/../auth/token', 'auth/token'):
            item.request.pretty_url = 'https://chatgpt.com/backend-api/codex/' + suffix
            self.assertFalse(_selected(item))

    def test_stream_replay_does_not_normalize_codex_tools_as_claude(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            async def collect():
                results = []
                stream = ContextEventStream(root / 'events.jsonl', 'session-test').events(mark_ready=True)
                try:
                    async for event in stream:
                        if event.get('type') == 'replay-ready':
                            break
                        results.append(event)
                finally:
                    await stream.aclose()
                return results
            # Bound the collector so a replay marker regression fails instead of hanging.
            results = asyncio.run(asyncio.wait_for(collect(), timeout=2))
            diffs = [item for item in results if item.get('kind') == 'context.diff']
            self.assertEqual(len(diffs), 1)
            self.assertEqual(diffs[0]['provider'], 'codex')
