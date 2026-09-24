import json
from pathlib import Path
import tempfile
import unittest

from src.server.codex_window import read_catalog, session_catalog, usage_window
from src.server.codex_context import CodexContext
from src.server.codex_http import CodexHttpContext
from src.tests.test_codex_context import Wire
from src.tests import test_codex_http


class CodexWindowTests(unittest.TestCase):
    def test_snapshot_validation_and_replay_stability(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            cache = root / 'models.json'
            cache.write_text(json.dumps({'fetched_at': 'fixture-date', 'models': [
                {'slug': 'fixture', 'context_window': 272000, 'max_context_window': 872000,
                 'effective_context_window_percent': 95},
                {'slug': 'invalid', 'context_window': True, 'effective_context_window_percent': 95},
                {'slug': 'missing-percent', 'context_window': 272000}]}))
            snapshot = session_catalog(root / 'session', cache)
            self.assertEqual(set(snapshot), {'fixture'})
            self.assertEqual(snapshot['fixture']['tokens'], 258400)
            self.assertIn('fixture-date', snapshot['fixture']['source'])
            cache.write_text('{}')
            self.assertEqual(session_catalog(root / 'session', cache), snapshot)
            self.assertEqual(read_catalog(cache), {})
            self.assertEqual((root / 'session/codex-context-windows.json').stat().st_mode & 0o777, 0o600)

    def test_ws_model_changes_unknown_and_override(self):
        wire = Wire()
        catalog = {'first': {'tokens': 258400, 'source': 'catalog fixture'},
                   'second': {'tokens': 100000, 'source': 'catalog fixture'}}
        adapter = CodexContext(catalog=catalog)
        for model, expected in [('first', 10), ('second', 25.84), ('unknown', None)]:
            adapter.consume(wire.create(model=model))
            adapter.consume(wire.server(rid=model))
            usage = adapter.consume(wire.server('completed', rid=model, usage={'input_tokens': 25840}))[-1]
            if expected is None:
                self.assertIsNone(usage['percent'])
            else:
                self.assertAlmostEqual(usage['percent'], expected)
        request = {'body': {'decoded': {'value': {'model': 'first'}}}}
        self.assertEqual(usage_window(request, 50, catalog, 100, 'explicit')['percent'], 50)
        self.assertEqual(usage_window(request, None, catalog, None, '')['percent'], None)

    def test_http_uses_same_effective_budget(self):
        with tempfile.TemporaryDirectory() as root:
            events, _ = test_codex_http.CodexHttpTests().fixture(Path(root))
            adapter = CodexHttpContext(CodexContext(catalog={
                'synthetic': {'tokens': 200, 'source': 'catalog fixture'}}))
            results = [result for event in events if adapter.handles(event) for result in adapter.consume(event)]
            self.assertEqual(results[-1]['percent'], 10)
            self.assertEqual(results[-1]['context_window_source'], 'catalog fixture')
