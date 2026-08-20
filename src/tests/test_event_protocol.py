from __future__ import annotations

import base64
import copy
import unittest

from src.protocol import ProtocolError, validate_event


def body(raw: bytes = b'{"model":"sonnet"}') -> dict:
    return {
        "wire": {
            "encoding": "base64",
            "data": base64.b64encode(raw).decode("ascii"),
            "byte_length": len(raw),
            "content_encoding": "identity",
        },
        "decoded": {"kind": "json", "value": {"model": "sonnet"}},
        "decode_status": "decoded",
    }


def envelope(kind: str, payload: dict, *, sequence: int = 1, flow: bool = True) -> dict:
    event = {
        "protocol_version": "1.0",
        "event_id": f"event-{sequence}",
        "session_id": "session-test",
        "sequence": sequence,
        "occurred_at": "2026-08-19T18:42:31.123456Z",
        "kind": kind,
        "sanitization": {
            "applied": True,
            "policy": "browser-v1",
            "redacted_fields": ["request.headers.authorization"],
        },
        "payload": payload,
    }
    if flow:
        event["flow_id"] = "flow-test"
    return event


class EventProtocolTests(unittest.TestCase):
    def test_accepts_all_v1_event_kinds(self) -> None:
        events = [
            envelope("request.started", {"request": {
                "method": "POST", "url": "https://example.test/messages",
                "http_version": "HTTP/2.0",
                "headers": {"authorization": "[REDACTED]", "content-type": "application/json"},
                "body": body(),
            }}),
            envelope("response.started", {
                "status_code": 200, "reason": "OK", "http_version": "HTTP/2.0",
                "headers": {"content-type": "text/event-stream"},
            }, sequence=2),
            envelope("response.block", {
                "block_index": 0, "offset": 0, "body": body(b"event: ping\n\n"), "final": False,
            }, sequence=3),
            envelope("flow.completed", {
                "request_body_bytes": 19, "response_body_bytes": 13, "response_blocks": 1,
                "archive": {"status": "written", "record_id": "flows.jsonl:1"},
            }, sequence=4),
            envelope("flow.error", {
                "stage": "response", "code": "upstream_disconnect", "message": "connection closed",
                "retryable": True, "request_observed": True, "response_observed": True,
            }, sequence=5),
            envelope("stream.gap", {
                "first_missing_sequence": 6, "last_missing_sequence": 9,
                "reason": "producer_buffer_overflow", "archive_may_recover": True,
            }, sequence=10, flow=False),
        ]
        for event in events:
            with self.subTest(kind=event["kind"]):
                validate_event(event)

    def test_rejects_unredacted_sensitive_header(self) -> None:
        event = envelope("request.started", {"request": {
            "method": "POST", "url": "https://example.test/messages",
            "http_version": "HTTP/2.0", "headers": {"Authorization": "Bearer secret"},
            "body": body(),
        }})
        with self.assertRaisesRegex(ProtocolError, "must be redacted"):
            validate_event(event)

    def test_rejects_browser_event_without_sanitization(self) -> None:
        event = envelope("flow.error", {
            "stage": "internal", "code": "failure", "message": "safe message",
            "retryable": False, "request_observed": False, "response_observed": False,
        })
        event["sanitization"]["applied"] = False
        with self.assertRaisesRegex(ProtocolError, "must be applied"):
            validate_event(event)

    def test_rejects_wire_length_mismatch(self) -> None:
        event = envelope("response.block", {
            "block_index": 0, "offset": 0, "body": body(b"abc"), "final": True,
        })
        event["payload"]["body"]["wire"]["byte_length"] = 99
        with self.assertRaisesRegex(ProtocolError, "does not match"):
            validate_event(event)

    def test_rejects_flow_id_on_gap(self) -> None:
        event = envelope("stream.gap", {
            "first_missing_sequence": 2, "last_missing_sequence": 3,
            "reason": "replay_expired", "archive_may_recover": True,
        }, flow=False)
        event["flow_id"] = "incorrect"
        with self.assertRaisesRegex(ProtocolError, "must not have flow_id"):
            validate_event(event)

    def test_rejects_unknown_fields(self) -> None:
        event = envelope("flow.completed", {
            "request_body_bytes": 0, "response_body_bytes": 0, "response_blocks": 0,
            "archive": {"status": "disabled"},
        })
        changed = copy.deepcopy(event)
        changed["surprise"] = True
        with self.assertRaisesRegex(ProtocolError, "unknown fields"):
            validate_event(changed)


if __name__ == "__main__":
    unittest.main()
