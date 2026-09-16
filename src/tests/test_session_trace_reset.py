import asyncio
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException
from src.server.app import create_app, CreateSessionRequest
from src.server.config import Settings
from src.server.startup_reset import clear_session_traces


class SessionTraceResetTests(unittest.IsolatedAsyncioTestCase):
    async def test_stop_start_clears_only_traces_and_join_preserves_them(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            trace = root / 'container/strace'
            (trace / '.nested').mkdir(parents=True)
            (trace / '.nested/pid.1').write_text('old trace')
            home = root / 'container/home/evaluator/.claude'
            home.mkdir(parents=True)
            memory = home / 'history.jsonl'
            memory.write_text('preserve home state')
            (trace / 'link').symlink_to(memory)
            active = None

            def create(argv, **kwargs):
                nonlocal active
                self.assertEqual(list(trace.iterdir()), [])
                (trace / 'pid.2').write_text('new trace')
                active = SimpleNamespace(id=kwargs['session_id'], pid=123, argv=argv, alive=True)
                return active

            async def stop(_):
                nonlocal active
                active = None
                return True

            manager = SimpleNamespace(active=lambda: active, create=Mock(side_effect=create), stop=stop)
            app = create_app(settings=Settings(workspace=root, state_dir=root / 'state'), manager=manager)
            start = next(r.endpoint for r in app.routes if r.path == '/api/sessions')
            stop_route = next(r.endpoint for r in app.routes if r.path == '/api/sessions/{session_id}' and 'DELETE' in r.methods)
            with patch('src.server.startup_reset.PROJECT_ROOT', root), \
                 patch('src.server.startup_reset.assert_home_unused') as unused, redirect_stdout(StringIO()):
                first = await start(CreateSessionRequest())
                second = await start(CreateSessionRequest())
                self.assertEqual(first.session_id, second.session_id)
                unused.assert_called_once_with(trace)
                self.assertEqual((trace / 'pid.2').read_text(), 'new trace')
                await stop_route(first.session_id)
                self.assertTrue((trace / 'pid.2').exists())
                third = await start(CreateSessionRequest())
                self.assertNotEqual(first.session_id, third.session_id)
                self.assertEqual(manager.create.call_count, 2)
                self.assertEqual(memory.read_text(), 'preserve home state')

    async def test_failed_cleanup_prevents_launch_and_override_skips_cleanup(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manager = SimpleNamespace(active=lambda: None, create=Mock(return_value=SimpleNamespace(id='fixture', pid=123, argv=('true',))))
            with patch('src.server.app.clear_session_traces', side_effect=RuntimeError('active container')) as clear:
                app = create_app(settings=Settings(workspace=root, state_dir=root / 'state'), manager=manager)
                start = next(r.endpoint for r in app.routes if r.path == '/api/sessions')
                with self.assertRaises(HTTPException) as error:
                    await start(CreateSessionRequest())
                self.assertEqual(error.exception.status_code, 409)
                manager.create.assert_not_called()
                clear.assert_called_once()
                app = create_app(settings=Settings(workspace=root, state_dir=root / 'state', command_override=('true',)), manager=manager)
                start = next(r.endpoint for r in app.routes if r.path == '/api/sessions')
                await start(CreateSessionRequest())
                clear.assert_called_once()

    async def test_concurrent_starts_share_one_cleanup_and_session(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            active = None
            started, release = asyncio.Event(), asyncio.Event()

            def create(argv, **kwargs):
                nonlocal active
                active = SimpleNamespace(id=kwargs['session_id'], pid=123, argv=argv)
                return active

            async def worker(*_):
                started.set()
                await release.wait()

            manager = SimpleNamespace(active=lambda: active, create=Mock(side_effect=create))
            app = create_app(settings=Settings(workspace=root, state_dir=root / 'state'), manager=manager)
            start = next(r.endpoint for r in app.routes if r.path == '/api/sessions')
            with patch('src.server.app.asyncio.to_thread', side_effect=worker) as cleanup:
                first = asyncio.create_task(start(CreateSessionRequest()))
                await started.wait()
                second = asyncio.create_task(start(CreateSessionRequest()))
                await asyncio.sleep(0)
                cleanup.assert_called_once()
                release.set()
                results = await asyncio.gather(first, second)
                self.assertEqual(results[0].session_id, results[1].session_id)
                manager.create.assert_called_once()
                cleanup.assert_called_once()


class SessionTraceGuardTests(unittest.TestCase):
    def test_active_mount_and_symlink_prevent_deletion(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            trace = root / 'container/strace'
            trace.mkdir(parents=True)
            keep = trace / 'pid.1'
            keep.write_text('keep')
            with patch('src.server.startup_reset.PROJECT_ROOT', root):
                with patch('src.server.startup_reset.assert_home_unused', side_effect=RuntimeError('active')):
                    with self.assertRaises(RuntimeError): clear_session_traces()
                self.assertTrue(keep.exists())
                with patch('src.server.startup_reset.assert_home_unused'), \
                     patch('src.server.startup_reset._assert_no_mounted_targets', side_effect=RuntimeError('mounted')):
                    with self.assertRaises(RuntimeError): clear_session_traces()
                self.assertTrue(keep.exists())
                trace.rename(root / 'outside')
                trace.symlink_to(root / 'outside', target_is_directory=True)
                with self.assertRaises(OSError): clear_session_traces()
                self.assertEqual((root / 'outside/pid.1').read_text(), 'keep')
