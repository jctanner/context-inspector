"""Dependency-free validator for Context Inspector live event protocol v1."""

from __future__ import annotations

import base64
import binascii
from datetime import datetime
from typing import Any


PROTOCOL_VERSION = "1.0"
SUPPORTED_PROTOCOL_VERSIONS = {"1.0", "1.1"}
EVENT_KINDS = {
    "request.started",
    "response.started",
    "response.block",
    "flow.completed",
    "flow.error",
    "stream.gap",
    "websocket.message",
    "websocket.closed",
}
SENSITIVE_HEADERS = {
    "authorization",
    "cookie",
    "proxy-authorization",
    "set-cookie",
    "x-api-key",
    "x-goog-api-key",
}
TOP_LEVEL_FIELDS = {
    "protocol_version",
    "event_id",
    "session_id",
    "sequence",
    "occurred_at",
    "kind",
    "flow_id",
    "sanitization",
    "payload",
}


class ProtocolError(ValueError):
    """Raised when a live event violates protocol v1."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ProtocolError(message)


def _exact_keys(value: dict[str, Any], allowed: set[str], path: str) -> None:
    unknown = set(value) - allowed
    _require(not unknown, f"{path} has unknown fields: {sorted(unknown)}")


def _nonempty_string(value: Any, path: str) -> None:
    _require(isinstance(value, str) and bool(value.strip()), f"{path} must be a non-empty string")


def _nonnegative_integer(value: Any, path: str) -> None:
    _require(isinstance(value, int) and not isinstance(value, bool) and value >= 0, f"{path} must be a non-negative integer")


def _timestamp(value: Any) -> None:
    _nonempty_string(value, "occurred_at")
    _require(value.endswith("Z"), "occurred_at must be UTC and end in Z")
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ProtocolError("occurred_at must be an RFC 3339 timestamp") from exc


def _headers(value: Any, path: str) -> None:
    _require(isinstance(value, dict), f"{path} must be an object")
    for name, header_value in value.items():
        _nonempty_string(name, f"{path} header name")
        _require(isinstance(header_value, str), f"{path}.{name} must be a string")
        if name.lower() in SENSITIVE_HEADERS:
            _require(header_value == "[REDACTED]", f"{path}.{name} must be redacted")


def _body(value: Any, path: str) -> None:
    _require(isinstance(value, dict), f"{path} must be an object")
    _exact_keys(value, {"wire", "decoded", "decode_status", "decode_error"}, path)
    _require(value.get("decode_status") in {"decoded", "unsupported", "failed"}, f"{path}.decode_status is invalid")

    wire = value.get("wire")
    _require(isinstance(wire, dict), f"{path}.wire must be an object")
    _exact_keys(wire, {"encoding", "data", "byte_length", "content_encoding"}, f"{path}.wire")
    _require(wire.get("encoding") == "base64", f"{path}.wire.encoding must be base64")
    _require(isinstance(wire.get("data"), str), f"{path}.wire.data must be a string")
    _nonnegative_integer(wire.get("byte_length"), f"{path}.wire.byte_length")
    _nonempty_string(wire.get("content_encoding"), f"{path}.wire.content_encoding")
    try:
        decoded_wire = base64.b64decode(wire["data"], validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ProtocolError(f"{path}.wire.data is not valid base64") from exc
    _require(len(decoded_wire) == wire["byte_length"], f"{path}.wire.byte_length does not match data")

    decoded = value.get("decoded")
    if value["decode_status"] == "decoded":
        _require(isinstance(decoded, dict), f"{path}.decoded is required when decoded")
        _exact_keys(decoded, {"kind", "value"}, f"{path}.decoded")
        _require(decoded.get("kind") in {"json", "text", "sse"}, f"{path}.decoded.kind is invalid")
        if decoded["kind"] in {"text", "sse"}:
            _require(isinstance(decoded.get("value"), str), f"{path}.decoded.value must be a string")
    else:
        _require(decoded is None, f"{path}.decoded must be absent unless decode_status is decoded")
    if "decode_error" in value:
        _require(value["decode_status"] == "failed", f"{path}.decode_error requires failed status")
        _nonempty_string(value["decode_error"], f"{path}.decode_error")


def _request(value: Any) -> None:
    _require(isinstance(value, dict), "payload.request must be an object")
    _exact_keys(value, {"method", "url", "http_version", "headers", "body"}, "payload.request")
    for field in ("method", "url", "http_version"):
        _nonempty_string(value.get(field), f"payload.request.{field}")
    _headers(value.get("headers"), "payload.request.headers")
    _body(value.get("body"), "payload.request.body")


def _validate_payload(kind: str, payload: Any) -> None:
    _require(isinstance(payload, dict), "payload must be an object")
    if kind == "request.started":
        _exact_keys(payload, {"request"}, "payload")
        _request(payload.get("request"))
    elif kind == "response.started":
        _exact_keys(payload, {"status_code", "reason", "http_version", "headers"}, "payload")
        _require(isinstance(payload.get("status_code"), int) and 100 <= payload["status_code"] <= 599, "payload.status_code must be an HTTP status")
        _require(isinstance(payload.get("reason"), str), "payload.reason must be a string")
        _nonempty_string(payload.get("http_version"), "payload.http_version")
        _headers(payload.get("headers"), "payload.headers")
    elif kind == "response.block":
        _exact_keys(payload, {"block_index", "offset", "body", "final"}, "payload")
        _nonnegative_integer(payload.get("block_index"), "payload.block_index")
        _nonnegative_integer(payload.get("offset"), "payload.offset")
        _body(payload.get("body"), "payload.body")
        _require(isinstance(payload.get("final"), bool), "payload.final must be boolean")
    elif kind == "flow.completed":
        _exact_keys(payload, {"request_body_bytes", "response_body_bytes", "response_blocks", "archive"}, "payload")
        for field in ("request_body_bytes", "response_body_bytes", "response_blocks"):
            _nonnegative_integer(payload.get(field), f"payload.{field}")
        archive = payload.get("archive")
        _require(isinstance(archive, dict), "payload.archive must be an object")
        _exact_keys(archive, {"status", "record_id", "error"}, "payload.archive")
        _require(archive.get("status") in {"written", "disabled", "failed"}, "payload.archive.status is invalid")
        if archive["status"] == "written":
            _nonempty_string(archive.get("record_id"), "payload.archive.record_id")
        if "error" in archive:
            _require(archive["status"] == "failed", "payload.archive.error requires failed status")
            _nonempty_string(archive["error"], "payload.archive.error")
    elif kind == "flow.error":
        _exact_keys(payload, {"stage", "code", "message", "retryable", "request_observed", "response_observed"}, "payload")
        _require(payload.get("stage") in {"request", "connect", "response", "archive", "internal"}, "payload.stage is invalid")
        _nonempty_string(payload.get("code"), "payload.code")
        _nonempty_string(payload.get("message"), "payload.message")
        for field in ("retryable", "request_observed", "response_observed"):
            _require(isinstance(payload.get(field), bool), f"payload.{field} must be boolean")
    elif kind == "stream.gap":
        _exact_keys(payload, {"first_missing_sequence", "last_missing_sequence", "reason", "archive_may_recover"}, "payload")
        _nonnegative_integer(payload.get("first_missing_sequence"), "payload.first_missing_sequence")
        _nonnegative_integer(payload.get("last_missing_sequence"), "payload.last_missing_sequence")
        _require(payload["first_missing_sequence"] > 0, "first missing sequence must be positive")
        _require(payload["last_missing_sequence"] >= payload["first_missing_sequence"], "missing sequence interval is reversed")
        _nonempty_string(payload.get("reason"), "payload.reason")
        _require(isinstance(payload.get("archive_may_recover"), bool), "payload.archive_may_recover must be boolean")
    elif kind == "websocket.message":
        _exact_keys(payload, {"message_index", "direction", "message_type", "timestamp", "body"}, "payload")
        _nonnegative_integer(payload.get("message_index"), "payload.message_index")
        _require(payload.get("direction") in {"client_to_server", "server_to_client"}, "payload.direction is invalid")
        _require(payload.get("message_type") in {"text", "binary"}, "payload.message_type is invalid")
        _require(isinstance(payload.get("timestamp"), (int, float)) and not isinstance(payload.get("timestamp"), bool), "payload.timestamp must be numeric")
        _body(payload.get("body"), "payload.body")
    elif kind == "websocket.closed":
        _exact_keys(payload, {"message_count", "close_code", "closed_by_client", "error", "archive_status"}, "payload")
        _nonnegative_integer(payload.get("message_count"), "payload.message_count")
        code = payload.get("close_code")
        _require(code is None or type(code) is int and 1000 <= code <= 4999, "payload.close_code is invalid")
        _require(payload.get("closed_by_client") is None or type(payload["closed_by_client"]) is bool, "payload.closed_by_client is invalid")
        _require(type(payload.get("error")) is bool, "payload.error must be boolean")
        _require(payload.get("archive_status") in {"written", "failed"}, "payload.archive_status is invalid")


def validate_event(event: Any) -> None:
    """Validate one browser-safe protocol v1 event or raise ProtocolError."""

    _require(isinstance(event, dict), "event must be an object")
    _exact_keys(event, TOP_LEVEL_FIELDS, "event")
    version = event.get("protocol_version")
    _require(version in SUPPORTED_PROTOCOL_VERSIONS, "unsupported protocol_version")
    _nonempty_string(event.get("event_id"), "event_id")
    _nonempty_string(event.get("session_id"), "session_id")
    _require(isinstance(event.get("sequence"), int) and not isinstance(event["sequence"], bool) and event["sequence"] > 0, "sequence must be a positive integer")
    _timestamp(event.get("occurred_at"))
    kind = event.get("kind")
    _require(kind in EVENT_KINDS, "kind is not supported")
    _require(version == "1.1" or not kind.startswith("websocket."), "websocket transport requires protocol_version 1.1")

    if kind == "stream.gap":
        _require("flow_id" not in event, "stream.gap must not have flow_id")
    else:
        _nonempty_string(event.get("flow_id"), "flow_id")

    sanitization = event.get("sanitization")
    _require(isinstance(sanitization, dict), "sanitization must be an object")
    _exact_keys(sanitization, {"applied", "policy", "redacted_fields"}, "sanitization")
    _require(sanitization.get("applied") is True, "sanitization must be applied")
    _nonempty_string(sanitization.get("policy"), "sanitization.policy")
    redacted = sanitization.get("redacted_fields")
    _require(isinstance(redacted, list) and all(isinstance(item, str) for item in redacted), "sanitization.redacted_fields must be a string array")

    _validate_payload(kind, event.get("payload"))
