import asyncio
import json
import os
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace

from fastapi import HTTPException, Response
from pydantic import ValidationError
from src.server.app import create_app, MCPCountRequest
from src.server.config import Settings
from src.server.mcp_config import get_count, set_count


class MCPConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / ".context/mcp-dump/config.json"

    def test_default_create_and_large_count_preserves_fields(self):
        current = get_count(self.root)
        self.assertEqual(current["tool_count"], "1")
        self.assertFalse(self.path.exists())
        saved = set_count(self.root, 100000, current["revision"])
        self.assertEqual(saved["tool_count"], "100000")
        config = json.loads(self.path.read_text())
        config.update(seed=6, schema_properties=17, description_words=82, custom="preserved")
        self.path.write_text(json.dumps(config))
        current = get_count(self.root)
        set_count(self.root, 12345678901234567890, current["revision"])
        result = json.loads(self.path.read_text())
        self.assertEqual(result, {**config, "tool_count": 12345678901234567890})
        self.assertEqual(list(self.path.parent.glob("*.tmp")), [])

    def test_invalid_input_and_revision_do_not_write(self):
        current = get_count(self.root)
        for value in (0, -1, True, 1.5, "1"):
            with self.assertRaises(HTTPException):
                set_count(self.root, value, current["revision"])
        self.assertFalse(self.path.exists())
        set_count(self.root, 3, current["revision"])
        previous = self.path.read_bytes()
        with self.assertRaises(HTTPException) as error:
            set_count(self.root, 5, current["revision"])
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(self.path.read_bytes(), previous)

    def test_non_count_config_is_not_validated_by_widget(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text('{"tool_count": -4, "schema_properties": 999}')
        current = get_count(self.root)
        set_count(self.root, 5, current["revision"])
        self.assertEqual(json.loads(self.path.read_text()), {"tool_count": 5, "schema_properties": 999})

    def test_invalid_json_kept_intact(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text("{")
        with self.assertRaises(HTTPException):
            get_count(self.root)
        with self.assertRaises(HTTPException):
            set_count(self.root, 3, "bad")
        self.assertEqual(self.path.read_text(), "{")

    def test_symlink_and_special_file_protection(self):
        self.path.parent.mkdir(parents=True)
        outside = self.root / "outside.json"
        outside.write_text('{"tool_count": 9}')
        self.path.symlink_to(outside)
        for operation in (lambda: get_count(self.root), lambda: set_count(self.root, 5, "bad")):
            with self.assertRaises(HTTPException): operation()
        self.assertEqual(outside.read_text(), '{"tool_count": 9}')
        self.path.unlink()
        os.mkfifo(self.path)
        with self.assertRaises(HTTPException): get_count(self.root)
        self.path.unlink()
        self.path.parent.rmdir()
        self.path.parent.symlink_to(self.root)
        with self.assertRaises(HTTPException): get_count(self.root)

    def test_request_validates_only_positive_integer(self):
        for value in (True, 0, -1, 3.2, "", "2.0", "1e3", "-1"):
            with self.assertRaises(ValidationError): MCPCountRequest(tool_count=value, revision="any")
        for value in (1, 100000, "100000", "12345678901234567890"):
            self.assertEqual(MCPCountRequest(tool_count=value, revision="any").tool_count, int(value))


class MCPConfigRoutes(unittest.IsolatedAsyncioTestCase):
    async def test_read_write_routes_and_header(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = Settings(workspace=Path(directory), command_override=("true",))
            app = create_app(settings=settings, manager=SimpleNamespace())
            routes = [r for r in app.routes if r.path == "/api/mcp-dump/count"]
            read = next(r.endpoint for r in routes if "GET" in r.methods)
            write = next(r.endpoint for r in routes if "PUT" in r.methods)
            response = Response()
            current = await read(response)
            self.assertEqual(response.headers["Cache-Control"], "no-store")
            request = MCPCountRequest(tool_count="100000", revision=current["revision"])
            with self.assertRaises(HTTPException) as error:
                await write(request, Response(), None)
            self.assertEqual(error.exception.status_code, 403)
            self.assertEqual((await write(request, Response(), "1"))["tool_count"], "100000")


if __name__ == "__main__":
    unittest.main()
