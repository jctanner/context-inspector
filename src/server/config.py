"""Runtime configuration and safe command construction."""

from __future__ import annotations

import os
import json
import tempfile
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PARENT_PROJECT_ROOT = PROJECT_ROOT.parent
DEFAULT_RUNNER = PROJECT_ROOT / "src" / "runtime" / "run.sh"
DEFAULT_STATE_DIR = Path(tempfile.gettempdir()) / f"context-inspector-{os.getuid()}"


@dataclass(frozen=True)
class Settings:
    host: str = "127.0.0.1"
    port: int = 8765
    workspace: Path = PARENT_PROJECT_ROOT
    runner: Path = DEFAULT_RUNNER
    model: str = "sonnet"
    command_override: tuple[str, ...] | None = None
    state_dir: Path = DEFAULT_STATE_DIR
    context_window_tokens: int = 200_000
    context_window_source: str = "configured default from experiment baseline"

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
            host=os.environ.get("CONTEXT_INSPECTOR_HOST", "127.0.0.1"),
            port=int(os.environ.get("CONTEXT_INSPECTOR_PORT", "8765")),
            workspace=Path(os.environ.get("CONTEXT_INSPECTOR_WORKSPACE", PARENT_PROJECT_ROOT)).resolve(),
            runner=Path(os.environ.get("CONTEXT_INSPECTOR_RUNNER", DEFAULT_RUNNER)).resolve(),
            model=os.environ.get("CONTEXT_INSPECTOR_MODEL", "sonnet"),
            command_override=command_override,
            state_dir=Path(os.environ.get("CONTEXT_INSPECTOR_STATE_DIR", DEFAULT_STATE_DIR)).resolve(),
            context_window_tokens=int(configured_window or "200000"),
            context_window_source="environment override" if configured_window else "configured default from experiment baseline",
        )

    def validate(self) -> None:
        if self.host not in {"127.0.0.1", "::1", "localhost"}:
            raise ValueError("Context Inspector must bind to loopback unless the code is explicitly revised")
        if not self.workspace.is_dir():
            raise ValueError(f"Workspace does not exist: {self.workspace}")
        if self.context_window_tokens <= 0:
            raise ValueError("CONTEXT_INSPECTOR_CONTEXT_WINDOW_TOKENS must be positive")
        if self.command_override is None:
            if not self.runner.is_file():
                raise ValueError(f"MITM runner does not exist: {self.runner}")
            if not os.access(self.runner, os.X_OK):
                raise ValueError(f"MITM runner is not executable: {self.runner}")

    def claude_command(self, extra_args: tuple[str, ...] = ()) -> tuple[str, ...]:
        """Return an argv vector; never interpolate user data into a shell command."""

        if self.command_override is not None:
            if extra_args:
                raise ValueError("extra_args are unavailable with a command override")
            return self.command_override
        return (
            str(self.runner),
            "--",
            "claude",
            f"--model={self.model}",
            "--dangerously-skip-permissions",
            *extra_args,
        )
