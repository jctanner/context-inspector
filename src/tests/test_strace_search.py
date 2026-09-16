import asyncio
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi import HTTPException, Response
from src.server.strace_search import search_traces
from src.server.app import create_app
from src.server.config import Settings


class StraceSearchTests(unittest.TestCase):
    def test_literal_lines_recursive_hidden_and_no_link_escape(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'strace'
            (root / '.nested').mkdir(parents=True)
            (root / 'pid.1').write_text('first\nopenat("SKILL.md")\nSKILLXmd\n')
            (root / '.nested/pid.2').write_text('SKILL.md <script>\n')
            outside = Path(temp) / 'secret'
            outside.write_text('SKILL.md outside')
            (root / 'link').symlink_to(outside)
            (root / 'dirlink').symlink_to(Path(temp))
            os.link(outside, root / 'hardlink')
            os.mkfifo(root / 'fifo')
            result = search_traces(root, 'SKILL.md')
            self.assertEqual({(m['path'], m['line']) for m in result['matches']},
                             {('pid.1', 2), ('.nested/pid.2', 1)})
            self.assertEqual(result['files_scanned'], 2)
            self.assertTrue(result['partial'])
            self.assertFalse(search_traces(root, 'skill.md')['matches'])
            for query in ('', '\n', '\x00', 'x' * 1025):
                with self.assertRaises(HTTPException):
                    search_traces(root, query)

    def test_limits_missing_root_and_root_symlink(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'strace'
            self.assertTrue(search_traces(root, 'x')['missing'])
            self.assertFalse(root.exists())
            root.mkdir()
            (root / 'pid.1').write_text('x\nx\nx\n')
            with patch('src.server.strace_search.MAX_RESULTS', 2):
                result = search_traces(root, 'x')
                self.assertEqual(len(result['matches']), 2)
                self.assertTrue(result['partial'])
            with patch('src.server.strace_search.MAX_BYTES', 2):
                result = search_traces(root, 'x')
                self.assertEqual(result['bytes_scanned'], 2)
                self.assertTrue(result['partial'])
            with patch('src.server.strace_search.MAX_SECONDS', 0):
                self.assertTrue(search_traces(root, 'x')['partial'])
            (root / 'pid.1').write_text('x' * 100 + '\nx\n')
            with patch('src.server.strace_search.MAX_LINE', 32):
                result = search_traces(root, 'x')
                self.assertEqual(result['matches'], [{'path': 'pid.1', 'line': 2, 'text': 'x'}])
                self.assertTrue(result['partial'])
            link = Path(temp) / 'link'
            link.symlink_to(root)
            with self.assertRaises(HTTPException):
                search_traces(link, 'x')


class StraceSearchAPITests(unittest.IsolatedAsyncioTestCase):
    async def test_read_only_fixed_root_without_session(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'strace').mkdir()
            (root / 'strace/pid.1').write_text('fixture\n')
            with patch('src.server.app.CONTAINER_ROOT', root):
                app = create_app(settings=Settings(workspace=root, command_override=('true',)), manager=SimpleNamespace())
                route = next(r for r in app.routes if r.path == '/api/strace/search')
                self.assertEqual(route.methods, {'GET'})
                response = Response()
                result = await route.endpoint(response, 'fixture')
                self.assertEqual(response.headers['Cache-Control'], 'no-store')
                self.assertEqual(result['matches'][0]['path'], 'pid.1')
                self.assertFalse(result['partial'])
                with self.assertRaises(HTTPException) as error:
                    await route.endpoint(Response(), '\n')
                self.assertEqual(error.exception.headers['Cache-Control'], 'no-store')

    async def test_concurrent_search_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            app = create_app(settings=Settings(workspace=Path(temp), command_override=('true',)), manager=SimpleNamespace())
            endpoint = next(r.endpoint for r in app.routes if r.path == '/api/strace/search')
            started, release = asyncio.Event(), asyncio.Event()

            async def worker(*args):
                started.set()
                await release.wait()
                return {'matches': []}

            with patch('src.server.app.asyncio.to_thread', side_effect=worker):
                first = asyncio.create_task(endpoint(Response(), 'one'))
                await started.wait()
                try:
                    with self.assertRaises(HTTPException) as error:
                        await endpoint(Response(), 'two')
                    self.assertEqual(error.exception.status_code, 429)
                finally:
                    release.set()
                    await first
