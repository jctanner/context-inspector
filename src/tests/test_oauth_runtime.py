"""Synthetic credential preflight tests; never inspect host login state."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from src.runtime.oauth import CredentialError, claude_auth_directory, codex_auth_file, codex_command, isolated_codex_environment, codex_cached_models, native_launch
from src.server.config import Settings


class OAuthRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.path = self.root / "auth.json"
        self.value = {"auth_mode": "chatgpt", "tokens": dict.fromkeys(
            ("access_token", "refresh_token", "id_token", "account_id"), "synthetic-secret-sentinel")}
        self.write(self.value)

    def write(self, value):
        self.path.write_text(json.dumps(value))
        self.path.chmod(0o600)

    def test_native_refresh_identity_and_replacement(self):
        auth = codex_auth_file(self.root)
        self.write({**self.value, "last_refresh": "synthetic-update"})
        self.assertTrue(auth.unchanged_identity())
        replacement = self.root / "replacement"
        replacement.write_text(self.path.read_text())
        replacement.replace(self.path)
        self.assertFalse(auth.unchanged_identity())
        self.path.unlink()
        self.assertFalse(auth.unchanged_identity())

    def test_claude_directory_allows_native_credential_replacement(self):
        store = self.root / "claude-store"
        store.mkdir(mode=0o700)
        credentials = store / ".credentials.json"
        credentials.write_text(json.dumps({"claudeAiOauth": {"accessToken": "synthetic-a", "refreshToken": "synthetic-r"}}))
        credentials.chmod(0o600)
        shared = claude_auth_directory(store)
        replacement = store / "replacement"
        replacement.write_text(credentials.read_text())
        replacement.chmod(0o600)
        replacement.replace(credentials)
        self.assertTrue(shared.unchanged_identity())
        self.assertTrue(claude_auth_directory(store).directory)
        credentials.unlink()
        credentials.symlink_to(self.path)
        with self.assertRaises(CredentialError):
            claude_auth_directory(store)

    def test_keyring_auto_and_invalid_auth_fail_without_token_echo(self):
        for store in ("keyring", "auto", "ephemeral"):
            (self.root / "config.toml").write_text(f'cli_auth_credentials_store="{store}"')
            with self.assertRaises(CredentialError):
                codex_auth_file(self.root)
        (self.root / "config.toml").unlink()
        for value in ({"OPENAI_API_KEY": "synthetic-secret-sentinel"}, [], {"tokens": {"access_token": "synthetic-secret-sentinel"}}):
            self.write(value)
            with self.assertRaises(CredentialError) as error:
                codex_auth_file(self.root)
            self.assertNotIn("synthetic-secret-sentinel", str(error.exception))

    def test_symlink_fifo_and_shared_permissions_rejected(self):
        self.path.chmod(0o644)
        with self.assertRaises(CredentialError):
            codex_auth_file(self.root)
        saved = self.root / "saved"
        self.path.rename(saved)
        self.path.symlink_to(saved)
        with self.assertRaises(CredentialError):
            codex_auth_file(self.root)
        self.path.unlink()
        os.mkfifo(self.path, 0o600)
        with self.assertRaises(CredentialError):
            codex_auth_file(self.root)

    def test_native_command_and_isolated_proxy_environment(self):
        command = codex_command("synthetic-model")
        self.assertIn("--no-daemon", command)
        self.assertEqual(command[command.index("--model") + 1], "synthetic-model")
        self.assertNotIn("--ignore-user-config", command)
        env = isolated_codex_environment("http://synthetic-proxy:8080")
        self.assertEqual(env["CODEX_CA_CERTIFICATE"], "/mitmproxy-ca-cert.pem")
        self.assertNotIn("OPENAI_API_KEY", env)
        self.assertNotIn("GOOGLE_APPLICATION_CREDENTIALS", env)
        self.assertEqual(Settings().session_command("codex", "oauth", model="synthetic-model")[2:], command)
        for model in ("", "--remote", "bad\nmodel"):
            with self.assertRaises(ValueError):
                codex_command(model)

    def test_native_model_catalog_rejects_hidden_and_invalid_entries(self):
        (self.root / "models_cache.json").write_text(json.dumps({"models": [
            {"slug": "synthetic-model", "visibility": "list"},
            {"slug": "hidden-model", "visibility": "hide"},
            {"slug": "--unsafe", "visibility": "list"},
            {"slug": "new\nline", "visibility": "list"},
            {"slug": "synthetic-model", "visibility": "list"}, None,
        ]}))
        with patch.dict(os.environ, {"CODEX_HOME": str(self.root)}):
            self.assertEqual(codex_cached_models(), ("synthetic-model",))

    def test_shell_launch_mounts_only_native_auth_and_disables_other_providers(self):
        project = self.root / "project"
        runtime = project / "src/runtime"
        runtime.mkdir(parents=True)
        for name in ("run.sh", "oauth.py", "container-entrypoint.sh", "harness_image.py", "strace-env.sh", "mlflow-env.sh"):
            shutil.copyfile(Path("src/runtime") / name, runtime / name)
        shutil.copytree(Path("src/runtime/harnesses"), runtime / "harnesses")
        shutil.copytree(Path("src/runtime/strace"), runtime / "strace")
        python = project / ".venv/bin/python"
        python.parent.mkdir(parents=True)
        python.symlink_to(sys.executable)
        tools = self.root / "bin"
        tools.mkdir()
        calls = self.root / "podman-calls.jsonl"
        podman = tools / "podman"
        podman.write_text('''#!/usr/bin/env python3
import json, os, pathlib, sys
with open(os.environ["SYNTHETIC_PODMAN_CALLS"], "a") as output:
    output.write(json.dumps(sys.argv[1:]) + "\\n")
if sys.argv[1] == "inspect": print("true")
if sys.argv[1] == "cp": pathlib.Path(sys.argv[-1]).write_text('{"synthetic":true}\\n')
if "-it" in sys.argv: sys.exit(7)
''')
        podman.chmod(0o700)
        state = self.root / "state"
        ca = state / "runtime/mitmproxy/mitmproxy-ca-cert.pem"
        ca.parent.mkdir(parents=True)
        ca.write_text("synthetic-ca")
        before = self.path.read_bytes()
        result = subprocess.run(["bash", str(runtime / "run.sh"), "--", *codex_command("synthetic-model")],
            cwd=self.root, capture_output=True, text=True, timeout=15, env={
                "PATH": str(tools) + ":" + os.environ["PATH"], "HOME": str(self.root), "CODEX_HOME": str(self.root),
                "SYNTHETIC_PODMAN_CALLS": str(calls),
                "CONTEXT_INSPECTOR_HARNESS": "codex", "CONTEXT_INSPECTOR_AUTH_MODE": "oauth",
                "CONTEXT_INSPECTOR_SESSION_ID": "synthetic", "CONTEXT_INSPECTOR_STATE_DIR": str(state),
                "CONTEXT_INSPECTOR_EVENT_FILE": str(state / "session/events.jsonl"),
                "GOOGLE_APPLICATION_CREDENTIALS": str(self.path), "OPENAI_API_KEY": "synthetic-unwanted-key",
            })
        self.assertEqual(result.returncode, 7, result.stderr)
        records = [json.loads(line) for line in calls.read_text().splitlines()]
        self.assertTrue(any(call[0] == "cp" for call in records), "Archive must survive a failed CLI")
        agent = next(call for call in records if "-it" in call)
        self.assertIn(str(self.path) + ":/home/evaluator/.codex/auth.json:rw", agent)
        self.assertFalse(any(":/usr/local/bin/" in item for item in agent))
        self.assertTrue(any("context-inspector-claude-strace:" in item for item in agent))
        self.assertIn("CODEX_CA_CERTIFICATE=/mitmproxy-ca-cert.pem", agent)
        self.assertIn("CONTEXT_INSPECTOR_STRACE_ENABLED=1", agent)
        self.assertIn("--no-daemon", agent)
        self.assertIn("SYS_PTRACE", agent)
        self.assertNotIn("synthetic-unwanted-key", json.dumps(records))
        self.assertFalse((state / "runtime/adc.json").exists())
        self.assertEqual(self.path.read_bytes(), before)

    def test_codex_preflight_needs_credentials_not_host_executables(self):
        with patch.dict(os.environ, {"CODEX_HOME": str(self.root), "PATH": "/missing"}):
            self.assertEqual(native_launch("codex").auth.path, self.path)
