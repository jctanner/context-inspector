"""Conservative request-stream identity classification from wire evidence."""

from __future__ import annotations

import hashlib
import json
from typing import Any


AGENT_ID_HEADER = "x-claude-code-agent-id"
SESSION_ID_HEADER = "x-claude-code-session-id"


def classify_request_stream(request: dict[str, Any]) -> dict[str, Any]:
    headers = {str(key).lower(): value for key, value in (request.get("headers") or {}).items()}
    agent_id = headers.get(AGENT_ID_HEADER)
    session_id = headers.get(SESSION_ID_HEADER)
    body = request.get("body") or {}
    payload = (body.get("decoded") or {}).get("value")
    system = payload.get("system") if isinstance(payload, dict) else None
    tools = payload.get("tools") if isinstance(payload, dict) else None
    heuristic = {
        "system_fingerprint": hashlib.sha256(json.dumps(system, sort_keys=True, separators=(",", ":")).encode()).hexdigest() if system is not None else None,
        "tool_names": [tool.get("name") for tool in tools if isinstance(tool, dict) and isinstance(tool.get("name"), str)] if isinstance(tools, list) else [],
    }
    if isinstance(agent_id, str) and agent_id:
        return {
            "stream_id": f"agent:{agent_id}", "classification": "identified_agent",
            "confidence": "high", "evidence": [f"header:{AGENT_ID_HEADER}"],
            "session_id_hint": session_id, "heuristic_signals": heuristic,
        }
    return {
        "stream_id": "unclassified", "classification": "unclassified",
        "confidence": "none", "evidence": [], "session_id_hint": session_id,
        "heuristic_signals": heuristic,
    }
