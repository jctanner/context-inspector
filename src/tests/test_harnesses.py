import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException, Response
from pydantic import ValidationError
from src.server.app import CreateSessionRequest, create_app
from src.server.config import Settings
from src.server.harnesses import catalog, get_profile
from src.runtime.oauth import CredentialError


class ProfileTests(unittest.TestCase):
    def test_inspector_catalog_wins_over_host_and_empty_does_not_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            host, inspector = root / "host", root / "inspector"
            host.mkdir()
            (inspector / ".codex").mkdir(parents=True)
            def write(path, names):
                path.write_text(json.dumps({"models": [{"slug": name, "visibility": "list"} for name in names]}))
            write(host / "models_cache.json", ["host-only"])
            with patch.dict(os.environ, {"CODEX_HOME": str(host)}), patch("src.server.harnesses.CLAUDE_HOME", inspector):
                self.assertEqual(get_profile("codex", "oauth").models, ("host-only",))
                write(inspector / ".codex/models_cache.json", ["gpt-6-sol", "gpt-6-luna"])
                self.assertEqual(get_profile("codex", "oauth").models, ("gpt-6-sol", "gpt-6-luna"))
                self.assertEqual(catalog()["profiles"][-1]["model_source"], "native inspector model cache")
                write(host / "models_cache.json", ["changed-host"])
                self.assertEqual(get_profile("codex", "oauth").models, ("gpt-6-sol", "gpt-6-luna"))
                write(inspector / ".codex/models_cache.json", [])
                self.assertFalse(get_profile("codex", "oauth").available)

    def test_valid_pairs_and_native_model_catalog(self):
        with patch("src.server.harnesses.codex_cached_models", return_value=("synthetic-model",)):
            profiles = catalog()["profiles"]
        self.assertEqual([(p["harness"], p["auth_mode"]) for p in profiles], [("claude", "vertex"), ("claude", "oauth"), ("codex", "oauth")])
        self.assertTrue(all(profile["available"] for profile in profiles))
        self.assertEqual(profiles[2]["models"], ("synthetic-model",))
        with patch("src.server.harnesses.codex_cached_models", return_value=()):
            self.assertFalse(get_profile("codex", "oauth").available)
        with self.assertRaises(ValueError):
            get_profile("codex", "vertex")
        for fields in ({"harness": "codex", "auth_mode": "vertex"}, {"token": "sentinel"}, {"credential_path": "/tmp/anything"}):
            with self.assertRaises(ValidationError):
                CreateSessionRequest(**fields)

    def test_command_override_catalog_is_unavailable(self):
        self.assertTrue(all(not p["available"] for p in catalog(True)["profiles"]))

    def test_runner_rejects_missing_native_auth_before_creating_state(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "untouched" / "events.jsonl"
            result = subprocess.run(["bash", "src/runtime/run.sh", "--", "codex"], capture_output=True, text=True,
                env={**os.environ, "CONTEXT_INSPECTOR_SESSION_ID": "synthetic", "CONTEXT_INSPECTOR_EVENT_FILE": str(target),
                     "CODEX_HOME": str(Path(directory) / "missing-host-login"),
                     "CONTEXT_INSPECTOR_HARNESS": "codex", "CONTEXT_INSPECTOR_AUTH_MODE": "oauth"})
            self.assertEqual(result.returncode, 2)
            self.assertFalse(target.parent.exists())


class ProfileRouteTests(unittest.IsolatedAsyncioTestCase):
    async def test_oauth_launch_metadata_and_native_commands(self):
        for harness, model in (("codex", "synthetic-model"), ("claude", "claude-haiku-4-5")):
            with self.subTest(harness=harness), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                active = None
                def create(argv, **kwargs):
                    nonlocal active
                    active = SimpleNamespace(id=kwargs["session_id"], pid=1, argv=argv, alive=True)
                    return active
                manager = SimpleNamespace(active=lambda: active, get=lambda _: active, create=Mock(side_effect=create))
                app = create_app(settings=Settings(workspace=root, state_dir=root / "state"), manager=manager)
                route = lambda path: next(r.endpoint for r in app.routes if r.path == path)
                with patch("src.server.app.native_launch") as preflight, \
                     patch("src.server.app.clear_session_traces") as clear, \
                     patch("src.server.harnesses.codex_cached_models", return_value=("synthetic-model",)):
                    def cleanup():
                        self.assertEqual(preflight.call_count, 1, "Native preflight must precede cleanup")
                    clear.side_effect = cleanup
                    created = await route("/api/sessions")(CreateSessionRequest(harness=harness, auth_mode="oauth", model=model))
                    preflight.assert_called_once_with(harness)
                    self.assertEqual(created.harness, harness)
                    self.assertEqual(created.auth_mode, "oauth")
                    self.assertEqual(created.selected_model, model)
                    self.assertIn("strace", created.capabilities)
                    argv = manager.create.call_args.args[0]
                    self.assertEqual(argv[2], harness)
                    self.assertIn("--no-daemon" if harness == "codex" else "--setting-sources", argv)
                    self.assertEqual(manager.create.call_args.kwargs["env"]["CONTEXT_INSPECTOR_AUTH_MODE"], "oauth")
                    joined = await route("/api/sessions")(CreateSessionRequest())
                    self.assertEqual(joined.session_id, created.session_id)
                    self.assertEqual(joined.capabilities, created.capabilities)
                    self.assertEqual(manager.create.call_count, 1)

    async def test_catalog_rejection_metadata_conflict_and_reconnect(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active = None
            def create(argv, **kwargs):
                nonlocal active
                active = SimpleNamespace(id=kwargs["session_id"], pid=1, argv=argv, alive=True)
                return active
            manager = SimpleNamespace(active=lambda: active, get=lambda _: active, create=Mock(side_effect=create))
            app = create_app(settings=Settings(workspace=root, state_dir=root / "state"), manager=manager)
            route = lambda path: next(r.endpoint for r in app.routes if r.path == path)
            response = Response()
            self.assertEqual(len((await route("/api/profiles")(response))["profiles"]), 3)
            self.assertEqual(response.headers["cache-control"], "no-store")
            start = route("/api/sessions")
            with patch("src.server.app.clear_session_traces") as clear, \
                 patch("src.server.app.native_launch", side_effect=CredentialError("synthetic missing login")), \
                 patch("src.server.harnesses.codex_cached_models", return_value=("synthetic-model",)):
                for harness in ("claude", "codex"):
                    with self.assertRaises(HTTPException) as error:
                        await start(CreateSessionRequest(harness=harness, auth_mode="oauth"))
                    self.assertEqual(error.exception.status_code, 409)
                manager.create.assert_not_called()
                clear.assert_not_called()
                with self.assertRaises(HTTPException):
                    await start(CreateSessionRequest(harness="claude", auth_mode="vertex", extra_args=["--settings", "{}"]))
                first = await start(CreateSessionRequest(harness="claude", auth_mode="vertex", model="claude-haiku-4-5"))
                self.assertEqual((first.harness, first.auth_mode), ("claude", "vertex"))
                record = root / "state" / "sessions" / first.session_id / "launch.json"
                self.assertEqual(json.loads(record.read_text())["auth_mode"], "vertex")
                self.assertEqual(record.stat().st_mode & 0o777, 0o600)
                for selection in ({"harness": "codex", "auth_mode": "oauth"}, {"harness": "claude", "auth_mode": "vertex", "model": "claude-sonnet-5"}):
                    with self.assertRaises(HTTPException) as error:
                        await start(CreateSessionRequest(**selection))
                    self.assertEqual(error.exception.status_code, 409)
                joined = await start(CreateSessionRequest())
                self.assertEqual(joined.session_id, first.session_id)
                self.assertEqual(joined.capture_profile, "anthropic-http-v1")
                status = await route("/api/sessions/active")()
                self.assertEqual(status.capabilities, first.capabilities)
                self.assertEqual(manager.create.call_count, 1)
                clear.assert_called_once()
