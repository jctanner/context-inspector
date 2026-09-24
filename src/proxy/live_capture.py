"""mitmproxy addon that emits sanitized live events and completed archives."""

from __future__ import annotations

import base64
import gzip
import json
import os
import re
import threading
import uuid
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, unquote, urlsplit

try:
    from mitmproxy import http
except ImportError:  # Unit tests run without the proxy distribution installed.
    http = Any


SENSITIVE_HEADERS = {
    "authorization", "cookie", "proxy-authorization", "set-cookie",
    "x-api-key", "x-goog-api-key",
}
HOST_PATTERN = re.compile(os.environ.get("CAPTURE_HOST_RE", r"(^|\.)(anthropic\.com|googleapis\.com|googleusercontent\.com)$"), re.I)
IGNORE_URL_PATTERN = re.compile(os.environ.get("CAPTURE_IGNORE_URL_RE", r"^https://www\.googleapis\.com/discovery/v1/apis$"), re.I)
ANTHROPIC_MODEL_PATHS = {"/v1/messages", "/v1/messages/count_tokens"}
VERTEX_MODEL_PATH = re.compile(r"(?:^|/)models/[^/]+:(?:rawPredict|streamRawPredict|countTokens)$", re.I)
SENSITIVE_QUERY_KEYS = {
    "access_token", "api_key", "apikey", "auth", "authorization", "key",
    "oauth_token", "refresh_token", "token",
}
HTTP_PROTOCOL_VERSION = "1.0"
CODEX_WEBSOCKET_HOST = "chatgpt.com"
CODEX_WEBSOCKET_PATH = "/backend-api/codex/responses"


def _selected(flow: Any) -> bool:
    """Select only known model operations; reject auth and unknown traffic early.

    This guard runs before URLs, headers, or bodies are copied into addon state.
    A host allowlist alone is not sufficient: OAuth token exchanges use Google
    hosts also used by Vertex model requests.
    """
    request = flow.request
    if codex_http_url(request.pretty_url) and request.method.upper() == "POST":
        return True
    if not HOST_PATTERN.search(request.pretty_host) or request.method.upper() != "POST":
        return False
    if IGNORE_URL_PATTERN.search(request.pretty_url):
        return False
    try:
        parsed = urlsplit(request.pretty_url)
        host = (parsed.hostname or "").lower()
        path = unquote(parsed.path)
        query_keys = {key.lower() for key, _ in parse_qsl(parsed.query, keep_blank_values=True)}
    except (ValueError, UnicodeError):
        return False
    if parsed.username is not None or parsed.password is not None or query_keys & SENSITIVE_QUERY_KEYS:
        return False
    if host == "api.anthropic.com" and path in ANTHROPIC_MODEL_PATHS:
        return True
    if (host.endswith(".googleapis.com") or host == "googleapis.com") and VERTEX_MODEL_PATH.search(path):
        return True
    return False


def codex_http_url(url: str) -> bool:
    try:
        parsed = urlsplit(url)
        return (parsed.scheme == "https" and parsed.hostname == CODEX_WEBSOCKET_HOST
                and parsed.port in (None, 443) and parsed.path == CODEX_WEBSOCKET_PATH
                and not parsed.query and not parsed.fragment
                and parsed.username is None and parsed.password is None)
    except (ValueError, UnicodeError):
        return False


