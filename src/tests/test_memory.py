from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi import HTTPException, Response
from src.server.memory_files import inspect_memory, MemoryError, MAX_BYTES
from src.server.app import create_app
from src.server.config import Settings
from src.server.memory import get_memory


class MemoryReaderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.root = self.home / ".claude"
        self.folder = self.root / "projects" / "-workspace" / "memory"
        self.folder.mkdir(parents=True)
        (self.folder / "MEMORY.md").write_text("# Memory\n<unsafe> stays text", encoding="utf-8")
        (self.root / "CLAUDE.md").write_text("Global instructions")
        (self.root / ".credentials.json").write_text("SECRET")
        (self.root / "projects" / "-workspace" / "transcript.jsonl").write_text("PRIVATE")

    def test_allowlisted_listing_and_exact_read(self):
        listing = inspect_memory("list", home=self.home)
        self.assertEqual([f["path"] for f in listing["files"]], ["CLAUDE.md", "projects/-workspace/memory/MEMORY.md"])
        result = inspect_memory("read", "projects/-workspace/memory/MEMORY.md", home=self.home)
        self.assertEqual(result["content"], "# Memory\n<unsafe> stays text")
        self.assertEqual(result["size"], len(result["content"].encode()))
        self.assertIn("modified_at", result)

    def test_arbitrary_paths_and_mutation_actions_rejected(self):
        for path in ["/etc/passwd", "../.credentials.json", ".credentials.json", "projects/-workspace/transcript.jsonl",
                     "projects/-workspace/memory/../../CLAUDE.md", "projects//memory/a.md", "projects/x/memory/a\\b.md", "projects/x/memory/a\x00.md"]:
            with self.subTest(path=repr(path)), self.assertRaises(MemoryError):
                inspect_memory("read", path, home=self.home)
        for action in ["write", "delete", "create", "rename"]:
            with self.assertRaises(MemoryError): inspect_memory(action, home=self.home)

    def test_symlinks_and_hardlinks_are_not_exposed(self):
        (self.folder / "link.md").symlink_to(self.root / ".credentials.json")
        (self.folder / "escape").symlink_to(self.root, target_is_directory=True)
        os.link(self.root / ".credentials.json", self.folder / "hard.md")
        listing = inspect_memory("list", home=self.home)
        self.assertEqual(len(listing["files"]), 2)
        for path in ["link.md", "escape/CLAUDE.md", "hard.md"]:
            with self.assertRaises((MemoryError, OSError)):
                inspect_memory("read", f"projects/-workspace/memory/{path}", home=self.home)

    def test_symlinked_root_or_project_is_not_followed(self):
        (self.root / "projects" / "linked").symlink_to(self.root / "projects" / "-workspace", target_is_directory=True)
        self.assertEqual(len(inspect_memory("list", home=self.home)["files"]), 2)
        alias = self.home / "alias"
        alias.symlink_to(self.home, target_is_directory=True)
        with self.assertRaises(OSError): inspect_memory("list", home=alias)

    def test_limits_binary_and_special_files(self):
        (self.folder / "big.md").write_bytes(b"x" * (MAX_BYTES + 1))
        (self.folder / "binary.md").write_bytes(b"\xff\x00")
        os.mkfifo(self.folder / "pipe.md")
        for name, status in [("big.md", 413), ("binary.md", 415), ("pipe.md", 400)]:
            with self.assertRaises(MemoryError) as raised:
                inspect_memory("read", f"projects/-workspace/memory/{name}", home=self.home)
            self.assertEqual(raised.exception.status, status)
        with patch("src.server.memory_files.MAX_FILES", 1):
            self.assertTrue(inspect_memory("list", home=self.home)["truncated"])

    def test_missing_memory_and_deleted_file(self):
        self.assertEqual(inspect_memory("list", home=self.home / "absent")["files"], [])
        with self.assertRaises(FileNotFoundError):
            inspect_memory("read", "projects/-workspace/memory/gone.md", home=self.home)


SID = "session-" + "a" * 32
class LocalMemoryTests(unittest.TestCase):
    def test_direct_mirror_reads_without_subprocess_or_host_home(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            (home / ".claude").mkdir()
            (home / ".claude" / "CLAUDE.md").write_text("Local fixture")
            with patch("src.server.memory.CLAUDE_HOME", home), patch("subprocess.run", side_effect=AssertionError("No container APIs")), patch.dict(os.environ, {"HOME": "/must-not-read"}):
                self.assertEqual(get_memory(SID)["files"][0]["path"], "CLAUDE.md")
                self.assertEqual(get_memory(SID, "CLAUDE.md")["content"], "Local fixture")
                with self.assertRaises(HTTPException): get_memory(SID, "../secret")

    def test_missing_file_error_does_not_expose_host_paths(self):
        with tempfile.TemporaryDirectory() as directory, patch("src.server.memory.CLAUDE_HOME", Path(directory)):
            with self.assertRaises(HTTPException) as error: get_memory(SID, "CLAUDE.md")
            self.assertNotIn(directory, error.exception.detail)


class MemoryRouteTests(unittest.IsolatedAsyncioTestCase):
    async def test_routes_are_get_only_active_scoped_and_no_store(self):
        session = SimpleNamespace(id=SID)
        manager = SimpleNamespace(active=lambda: session)
        app = create_app(settings=Settings(), manager=manager)
        routes = [r for r in app.routes if "/memory" in r.path]
        self.assertEqual(len(routes), 2)
        for route in routes:
            self.assertEqual(route.methods, {"GET"})
        endpoint = next(r.endpoint for r in routes if r.path.endswith("/memory"))
        with patch("src.server.app.get_memory", return_value={"files": []}) as reader:
            response = Response()
            self.assertEqual(await endpoint(SID, response), {"files": []})
            self.assertEqual(response.headers["Cache-Control"], "no-store")
            with self.assertRaises(HTTPException) as raised:
                await endpoint("other", Response())
            self.assertEqual(raised.exception.status_code, 404)
            self.assertEqual(reader.call_count, 1)
        with patch("src.server.app.get_memory", side_effect=HTTPException(413, "Too large")):
            with self.assertRaises(HTTPException) as raised:
                await endpoint(SID, Response())
            self.assertEqual(raised.exception.headers["Cache-Control"], "no-store")
        with patch("src.server.app.get_memory", side_effect=lambda *args: setattr(manager, "active", lambda: None) or {}):
            with self.assertRaises(HTTPException) as raised:
                await endpoint(SID, Response())
            self.assertEqual(raised.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
