import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException, Response
from pydantic import ValidationError
from src.runtime.skill_dump.generator import generate, write_skill
from src.server.skill_count import SkillCount
from src.server.app import create_app, SkillCountRequest
from src.server.config import Settings


class SkillCountTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.folder = self.root / ".context/skill-dump/.claude/skills"
        self.control = SkillCount(self.root)
        self.addCleanup(self.control.close)

    def apply(self, count):
        self.control.start(count, self.control.snapshot()["revision"])
        self.control.worker.join(timeout=10)
        self.assertFalse(self.control.worker.is_alive())
        result = self.control.snapshot()
        self.assertFalse(result["running"])
        self.assertIsNone(result["error"])
        return result

    def test_grow_shrink_without_backups_preserves_retained_files(self):
        self.assertEqual(self.control.snapshot()["skill_count"], "0")
        self.assertFalse(self.folder.exists())
        self.assertEqual(self.apply(3)["skill_count"], "3")
        first = self.folder / "skill-dump-0001/SKILL.md"
        original = first.read_bytes()
        for file in self.folder.glob("*/SKILL.md"):
            lines = file.read_text().splitlines()
            self.assertTrue(500 <= len(lines) <= 5000)
            self.assertEqual(len(lines[2].removeprefix('description: "').removesuffix('"').split()), 96)
        unrelated = self.folder / "authored"
        unrelated.mkdir()
        (unrelated / "SKILL.md").write_text("Do not change")
        self.assertEqual(self.apply(1)["skill_count"], "1")
        self.assertEqual(first.read_bytes(), original)
        self.assertFalse((self.folder / "skill-dump-0002").exists())
        self.assertFalse((self.folder / "skill-dump-0003").exists())
        self.assertEqual((unrelated / "SKILL.md").read_text(), "Do not change")
        self.assertEqual(sorted(p.name for p in self.folder.iterdir()), ["authored", "skill-dump-0001"])
        self.assertEqual(self.apply(2)["skill_count"], "2")
        self.assertEqual(first.read_bytes(), original)

    def test_adopts_existing_cli_files_and_conflicts(self):
        generate(self.folder, 2, 96, seed=1)
        current = self.control.snapshot()
        self.assertEqual(current["skill_count"], "2")
        file = self.folder / "skill-dump-0001/SKILL.md"
        file.write_text(file.read_text() + "new text\n")
        with self.assertRaises(HTTPException) as error:
            self.control.start(1, current["revision"])
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(self.apply(1)["skill_count"], "1")

    def test_foreign_files_prevent_mutation(self):
        self.apply(2)
        extra = self.folder / "skill-dump-0002/user.txt"
        extra.write_text("user data")
        with self.assertRaises(HTTPException): self.control.snapshot()
        with self.assertRaises(HTTPException): self.control.start(1, "any")
        self.assertEqual(extra.read_text(), "user data")
        extra.unlink()
        (extra.parent / "SKILL.md").write_text("authored, not generator output")
        with self.assertRaises(HTTPException): self.control.snapshot()

    def test_symlinks_and_hardlinks_rejected(self):
        self.apply(1)
        file = self.folder / "skill-dump-0001/SKILL.md"
        outside = self.root / "outside.md"
        file.rename(outside)
        file.symlink_to(outside)
        with self.assertRaises(HTTPException): self.control.snapshot()
        file.unlink()
        os.link(outside, file)
        with self.assertRaises(HTTPException): self.control.snapshot()
        file.unlink()
        file.parent.rmdir()
        file.parent.symlink_to(self.root)
        with self.assertRaises(HTTPException): self.control.snapshot()
        self.assertTrue(outside.exists())

    def test_parent_symlink_rejected(self):
        (self.root / ".context").symlink_to(self.root)
        with self.assertRaises(HTTPException): self.control.start(2, "bad")

    def test_progress_and_concurrent_apply(self):
        entered, release = threading.Event(), threading.Event()
        def slow(*args, **kwargs):
            entered.set()
            release.wait(timeout=3)
            return write_skill(*args, **kwargs)
        with patch("src.server.skill_count.write_skill", side_effect=slow):
            self.control.start(2, self.control.snapshot()["revision"])
            self.assertTrue(entered.wait(timeout=2))
            state = self.control.snapshot()
            self.assertTrue(state["running"])
            self.assertEqual(state["target_count"], "2")
            with self.assertRaises(HTTPException): self.control.start(3, state["revision"])
            release.set()
            self.control.worker.join(timeout=5)
        self.assertEqual(self.control.snapshot()["skill_count"], "2")

    def test_failed_generation_recovers_and_invalid_counts_do_not_write(self):
        for count in (0, -1, True, 1.2, "1"):
            with self.assertRaises(HTTPException): self.control.start(count, "any")
        self.assertFalse(self.folder.exists())
        with patch("src.server.skill_count.write_skill", side_effect=OSError("fixture disk full")):
            self.control.start(2, self.control.snapshot()["revision"])
            self.control.worker.join(timeout=5)
        state = self.control.snapshot()
        self.assertIsNotNone(state["error"])
        self.assertEqual(state["skill_count"], "0")
        self.assertEqual(list(self.folder.iterdir()), [])
        self.assertEqual(self.apply(1)["skill_count"], "1")

    def test_request_integer_validation(self):
        for value in (True, 0, -1, "", "1.5", "1e3"):
            with self.assertRaises(ValidationError): SkillCountRequest(skill_count=value, revision="r")
        self.assertEqual(SkillCountRequest(skill_count="100000", revision="r").skill_count, 100000)


class SkillCountRouteTests(unittest.IsolatedAsyncioTestCase):
    async def test_routes_and_header(self):
        with tempfile.TemporaryDirectory() as directory:
            app = create_app(settings=Settings(workspace=Path(directory), command_override=("true",)),
                             manager=SimpleNamespace())
            routes = [r for r in app.routes if r.path == "/api/skill-dump/count"]
            read = next(r.endpoint for r in routes if "GET" in r.methods)
            write = next(r.endpoint for r in routes if "PUT" in r.methods)
            response = Response()
            current = await read(response)
            self.assertEqual(response.headers["Cache-Control"], "no-store")
            request = SkillCountRequest(skill_count=1, revision=current["revision"])
            with self.assertRaises(HTTPException): await write(request, Response(), None)
            try:
                result = await write(request, Response(), "1")
                self.assertTrue(result["running"])
            finally:
                app.state.skills.close()


if __name__ == "__main__":
    unittest.main()
