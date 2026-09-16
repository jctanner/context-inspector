import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from fastapi import HTTPException, Response
from src.server.workspace_files import inspect_workspace, MAX_BYTES
from src.server.app import create_app
from src.server.config import Settings


class WorkspaceFilesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / ".context").mkdir()
        (self.root / ".context/config.json").write_text('{"fixture": true}')
        (self.root / "note.txt").write_text("<script>alert(1)</script>\n☃", encoding="utf-8")

    def test_listing_hidden_nested_and_pagination(self):
        for i in range(230): (self.root / f"item-{i:03d}.txt").write_text("")
        names, cursor = [], ""
        while True:
            page = inspect_workspace(self.root, "list", after=cursor, limit=30)
            self.assertLessEqual(len(page["entries"]), 30)
            names.extend(item["name"] for item in page["entries"])
            cursor = page["next_cursor"]
            if cursor is None: break
        self.assertEqual(len(names), 232)
        self.assertEqual(len(set(names)), 232)
        self.assertEqual(names[0], ".context")
        nested = inspect_workspace(self.root, "list", ".context")
        self.assertEqual(nested["entries"][0]["path"], ".context/config.json")

    def test_exact_read_metadata_and_empty_file(self):
        file = inspect_workspace(self.root, "read", "note.txt")
        self.assertEqual(file["content"], "<script>alert(1)</script>\n☃")
        self.assertEqual(file["size"], len(file["content"].encode()))
        self.assertIn("modified_at", file)
        (self.root / "empty").write_bytes(b"")
        self.assertEqual(inspect_workspace(self.root, "read", "empty")["content"], "")

    def test_paths_and_operations_rejected(self):
        for path in ("../secret", "/etc/passwd", "x/../note.txt", ".", "x//y", "x\\y", "x\x00"):
            with self.assertRaises(HTTPException): inspect_workspace(self.root, "read", path)
        with self.assertRaises(HTTPException): inspect_workspace(self.root, "write", "note.txt")
        with self.assertRaises(HTTPException): inspect_workspace(self.root, "read", "")

    def test_links_and_special_files_cannot_be_read(self):
        (self.root / "link").symlink_to(self.root / "note.txt")
        (self.root / "dirlink").symlink_to(self.root / ".context")
        os.link(self.root / "note.txt", self.root / "hardlink")
        os.mkfifo(self.root / "fifo")
        for path in ("link", "dirlink/config.json", "hardlink", "fifo"):
            with self.assertRaises(HTTPException): inspect_workspace(self.root, "read", path)
        with self.assertRaises(HTTPException): inspect_workspace(self.root, "list", "dirlink")
        entries = {e["name"]: e for e in inspect_workspace(self.root, "list")["entries"]}
        for path in ("link", "dirlink", "hardlink", "fifo"):
            self.assertFalse(entries[path]["accessible"])

    def test_missing_large_binary_and_symlinked_root(self):
        for name, content, status in (("big", b"x" * (MAX_BYTES + 1), 413),
                                      ("binary", b"x\x00", 415), ("invalid", b"\xff", 415)):
            (self.root / name).write_bytes(content)
            with self.assertRaises(HTTPException) as error: inspect_workspace(self.root, "read", name)
            self.assertEqual(error.exception.status_code, status)
        with self.assertRaises(HTTPException) as error: inspect_workspace(self.root, "read", "gone")
        self.assertEqual(error.exception.status_code, 404)
        self.assertNotIn(str(self.root), error.exception.detail)
        alias = self.root / "alias"
        alias.symlink_to(self.root)
        with self.assertRaises(HTTPException): inspect_workspace(alias, "list")


class WorkspaceRouteTests(unittest.IsolatedAsyncioTestCase):
    async def test_get_only_routes_without_active_session(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "fixture.txt").write_text("fixture")
            app = create_app(settings=Settings(workspace=root, command_override=("true",)), manager=SimpleNamespace())
            routes = [r for r in app.routes if r.path.startswith("/api/workspace")]
            self.assertEqual(len(routes), 2)
            self.assertTrue(all(r.methods == {"GET"} for r in routes))
            listing = next(r.endpoint for r in routes if r.path == "/api/workspace")
            read = next(r.endpoint for r in routes if r.path.endswith("/file"))
            response = Response()
            self.assertEqual((await listing(response, "", "", 100))["entries"][0]["name"], "fixture.txt")
            self.assertEqual(response.headers["Cache-Control"], "no-store")
            self.assertEqual((await read(Response(), "fixture.txt"))["content"], "fixture")


if __name__ == "__main__": unittest.main()
