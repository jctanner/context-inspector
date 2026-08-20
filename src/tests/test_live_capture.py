from __future__ import annotations

import gzip
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from src.protocol.events import validate_event
from src.proxy.live_capture import JsonlEmitter, LiveCapture, _body


class Headers(dict):
    def items(self, multi=False):
        return super().items()


def flow(flow_id="flow-1", response_body=b'data: {"type":"done"}\n\n'):
    request = SimpleNamespace(
        method="POST", pretty_url="https://api.anthropic.com/v1/messages",
        pretty_host="api.anthropic.com", http_version="HTTP/2.0",
        headers=Headers({"content-type": "application/json", "Authorization": "secret"}),
        raw_content=b'{"messages":[]}',
    )
    response = SimpleNamespace(
        status_code=200, reason="OK", http_version="HTTP/2.0",
        headers=Headers({"content-type": "text/event-stream", "set-cookie": "secret"}),
        raw_content=response_body, stream=None,
    )
    return SimpleNamespace(id=flow_id, request=request, response=response, error=None)


class LiveCaptureTests(unittest.TestCase):
    def test_json_and_compressed_body_retain_wire_bytes(self) -> None:
        raw = gzip.compress(b'{"answer":42}')
        body = _body(raw, "application/json", "gzip")
        self.assertEqual(body["decoded"]["value"], {"answer": 42})
        self.assertEqual(body["wire"]["byte_length"], len(raw))

    def test_request_stream_and_archive_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            emitter = JsonlEmitter(root / "events.jsonl", "session-test")
            addon = LiveCapture(emitter, root / "archive.jsonl")
            item = flow()
            addon.request(item)
            addon.responseheaders(item)
            self.assertEqual([json.loads(line)["kind"] for line in (root / "events.jsonl").read_text().splitlines()], ["request.started", "response.started"])
            first = b'data: {"type":"message_start"}\n\n'
            second = b'data: {"type":"message_stop"}\n\n'
            self.assertEqual(item.response.stream(first), first)
            self.assertEqual(item.response.stream(second), second)
            addon.response(item)
            events = [json.loads(line) for line in (root / "events.jsonl").read_text().splitlines()]
            for event in events:
                validate_event(event)
            self.assertEqual([event["kind"] for event in events], ["request.started", "response.started", "response.block", "response.block", "flow.completed"])
            self.assertEqual(events[0]["payload"]["request"]["headers"]["Authorization"], "[REDACTED]")
            self.assertEqual(events[1]["payload"]["headers"]["set-cookie"], "[REDACTED]")
            self.assertEqual(b"".join((first, second)), __import__("base64").b64decode(json.loads((root / "archive.jsonl").read_text())["response"]["body"]["wire"]["data"]))

    def test_error_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            addon = LiveCapture(JsonlEmitter(root / "events.jsonl", "session-test"), root / "archive.jsonl")
            item = flow()
            addon.request(item)
            item.error = "connection reset"
            addon.error(item)
            event = json.loads((root / "events.jsonl").read_text().splitlines()[-1])
            validate_event(event)
            self.assertEqual(event["kind"], "flow.error")


if __name__ == "__main__":
    unittest.main()
