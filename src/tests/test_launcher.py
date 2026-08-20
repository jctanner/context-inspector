from __future__ import annotations

import os
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path
import unittest


class LauncherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = Path(__file__).parents[1] / "bin" / "context-inspector"

    def make_project(self, root: Path) -> Path:
        launcher = root / "src" / "bin" / "context-inspector"
        launcher.parent.mkdir(parents=True)
        shutil.copyfile(self.source, launcher)
        launcher.chmod(launcher.stat().st_mode | stat.S_IXUSR)
        return launcher

    def test_missing_project_env_fails_before_startup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            launcher = self.make_project(root)
            result = subprocess.run([launcher], text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 1)
            self.assertIn(f"required environment file not found: {root / '.env'}", result.stderr)
            self.assertIn(f"cp {root / '.env.example'} {root / '.env'}", result.stderr)

    def test_project_env_is_exported_to_server_process(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            launcher = self.make_project(root)
            (root / ".env").write_text("INSPECTOR_ENV_TEST=from-project-root\n")
            (root / "src" / "web" / "dist").mkdir(parents=True)
            (root / "src" / "web" / "dist" / "index.html").write_text("ready")
            fake_bin = root / "fake-bin"
            fake_bin.mkdir()
            fake_python = fake_bin / "python"
            fake_python.write_text("#!/usr/bin/env bash\nprintf '%s' \"${INSPECTOR_ENV_TEST:-missing}\"\n")
            fake_python.chmod(0o755)
            environment = os.environ.copy()
            environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
            result = subprocess.run([launcher], text=True, capture_output=True, check=False, env=environment)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "from-project-root")


if __name__ == "__main__":
    unittest.main()
