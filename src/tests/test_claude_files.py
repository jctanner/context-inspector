import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi import HTTPException, Response
from src.server.app import create_app
from src.server.config import Settings


class ClaudeFilesTests(unittest.IsolatedAsyncioTestCase):
    async def test_read_only_mirror_without_session_and_boundary_checks(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            root = home / ".claude"
            root.mkdir()
            (home / "outside.txt").write_text("must not escape")
            (root / "projects/p/memory").mkdir(parents=True)
            (root / "projects/p/memory/MEMORY.md").write_text("memory fixture")
            (root / ".settings.json").write_text('{"fixture": true}')
            (root / ".credentials.json").write_text('{"oauth_token":"synthetic-secret"}')
            (root / "link").symlink_to(home / "outside.txt")
            (root / "dirlink").symlink_to(home)
            os.link(home / "outside.txt", root / "hardlink")
            os.mkfifo(root / "fifo")
            with patch("src.server.app.CLAUDE_HOME", home):
                app = create_app(settings=Settings(workspace=home, command_override=("true",)), manager=SimpleNamespace())
                routes = [r for r in app.routes if r.path.startswith("/api/claude-files")]
                self.assertEqual(len(routes), 2)
                self.assertTrue(all(r.methods == {"GET"} for r in routes))
                listing = next(r.endpoint for r in routes if not r.path.endswith("/file"))
                read = next(r.endpoint for r in routes if r.path.endswith("/file"))
                response = Response()
                page = await listing(response, "", "", 100)
                self.assertEqual(response.headers["Cache-Control"], "no-store")
                names = {e["name"] for e in page["entries"]}
                self.assertIn(".settings.json", names)
                self.assertNotIn(".credentials.json", names)
                self.assertNotIn("outside.txt", names)
                self.assertEqual((await read(Response(), "projects/p/memory/MEMORY.md"))["content"], "memory fixture")
                self.assertEqual((await read(Response(), ".settings.json"))["content"], '{"fixture": true}')
                with self.assertRaises(HTTPException) as hidden_credential:
                    await read(Response(), ".credentials.json")
                self.assertEqual(hidden_credential.exception.status_code, 404)
                self.assertNotIn("synthetic-secret", hidden_credential.exception.detail)
                for path in ("../outside.txt", "/etc/passwd", "link", "dirlink/outside.txt", "hardlink", "fifo", "missing"):
                    with self.subTest(path=path), self.assertRaises(HTTPException) as error:
                        await read(Response(), path)
                    self.assertEqual(error.exception.headers["Cache-Control"], "no-store")
                    self.assertNotIn(str(home), error.exception.detail)

    async def test_missing_root_does_not_create_files_or_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            with patch("src.server.app.CLAUDE_HOME", home):
                app = create_app(settings=Settings(workspace=home, command_override=("true",)), manager=SimpleNamespace())
                listing = next(r.endpoint for r in app.routes if r.path == "/api/claude-files")
                with self.assertRaises(HTTPException) as error:
                    await listing(Response(), "", "", 100)
                self.assertEqual(error.exception.status_code, 404)
                self.assertFalse((home / ".claude").exists())