def _codex_websocket_selected(flow: Any) -> bool:
    """Match only Codex's source-verified default ChatGPT Responses socket."""
    request = flow.request
    if request.method.upper() != "GET" or request.pretty_host.lower() != CODEX_WEBSOCKET_HOST:
        return False
    try:
        parsed = urlsplit(request.pretty_url)
        path = unquote(parsed.path)
        query_keys = {key.lower() for key, _ in parse_qsl(parsed.query, keep_blank_values=True)}
    except (ValueError, UnicodeError):
        return False
    return (
        parsed.scheme == "https"
        and parsed.hostname == CODEX_WEBSOCKET_HOST
        and parsed.username is None
        and parsed.password is None
        and path == CODEX_WEBSOCKET_PATH
        and not parsed.query
        and not query_keys & SENSITIVE_QUERY_KEYS
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _headers(headers: Any) -> tuple[dict[str, str], list[str]]:
    result: dict[str, str] = {}
    redacted: list[str] = []
    values = headers.items(multi=True) if hasattr(headers, "items") else headers.items()
    for key, value in values:
        if key.lower() in SENSITIVE_HEADERS:
            result[key] = "[REDACTED]"
            redacted.append(key)
        else:
            result[key] = value
    return result, redacted


def _body(raw: bytes, content_type: str = "", content_encoding: str = "") -> dict[str, Any]:
    encoding = (content_encoding or "identity").lower()
    wire = {
        "encoding": "base64",
        "data": base64.b64encode(raw).decode("ascii"),
        "byte_length": len(raw),
        "content_encoding": encoding,
    }
    decoded_raw = raw
    try:
        if encoding == "gzip":
            decoded_raw = gzip.decompress(raw)
        elif encoding == "deflate":
            decoded_raw = zlib.decompress(raw)
        elif encoding not in {"", "identity"}:
            return {"wire": wire, "decoded": None, "decode_status": "unsupported"}
        text = decoded_raw.decode("utf-8")
        if "json" in content_type:
            decoded = {"kind": "json", "value": json.loads(text)}
        elif "event-stream" in content_type:
            decoded = {"kind": "sse", "value": text}
        else:
            decoded = {"kind": "text", "value": text}
        return {"wire": wire, "decoded": decoded, "decode_status": "decoded"}
    except Exception as exc:
        return {
            "wire": wire,
            "decoded": None,
            "decode_status": "failed",
            "decode_error": f"{type(exc).__name__}: {exc}",
        }


class JsonlEmitter:
    """Serialize events atomically within the mitmproxy process."""

    def __init__(self, path: Path, session_id: str) -> None:
        self.path = path
        self.session_id = session_id
        self.sequence = 0
        self._lock = threading.Lock()

    def emit(self, kind: str, flow_id: str | None, payload: dict[str, Any], redacted: list[str] | None = None, protocol_version: str = HTTP_PROTOCOL_VERSION) -> dict[str, Any]:
        with self._lock:
            self.sequence += 1
            event = {
                "protocol_version": protocol_version,
                "event_id": uuid.uuid4().hex,
                "session_id": self.session_id,
                "sequence": self.sequence,
                "occurred_at": _now(),
                "kind": kind,
                "sanitization": {
                    "applied": True,
                    "policy": "credential-headers-v1",
                    "redacted_fields": sorted(redacted or []),
                },
                "payload": payload,
            }
            if flow_id is not None:
                event["flow_id"] = flow_id
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(event, separators=(",", ":")) + "\n")
                stream.flush()
            return event


