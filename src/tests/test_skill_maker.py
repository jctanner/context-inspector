import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/skill-maker.py"
SPEC = importlib.util.spec_from_file_location("skill_maker", SCRIPT)
maker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(maker)


class SkillMakerTests(unittest.TestCase):
    def test_default_batch_via_cli_from_other_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "skills"
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--output", str(output), "--seed", "42"],
                cwd=directory, capture_output=True, text=True, check=True,
            )
            files = sorted(output.glob("*/SKILL.md"))
            self.assertEqual(len(files), 1000)
            descriptions = set()
            lengths = set()
            for file in files:
                text = file.read_text()
                lines = text.splitlines()
                self.assertEqual(lines[0], "---")
                self.assertEqual(lines[1], f"name: {file.parent.name}")
                self.assertEqual(lines[3], "---")
                description = lines[2].removeprefix('description: "').removesuffix('"')
                self.assertEqual(len(description.split()), 96)
                self.assertLessEqual(len(description), 1024)
                descriptions.add(description)
                self.assertGreaterEqual(len(lines), 500)
                self.assertLessEqual(len(lines), 5000)
                lengths.add(len(lines))
                for line in lines[9:]:
                    self.assertEqual(len(line.split()), 20)
            self.assertEqual(len(descriptions), 1000)
            self.assertGreater(len(lengths), 100)
            self.assertIn("Created 1,000 skills", result.stdout)
            self.assertEqual(maker.DEFAULT_OUTPUT, ROOT /
                             "container/workspace/.context/skill-dump/.claude/skills")

    def test_seed_reproducibility(self):
        with tempfile.TemporaryDirectory() as directory:
            a, b = Path(directory) / "a", Path(directory) / "b"
            for output in (a, b):
                maker.generate(output, 2, 10, 20, seed=7)
            self.assertEqual((a / "skill-dump-0001/SKILL.md").read_bytes(),
                             (b / "skill-dump-0001/SKILL.md").read_bytes())

    def test_collision_preflight_preserves_existing_files(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            existing = output / "skill-dump-0002"
            existing.mkdir()
            marker = existing / "SKILL.md"
            marker.write_text("user data")
            with self.assertRaises(FileExistsError):
                maker.generate(output, 3, 10, 20)
            self.assertEqual(marker.read_text(), "user data")
            self.assertFalse((output / "skill-dump-0001").exists())

    def test_dangling_symlink_collision(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "skill-dump-0001").symlink_to(output / "missing")
            with self.assertRaises(FileExistsError):
                maker.generate(output, 1, 10, 20)
            self.assertFalse((output / "missing").exists())

    def test_invalid_counts_write_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "skills"
            for counts in ((0, 10, 20), (1, 0, 20), (1, 10, 0), (1, 1000, 20)):
                with self.assertRaises(ValueError):
                    maker.generate(output, *counts)
                self.assertFalse(output.exists())

    def test_exact_bounds(self):
        with tempfile.TemporaryDirectory() as directory:
            for length in (10, 500, 5000):
                output = Path(directory) / str(length)
                maker.generate(output, 1, 10, min_lines=length, max_lines=length)
                text = (output / "skill-dump-0001/SKILL.md").read_text()
                self.assertEqual(len(text.splitlines()), length)

    def test_invalid_line_bounds_write_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "skills"
            for lower, upper in ((0, 5000), (9, 5000), (5000, 500)):
                with self.assertRaises(ValueError):
                    maker.generate(output, 1, 10, min_lines=lower, max_lines=upper)
                self.assertFalse(output.exists())

    def test_custom_cli_bounds(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--output", directory, "--count", "2",
                 "--min-lines", "500", "--max-lines", "500", "--words-per-line", "3"],
                capture_output=True, text=True, check=True,
            )
            for file in Path(directory).glob("*/SKILL.md"):
                lines = file.read_text().splitlines()
                self.assertEqual(len(lines), 500)
                self.assertTrue(all(len(line.split()) == 3 for line in lines[9:]))
            self.assertIn("500–500 total lines", result.stdout)


if __name__ == "__main__":
    unittest.main()
