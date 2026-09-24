"""Conservative interpretation helpers for captured Codex Responses messages.

Raw WebSocket messages remain the evidence. These helpers only expose fields
whose meaning is defined by the Responses event shape and leave omissions or
unknown event variants uninterpreted.
"""

from __future__ import annotations

import json
from typing import Any


def _count(value: Any) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None


def parse_codex_message(direction: str, raw: bytes | str) -> dict[str, Any] | None:
    """Return a narrow normalized observation for a JSON Responses message.

    The returned object never replaces or mutates the captured wire message.
    Binary, invalid JSON, and unrecognized events return ``None``.
    """

    if direction not in {"client_to_server", "server_to_client"}:
        return None
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
        return None
    if not isinstance(value, dict) or not isinstance(value.get("type"), str):
        return None

    event_type = value["type"]
    if direction == "client_to_server" and event_type == "response.create":
        request = {key: value[key] for key in ("model", "instructions", "input", "tools", "previous_response_id") if key in value}
        return {
            "observation": "response.create",
            "request": request,
            "request_completeness": "wire_message_fields_only",
        }

    if direction != "server_to_client" or event_type != "response.completed":
        return None
    response = value.get("response")
    if not isinstance(response, dict):
        return None
    usage = response.get("usage")
    if not isinstance(usage, dict):
        usage = {}
    details = usage.get("input_tokens_details")
    if not isinstance(details, dict):
        details = {}
    output_details = usage.get("output_tokens_details")
    if not isinstance(output_details, dict):
        output_details = {}

    output_tokens = _count(usage.get("output_tokens"))
    cached_tokens = _count(details.get("cached_tokens"))
    reasoning_tokens = _count(output_details.get("reasoning_tokens"))
    return {
        "observation": "response.completed",
        "response_id": response.get("id") if isinstance(response.get("id"), str) else None,
        "model": response.get("model") if isinstance(response.get("model"), str) else None,
        "usage": {
            "input_tokens": _count(usage.get("input_tokens")),
            "cached_input_tokens": cached_tokens,
            "uncached_input_tokens": (
                usage["input_tokens"] - cached_tokens
                if _count(usage.get("input_tokens")) is not None
                and cached_tokens is not None
                and cached_tokens <= usage["input_tokens"]
                else None
            ),
            "output_tokens": output_tokens,
            "reasoning_output_tokens": reasoning_tokens,
            "total_tokens": _count(usage.get("total_tokens")),
        },
        "context_window_tokens": None,
        "context_window_source": "unknown",
    }
