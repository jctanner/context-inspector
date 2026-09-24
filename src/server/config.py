"""Runtime configuration and safe command construction."""

from __future__ import annotations

import os
import json
import tempfile
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONTAINER_ROOT = PROJECT_ROOT / "container"
CLAUDE_HOME = CONTAINER_ROOT / "home" / "evaluator"
DEFAULT_WORKSPACE = CONTAINER_ROOT / "workspace"
DEFAULT_MODEL = "claude-haiku-4-5"
SESSION_MODELS = (DEFAULT_MODEL, "claude-sonnet-5", "claude-sonnet-4-6", "claude-opus-4-6")
DEFAULT_RUNNER = PROJECT_ROOT / "src" / "runtime" / "run.sh"
DEFAULT_STATE_DIR = Path(tempfile.gettempdir()) / f"context-inspector-{os.getuid()}"


@dataclass(frozen=True)
class Settings:
    host: str = "0.0.0.0"
    port: int = 8765
    workspace: Path = DEFAULT_WORKSPACE
    runner: Path = DEFAULT_RUNNER
    model: str = DEFAULT_MODEL
    command_override: tuple[str, ...] | None = None
    state_dir: Path = DEFAULT_STATE_DIR
    context_window_tokens: int | None = None
    context_window_source: str = "configured override"

    @classmethod
    def from_environment(cls) -> "Settings":
        command_json = os.environ.get("CONTEXT_INSPECTOR_COMMAND_JSON")
        command_override = None
        if command_json:
            parsed = json.loads(command_json)
            if not isinstance(parsed, list) or not parsed or not all(isinstance(item, str) for item in parsed):
                raise ValueError("CONTEXT_INSPECTOR_COMMAND_JSON must be a non-empty JSON string array")
            command_override = tuple(parsed)
        configured_window = os.environ.get("CONTEXT_INSPECTOR_CONTEXT_WINDOW_TOKENS")
        return cls(
            host=os.environ.get("CONTEXT_INSPECTOR_HOST", "0.0.0.0"),
            port=int(os.environ.get("CONTEXT_INSPECTOR_PORT", "8765")),
            workspace=Path(os.environ.get("CONTEXT_INSPECTOR_WORKSPACE", DEFAULT_WORKSPACE)).resolve(),
            runner=Path(os.environ.get("CONTEXT_INSPECTOR_RUNNER", DEFAULT_RUNNER)).resolve(),
            model=os.environ.get("CONTEXT_INSPECTOR_MODEL", DEFAULT_MODEL),
            command_override=command_override,
            state_dir=Path(os.environ.get("CONTEXT_INSPECTOR_STATE_DIR", DEFAULT_STATE_DIR)).resolve(),
            context_window_tokens=int(configured_window) if configured_window else None,
            context_window_source="environment override" if configured_window else "configured override",
        )

    def validate(self) -> None:
        if self.host not in {"0.0.0.0", "127.0.0.1", "::1", "localhost"}:
            raise ValueError("Context Inspector host must be 0.0.0.0 or a loopback address")
        if self.workspace == DEFAULT_WORKSPACE:
            self.workspace.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            self.workspace.mkdir(mode=0o700, exist_ok=True)
        if not self.workspace.is_dir():
            raise ValueError(f"Workspace does not exist: {self.workspace}")
        if self.context_window_tokens is not None and self.context_window_tokens <= 0:
            raise ValueError("CONTEXT_INSPECTOR_CONTEXT_WINDOW_TOKENS must be positive")
        if self.command_override is None:
            if not self.runner.is_file():
                raise ValueError(f"MITM runner does not exist: {self.runner}")
            if not os.access(self.runner, os.X_OK):
                raise ValueError(f"MITM runner is not executable: {self.runner}")

    def claude_command(self, extra_args: tuple[str, ...] = (), *, model: str | None = None) -> tuple[str, ...]:
        """Return an argv vector; never interpolate user data into a shell command."""

        if model is not None:
            if model not in SESSION_MODELS:
                raise ValueError("Unsupported session model")
            if any(arg == "--model" or arg.startswith("--model=") for arg in extra_args):
                raise ValueError("Select the model using the model field, not extra_args")
        if self.command_override is not None:
            if model is not None:
                raise ValueError("Model selection is unavailable with a command override")
            if extra_args:
                raise ValueError("extra_args are unavailable with a command override")
            return self.command_override
        return (
            str(self.runner),
            "--",
            "claude",
            f"--model={model if model is not None else self.model}",
            "--dangerously-skip-permissions",
            *extra_args,
        )

    def session_command(self, harness: str, auth_mode: str, extra_args: tuple[str, ...] = (), *, model: str | None = None) -> tuple[str, ...]:
        if harness == "claude":
            if auth_mode == "oauth":
                if extra_args or self.command_override is not None:
                    raise ValueError("Claude OAuth profiles cannot override the native command")
                return (*self.claude_command(model=model), "--setting-sources", "", "--strict-mcp-config")
            return self.claude_command(extra_args, model=model)
        if (harness, auth_mode) != ("codex", "oauth"):
            raise ValueError("Unsupported harness/auth combination")
        if self.command_override is not None or extra_args:
            raise ValueError("Codex profiles cannot override the native command")
        from src.runtime.oauth import codex_command
        if model is None:
            raise ValueError("Select an available Codex model")
        return (str(self.runner), "--", *codex_command(model))
