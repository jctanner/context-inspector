"""Verify ignore policy without creating any sensitive or generated files."""

from pathlib import Path
import subprocess
import unittest


class GitignoreTests(unittest.TestCase):
    def ignored(self, paths):
        result = subprocess.run(
            ["git", "-c", "core.excludesFile=/dev/null", "check-ignore", "--no-index", "--stdin"],
            cwd=Path(__file__).resolve().parents[2], input="\n".join(paths) + "\n",
            text=True, capture_output=True,
        )
        self.assertIn(result.returncode, (0, 1), result.stderr)
        return set(result.stdout.splitlines())

    def test_sensitive_and_generated_paths_are_ignored(self):
        paths = [
            ".env", ".env.local", ".env.production", ".state/claude/.claude.json",
            "captures/traffic.jsonl", "state/runtime/adc.json", "flows-session.jsonl",
            ".mitmproxy/mitmproxy-ca.pem", "adc.json", "server.log",
            "workspace/private.txt", "workspace/project/.env",
            "container/home/evaluator/.claude/.credentials.json", "container/home/evaluator/.claude.json",
            "container/home/evaluator/.claude/projects/-workspace/memory/MEMORY.md", "container/workspace/private.txt",
            ".venv/bin/python", "src/server/__pycache__/app.cpython-314.pyc",
            "context_inspector.egg-info/PKG-INFO", "build/lib/app.py",
            ".pytest_cache/cache", ".coverage", "htmlcov/index.html",
            "src/web/node_modules/pkg/index.js", "src/web/dist/index.html",
            "src/web/.vite/cache", "src/web/app.tsbuildinfo",
            ".playwright-mcp/screenshot.png", "test-results/trace.zip",
            "playwright-report/index.html", ".vscode/settings.json", ".DS_Store",
        ]
        self.assertEqual(self.ignored(paths), set(paths))

    def test_source_examples_lockfiles_and_docs_stay_visible(self):
        paths = [
            ".gitignore", ".env.example", "pyproject.toml",
            "uv.lock", "src/web/package-lock.json", "src/web/package.json",
            "src/server/app.py", "src/tests/test_gitignore.py",
            "src/tests/fixtures/sanitized.jsonl", "src/web/request-tabs.ts",
            "AGENTS.md", "PLAN.md", "README.md", "docs/notes/session-log.md",
        ]
        self.assertEqual(self.ignored(paths), set())
