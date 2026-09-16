from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from pydantic import ValidationError
from src.server.app import create_app, CreateSessionRequest
from src.server.config import Settings, SESSION_MODELS


class StartModelTests(unittest.TestCase):
    def test_exact_choices_and_default_compatibility(self):
        self.assertEqual(SESSION_MODELS, ("claude-haiku-4-5", "claude-sonnet-5", "claude-sonnet-4-6", "claude-opus-4-6"))
        settings = Settings(model="configured-model")
        for model in SESSION_MODELS:
            request = CreateSessionRequest(model=model)
            command = settings.claude_command(model=request.model)
            self.assertEqual([a for a in command if a.startswith("--model=")], [f"--model={model}"])
        self.assertIn("--model=configured-model", settings.claude_command())
        for model in ("unknown", "", True, 2):
            with self.assertRaises(ValidationError): CreateSessionRequest(model=model)
        with self.assertRaises(ValueError): settings.claude_command(("--model=other",), model=SESSION_MODELS[0])
        with self.assertRaises(ValueError): Settings(command_override=("true",)).claude_command(model=SESSION_MODELS[0])


class StartModelRouteTests(unittest.IsolatedAsyncioTestCase):
    @patch('src.server.app.clear_session_traces')
    async def test_new_sessions_use_choice_and_shared_sessions_are_unchanged(self, clear):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active = None
            def create(argv, **kwargs):
                nonlocal active
                active = SimpleNamespace(id=kwargs["session_id"], pid=123, argv=argv, alive=True)
                return active
            manager = SimpleNamespace(active=lambda: active, create=Mock(side_effect=create), get=lambda _: active)
            app = create_app(settings=Settings(workspace=root, state_dir=root / "state"), manager=manager)
            endpoint = next(r.endpoint for r in app.routes if r.path == "/api/sessions" and "POST" in r.methods)
            for model in SESSION_MODELS:
                active = None
                first = await endpoint(CreateSessionRequest(model=model))
                self.assertEqual(clear.call_count, manager.create.call_count)
                self.assertIn(f"--model={model}", manager.create.call_args.args[0])
                self.assertEqual(first.selected_model, model)
                calls = manager.create.call_count
                second = await endpoint(CreateSessionRequest(model="claude-opus-4-6"))
                self.assertEqual(first.session_id, second.session_id)
                self.assertEqual(second.selected_model, model)
                self.assertEqual(manager.create.call_count, calls)
                self.assertEqual(clear.call_count, calls)
                for path in ("/api/sessions/active", "/api/sessions/{session_id}"):
                    status = next(r.endpoint for r in app.routes if r.path == path and "GET" in r.methods)
                    result = await status() if path.endswith("active") else await status(active.id)
                    self.assertEqual(result.selected_model, model)

    async def test_launch_metadata_handles_split_args_and_unknown_model(self):
        with tempfile.TemporaryDirectory() as directory:
            active = SimpleNamespace(id="fixture", pid=123, alive=True, argv=("claude", "--model", "claude-sonnet-4-6"))
            manager = SimpleNamespace(active=lambda: active)
            app = create_app(settings=Settings(workspace=Path(directory)), manager=manager)
            endpoint = next(r.endpoint for r in app.routes if r.path == "/api/sessions/active")
            self.assertEqual((await endpoint()).selected_model, "claude-sonnet-4-6")
            active.argv = ("custom-command",)
            self.assertIsNone((await endpoint()).selected_model)
