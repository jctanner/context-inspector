"""Read-only memory API adapter; no container API or host-home fallback."""
from __future__ import annotations

from fastapi import HTTPException

from .config import CLAUDE_HOME
from .memory_files import inspect_memory, MemoryError


def get_memory(session_id: str, path: str | None = None) -> dict:
    try:
        result = inspect_memory("list" if path is None else "read", path or "", home=CLAUDE_HOME)
    except MemoryError as exc:
        raise HTTPException(exc.status, str(exc)) from None
    except OSError:
        raise HTTPException(404, "Memory file unavailable or unsafe path") from None
    return {"session_id": session_id, "source": "Project-local mirror · container/home/evaluator/.claude", **result}