class LiveCapture:
    def __init__(self, emitter: JsonlEmitter | None = None, archive_path: Path | None = None) -> None:
        session_id = os.environ.get("CONTEXT_INSPECTOR_SESSION_ID", "unconfigured")
        event_path = Path(os.environ.get("CONTEXT_INSPECTOR_EVENT_FILE", "/tmp/context-inspector-events.jsonl"))
        self.emitter = emitter or JsonlEmitter(event_path, session_id)
        self.archive_path = archive_path or Path(os.environ.get("CAPTURE_FILE", "/tmp/flows.jsonl"))
        self._state: dict[str, dict[str, Any]] = {}
        self._websocket_state: dict[str, dict[str, int]] = {}

    def websocket_start(self, flow: Any) -> None:
        # Do not persist the upgrade request or its headers: they carry auth.
        if _codex_websocket_selected(flow):
            self._websocket_state[flow.id] = {"messages": 0, "archive_failed": False}

    def websocket_message(self, flow: Any) -> None:
        state = self._websocket_state.get(flow.id)
        websocket = getattr(flow, "websocket", None)
        messages = getattr(websocket, "messages", None)
        if state is None or not messages:
            return
        message = messages[-1]
        content = bytes(message.content)
        is_text = bool(message.is_text)
        body = _body(content, "application/json" if is_text else "application/octet-stream")
        if not is_text:
            body["decoded"] = None
            body["decode_status"] = "unsupported"
            body.pop("decode_error", None)
        index = state["messages"]
        state["messages"] += 1
        event = self.emitter.emit("websocket.message", flow.id, {
            "message_index": index,
            "direction": "client_to_server" if message.from_client else "server_to_client",
            "message_type": "text" if is_text else "binary",
            "timestamp": float(message.timestamp),
            "body": body,
        }, protocol_version="1.1")
        if not self._archive_websocket(event):
            state["archive_failed"] = True

    def websocket_end(self, flow: Any) -> None:
        state = self._websocket_state.pop(flow.id, None)
        if state is None:
            return
        websocket = getattr(flow, "websocket", None)
        event = self.emitter.emit("websocket.closed", flow.id, {
            "message_count": state["messages"],
            "close_code": getattr(websocket, "close_code", None),
            "closed_by_client": getattr(websocket, "closed_by_client", None),
            "error": bool(getattr(flow, "error", None)),
            "archive_status": "failed" if state["archive_failed"] else "written",
        }, protocol_version="1.1")
        self._archive_websocket(event)

    def _archive_websocket(self, event: dict[str, Any]) -> bool:
        # Incremental records survive long-running sockets and interrupted runs.
        # No HTTP upgrade headers or URL are included.
        try:
            self.archive_path.parent.mkdir(parents=True, exist_ok=True)
            with self.archive_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps({"record_id": event["event_id"], "transport": "websocket", "event": event}, separators=(",", ":")) + "\n")
            return True
        except OSError:
            return False

    def request(self, flow: http.HTTPFlow) -> None:
        if not _selected(flow):
            return
        request_headers, redacted = _headers(flow.request.headers)
        raw = flow.request.raw_content or b""
        self._state[flow.id] = {
            "request_bytes": len(raw), "request_wire": raw, "request_headers": request_headers,
            "response_bytes": 0, "blocks": 0, "chunks": [], "response_started": False,
        }
        self.emitter.emit("request.started", flow.id, {"request": {
            "method": flow.request.method,
            "url": flow.request.pretty_url,
            "http_version": flow.request.http_version,
            "headers": request_headers,
            "body": _body(raw, flow.request.headers.get("content-type", ""), flow.request.headers.get("content-encoding", "")),
        }}, redacted)

    def responseheaders(self, flow: http.HTTPFlow) -> None:
        if flow.id not in self._state:
            return
        headers, redacted = _headers(flow.response.headers)
        self._state[flow.id]["response_started"] = True
        self._state[flow.id]["response_headers"] = headers
        self.emitter.emit("response.started", flow.id, {
            "status_code": flow.response.status_code,
            "reason": flow.response.reason or "",
            "http_version": flow.response.http_version,
            "headers": headers,
        }, redacted)
        content_type = flow.response.headers.get("content-type", "")
        content_encoding = flow.response.headers.get("content-encoding", "")

        def stream(chunk: bytes) -> bytes:
            state = self._state[flow.id]
            index = state["blocks"]
            offset = state["response_bytes"]
            state["chunks"].append(chunk)
            state["blocks"] += 1
            state["response_bytes"] += len(chunk)
            self.emitter.emit("response.block", flow.id, {
                "block_index": index,
                "offset": offset,
                "body": _body(chunk, content_type, content_encoding),
                "final": len(chunk) == 0,
            })
            return chunk

        flow.response.stream = stream

    def response(self, flow: http.HTTPFlow) -> None:
        if flow.id not in self._state:
            return
        state = self._state.pop(flow.id)
        archive_status: dict[str, Any]
        try:
            record_id = uuid.uuid4().hex
            record = {
                "record_id": record_id,
                "captured_at": _now(),
                "flow_id": flow.id,
                "request": {
                    "method": flow.request.method, "url": flow.request.pretty_url,
                    "http_version": flow.request.http_version, "headers": state["request_headers"],
                    "body": _body(state["request_wire"], flow.request.headers.get("content-type", ""), flow.request.headers.get("content-encoding", "")),
                },
                "response": {
                    "status_code": flow.response.status_code, "reason": flow.response.reason or "",
                    "http_version": flow.response.http_version, "headers": state.get("response_headers", {}),
                    "body": _body(b"".join(state["chunks"]), flow.response.headers.get("content-type", ""), flow.response.headers.get("content-encoding", "")),
                },
            }
            self.archive_path.parent.mkdir(parents=True, exist_ok=True)
            with self.archive_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(record, separators=(",", ":")) + "\n")
            archive_status = {"status": "written", "record_id": record_id}
        except Exception as exc:
            archive_status = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}
        self.emitter.emit("flow.completed", flow.id, {
            "request_body_bytes": state["request_bytes"],
            "response_body_bytes": state["response_bytes"],
            "response_blocks": state["blocks"],
            "archive": archive_status,
        })

    def error(self, flow: http.HTTPFlow) -> None:
        if flow.id in self._websocket_state:
            self.websocket_end(flow)
            return
        if not _selected(flow):
            return
        state = self._state.pop(flow.id, None)
        self.emitter.emit("flow.error", flow.id, {
            "stage": "response" if state else "connect",
            "code": "upstream_error",
            "message": str(flow.error or "Unknown upstream error"),
            "retryable": True,
            "request_observed": state is not None,
            "response_observed": bool(state and state["response_started"]),
        })


addons = [LiveCapture()]
