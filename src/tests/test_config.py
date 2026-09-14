"""Regression tests for workspace and model configuration."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.server.config import DEFAULT_WORKSPACE, PROJECT_ROOT, Settings


class ModelTests(unittest.TestCase):
    def test_default_model_and_cli_argument(self):
        with patch.dict(os.environ, {}, clear=True):
            for settings in (Settings(), Settings.from_environment()):
                self.assertEqual(settings.model, "claude-haiku-4-5")
                self.assertIn("--model=claude-haiku-4-5", settings.claude_command())

    def test_model_override_and_cli_argument(self):
        with patch.dict(os.environ, {"CONTEXT_INSPECTOR_MODEL": "custom-model"}, clear=True):
            settings = Settings.from_environment()
        self.assertEqual(settings.model, "custom-model")
        self.assertIn("--model=custom-model", settings.claude_command())


class WorkspaceTests(unittest.TestCase):
    def test_defaults_are_project_local(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(Settings().workspace, PROJECT_ROOT / "workspace")
            self.assertEqual(Settings.from_environment().workspace, DEFAULT_WORKSPACE)
            self.assertNotEqual(DEFAULT_WORKSPACE, PROJECT_ROOT.parent)

    def test_validation_creates_default_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "workspace"
            with patch("src.server.config.DEFAULT_WORKSPACE", workspace):
                settings = Settings(workspace=workspace, command_override=("true",))
                settings.validate()
                settings.validate()
            self.assertTrue(workspace.is_dir())

    def test_explicit_workspace_is_respected(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"CONTEXT_INSPECTOR_WORKSPACE": directory}, clear=True):
                settings = Settings.from_environment()
            self.assertEqual(settings.workspace, Path(directory).resolve())
            settings.validate()

    def test_missing_explicit_workspace_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "missing"
            with self.assertRaisesRegex(ValueError, "Workspace does not exist"):
                Settings(workspace=workspace).validate()
            self.assertFalse(workspace.exists())
